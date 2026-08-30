# Copyright (C) 2024–present  Loren Eteval & contributors <loren.eteval@proton.me>
#
# This file is part of Furious.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Exercise controller state transitions without real networking side effects."""

from __future__ import annotations

from Furious.Controllers.ConnectionController import (
    ConnectionController,
    ConnectionState,
)
from Furious.Controllers.RoutingController import RoutingController
from Furious.Controllers.SettingsController import SettingsController
from Furious.Frozenlib import AppBinarySettings, AppSettings
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Service.LogManager import LogManager

from PySide6 import QtCore

from tests.support import application, isolatedSettings, processQtEvents

import unittest

from types import SimpleNamespace
from unittest import mock


class ControllerConfiguration(CoreConfiguration):
    """Provide a valid local proxy endpoint for controller-only tests."""

    def httpProxy(self) -> str:
        """Return a deterministic loopback proxy endpoint."""
        return '127.0.0.1:18080'

    def coreName(self) -> str:
        """Return a deterministic core display name."""
        return 'Fixture Core'


class FixtureCoreManager:
    """Record lifecycle calls without launching a subprocess or changing routes."""

    def __init__(
        self,
        *,
        startResult=True,
        startError='',
        startException=None,
        stopException=None,
    ):
        """Initialize deterministic start behavior."""
        self.startResult = startResult
        self.lastStartError = startError
        self.startException = startException
        self.stopException = stopException
        self.runtimes = []
        self.startCalls = []
        self.stopCalls = 0

    def start(self, configuration, **kwargs):
        """Record one requested start and return the configured result."""
        self.startCalls.append((configuration, kwargs))

        if self.startException is not None:
            raise self.startException

        return self.startResult

    def stopAll(self):
        """Record one bounded cleanup operation."""
        self.stopCalls += 1
        self.runtimes.clear()

        if self.stopException is not None:
            raise self.stopException


class FixtureStartOperation(QtCore.QObject):
    """Publish controllable asynchronous startup outcomes."""

    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(object, str, str)
    cancelled = QtCore.Signal(object)

    def succeed(self):
        """Publish one successful manager commit."""
        self.succeeded.emit(self)

    def fail(self, message='fixture failure', details=''):
        """Publish one failed manager transaction."""
        self.failed.emit(self, message, details)


class FixtureAsyncCoreManager:
    """Record controller use of the asynchronous manager boundary."""

    def __init__(self):
        """Initialize empty operation and runtime history."""
        self.lastStartError = ''
        self.runtimes = []
        self.operations = []
        self.cancelCalls = []
        self.stopCalls = 0

    def startAsync(self, configuration, **kwargs):
        """Return one idle operation for the controller to observe."""
        operation = FixtureStartOperation()
        self.operations.append((operation, configuration, kwargs))

        return operation

    def cancelStart(self, operation):
        """Cancel one exact operation."""
        self.cancelCalls.append(operation)
        operation.cancelled.emit(operation)

        return True

    def stopAll(self):
        """Record stable-runtime cleanup."""
        self.stopCalls += 1
        self.runtimes.clear()


class FixtureUpdatesManager:
    """Record update hooks without contacting any update service."""

    def __init__(self):
        """Initialize empty call history."""
        self.proxy = None
        self.checks = 0

    def configureHttpProxy(self, proxy):
        """Record the proxy endpoint passed by post-connect maintenance."""
        self.proxy = proxy

    def checkForUpdates(self, **kwargs):
        """Record a suppressed network update check."""
        self.checks += 1


class ConnectionControllerTest(unittest.TestCase):
    """Verify state and cleanup while all host mutations are patched out."""

    def setUp(self):
        """Install a fresh structured log manager on the test application."""
        self.app = application()
        self.app.logManager = LogManager(parent=self.app)
        self.profile = ServerProfile.fromConfiguration(
            ControllerConfiguration({'type': 'controller-fixture'})
        )

    def tearDown(self):
        """Release the test-owned log manager."""
        manager = self.app.logManager

        self.app.logManager = None

        if manager is not None:
            manager.deleteLater()

        processQtEvents()

    def testSuccessfulConnectionAndDisconnectionStateMachine(self):
        """Publish stable states while using only injected runtime resources."""
        with isolatedSettings():
            core = FixtureCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )
            states = []
            interactions = []
            controller.stateChanged.connect(states.append)
            controller.interactionEnabledChanged.connect(interactions.append)

            with (
                mock.patch(
                    'Furious.Controllers.ConnectionController.SystemProxy.set'
                ) as proxySet,
                mock.patch(
                    'Furious.Controllers.ConnectionController.SystemProxy.off'
                ) as proxyOff,
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                self.assertEqual(controller.state, ConnectionState.Connected)
                self.assertIs(controller.activeProfile, self.profile)
                self.assertEqual(
                    AppSettings.get('Connect'),
                    AppBinarySettings.ON_,
                )

                proxySet.assert_called_once()

                self.assertTrue(controller.startDisconnection('Stopped'))

                proxyOff.assert_called_once()

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertIsNone(controller.activeProfile)
            self.assertEqual(core.stopCalls, 1)
            self.assertEqual(
                states,
                [
                    ConnectionState.Connecting,
                    ConnectionState.Connected,
                    ConnectionState.Disconnecting,
                    ConnectionState.Disconnected,
                ],
            )
            self.assertEqual(interactions, [False, True, False, True])

            controller.deleteLater()

    def testFailedRuntimeStartReturnsToDisconnectedWithError(self):
        """Stop a failed launch and expose one user-facing error object."""
        with isolatedSettings():
            core = FixtureCoreManager(
                startResult=False,
                startError='fixture launch failure',
            )
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )
            errors = []
            notifications = []
            controller.errorOccurred.connect(errors.append)
            controller.notificationRequested.connect(notifications.append)

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertFalse(controller.startConnection(self.profile))

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertEqual(core.stopCalls, 1)
            self.assertIsNone(controller.activeProfile)
            self.assertEqual(
                AppSettings.get('Connect'),
                AppBinarySettings.OFF,
            )
            self.assertEqual(len(errors), 1)
            self.assertIn('fixture launch failure', errors[0].message)
            self.assertEqual(notifications, [])

            controller.deleteLater()

    def testUnexpectedCoreExitUsesStructuredErrorAfterCleanup(self):
        """Queue an unexpected exit, clean the runtime, then publish its error."""
        with isolatedSettings():
            core = FixtureCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )
            events = []
            controller.stateChanged.connect(lambda state: events.append(state.value))
            controller.errorOccurred.connect(lambda error: events.append(error.message))
            process = mock.Mock()
            process.name.return_value = 'Fixture Core'

            controller._setActiveProfile(self.profile)
            controller._startConnecting()

            with mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'):
                controller.coreExitCallback(process, 61)
                controller._callActionFromQueue()

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertEqual(core.stopCalls, 1)
            self.assertIsNone(controller.activeProfile)
            self.assertEqual(events[-2], ConnectionState.Disconnected.value)
            self.assertIn('Fixture Core', events[-1])

            controller.deleteLater()

    def testInvalidProfileNeverCallsRuntimeOrSystemProxy(self):
        """Reject invalid input before any process or host mutation is attempted."""
        with isolatedSettings():
            core = FixtureCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with mock.patch(
                'Furious.Controllers.ConnectionController.SystemProxy.set'
            ) as proxySet:
                self.assertFalse(controller.startConnection(CoreConfiguration()))

            self.assertEqual(core.startCalls, [])

            proxySet.assert_not_called()

            self.assertIsNotNone(controller.lastError)
            self.assertEqual(controller.state, ConnectionState.Disconnected)

            controller.deleteLater()

    def testShutdownPreservesReconnectPreference(self):
        """Stop only the injected runtime while preserving next-start intent."""
        with isolatedSettings():
            core = FixtureCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.set'),
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertTrue(controller.startConnection(self.profile))

                controller.shutdown()

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertEqual(
                AppSettings.get('Connect'),
                AppBinarySettings.ON_,
            )
            self.assertEqual(core.stopCalls, 1)

            controller.deleteLater()

    def testDuplicateStartIsRejectedWithoutASecondRuntime(self):
        """Keep one lifecycle owner while already connected."""
        with isolatedSettings():
            core = FixtureCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.set'),
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                self.assertFalse(controller.startConnection(self.profile))
                self.assertEqual(len(core.startCalls), 1)
                self.assertTrue(controller.startDisconnection())

            controller.deleteLater()

    def testAsyncManagerCommitsSystemProxyOnlyAfterSuccess(self):
        """Remain Connecting until the manager transaction commits."""
        with isolatedSettings():
            core = FixtureAsyncCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch(
                    'Furious.Controllers.ConnectionController.SystemProxy.set'
                ) as proxySet,
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                self.assertTrue(controller.isConnecting())
                proxySet.assert_not_called()

                operation = core.operations[0][0]
                core.runtimes.append(object())
                operation.succeed()

                self.assertTrue(controller.isConnected())
                proxySet.assert_called_once()
                self.assertTrue(controller.startDisconnection())

            controller.deleteLater()

    def testDisconnectCancelsAnInFlightStartupGeneration(self):
        """Cancel partial startup without ever enabling the system proxy."""
        with isolatedSettings():
            core = FixtureAsyncCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch(
                    'Furious.Controllers.ConnectionController.SystemProxy.set'
                ) as proxySet,
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                operation = core.operations[0][0]
                self.assertTrue(controller.startDisconnection())

            self.assertEqual(core.cancelCalls, [operation])
            self.assertTrue(controller.state is ConnectionState.Disconnected)
            proxySet.assert_not_called()

            controller.deleteLater()

    def testReconnectCancelsConnectingGenerationBeforeReplacement(self):
        """Replace a Connecting attempt without accepting stale completion."""
        with isolatedSettings():
            core = FixtureAsyncCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch(
                    'Furious.Controllers.ConnectionController.Storage.UserServers',
                    return_value=[self.profile],
                ),
                mock.patch(
                    'Furious.Controllers.ConnectionController.Storage.UserActivatedItemIndex',
                    return_value=0,
                ),
                mock.patch(
                    'Furious.Controllers.ConnectionController.SystemProxy.set'
                ) as proxySet,
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                first = core.operations[0][0]
                self.assertTrue(controller.startReconnection())
                second = core.operations[1][0]

                first.succeed()
                self.assertTrue(controller.isConnecting())
                proxySet.assert_not_called()

                core.runtimes.append(object())
                second.succeed()
                self.assertTrue(controller.isConnected())
                proxySet.assert_called_once()
                controller.startDisconnection()

            self.assertEqual(core.cancelCalls, [first])

            controller.deleteLater()

    def testStartAndProxyExceptionsReturnToStableDisconnectedState(self):
        """Clean every partially acquired resource after injected failures."""
        for core, proxySideEffect in (
            (FixtureCoreManager(startException=RuntimeError('start')), None),
            (FixtureCoreManager(), RuntimeError('proxy')),
        ):
            with self.subTest(
                startException=core.startException,
                proxyException=proxySideEffect,
            ), isolatedSettings():
                controller = ConnectionController(
                    coreManager=core,
                    updatesManager=FixtureUpdatesManager(),
                )

                with (
                    mock.patch(
                        'Furious.Controllers.ConnectionController.SystemProxy.set',
                        side_effect=proxySideEffect,
                    ),
                    mock.patch(
                        'Furious.Controllers.ConnectionController.SystemProxy.off'
                    ),
                    mock.patch.object(controller, '_runPostConnectTasksOnce'),
                ):
                    self.assertFalse(controller.startConnection(self.profile))

                self.assertEqual(controller.state, ConnectionState.Disconnected)
                self.assertIsNone(controller.activeProfile)
                self.assertEqual(core.stopCalls, 1)
                self.assertFalse(controller._actionTimer.isActive())

                controller.deleteLater()

    def testStopExceptionCannotStrandConnectionControls(self):
        """Complete disconnect even when the runtime reports cleanup failure."""
        with isolatedSettings():
            core = FixtureCoreManager(stopException=RuntimeError('stop'))
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.set'),
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertTrue(controller.startConnection(self.profile))
                self.assertTrue(controller.startDisconnection())

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertIsNone(controller.activeProfile)
            self.assertTrue(controller.interactionEnabled)
            self.assertFalse(controller._actionTimer.isActive())

            controller.deleteLater()

    def testStartupRestorationHonorsPersistedPreference(self):
        """Restore exactly one selected profile only when startup reconnect is on."""
        for reconnect, expectedStarts in ((False, 0), (True, 1)):
            with self.subTest(reconnect=reconnect), isolatedSettings():
                core = FixtureCoreManager()
                controller = ConnectionController(
                    coreManager=core,
                    updatesManager=FixtureUpdatesManager(),
                )

                if reconnect:
                    AppSettings.turnON_('Connect')
                else:
                    AppSettings.turnOFF('Connect')

                with (
                    mock.patch(
                        'Furious.Controllers.ConnectionController.Storage.UserServers',
                        return_value=[self.profile],
                    ),
                    mock.patch(
                        'Furious.Controllers.ConnectionController.Storage.UserActivatedItemIndex',
                        return_value=0,
                    ),
                    mock.patch(
                        'Furious.Controllers.ConnectionController.SystemProxy.set'
                    ),
                    mock.patch(
                        'Furious.Controllers.ConnectionController.SystemProxy.off'
                    ),
                    mock.patch.object(controller, '_runPostConnectTasksOnce'),
                ):
                    self.assertEqual(
                        controller.restoreStartupState(),
                        reconnect,
                    )

                    if controller.isConnected():
                        controller.startDisconnection()

                self.assertEqual(len(core.startCalls), expectedStarts)

                controller.deleteLater()


class RoutingControllerTest(unittest.TestCase):
    """Verify routing follows the connected profile and reconnects once."""

    def setUp(self):
        """Create two distinct profiles for connected and selected state."""
        self.connectedProfile = ServerProfile.fromConfiguration(
            ControllerConfiguration({'type': 'connected'})
        )
        self.selectedProfile = ServerProfile.fromConfiguration(
            ControllerConfiguration({'type': 'selected'})
        )

    def testConnectedConfigurationTakesPriorityOverRepositorySelection(self):
        """Keep routing capabilities bound to the profile actually in use."""
        connectionController = mock.Mock()
        connectionController.activeProfile = self.connectedProfile

        with (
            mock.patch(
                'Furious.Controllers.RoutingController.AppConnectionController',
                return_value=connectionController,
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.Storage.UserActivatedItemIndex',
                return_value=0,
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.Storage.UserServers',
                return_value=[self.selectedProfile],
            ),
        ):
            self.assertIs(
                RoutingController.currentProfileForRouting(),
                self.connectedProfile,
            )

    def testSelectionFallsBackToRepositoryAndReconnectsOnce(self):
        """Persist supported routing and restart the connected runtime once."""
        connectionController = mock.Mock()
        connectionController.activeProfile = None
        connectionController.isConnected.return_value = True
        option = SimpleNamespace(id='fixture-route')
        registry = mock.Mock()
        registry.routingOptions.return_value = (option,)
        registry.normalizeRouting.side_effect = lambda _config, routing: routing

        with (
            isolatedSettings(),
            mock.patch(
                'Furious.Controllers.RoutingController.AppConnectionController',
                return_value=connectionController,
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.Storage.UserActivatedItemIndex',
                return_value=0,
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.Storage.UserServers',
                return_value=[self.selectedProfile],
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.getPluginRegistry',
                return_value=registry,
            ),
        ):
            controller = RoutingController()

            self.assertTrue(controller.selectRouting(option.id))
            self.assertEqual(AppSettings.get('Routing'), option.id)

            connectionController.startReconnection.assert_called_once_with()

            controller.deleteLater()


class SettingsControllerTest(unittest.TestCase):
    """Verify settings apply through application service accessors."""

    def testMetricsSettingUsesTrafficStatisticsService(self):
        """Apply collection state without reaching through a page widget."""
        service = mock.Mock()

        with isolatedSettings(), mock.patch(
            'Furious.Controllers.SettingsController.AppTrafficStatsManager',
            return_value=service,
        ):
            SettingsController.setMetricsCollectionEnabled(False)

            service.setCollectionEnabled.assert_called_once_with(False)

    def testEndpointSettingUsesEndpointInformationService(self):
        """Apply endpoint inspection directly to its long-lived service."""
        service = mock.Mock()

        with isolatedSettings(), mock.patch(
            'Furious.Controllers.SettingsController.AppEndpointInfoService',
            return_value=service,
        ):
            SettingsController.setProxyEndpointInfoEnabled(False)

            service.setEnabled.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
