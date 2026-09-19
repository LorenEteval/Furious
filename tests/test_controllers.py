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
from Furious.Interface import RuntimeExit, RuntimeExitReason
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Service.LogManager import LogManager

from PySide6 import QtCore

from tests.support import application, isolatedSettings, processQtEvents

import unittest
import importlib

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
                controller.coreExitCallback(
                    process,
                    RuntimeExit(61, RuntimeExitReason.Unexpected),
                )
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

    def testAsyncSemanticStartFailureDoesNotCollapseToUnknownError(self):
        """Preserve one manager-provided semantic error through presentation."""
        with isolatedSettings():
            core = FixtureAsyncCoreManager()
            controller = ConnectionController(
                coreManager=core,
                updatesManager=FixtureUpdatesManager(),
            )

            errors = []
            controller.errorOccurred.connect(errors.append)

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch(
                    'Furious.Controllers.ConnectionController._',
                    side_effect=lambda text: text,
                ),
            ):
                self.assertTrue(controller.startConnection(self.profile))

                operation = core.operations[0][0]
                operation.fail(
                    'Invalid server configuration',
                    'Fixture Core exited during startup with code 23',
                )

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertEqual(len(errors), 1)
            self.assertEqual(
                errors[0].message,
                'Fixture Core: Invalid server configuration',
            )
            self.assertNotIn('Unknown error', errors[0].message)

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

    def testActualProxyHelperFailurePreservesCommittedStartup(self):
        """Keep a usable core connected when best-effort system proxy setup fails."""
        proxyModule = importlib.import_module('Furious.Frozenlib.SystemProxy')

        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous), isolatedSettings():
                core = (
                    FixtureAsyncCoreManager() if asynchronous else FixtureCoreManager()
                )
                controller = ConnectionController(
                    coreManager=core, updatesManager=FixtureUpdatesManager()
                )
                self.addCleanup(controller.deleteLater)

                states = []
                errors = []

                controller.stateChanged.connect(states.append)
                controller.errorOccurred.connect(errors.append)

                with mock.patch.object(
                    proxyModule, 'PLATFORM', 'Linux'
                ), mock.patch.object(
                    proxyModule, 'handleAppSystemProxyMode', return_value=True
                ), mock.patch.object(
                    proxyModule,
                    'linuxProxyConfig',
                    side_effect=OSError('host rejected operation'),
                ), mock.patch.object(
                    controller, '_runPostConnectTasksOnce'
                ) as postConnect:
                    self.assertTrue(controller.startConnection(self.profile))

                    if asynchronous:
                        core.operations[0][0].succeed()

                    processQtEvents()

                    self.assertEqual(controller.state, ConnectionState.Connected)
                    self.assertEqual(states.count(ConnectionState.Connected), 1)
                    self.assertIs(controller.activeProfile, self.profile)
                    self.assertEqual(core.stopCalls, 0)
                    self.assertEqual(errors, [])
                    postConnect.assert_called_once()

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

    def testDisabledCustomRoutingStaysOnFallbackAfterReenable(self):
        """Exercise the real reconnect prompt, tray menu, and routing selector."""
        from Furious.Actions.Routing import RoutingAction
        from Furious.Backends.Configuration import ConfigXray
        from Furious.Backends.Xray.Plugin import XrayPlugin
        from Furious.Backends.Xray.RoutingWindow import UserRoutingTableView
        from Furious.Frozenlib import AppBuiltinRouting
        from Furious.Plugins import PluginRegistry
        from Furious.Qt import AppQMessageBox
        from Furious.Qt.QtWidgets import MBoxNewChangesNextTime
        from Furious.Repository import Storage
        from Furious.Widget.RoutingSelector import RoutingSelector

        app = application()
        with isolatedSettings():
            profile = ServerProfile.fromConfiguration(
                ConfigXray(
                    {
                        'inbounds': [
                            {'protocol': 'http', 'listen': '127.0.0.1', 'port': 18080}
                        ],
                        'outbounds': [{'protocol': 'freedom', 'tag': 'proxy'}],
                    }
                )
            )
            routings = {
                'active': {'remark': 'My routing', 'enabled': True, 'rules': []}
            }
            registry = PluginRegistry()
            registry.register(XrayPlugin())
            core = FixtureCoreManager()
            launchedRoutes = []

            def start(configuration, **kwargs):
                launchedRoutes.append(
                    registry.normalizeRouting(configuration, kwargs['routing'])
                )
                return True

            core.start = start
            connection = ConnectionController(
                coreManager=core, updatesManager=FixtureUpdatesManager()
            )
            logManager = LogManager()
            with (
                mock.patch.object(app, 'connectionController', connection),
                mock.patch.object(app, 'logManager', logManager),
                mock.patch.object(Storage, 'UserRoutings', return_value=routings),
                mock.patch.object(Storage, 'UserServers', return_value=[profile]),
                mock.patch.object(Storage, 'UserActivatedItemIndex', return_value=0),
                mock.patch(
                    'Furious.Controllers.RoutingController.getPluginRegistry',
                    return_value=registry,
                ),
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.set'),
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(connection, '_runPostConnectTasksOnce'),
                mock.patch('sys.excepthook') as exceptionHook,
            ):
                AppSettings.set('Routing', 'Custom:active')
                controller = RoutingController()
                with mock.patch.object(app, 'routingController', controller):
                    view = UserRoutingTableView()
                    tray = RoutingAction(parent=view)
                    selector = RoutingSelector(parent=view)
                    try:
                        self.assertTrue(connection.startConnection(profile))
                        self.assertEqual(launchedRoutes, ['Custom:active'])
                        view.indexWidget(view.sourceModel.index(0, 2)).setCurrentIndex(
                            1
                        )
                        prompt = view.findChild(MBoxNewChangesNextTime)
                        self.assertIsNotNone(prompt)
                        prompt.button(AppQMessageBox.StandardButton.Yes).click()
                        processQtEvents()
                        fallback = AppBuiltinRouting.BypassMainlandChina.value
                        self.assertEqual(launchedRoutes, ['Custom:active', fallback])
                        tray.rebuildMenu()
                        self.assertEqual(controller.routing, fallback)
                        view.indexWidget(view.sourceModel.index(0, 2)).setCurrentIndex(
                            0
                        )
                        tray.rebuildMenu()
                        self.assertEqual(controller.routing, fallback)
                        self.assertEqual(AppSettings.get('Routing'), fallback)
                        self.assertEqual(selector.currentData(), fallback)
                        checked = [
                            action.routingValue
                            for action in tray._menu.actions()
                            if action.isChecked()
                        ]
                        self.assertEqual(checked, [fallback])
                        self.assertEqual(len(launchedRoutes), 2)
                        self.assertEqual(view.findChildren(MBoxNewChangesNextTime), [])

                        customAction = next(
                            action
                            for action in tray._menu.actions()
                            if getattr(action, 'routingValue', None) == 'Custom:active'
                        )
                        customAction.trigger()
                        self.assertEqual(
                            launchedRoutes, ['Custom:active', fallback, 'Custom:active']
                        )
                        self.assertEqual(selector.currentData(), 'Custom:active')
                        view.indexWidget(view.sourceModel.index(0, 2)).setCurrentIndex(
                            1
                        )
                        prompt = view.findChild(MBoxNewChangesNextTime)
                        prompt.button(AppQMessageBox.StandardButton.No).click()
                        processQtEvents()
                        self.assertEqual(len(launchedRoutes), 3)
                        view.indexWidget(view.sourceModel.index(0, 2)).setCurrentIndex(
                            0
                        )
                        tray.rebuildMenu()
                        self.assertEqual(controller.routing, fallback)
                        self.assertEqual(AppSettings.get('Routing'), fallback)
                        self.assertEqual(len(launchedRoutes), 3)
                        exceptionHook.assert_not_called()
                    finally:
                        connection.startDisconnection()
                        view.deleteLater()
                        controller.deleteLater()
                        processQtEvents()
            connection.deleteLater()
            logManager.deleteLater()
            registry.shutdown()
            processQtEvents()

    def testOnlyExplicitInvalidationPersistsFallbackWithoutReconnecting(self):
        """Capability refresh stays observational until a selected choice is revoked."""
        connection = mock.Mock(activeProfile=self.connectedProfile)
        registry = mock.Mock()
        registry.routingOptions.return_value = (SimpleNamespace(id='fallback'),)
        registry.normalizeRouting.return_value = 'fallback'
        with (
            isolatedSettings(),
            mock.patch(
                'Furious.Controllers.RoutingController.AppConnectionController',
                return_value=connection,
            ),
            mock.patch(
                'Furious.Controllers.RoutingController.getPluginRegistry',
                return_value=registry,
            ),
        ):
            AppSettings.set('Routing', 'unavailable')
            controller = RoutingController()
            try:
                controller.refresh(force=True)
                self.assertEqual(controller.routing, 'fallback')
                self.assertEqual(AppSettings.get('Routing'), 'unavailable')
                self.assertFalse(controller.invalidateRouting('other'))
                self.assertEqual(AppSettings.get('Routing'), 'unavailable')
                self.assertTrue(controller.invalidateRouting('unavailable'))
                self.assertEqual(AppSettings.get('Routing'), 'fallback')
                self.assertFalse(controller.invalidateRouting('fallback'))
                connection.startReconnection.assert_not_called()
            finally:
                controller.deleteLater()
                processQtEvents()

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
