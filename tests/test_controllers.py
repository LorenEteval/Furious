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
from Furious.Frozenlib import AppBinarySettings, AppSettings
from Furious.Models import ConfigFactory, ServerProfile
from Furious.Service.LogManager import LogManager

from tests.support import application, isolatedSettings, processQtEvents

import unittest

from unittest import mock


class ControllerConfiguration(ConfigFactory):
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
        self.processesPool = []
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
        self.processesPool.clear()

        if self.stopException is not None:
            raise self.stopException


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
                self.assertIs(controller.activeConfiguration, self.profile)
                self.assertEqual(
                    AppSettings.get('Connect'),
                    AppBinarySettings.ON_,
                )

                proxySet.assert_called_once()

                self.assertTrue(controller.startDisconnection('Stopped'))

                proxyOff.assert_called_once()

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertIsNone(controller.activeConfiguration)
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
            controller.errorOccurred.connect(errors.append)

            with (
                mock.patch('Furious.Controllers.ConnectionController.SystemProxy.off'),
                mock.patch.object(controller, '_runPostConnectTasksOnce'),
            ):
                self.assertFalse(controller.startConnection(self.profile))

            self.assertEqual(controller.state, ConnectionState.Disconnected)
            self.assertEqual(core.stopCalls, 1)
            self.assertIsNone(controller.activeConfiguration)
            self.assertEqual(
                AppSettings.get('Connect'),
                AppBinarySettings.OFF,
            )
            # Runtime start failures are currently presented through the
            # disconnection notification path, not the preflight error signal.
            self.assertEqual(errors, [])

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
                self.assertFalse(controller.startConnection(ConfigFactory()))

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
                self.assertIsNone(controller.activeConfiguration)
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
            self.assertIsNone(controller.activeConfiguration)
            self.assertTrue(controller.interactionEnabled)
            self.assertFalse(controller._actionTimer.isActive())

            controller.deleteLater()


if __name__ == '__main__':
    unittest.main()
