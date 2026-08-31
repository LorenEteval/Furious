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

"""Provide an explicit release-confidence tier for sustained churn."""

from __future__ import annotations

from Furious.Backends.ExternalCore import ConfigExternalCore, ExternalCoreProcess
from Furious.Interface import ApplicationRunner
from Furious.Models import CoreConfiguration, LogCategory, ServerProfile
from Furious.Plugins import FuriousPlugin, PluginMetadata, PluginRegistry
from Furious.Qt import AppQDialog, AppQMessageBox, AppQTransientDialog
from Furious.Utility import AppMainProcess
from Furious.Service import APPLICATION_LOG_CATEGORY, LogManager, MetricsHistory
from Furious.Widget import NavigationView
from Furious.Window.QRCodeWindow import QRCodeWindow

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    resourceSnapshot,
    veryHeavyEnabled,
    waitFor,
)

from importlib import import_module
from pathlib import Path
from unittest import mock

import gc
import multiprocessing
import sys
import tempfile
import threading
import unittest
import weakref

qrCodeModule = import_module('Furious.Window.QRCodeWindow')


class _ReleaseApplication:
    """Provide one picklable successful application-process fixture."""

    @staticmethod
    def run() -> int:
        """Return the normal semantic application exit code."""
        return ApplicationRunner.ExitCode.ExitSuccess.value


def _releaseApplication():
    """Return one application fixture inside the spawned child."""
    return _ReleaseApplication()


@unittest.skipUnless(
    veryHeavyEnabled(),
    'set FURIOUS_VERY_HEAVY_TESTS=1 for release-confidence stress tests',
)
class VeryHeavyContractTest(unittest.TestCase):
    """Exercise high-count pure and Qt ownership contracts on explicit request."""

    @classmethod
    def setUpClass(cls):
        """Create the one process-lifetime test application."""
        application()

    def tearDown(self):
        """Drain deferred deletion before the next sustained workload."""
        collectAtBoundary()

    def testFiveThousandPluginLifecyclesReleaseEachRegistry(self):
        """Register, shut down, and collect independent plugin owners."""
        stopped = 0
        pluginReferences = []
        registryReferences = []
        snapshots = []

        class FixturePlugin(FuriousPlugin):
            """Expose metadata only and record exact lifecycle completion."""

            def __init__(self, index):
                """Give every plugin one non-conflicting stable identity."""
                self.metadata = PluginMetadata(f'tests.heavy.{index}', 'Heavy')

            def shutdown(self):
                """Record the registry-owned shutdown callback."""
                nonlocal stopped
                stopped += 1

        for index in range(5_000):
            registry = PluginRegistry()
            plugin = FixturePlugin(index)
            registry.register(plugin)
            registry.shutdown()

            pluginReferences.append(weakref.ref(plugin))
            registryReferences.append(weakref.ref(registry))

            del plugin, registry

            if (index + 1) % 1_000 == 0:
                gc.collect()
                snapshots.append(resourceSnapshot())

        gc.collect()

        self.assertEqual(stopped, 5_000)
        self.assertTrue(all(reference() is None for reference in pluginReferences))
        self.assertTrue(all(reference() is None for reference in registryReferences))
        self.assertEqual(snapshots[-1]['threads'], snapshots[0]['threads'])

    def testOneHundredApplicationChildrenLeaveNoAuxiliaryProcesses(self):
        """Repeat the exact outer child boundary without manager processes."""
        baselineChildren = {child.pid for child in multiprocessing.active_children()}
        baseline = resourceSnapshot()
        snapshots = []

        for index in range(100):
            process = AppMainProcess(_releaseApplication)

            try:
                process.start()
                process.join(15)

                if process.is_alive():
                    process.terminate()
                    process.join(5)
                    self.fail(f'application child {index} exceeded its timeout')

                self.assertEqual(process.exitcode, 0)
                self.assertFalse(process.fileWritten.value)
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(5)

                process.close()

            if (index + 1) % 20 == 0:
                snapshots.append(resourceSnapshot())

        remainingChildren = {
            child.pid for child in multiprocessing.active_children()
        }.difference(baselineChildren)

        self.assertEqual(remainingChildren, set())
        self.assertEqual(snapshots[-1]['threads'], baseline['threads'])

    def testOneHundredExternalCoreCyclesReapPipesAndThreads(self):
        """Sustain the real harmless subprocess lifecycle at release scale."""
        baselineThreads = {thread.ident for thread in threading.enumerate()}
        baseline = resourceSnapshot()
        snapshots = []

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            configuration = ConfigExternalCore(
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
                for index in range(100):
                    self.assertTrue(runtime.start(configuration))
                    process = runtime.process

                    self.assertIsNotNone(process)
                    self.assertTrue(runtime.isAlive())

                    runtime.stop()

                    self.assertFalse(runtime.isAlive())
                    self.assertIsNone(runtime.process)
                    self.assertFalse(runtime._readerThreads)
                    self.assertIsNone(runtime._watcherThread)
                    self.assertIsNotNone(process.poll())

                    if (index + 1) % 20 == 0:
                        snapshots.append(resourceSnapshot())
            finally:
                runtime.dispose()

        remainingThreads = {
            thread.ident
            for thread in threading.enumerate()
            if thread.ident not in baselineThreads
        }

        self.assertEqual(remainingThreads, set())
        self.assertEqual(snapshots[-1]['threads'], baseline['threads'])

        baselineHandles = baseline['handles']
        handles = tuple(
            snapshot['handles']
            for snapshot in snapshots
            if snapshot['handles'] is not None
        )

        if baselineHandles is not None and len(handles) == len(snapshots):
            self.assertLessEqual(
                max((*handles, baselineHandles)) - baselineHandles,
                4,
            )

    def testOneHundredThousandMetricsRemainTimeBounded(self):
        """Prune a long monotonic stream to the configured history window."""
        history = MetricsHistory(maximumHistorySeconds=1_000)

        for sampledAt in range(100_000):
            history.recordSample(
                {'network.download.speed': sampledAt},
                sampledAt=sampledAt,
            )

        samples = history.rawSamples()

        self.assertEqual(len(samples), 1_001)
        self.assertEqual(samples[0].sampledAt, 98_999)
        self.assertEqual(samples[-1].sampledAt, 99_999)

        history.deleteLater()

    def testConcurrentFortyThousandLogsHaveOneTotalOrder(self):
        """Preserve every entry exactly once under concurrent producers."""
        manager = LogManager(maximumEntries=40_000, autoClearEnabled=False)
        manager.registerCategory(LogCategory('tests.concurrent', 'Concurrent'))
        baselineThreads = resourceSnapshot()['threads']
        workers = []

        def appendBatch(workerIndex):
            """Append one disjoint producer range through the public API."""
            for entryIndex in range(5_000):
                manager.append(
                    f'{workerIndex}:{entryIndex}',
                    'tests.concurrent',
                )

        for workerIndex in range(8):
            worker = threading.Thread(target=appendBatch, args=(workerIndex,))
            worker.start()
            workers.append(worker)

        for worker in workers:
            worker.join(30)
            self.assertFalse(worker.is_alive())

        entries = manager.entries('tests.concurrent')

        self.assertEqual(len(entries), 40_000)
        self.assertEqual(len({entry.message for entry in entries}), 40_000)
        self.assertEqual(
            tuple(entry.sequence for entry in entries),
            tuple(range(1, 40_001)),
        )
        self.assertEqual(resourceSnapshot()['threads'], baselineThreads)

        manager.deleteLater()

    def testTwentyThousandNavigationSwitchesPreserveOnePage(self):
        """Switch existing pages without allocating replacement widgets."""
        navigation = NavigationView()
        pages = []

        for index in range(16):
            page = QWidget(parent=navigation)
            pages.append(page)
            navigation.addPage(
                f'page-{index}',
                page,
                f'Page {index}',
                'house-door.svg',
            )

        navigation.show()
        processQtEvents()

        for index in range(20_000):
            navigation.setCurrentPage(f'page-{index % len(pages)}')

            if (index + 1) % 2_000 == 0:
                processQtEvents()

        self.assertEqual(navigation.currentPageId(), 'page-15')
        self.assertIs(navigation.pageStack.currentWidget(), pages[-1])
        self.assertEqual(navigation.pageStack.count(), len(pages))

        navigation.close()
        navigation.deleteLater()

    def testOneThousandTransientDialogsLeaveNoRegistryEntries(self):
        """Open and destroy dialogs in batches without retaining wrappers."""
        references = []
        baseline = resourceSnapshot()

        for index in range(1_000):
            dialog = AppQTransientDialog()
            references.append(weakref.ref(dialog))
            dialog.show()
            dialog.close()
            dialog.deleteLater()

            if (index + 1) % 50 == 0:
                collectAtBoundary()

        del dialog
        collectAtBoundary()

        self.assertTrue(all(reference() is None for reference in references))
        self.assertFalse(AppQTransientDialog._openDialogs)
        self.assertEqual(resourceSnapshot()['threads'], baseline['threads'])

    def testFiveHundredMessageBoxesLeaveNoRegistryEntries(self):
        """Exercise shared asynchronous dialog ownership at release scale."""
        references = []

        for index in range(500):
            messageBox = AppQMessageBox(
                icon=AppQMessageBox.Icon.Information,
                text=f'Message {index}',
                buttons=AppQMessageBox.StandardButton.Ok,
            )
            references.append(weakref.ref(messageBox))
            messageBox.show()
            messageBox.accept()
            messageBox.deleteLater()

            if (index + 1) % 25 == 0:
                collectAtBoundary()

        del messageBox
        collectAtBoundary()

        self.assertTrue(all(reference() is None for reference in references))
        self.assertFalse(AppQDialog._openDialogs)

    def testOneThousandRealQRCodeTabsYieldShowAndReleaseOwners(self):
        """Render a release-scale QR window without starving or retaining Qt owners."""
        count = 1_000
        profiles = [
            ServerProfile.fromConfiguration(
                CoreConfiguration(
                    {'type': 'fixture', 'address': f'node-{index}.example'}
                ),
                {'displayName': f'Profile {index + 1}'},
            )
            for index in range(count)
        ]
        heartbeat = []
        windowDestroyed = []

        with isolatedSettings(), mock.patch.object(
            qrCodeModule,
            'MAXIMUM_QR_EXPORT_PROFILES',
            count,
        ), mock.patch.object(
            qrCodeModule.Storage,
            'UserServers',
            return_value=profiles,
        ), mock.patch.object(
            qrCodeModule,
            'exportConfiguration',
            side_effect=lambda profile: (
                f'socks://{profile.itemRemark}.example:1080#Release-QR'
            ),
        ):
            window = QRCodeWindow()
            window.destroyed.connect(lambda *_args: windowDestroyed.append(True))
            result = window.startExportByIndex(range(count))
            windowReference = weakref.ref(window)

            QtCore.QTimer.singleShot(
                0,
                lambda: heartbeat.append(window.tabCount()),
            )

            self.assertTrue(waitFor(lambda: bool(heartbeat), timeout=5.0))
            self.assertLess(heartbeat[0], count)
            self.assertIs(result, window)
            self.assertTrue(
                waitFor(
                    lambda: window.tabCount() > 0,
                    timeout=10.0,
                )
            )
            self.assertTrue(window.isVisible())
            self.assertTrue(
                waitFor(lambda: not window.isExporting(), timeout=300.0),
                'release-scale QR export did not complete',
            )
            self.assertEqual(window.tabCount(), count)

            window.close()
            self.assertTrue(waitFor(lambda: not isValid(window)))

        del result, window
        collectAtBoundary()

        self.assertEqual(windowDestroyed, [True])
        self.assertIsNone(windowReference())


if __name__ == '__main__':
    unittest.main()
