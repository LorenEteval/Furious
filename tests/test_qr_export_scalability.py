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

"""Exercise bounded, incremental QR export with real Qt delivery."""

from __future__ import annotations

from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Window.QRCodeWindow import (
    MAXIMUM_QR_EXPORT_PROFILES,
    QRCodeWindow,
    captureQRCodeExportItems,
)

from PySide6 import QtCore
from PySide6.QtGui import QImage

from shiboken6 import isValid

from unittest import mock

import segno
import unittest
import weakref

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    waitFor,
)


class QRCodeExportScalabilityTest(unittest.TestCase):
    """Verify QR export remains bounded, responsive, stable, and disposable."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide offscreen QApplication."""
        application()

    def setUp(self):
        """Isolate settings used by top-level window presentation."""
        self.settingsContext = isolatedSettings()
        self.settingsContext.__enter__()

    def tearDown(self):
        """Drain deferred window deletion before restoring settings."""
        collectAtBoundary()
        self.settingsContext.__exit__(None, None, None)

    @staticmethod
    def profile(index: int) -> ServerProfile:
        """Return one independent deterministic profile fixture."""
        return ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture', 'address': f'{index}.example'}),
            {'displayName': f'Profile {index + 1}'},
        )

    @classmethod
    def profiles(cls, count: int) -> list[ServerProfile]:
        """Return the requested deterministic profile list."""
        return [cls.profile(index) for index in range(count)]

    @staticmethod
    def qrImage(*_args) -> QImage:
        """Return a small valid square image for orchestration-only tests."""
        image = QImage(29, 29, QImage.Format.Format_Grayscale8)
        image.fill(255)

        return image

    def testCaptureLimitForOneFiftyFiftyOneAndThousands(self):
        """Snapshot no more than fifty profiles regardless of selection size."""
        for selectedCount in (1, 50, 51, 2000):
            with self.subTest(selectedCount=selectedCount):
                profiles = []

                for index in range(selectedCount):
                    profile = mock.Mock(itemRemark=f'Profile {index + 1}')
                    profile.deepcopy.return_value = mock.Mock()
                    profiles.append(profile)

                items = captureQRCodeExportItems(
                    range(selectedCount),
                    profiles=profiles,
                )
                expected = min(selectedCount, MAXIMUM_QR_EXPORT_PROFILES)

                self.assertEqual(len(items), expected)
                self.assertEqual(
                    sum(profile.deepcopy.call_count for profile in profiles),
                    expected,
                )

                if selectedCount > MAXIMUM_QR_EXPORT_PROFILES:
                    self.assertTrue(
                        all(
                            profile.deepcopy.call_count == 0
                            for profile in profiles[MAXIMUM_QR_EXPORT_PROFILES:]
                        )
                    )

    def testSingleProfileExportRemainsImmediate(self):
        """Keep one-profile export synchronous without scheduling a batch."""
        profiles = self.profiles(1)
        window = QRCodeWindow()

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            return_value='socks://single.example:1080#Single',
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            result = window.startExportByIndex([0])

        self.assertIs(result, window)
        self.assertFalse(window.isExporting())
        self.assertEqual(window.exportProcessedCount(), 1)
        self.assertEqual(window.exportGeneratedCount(), 1)
        self.assertEqual(window.tabCount(), 1)
        self.assertTrue(window.isVisible())

        window.close()

    def testOperationAttemptsAtMostTheProductionCap(self):
        """Attempt exactly the captured count and discard an empty result window."""
        for selectedCount in (50, 51, 1000):
            with self.subTest(selectedCount=selectedCount):
                profiles = self.profiles(selectedCount)
                window = QRCodeWindow()
                appendExportItem = mock.Mock(return_value=False)
                window.appendExportItem = appendExportItem

                with mock.patch(
                    'Furious.Window.QRCodeWindow.Storage.UserServers',
                    return_value=profiles,
                ):
                    result = window.startExportByIndex(range(selectedCount))

                expected = min(selectedCount, MAXIMUM_QR_EXPORT_PROFILES)

                self.assertIs(result, window)
                self.assertEqual(appendExportItem.call_count, 0)
                self.assertTrue(
                    waitFor(lambda: not isValid(window), timeout=5.0),
                    'empty QR operation did not close',
                )
                self.assertEqual(appendExportItem.call_count, expected)

    def testGenerationYieldsToAnUnrelatedQtEvent(self):
        """Deliver unrelated work after one attempt and before batch completion."""
        profiles = self.profiles(6)
        attempts = []
        marker = []
        window = QRCodeWindow()

        def export(profile):
            """Record one exported snapshot."""
            attempts.append(profile.itemRemark)

            return f'socks://{len(attempts)}.example:1080#Fixture'

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=export,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            result = window.startExportByIndex(range(len(profiles)))
            QtCore.QTimer.singleShot(0, lambda: marker.append(len(attempts)))

            self.assertIs(result, window)
            self.assertEqual(attempts, [])
            self.assertTrue(window.isVisible())
            self.assertTrue(waitFor(lambda: bool(marker)))
            self.assertEqual(marker, [1])
            self.assertTrue(waitFor(lambda: not window.isExporting()))

        self.assertEqual(len(attempts), len(profiles))
        self.assertEqual(window.exportProcessedCount(), len(profiles))
        self.assertEqual(window.exportGeneratedCount(), len(profiles))
        self.assertEqual(window.tabCount(), len(profiles))

        window.close()

    def testClosingBeforeFirstItemCancelsTheBatch(self):
        """Close the retained result window before its first scheduled attempt."""
        profiles = self.profiles(5)
        attempts = []
        window = QRCodeWindow()

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=lambda profile: attempts.append(profile) or 'fixture',
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            window.startExportByIndex(range(len(profiles)))
            self.assertEqual(window.tabCount(), 0)
            window.close()
            processQtEvents()

        self.assertEqual(attempts, [])
        self.assertTrue(waitFor(lambda: not isValid(window)))

    def testClosingMidwayStopsNewTabs(self):
        """Retain no window after close prevents the next scheduled attempt."""
        for closeAfter in (3, 49):
            with self.subTest(closeAfter=closeAfter):
                profiles = self.profiles(50)
                attempts = []
                window = QRCodeWindow()

                def export(profile):
                    """Schedule window close immediately after the target attempt."""
                    attempts.append(profile.itemRemark)

                    if len(attempts) == closeAfter:
                        QtCore.QTimer.singleShot(0, window.close)

                    return f'socks://{len(attempts)}.example:1080#Fixture'

                with mock.patch(
                    'Furious.Window.QRCodeWindow.Storage.UserServers',
                    return_value=profiles,
                ), mock.patch(
                    'Furious.Window.QRCodeWindow.exportConfiguration',
                    side_effect=export,
                ), mock.patch(
                    'Furious.Window.QRCodeWindow.createQRCodeImage',
                    side_effect=self.qrImage,
                ):
                    window.startExportByIndex(range(len(profiles)))
                    self.assertTrue(waitFor(lambda: not isValid(window)))

                self.assertEqual(len(attempts), closeAfter)

                processQtEvents()
                self.assertEqual(len(attempts), closeAfter)

    def testIndividualFailuresPreserveValidTabs(self):
        """Continue after exporter, empty-data, and QR-overflow failures."""
        profiles = self.profiles(4)
        attempts = []
        window = QRCodeWindow()

        def export(profile):
            """Return each representative exporter outcome."""
            attempts.append(profile.itemRemark)

            if profile.itemRemark == 'Profile 1':
                raise RuntimeError('fixture exporter failure')

            if profile.itemRemark == 'Profile 2':
                return ''

            if profile.itemRemark == 'Profile 3':
                return 'overflow'

            return 'socks://valid.example:1080#Valid'

        def createImage(uri):
            """Raise only for the representative oversized payload."""
            if uri == 'overflow':
                raise segno.DataOverflowError('fixture overflow')

            return self.qrImage()

        with self.assertLogs(
            'Furious.Window.QRCodeWindow', level='WARNING'
        ), mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=export,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=createImage,
        ):
            window.startExportByIndex(range(len(profiles)))
            self.assertTrue(waitFor(lambda: not window.isExporting()))

        self.assertEqual(len(attempts), 4)
        self.assertEqual(window.exportProcessedCount(), 4)
        self.assertEqual(window.exportGeneratedCount(), 1)
        self.assertEqual(window.tabCount(), 1)
        self.assertEqual(window.tabWidget.tabText(0), '4 - Profile 4')

        window.close()

    def testRepositoryMutationCannotRetargetCapturedProfiles(self):
        """Export the initial snapshots after their source collection is replaced."""
        profiles = self.profiles(5)
        originalRemarks = [profile.itemRemark for profile in profiles]
        exportedRemarks = []
        window = QRCodeWindow()

        def export(profile):
            """Observe the immutable operation snapshot."""
            exportedRemarks.append(profile.itemRemark)

            return f'socks://{len(exportedRemarks)}.example:1080#Fixture'

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=export,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            window.startExportByIndex(range(len(profiles)))

            for profile in profiles:
                profile.metadata.displayName = 'Mutated'

            profiles.reverse()
            profiles.clear()

            self.assertTrue(waitFor(lambda: not window.isExporting()))

        self.assertEqual(exportedRemarks, originalRemarks)
        self.assertEqual(
            [window.tabWidget.tabText(index) for index in range(window.tabCount())],
            [f'{index + 1} - {remark}' for index, remark in enumerate(originalRemarks)],
        )

        window.close()

    def testClosingQRCodeWindowCancelsAndDestroysTheOperation(self):
        """Stop after the first tab when the QR window closes during generation."""
        profiles = self.profiles(8)
        attempts = []
        window = QRCodeWindow()
        windowReference = weakref.ref(window)

        def export(profile):
            """Close the shown window before the next scheduled profile."""
            attempts.append(profile.itemRemark)

            if len(attempts) == 1:
                QtCore.QTimer.singleShot(0, window.close)

            return 'socks://close.example:1080#Close'

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=export,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            window.startExportByIndex(range(len(profiles)))
            self.assertTrue(waitFor(lambda: not isValid(window)))

        processQtEvents()
        self.assertEqual(attempts, ['Profile 1'])

        del window
        collectAtBoundary()

        self.assertIsNone(windowReference())

    def testRepeatedWindowOwnedExportsReturnToBaseline(self):
        """Destroy window-owned timers and captured state without retained callbacks."""
        iterations = 24
        windowReferences = []
        windowDestroyed = []

        with mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            return_value='socks://lifetime.example:1080#Lifetime',
        ), mock.patch(
            'Furious.Window.QRCodeWindow.createQRCodeImage',
            side_effect=self.qrImage,
        ):
            for _index in range(iterations):
                profiles = self.profiles(2)
                window = QRCodeWindow()

                with mock.patch(
                    'Furious.Window.QRCodeWindow.Storage.UserServers',
                    return_value=profiles,
                ):
                    result = window.startExportByIndex((0, 1))

                self.assertIs(result, window)
                window.destroyed.connect(lambda *_args: windowDestroyed.append(True))
                windowReferences.append(weakref.ref(window))

                self.assertTrue(waitFor(lambda: not window.isExporting()))
                window.close()
                self.assertTrue(waitFor(lambda: not isValid(window)))

        del result, window
        collectAtBoundary()

        self.assertEqual(windowDestroyed, [True] * iterations)
        self.assertTrue(all(reference() is None for reference in windowReferences))


if __name__ == '__main__':
    unittest.main()
