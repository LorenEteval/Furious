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

from Furious.Actions.Import import ImportURIsProgressDialog, importURIs
from Furious.Backends.Xray.Plugin import XrayPlugin
from Furious.Controllers import ConnectionState
from Furious.Controllers.SettingsController import SettingsController
from Furious.Frozenlib import AppBuiltinProxyMode, AppSettings, Mixins
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Plugins import PluginRegistry
from Furious.Plugins.API import RoutingOption
from Furious.Repository import Storage, SubscriptionGroup
from Furious.Service import ProfileTestField, ProfileTestResult
from Furious.Service.ProfileTesting import ProfileTestTarget
from Furious.Qt import (
    AppQAction,
    AppHue,
    AppQDialog,
    AppQSwitch,
    AppStyleSheet,
    gettext,
)
from Furious.Widget.RoutingSelector import RoutingSelector
from Furious.Widget.ServerTableView import (
    DeleteServersProgressDialog,
    MBoxQuestionDelete,
    ServerTableView,
)
from Furious.Widget.SubscriptionTableView import SubscriptionTableView
from Furious.Window.HomePage import HomePage
from Furious.Window.SettingsPage import (
    _SystemProxySettingsCard,
    _ToggleSettingsCard,
)
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog

from PySide6 import QtCore, QtGui
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QLineEdit, QToolButton, QVBoxLayout, QWidget

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


class _PaintEventCounter(QtCore.QObject):
    """Count viewport paints without synthesizing an unrelated mouse event."""

    def __init__(self, target):
        """Observe paint events delivered to *target*."""
        super().__init__(target)

        self.target = target
        self.count = 0

    def eventFilter(self, watched, event):
        """Count paints while preserving normal viewport event delivery."""
        if watched is self.target and event.type() == QtCore.QEvent.Type.Paint:
            self.count += 1

        return super().eventFilter(watched, event)


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

    def testSearchUsesCurrentDisplayedMetadataWithoutAStaleCache(self):
        """The fast row projection retains regex, literal and live-cell semantics."""
        with isolatedSettings():
            table = self._table(('alpha[1]', 'beta'))
            try:
                table.search('alpha[1]', regex=False)
                self.assertEqual(table.proxyModel.rowCount(), 1)
                table.search('ALPHA', caseSensitive=True)
                self.assertEqual(table.proxyModel.rowCount(), 0)
                table.search('ALPHA')
                self.assertEqual(table.proxyModel.rowCount(), 1)
                table.search('23 ms')
                self.assertEqual(table.proxyModel.rowCount(), 0)
                profile = Storage.UserServers()[1]
                profile.metadata.latency = '23 ms'
                table.sourceModel.emitRowChanged(1)
                self.assertEqual(table.proxyModel.rowCount(), 1)
                self.assertEqual(
                    table.sourceRowFromProxyIndex(table.proxyModel.index(0, 0)), 1
                )
                profile.metadata.latency = '42 ms'
                table.sourceModel.emitRowChanged(1)
                self.assertEqual(table.proxyModel.rowCount(), 0)
            finally:
                self._destroyTable(table)

    def testConnectionStateRepaintsActiveRowWithoutMouseEvent(self):
        """Invalidate the active row's color through source and proxy models."""
        poolType = type(Mixins.ConnectionAware.ObjectsPool)
        connectionController = _ConnectionControllerFixture()

        with (
            isolatedSettings(),
            mock.patch.object(
                Mixins.ConnectionAware,
                'ObjectsPool',
                poolType(),
            ),
            mock.patch(
                'Furious.Qt.DynamicTheme.AppConnectionController',
                return_value=connectionController,
            ),
            mock.patch('Furious.Qt.DynamicTheme.SystemRuntime.isAdmin') as isAdmin,
        ):
            table = self._table(('target', 'zulu', 'alpha'))
            target = Storage.UserServers()[0]
            target.metadata.subscriptionSource = 'group-a'
            target.metadata.subscriptionManaged = True
            paintCounter = _PaintEventCounter(table.viewport())
            table.viewport().installEventFilter(paintCounter)

            def assertVisualTransition(state, admin, expectedColor, resolvedTheme):
                """Assert one semantic color invalidation and resulting paint."""
                connectionController.state = state
                isAdmin.return_value = admin

                sourceSpy = QSignalSpy(table.sourceModel.dataChanged)
                proxySpy = QSignalSpy(table.proxyModel.dataChanged)
                paintCounter.count = 0

                callback = (
                    Mixins.ConnectionAware.callConnectedCallback
                    if state is ConnectionState.Connected
                    else Mixins.ConnectionAware.callDisconnectedCallback
                )

                with mock.patch.object(
                    application(),
                    'theme',
                    return_value=resolvedTheme,
                ):
                    callback()
                    processQtEvents()

                activeRow = Storage.UserActivatedItemIndex()
                sourceIndex = table.sourceModel.index(activeRow, 0)
                proxyIndex = table.proxyIndexFromSourceRow(activeRow)
                expectedRoles = (int(QtCore.Qt.ItemDataRole.ForegroundRole),)

                self.assertTrue(sourceIndex.isValid())
                self.assertTrue(proxyIndex.isValid())
                self.assertEqual(sourceSpy.count(), 1)
                self.assertEqual(proxySpy.count(), 1)

                sourceArguments = sourceSpy.at(0)
                proxyArguments = proxySpy.at(0)

                self.assertEqual(sourceArguments[0].row(), activeRow)
                self.assertEqual(sourceArguments[0].column(), 0)
                self.assertEqual(sourceArguments[1].row(), activeRow)
                self.assertEqual(
                    sourceArguments[1].column(),
                    table.sourceModel.columnCount() - 1,
                )
                self.assertEqual(
                    tuple(int(role) for role in sourceArguments[2]),
                    expectedRoles,
                )

                self.assertEqual(proxyArguments[0].row(), proxyIndex.row())
                self.assertEqual(proxyArguments[1].row(), proxyIndex.row())
                self.assertEqual(
                    tuple(int(role) for role in proxyArguments[2]),
                    expectedRoles,
                )

                self.assertEqual(
                    table.sourceModel.data(
                        sourceIndex,
                        QtCore.Qt.ItemDataRole.ForegroundRole,
                    ),
                    QtGui.QColor(expectedColor),
                )
                self.assertGreater(
                    paintCounter.count,
                    0,
                    'the data change must schedule a paint without mouse movement',
                )

            try:
                self.assertIsInstance(table, Mixins.ConnectionAware)
                self.assertEqual(
                    table.sourceModel.data(
                        table.sourceModel.index(0, 0),
                        QtCore.Qt.ItemDataRole.ForegroundRole,
                    ),
                    QtGui.QColor(AppHue.disconnectedColor()),
                )

                assertVisualTransition(
                    ConnectionState.Connected,
                    False,
                    AppHue.ColorRGB.LIGHT_RED,
                    'Dark',
                )
                assertVisualTransition(
                    ConnectionState.Disconnected,
                    False,
                    AppHue.disconnectedColor(),
                    'Light',
                )

                table.search('target')
                table.proxyModel.setSubscriptionFilter('group-a')
                table.sortByColumn(0, QtCore.Qt.SortOrder.DescendingOrder)
                processQtEvents()

                self.assertIs(
                    Storage.UserServers()[Storage.UserActivatedItemIndex()],
                    target,
                )
                assertVisualTransition(
                    ConnectionState.Connected,
                    True,
                    AppHue.ColorRGB.LIGHT_PURPLE,
                    'Light',
                )
                assertVisualTransition(
                    ConnectionState.Disconnected,
                    True,
                    AppHue.disconnectedColor(),
                    'Dark',
                )
            finally:
                self._destroyTable(table)

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

    def testTestActionsUseOnlyMultithreadedDownloadSpeedAction(self):
        """Expose one download command backed by the multithreaded scheduler."""
        with isolatedSettings():
            table = self._table(('one',))

            try:
                actions = tuple(
                    action
                    for action in table.testActions
                    if isinstance(action, AppQAction)
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


class SubscriptionTableQtInteractionTest(unittest.TestCase):
    """Protect subscription ordering through real selection and shortcuts."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Release the subscription repository and deferred table objects."""
        Storage._UserSubsStorage.cache_clear()
        collectAtBoundary()

    @staticmethod
    def _table(parent=None):
        """Build one visible table with deterministic stable subscription IDs."""
        for order, unique in enumerate(('A', 'B', 'C', 'D', 'E')):
            Storage.upsertSubscriptionGroup(
                SubscriptionGroup(
                    id=unique,
                    remark=unique,
                    sortOrder=order,
                )
            )

        table = SubscriptionTableView(parent=parent)
        table.resize(900, 360)
        table.show()
        table.activateWindow()
        processQtEvents()

        return table

    def _clickRow(self, table, row, modifiers=QtCore.Qt.NoModifier):
        """Select one subscription row through the real viewport mouse path."""
        index = table.sourceModel.index(row, 0)
        rectangle = table.visualRect(index)

        self.assertTrue(index.isValid())
        self.assertFalse(rectangle.isEmpty())

        QTest.mouseClick(
            table.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifiers,
            rectangle.center(),
        )
        processQtEvents()

    @staticmethod
    def _destroyTable(table):
        """Release the persistent table, menu, and owned actions through Qt."""
        table.close()
        table.deleteLater()

    @contextmanager
    def _deleteConfirmation(self, table):
        """Open the real asynchronous prompt and release it after each case."""
        confirmation = MBoxQuestionDelete(parent=table)

        try:
            with mock.patch(
                'Furious.Widget.SubscriptionTableView.MBoxQuestionDelete',
                return_value=confirmation,
            ):
                table.deleteSelectedItem()

            self.assertTrue(waitFor(confirmation.isVisible))

            yield confirmation
        finally:
            if isValid(confirmation):
                confirmation.close()

            processQtEvents()

    def testDeleteConfirmationKeepsCapturedGroupsAfterReordering(self):
        """Delete the original IDs at their current rows despite selection changes."""
        for position, expectedRows in (
            (None, (1, 2)),
            ('down', (2, 3)),
            ('up', (0, 1)),
        ):
            with self.subTest(position=position), isolatedSettings():
                Storage._UserSubsStorage.cache_clear()

                table = self._table()
                table.subsManager = mock.Mock()
                table.deleteUniqueCallback = mock.Mock()

                try:
                    self._clickRow(table, 1)
                    self._clickRow(table, 3, QtCore.Qt.KeyboardModifier.ControlModifier)

                    with self._deleteConfirmation(table) as confirmation:
                        if position is not None:
                            table.moveSelectedGroups(position)

                        table.clearSelection()
                        table.setCurrentIndex(table.sourceModel.index(0, 0))

                        removed = QSignalSpy(table.sourceModel.rowsRemoved)
                        changed = QSignalSpy(table.groupsChanged)

                        confirmation.done(int(confirmation.StandardButton.Yes))
                        processQtEvents()

                        self.assertEqual(tuple(Storage.UserSubs()), ('A', 'C', 'E'))
                        self.assertEqual(
                            [item['sortOrder'] for item in Storage.UserSubs().values()],
                            [0, 1, 2],
                        )
                        self.assertEqual(
                            table.deleteUniqueCallback.call_args_list,
                            [mock.call('B'), mock.call('D')],
                        )
                        self.assertEqual(
                            table.subsManager.removeAutoUpdate.call_args_list,
                            [mock.call('B'), mock.call('D')],
                        )
                        self.assertEqual(removed.count(), 2)
                        self.assertEqual(
                            [(removed.at(i)[1], removed.at(i)[2]) for i in range(2)],
                            [(row, row) for row in expectedRows],
                        )
                        self.assertEqual(changed.count(), 1)
                        self.assertFalse(isValid(confirmation))
                finally:
                    self._destroyTable(table)

    def testDeleteConfirmationSkipsMissingGroupsAndPreservesNewGroups(self):
        """Ignore vanished targets without retargeting their replacement rows."""
        for missing in (('B',), ('B', 'D')):
            with self.subTest(missing=missing), isolatedSettings():
                Storage._UserSubsStorage.cache_clear()

                table = self._table()
                table.subsManager = mock.Mock()
                table.deleteUniqueCallback = mock.Mock()

                try:
                    self._clickRow(table, 1)
                    self._clickRow(table, 3, QtCore.Qt.KeyboardModifier.ControlModifier)

                    with self._deleteConfirmation(table) as confirmation:
                        for unique in missing:
                            row = tuple(Storage.UserSubs()).index(unique)

                            table.sourceModel.beginRemoveRows(
                                QtCore.QModelIndex(), row, row
                            )
                            Storage.removeSubscriptionGroup(unique)
                            table.sourceModel.endRemoveRows()

                        table.appendNewItem(unique='F', remark='F')

                        removed = QSignalSpy(table.sourceModel.rowsRemoved)
                        changed = QSignalSpy(table.groupsChanged)
                        expectedCalls = [] if 'D' in missing else [mock.call('D')]

                        confirmation.done(int(confirmation.StandardButton.Yes))
                        processQtEvents()

                        self.assertEqual(
                            tuple(Storage.UserSubs()), ('A', 'C', 'E', 'F')
                        )
                        self.assertEqual(
                            table.deleteUniqueCallback.call_args_list, expectedCalls
                        )
                        self.assertEqual(
                            table.subsManager.removeAutoUpdate.call_args_list,
                            expectedCalls,
                        )
                        self.assertEqual(removed.count(), len(expectedCalls))
                        self.assertEqual(changed.count(), len(expectedCalls))
                        self.assertFalse(isValid(confirmation))
                finally:
                    self._destroyTable(table)

    def testDeleteConfirmationRejectionLeavesGroupsUntouched(self):
        """Keep cancellation and window-close paths free of deletion side effects."""
        for closeWindow in (False, True):
            with self.subTest(closeWindow=closeWindow), isolatedSettings():
                Storage._UserSubsStorage.cache_clear()

                table = self._table()
                table.subsManager = mock.Mock()
                table.deleteUniqueCallback = mock.Mock()

                try:
                    self._clickRow(table, 1)

                    with self._deleteConfirmation(table) as confirmation:
                        removed = QSignalSpy(table.sourceModel.rowsRemoved)
                        changed = QSignalSpy(table.groupsChanged)

                        if closeWindow:
                            confirmation.close()
                        else:
                            confirmation.done(int(confirmation.StandardButton.No))

                        processQtEvents()

                        self.assertEqual(
                            tuple(Storage.UserSubs()), ('A', 'B', 'C', 'D', 'E')
                        )
                        table.deleteUniqueCallback.assert_not_called()
                        table.subsManager.removeAutoUpdate.assert_not_called()
                        self.assertEqual(removed.count(), 0)
                        self.assertEqual(changed.count(), 0)
                        self.assertFalse(isValid(confirmation))
                finally:
                    self._destroyTable(table)

    def testContextMenuHasOnlyWidgetScopedMoveShortcuts(self):
        """Expose only table-scoped Ctrl+Up and Ctrl+Down move commands."""
        with isolatedSettings():
            table = self._table()

            try:
                actions = tuple(
                    action
                    for action in table.contextMenu.actions()
                    if not action.isSeparator()
                )

                self.assertEqual(
                    [action.textEnglish for action in actions],
                    ['Move Up', 'Move Down'],
                )
                self.assertNotIn('Delete', [action.textEnglish for action in actions])

                for action, key in (
                    (table.moveUpActionRef, QtCore.Qt.Key.Key_Up),
                    (table.moveDownActionRef, QtCore.Qt.Key.Key_Down),
                ):
                    self.assertEqual(
                        action.shortcut(),
                        QtGui.QKeySequence(
                            QtCore.QKeyCombination(
                                QtCore.Qt.KeyboardModifier.ControlModifier,
                                key,
                            )
                        ),
                    )
                    self.assertEqual(
                        action.shortcutContext(),
                        QtCore.Qt.ShortcutContext.WidgetShortcut,
                    )
                    self.assertIn(action, table.actions())
                    self.assertIs(action.parent(), table)
            finally:
                self._destroyTable(table)

    def testMultiMoveShortcutsPreserveIdentityCurrentItemAndFocus(self):
        """Keep noncontiguous selection ready across repeated keyboard moves."""
        with isolatedSettings():
            table = self._table()

            try:
                self._clickRow(table, 1)
                self._clickRow(
                    table,
                    3,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )

                selected = {'B', 'D'}
                current = 'D'

                for expected in (
                    ('B', 'A', 'D', 'C', 'E'),
                    ('B', 'D', 'A', 'C', 'E'),
                ):
                    QTest.keyClick(
                        table,
                        QtCore.Qt.Key.Key_Up,
                        QtCore.Qt.KeyboardModifier.ControlModifier,
                    )
                    processQtEvents()

                    self.assertEqual(tuple(Storage.UserSubs()), expected)
                    self.assertEqual(set(table.selectedUniques), selected)
                    self.assertEqual(table._currentUnique(), current)
                    self.assertTrue(table.hasFocus())

                QTest.keyClick(
                    table,
                    QtCore.Qt.Key.Key_Down,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )
                processQtEvents()

                self.assertEqual(
                    tuple(Storage.UserSubs()),
                    ('A', 'B', 'D', 'C', 'E'),
                )
                self.assertEqual(set(table.selectedUniques), selected)
                self.assertEqual(table._currentUnique(), current)
                self.assertTrue(table.hasFocus())
            finally:
                self._destroyTable(table)

    def testMoveShortcutDoesNotFireFromSiblingEditor(self):
        """Keep subscription movement inactive while a sibling editor has focus."""
        with isolatedSettings():
            window = QWidget()
            layout = QVBoxLayout(window)
            editor = QLineEdit(window)
            table = self._table(parent=window)

            layout.addWidget(editor)
            layout.addWidget(table)
            window.resize(900, 500)
            window.show()
            window.activateWindow()
            processQtEvents()

            try:
                self._clickRow(table, 1)
                editor.setFocus()

                self.assertTrue(waitFor(lambda: application().focusWidget() is editor))

                before = tuple(Storage.UserSubs())

                QTest.keyClick(
                    editor,
                    QtCore.Qt.Key.Key_Down,
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                )
                processQtEvents()

                self.assertEqual(tuple(Storage.UserSubs()), before)
                self.assertIs(application().focusWidget(), editor)
            finally:
                self._destroyTable(table)
                window.close()
                window.deleteLater()


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
    def _home(
        self,
        settingsController,
        connectionController,
        routingController,
        *,
        importActions=(),
    ):
        """Build the smallest side-effect-free real Home composition."""
        registry = mock.Mock()
        registry.protocolDescriptors.return_value = ()

        with ExitStack() as stack:
            for target, value in (
                ('Furious.Window.HomePage.AppSettingsController', settingsController),
                (
                    'Furious.Widget.ServerTableView.AppConnectionController',
                    connectionController,
                ),
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
                mock.patch.object(
                    HomePage, 'serverImportActions', return_value=importActions
                )
            )

            home = HomePage()

            try:
                yield home
            finally:
                home.trafficStatsManager.cleanup()
                home.userServersQTableWidget.cleanup()
                home.close()
                home.deleteLater()

    def testHomeSearchDebouncesTypingAndRetainsStableProfileIdentity(self):
        """Search without Enter, then clear immediately without stale timer work."""
        with isolatedSettings():
            settings = SettingsController()
            connection = _ConnectionControllerFixture()
            routing = _RoutingControllerFixture(
                (RoutingOption('default', 'Default'),), 'default'
            )
            try:
                with self._home(settings, connection, routing) as home:
                    table = home.userServersQTableWidget
                    profiles = [
                        ServerTableQtInteractionTest._profile(name)
                        for name in ('alpha', 'beta')
                    ]
                    for profile in profiles:
                        table.appendNewItemByFactory(profile)
                    home.show()
                    home.activateWindow()
                    table.setFocus()
                    processQtEvents()
                    QTest.keyClick(table, QtCore.Qt.Key_F, QtCore.Qt.ControlModifier)
                    self.assertTrue(waitFor(home.searchLineEdit.hasFocus))
                    with mock.patch.object(
                        table, 'search', wraps=table.search
                    ) as search:
                        QTest.keyClicks(home.searchLineEdit, 'alpha')
                        self.assertEqual(search.call_count, 0)
                        self.assertTrue(
                            waitFor(lambda: table.proxyModel.rowCount() == 1)
                        )
                        self.assertEqual(search.call_count, 1)
                        self.assertEqual(
                            table.sourceRowFromProxyIndex(table.proxyModel.index(0, 0)),
                            0,
                        )
                        home.searchLineEdit.setText('beta')
                        home.searchLineEdit.clear()
                        self.assertEqual(table.proxyModel.rowCount(), 2)
                        self.assertFalse(home._searchTimer.isActive())
                        home.searchLineEdit.setText('beta')
                        QTest.keyClick(home.searchLineEdit, QtCore.Qt.Key_Return)
                        self.assertEqual(table.proxyModel.rowCount(), 1)
                        self.assertFalse(home._searchTimer.isActive())
                        self.assertEqual(
                            table.sourceRowFromProxyIndex(table.proxyModel.index(0, 0)),
                            1,
                        )
                    self.assertEqual(list(Storage.UserServers()), profiles)
                    home.searchLineEdit.setText('alpha')
                    home.hide()
                    self.assertFalse(home._searchTimer.isActive())
                    home.show()
                    self.assertEqual(table.proxyModel.rowCount(), 1)
                    self.assertEqual(
                        table.sourceRowFromProxyIndex(table.proxyModel.index(0, 0)), 0
                    )
            finally:
                settings.deleteLater()
                connection.deleteLater()
                routing.deleteLater()

    def testHomeTestsMenuPreservesSelectionAndHighlight(self):
        """Keep mouse-opened tests tied to visibly selected, mapped profiles."""
        with isolatedSettings():
            settings = SettingsController()
            connection = _ConnectionControllerFixture()
            routing = _RoutingControllerFixture(
                (RoutingOption('default', 'Default'),), 'default'
            )
            profiles = [
                ServerTableQtInteractionTest._profile(name)
                for name in ('match zeta', 'hidden', 'match alpha')
            ]
            Storage.UserServers().extend(profiles)
            try:
                with self._home(settings, connection, routing) as home:
                    home.resize(1000, 600)
                    home.show()
                    home.activateWindow()
                    table = home.userServersQTableWidget
                    home.searchLineEdit.setText('match')
                    home.applySearch()
                    table.sortByColumn(0, QtCore.Qt.AscendingOrder)
                    processQtEvents()
                    expectedIds = {
                        p.metadata.profileId for p in (profiles[0], profiles[2])
                    }
                    for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                        with self.subTest(theme=theme), mock.patch.object(
                            application(), 'theme', return_value=theme
                        ):
                            home.setStyleSheet(AppStyleSheet.forTheme(theme))
                            table.setFocus()
                            QTest.mouseClick(
                                table.viewport(),
                                QtCore.Qt.LeftButton,
                                QtCore.Qt.NoModifier,
                                table.visualRect(table.proxyModel.index(0, 0)).center(),
                            )
                            QTest.mouseClick(
                                table.viewport(),
                                QtCore.Qt.LeftButton,
                                QtCore.Qt.ControlModifier,
                                table.visualRect(table.proxyModel.index(1, 0)).center(),
                            )
                            QTest.keyRelease(table, QtCore.Qt.Key_Control)
                            processQtEvents()
                            rect = table.visualRect(table.proxyModel.index(0, 0))
                            sample = QtCore.QPoint(rect.right() - 12, rect.center().y())
                            before = (
                                table.viewport().grab().toImage().pixelColor(sample)
                            )
                            self.assertEqual(
                                before,
                                QtGui.QColor(
                                    AppStyleSheet.paletteForTheme(theme)['selection']
                                ),
                            )
                            # A real click can paint between press and release.
                            QTest.mousePress(home.testButton, QtCore.Qt.LeftButton)
                            processQtEvents()
                            self.assertFalse(home.testMenu.isVisible())
                            self.assertEqual(
                                table.viewport().grab().toImage().pixelColor(sample),
                                before,
                            )
                            QTest.mouseRelease(home.testButton, QtCore.Qt.LeftButton)
                            processQtEvents()
                            self.assertTrue(home.testMenu.isVisible())
                            self.assertEqual(
                                {
                                    Storage.UserServers()[i].metadata.profileId
                                    for i in table.selectedIndex
                                },
                                expectedIds,
                            )
                            self.assertEqual(
                                table.viewport().grab().toImage().pixelColor(sample),
                                before,
                            )
                            with mock.patch.object(
                                table.profileTestManager, 'testPing'
                            ) as testPing:
                                home.testMenu.setActiveAction(table.testActions[0])
                                QTest.keyClick(home.testMenu, QtCore.Qt.Key_Return)
                                processQtEvents()
                                testPing.assert_called_once()
                                self.assertEqual(
                                    {
                                        p.metadata.profileId
                                        for p in testPing.call_args.args[0]
                                    },
                                    expectedIds,
                                )
                            self.assertTrue(home.testButton.hasFocus())
                            self.assertEqual(
                                table.viewport().grab().toImage().pixelColor(sample),
                                before,
                            )
                            # A cancelled click must not open a menu or leave a
                            # highlight override after focus moves elsewhere.
                            QTest.mousePress(home.testButton, QtCore.Qt.LeftButton)
                            QTest.mouseRelease(
                                home.testButton,
                                QtCore.Qt.LeftButton,
                                pos=QtCore.QPoint(-10, -10),
                            )
                            processQtEvents()
                            self.assertFalse(home.testMenu.isVisible())
                            home.searchLineEdit.setFocus()
                            processQtEvents()
                            self.assertFalse(table.property('keepSelectionHighlighted'))
                            self.assertEqual(
                                table.viewport().grab().toImage().pixelColor(sample),
                                QtGui.QColor(
                                    AppStyleSheet.paletteForTheme(theme)['raised']
                                ),
                            )

                    # Opening and dismissing from the keyboard returns to the button.
                    home.testButton.setFocus(QtCore.Qt.TabFocusReason)
                    processQtEvents()
                    before = table.viewport().grab().toImage().pixelColor(sample)
                    QTest.keyPress(home.testButton, QtCore.Qt.Key_Space)
                    processQtEvents()
                    self.assertEqual(
                        table.viewport().grab().toImage().pixelColor(sample), before
                    )
                    QTest.keyRelease(home.testButton, QtCore.Qt.Key_Space)
                    processQtEvents()
                    self.assertTrue(home.testMenu.isVisible())
                    QTest.keyClick(home.testMenu, QtCore.Qt.Key_Escape)
                    processQtEvents()
                    self.assertTrue(home.testButton.hasFocus())
                    home.searchLineEdit.setFocus()
                    with mock.patch.object(
                        table.profileTestManager, 'testPing'
                    ) as testPing:
                        QTest.keyClick(
                            home.searchLineEdit,
                            QtCore.Qt.Key_P,
                            QtCore.Qt.ControlModifier,
                        )
                        QTest.keyRelease(home.searchLineEdit, QtCore.Qt.Key_Control)
                        processQtEvents()
                        testPing.assert_not_called()
            finally:
                settings.deleteLater()
                connection.deleteLater()
                routing.deleteLater()

    def testHomeEmptyStateRecoversFilteredProfilesAndReusesActions(self):
        """Use existing menus, search clear and group selection to recover profiles."""
        with isolatedSettings():
            AppSettings.set('Language', 'EN')
            settings = SettingsController()
            connection = _ConnectionControllerFixture()
            routing = _RoutingControllerFixture(
                (RoutingOption('default', 'Default'),), 'default'
            )

            imported = []
            action = AppQAction(
                'Fixture import',
                callback=lambda: imported.append(True),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.ControlModifier, QtCore.Qt.Key_V
                ),
                translatable=False,
            )

            try:
                with self._home(
                    settings, connection, routing, importActions=(action,)
                ) as home:
                    home.resize(1000, 600)
                    home.show()
                    home.activateWindow()
                    processQtEvents()

                    self.assertTrue(home.emptyState.isVisible())
                    self.assertIn('No profiles yet', home.emptyStateLabel.text())
                    self.assertIs(home.importMenu.actions()[0], action)
                    self.assertNotIn(
                        action, home.userServersQTableWidget.contextMenu.actions()
                    )

                    QTest.mouseClick(home.importButton, QtCore.Qt.LeftButton)
                    processQtEvents()

                    QTest.keyClick(home.importMenu, QtCore.Qt.Key_Down)
                    QTest.keyClick(home.importMenu, QtCore.Qt.Key_Return)
                    processQtEvents()

                    self.assertEqual(imported, [True])

                    table = home.userServersQTableWidget
                    table.setFocus()
                    processQtEvents()
                    QTest.keyClick(table, QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)
                    processQtEvents()

                    self.assertEqual(imported, [True, True])
                    self.assertEqual(
                        action.shortcutContext(),
                        QtCore.Qt.ShortcutContext.WidgetShortcut,
                    )

                    profile = ServerTableQtInteractionTest._profile('alpha')
                    home.userServersQTableWidget.appendNewItemByFactory(profile)
                    processQtEvents()

                    self.assertFalse(home.emptyState.isVisible())

                    home.searchLineEdit.setFocus()
                    QTest.keyClicks(home.searchLineEdit, 'missing')
                    QTest.keyClick(home.searchLineEdit, QtCore.Qt.Key_Return)
                    processQtEvents()

                    self.assertTrue(home.emptyState.isVisible())

                    QTest.mouseClick(
                        home.searchLineEdit.findChild(QToolButton), QtCore.Qt.LeftButton
                    )
                    processQtEvents()

                    self.assertFalse(home.emptyState.isVisible())
                    self.assertTrue(home.searchLineEdit.hasFocus())
                    self.assertEqual(home.searchLineEdit.text(), '')
                    self.assertIs(Storage.UserServers()[0], profile)

                    home.subscriptionFilterComboBox.addItem(
                        'Empty group', 'missing-group'
                    )
                    home.subscriptionFilterComboBox.setCurrentIndex(2)
                    processQtEvents()

                    self.assertTrue(home.emptyState.isVisible())

                    home.subscriptionFilterComboBox.setFocus()
                    QTest.keyClick(home.subscriptionFilterComboBox, QtCore.Qt.Key_Home)
                    processQtEvents()

                    self.assertEqual(home.subscriptionFilterComboBox.currentIndex(), 0)
                    self.assertEqual(
                        home.userServersQTableWidget.proxyModel.rowCount(), 1
                    )

                    testActions = [
                        action
                        for action in table.testActions
                        if isinstance(action, AppQAction)
                    ]
                    contextActions = table.contextMenu.actions()
                    testSection = home.testMenu.actions()

                    self.assertEqual(len(testActions), 5)
                    self.assertEqual(
                        [action for action in testSection if not action.isSeparator()],
                        testActions,
                    )
                    self.assertEqual(
                        [
                            None if action.isSeparator() else action.text()
                            for action in testSection
                        ],
                        [
                            'Test Ping Latency',
                            'Test Tcping Latency',
                            'Test Download Speed',
                            None,
                            'Clear Test Results',
                            None,
                            'Stop All Tests',
                        ],
                    )
                    self.assertTrue(testActions[-1].icon().isNull())
                    self.assertIs(home.testButton.popupMenu(), home.testMenu)
                    for testAction in testActions:
                        self.assertNotIn(testAction, contextActions)
                        self.assertIn(testAction, table.actions())

                    table.setFocus()
                    processQtEvents()

                    for key, method in (
                        (QtCore.Qt.Key_P, 'testSelectedItemPingLatency'),
                        (QtCore.Qt.Key_O, 'testSelectedItemTcpingLatency'),
                        (QtCore.Qt.Key_M, 'testSelectedItemDownloadSpeedMulti'),
                        (QtCore.Qt.Key_R, 'clearSelectedItemTestResult'),
                    ):
                        with mock.patch.object(table, method) as callback:
                            QTest.keyClick(table, key, QtCore.Qt.ControlModifier)
                            processQtEvents()

                            callback.assert_called_once_with()

                    manager = home.userServersQTableWidget.profileTestManager

                    with mock.patch.object(
                        manager._latencyScheduler, 'cancelAll'
                    ) as cancel:
                        table = home.userServersQTableWidget
                        menu = home.testMenu
                        QTest.mouseClick(home.testButton, QtCore.Qt.LeftButton)
                        processQtEvents()
                        menu.setActiveAction(table.testActions[-1])
                        QTest.keyClick(menu, QtCore.Qt.Key_Return)
                        processQtEvents()

                    cancel.assert_called_once_with()

                    home.userServersQTableWidget.deleteItemByIndex(
                        [0], showTrayMessage=False, showProgress=False
                    )
                    processQtEvents()

                    self.assertTrue(home.emptyState.isVisible())
                    self.assertIn('No profiles yet', home.emptyStateLabel.text())
            finally:
                settings.deleteLater()
                connection.deleteLater()
                routing.deleteLater()

    def testHomeTunModeLabelExplainsMissingAdministratorPrivilege(self):
        """Use the same privilege-aware TUN presentation as Settings."""
        with (
            isolatedSettings(),
            mock.patch(
                'Furious.Controllers.SettingsController.PLATFORM',
                'Windows',
            ),
            mock.patch(
                'Furious.Controllers.SettingsController.SystemRuntime.isAdmin',
                return_value=False,
            ),
            mock.patch(
                'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
            ),
            mock.patch(
                'Furious.Window.TunSettingsDialog.PLATFORM',
                'Windows',
            ),
            mock.patch(
                'Furious.Window.TunSettingsDialog.ADMINISTRATOR_NAME',
                'Administrator',
            ),
        ):
            settingsController = SettingsController()
            connectionController = _ConnectionControllerFixture()
            routingController = _RoutingControllerFixture(
                (RoutingOption('default', 'Default'),),
                'default',
            )

            with self._home(
                settingsController,
                connectionController,
                routingController,
            ) as home:
                self.assertEqual(
                    gettext(home.tunModeLabel.text(), 'EN'),
                    'TUN Mode Disabled (Administrator)',
                )
                self.assertFalse(home.tunModeSwitch.isEnabled())

            settingsController.deleteLater()
            connectionController.deleteLater()
            routingController.deleteLater()

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
                settingsController.tunModeChanged.connect(
                    tunCard.checkBox.syncCheckedAnimated
                )
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

                for switch in (home.tunModeSwitch, tunCard.checkBox):
                    self.assertEqual(
                        switch._animation.state(),
                        QtCore.QAbstractAnimation.State.Running,
                    )

                QTest.qWait(AppQSwitch.AnimationDuration + 40)
                processQtEvents()

                self.assertTrue(home.tunModeSwitch.isChecked())
                self.assertTrue(tunCard.checkBox.isChecked())
                self.assertEqual(home.tunModeSwitch.thumbPosition, 1.0)
                self.assertEqual(tunCard.checkBox.thumbPosition, 1.0)
                self.assertEqual(tunStates, [True])

                QTest.mouseClick(
                    tunCard.checkBox,
                    QtCore.Qt.MouseButton.LeftButton,
                    pos=tunCard.checkBox.rect().center(),
                )

                for switch in (home.tunModeSwitch, tunCard.checkBox):
                    self.assertEqual(
                        switch._animation.state(),
                        QtCore.QAbstractAnimation.State.Running,
                    )

                QTest.qWait(AppQSwitch.AnimationDuration + 40)
                processQtEvents()

                self.assertFalse(home.tunModeSwitch.isChecked())
                self.assertFalse(tunCard.checkBox.isChecked())
                self.assertEqual(home.tunModeSwitch.thumbPosition, 0.0)
                self.assertEqual(tunCard.checkBox.thumbPosition, 0.0)
                self.assertEqual(tunStates, [True, False])

                QTest.mouseClick(
                    home.tunModeSwitch,
                    QtCore.Qt.MouseButton.LeftButton,
                    pos=home.tunModeSwitch.rect().center(),
                )
                QTest.qWait(20)
                QTest.mouseClick(
                    home.tunModeSwitch,
                    QtCore.Qt.MouseButton.LeftButton,
                    pos=home.tunModeSwitch.rect().center(),
                )
                QTest.qWait(AppQSwitch.AnimationDuration + 40)
                processQtEvents()

                self.assertFalse(home.tunModeSwitch.isChecked())
                self.assertFalse(tunCard.checkBox.isChecked())
                self.assertEqual(home.tunModeSwitch.thumbPosition, 0.0)
                self.assertEqual(tunCard.checkBox.thumbPosition, 0.0)
                self.assertEqual(tunStates, [True, False, True, False])

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


class ProfileMutationBatchTest(unittest.TestCase):
    """Exercise real model mutations with bounded progress and stable targets."""

    @classmethod
    def setUpClass(cls):
        application()

    def tearDown(self):
        collectAtBoundary()

    @staticmethod
    def profile(name):
        return ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture'}), {'displayName': name}
        )

    @contextmanager
    def table(self, count=0):
        controller = mock.Mock()
        controller.isConnected.return_value = False

        with (
            isolatedSettings(),
            mock.patch.object(Storage, 'UserServers', return_value=[]),
            mock.patch(
                'Furious.Widget.ServerTableView.AppConnectionController',
                return_value=controller,
            ),
        ):
            Storage.UserServers().extend(
                self.profile(f'profile-{index:04}') for index in range(count)
            )
            AppSettings.set('ActivatedItemIndex', str(count - 1))

            table = ServerTableView(
                configurationEditorFactory=QWidget,
                qrCodeWindowFactory=QWidget,
                importActionsFactory=tuple,
            )
            table.sourceModel.refreshIndexes()

            try:
                yield table, controller
            finally:
                table.cleanup()
                table.close()
                table.deleteLater()
                processQtEvents()

    def testImportCoalescesRowsAndProgressWithoutLosingInvalidInputPositions(self):
        profiles = [self.profile(str(index)) for index in range(600)]
        invalid = mock.Mock()
        invalid.isValid.return_value = False
        parsed = [
            invalid if index in (200, 501) else item
            for index, item in enumerate(profiles)
        ]
        expected = [item for item in parsed if item is not invalid]

        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch('Furious.Actions.Import.profileFromAny', side_effect=parsed),
            mock.patch.object(ServerProfile, 'isValid', return_value=True),
            mock.patch('Furious.Actions.Import.time') as clock,
            mock.patch('Furious.Actions.Import.singleShotWeakly') as schedule,
            mock.patch('Furious.Actions.Import.MBoxImportMultiSuccess') as success,
            mock.patch.object(
                table, 'reconcileProfileTestJobs', wraps=table.reconcileProfileTestJobs
            ) as reconcile,
            mock.patch.object(
                table.sourceModel,
                'refreshIndexes',
                wraps=table.sourceModel.refreshIndexes,
            ) as refresh,
        ):
            clock.monotonic.return_value = 10.0
            failure = mock.Mock()
            dialog = ImportURIsProgressDialog(
                tuple('input' for _ in parsed), failure, parent=table
            )
            inserted = QSignalSpy(table.sourceModel.rowsInserted)

            with mock.patch.object(
                dialog, 'updateStatus', wraps=dialog.updateStatus
            ) as status:
                dialog.importNext()

                self.assertEqual(dialog.currentIndex, 128)
                self.assertEqual(len(Storage.UserServers()), 128)
                status.assert_not_called()

                clock.monotonic.return_value = 10.101
                dialog.importNext()

                self.assertEqual(dialog.currentIndex, 256)
                self.assertEqual(status.call_count, 1)
                self.assertIn('256/600', dialog.statusLabel.text())

                for _index in range(4):
                    dialog.importNext()

                self.assertEqual(status.call_count, 2)

            self.assertEqual(Storage.UserServers(), expected)
            self.assertEqual(dialog.imported, [item.itemRemark for item in expected])
            self.assertEqual(
                [item.index for item in expected], list(range(len(expected)))
            )

            self.assertEqual(inserted.count(), 5)
            self.assertEqual(
                [(inserted.at(i)[1], inserted.at(i)[2]) for i in range(5)],
                [(0, 127), (128, 254), (255, 382), (383, 509), (510, 597)],
            )

            self.assertEqual(reconcile.call_count, 5)
            refresh.assert_not_called()
            self.assertEqual(schedule.call_count, 4)
            success.return_value.open.assert_called_once()
            failure.assert_not_called()
            self.assertEqual(Storage.UserActivatedItemIndex(), 0)

    def testSlowParserYieldsAndCancellationPreservesCommittedBatch(self):
        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch.object(ServerProfile, 'isValid', return_value=True),
            mock.patch('Furious.Actions.Import.time') as clock,
            mock.patch('Furious.Actions.Import.singleShotWeakly'),
            mock.patch('Furious.Actions.Import.MBoxImportSuccess') as success,
        ):
            clock.monotonic.return_value = 10.0
            profile = self.profile('first')

            def parse(_uri):
                clock.monotonic.return_value += 0.010
                return profile

            with mock.patch(
                'Furious.Actions.Import.profileFromAny', side_effect=parse
            ) as parser:
                dialog = ImportURIsProgressDialog(
                    ('first', 'second', 'third'), parent=table
                )

                dialog.importNext()

                self.assertEqual(dialog.currentIndex, 1)
                self.assertEqual(Storage.UserServers(), [profile])

                dialog.cancel()
                dialog.importNext()
                dialog.importNext()

                self.assertTrue(dialog.finishedImport)
                parser.assert_called_once()
                success.assert_not_called()

    def testInvalidImportReportsFailureOnce(self):
        invalid = mock.Mock()
        invalid.isValid.return_value = False

        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.profileFromAny', return_value=invalid),
            mock.patch('Furious.Actions.Import.AppMainWindow') as window,
        ):
            failure = mock.Mock()
            dialog = ImportURIsProgressDialog(
                ('invalid', 'invalid'), failure, parent=table
            )

            dialog.importNext()
            dialog.importNext()

            failure.assert_called_once_with()
            window.assert_not_called()
            self.assertEqual(Storage.UserServers(), [])

    def testDeletionCoalescesContiguousRowsAndDisconnectsActiveProfileOnce(self):
        with (
            self.table(1000) as (table, controller),
            mock.patch('Furious.Widget.ServerTableView.time') as clock,
            mock.patch('Furious.Widget.ServerTableView.singleShotWeakly') as schedule,
            mock.patch.object(
                table, 'reconcileProfileTestJobs', wraps=table.reconcileProfileTestJobs
            ) as reconcile,
        ):
            clock.monotonic.return_value = 10.0
            controller.isConnected.return_value = True
            profiles = list(Storage.UserServers())
            removed = QSignalSpy(table.sourceModel.rowsRemoved)
            activated = QSignalSpy(table.activeServerChanged)
            dialog = DeleteServersProgressDialog(table, range(1000), parent=table)

            with mock.patch.object(
                dialog, 'updateStatus', wraps=dialog.updateStatus
            ) as status:
                dialog.deleteNext()

                self.assertIs(
                    Storage.UserServers()[Storage.UserActivatedItemIndex()],
                    profiles[-1],
                )
                self.assertEqual(dialog.deletedCount, 128)
                controller.startDisconnection.assert_not_called()
                status.assert_not_called()

                clock.monotonic.return_value = 10.101
                dialog.deleteNext()

                self.assertIn('256/1000', dialog.statusLabel.text())

                for _index in range(7):
                    dialog.deleteNext()

                self.assertEqual(status.call_count, 2)

            self.assertEqual(Storage.UserServers(), [])
            self.assertTrue(all(profile.deleted for profile in profiles))

            self.assertEqual(removed.count(), 8)
            self.assertEqual(reconcile.call_count, 8)
            self.assertEqual(schedule.call_count, 7)

            self.assertEqual(Storage.UserActivatedItemIndex(), -1)
            self.assertEqual(activated.count(), 1)
            controller.startDisconnection.assert_called_once()

    def testDeletionKeepsCapturedTargetsAcrossSortRemovalAndCancellation(self):
        with (
            self.table(6) as (table, controller),
            mock.patch('Furious.Widget.ServerTableView.singleShotWeakly'),
        ):
            profiles = list(Storage.UserServers())
            dialog = DeleteServersProgressDialog(table, range(5), parent=table)
            dialog.BatchSize = 2

            dialog.deleteNext()

            self.assertEqual(Storage.UserServers(), profiles[2:])

            table.sourceModel.sort(0, QtCore.Qt.DescendingOrder)
            table.deleteItemByIndex([3], showProgress=False)
            newcomer = self.profile('new')
            table.appendNewItemByFactory(newcomer)

            dialog.deleteNext()
            dialog.cancel()
            dialog.deleteNext()

            self.assertEqual(dialog.deletedCount, 3)
            self.assertEqual(
                Storage.UserServers(), [profiles[5], profiles[4], newcomer]
            )
            self.assertEqual(
                [profile.index for profile in Storage.UserServers()], [0, 1, 2]
            )
            self.assertIs(
                Storage.UserServers()[Storage.UserActivatedItemIndex()], profiles[5]
            )
            controller.startDisconnection.assert_not_called()

    def testSparseDeletionPreservesPersistentIndexesAndIgnoresInvalidRows(self):
        with self.table(10) as (table, controller):
            profiles = list(Storage.UserServers())
            survivor = QtCore.QPersistentModelIndex(table.sourceModel.index(5, 0))
            removed = QSignalSpy(table.sourceModel.rowsRemoved)

            count = table.deleteItemByIndex(
                [-1, 2, 3, 3, 6, 7, 8, 100], showProgress=False
            )

            self.assertEqual(count, 5)
            self.assertEqual(
                Storage.UserServers(), [profiles[index] for index in (0, 1, 4, 5, 9)]
            )
            self.assertEqual(
                [(removed.at(i)[1], removed.at(i)[2]) for i in range(2)],
                [(6, 8), (2, 3)],
            )
            self.assertTrue(survivor.isValid())
            self.assertEqual(survivor.row(), 3)
            self.assertEqual(Storage.UserActivatedItemIndex(), 4)

    def testRealCancelInputStopsImportBetweenBatchesAndDestroysDialog(self):
        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch(
                'Furious.Actions.Import.profileFromAny',
                side_effect=lambda _uri: self.profile('input'),
            ),
            mock.patch.object(ServerProfile, 'isValid', return_value=True),
            mock.patch('Furious.Actions.Import.MBoxImportMultiSuccess') as success,
        ):
            dialog = ImportURIsProgressDialog(
                tuple('input' for _ in range(2000)), parent=table
            )
            destroyed = QSignalSpy(dialog.destroyed)

            dialog.open()
            QtCore.QTimer.singleShot(
                0, lambda: QTest.mouseClick(dialog.cancelButton, QtCore.Qt.LeftButton)
            )

            self.assertTrue(waitFor(lambda: destroyed.count() == 1))
            self.assertGreater(len(Storage.UserServers()), 0)
            self.assertLessEqual(len(Storage.UserServers()), dialog.BatchSize)
            success.assert_not_called()

    def testRealParserImportsValidProfilesAmongInvalidInputs(self):
        registry = PluginRegistry()
        registry.register(XrayPlugin())

        with (
            mock.patch(
                'Furious.Plugins.Profile.getPluginRegistry', return_value=registry
            ),
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch('Furious.Actions.Import.MBoxImportMultiSuccess') as success,
        ):
            dialog = ImportURIsProgressDialog(
                (
                    'socks://example.test:1080#first',
                    'invalid',
                    'socks://example.test:1081#second',
                ),
                parent=table,
            )
            done = QSignalSpy(dialog.finished)

            dialog.open()

            self.assertTrue(waitFor(lambda: done.count() == 1))
            self.assertEqual(
                [profile.itemRemark for profile in Storage.UserServers()],
                ['first', 'second'],
            )
            self.assertTrue(all(profile.isValid() for profile in Storage.UserServers()))
            success.return_value.open.assert_called_once()

    def testInsertionPreservesInitialActiveNotificationAndRefreshesTestTargets(self):
        with self.table() as (table, controller):
            AppSettings.set('ActivatedItemIndex', '0')
            first, second = self.profile('first'), self.profile('second')
            target = ProfileTestTarget.capture(first)
            activated = QSignalSpy(table.activeServerChanged)

            table.appendNewItemsByFactories((first, second))

            self.assertEqual(activated.count(), 1)
            self.assertIs(table.profileTestManager.resolveTarget(target), first)

            table.deleteItemByIndex((0,), showProgress=False)

            self.assertIsNone(table.profileTestManager.resolveTarget(target))
            self.assertFalse(
                table.profileTestManager.applyResult(
                    target, ProfileTestResult(ProfileTestField.Latency, 'stale')
                )
            )
            self.assertEqual(first.metadata.latency, '')

    def testDeleteConfirmationKeepsOriginalTargetAfterSorting(self):
        with self.table(4) as (table, controller):
            profiles = list(Storage.UserServers())
            table.setCurrentIndex(table.proxyIndexFromSourceRow(0))
            confirmation = MBoxQuestionDelete(parent=table)

            with mock.patch(
                'Furious.Widget.ServerTableView.MBoxQuestionDelete',
                return_value=confirmation,
            ):
                table.deleteSelectedItem()
                table.sourceModel.sort(0, QtCore.Qt.DescendingOrder)
                confirmation.done(int(confirmation.StandardButton.Yes))

                self.assertTrue(profiles[0].deleted)
                self.assertEqual(
                    Storage.UserServers(), [profiles[3], profiles[2], profiles[1]]
                )
                self.assertIs(
                    Storage.UserServers()[Storage.UserActivatedItemIndex()], profiles[3]
                )

    def testBatchPreparationFailureDoesNotPublishPartialRows(self):
        with self.table(1) as (table, controller):
            original = list(Storage.UserServers())
            inserted = QSignalSpy(table.sourceModel.rowsInserted)

            with self.assertRaises(TypeError):
                table.appendNewItemsByFactories((self.profile('valid'), object()))

            self.assertEqual(Storage.UserServers(), original)
            self.assertEqual(inserted.count(), 0)

    def testSmallImportsCompleteDirectlyWithOneInsertion(self):
        for count in (1, 64):
            with (
                self.subTest(count=count),
                self.table(2) as (table, controller),
                mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
                mock.patch.object(ServerProfile, 'isValid', return_value=True),
                mock.patch('Furious.Actions.Import.MBoxImportSuccess') as singleSuccess,
                mock.patch(
                    'Furious.Actions.Import.MBoxImportMultiSuccess'
                ) as multiSuccess,
                mock.patch.object(ImportURIsProgressDialog, 'open') as progress,
                mock.patch.object(
                    table,
                    'reconcileProfileTestJobs',
                    wraps=table.reconcileProfileTestJobs,
                ) as reconcile,
            ):
                imported = [self.profile(f'new-{index}') for index in range(count)]
                inserted = QSignalSpy(table.sourceModel.rowsInserted)

                with mock.patch(
                    'Furious.Actions.Import.profileFromAny', side_effect=imported
                ):
                    importURIs(*('input' for _ in range(count)))

                self.assertEqual(Storage.UserServers()[2:], imported)
                self.assertEqual(inserted.count(), 1)
                self.assertEqual((inserted.at(0)[1], inserted.at(0)[2]), (2, count + 1))
                reconcile.assert_called_once_with()
                progress.assert_not_called()

                if count == 1:
                    singleSuccess.return_value.open.assert_called_once()
                else:
                    multiSuccess.return_value.open.assert_called_once()
                    self.assertEqual(multiSuccess.return_value.rowIndex, 2)

    def testSmallImportRetainsInvalidInputAndFailureBehavior(self):
        invalid = mock.Mock()
        invalid.isValid.return_value = False

        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch('Furious.Actions.Import.MBoxImportSuccess') as success,
            mock.patch.object(ImportURIsProgressDialog, 'open') as progress,
        ):
            failure = mock.Mock()

            with mock.patch(
                'Furious.Actions.Import.profileFromAny', return_value=invalid
            ):
                importURIs('invalid', 'invalid', failureCallback=failure)

            failure.assert_called_once_with()
            self.assertFalse(Storage.UserServers())

            valid = self.profile('valid')

            with (
                mock.patch(
                    'Furious.Actions.Import.profileFromAny',
                    side_effect=(invalid, valid),
                ),
                mock.patch.object(ServerProfile, 'isValid', return_value=True),
            ):
                importURIs('invalid', 'valid', failureCallback=failure)

            self.assertEqual(Storage.UserServers(), [valid])
            failure.assert_called_once_with()
            success.return_value.open.assert_called_once()
            progress.assert_not_called()

    def testImportsAboveCutoffUseTheExistingProgressBatches(self):
        with (
            self.table() as (table, controller),
            mock.patch('Furious.Actions.Import.AppMainWindow', return_value=table),
            mock.patch('Furious.Actions.Import.profileFromAny') as parser,
            mock.patch.object(
                ImportURIsProgressDialog, 'open', autospec=True
            ) as progress,
        ):
            uris = tuple('input' for _ in range(65))

            importURIs(*uris)

            progress.assert_called_once()

            dialog = progress.call_args.args[0]
            self.assertEqual(dialog.uris, uris)
            self.assertEqual(dialog.BatchSize, 128)
            self.assertEqual(dialog.currentIndex, 0)
            parser.assert_not_called()
            self.assertFalse(Storage.UserServers())

    def testDeletionCutoffCountsOnlyDistinctValidTargets(self):
        for count in (1, 64, 65):
            with (
                self.subTest(count=count),
                self.table(70) as (table, controller),
                mock.patch.object(
                    DeleteServersProgressDialog, 'open', autospec=True
                ) as progress,
            ):
                profiles = list(Storage.UserServers())
                indexes = [*range(count), *range(count), -1, 1000]

                deleted = table.deleteItemByIndex(indexes)

                if count <= 64:
                    self.assertEqual(deleted, count)
                    self.assertEqual(Storage.UserServers(), profiles[count:])
                    progress.assert_not_called()
                else:
                    self.assertEqual(deleted, 0)
                    self.assertEqual(Storage.UserServers(), profiles)
                    progress.assert_called_once()

                    dialog = progress.call_args.args[0]
                    self.assertEqual(dialog.total, 65)
                    self.assertEqual(dialog.BatchSize, 128)


if __name__ == '__main__':
    unittest.main()
