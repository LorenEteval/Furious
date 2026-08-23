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

"""Protect the outer application process and command-line dispatch boundaries."""

from __future__ import annotations

from Furious.Interface import ApplicationRunner
from Furious.Utility.AppMainProcess import AppMainProcess

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import importlib
import multiprocessing
import signal
import sys
import tempfile
import unittest

AppMainProcessModule = importlib.import_module('Furious.Utility.AppMainProcess')


class _SuccessfulApplication:
    """Provide one picklable process-boundary application fixture."""

    @staticmethod
    def run() -> int:
        """Return the normal semantic exit code."""
        return ApplicationRunner.ExitCode.ExitSuccess.value

    @staticmethod
    def exit(_exitCode=0):
        """Accept the signal-handler contract without host side effects."""


def _successfulApplication():
    """Return one picklable application fixture in a spawned child."""
    return _SuccessfulApplication()


class AppMainProcessTest(unittest.TestCase):
    """Verify exact child ownership, crash mapping, and signal safety."""

    def testSharedCrashFlagDoesNotCreateAManagerServer(self):
        """Use one synchronized scalar without spawning an unmanaged manager."""
        with mock.patch.object(
            AppMainProcessModule.multiprocessing,
            'Manager',
            side_effect=AssertionError('manager must not be created'),
        ):
            process = AppMainProcess(_successfulApplication)

        try:
            self.assertFalse(process.fileWritten.value)
        finally:
            process.close()

    def testExactApplicationChildExitsWithoutAuxiliaryChildren(self):
        """Start, join, and close only the exact application child."""
        baseline = {child.pid for child in multiprocessing.active_children()}
        process = AppMainProcess(_successfulApplication)

        try:
            process.start()
            process.join(15)

            if process.is_alive():
                process.terminate()
                process.join(5)
                self.fail('application child did not exit within its bound')

            self.assertEqual(process.exitcode, 0)
            self.assertFalse(process.fileWritten.value)
        finally:
            if process.is_alive():
                process.terminate()
                process.join(5)

            process.close()

        remaining = {child.pid for child in multiprocessing.active_children()}

        self.assertEqual(remaining - baseline, set())

    def testExceptionHookPreservesSemanticExitCodes(self):
        """Map assertion and unknown failures without hiding crash-log attempts."""
        for exception, expected in (
            (AssertionError('assertion'), ApplicationRunner.ExitCode.AssertionError),
            (RuntimeError('runtime'), ApplicationRunner.ExitCode.UnknownException),
        ):
            with self.subTest(exception=type(exception).__name__):
                owner = SimpleNamespace(saveCrashLog=mock.Mock())

                with (
                    mock.patch.object(AppMainProcessModule, 'APP', return_value=None),
                    mock.patch.object(
                        AppMainProcessModule.traceback,
                        'print_exception',
                    ),
                    self.assertRaises(SystemExit) as raised,
                ):
                    AppMainProcess.exceptHook(
                        owner,
                        type(exception),
                        exception,
                        exception.__traceback__,
                    )

                self.assertEqual(raised.exception.code, expected.value)
                owner.saveCrashLog.assert_called_once()

    def testExceptionHookUsesPartiallyConstructedApplicationWhenAvailable(self):
        """Request application-owned exit after construction has succeeded."""
        application = SimpleNamespace(exit=mock.Mock())
        owner = SimpleNamespace(saveCrashLog=mock.Mock())
        exception = RuntimeError('runtime')

        with (
            mock.patch.object(
                AppMainProcessModule,
                'APP',
                return_value=application,
            ),
            mock.patch.object(AppMainProcessModule.traceback, 'print_exception'),
        ):
            AppMainProcess.exceptHook(
                owner,
                type(exception),
                exception,
                exception.__traceback__,
            )

        application.exit.assert_called_once_with(
            ApplicationRunner.ExitCode.UnknownException.value
        )

    def testSignalHandlerIsSafeBeforeAndAfterApplicationConstruction(self):
        """Handle the exact signal without dereferencing absent application state."""
        owner = SimpleNamespace(application=None)

        with self.assertRaises(SystemExit) as raised:
            AppMainProcess.handler(owner, signal.SIGTERM, None)

        self.assertEqual(
            raised.exception.code,
            ApplicationRunner.ExitCode.ExitSuccess.value,
        )

        application = SimpleNamespace(exit=mock.Mock())
        owner.application = application

        AppMainProcess.handler(owner, signal.SIGINT, None)

        application.exit.assert_called_once_with()

    def testCrashLogUsesOnlyTheConfiguredTemporaryPath(self):
        """Write one bounded diagnostic file and publish its shared result."""
        owner = SimpleNamespace(
            logFileName='crash.log',
            fileWritten=SimpleNamespace(value=False),
        )

        try:
            raise RuntimeError('diagnostic fixture')
        except RuntimeError:
            exceptionType, exceptionValue, tb = sys.exc_info()

        with tempfile.TemporaryDirectory() as directory:
            crashDirectory = Path(directory) / 'crashes'

            with (
                mock.patch.object(
                    AppMainProcessModule,
                    'CRASH_LOG_DIR',
                    crashDirectory,
                ),
                mock.patch.object(AppMainProcessModule, 'APP', return_value=None),
            ):
                AppMainProcess.saveCrashLog(
                    owner,
                    exceptionType,
                    exceptionValue,
                    tb,
                )

            self.assertTrue(owner.fileWritten.value)
            self.assertIn(
                'diagnostic fixture',
                (crashDirectory / owner.logFileName).read_text(encoding='utf-8'),
            )


class CommandLineDispatchTest(unittest.TestCase):
    """Keep entry-point selection narrow and diagnosable."""

    def setUp(self):
        """Import the module after the test environment is established."""
        self.module = importlib.import_module('Furious.__main__')

    def testClearAndNormalCommandsUseOnlyTheirSelectedPath(self):
        """Dispatch the built-in clear command without starting the GUI child."""
        with (
            mock.patch.object(
                self.module.sys,
                'argv',
                ['Furious', self.module.AppBuiltinCommand.Clear.value],
            ),
            mock.patch.object(self.module, 'runClearSettings') as clear,
            mock.patch.object(self.module, 'runAppMain') as run,
        ):
            self.module.main()

        clear.assert_called_once_with()
        run.assert_not_called()

        with (
            mock.patch.object(self.module.sys, 'argv', ['Furious']),
            mock.patch.object(self.module, 'runClearSettings') as clear,
            mock.patch.object(self.module, 'runAppMain') as run,
        ):
            self.module.main()

        run.assert_called_once_with()
        clear.assert_not_called()

    def testUnexpectedEntrypointFailureUsesStableFallbackExit(self):
        """Keep a bootstrap exception visible and map it to the legacy fallback."""
        with (
            mock.patch.object(self.module.sys, 'argv', ['Furious']),
            mock.patch.object(
                self.module,
                'runAppMain',
                side_effect=RuntimeError('bootstrap fixture'),
            ),
            mock.patch.object(self.module.traceback, 'print_exc') as printException,
            self.assertRaises(SystemExit) as raised,
        ):
            self.module.main()

        self.assertEqual(raised.exception.code, -1)
        printException.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
