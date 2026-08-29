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

"""Exercise real Qt input, focus, model/view, and shared-surface behavior."""

from __future__ import annotations

from Furious.Controllers import ConnectionState
from Furious.Controllers.SettingsController import SettingsController
from Furious.Frozenlib import AppBuiltinProxyMode, AppSettings
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Plugins.API import RoutingOption
from Furious.Repository import Storage, SubscriptionGroup
from Furious.Qt import AppQDialog
from Furious.Widget.RoutingSelector import RoutingSelector
from Furious.Widget.ServerTableView import ServerTableView
from Furious.Window.HomePage import HomePage
from Furious.Window.SettingsPage import (
    _SystemProxySettingsCard,
    _ToggleSettingsCard,
)
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog

from PySide6 import QtCore, QtGui
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from shiboken6 import isValid

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    waitFor,
)

from contextlib import ExitStack, contextmanager

import unittest
import weakref

from unittest import mock


class _ConnectionControllerFixture(QtCore.QObject):
    """Publish the application-lifetime signals consumed by real Home widgets."""

    stateChanged = QtCore.Signal(object)
    activeProfileChanged = QtCore.Signal(object)
    interactionEnabledChanged = QtCore.Signal(bool)

    def __init__(self):
        """Start in the deterministic disconnected and interactive state."""
        super().__init__()

        self.state = ConnectionState.Disconnected
        self.activeProfile = None
        self.interactionEnabled = True
        self.toggleCount = 0

    def isConnected(self) -> bool:
        """Return whether this fixture is in the connected state."""
        return self.state is ConnectionState.Connected

    def isConnecting(self) -> bool:
        """Return whether this fixture is in the connecting state."""
        return self.state is ConnectionState.Connecting

    def toggle(self):
        """Record a connection request without starting a runtime."""
        self.toggleCount += 1

    def setInteractionEnabled(self, enabled: bool):
        """Publish the same interaction gate as the real controller."""
        self.interactionEnabled = bool(enabled)
        self.interactionEnabledChanged.emit(self.interactionEnabled)


class _RoutingControllerFixture(QtCore.QObject):
    """Provide stable routing options while recording real combo-box requests."""

    stateChanged = QtCore.Signal(object, str)
    interactionEnabledChanged = QtCore.Signal(bool)

    def __init__(self, options, routing):
        """Store one semantic routing snapshot."""
        super().__init__()

        self.options = tuple(options)
        self.routing = routing
        self.interactionEnabled = True
        self.selections = []

    def state(self):
        """Return the current semantic routing snapshot."""
        return self.options, self.routing

    def refresh(self, *, force=False):
        """Optionally republish the current routing snapshot."""
        if force:
            self.stateChanged.emit(*self.state())

        return self.state()

    def selectRouting(self, routing):
        """Record one user-originated routing selection."""
        self.routing = routing
        self.selections.append(routing)

    def setInteractionEnabled(self, enabled: bool):
        """Publish whether routing may be changed."""
        self.interactionEnabled = bool(enabled)
        self.interactionEnabledChanged.emit(self.interactionEnabled)


class ServerTableQtInteractionTest(unittest.TestCase):
    """Protect identity-aware table behavior through actual Qt input events."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Release repository owners and deferred table/menu objects."""
        Storage._UserServersStorage.cache_clear()
        Storage._UserSubsStorage.cache_clear()
        collectAtBoundary()

    @staticmethod
    def _profile(name: str):
        """Build one deterministic profile with a stable generated identity."""
        return ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture'}),
            {'displayName': name},
        )

    def _table(self, names):
        """Build and show one real server table backed by isolated repositories."""
        Storage.UserServers().extend(self._profile(name) for name in names)
        AppSettings.set('ActivatedItemIndex', '0')

        table = ServerTableView(
            configurationEditorFactory=QWidget,
            qrCodeWindowFactory=QWidget,
            importActionsFactory=tuple,
        )
        table.resize(960, 420)
        table.show()
        table.activateWindow()

        processQtEvents()

        return table

    @staticmethod
    def _destroyTable(table):
        """Use the table's production cleanup and Qt deferred-delete paths."""
        table.cleanup()
        table.close()
        table.deleteLater()

    def _clickProxyRow(self, table, row, modifiers=QtCore.Qt.NoModifier):
        """Select one visible row through the viewport's real mouse path."""
        index = table.proxyModel.index(row, 0)

        self.assertTrue(index.isValid())

        rectangle = table.visualRect(index)

        self.assertFalse(rectangle.isEmpty())

        QTest.mouseClick(
            table.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifiers,
            rectangle.center(),
        )
        processQtEvents()

    @staticmethod
    def _selectedProfileIds(table):
        """Return stable source identities selected through the proxy view."""
        return tuple(
            Storage.UserServers()[row].metadata.profileId for row in table.selectedIndex
        )

    @staticmethod
    def _currentProfileId(table):
        """Return the source identity represented by the current proxy index."""
        row = table.sourceRowFromProxyIndex(table.currentIndex())

        if 0 <= row < len(Storage.UserServers()):
            return Storage.UserServers()[row].metadata.profileId

        return None

    def testMouseMultiSelectionAndRepeatedShortcutPreserveIdentityAndFocus(self):
        """Keep Ctrl-click selection/current identity ready across repeated moves."""
        with isolatedSettings():
            names = (
                'visible first',
                'hidden',
                'visible second',
                'visible third',
                'visible fourth',
                'visible fifth',
            )
            table = self._table(names)

            try:
                table.search('^visible')
                processQtEvents()

                self._clickProxyRow(table, 1)
                self._clickProxyRow(
                    table,
                    2,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )

                selectedIds = set(self._selectedProfileIds(table))
                currentId = self._currentProfileId(table)

                for _iteration in range(2):
                    QTest.keyClick(
                        table,
                        QtCore.Qt.Key.Key_Down,
                        QtCore.Qt.KeyboardModifier.ControlModifier,
                    )
                    processQtEvents()

                    self.assertTrue(table.hasFocus())
                    self.assertEqual(set(self._selectedProfileIds(table)), selectedIds)
                    self.assertEqual(self._currentProfileId(table), currentId)

                self.assertEqual(
                    [profile.itemRemark for profile in Storage.UserServers()],
                    [
                        'visible first',
                        'hidden',
                        'visible fourth',
                        'visible fifth',
                        'visible second',
                        'visible third',
                    ],
                )
            finally:
                self._destroyTable(table)

    def testTableShortcutDoesNotFireFromSiblingEditor(self):
        """Keep table commands inactive while the Home search editor owns focus."""
        with isolatedSettings():
            window = QWidget()
            layout = QVBoxLayout(window)
            editor = QLineEdit(window)
            table = self._table(('one', 'two', 'three'))

            layout.addWidget(editor)
            layout.addWidget(table)
            window.resize(960, 500)
            window.show()
            window.activateWindow()
            processQtEvents()

            try:
                self._clickProxyRow(table, 1)
                editor.setFocus()

                self.assertTrue(
                    waitFor(lambda: application().focusWidget() is editor),
                )

                before = tuple(
                    profile.metadata.profileId for profile in Storage.UserServers()
                )

                QTest.keyClick(
                    editor,
                    QtCore.Qt.Key.Key_Down,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )
                processQtEvents()

                self.assertIs(application().focusWidget(), editor)
                self.assertEqual(
                    tuple(
                        profile.metadata.profileId for profile in Storage.UserServers()
                    ),
                    before,
                )

                table.proxyModel.sort(
                    0,
                    QtCore.Qt.SortOrder.AscendingOrder,
                )
                processQtEvents()

                self.assertIs(application().focusWidget(), editor)
            finally:
                self._destroyTable(table)
                window.close()
                window.deleteLater()

    def testNestedTableShortcutDoesNotFireFromSiblingEditor(self):
        """Confine the Advanced submenu's Ctrl+E action to the focused table."""
        with isolatedSettings():
            window = QWidget()
            layout = QVBoxLayout(window)
            editor = QLineEdit(window)
            table = self._table(('one',))
            editRequests = []

            table.editSelectedItemConfiguration = lambda: editRequests.append(True)

            layout.addWidget(editor)
            layout.addWidget(table)
            window.resize(960, 500)
            window.show()
            window.activateWindow()
            processQtEvents()

            try:
                self._clickProxyRow(table, 0)
                editor.setFocus()

                self.assertTrue(
                    waitFor(lambda: application().focusWidget() is editor),
                )
                self.assertEqual(
                    table.customizeJSONConfigActionRef.shortcutContext(),
                    QtCore.Qt.ShortcutContext.WidgetShortcut,
                )

                QTest.keyClick(
                    editor,
                    QtCore.Qt.Key.Key_E,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )
                processQtEvents()

                self.assertEqual(editRequests, [])
                self.assertIs(application().focusWidget(), editor)
            finally:
                self._destroyTable(table)
                window.close()
                window.deleteLater()

    def testContextMenuUsesOnlyMultithreadedDownloadSpeedAction(self):
        """Expose one download command backed by the multithreaded scheduler."""
        with isolatedSettings():
            table = self._table(('one',))

            try:
                actions = tuple(
                    action
                    for action in table.contextMenu.actions()
                    if not action.isSeparator()
                    and action.textEnglish == 'Test Download Speed'
                )

                self.assertEqual(len(actions), 1)
                self.assertEqual(
                    actions[0].shortcut(),
                    QtGui.QKeySequence(
                        QtCore.QKeyCombination(
                            QtCore.Qt.KeyboardModifier.ControlModifier,
                            QtCore.Qt.Key.Key_M,
                        )
                    ),
                )

                with (
                    mock.patch.object(
                        table,
                        'testSelectedItemDownloadSpeedMulti',
                    ) as multithreaded,
                    mock.patch.object(
                        table,
                        'testSelectedItemDownloadSpeed',
                    ) as singleThreaded,
                ):
                    actions[0].trigger()
                    processQtEvents()

                multithreaded.assert_called_once_with()
                singleThreaded.assert_not_called()
            finally:
                self._destroyTable(table)

    def testHeaderSortPreservesSelectionCurrentAndActiveIdentity(self):
        """Remap Qt persistent indexes when a real header click sorts rows."""
        with isolatedSettings():
            table = self._table(('zulu', 'alpha', 'mike'))

            try:
                AppSettings.set('ActivatedItemIndex', '2')
                table.sourceModel.emitAllChanged()

                self._clickProxyRow(table, 0)
                self._clickProxyRow(
                    table,
                    2,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )

                selectedIds = set(self._selectedProfileIds(table))
                currentId = self._currentProfileId(table)
                activeId = Storage.UserServers()[2].metadata.profileId
                header = table.horizontalHeader()
                position = QtCore.QPoint(
                    header.sectionViewportPosition(0) + header.sectionSize(0) // 2,
                    header.height() // 2,
                )

                for _iteration in range(2):
                    QTest.mouseClick(
                        header.viewport(),
                        QtCore.Qt.MouseButton.LeftButton,
                        pos=position,
                    )
                    processQtEvents()

                    descending = (
                        header.sortIndicatorOrder()
                        == QtCore.Qt.SortOrder.DescendingOrder
                    )

                    self.assertEqual(
                        [profile.itemRemark for profile in Storage.UserServers()],
                        sorted(
                            ('zulu', 'alpha', 'mike'),
                            reverse=descending,
                        ),
                    )
                    self.assertEqual(set(self._selectedProfileIds(table)), selectedIds)
                    self.assertEqual(self._currentProfileId(table), currentId)
                    self.assertEqual(
                        Storage.UserServers()[
                            Storage.UserActivatedItemIndex()
                        ].metadata.profileId,
                        activeId,
                    )
            finally:
                self._destroyTable(table)

    def testFilteredShortcutUsesMappedSourceProfileIdentity(self):
        """Apply a real shortcut to the selected source object, not proxy row zero."""
        with isolatedSettings():
            table = self._table(('alpha', 'literal[', 'target'))

            for index, profile in enumerate(Storage.UserServers()):
                profile.metadata.latency = f'{index + 1} ms'
                profile.metadata.speed = f'{index + 1} MiB/s'

            try:
                table.search('[')
                processQtEvents()

                self.assertEqual(table.proxyModel.rowCount(), 1)

                self._clickProxyRow(table, 0)

                selectedId = self._selectedProfileIds(table)

                self.assertEqual(
                    selectedId,
                    (Storage.UserServers()[1].metadata.profileId,),
                )

                QTest.keyClick(
                    table,
                    QtCore.Qt.Key.Key_R,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )
                processQtEvents()

                self.assertEqual(Storage.UserServers()[0].metadata.latency, '1 ms')
                self.assertEqual(Storage.UserServers()[1].metadata.latency, '')
                self.assertEqual(Storage.UserServers()[1].metadata.speed, '')
                self.assertEqual(Storage.UserServers()[2].metadata.latency, '3 ms')
            finally:
                self._destroyTable(table)

    def testFilterClearPreservesVisibleSelectionAndHiddenActiveIdentity(self):
        """Keep semantic selection and activation stable across proxy filtering."""
        with isolatedSettings():
            table = self._table(('alpha', 'beta', 'gamma'))

            try:
                AppSettings.set('ActivatedItemIndex', '1')
                table.sourceModel.emitAllChanged()
                self._clickProxyRow(table, 2)

                selectedId = self._selectedProfileIds(table)
                currentId = self._currentProfileId(table)
                activeId = Storage.UserServers()[1].metadata.profileId

                table.search('gamma')
                processQtEvents()

                self.assertEqual(table.proxyModel.rowCount(), 1)
                self.assertEqual(self._selectedProfileIds(table), selectedId)
                self.assertEqual(self._currentProfileId(table), currentId)
                self.assertEqual(
                    Storage.UserServers()[
                        Storage.UserActivatedItemIndex()
                    ].metadata.profileId,
                    activeId,
                )

                table.search('')
                processQtEvents()

                self.assertEqual(table.proxyModel.rowCount(), 3)
                self.assertEqual(self._selectedProfileIds(table), selectedId)
                self.assertEqual(self._currentProfileId(table), currentId)
                self.assertEqual(
                    Storage.UserServers()[
                        Storage.UserActivatedItemIndex()
                    ].metadata.profileId,
                    activeId,
                )
            finally:
                self._destroyTable(table)

    def testDynamicSubscriptionMenuReleasesReplacedActions(self):
        """Rebuild a shown context menu without retaining obsolete QActions."""
        with isolatedSettings():
            Storage.upsertSubscriptionGroup(
                SubscriptionGroup(id='group-a', remark='Group A')
            )
            Storage.upsertSubscriptionGroup(
                SubscriptionGroup(id='group-b', remark='Group B', sortOrder=1)
            )
            table = self._table(('manual',))

            try:
                self._clickProxyRow(table, 0)
                table.contextMenu.popup(table.viewport().mapToGlobal(QtCore.QPoint()))

                self.assertTrue(waitFor(table.contextMenu.isVisible))

                firstActions = tuple(table._subscriptionActions)
                firstReferences = tuple(weakref.ref(action) for action in firstActions)

                self.assertEqual(
                    [action.textEnglish for action in firstActions],
                    ['No subscription', 'Group A', 'Group B'],
                )

                table.contextMenu.hide()
                Storage.removeSubscriptionGroup('group-b')
                Storage.upsertSubscriptionGroup(
                    SubscriptionGroup(id='group-c', remark='Group C', sortOrder=1)
                )
                table.contextMenu.popup(table.viewport().mapToGlobal(QtCore.QPoint()))

                self.assertTrue(waitFor(table.contextMenu.isVisible))
                self.assertEqual(
                    [action.textEnglish for action in table._subscriptionActions],
                    ['No subscription', 'Group A', 'Group C'],
                )

                del firstActions
                collectAtBoundary()

                self.assertTrue(
                    all(
                        reference() is None or not isValid(reference())
                        for reference in firstReferences
                    )
                )
            finally:
                table.contextMenu.hide()
                self._destroyTable(table)


class SharedSettingsQtWorkflowTest(unittest.TestCase):
    """Exercise real Home/Settings controls around one shared controller."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Release repository caches and deferred page/card objects."""
        Storage._UserServersStorage.cache_clear()
        Storage._UserSubsStorage.cache_clear()
        collectAtBoundary()

    @contextmanager
    def _home(self, settingsController, connectionController, routingController):
        """Build the smallest side-effect-free real Home composition."""
        registry = mock.Mock()
        registry.protocolDescriptors.return_value = ()

        with ExitStack() as stack:
            for target, value in (
                ('Furious.Window.HomePage.AppSettingsController', settingsController),
                (
                    'Furious.Window.HomePage.AppConnectionController',
                    connectionController,
                ),
                ('Furious.Window.HomePage.AppRoutingController', routingController),
                (
                    'Furious.Widget.ConnectionButton.AppConnectionController',
                    connectionController,
                ),
                (
                    'Furious.Widget.RoutingSelector.AppRoutingController',
                    routingController,
                ),
                ('Furious.Window.HomePage.getPluginRegistry', registry),
            ):
                stack.enter_context(mock.patch(target, return_value=value))

            stack.enter_context(
                mock.patch.object(HomePage, 'serverImportActions', return_value=())
            )

            home = HomePage()

            try:
                yield home
            finally:
                home.trafficStatsManager.cleanup()
                home.userServersQTableWidget.cleanup()
                home.close()
                home.deleteLater()

    def testHomeAndSettingsControlsSynchronizeWithoutDuplicateSignals(self):
        """Round-trip real proxy/TUN input without stale or recursive updates."""
        with (
            isolatedSettings(),
            mock.patch('Furious.Controllers.SettingsController.PLATFORM', 'Linux'),
            mock.patch(
                'Furious.Controllers.SettingsController.SystemRuntime.flatpakID',
                return_value='',
            ),
            mock.patch(
                'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
            ),
        ):
            AppSettings.set('SystemProxyMode', AppBuiltinProxyMode.Auto.value)
            AppSettings.turnOFF('VPNMode')

            settingsController = SettingsController()
            connectionController = _ConnectionControllerFixture()
            routingController = _RoutingControllerFixture(
                (RoutingOption('default', 'Default'),),
                'default',
            )

            with (
                mock.patch(
                    'Furious.Window.SettingsPage.AppSettingsController',
                    return_value=settingsController,
                ),
                self._home(
                    settingsController,
                    connectionController,
                    routingController,
                ) as home,
            ):
                settingsSurface = QWidget()
                settingsLayout = QVBoxLayout(settingsSurface)
                proxyCard = _SystemProxySettingsCard('System Proxy')
                tunCard = _ToggleSettingsCard(
                    'shield-check.svg',
                    'VPNMode',
                    settingsController.setTUNMode,
                    'TUN Mode',
                )

                settingsController.systemProxyModeChanged.connect(proxyCard.sync)
                settingsController.tunModeChanged.connect(tunCard.checkBox.syncChecked)
                settingsLayout.addWidget(proxyCard)
                settingsLayout.addWidget(tunCard)

                proxyModes = []
                tunStates = []

                settingsController.systemProxyModeChanged.connect(proxyModes.append)
                settingsController.tunModeChanged.connect(tunStates.append)

                home.show()
                settingsSurface.show()
                processQtEvents()

                QTest.keyClick(
                    home.systemProxyComboBox,
                    QtCore.Qt.Key.Key_Down,
                )
                processQtEvents()

                self.assertEqual(
                    home.systemProxyComboBox.currentData(),
                    AppBuiltinProxyMode.NoChanges.value,
                )
                self.assertEqual(
                    proxyCard.comboBox.currentData(),
                    AppBuiltinProxyMode.NoChanges.value,
                )
                self.assertEqual(proxyModes, [AppBuiltinProxyMode.NoChanges.value])

                QTest.keyClick(proxyCard.comboBox, QtCore.Qt.Key.Key_Up)
                processQtEvents()

                self.assertEqual(
                    home.systemProxyComboBox.currentData(),
                    AppBuiltinProxyMode.Auto.value,
                )
                self.assertEqual(
                    proxyModes,
                    [
                        AppBuiltinProxyMode.NoChanges.value,
                        AppBuiltinProxyMode.Auto.value,
                    ],
                )

                QTest.mouseClick(
                    home.tunModeSwitch,
                    QtCore.Qt.MouseButton.LeftButton,
                    pos=home.tunModeSwitch.rect().center(),
                )
                processQtEvents()

                self.assertTrue(home.tunModeSwitch.isChecked())
                self.assertTrue(tunCard.checkBox.isChecked())
                self.assertEqual(tunStates, [True])

                QTest.mouseClick(
                    tunCard.checkBox,
                    QtCore.Qt.MouseButton.LeftButton,
                    pos=tunCard.checkBox.rect().center(),
                )
                processQtEvents()

                self.assertFalse(home.tunModeSwitch.isChecked())
                self.assertFalse(tunCard.checkBox.isChecked())
                self.assertEqual(tunStates, [True, False])

                connectionController.setInteractionEnabled(False)
                processQtEvents()

                self.assertFalse(home.systemProxyComboBox.isEnabled())
                self.assertFalse(home.tunModeSwitch.isEnabled())

                connectionController.setInteractionEnabled(True)
                processQtEvents()

                self.assertTrue(home.systemProxyComboBox.isEnabled())
                self.assertTrue(home.tunModeSwitch.isEnabled())

                settingsSurface.close()
                settingsSurface.deleteLater()

            settingsController.deleteLater()
            connectionController.deleteLater()
            routingController.deleteLater()


class RoutingSelectorQtInteractionTest(unittest.TestCase):
    """Verify semantic routing selection through real combo-box key events."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Drain deferred selector deletion between tests."""
        collectAtBoundary()

    def testKeyboardSelectionPublishesOnceAndExternalStateDoesNotLoop(self):
        """Separate one user request from blocked controller-driven refreshes."""
        options = (
            RoutingOption('route-a', 'Route A'),
            RoutingOption('route-b', 'Route B', separatorBefore=True),
        )
        controller = _RoutingControllerFixture(options, 'route-a')

        with mock.patch(
            'Furious.Widget.RoutingSelector.AppRoutingController',
            return_value=controller,
        ):
            parent = QWidget()
            layout = QVBoxLayout(parent)
            selector = RoutingSelector(parent)

            layout.addWidget(selector)
            parent.show()
            parent.activateWindow()
            selector.setFocus()
            processQtEvents()

            QTest.keyClick(selector, QtCore.Qt.Key.Key_Down)
            processQtEvents()

            self.assertEqual(selector.currentData(), 'route-b')
            self.assertEqual(controller.selections, ['route-b'])

            controller.routing = 'route-a'
            controller.stateChanged.emit(*controller.state())
            processQtEvents()

            self.assertEqual(selector.currentData(), 'route-a')
            self.assertEqual(controller.selections, ['route-b'])

            controller.setInteractionEnabled(False)
            processQtEvents()

            self.assertFalse(selector.isEnabled())

            parent.close()
            parent.deleteLater()

        controller.deleteLater()


class SubscriptionEditorQtInteractionTest(unittest.TestCase):
    """Protect editor completion and destruction through real dialog keys."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish transient native deletion and registry cleanup."""
        collectAtBoundary()

    def testEnterAcceptsValidEditorAndDestroysTransient(self):
        """Route Return through the default button and delete-on-close lifecycle."""
        dialog = _SubscriptionEditorDialog(
            {
                'remark': 'Fixture',
                'webURL': 'https://example.test/subscription',
            }
        )
        reference = weakref.ref(dialog)
        finished = []

        dialog.finished.connect(finished.append)
        dialog.open()

        self.assertTrue(waitFor(dialog.isVisible))

        dialog.urlEdit.setFocus()
        QTest.keyClick(dialog.urlEdit, QtCore.Qt.Key.Key_Return)
        processQtEvents()

        self.assertEqual(finished, [int(AppQDialog.DialogCode.Accepted)])
        self.assertFalse(isValid(dialog))
        self.assertEqual(AppQDialog._openDialogs, {})

        del dialog
        collectAtBoundary()

        self.assertIsNone(reference())

    def testEscapeRejectsEditsWithoutMutatingInputAndDestroysTransient(self):
        """Cancel through Escape without committing or retaining the editor."""
        original = {
            'remark': 'Original',
            'webURL': 'https://example.test/original',
        }
        dialog = _SubscriptionEditorDialog(original)
        reference = weakref.ref(dialog)
        finished = []

        dialog.finished.connect(finished.append)
        dialog.open()

        self.assertTrue(waitFor(dialog.isVisible))

        dialog.remarkEdit.setText('Changed')
        dialog.urlEdit.setText('https://example.test/changed')
        QTest.keyClick(dialog.urlEdit, QtCore.Qt.Key.Key_Escape)
        processQtEvents()

        self.assertEqual(finished, [int(AppQDialog.DialogCode.Rejected)])
        self.assertEqual(
            original,
            {
                'remark': 'Original',
                'webURL': 'https://example.test/original',
            },
        )
        self.assertFalse(isValid(dialog))
        self.assertEqual(AppQDialog._openDialogs, {})

        del dialog
        collectAtBoundary()

        self.assertIsNone(reference())


if __name__ == '__main__':
    unittest.main()
