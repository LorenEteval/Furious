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

"""Protect the explicit lifecycle and composition refactors."""

from Furious.Application.DesktopApplication import (
    DesktopApplication,
    SingletonApplication,
    _ApplicationCleanupStack,
    _ExistingInstanceResult,
    _SingletonStartupResult,
)
from Furious.Frozenlib import AppBuiltinCommand
from Furious.Interface import ApplicationRunner, CoreRuntime
from Furious.Qt.AppStyleSheet import AppStyleSheet
from Furious.Service.ConnectionManager import ConnectionManager

from PySide6 import QtCore
from PySide6.QtNetwork import QLocalServer

from types import SimpleNamespace
from unittest import TestCase, mock

import importlib
import os
import sys
import tempfile
import textwrap
import subprocess
import time
import uuid

CoreProcessWorkerModule = importlib.import_module('Furious.Core.CoreProcessWorker')


class _Runtime(CoreRuntime):
    """Record exact runtime ownership without starting a host process."""

    def __init__(self):
        super().__init__()

        self.stopCount = 0
        self.disposeCount = 0

    @staticmethod
    def name() -> str:
        return 'Test runtime'

    @staticmethod
    def version() -> str:
        return '0'

    def start(self, *args, **kwargs) -> bool:
        return True

    def stop(self):
        self.stopCount += 1

    def dispose(self):
        self.disposeCount += 1

    def isAlive(self) -> bool:
        return self.stopCount == 0


class ApplicationLifecycleTransactionTest(TestCase):
    """Verify reverse rollback and idempotent exit requests."""

    @staticmethod
    def _application(failureStage=None):
        calls = []
        cleanupStack = _ApplicationCleanupStack()

        def stage(name, *, cleanup=None):
            def run():
                calls.append(name)

                if failureStage == name:
                    raise RuntimeError(f'{name} failed')

                if cleanup is not None:
                    cleanupStack.register(name, lambda: calls.append(cleanup))

            return run

        plugin = SimpleNamespace(shutdown=lambda: calls.append('cleanup plugins'))
        application = SimpleNamespace(
            _cleanupStack=cleanupStack,
            shouldExitForExistingInstance=mock.Mock(return_value=False),
            addEnviron=stage('plugins'),
            addStorage=stage('storage'),
            _initializeControllers=stage('controllers'),
            _cleanupControllers=lambda: calls.append('cleanup controllers'),
            addCustomFont=stage('font'),
            configureLogging=stage('logging'),
            _logRuntimeInformation=stage('runtime information'),
            _initializeThemeDetection=stage('theme detection'),
            _stopThemeDetection=lambda: calls.append('cleanup theme detection'),
            aboutToQuit=SimpleNamespace(connect=mock.Mock()),
            _initializeSystemIntegration=stage('system integration'),
            _initializeUI=stage('application UI'),
            _cleanupUI=lambda: calls.append('cleanup application UI'),
            connectionController=SimpleNamespace(
                restoreStartupState=stage('startup restoration')
            ),
            exec=stage('event loop'),
            _exitRequested=False,
            _exitCode=ApplicationRunner.ExitCode.ExitSuccess.value,
        )
        application.addEnviron = mock.Mock(
            side_effect=(
                RuntimeError('plugins failed')
                if failureStage == 'plugins'
                else lambda: (calls.append('plugins'), plugin)[1]
            )
        )
        application.cleanup = cleanupStack.close

        return application, calls

    def testCleanupStackRunsInReverseAndContinuesAfterFailure(self):
        calls = []
        stack = _ApplicationCleanupStack()
        stack.register('first', lambda: calls.append('first'))

        def failingCleanup():
            calls.append('second')
            raise RuntimeError('expected cleanup failure')

        stack.register('second', failingCleanup)
        stack.register('third', lambda: calls.append('third'))

        with self.assertLogs('Furious.Application.DesktopApplication', level='ERROR'):
            self.assertTrue(stack.close())

        self.assertEqual(calls, ['third', 'second', 'first'])
        self.assertFalse(stack.close())
        self.assertEqual(calls, ['third', 'second', 'first'])

    def testRepeatedExitMakesOneFinalTerminationRequest(self):
        application = SimpleNamespace(
            _exitRequested=False,
            _exitCode=ApplicationRunner.ExitCode.ExitSuccess.value,
            setExitingFlag=mock.Mock(),
            cleanup=mock.Mock(),
        )

        with mock.patch(
            'Furious.Application.DesktopApplication.QtCore.QCoreApplication.exit'
        ) as finalExit:
            DesktopApplication.exit(application, 23)
            DesktopApplication.exit(application, 42)

        application.cleanup.assert_not_called()

        self.assertEqual(application._exitCode, 23)

        finalExit.assert_called_once_with(23)

    def testFirstInstanceClaimsEndpointWithoutRemovingSocket(self):
        """Serialize election, then continue only after the endpoint is owned."""
        electionLock = mock.Mock()
        electionLock.tryLock.return_value = True
        application = SimpleNamespace(
            serverName='test-server',
            _notifyExistingInstance=mock.Mock(
                return_value=_ExistingInstanceResult.Unreachable
            ),
            _singletonElectionLock=mock.Mock(return_value=electionLock),
            _electPrimaryUnderLock=mock.Mock(
                return_value=_SingletonStartupResult.Primary
            ),
            _recoverStaleEndpointAndClaim=mock.Mock(),
            SingletonElectionLockTimeout=3000,
        )

        shouldExit = SingletonApplication.shouldExitForExistingInstance(application)

        self.assertFalse(shouldExit)
        electionLock.tryLock.assert_called_once_with(3000)
        electionLock.unlock.assert_called_once_with()
        application._electPrimaryUnderLock.assert_called_once_with(
            _ExistingInstanceResult.Unreachable
        )
        application._recoverStaleEndpointAndClaim.assert_not_called()

    def testSecondInstanceForwardsCommandWithoutClaimingEndpoint(self):
        """Exit as secondary after forwarding to a reachable primary."""
        application = SimpleNamespace(
            _notifyExistingInstance=mock.Mock(
                return_value=_ExistingInstanceResult.CommandForwarded
            ),
            _singletonElectionLock=mock.Mock(),
        )

        shouldExit = SingletonApplication.shouldExitForExistingInstance(application)

        self.assertTrue(shouldExit)
        application._singletonElectionLock.assert_not_called()

    def testConcurrentListenLoserReprobesWinnerWithoutRecovery(self):
        """Recognize a launcher that wins while this process waits for the lock."""
        application = SimpleNamespace(
            _existingEndpointIsReachable=mock.Mock(return_value=True),
            _listenAsPrimaryInstance=mock.Mock(),
        )

        result = SingletonApplication._electPrimaryUnderLock(
            application,
            _ExistingInstanceResult.Unreachable,
        )

        self.assertIs(result, _SingletonStartupResult.ExistingInstance)
        application._listenAsPrimaryInstance.assert_not_called()

    def testElectionRechecksForConcurrentWinner(self):
        """Never unlink an endpoint that becomes reachable after failed listen."""
        application = SimpleNamespace(
            _existingEndpointIsReachable=mock.Mock(side_effect=(False, True)),
            _listenAsPrimaryInstance=mock.Mock(return_value=False),
        )

        with mock.patch(
            'Furious.Application.DesktopApplication.QLocalServer.removeServer'
        ) as removeServer:
            result = SingletonApplication._electPrimaryUnderLock(
                application,
                _ExistingInstanceResult.Unreachable,
            )

        self.assertIs(result, _SingletonStartupResult.ExistingInstance)
        removeServer.assert_not_called()
        application._listenAsPrimaryInstance.assert_called_once_with()

    def testSingletonRecoveryRemovesOnlyConfirmedStaleEndpoint(self):
        """Remove a stale socket only inside the serialized recovery section."""
        application = SimpleNamespace(
            serverName='test-server',
            _listenAsPrimaryInstance=mock.Mock(return_value=True),
        )

        with mock.patch(
            'Furious.Application.DesktopApplication.QLocalServer.removeServer',
            return_value=True,
        ) as removeServer:
            result = SingletonApplication._recoverStaleEndpointAndClaim(application)

        self.assertIs(result, _SingletonStartupResult.Primary)
        removeServer.assert_called_once_with('test-server')

    def testRecoveryContinuesWhenStaleEndpointIsAlreadyAbsent(self):
        """Allow final listen() to decide ownership when removeServer() returns false."""
        application = SimpleNamespace(
            serverName='test-server',
            _listenAsPrimaryInstance=mock.Mock(return_value=True),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.QLocalServer.removeServer',
                return_value=False,
            ) as removeServer,
            self.assertLogs('Furious.Application.DesktopApplication', level='WARNING'),
        ):
            result = SingletonApplication._recoverStaleEndpointAndClaim(application)

        self.assertIs(result, _SingletonStartupResult.Primary)
        removeServer.assert_called_once_with('test-server')

    def testFinalListenFailureFailsClosed(self):
        """Never continue full startup when final ownership remains uncertain."""
        application = SimpleNamespace(
            serverName='test-server',
            server=SimpleNamespace(errorString=mock.Mock(return_value='address busy')),
            _listenAsPrimaryInstance=mock.Mock(return_value=False),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.QLocalServer.removeServer',
                return_value=True,
            ),
            self.assertLogs('Furious.Application.DesktopApplication', level='ERROR'),
        ):
            result = SingletonApplication._recoverStaleEndpointAndClaim(application)

        self.assertIs(result, _SingletonStartupResult.OwnershipUnresolved)

    def testElectionLockFailuresAreDistinguishedAndFailClosed(self):
        """Differentiate contention, permission, and filesystem election failures."""
        errorLevels = (
            (QtCore.QLockFile.LockError.LockFailedError, 'INFO'),
            (QtCore.QLockFile.LockError.PermissionError, 'ERROR'),
            (QtCore.QLockFile.LockError.UnknownError, 'ERROR'),
        )

        for lockError, logLevel in errorLevels:
            with self.subTest(lockError=lockError):
                electionLock = SimpleNamespace(
                    tryLock=mock.Mock(return_value=False),
                    error=mock.Mock(return_value=lockError),
                    fileName=mock.Mock(return_value='test.lock'),
                    unlock=mock.Mock(),
                )
                application = SimpleNamespace(
                    _notifyExistingInstance=mock.Mock(
                        return_value=_ExistingInstanceResult.Unreachable
                    ),
                    _singletonElectionLock=mock.Mock(return_value=electionLock),
                    _logElectionLockFailure=lambda lock: (
                        SingletonApplication._logElectionLockFailure(lock)
                    ),
                    SingletonElectionLockTimeout=3000,
                )

                with self.assertLogs(
                    'Furious.Application.DesktopApplication', level=logLevel
                ):
                    shouldExit = SingletonApplication.shouldExitForExistingInstance(
                        application
                    )

                self.assertTrue(shouldExit)
                electionLock.unlock.assert_not_called()

    def testElectionLockUsesExplicitStaleIntervalInTemporaryDirectory(self):
        """Configure Qt's automatic crashed-lock cleanup for this short transaction."""
        electionLock = mock.Mock()
        application = SimpleNamespace(
            serverName='test-server',
            SingletonElectionLockStaleTime=30000,
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.QtCore.QStandardPaths.writableLocation',
                return_value='temporary-root',
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.QtCore.QLockFile',
                return_value=electionLock,
            ) as lockFactory,
        ):
            result = SingletonApplication._singletonElectionLock(application)

        self.assertIs(result, electionLock)
        lockFactory.assert_called_once_with(
            os.path.join('temporary-root', 'test-server.lock')
        )
        electionLock.setStaleLockTime.assert_called_once_with(30000)

    def testRunAsWaitsForPrimaryDisconnectBeforeAllowingElection(self):
        """Treat a completed RunAs disconnect as permission to attempt listen()."""
        socket = mock.Mock()
        socket.waitForConnected.return_value = True
        socket.waitForDisconnected.return_value = True
        application = SimpleNamespace(
            serverName='test-server',
            socket=socket,
            ExistingInstanceConnectTimeout=1000,
            RunAsHandoffTimeout=3000,
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.sys.argv',
                ['furious', AppBuiltinCommand.RunAs.value],
            ),
            self.assertLogs('Furious.Application.DesktopApplication', level='INFO'),
        ):
            result = SingletonApplication._notifyExistingInstance(application)

        self.assertIs(result, _ExistingInstanceResult.RunAsHandoffAccepted)
        socket.waitForDisconnected.assert_called_once_with(3000)
        socket.write.assert_called_once_with(AppBuiltinCommand.RunAs.value.encode())

    def testRunAsTimeoutKeepsReplacementFromStarting(self):
        """Fail closed while the original primary still owns the endpoint."""
        socket = mock.Mock()
        socket.waitForConnected.return_value = True
        socket.waitForDisconnected.return_value = False
        application = SimpleNamespace(
            serverName='test-server',
            socket=socket,
            ExistingInstanceConnectTimeout=1000,
            RunAsHandoffTimeout=3000,
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.sys.argv',
                ['furious', AppBuiltinCommand.RunAs.value],
            ),
            self.assertLogs('Furious.Application.DesktopApplication', level='WARNING'),
        ):
            result = SingletonApplication._notifyExistingInstance(application)

        self.assertIs(result, _ExistingInstanceResult.CommandForwarded)

    def testRunAsElectionWaitsForActualEndpointRelease(self):
        """Do not equate command-channel disconnect with endpoint ownership."""
        application = SimpleNamespace(
            serverName='test-server',
            _waitForRunAsEndpointRelease=mock.Mock(return_value=True),
            _existingEndpointIsReachable=mock.Mock(),
            _listenAsPrimaryInstance=mock.Mock(return_value=True),
        )

        result = SingletonApplication._electPrimaryUnderLock(
            application,
            _ExistingInstanceResult.RunAsHandoffAccepted,
        )

        self.assertIs(result, _SingletonStartupResult.Primary)
        application._waitForRunAsEndpointRelease.assert_called_once_with()
        application._existingEndpointIsReachable.assert_not_called()

    def testRunAsElectionFailsClosedWhenEndpointIsNotReleased(self):
        """Reject overlap when the old process does not finish its handoff."""
        application = SimpleNamespace(
            _waitForRunAsEndpointRelease=mock.Mock(return_value=False),
            _listenAsPrimaryInstance=mock.Mock(),
        )

        with self.assertLogs('Furious.Application.DesktopApplication', level='ERROR'):
            result = SingletonApplication._electPrimaryUnderLock(
                application,
                _ExistingInstanceResult.RunAsHandoffAccepted,
            )

        self.assertIs(result, _SingletonStartupResult.OwnershipUnresolved)
        application._listenAsPrimaryInstance.assert_not_called()

    def testEmptyAndUnsupportedCommandsRemainSecondaryLaunches(self):
        """Forward empty and future commands without creating another primary."""
        for arguments, expectedCommand in (
            (['furious'], AppBuiltinCommand.Empty.value),
            (['furious', 'future-command'], 'future-command'),
        ):
            with self.subTest(arguments=arguments):
                socket = mock.Mock()
                socket.waitForConnected.return_value = True
                application = SimpleNamespace(
                    serverName='test-server',
                    socket=socket,
                    ExistingInstanceConnectTimeout=1000,
                    RunAsHandoffTimeout=3000,
                )

                with mock.patch(
                    'Furious.Application.DesktopApplication.sys.argv', arguments
                ):
                    result = SingletonApplication._notifyExistingInstance(application)

                self.assertIs(result, _ExistingInstanceResult.CommandForwarded)
                socket.write.assert_called_once_with(expectedCommand.encode())

    def testUnreachableEndpointDoesNotWriteACommand(self):
        """Report no primary when connectToServer cannot establish a channel."""
        socket = mock.Mock()
        socket.waitForConnected.return_value = False
        application = SimpleNamespace(
            serverName='test-server',
            socket=socket,
            ExistingInstanceConnectTimeout=1000,
        )

        result = SingletonApplication._notifyExistingInstance(application)

        self.assertIs(result, _ExistingInstanceResult.Unreachable)
        socket.write.assert_not_called()

    def testDisappearingConnectionFailsClosedWithoutStartingRecovery(self):
        """Treat a failed command write as evidence of an existing owner."""
        socket = mock.Mock()
        socket.waitForConnected.return_value = True
        socket.write.return_value = -1
        socket.errorString.return_value = 'peer closed'
        application = SimpleNamespace(
            serverName='test-server',
            socket=socket,
            ExistingInstanceConnectTimeout=1000,
            RunAsHandoffTimeout=3000,
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.sys.argv',
                ['furious'],
            ),
            self.assertLogs('Furious.Application.DesktopApplication', level='WARNING'),
        ):
            probeResult = SingletonApplication._notifyExistingInstance(application)

        self.assertIs(
            probeResult,
            _ExistingInstanceResult.CommandDeliveryUncertain,
        )

        election = SimpleNamespace(
            _notifyExistingInstance=mock.Mock(return_value=probeResult),
            _singletonElectionLock=mock.Mock(),
        )

        self.assertTrue(SingletonApplication.shouldExitForExistingInstance(election))
        election._singletonElectionLock.assert_not_called()

    def testStartupResultMapsUncertainOwnershipToExit(self):
        """Return the explicit primary state only after listen succeeds."""
        application = SimpleNamespace(
            serverName='test-server',
            _existingEndpointIsReachable=mock.Mock(return_value=False),
            _listenAsPrimaryInstance=mock.Mock(return_value=True),
        )

        result = SingletonApplication._electPrimaryUnderLock(
            application,
            _ExistingInstanceResult.Unreachable,
        )

        self.assertIs(result, _SingletonStartupResult.Primary)

    def testRecoveryResultControlsFinalStartupDecision(self):
        """Enter recovery only for the explicit stale-endpoint state."""
        electionLock = mock.Mock()
        electionLock.tryLock.return_value = True
        application = SimpleNamespace(
            _notifyExistingInstance=mock.Mock(
                return_value=_ExistingInstanceResult.Unreachable
            ),
            _singletonElectionLock=mock.Mock(return_value=electionLock),
            _electPrimaryUnderLock=mock.Mock(
                return_value=_SingletonStartupResult.RecoveryRequired
            ),
            _recoverStaleEndpointAndClaim=mock.Mock(
                return_value=_SingletonStartupResult.Primary
            ),
            SingletonElectionLockTimeout=3000,
        )

        self.assertFalse(
            SingletonApplication.shouldExitForExistingInstance(application)
        )
        application._recoverStaleEndpointAndClaim.assert_called_once_with()
        electionLock.unlock.assert_called_once_with()

    def testConcurrentProcessesElectExactlyOnePrimary(self):
        """Exercise the real Qt local-server race with isolated processes."""
        serverName = f'furious-singleton-test-{uuid.uuid4()}'
        script = textwrap.dedent(r"""
            import os
            import sys
            import time

            os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

            from PySide6 import QtCore

            from Furious.Application.DesktopApplication import SingletonApplication


            class RaceApplication(SingletonApplication):
                @QtCore.Slot()
                def handleNewConnection(self):
                    while self.server.hasPendingConnections():
                        socket = self.server.nextPendingConnection()

                        if socket is None:
                            continue

                        socket.waitForReadyRead(1000)
                        socket.readAll()
                        socket.disconnectFromServer()
                        socket.deleteLater()
                        QtCore.QTimer.singleShot(100, self.quit)


            server_name, barrier, participant = sys.argv[1:]
            application = RaceApplication([sys.argv[0]])
            application.serverName = server_name

            with open(f'{barrier}.{participant}.ready', 'w', encoding='utf-8'):
                pass

            deadline = time.monotonic() + 10

            while not os.path.exists(barrier):
                if time.monotonic() >= deadline:
                    raise RuntimeError('race barrier was not released')

                time.sleep(0.01)

            should_exit = application.shouldExitForExistingInstance()
            print(
                'SINGLETON_RESULT:secondary'
                if should_exit
                else 'SINGLETON_RESULT:primary',
                flush=True,
            )

            if not should_exit:
                # Keep the authoritative endpoint alive until the contender
                # connects.  The longer timer is only a bounded test fallback.
                QtCore.QTimer.singleShot(8000, application.quit)
                application.exec()
                application.server.close()
            """)
        environment = os.environ.copy()
        environment['QT_QPA_PLATFORM'] = 'offscreen'
        processes = []

        with tempfile.TemporaryDirectory() as temporaryDirectory:
            barrier = os.path.join(temporaryDirectory, 'start')

            try:
                participants = ('one', 'two', 'three', 'four')

                for participant in participants:
                    processes.append(
                        subprocess.Popen(
                            [
                                sys.executable,
                                '-c',
                                script,
                                serverName,
                                barrier,
                                participant,
                            ],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=environment,
                            text=True,
                        )
                    )

                deadline = time.monotonic() + 10
                readyPaths = tuple(
                    f'{barrier}.{participant}.ready' for participant in participants
                )

                while not all(os.path.exists(path) for path in readyPaths):
                    if time.monotonic() >= deadline:
                        self.fail('singleton race participants did not become ready')

                    time.sleep(0.01)

                with open(barrier, 'w', encoding='utf-8'):
                    pass

                outputs = []

                for process in processes:
                    stdout, stderr = process.communicate(timeout=15)
                    outputs.append(stdout)
                    self.assertEqual(
                        process.returncode,
                        0,
                        f'child failed:\n{stdout}{stderr}',
                    )
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()

                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)

                QLocalServer.removeServer(serverName)

        results = [
            line
            for output in outputs
            for line in output.splitlines()
            if line.startswith('SINGLETON_RESULT:')
        ]

        self.assertCountEqual(
            results,
            (
                'SINGLETON_RESULT:primary',
                'SINGLETON_RESULT:secondary',
                'SINGLETON_RESULT:secondary',
                'SINGLETON_RESULT:secondary',
            ),
            outputs,
        )

    def testUnavailableTrayShowsMainWindowAndEnablesWindowQuit(self):
        """Run normally without a desktop tray instead of rejecting Linux."""
        mainWindow = mock.Mock()
        trayFactory = mock.Mock()
        trayFactory.isSystemTrayAvailable.return_value = False
        application = SimpleNamespace(
            applyThemePreference=mock.Mock(),
            mainWindow=None,
            systemTray=None,
            setQuitOnLastWindowClosed=mock.Mock(),
            _cleanupUI=mock.Mock(),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.MainWindow',
                return_value=mainWindow,
            ),
            mock.patch('Furious.Application.DesktopApplication.TrayIcon', trayFactory),
            mock.patch('Furious.Application.DesktopApplication.PLATFORM', 'Linux'),
        ):
            DesktopApplication._initializeUI(application)

        application.setQuitOnLastWindowClosed.assert_called_once_with(True)
        mainWindow.show.assert_called_once_with()
        self.assertIsNone(application.systemTray)
        trayFactory.assert_not_called()

    def testAvailableTrayPreservesBackgroundApplicationBehavior(self):
        """Retain the existing tray-owned startup path when a tray is present."""
        mainWindow = mock.Mock()
        tray = mock.Mock()
        trayFactory = mock.Mock(return_value=tray)
        trayFactory.isSystemTrayAvailable.return_value = True
        application = SimpleNamespace(
            applyThemePreference=mock.Mock(),
            mainWindow=None,
            systemTray=None,
            setQuitOnLastWindowClosed=mock.Mock(),
            _cleanupUI=mock.Mock(),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.MainWindow',
                return_value=mainWindow,
            ),
            mock.patch('Furious.Application.DesktopApplication.TrayIcon', trayFactory),
            mock.patch('Furious.Application.DesktopApplication.PLATFORM', 'Linux'),
        ):
            DesktopApplication._initializeUI(application)

        application.setQuitOnLastWindowClosed.assert_called_once_with(False)
        mainWindow.show.assert_not_called()
        tray.show.assert_called_once_with()
        tray.setCustomToolTip.assert_called_once_with()
        tray.bootstrap.assert_called_once_with()

    def testSuccessfulRunAcquiresEveryStageOnceAndCleansUpInReverse(self):
        application, calls = self._application()

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.TrayIcon.isSystemTrayAvailable',
                return_value=True,
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.Mixins.CleanupOnExit.cleanupAll',
                side_effect=lambda: calls.append('cleanup storage'),
            ),
        ):
            result = DesktopApplication.run(application)

        self.assertIsNone(result)
        self.assertEqual(calls.count('plugins'), 1)
        self.assertEqual(calls.count('event loop'), 1)
        self.assertEqual(
            calls[-5:],
            [
                'cleanup application UI',
                'cleanup theme detection',
                'cleanup controllers',
                'cleanup storage',
                'cleanup plugins',
            ],
        )

    def testSystemIntegrationOwnsTheWindowsSessionListener(self):
        cleanupStack = _ApplicationCleanupStack()
        shutdownSignal = SimpleNamespace(emit=mock.Mock())
        application = SimpleNamespace(
            _cleanupStack=cleanupStack,
            _sessionShutdownRequested=shutdownSignal,
            setQuitOnLastWindowClosed=mock.Mock(),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.Win32Session.set',
                return_value=True,
            ) as setCallback,
            mock.patch(
                'Furious.Application.DesktopApplication.Win32Session.run',
                return_value=True,
            ) as runListener,
            mock.patch(
                'Furious.Application.DesktopApplication.Win32Session.off',
                return_value=True,
            ) as stopListener,
            mock.patch(
                'Furious.Application.DesktopApplication.AppSettings.get',
                return_value='manual',
            ),
        ):
            DesktopApplication._initializeSystemIntegration(application)
            cleanupStack.close()

        setCallback.assert_called_once_with(shutdownSignal.emit)
        runListener.assert_called_once_with()
        stopListener.assert_called_once_with()

    def testSystemIntegrationSkipsWindowsProxyDaemonOnMacOS(self):
        """Do not register a nonexistent native proxy-daemon resource on macOS."""
        cleanupStack = _ApplicationCleanupStack()
        application = SimpleNamespace(
            _cleanupStack=cleanupStack,
            _sessionShutdownRequested=SimpleNamespace(emit=mock.Mock()),
            setQuitOnLastWindowClosed=mock.Mock(),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.Win32Session.set',
                return_value=False,
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.AppSettings.get',
                return_value='Auto',
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.PLATFORM',
                'Darwin',
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.off'
            ) as proxyOff,
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.daemonOn_'
            ) as daemonOn,
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.daemonOff'
            ) as daemonOff,
        ):
            DesktopApplication._initializeSystemIntegration(application)
            cleanupStack.close()

        proxyOff.assert_called_once_with()
        daemonOn.assert_not_called()
        daemonOff.assert_not_called()

    def testSystemIntegrationOwnsOnlyWindowsProxyDaemonCleanup(self):
        """Keep OS proxy state under the connection controller's ownership."""
        cleanupStack = _ApplicationCleanupStack()
        application = SimpleNamespace(
            _cleanupStack=cleanupStack,
            _sessionShutdownRequested=SimpleNamespace(emit=mock.Mock()),
            setQuitOnLastWindowClosed=mock.Mock(),
        )

        with (
            mock.patch(
                'Furious.Application.DesktopApplication.Win32Session.set',
                return_value=False,
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.AppSettings.get',
                return_value='Auto',
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.PLATFORM',
                'Windows',
            ),
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.off'
            ) as proxyOff,
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.daemonOn_'
            ) as daemonOn,
            mock.patch(
                'Furious.Application.DesktopApplication.SystemProxy.daemonOff'
            ) as daemonOff,
        ):
            DesktopApplication._initializeSystemIntegration(application)
            cleanupStack.close()

        proxyOff.assert_called_once_with()
        daemonOn.assert_called_once_with()
        daemonOff.assert_called_once_with()

    def testProcessOutputRedirectorDoesNotDelayCoreEntrypoint(self):
        """Begin the core immediately while its file reader drains early output."""

        class _Stream:
            def __init__(self, descriptor):
                self.descriptor = descriptor

            def fileno(self):
                return self.descriptor

            def close(self):
                pass

        class _TemporaryDir:
            def __init__(self, directory):
                self.directory = directory

            def isValid(self):
                return True

            def filePath(self, name):
                return os.path.join(self.directory, name)

        with tempfile.TemporaryDirectory() as directory:
            thread = SimpleNamespace(start=mock.Mock())
            entrypoint = mock.Mock()
            fakeSys = SimpleNamespace(stdout=_Stream(1), stderr=_Stream(2))

            with (
                mock.patch.object(
                    CoreProcessWorkerModule.SystemRuntime,
                    'isPythonw',
                    return_value=False,
                ),
                mock.patch.object(
                    CoreProcessWorkerModule.ProcessOutputRedirector,
                    'TemporaryDir',
                    _TemporaryDir(directory),
                ),
                mock.patch.object(CoreProcessWorkerModule, 'sys', fakeSys),
                mock.patch.object(CoreProcessWorkerModule.os, 'dup2'),
                mock.patch.object(
                    CoreProcessWorkerModule.threading,
                    'Thread',
                    return_value=thread,
                ),
                mock.patch.object(CoreProcessWorkerModule.time, 'sleep') as sleep,
            ):
                CoreProcessWorkerModule.ProcessOutputRedirector.launch(
                    mock.Mock(), entrypoint, True
                )

        sleep.assert_not_called()
        thread.start.assert_called_once_with()
        entrypoint.assert_called_once_with()

    def testCoreLogQueueIsBoundedAndTruncatesBeforeTransport(self):
        """Drop excess burst output instead of retaining an unbounded backlog."""
        received = []
        messageQueue = CoreProcessWorkerModule.MsgQueue(
            msgCallback=received.append,
            maximumPendingMessages=4,
        )

        try:
            oversized = 'x' * (
                CoreProcessWorkerModule.MsgQueue.MAXIMUM_MESSAGE_CHARACTERS + 100
            )
            accepted = [
                messageQueue.putMessage(oversized if index == 0 else str(index))
                for index in range(20)
            ]

            self.assertLessEqual(sum(accepted), 4)

            for _ in range(20):
                messageQueue.processMsg()
                if received:
                    break
                QtCore.QThread.msleep(5)

            self.assertTrue(received)
            self.assertLessEqual(
                len(received[0]),
                CoreProcessWorkerModule.MsgQueue.MAXIMUM_MESSAGE_CHARACTERS,
            )
        finally:
            messageQueue.dispose()

    def testCoreLogQueueBacksOffWhileIdleAndRecoversOnActivity(self):
        """Poll rapidly during output and progressively less often while idle."""
        received = []
        messageQueue = CoreProcessWorkerModule.MsgQueue(msgCallback=received.append)

        try:
            messageQueue.getNoWait = mock.Mock(return_value='')

            expectedTimeouts = (32, 64, 128, 256, 256)

            for expectedTimeout in expectedTimeouts:
                messageQueue.processMsg()
                self.assertEqual(messageQueue.getTimeout(), expectedTimeout)
                self.assertEqual(messageQueue.timer.interval(), expectedTimeout)

            messageQueue.getNoWait = mock.Mock(side_effect=('message', ''))
            messageQueue.processMsg()

            self.assertEqual(received, ['message'])
            self.assertEqual(
                messageQueue.getTimeout(),
                CoreProcessWorkerModule.MsgQueue.ACTIVE_DRAIN_INTERVAL,
            )
            self.assertEqual(
                messageQueue.timer.interval(),
                CoreProcessWorkerModule.MsgQueue.ACTIVE_DRAIN_INTERVAL,
            )
        finally:
            messageQueue.dispose()

    def testFailuresAtMeaningfulStagesRollBackOnlyEarlierStages(self):
        expected = {
            'storage': ['cleanup storage', 'cleanup plugins'],
            'controllers': ['cleanup storage', 'cleanup plugins'],
            'theme detection': [
                'cleanup controllers',
                'cleanup storage',
                'cleanup plugins',
            ],
            'application UI': [
                'cleanup theme detection',
                'cleanup controllers',
                'cleanup storage',
                'cleanup plugins',
            ],
        }

        for failureStage, cleanupCalls in expected.items():
            with self.subTest(failureStage=failureStage):
                application, calls = self._application(failureStage)

                with (
                    mock.patch(
                        'Furious.Application.DesktopApplication.TrayIcon.isSystemTrayAvailable',
                        return_value=True,
                    ),
                    mock.patch(
                        'Furious.Application.DesktopApplication.Mixins.CleanupOnExit.cleanupAll',
                        side_effect=lambda: calls.append('cleanup storage'),
                    ),
                    mock.patch(
                        'Furious.Application.DesktopApplication.traceback.print_exc'
                    ),
                ):
                    result = DesktopApplication.run(application)

                self.assertEqual(
                    result,
                    ApplicationRunner.ExitCode.UnknownException.value,
                )
                self.assertEqual(
                    [call for call in calls if call.startswith('cleanup')],
                    cleanupCalls,
                )

    def testDesktopApplicationFinalizesWithoutNativeSessionCallback(self):
        """Exercise the real run/finalization boundary in a clean child process."""
        if sys.platform != 'win32':
            self.skipTest('the former native-session finalizer bug was Windows-only')

        script = textwrap.dedent("""
            import sys
            from types import SimpleNamespace

            from PySide6 import QtCore
            from PySide6.QtWidgets import QWidget

            from Furious.Application import DesktopApplication
            from Furious.Application.TrayIcon import TrayIcon


            class ProbeApplication(DesktopApplication):
                def shouldExitForExistingInstance(self):
                    return False

                def addEnviron(self):
                    return SimpleNamespace(shutdown=lambda: None)

                def addStorage(self):
                    pass

                def _initializeControllers(self):
                    class Controller(QtCore.QObject):
                        def restoreStartupState(self):
                            pass

                        def shutdown(self):
                            pass

                    self.connectionController = Controller(self)
                    self.routingController = QtCore.QObject(self)
                    self.settingsController = None

                def addCustomFont(self):
                    pass

                def configureLogging(self):
                    pass

                def _logRuntimeInformation(self):
                    pass

                def _initializeThemeDetection(self):
                    pass

                def _initializeSystemIntegration(self):
                    self.setQuitOnLastWindowClosed(False)

                def _initializeUI(self):
                    self.mainWindow = QWidget()
                    self.systemTray = None
                    self.mainWindow.show()


            TrayIcon.isSystemTrayAvailable = staticmethod(lambda: True)
            application = ProbeApplication(sys.argv)
            QtCore.QTimer.singleShot(0, application.exit)
            raise SystemExit(application.run())
            """)

        environment = os.environ.copy()
        environment['QT_QPA_PLATFORM'] = 'offscreen'

        for cycle in range(5):
            result = subprocess.run(
                [sys.executable, '-c', script],
                capture_output=True,
                env=environment,
                text=True,
                timeout=20,
            )

            self.assertEqual(
                result.returncode,
                0,
                f'finalization cycle {cycle + 1}:\n{result.stdout}{result.stderr}',
            )


class ConnectionStartupTransactionTest(TestCase):
    """Verify one failed attempt releases only its own exact runtimes."""

    def testDnsResolverIsAcquiredLazilyAndReleasedByTheManager(self):
        """Avoid constructing a Qt network manager before QApplication exists."""
        resolver = mock.Mock()
        manager = ConnectionManager()

        with mock.patch(
            'Furious.Service.ConnectionManager.DnsResolver',
            return_value=resolver,
        ) as resolverFactory:
            resolverFactory.assert_not_called()
            self.assertIs(manager._connectionDnsResolver(), resolver)
            self.assertIs(manager._connectionDnsResolver(), resolver)

        resolverFactory.assert_called_once_with()

        manager.cleanup()

        resolver.dispose.assert_called_once_with()
        self.assertIsNone(manager._dnsResolver)

    @staticmethod
    def _start(manager, runtime, *, success):
        with (
            mock.patch.object(
                manager,
                '_prepareTUNPolicy',
                return_value=(False, False),
            ),
            mock.patch.object(
                manager,
                '_startCoreRuntime',
                return_value=(runtime, success),
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=False,
            ),
        ):
            return manager.start(object(), '', deepcopy=False)

    def testFailedPrimaryRuntimeDoesNotStopEarlierOwnedRuntime(self):
        manager = ConnectionManager()
        existing = _Runtime()
        failed = _Runtime()
        manager.runtimes.append(existing)

        self.assertFalse(self._start(manager, failed, success=False))
        self.assertEqual(manager.runtimes, [existing])
        self.assertEqual(existing.stopCount, 0)
        self.assertEqual(failed.stopCount, 1)
        self.assertEqual(failed.disposeCount, 1)

    def testUnexpectedLaterStageFailureRollsBackThePrimaryRuntime(self):
        manager = ConnectionManager()
        runtime = _Runtime()

        with (
            mock.patch.object(
                manager,
                '_prepareTUNPolicy',
                return_value=(False, True),
            ),
            mock.patch.object(
                manager,
                '_startCoreRuntime',
                return_value=(runtime, True),
            ),
            mock.patch.object(
                manager,
                '_startApplicationTun2socks',
                side_effect=RuntimeError('host setup failed'),
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=True,
            ),
            self.assertRaisesRegex(RuntimeError, 'host setup failed'),
        ):
            manager.start(object(), '', deepcopy=False)

        self.assertEqual(manager.runtimes, [])
        self.assertEqual(runtime.stopCount, 1)
        self.assertEqual(runtime.disposeCount, 1)

    def testSuccessfulAttemptCommitsRuntimeOwnership(self):
        manager = ConnectionManager()
        runtime = _Runtime()

        self.assertTrue(self._start(manager, runtime, success=True))
        self.assertEqual(manager.runtimes, [runtime])
        self.assertEqual(runtime.stopCount, 0)

        manager.stopAll()

    def testRuntimeRemainsAttemptOwnedUntilEveryStageSucceeds(self):
        manager = ConnectionManager()
        existing = _Runtime()
        primary = _Runtime()
        manager.runtimes.append(existing)
        observedOwnership = []

        def startApplicationTun2socks(attempt, *args):
            observedOwnership.append((tuple(manager.runtimes), tuple(attempt.runtimes)))

            return True

        with (
            mock.patch.object(
                manager,
                '_prepareTUNPolicy',
                return_value=(False, True),
            ),
            mock.patch.object(
                manager,
                '_startCoreRuntime',
                return_value=(primary, True),
            ),
            mock.patch.object(
                manager,
                '_startApplicationTun2socks',
                side_effect=startApplicationTun2socks,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=True,
            ),
        ):
            self.assertTrue(manager.start(object(), '', deepcopy=False))

        self.assertEqual(observedOwnership, [((existing,), (primary,))])
        self.assertEqual(manager.runtimes, [existing, primary])


class StyleSheetCompositionTest(TestCase):
    """Keep the public stylesheet complete after internal source splitting."""

    def testBothThemesContainEveryRepresentativeComponentFamily(self):
        selectors = (
            'QMainWindow,',
            'QToolTip {',
            'QPushButton {',
            'QTableView,',
            'QScrollBar:vertical {',
            'QProgressBar {',
        )

        for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
            with self.subTest(theme=theme):
                stylesheet = AppStyleSheet.forTheme(theme)

                for selector in selectors:
                    self.assertIn(selector, stylesheet)

                self.assertEqual(stylesheet.count('QToolTip {'), 1)
                self.assertEqual(stylesheet.count('QTableView,'), 1)

    def testComboBoxDropDownHoverStaysInsideTheFocusBorder(self):
        """Keep the arrow hover fill from covering the outer focus outline."""
        for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
            with self.subTest(theme=theme):
                stylesheet = AppStyleSheet.forTheme(theme)
                dropDownRule = stylesheet.split('QComboBox::drop-down {', 1)[1]
                dropDownRule = dropDownRule.split('}', 1)[0]

                self.assertIn('subcontrol-origin: padding;', dropDownRule)

    def testSpinBoxButtonHoverStaysInsideTheFocusBorder(self):
        """Keep both spin-button hover fills inside the outer focus outline."""
        selectors = (
            'QSpinBox::up-button,',
            'QSpinBox::down-button,',
        )

        for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
            stylesheet = AppStyleSheet.forTheme(theme)

            for selector in selectors:
                with self.subTest(theme=theme, selector=selector):
                    buttonRule = stylesheet.split(selector, 1)[1]
                    buttonRule = buttonRule.split('}', 1)[0]

                    self.assertIn('subcontrol-origin: padding;', buttonRule)
