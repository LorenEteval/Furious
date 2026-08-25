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

"""Protect the platform-neutral application dialog presentation lifecycle."""

from __future__ import annotations

from Furious.Backends.Xray.RoutingWindow import (
    RoutingRemarkEditDialog,
    RoutingTextEditDialog,
)
from Furious.Qt import (
    AppQDialog,
    AppQMessageBox,
    AppQTransientDialog,
)

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget

from tests.support import (
    application,
    collectAtBoundary,
    processQtEvents,
    waitFor,
)

from unittest import mock

import unittest
import weakref


class LifecycleProbeDialog(AppQDialog):
    """Record the ordering of geometry preparation and native presentation."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(321, 123)

    def __init__(self):
        """Initialize state that the geometry hook may safely consume."""
        self.constructed = False
        self.events = []

        super().__init__()

        self.constructed = True

    def prepareInitialGeometry(self):
        """Record geometry preparation preconditions."""
        self.events.append(
            (
                'prepare',
                self.constructed,
                self.isVisible(),
            )
        )

        super().prepareInitialGeometry()

    def showEvent(self, event):
        """Record each native presentation."""
        self.events.append(('show', self.size()))

        super().showEvent(event)


class FixedProbeDialog(AppQDialog):
    """Expose the declarative fixed-size policy."""

    FIXED_DIALOG_SIZE = QtCore.QSize(360, 180)


class FailingProbeDialog(AppQDialog):
    """Raise at the geometry boundary to verify open-registry cleanup."""

    def prepareInitialGeometry(self):
        """Reject presentation before Qt shows the dialog."""
        raise RuntimeError('fixture geometry failure')


class TransientProbeDialog(AppQTransientDialog):
    """Expose one-shot deletion with declarative geometry."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(300, 150)


class CountingMessageBox(AppQMessageBox):
    """Publish native show events outside the delete-on-close wrapper."""

    def __init__(self, showEvents, *args, **kwargs):
        """Retain the external event list used after native deletion."""
        self._showEvents = showEvents

        super().__init__(*args, **kwargs)

    def showEvent(self, event):
        """Record one native presentation before base centering."""
        self._showEvents.append(True)

        super().showEvent(event)


class DialogGeometryTest(unittest.TestCase):
    """Verify sizing, centering, presentation, and lifetime as one contract."""

    @classmethod
    def setUpClass(cls):
        """Create the one QApplication used by the suite."""
        application()

    def tearDown(self):
        """Drain deferred deletion and require async ownership to settle."""
        collectAtBoundary()

        self.assertEqual(AppQDialog._openDialogs, {})

    def dispose(self, dialog):
        """Destroy a reusable fixture after its assertion scope."""
        if dialog.isVisible():
            dialog.close()

        dialog.deleteLater()
        collectAtBoundary()

    def testConstructorDoesNotCallSubclassGeometryHook(self):
        """Wait until complete subclass construction before geometry preparation."""
        dialog = LifecycleProbeDialog()

        self.assertEqual(dialog.events, [])

        dialog.show()
        processQtEvents()

        self.assertEqual(dialog.events[0], ('prepare', True, False))
        self.assertEqual(dialog.events[1], ('show', dialog.DEFAULT_DIALOG_SIZE))

        self.dispose(dialog)

    def testRepeatedShowKeepsLiveSizeAndCentersEveryPresentation(self):
        """Prepare once while preserving the established per-show centering UX."""
        dialog = LifecycleProbeDialog()

        with mock.patch('Furious.Qt.QtWidgets.moveToCenter') as center:
            dialog.show()
            processQtEvents()
            dialog.hide()
            processQtEvents()

            liveSize = QtCore.QSize(444, 222)
            dialog.resize(liveSize)
            dialog.show()
            processQtEvents()

        self.assertEqual(
            [event for event in dialog.events if event[0] == 'prepare'],
            [('prepare', True, False)],
        )
        self.assertEqual(
            len([event for event in dialog.events if event[0] == 'show']),
            2,
        )
        self.assertEqual(dialog.size(), liveSize)
        self.assertEqual(center.call_count, 2)

        self.dispose(dialog)

    def testOpenPresentsOnceAndBalancesLifetimeRegistry(self):
        """Let QDialog.open perform the sole native show and release its wrapper."""
        dialog = LifecycleProbeDialog()
        key = dialog._lifetimeKey

        dialog.open()
        processQtEvents()

        self.assertEqual(
            len([event for event in dialog.events if event[0] == 'show']),
            1,
        )
        self.assertIn(key, AppQDialog._openDialogs)

        dialog.reject()
        processQtEvents()

        self.assertNotIn(key, AppQDialog._openDialogs)

        self.dispose(dialog)

    def testExecPresentsOnceWithPreparedGeometry(self):
        """Let QDialog.exec perform the sole blocking native presentation."""
        dialog = LifecycleProbeDialog()

        QtCore.QTimer.singleShot(0, dialog.accept)

        result = dialog.exec()

        self.assertEqual(
            result,
            int(AppQDialog.DialogCode.Accepted),
        )
        self.assertEqual(
            len([event for event in dialog.events if event[0] == 'prepare']),
            1,
        )
        self.assertEqual(
            len([event for event in dialog.events if event[0] == 'show']),
            1,
        )

        self.dispose(dialog)

    def testOpenGeometryFailureDoesNotShowOrRetainDialog(self):
        """Release async ownership when initial geometry preparation raises."""
        dialog = FailingProbeDialog()
        key = dialog._lifetimeKey

        for _attempt in range(2):
            with self.assertRaisesRegex(RuntimeError, 'fixture geometry failure'):
                dialog.open()

        self.assertFalse(dialog.isVisible())
        self.assertNotIn(key, AppQDialog._openDialogs)

        self.dispose(dialog)

    def testDeclarativeFixedSizeIsAppliedAtFirstPresentation(self):
        """Apply both fixed dimensions without constructor-time virtual calls."""
        dialog = FixedProbeDialog()

        dialog.show()
        processQtEvents()

        self.assertEqual(dialog.size(), dialog.FIXED_DIALOG_SIZE)
        self.assertEqual(dialog.minimumSize(), dialog.FIXED_DIALOG_SIZE)
        self.assertEqual(dialog.maximumSize(), dialog.FIXED_DIALOG_SIZE)

        self.dispose(dialog)

    def testTransientDialogDeletesAfterAsyncCompletion(self):
        """Delete the Qt object and release the Python wrapper after open/accept."""
        dialog = TransientProbeDialog()
        reference = weakref.ref(dialog)
        key = dialog._lifetimeKey

        dialog.open()
        processQtEvents()
        dialog.accept()

        del dialog

        collectAtBoundary()

        self.assertTrue(waitFor(lambda: reference() is None))
        self.assertNotIn(key, AppQDialog._openDialogs)

    def testRepresentativeDialogsKeepTheirProductDimensions(self):
        """Preserve one resizable and one fixed real dialog size."""
        remarkDialog = RoutingRemarkEditDialog('Fixture')
        remarkDialog.show()
        processQtEvents()

        self.assertEqual(
            remarkDialog.size(),
            RoutingRemarkEditDialog.DEFAULT_DIALOG_SIZE,
        )

        textDialog = RoutingTextEditDialog('Fixture')
        textDialog.show()
        processQtEvents()

        self.assertEqual(
            textDialog.size(),
            RoutingTextEditDialog.FIXED_DIALOG_SIZE,
        )
        self.assertEqual(
            textDialog.minimumSize(),
            RoutingTextEditDialog.FIXED_DIALOG_SIZE,
        )

        remarkDialog.close()
        textDialog.close()
        collectAtBoundary()

    def testMessageBoxOpenAndExecEachPresentOnce(self):
        """Keep specialized async and sync paths to one native show event."""
        owner = QWidget()
        owner.resize(800, 600)
        owner.show()

        openEvents = []
        openBox = CountingMessageBox(
            openEvents,
            parent=owner,
            text='Async fixture',
            buttons=AppQMessageBox.StandardButton.Ok,
        )
        key = openBox._lifetimeKey
        heldAtFinished = []
        openBox.finished.connect(
            lambda _result: heldAtFinished.append(key in AppQDialog._openDialogs)
        )

        openBox.open()
        processQtEvents()

        self.assertEqual(openEvents, [True])
        self.assertIn(key, AppQDialog._openDialogs)

        openBox.accept()

        self.assertEqual(heldAtFinished, [True])
        self.assertIn(key, AppQDialog._openDialogs)

        collectAtBoundary()

        self.assertNotIn(key, AppQDialog._openDialogs)

        execEvents = []
        execBox = CountingMessageBox(
            execEvents,
            parent=owner,
            text='Sync fixture',
            buttons=AppQMessageBox.StandardButton.Ok,
        )
        QtCore.QTimer.singleShot(
            0,
            execBox.button(AppQMessageBox.StandardButton.Ok).click,
        )

        result = execBox.exec()

        self.assertEqual(
            result,
            int(AppQMessageBox.StandardButton.Ok),
        )
        self.assertEqual(execEvents, [True])

        owner.close()
        owner.deleteLater()
        collectAtBoundary()

    def testMessageBoxRetainsAdaptivePerShowSizingAndParentCentering(self):
        """Keep message-box sizing specialized while sharing show-event centering."""
        owner = QWidget()
        owner.resize(800, 600)
        owner.show()

        messageBox = AppQMessageBox(
            parent=owner,
            text='Ready',
            buttons=AppQMessageBox.StandardButton.Ok,
        )

        with mock.patch('Furious.Qt.QtWidgets.moveToCenter') as center:
            messageBox.show()
            processQtEvents()
            singleButtonWidth = messageBox.width()

            messageBox.hide()
            messageBox.setStandardButtons(
                AppQMessageBox.StandardButton.Save
                | AppQMessageBox.StandardButton.Discard
                | AppQMessageBox.StandardButton.Cancel
            )
            messageBox.show()
            processQtEvents()

        self.assertGreater(messageBox.width(), singleButtonWidth)
        self.assertEqual(center.call_count, 2)
        self.assertTrue(
            all(call.args == (messageBox, owner) for call in center.call_args_list)
        )

        messageBox.close()
        owner.close()
        owner.deleteLater()
        collectAtBoundary()


if __name__ == '__main__':
    unittest.main()
