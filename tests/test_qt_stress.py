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

"""Measure lifetime and memory trends across hundreds of Qt UI cycles."""

from __future__ import annotations

from Furious.Frozenlib import Mixins
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Qt import AppQAction, AppQMenu, AppQTransientDialog
from Furious.Backends.Hysteria2.Editor import Hysteria2Editor
from Furious.Backends.Xray.RoutingWindow import RoutingPreviewDialog
from Furious.Backends.Xray.VlessEditor import VlessEditor
from Furious.Window.QRCodeWindow import (
    MAXIMUM_QR_EXPORT_PROFILES,
    QRCodeWindow,
)

from PySide6 import QtCore, QtGui

from shiboken6 import isValid

from tests.support import (
    application,
    collectAtBoundary,
    currentRSS,
    currentNativeHandleCount,
    isolatedSettings,
    qObjectCount,
    waitFor,
)

from unittest import mock

import unittest
import weakref
import tracemalloc


class StressDialog(AppQTransientDialog):
    """Own representative actions, a menu, a timer, and signal callbacks."""

    def __init__(self):
        """Create one inexpensive but ownership-rich transient dialog."""
        super().__init__()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

        self.actionsForTest = tuple(
            AppQAction(f'Action {index}', callback=self.update) for index in range(3)
        )

        self.menuForTest = AppQMenu(*self.actionsForTest, parent=self)


class QtMemoryStressTest(unittest.TestCase):
    """Reject linear live-object retention while tolerating allocator caching."""

    WarmupIterations = 40
    BatchIterations = 100
    BatchCount = 3

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    @staticmethod
    def _runBatch(iterations):
        """Create and close a batch without forcing collection per cycle."""
        references, destroyed = [], []

        for _index in range(iterations):
            dialog = StressDialog()
            dialog.destroyed.connect(lambda *_args: destroyed.append(True))

            references.append(weakref.ref(dialog))

            dialog.show()
            dialog.close()

        del dialog

        collectAtBoundary()

        return references, len(destroyed)

    def testThreeHundredCyclesPlateauAfterWarmup(self):
        """Combine direct destruction, pool counts, Python memory, and RSS trend."""
        collectAtBoundary()

        baseline = {
            'dialog': qObjectCount(StressDialog),
            'timer': qObjectCount(QtCore.QTimer),
            'menu': qObjectCount(AppQMenu),
            'action': qObjectCount(AppQAction),
            'translationPool': len(Mixins.QTranslatable.ObjectsPool),
            'themePool': len(Mixins.ThemeAware.ObjectsPool),
            'connectionPool': len(Mixins.ConnectionAware.ObjectsPool),
        }

        tracemalloc.start()

        try:
            warmupReferences, warmupDestroyed = self._runBatch(self.WarmupIterations)
            warmupPython = tracemalloc.get_traced_memory()[0]
            rssSamples = [currentRSS()]
            pythonSamples = [warmupPython]
            liveSamples = [qObjectCount(StressDialog)]
            resourceSamples = [
                {
                    'timer': qObjectCount(QtCore.QTimer),
                    'menu': qObjectCount(AppQMenu),
                    'action': qObjectCount(AppQAction),
                }
            ]
            references = list(warmupReferences)
            destroyed = warmupDestroyed

            for _batch in range(self.BatchCount):
                batchReferences, batchDestroyed = self._runBatch(self.BatchIterations)
                references.extend(batchReferences)
                destroyed += batchDestroyed
                rssSamples.append(currentRSS())
                pythonSamples.append(tracemalloc.get_traced_memory()[0])
                liveSamples.append(qObjectCount(StressDialog))
                resourceSamples.append(
                    {
                        'timer': qObjectCount(QtCore.QTimer),
                        'menu': qObjectCount(AppQMenu),
                        'action': qObjectCount(AppQAction),
                    }
                )

            totalIterations = (
                self.WarmupIterations + self.BatchIterations * self.BatchCount
            )

            self.assertEqual(destroyed, totalIterations)
            self.assertTrue(all(reference() is None for reference in references))
            self.assertEqual(liveSamples, [baseline['dialog']] * 4)

            for resourceSample in resourceSamples:
                self.assertEqual(resourceSample['timer'], baseline['timer'])
                self.assertEqual(resourceSample['menu'], baseline['menu'])
                self.assertEqual(resourceSample['action'], baseline['action'])

            self.assertEqual(
                len(Mixins.QTranslatable.ObjectsPool),
                baseline['translationPool'],
            )
            self.assertEqual(
                len(Mixins.ThemeAware.ObjectsPool),
                baseline['themePool'],
            )
            self.assertEqual(
                len(Mixins.ConnectionAware.ObjectsPool),
                baseline['connectionPool'],
            )

            pythonGrowth = tuple(
                later - earlier
                for earlier, later in zip(pythonSamples, pythonSamples[1:])
            )
            # A persistent leak produces similar positive growth in every
            # post-warm-up batch.  Permit normal tracing/allocator noise, but
            # fail a sustained multi-megabyte trend correlated with no cache
            # stabilization.
            suspiciousPythonGrowth = (
                all(growth > 512 * 1024 for growth in pythonGrowth)
                and sum(pythonGrowth) > 3 * 1024 * 1024
            )

            self.assertFalse(
                suspiciousPythonGrowth,
                f'continued Python retention after warm-up: {pythonSamples}',
            )

            presentRSS = tuple(value for value in rssSamples if value is not None)

            if len(presentRSS) == len(rssSamples):
                rssGrowth = tuple(
                    later - earlier
                    for earlier, later in zip(presentRSS, presentRSS[1:])
                )
                suspiciousRSSGrowth = (
                    all(growth > 4 * 1024 * 1024 for growth in rssGrowth)
                    and sum(rssGrowth) > 16 * 1024 * 1024
                )

                self.assertFalse(
                    suspiciousRSSGrowth,
                    f'continued resident-memory growth after warm-up: {presentRSS}',
                )

            print(
                'Qt lifetime stress:',
                {
                    'widget': StressDialog.__name__,
                    'iterations': totalIterations,
                    'destroyed': destroyed,
                    'liveSamples': liveSamples,
                    'resourceSamples': resourceSamples,
                    'pythonBytes': pythonSamples,
                    'rssBytes': rssSamples,
                },
            )
        finally:
            tracemalloc.stop()

    def testRealDialogFamiliesPlateauAcrossBatches(self):
        """Measure representative production editors instead of only a probe."""
        factories = (
            ('routing-preview', lambda: RoutingPreviewDialog({'rules': []})),
            ('vless-editor', VlessEditor),
            ('hysteria2-editor', Hysteria2Editor),
        )
        warmupIterations, batchIterations, batchCount = 3, 8, 3

        with isolatedSettings():
            for family, factory in factories:
                with self.subTest(family=family):
                    collectAtBoundary()

                    baseline = {
                        'timer': qObjectCount(QtCore.QTimer),
                        'action': qObjectCount(QtGui.QAction),
                        'menu': qObjectCount(AppQMenu),
                        'translationPool': len(Mixins.QTranslatable.ObjectsPool),
                        'themePool': len(Mixins.ThemeAware.ObjectsPool),
                        'connectionPool': len(Mixins.ConnectionAware.ObjectsPool),
                    }

                    references, destroyed, samples = [], [], []

                    for batch, iterations in enumerate(
                        (warmupIterations,) + (batchIterations,) * batchCount
                    ):
                        for _index in range(iterations):
                            dialog = factory()
                            dialog.destroyed.connect(
                                lambda *_args, _destroyed=destroyed: _destroyed.append(
                                    True
                                )
                            )

                            references.append(weakref.ref(dialog))

                            dialog.show()
                            dialog.close()

                        del dialog

                        collectAtBoundary()

                        samples.append(
                            {
                                'batch': batch,
                                'timer': qObjectCount(QtCore.QTimer),
                                'action': qObjectCount(QtGui.QAction),
                                'menu': qObjectCount(AppQMenu),
                                'handles': currentNativeHandleCount(),
                                'rss': currentRSS(),
                            }
                        )

                    total = warmupIterations + batchIterations * batchCount

                    self.assertEqual(len(destroyed), total)
                    self.assertTrue(
                        all(reference() is None for reference in references)
                    )

                    for sample in samples:
                        self.assertEqual(sample['timer'], baseline['timer'])
                        self.assertEqual(sample['action'], baseline['action'])
                        self.assertEqual(sample['menu'], baseline['menu'])

                    self.assertEqual(
                        len(Mixins.QTranslatable.ObjectsPool),
                        baseline['translationPool'],
                    )
                    self.assertEqual(
                        len(Mixins.ThemeAware.ObjectsPool),
                        baseline['themePool'],
                    )
                    self.assertEqual(
                        len(Mixins.ConnectionAware.ObjectsPool),
                        baseline['connectionPool'],
                    )

                    handles = tuple(
                        sample['handles']
                        for sample in samples
                        if sample['handles'] is not None
                    )

                    if len(handles) == len(samples):
                        self.assertLessEqual(max(handles) - min(handles), 4)

                    print(
                        'Qt real-dialog stress:',
                        {
                            'family': family,
                            'iterations': total,
                            'destroyed': len(destroyed),
                            'samples': samples,
                        },
                    )


class QRCodeExportStressTest(unittest.TestCase):
    """Exercise real QR generation, presentation, and cleanup in batches."""

    BatchCount = 3
    ProfilesPerBatch = MAXIMUM_QR_EXPORT_PROFILES

    @classmethod
    def setUpClass(cls):
        """Create the process-wide offscreen QApplication."""
        application()

    def setUp(self):
        """Isolate settings used by top-level window presentation."""
        self.settingsContext = isolatedSettings()
        self.settingsContext.__enter__()

    def tearDown(self):
        """Drain deferred deletion before restoring settings."""
        collectAtBoundary()
        self.settingsContext.__exit__(None, None, None)

    @staticmethod
    def profiles(count: int):
        """Return deterministic profiles for a real QR rendering workload."""
        return [
            ServerProfile.fromConfiguration(
                CoreConfiguration(
                    {'type': 'fixture', 'address': f'node-{index}.example'}
                ),
                {'displayName': f'Profile {index + 1}'},
            )
            for index in range(count)
        ]

    def testRepeatedRealQRCodeBatchesYieldShowAndRelease(self):
        """Render real QR tabs while keeping events and owners observable."""
        collectAtBoundary()
        baselineWindows = qObjectCount(QRCodeWindow)
        windowReferences = []
        windowDestroyed = []

        for batch in range(self.BatchCount):
            profiles = self.profiles(self.ProfilesPerBatch)
            heartbeat = []
            window = QRCodeWindow()
            window.destroyed.connect(lambda *_args: windowDestroyed.append(True))

            with mock.patch(
                'Furious.Window.QRCodeWindow.Storage.UserServers',
                return_value=profiles,
            ), mock.patch(
                'Furious.Window.QRCodeWindow.exportConfiguration',
                side_effect=lambda profile, _batch=batch: (
                    f'socks://node-{_batch}-{profile.itemRemark}.example:1080'
                    f'#Batch-{_batch}'
                ),
            ):
                result = window.startExportByIndex(range(len(profiles)))
                QtCore.QTimer.singleShot(
                    0,
                    lambda _window=window: heartbeat.append(_window.tabCount()),
                )

                self.assertTrue(waitFor(lambda: bool(heartbeat), timeout=5.0))
                self.assertLess(heartbeat[0], len(profiles))
                self.assertIs(result, window)
                self.assertTrue(
                    waitFor(
                        lambda: window.tabCount() > 0,
                        timeout=10.0,
                    )
                )
                self.assertTrue(window.isVisible())
                self.assertTrue(
                    waitFor(lambda: not window.isExporting(), timeout=30.0),
                    'real QR batch did not complete',
                )

            self.assertEqual(window.tabCount(), len(profiles))

            windowReferences.append(weakref.ref(window))
            window.close()
            self.assertTrue(waitFor(lambda: not isValid(window)))

        del result, window
        collectAtBoundary()

        self.assertEqual(windowDestroyed, [True] * self.BatchCount)
        self.assertTrue(all(reference() is None for reference in windowReferences))
        self.assertEqual(qObjectCount(QRCodeWindow), baselineWindows)


if __name__ == '__main__':
    unittest.main()
