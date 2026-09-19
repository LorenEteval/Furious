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
from Furious.Backends.Xray.AssetListView import XrayAssetListView
from Furious.Backends.Xray.RoutingWindow import (
    UserRoutingTableView,
    RoutingDocumentationURL,
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
from Furious.Actions.Import import ImportURIsProgressDialog
from Furious.Frozenlib import Mixins
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Repository import Storage
from Furious.Widget.ServerTableView import ServerTableView
from Furious.Widget.SubscriptionTableView import SubscriptionTableView
from Furious.Qt import (
    AppQAction,
    AppQDialog,
    AppQMainWindow,
    AppQMenu,
    AppQMessageBox,
    AppQSwitch,
    AppQTransientDialog,
    connectWeakly,
    singleShotWeakly,
)
from Furious.Qt.QtWidgets import _AppMessageBoxMask
from Furious.Window.QRCodeWindow import QRCodeWindow, _QRCodePage
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog
from Furious.Window.IndentDialog import IndentDialog
from Furious.Window.TextEditorWindow import TextEditorWindow
from Furious.Widget.ServerTableView import DeleteServersProgressDialog

from PySide6 import QtCore
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QPushButton, QWidget

from shiboken6 import isValid, delete as deleteQObject

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
from pathlib import Path
import tempfile
import unittest
from unittest import mock
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


class DelayedReceiver(QtCore.QObject):
    """Record weakly scheduled work while this receiver remains alive."""

    def __init__(self, calls):
        """Retain only the caller-owned result list."""
        super().__init__()

        self._calls = calls

    @QtCore.Slot()
    def record(self):
        """Record one delivered timer callback."""
        self._calls.append(1)


class QtLifetimeTest(unittest.TestCase):
    """Stress direct destruction evidence without relying on process RSS alone."""

    def testRemovedMessageBoxButtonDisconnectsAndCanBeReused(self):
        """Detaching a button ends only the box-owned signal and role lifetime."""
        application()
        with isolatedSettings():
            box = AppQMessageBox()
            button = QPushButton('Reusable button')
            finished = []
            externalClicks = []
            box.finished.connect(finished.append)
            button.clicked.connect(lambda: externalClicks.append(True))
            try:
                for _ in range(30):
                    box.addButton(button, box.ButtonRole.AcceptRole)
                    box.setDefaultButton(button)
                    box.setEscapeButton(button)
                    box.removeButton(button)
                    button.click()
                    self.assertEqual(finished, [])
                    self.assertIsNone(box.defaultButton())
                    self.assertIsNone(box.escapeButton())
                    self.assertIsNone(button.parent())
                    self.assertEqual(button.receivers(QtCore.SIGNAL('clicked()')), 1)

                self.assertEqual(len(externalClicks), 30)
                box.addButton(button, box.ButtonRole.AcceptRole)
                box.addButton(button, box.ButtonRole.AcceptRole)
                box.open()
                button.click()
                processQtEvents()
                self.assertEqual(finished, [int(AppQDialog.DialogCode.Accepted)])
                self.assertFalse(isValid(box))
                self.assertFalse(isValid(button))
            finally:
                if isValid(box):
                    deleteQObject(box)
                if isValid(button):
                    deleteQObject(button)
                processQtEvents()

    def testReplacingMessageBoxButtonsReleasesOldDefaultAndEscape(self):
        """A retained dialog must not retain removed standard-button wrappers."""
        application()
        with isolatedSettings():
            box = AppQMessageBox()
            references = []
            try:
                for _ in range(30):
                    box.setStandardButtons(box.StandardButton.Yes)
                    button = box.button(box.StandardButton.Yes)
                    references.append(weakref.ref(button))
                    box.setDefaultButton(button)
                    box.setEscapeButton(button)
                    box.setStandardButtons(box.StandardButton.No)
                    del button
                    processQtEvents()
                    self.assertIsNone(box.defaultButton())
                    self.assertIsNone(box.escapeButton())
                self.assertTrue(all(reference() is None for reference in references))
            finally:
                deleteQObject(box)
                processQtEvents()

    def testNativeButtonDestructionRemovesMessageBoxRegistrations(self):
        """Deleting an attached button cannot leave invalid wrapper roles behind."""
        application()
        with isolatedSettings():
            box = AppQMessageBox()
            try:
                for _ in range(30):
                    button = box.addButton(box.StandardButton.Yes)
                    box.setDefaultButton(button)
                    box.setEscapeButton(button)
                    deleteQObject(button)
                    self.assertEqual(box.buttons(), [])
                    self.assertIsNone(box.defaultButton())
                    self.assertIsNone(box.escapeButton())
                    self.assertIsNone(box.button(box.StandardButton.Yes))
            finally:
                deleteQObject(box)
                processQtEvents()

    def testMessageBoxCallbackMayDestroyItsOwner(self):
        """Button activation cannot finish a box destroyed by its own listener."""
        application()
        with isolatedSettings():
            owner = QWidget()
            box = AppQMessageBox(parent=owner)
            button = box.addButton(box.StandardButton.Yes)
            box.buttonClicked.connect(lambda *_args: deleteQObject(owner))
            with mock.patch('sys.excepthook') as exceptionHook:
                button.click()
                processQtEvents()
            exceptionHook.assert_not_called()
            self.assertFalse(isValid(box))
            self.assertFalse(isValid(button))

    def testRoutingDocumentationDoesNotEnterCompiledMethodProtection(self):
        """Closing routing editors releases labels under Nuitka-style retention."""
        originalConnect = QtCore.SignalInstance.connect
        protectedCallbacks = []
        references = []
        destroyed = []

        def protectingConnect(signal, callback, *args, **kwargs):
            if isinstance(getattr(callback, '__self__', None), QtCore.QObject):
                protectedCallbacks.append(callback)

            return originalConnect(signal, callback, *args, **kwargs)

        with mock.patch.object(QtCore.SignalInstance, 'connect', protectingConnect):
            for _ in range(30):
                dialog = RoutingRuleEditDialog({'type': 'field'})

                for label in dialog.findChildren(RoutingDocumentationURL):
                    references.append(weakref.ref(label))
                    label.destroyed.connect(lambda *_args: destroyed.append(True))

                del label

                dialog.open()
                dialog.reject()

                del dialog

                processQtEvents()

        collectAtBoundary()

        self.assertAllDestroyed(references, destroyed, 30)
        self.assertFalse(protectedCallbacks)

    def testRoutingDeleteConfirmationDiesWithTransientOwner(self):
        """A Windows confirmation cannot retain or call a deleted rules editor."""
        references = []
        destroyed = []

        for _ in range(30):
            routing = {'rules': [{'ruleTag': 'keep'}]}
            dialog = RoutingRulesDialog(routing)
            dialog.open()
            dialog.listView.setCurrentIndex(dialog.listView.rulesModel.index(0, 0))

            with mock.patch('Furious.Backends.Xray.RoutingWindow.PLATFORM', 'Windows'):
                dialog.deleteRule()

            confirmation = next(
                item
                for item in AppQDialog._openDialogs.values()
                if isinstance(item, AppQMessageBox)
            )

            for item in (dialog, confirmation):
                references.append(weakref.ref(item))
                item.destroyed.connect(lambda *_args: destroyed.append(True))

            del item

            try:
                dialog.deleteLater()
                processQtEvents()

                self.assertFalse(isValid(dialog))
                self.assertFalse(isValid(confirmation))
                self.assertEqual(routing['rules'], [{'ruleTag': 'keep'}])
            finally:
                if isValid(confirmation):
                    confirmation.reject()
                    processQtEvents()

            del dialog, confirmation

        collectAtBoundary()

        self.assertAllDestroyed(references, destroyed, 60)

    def testActionOwnedMenusDieWithActionAndPreserveExplicitOwners(self):
        """QAction's menu association must not strand an unparented native menu."""
        references = []
        destroyed = []

        for explicitOwner in (False, True):
            for _ in range(30):
                owner = QWidget()
                menu = AppQMenu(parent=owner if explicitOwner else None)
                action = AppQAction('Menu fixture', menu=menu, parent=owner)

                references.append(weakref.ref(menu))
                menu.destroyed.connect(lambda *_args: destroyed.append(True))

                action.deleteLater()
                processQtEvents()

                self.assertFalse(isValid(action))

                try:
                    self.assertEqual(isValid(menu), explicitOwner)
                finally:
                    if isValid(menu):
                        menu.deleteLater()

                    owner.deleteLater()
                    processQtEvents()

                del action, menu, owner

        self.assertAllDestroyed(references, destroyed, 60)

    def testViewConfirmationsDieWithTheirCallbackOwner(self):
        """Deleting a view also destroys every prompt that could mutate it."""
        profile = ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture'}), {'displayName': 'Keep'}
        )
        profiles = [profile]
        subscriptions = {'fixture': {'remark': 'Keep', 'enabled': False}}
        routings = {'fixture': {'remark': 'Keep', 'rules': []}}

        with (
            isolatedSettings(),
            mock.patch.object(Storage, 'UserServers', lambda: profiles),
            mock.patch.object(Storage, 'UserSubs', lambda: subscriptions),
            mock.patch.object(Storage, 'UserRoutings', lambda: routings),
            tempfile.TemporaryDirectory() as directory,
            mock.patch(
                'Furious.Backends.Xray.AssetListView.XRAY_ASSET_DIR', Path(directory)
            ),
        ):
            asset = Path(directory) / 'fixture.dat'
            asset.write_bytes(b'keep')

            for platform in ('Windows', 'Linux', 'Darwin'):
                for family in (
                    'servers',
                    'subscriptions',
                    'routings',
                    'assetDelete',
                    'assetOverwrite',
                ):
                    with self.subTest(platform=platform, family=family):
                        references = []
                        destroyed = []

                        for _ in range(20):
                            parent = QWidget()

                            if family == 'servers':
                                view = ServerTableView(
                                    parent=parent,
                                    configurationEditorFactory=QWidget,
                                    qrCodeWindowFactory=QWidget,
                                    importActionsFactory=tuple,
                                )
                            elif family == 'subscriptions':
                                view = SubscriptionTableView(parent=parent)
                            elif family == 'routings':
                                view = UserRoutingTableView(parent=parent)
                            else:
                                view = XrayAssetListView(parent=parent)

                            view.setCurrentIndex(view.model().index(0, 0))
                            module = type(view).__module__

                            with mock.patch(module + '.PLATFORM', platform):
                                if family == 'assetOverwrite':
                                    view.appendNewItem(str(asset))
                                else:
                                    view.deleteSelectedItem()

                            confirmation = next(iter(AppQDialog._openDialogs.values()))
                            references.append(weakref.ref(confirmation))
                            confirmation.destroyed.connect(
                                lambda *_args: destroyed.append(True)
                            )

                            if isinstance(view, ServerTableView):
                                view.cleanup()
                                view.configurationEditor.deleteLater()

                            try:
                                view.deleteLater()
                                processQtEvents()

                                self.assertFalse(isValid(view))
                                self.assertFalse(isValid(confirmation))
                                self.assertTrue(isValid(parent))

                                self.assertEqual(profiles, [profile])
                                self.assertIn('fixture', subscriptions)
                                self.assertIn('fixture', routings)
                                self.assertEqual(asset.read_bytes(), b'keep')
                            finally:
                                if isValid(confirmation):
                                    confirmation.reject()

                                parent.deleteLater()
                                processQtEvents()

                            del confirmation, view, parent

                        self.assertAllDestroyed(references, destroyed, 20)

    def testReopenedDialogSurvivesPreviousPresentationCleanup(self):
        """A queued finish must not release the next asynchronous presentation."""
        destroyed = []
        references = []

        for method in ('accept', 'reject', 'close'):
            for _ in range(20):
                dialog = AppQDialog()
                dialog.destroyed.connect(lambda *_args: destroyed.append(True))

                reference = weakref.ref(dialog)
                references.append(reference)

                key = dialog._lifetimeKey

                dialog.open()
                getattr(dialog, method)()
                dialog.open()

                del dialog

                processQtEvents()

                self.assertIsNotNone(reference())
                self.assertTrue(isValid(reference()))
                self.assertTrue(reference().isVisible())
                self.assertIs(AppQDialog._openDialogs.get(key), reference())

                getattr(reference(), method)()

                processQtEvents()

                self.assertIsNone(reference())
                self.assertNotIn(key, AppQDialog._openDialogs)

        self.assertAllDestroyed(references, destroyed, 60)

    def testIndependentSenderDestructionReleasesReceiverCleanupHooks(self):
        """A surviving receiver must not accumulate hooks for dead senders."""
        receiver = DelayedReceiver([])
        self.addCleanup(receiver.deleteLater)
        counts = []

        for _ in range(40):
            sender = LongLivedEmitter()
            connectWeakly(sender.emitted, receiver, 'record', sender=sender)

            sender.deleteLater()
            processQtEvents()

            counts.append(receiver.receivers(QtCore.SIGNAL('destroyed(QObject*)')))

        self.assertEqual(counts, [counts[0]] * len(counts))

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

    def testCompiledBoundMethodProtectionDoesNotRetainTransientActions(self):
        """Keep Nuitka-like protected callbacks without retaining deleted actions."""
        originalConnect = QtCore.SignalInstance.connect
        protectedCallbacks = []
        triggered = []

        def protectingConnect(signal, callback, *args, **kwargs):
            """Emulate the packaged runtime's global bound-method protection."""
            if getattr(callback, '__self__', None) is not None:
                protectedCallbacks.append(callback)

            return originalConnect(signal, callback, *args, **kwargs)

        references = []

        with mock.patch.object(
            QtCore.SignalInstance,
            'connect',
            protectingConnect,
        ):
            for index in range(100):
                action = AppQAction(
                    'Fixture action',
                    callback=lambda value=index: triggered.append(value),
                )
                references.append(weakref.ref(action))

                action.trigger()
                action.deleteLater()

        del action

        collectAtBoundary()

        self.assertEqual(triggered, list(range(100)))
        self.assertTrue(all(reference() is None for reference in references))
        self.assertFalse(
            any(
                isinstance(getattr(callback, '__self__', None), AppQAction)
                for callback in protectedCallbacks
            )
        )

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

    def testNativeMessageBoxDestructionReleasesItsWindowMask(self):
        """Direct Qt deletion must release a mask parented to a surviving window."""
        owner = QWidget()
        owner.show()
        processQtEvents()

        try:
            for _ in range(30):
                messageBox = AppQMessageBox(parent=owner, text='Lifetime probe')
                messageBox.open()
                mask = messageBox._windowMask

                self.assertIsNotNone(mask)

                messageBox.deleteLater()
                processQtEvents()

                self.assertFalse(isValid(messageBox))
                self.assertFalse(isValid(mask))
                self.assertEqual(owner.findChildren(_AppMessageBoxMask), [])
        finally:
            owner.deleteLater()
            processQtEvents()

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

    def testDeletedSenderSignalWrapperDoesNotCrashReceiverTeardown(self):
        """Release a shorter-lived sender before its weak receiver safely."""
        result = runPythonChild(
            """
from Furious.Qt import connectWeakly
from PySide6 import QtCore


class Sender(QtCore.QObject):
    emitted = QtCore.Signal()


class Receiver(QtCore.QObject):
    @QtCore.Slot()
    def receive(self):
        pass


application = QtCore.QCoreApplication([])
receiver = Receiver()
senders = []

for _index in range(1000):
    sender = Sender()
    connectWeakly(sender.emitted, receiver, 'receive', sender=sender)
    sender.emitted.emit()
    sender.deleteLater()
    senders.append(sender)


def finish():
    global senders

    senders = []
    receiver.deleteLater()
    application.quit()


QtCore.QTimer.singleShot(0, finish)
raise SystemExit(application.exec())
""",
            timeout=30,
        )

        assertChildSucceeded(self, result, 'sender-first weak-signal teardown child')

    def testWeakSingleShotDispatchDoesNotRetainDestroyedReceiver(self):
        """Run live work once and drop deferred work for a dead receiver."""
        calls = []
        liveReceiver = DelayedReceiver(calls)

        singleShotWeakly(0, liveReceiver, 'record')
        processQtEvents()

        self.assertEqual(calls, [1])

        deadReceiver = DelayedReceiver(calls)
        deadReference = weakref.ref(deadReceiver)

        singleShotWeakly(0, deadReceiver, 'record')

        del deadReceiver

        self.assertIsNone(deadReference())

        processQtEvents()

        self.assertEqual(calls, [1])

        liveReceiver.deleteLater()

    def testImportProgressWeakSchedulingCompletesAndDestroysEveryDialog(self):
        """Keep cooperative import callbacks outside packaged bound-method retention."""
        iterations = 40
        references = []
        destroyed = []

        with mock.patch(
            'Furious.Actions.Import.Storage.UserServers',
            return_value=[],
        ):
            for _index in range(iterations):
                dialog = ImportURIsProgressDialog(tuple())
                dialog.destroyed.connect(lambda *_args: destroyed.append(True))
                references.append(weakref.ref(dialog))

                dialog.open()
                processQtEvents()

        del dialog

        collectAtBoundary()

        self.assertAllDestroyed(references, destroyed, iterations)

    def testDeleteProgressWeakSchedulingCompletesAndDestroysEveryDialog(self):
        """Release empty cooperative delete dialogs after their scheduled work."""
        iterations = 40
        table = mock.Mock()
        references = []
        destroyed = []

        for _index in range(iterations):
            dialog = DeleteServersProgressDialog(table, tuple())
            dialog.destroyed.connect(lambda *_args: destroyed.append(True))
            references.append(weakref.ref(dialog))

            dialog.open()
            processQtEvents()

        del dialog

        collectAtBoundary()

        self.assertAllDestroyed(references, destroyed, iterations)
        table.deleteItemByIndex.assert_not_called()

    def testTextEditorIndentCompletionReceivesExactTransientDialog(self):
        """Apply indentation through explicit weak sender forwarding."""
        with isolatedSettings():
            editor = TextEditorWindow()
            editor.setPlainText('{"value": 1}', False)
            editor.setIndent()

            dialogs = editor.findChildren(IndentDialog)

            self.assertEqual(len(dialogs), 1)

            dialog = dialogs[0]
            dialog.indentSpin.setValue(4)
            dialog.accept()

            processQtEvents()

            self.assertIn('\n    "value": 1\n', editor.jsonEditor.toPlainText())

            editor.deleteLater()

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
