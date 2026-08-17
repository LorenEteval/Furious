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

"""Stress the harmless Python-backed external-core lifecycle."""

from __future__ import annotations

from Furious.Backends.ExternalCore import ConfigExternalCore, ExternalCoreProcess

from tests.support import currentNativeHandleCount, currentRSS

from pathlib import Path

import sys
import tempfile
import threading
import unittest


class ExternalProcessStressTest(unittest.TestCase):
    """Reject subprocess, pipe, and reader-thread growth across many restarts."""

    def testTwentyFourStartStopCyclesReleaseNativeResources(self):
        """Reap the exact child and return reader/watcher ownership every cycle."""
        baselineThreads = {thread.ident for thread in threading.enumerate()}
        baselineHandles = currentNativeHandleCount()
        samples = []

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = ConfigExternalCore(
                {
                    'type': 'external-core',
                    'executable': str(Path(sys.executable).resolve()),
                    'workingDirectory': directory,
                    'arguments': ['-u', '-c', 'import time; time.sleep(60)'],
                    'environment': {},
                    'httpProxy': '127.0.0.1:10809',
                    'socksProxy': '127.0.0.1:10808',
                    'shutdownTimeout': 1,
                }
            )
            runtime = ExternalCoreProcess()

            try:
                for index in range(24):
                    self.assertTrue(runtime.start(config))

                    process = runtime.process

                    self.assertIsNotNone(process)
                    self.assertTrue(runtime.isAlive())

                    runtime.stop()

                    self.assertFalse(runtime.isAlive())
                    self.assertIsNone(runtime.process)
                    self.assertFalse(runtime._readerThreads)
                    self.assertIsNone(runtime._watcherThread)
                    self.assertIsNotNone(process.poll())

                    if index % 6 == 5:
                        samples.append(
                            {
                                'cycle': index + 1,
                                'handles': currentNativeHandleCount(),
                                'rss': currentRSS(),
                                'threads': len(threading.enumerate()),
                            }
                        )
            finally:
                runtime.dispose()

        remainingThreads = {
            thread.ident
            for thread in threading.enumerate()
            if thread.ident not in baselineThreads
        }

        self.assertEqual(remainingThreads, set())

        handles = tuple(
            sample['handles'] for sample in samples if sample['handles'] is not None
        )

        if baselineHandles is not None and len(handles) == len(samples):
            self.assertLessEqual(max((*handles, baselineHandles)) - baselineHandles, 4)

        print('External process stress:', {'cycles': 24, 'samples': samples})


if __name__ == '__main__':
    unittest.main()
