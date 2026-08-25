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

"""Prove intended Qt ownership across representative transient UI families."""

from __future__ import annotations

from Furious.Backends.ExternalCore.Editor import ExternalCoreEditor
from Furious.Backends.Hysteria1.Editor import Hysteria1Editor
from Furious.Backends.Hysteria2.Editor import Hysteria2Editor
from Furious.Backends.Hysteria2.TunSettingsDialog import Hysteria2TunSettingsDialog
from Furious.Backends.Xray.RoutingWindow import (
    RoutingPreviewDialog,
    RoutingRuleEditDialog,
    RoutingRulesDialog,
)
from Furious.Backends.Xray.SocksEditor import SocksEditor
from Furious.Backends.Xray.ShadowsocksEditor import ShadowsocksEditor
from Furious.Backends.Xray.TrojanEditor import TrojanEditor
from Furious.Backends.Xray.TunSettingsDialog import XrayTunSettingsDialog
from Furious.Backends.Xray.VlessEditor import VlessEditor
from Furious.Backends.Xray.VmessEditor import VmessEditor
from Furious.Frozenlib import Mixins
from Furious.Qt import (
    AppQAction,
    AppQDialog,
    AppQMainWindow,
    AppQMenu,
    AppQMessageBox,
    AppQSwitch,
    AppQTransientDialog,
    connectWeakly,
)
from Furious.Qt.QtWidgets import _AppMessageBoxMask
from Furious.Window.QRCodeWindow import QRCodeWindow, _QRCodePage
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog
from Furious.Window.TextEditorWindow import TextEditorWindow

from PySide6 import QtCore
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid

from tests.support import (
    application,
    assertChildSucceeded,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    runPythonChild,
    waitFor,
)

import gc
import unittest
import weakref


class ProbeTransientDialog(AppQTransientDialog):
    """Own a running timer and menu so their destruction can be observed."""

    def __init__(self, parent=None):
        """Initialize representative transient QObject resources."""
        super().__init__(parent)

        self.timer = QtCore.QTimer(self)
        self.timer.start(1000)

        self.action = AppQAction('Fixture action')
        self.menu = AppQMenu(self.action, parent=self)


class ProbeWindow(AppQMainWindow):
    """Expose AppQMainWindow's asynchronous lifetime policy."""


class LongLivedEmitter(QtCore.QObject):
    """Represent one application-lifetime signal sender."""

    emitted = QtCore.Signal()


class TransientReceiver(AppQTransientDialog):
    """Connect a transient receiver to a long-lived sender."""

    def __init__(self, emitter, calls):
        """Connect exactly one same-process receiver callback."""
        super().__init__()

        self._calls = calls

        connectWeakly(
            emitter.emitted,
            self,
            'handleEmission',
            sender=emitter,
        )

    @QtCore.Slot()
    def handleEmission(self):
        """Record one signal delivery."""
        self._calls.append(1)


class QtLifetimeTest(unittest.TestCase):
    """Stress direct destruction evidence without relying on process RSS alone."""

    @classmethod
    def setUpClass(cls):
        """Create the one QApplication used by the entire test process."""
        application()

    def tearDown(self):
        """Drain deferred deletion and verify async registries are quiescent."""
        collectAtBoundary()

        self.assertEqual(AppQDialog._openDialogs, {})

    def assertAllDestroyed(self, references, destroyed, expected):
        """Assert weak wrappers and native destroyed signals agree."""
        self.assertTrue(
            waitFor(lambda: all(reference() is None for reference in references)),
            f'{sum(reference() is not None for reference in references)} wrappers remain',
        )
        self.assertEqual(len(destroyed), expected)

    def testTransientDialogTimerMenuAndActionAreDestroyedForEveryCycle(self):
        """Destroy timers, menus, actions, and weak-pool registrations 150 times."""
        iterations = 150
        dialogs, timers, menus, actions, destroyed = [], [], [], [], []
        poolBaselines = {
            pool: len(pool.ObjectsPool)
            for pool in (
                Mixins.ConnectionAware,
                Mixins.ThemeAware,
                Mixins.QTranslatable,
            )
        }

        for _index in range(iterations):
            dialog = ProbeTransientDialog()
            dialog.destroyed.connect(lambda *_args: destroyed.append(True))

            dialogs.append(weakref.ref(dialog))

            timers.append(weakref.ref(dialog.timer))
            menus.append(weakref.ref(dialog.menu))
            actions.append(weakref.ref(dialog.action))

            dialog.show()
            dialog.close()

        del dialog

        collectAtBoundary()

        self.assertAllDestroyed(dialogs, destroyed, iterations)
        self.assertTrue(all(reference() is None for reference in timers))
        self.assertTrue(all(reference() is None for reference in menus))
        self.assertTrue(all(reference() is None for reference in actions))

        for pool, baseline in poolBaselines.items():
            self.assertEqual(len(pool.ObjectsPool), baseline)

    def testAsyncDialogRegistryRetainsUntilNativeDestruction(self):
        """Keep a delete-on-close wrapper alive through deferred destruction."""
        dialog = ProbeTransientDialog()
        key = dialog._lifetimeKey
        reference = weakref.ref(dialog)
        heldAtFinished = []
        dialog.finished.connect(
            lambda _result: heldAtFinished.append(key in AppQDialog._openDialogs)
        )
        dialog.open()

        del dialog

        collectAtBoundary()

        self.assertIsNotNone(reference())
        self.assertIn(key, AppQDialog._openDialogs)

        reference().reject()

        self.assertEqual(heldAtFinished, [True])
        self.assertIn(key, AppQDialog._openDialogs)

        collectAtBoundary()

        self.assertTrue(waitFor(lambda: reference() is None))
        self.assertNotIn(key, AppQDialog._openDialogs)

    def testMainWindowRegistryPreventsPrematureCollectionAndReleasesOnClose(self):
        """Keep asynchronous top-level windows visible without leaking after close."""
        window = ProbeWindow()
        key = window._lifetimeKey
        reference = weakref.ref(window)
        window.show()

        del window

        collectAtBoundary()

        self.assertIsNotNone(reference())
        self.assertTrue(reference().isVisible())
        self.assertIn(key, AppQMainWindow._openWindows)

        reference().close()

        collectAtBoundary()

        self.assertTrue(waitFor(lambda: reference() is None))
        self.assertNotIn(key, AppQMainWindow._openWindows)

    def testMessageBoxAndParentMaskHaveTransientOwnership(self):
        """Remove every parent event filter/mask over repeated modal presentation."""
        iterations = 60

        owner = QWidget()
        owner.resize(640, 480)
        owner.show()

        references = []
        maskReferences = []
        destroyed = []

        for _index in range(iterations):
            messageBox = AppQMessageBox(
                icon=AppQMessageBox.Icon.Information,
                parent=owner,
                heading='Fixture heading',
                text='Fixture information',
                buttons=AppQMessageBox.StandardButton.Ok,
            )
            messageBox.destroyed.connect(lambda *_args: destroyed.append(True))
            messageBox.open()

            processQtEvents()

            references.append(weakref.ref(messageBox))
            maskReferences.append(weakref.ref(messageBox._windowMask))
            messageBox.close()

        del messageBox

        collectAtBoundary()

        self.assertAllDestroyed(references, destroyed, iterations)
        self.assertTrue(all(reference() is None for reference in maskReferences))
        self.assertEqual(owner.findChildren(_AppMessageBoxMask), [])

        owner.close()
        owner.deleteLater()

    def testLongLivedSenderDoesNotRetainClosedReceiversOrMultiplyCallbacks(self):
        """Disconnect deleted receivers and deliver once to the current receiver."""
        emitter = LongLivedEmitter()
        calls = []
        oldReferences = []

        for _index in range(100):
            receiver = TransientReceiver(emitter, calls)

            oldReferences.append(weakref.ref(receiver))

            receiver.show()
            receiver.close()

        del receiver

        collectAtBoundary()

        self.assertTrue(all(reference() is None for reference in oldReferences))
        self.assertEqual(emitter.receivers(QtCore.SIGNAL('emitted()')), 0)

        current = TransientReceiver(emitter, calls)
        current.show()

        self.assertEqual(emitter.receivers(QtCore.SIGNAL('emitted()')), 1)

        emitter.emitted.emit()

        processQtEvents()

        self.assertEqual(calls, [1])

        current.close()

        del current

        collectAtBoundary()

        self.assertEqual(emitter.receivers(QtCore.SIGNAL('emitted()')), 0)

        emitter.deleteLater()

    def testHysteria2SwitchAnimationStopsWithTransientEditor(self):
        """Destroy owned switch animations even when a toggle just started."""
        references = []
        destroyed = []

        for _index in range(30):
            editor = Hysteria2Editor()
            switches = editor.findChildren(AppQSwitch)

            self.assertTrue(switches)

            switch = switches[0]
            switch.setChecked(not switch.isChecked())

            references.extend((weakref.ref(switch), weakref.ref(switch._animation)))
            editor.destroyed.connect(lambda *_args: destroyed.append(True))
            editor.show()
            editor.close()

        del editor, switch, switches

        collectAtBoundary()

        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(len(destroyed), 30)

    def testServerTableEditorSequenceIsTransientAcrossPatternsAndClosePaths(self):
        """Stress the real table/editor path without per-cycle full collection."""
        result = runPythonChild(
            """
from tests.fixtures.editor_lifetime_probe import runProbe

for pattern in ('hysteria2', 'vless', 'alternating', 'reverse'):
    runProbe(100, pattern=pattern, closeMethod='reject')

runProbe(40, pattern='alternating', closeMethod='close')
runProbe(40, pattern='reverse', closeMethod='accept')
runProbe(35, pattern='representative', closeMethod='close')
""",
            timeout=120,
        )

        assertChildSucceeded(self, result, 'server editor lifetime child')

    def testRepresentativePluginEditorsAndDialogsAreTransient(self):
        """Destroy independent editor families after repeated normal closes."""
        factories = (
            ('external-core', ExternalCoreEditor, 35),
            ('socks-protocol', SocksEditor, 35),
            ('vless-protocol', VlessEditor, 25),
            ('vmess-protocol', VmessEditor, 25),
            ('trojan-protocol', TrojanEditor, 12),
            ('shadowsocks-protocol', ShadowsocksEditor, 12),
            ('hysteria1-protocol', Hysteria1Editor, 12),
            ('hysteria2-protocol', Hysteria2Editor, 25),
            ('xray-tun-settings', XrayTunSettingsDialog, 25),
            ('hysteria2-tun-settings', Hysteria2TunSettingsDialog, 25),
            (
                'routing-rule',
                lambda: RoutingRuleEditDialog(
                    {'type': 'field', 'outboundTag': 'proxy'}
                ),
                30,
            ),
            (
                'routing-rules',
                lambda: RoutingRulesDialog({'rules': []}),
                50,
            ),
            (
                'routing-preview',
                lambda: RoutingPreviewDialog({'rules': []}),
                50,
            ),
            ('subscription-editor', _SubscriptionEditorDialog, 50),
        )

        with isolatedSettings():
            for name, factory, iterations in factories:
                with self.subTest(family=name):
                    references, destroyed = [], []

                    for _index in range(iterations):
                        dialog = factory()
                        dialog.destroyed.connect(
                            lambda *_args, _destroyed=destroyed: _destroyed.append(True)
                        )

                        references.append(weakref.ref(dialog))

                        dialog.show()
                        dialog.close()

                    del dialog

                    collectAtBoundary()

                    self.assertAllDestroyed(
                        references,
                        destroyed,
                        iterations,
                    )

    def testQRCodeTopLevelWindowIsDeletedOnClose(self):
        """Destroy each transient QR window together with its page and label."""
        iterations = 100
        references, destroyed = [], []
        image = QImage(64, 64, QImage.Format.Format_Grayscale8)
        image.fill(QtCore.Qt.GlobalColor.white)

        for _index in range(iterations):
            window = QRCodeWindow()
            page = _QRCodePage(image, parent=window.tabWidget)
            window.tabWidget.addTab(page, 'Lifetime fixture')

            for object_ in (window, page, page.qrLabel):
                object_.destroyed.connect(lambda *_args: destroyed.append(True))
                references.append(weakref.ref(object_))

            window.show()
            window.close()

        del object_, page, window

        collectAtBoundary()

        self.assertAllDestroyed(
            references,
            destroyed,
            iterations * 3,
        )

    def testTextEditorWindowIsIntentionallyReusableThenExplicitlyDestroyed(self):
        """Reuse one persistent editor without duplicating menus or actions."""
        with isolatedSettings():
            editor = TextEditorWindow()
            reference = weakref.ref(editor)
            actionCount = len(editor.actions())
            fileActionCount = len(editor.fileMenu.actions())

            for _index in range(50):
                editor.show()

                processQtEvents(1)

                editor.close()

                processQtEvents(1)

                self.assertTrue(isValid(editor))
                self.assertEqual(len(editor.actions()), actionCount)
                self.assertEqual(len(editor.fileMenu.actions()), fileActionCount)

            self.assertNotIn(editor._lifetimeKey, AppQMainWindow._openWindows)

            editor.deleteLater()

            del editor

            collectAtBoundary()

            self.assertTrue(waitFor(lambda: reference() is None))


if __name__ == '__main__':
    unittest.main()
