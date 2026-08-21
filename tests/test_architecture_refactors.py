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
    _ApplicationCleanupStack,
)
from Furious.Interface import ApplicationRunner, CoreRuntime
from Furious.Qt.AppStyleSheet import AppStyleSheet
from Furious.Service.ConnectionManager import ConnectionManager

from PySide6 import QtCore

from types import SimpleNamespace
from unittest import TestCase, mock

import os
import sys
import textwrap
import subprocess


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
