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

"""Provide widgets for user servers Qt table view."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import *
from Furious.Repository import *
from Furious.Plugins import (
    blankProfile,
    exportConfiguration,
    getPluginRegistry,
    profileFromAny,
)
from Furious.Qt import *
from Furious.Qt.Signals import connectWeakly, singleShotWeakly
from Furious.Qt import gettext as _
from Furious.Service import (
    ProfileTestField,
    ProfileTestManager,
    ProfileTestResult,
    SubscriptionManager,
    SubscriptionUpdateBatch,
)
from Furious.Widget.WaitingSpinner import WaitingSpinner

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Callable, Union

import re
import logging
import functools

__all__ = ['ServerTableView']

logger = logging.getLogger(__name__)

registerAppSettings('ActivatedItemIndex')
# Migrate legacy settings
registerAppSettings('ServerWidgetSectionSizeTable')
registerAppSettings('UserServersHeaderViewState')


class MBoxUpdateSubsInfo(AppQMessageBox):
    """Represent m box update subs info."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxUpdateSubsInfo."""
        self.successArgs = kwargs.pop('successArgs', list())
        self.failureArgs = kwargs.pop('failureArgs', list())

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))

    def customText(self):
        """Return the user-facing message text for the m box update subs info."""
        if self.successArgs:
            text = _('Update subscription completed') + '\n\n'
        else:
            text = _('Update subscription failed')

        for param in self.successArgs:
            remark, webURL = param['remark'], param['webURL']

            text += (
                f'\U00002705 {remark} - {webURL} '
                + _('Configuration has been updated')
                + '\n'
            )

        if self.successArgs and self.failureArgs:
            text += '\n'
        elif self.failureArgs:
            text += '\n\n'

        for param in self.failureArgs:
            error, remark, webURL = (
                param['error'],
                param['remark'],
                param['webURL'],
            )

            # error is the specific failure reason. Not used
            # for mbox elegant appearance

            text += (
                f'\U0000274c {remark} - {webURL} '
                + _('Configuration update failed')
                + '\n'
            )

        return text

    def setColumnMinWidth(self):
        """Keep long subscription summaries readable in the Fluent dialog."""
        if PLATFORM == 'Windows':
            self.setContentMinimumWidth(
                max((len(row) + 10) for row in self.text().split('\n'))
                * self.fontMetrics().averageCharWidth(),
            )

    def retranslate(self):
        """Refresh translated text for the m box update subs info."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())
        self.setColumnMinWidth()

        # Ignore informative text, buttons

        self.moveToCenter()


class DeleteServersProgressDialog(AppQTransientDialog):
    """Present progress and cancellation controls for delete servers."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(420, 150)

    def __init__(self, table, indexes, showTrayMessage=True, parent=None):
        """Initialize the DeleteServersProgressDialog."""
        super().__init__(parent)

        self.table = table
        self.indexes = list(indexes)
        self.showTrayMessage = showTrayMessage
        self.total = len(self.indexes)
        self.nextIndex = 0
        self.deletedCount = 0
        self.deletedActivated = False
        self.canceled = False
        self.finishedDeletion = False
        self.currentRemark = ''

        self.setWindowTitle(_('Delete'))
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.spinner = WaitingSpinner(
            self,
            center_on_parent=False,
            lines=12,
            line_length=7,
            line_width=3,
            radius=7,
            color=QColor(96, 160, 255),
        )
        self.statusLabel = AppQLabel()
        self.detailLabel = AppQLabel()
        self.detailLabel.setWordWrap(True)
        self.cancelButton = AppQPushButton(_('Cancel'))

        connectWeakly(
            self.cancelButton.clicked,
            self,
            'cancel',
            sender=self.cancelButton,
        )

        statusLayout = QHBoxLayout()
        statusLayout.addWidget(self.spinner)
        statusLayout.addWidget(self.statusLabel, 1)

        layout = QVBoxLayout()
        layout.addLayout(statusLayout)
        layout.addWidget(self.detailLabel)
        layout.addWidget(self.cancelButton)

        self.setLayout(layout)

        self.updateStatus()

    def open(self):
        """Open the delete servers progress dialog asynchronously."""
        self.spinner.start()

        singleShotWeakly(0, self, 'deleteNext')

        return super().open()

    def reject(self):
        """Reject the current delete servers progress dialog values."""
        self.cancel()

    def cancel(self, *_args):
        """Cancel the delete servers progress dialog operation."""
        self.canceled = True
        self.cancelButton.setEnabled(False)
        self.updateStatus()

    def updateStatus(self):
        """Update status."""
        if self.canceled:
            self.statusLabel.setText(
                _('Canceling delete') + f'... {self.deletedCount}/{self.total}'
            )
        else:
            self.statusLabel.setText(
                _('Deleting') + f'... {self.deletedCount}/{self.total}'
            )

        if self.currentRemark:
            self.detailLabel.setText(_('Current') + f': {self.currentRemark}')
        else:
            self.detailLabel.setText('')

    @staticmethod
    def limitedRemark(remark: str) -> str:
        """Return the limited remark value used by the delete servers progress dialog."""
        remark = str(remark).strip()

        if len(remark) <= 120:
            return remark

        return remark[:117] + '...'

    def deleteNext(self):
        """Delete next."""
        if self.canceled or self.nextIndex >= self.total:
            self.finishDeletion()

            return

        originalIndex = self.indexes[self.nextIndex]
        self.nextIndex += 1
        deleteIndex = originalIndex - self.deletedCount

        if deleteIndex < 0 or deleteIndex >= len(Storage.UserServers()):
            self.updateStatus()

            singleShotWeakly(0, self, 'deleteNext')

            return

        factory = Storage.UserServers()[deleteIndex]

        self.currentRemark = self.limitedRemark(factory.itemRemark)

        if originalIndex == Storage.UserActivatedItemIndex():
            self.deletedActivated = True

        self.table.sourceModel.beginRemoveRows(
            QtCore.QModelIndex(),
            deleteIndex,
            deleteIndex,
        )

        factory.deleted = True

        Storage.UserServers().pop(deleteIndex)

        self.table.sourceModel.endRemoveRows()
        self.table.reconcileProfileTestJobs()

        if not self.deletedActivated and deleteIndex < Storage.UserActivatedItemIndex():
            AppSettings.set(
                'ActivatedItemIndex', str(Storage.UserActivatedItemIndex() - 1)
            )

        self.deletedCount += 1
        self.updateStatus()

        singleShotWeakly(0, self, 'deleteNext')

    def finishDeletion(self):
        """Handle finish deletion for the delete servers progress dialog."""
        if self.finishedDeletion:
            return

        self.finishedDeletion = True
        self.spinner.stop()

        self.table.sourceModel.refreshIndexes()
        self.table.sourceModel.emitAllChanged()

        if self.deletedActivated:
            # Set invalid first
            AppSettings.set('ActivatedItemIndex', str(-1))

            self.table.activeServerChanged.emit()

            controller = AppConnectionController()

            if controller.isConnected():
                controller.startDisconnection(
                    _('Disconnected') if self.showTrayMessage else ''
                )

        self.accept()

    def retranslate(self):
        """Refresh translated text for the delete servers progress dialog."""
        self.setWindowTitle(_(self.windowTitle()))
        self.cancelButton.setText(_(self.cancelButton.text()))
        self.updateStatus()


class ServerTableHorizontalHeader(AppQHeaderView):
    """Provide the user servers Qt table view horizontal table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the ServerTableHorizontalHeader."""
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class ServerTableVerticalHeader(AppQHeaderView):
    """Provide the user servers Qt table view vertical table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the ServerTableVerticalHeader."""
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class ServerTableColumn:
    """Describe and render user servers Qt table view table columns."""

    def __init__(self, name: str, func: Callable[[CoreConfiguration], str] = None):
        """Initialize the ServerTableColumn."""
        self.name = name
        self.func = func

    def __call__(self, item: ServerProfile) -> str:
        """Invoke the user servers Qt table view headers as a callable."""
        if callable(self.func):
            return self.func(item)
        else:
            return getattr(item, f'item{self}')

    def __eq__(self, other):
        """Compare the user servers Qt table view headers with another value."""
        return str(self) == str(other)

    def __str__(self):
        """Return the display text for the user servers Qt table view headers."""
        return self.name


def _subscriptionRemark(item: ServerProfile) -> str:
    """Resolve a persisted subscription ID to its user-visible remark."""
    if not item.itemSubscription:
        return ''

    subscription = Storage.UserSubs().get(item.itemSubscription, {})

    if not subscription:
        return _('Unknown Subscription')

    remark = subscription.get('remark', '') or item.itemSubscription

    return (
        remark if subscription.get('enabled', True) else f'{remark} ({_("Disabled")})'
    )


class UserServersTableModel(QtCore.QAbstractTableModel):
    """Expose user servers table data through a Qt item model."""

    SortRole = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, headers: list[ServerTableColumn], parent=None):
        """Initialize the UserServersTableModel."""
        super().__init__(parent)

        self.headers = headers

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of rows exposed by the model."""
        if parent.isValid():
            return 0

        return len(Storage.UserServers())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of columns exposed by the model."""
        if parent.isValid():
            return 0

        return len(self.headers)

    def flags(self, index):
        """Return the Qt item flags for a model index."""
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Return the data managed by the user servers table model."""
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()

        if row < 0 or row >= len(Storage.UserServers()):
            return None

        if column < 0 or column >= len(self.headers):
            return None

        server = Storage.UserServers()[row]
        header = self.headers[column]
        text = header(server)

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.ToolTipRole
        ):
            return text

        if role == QtCore.Qt.ItemDataRole.FontRole:
            font = QFont(AppFontName())

            if row == Storage.UserActivatedItemIndex():
                font.setBold(True)

            return font

        if role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if row == Storage.UserActivatedItemIndex():
                return QColor(AppHue.currentColor())

            return None

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if str(header) == 'Latency' or str(header) == 'Speed':
                return (
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

            return None

        if role == self.SortRole:
            if str(header) == 'Latency':
                return self.testResultSortValue(text, 'ms')

            if str(header) == 'Speed':
                return self.testResultSortValue(text, ' MiB/s')

            return text

        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        """Return display data for a table header section."""
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            if 0 <= section < len(self.headers):
                return _(str(self.headers[section]))

            return None

        return section + 1

    @staticmethod
    def testResultSortValue(text: str, suffix: str):
        """Return the test result sort value value used by the user servers table model."""
        if text.endswith(suffix):
            text = text[: -len(suffix)]

        try:
            return float(text)
        except Exception:
            # Any non-exit exceptions

            return abs(hash(text)) + 2**20

    def emitRowChanged(
        self,
        row: int,
        column: Union[int, None] = None,
        roles: list[QtCore.Qt.ItemDataRole] | None = None,
    ):
        """Handle emit row changed for the user servers table model."""
        if row < 0 or row >= self.rowCount():
            return

        if column is None:
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
        else:
            left = self.index(row, column)
            right = left

        self.dataChanged.emit(left, right, roles or [])

    def emitAllChanged(self):
        """Handle emit all changed for the user servers table model."""
        if self.rowCount() == 0 or self.columnCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            [],
        )

    @staticmethod
    def refreshIndexes():
        """Refresh indexes."""
        for index, item in enumerate(Storage.UserServers()):
            item.index = index

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        """Sort the user servers table model."""
        if column < 0 or column >= self.columnCount():
            return

        activatedIndex = Storage.UserActivatedItemIndex()

        if 0 <= activatedIndex < len(Storage.UserServers()):
            activatedServerId = id(Storage.UserServers()[activatedIndex])
        else:
            activatedServerId = None

        header = self.headers[column]
        persistentIndexes = tuple(
            (
                QtCore.QModelIndex(index),
                Storage.UserServers()[index.row()],
                index.column(),
            )
            for index in self.persistentIndexList()
            if index.isValid() and 0 <= index.row() < len(Storage.UserServers())
        )

        def keyFn(factory: ServerProfile):
            """Return the key fn value used by the user servers table model."""
            data = header(factory)

            if str(header) == 'Latency':
                return self.testResultSortValue(data, 'ms')

            if str(header) == 'Speed':
                return self.testResultSortValue(data, ' MiB/s')

            return data

        self.layoutAboutToBeChanged.emit()

        Storage.UserServers().sort(
            key=keyFn,
            reverse=order == QtCore.Qt.SortOrder.DescendingOrder,
        )
        self.refreshIndexes()

        rowsByIdentity = {
            id(profile): row for row, profile in enumerate(Storage.UserServers())
        }

        self.changePersistentIndexList(
            [index for index, _profile, _column in persistentIndexes],
            [
                self.index(rowsByIdentity[id(profile)], persistentColumn)
                for _index, profile, persistentColumn in persistentIndexes
            ],
        )

        if activatedServerId is not None:
            for index, server in enumerate(Storage.UserServers()):
                if id(server) == activatedServerId:
                    AppSettings.set('ActivatedItemIndex', str(index))

                    break

        self.layoutChanged.emit()


class UserServersSortFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filter and sort user servers sort filter data."""

    sortAboutToStart = QtCore.Signal()
    sortCompleted = QtCore.Signal()

    def __init__(self, parent=None):
        """Initialize the UserServersSortFilterProxyModel."""
        super().__init__(parent)

        self.searchPattern = ''
        self.searchCaseSensitive = False
        self.searchUseRegex = True
        self.searchRegex = None
        self.subscriptionFilter = None
        self.sortSuspended = False

        self.setSortRole(UserServersTableModel.SortRole)
        self.setDynamicSortFilter(True)

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        """Sort the user servers sort filter proxy model."""
        if self.sortSuspended:
            super().sort(-1, order)

            return

        if column < 0:
            super().sort(column, order)

            return

        model = self.sourceModel()

        if model is not None:
            self.sortAboutToStart.emit()

            try:
                model.sort(column, order)

                self.invalidate()
            finally:
                self.sortCompleted.emit()

    def setSearchPattern(
        self,
        pattern: str,
        *,
        caseSensitive: bool = False,
        regex: bool = True,
    ):
        """Set search pattern."""
        self.searchPattern = str(pattern or '')
        self.searchCaseSensitive = caseSensitive
        self.searchUseRegex = regex
        self.searchRegex = None

        if self.searchPattern:
            flags = 0 if caseSensitive else re.IGNORECASE
            regexPattern = (
                self.searchPattern if regex else re.escape(self.searchPattern)
            )

            try:
                self.searchRegex = re.compile(regexPattern, flags)
            except re.error as ex:
                logger.error(
                    f'invalid user servers search regex: {ex}. '
                    f'Fall back to literal matching'
                )

                self.searchRegex = re.compile(re.escape(self.searchPattern), flags)

        self.invalidateFilter()

    def setSubscriptionFilter(self, unique: str | None):
        """Limit rows to manual profiles or one subscription group."""
        self.subscriptionFilter = unique
        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow: int, sourceParent) -> bool:
        """Filter accepts row."""
        model = self.sourceModel()

        if model is None:
            return True

        if 0 <= sourceRow < len(Storage.UserServers()):
            profile = Storage.UserServers()[sourceRow]

            if self.subscriptionFilter == '':
                if profile.itemSubscriptionManaged:
                    return False
            elif (
                self.subscriptionFilter is not None
                and profile.itemSubscription != self.subscriptionFilter
            ):
                return False

        if not self.searchPattern or self.searchRegex is None:
            return True

        searchableText = '\n'.join(
            str(
                model.data(
                    model.index(sourceRow, column, sourceParent),
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                or ''
            )
            for column in range(model.columnCount(sourceParent))
        )

        return self.searchRegex.search(searchableText) is not None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        """Return display data for a table header section."""
        if (
            orientation == QtCore.Qt.Orientation.Vertical
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            return section + 1

        return super().headerData(section, orientation, role)


# ALL Headers VALUE
_TRANSLATABLE_HEADERS = [
    _('Remark'),
    _('Protocol'),
    _('Address'),
    _('Port'),
    _('Transport'),
    _('TLS'),
    _('Subscription'),
    _('Latency'),
    _('Speed'),
]


class ServerTableView(
    Mixins.QTranslatable,
    Mixins.CleanupOnExit,
    Mixins.ConnectionAware,
    AppQTableView,
):
    """Represent user servers Qt table view."""

    activeServerChanged = QtCore.Signal()

    RowHeight = 42

    Headers = [
        ServerTableColumn('Remark'),
        ServerTableColumn('Protocol'),
        ServerTableColumn('Address'),
        ServerTableColumn('Port'),
        ServerTableColumn('Transport'),
        ServerTableColumn('TLS'),
        ServerTableColumn('Subscription', _subscriptionRemark),
        ServerTableColumn('Latency'),
        ServerTableColumn('Speed'),
    ]

    def __init__(self, *args, **kwargs):
        """Initialize the server table view."""
        configurationEditorFactory, self.qrCodeWindowFactory, importActionsFactory = (
            kwargs.pop('configurationEditorFactory'),
            kwargs.pop('qrCodeWindowFactory'),
            kwargs.pop('importActionsFactory'),
        )

        super().__init__(*args, **kwargs)

        self.sourceModel = UserServersTableModel(self.Headers, parent=self)

        self.proxyModel = UserServersSortFilterProxyModel(parent=self)
        self.proxyModel.setSourceModel(self.sourceModel)
        self.setModel(self.proxyModel)
        self._sortSelectionSnapshot = None
        self.proxyModel.sortAboutToStart.connect(self._captureSortSelection)
        self.proxyModel.sortCompleted.connect(self._restoreSortSelection)

        self.subsManager = SubscriptionManager(parent=self)
        self.subsManager.subscriptionsChanged.connect(self._handleSubscriptionsChanged)
        self.subsManager.subscriptionCommitted.connect(
            self._handleSubscriptionCommitted
        )
        self.subsManager.updateCompleted.connect(
            self._handleSubscriptionUpdateCompleted
        )

        self.profileTestManager = ProfileTestManager(parent=self)

        connectWeakly(
            self.profileTestManager.resultApplied,
            self,
            '_handleProfileTestResultApplied',
            sender=self.profileTestManager,
        )

        self.configurationEditor = configurationEditorFactory()

        # Install custom header
        self.setHorizontalHeader(
            ServerTableHorizontalHeader(
                parent=self,
                legacySectionSizeSettingsName='ServerWidgetSectionSizeTable',
                sectionSizeSettingsName='UserServersHeaderViewState',
            )
        )
        self.setVerticalHeader(ServerTableVerticalHeader(self))
        self.setDefaultRowHeight(self.RowHeight)

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.proxyModel.sortSuspended = True
        self.setSortingEnabled(True)
        self.proxyModel.sortSuspended = False
        self.proxyModel.sort(-1)

        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        self.customizeJSONConfigActionRef = AppQAction(
            _('Customize JSON Configuration...'),
            icon=bootstrapIcon('braces-asterisk.svg'),
            callback=lambda: self.editSelectedItemConfiguration(),
            shortcut=QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_E,
            ),
        )

        self.advancedActionRef = AppQAction(
            _('Advanced...'),
            menu=AppQMenu(
                self.customizeJSONConfigActionRef,
            ),
            useActionGroup=False,
            checkable=False,
        )

        self.activateSelectedServerActionRef = AppQAction(
            _('Activate Selected Server'),
            callback=lambda: self.activateSelectedServer(),
            shortcut=QtCore.QKeyCombination(
                QtCore.Qt.Key.Key_Enter,
            ),
        )

        self.moveMenu = AppQMenu(
            AppQAction(
                _('Move to Top'),
                callback=lambda: self.moveSelectedItems('top'),
            ),
            AppQAction(
                _('Move Up'),
                callback=lambda: self.moveSelectedItems('up'),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Up,
                ),
            ),
            AppQAction(
                _('Move Down'),
                callback=lambda: self.moveSelectedItems('down'),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Down,
                ),
            ),
            AppQAction(
                _('Move to Bottom'),
                callback=lambda: self.moveSelectedItems('bottom'),
            ),
            parent=self,
        )

        self.moveActionRef = AppQAction(
            _('Move...'),
            menu=self.moveMenu,
            useActionGroup=False,
            checkable=False,
        )

        self.moveToSubscriptionMenu = AppQMenu(parent=self)
        self.moveToSubscriptionActionRef = AppQAction(
            _('Move To Subscription...'),
            menu=self.moveToSubscriptionMenu,
            useActionGroup=False,
            checkable=False,
        )
        self._subscriptionActions = []

        contextMenuActions = [
            self.moveActionRef,
            AppQAction(
                _('Duplicate'),
                callback=lambda: self.duplicateSelectedItem(),
            ),
            AppQAction(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.Key.Key_Delete,
                ),
            ),
            self.moveToSubscriptionActionRef,
            AppQSeparator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            AppQSeparator(),
            self.activateSelectedServerActionRef,
            AppQAction(
                _('Scroll To Activated Server'),
                callback=lambda: self.scrollToActivatedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_G,
                ),
            ),
            AppQSeparator(),
            AppQAction(
                _('Test Ping Latency'),
                callback=lambda: self.testSelectedItemPingLatency(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_P,
                ),
            ),
            AppQAction(
                _('Test Tcping Latency'),
                callback=lambda: self.testSelectedItemTcpingLatency(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_O,
                ),
            ),
            # The context menu intentionally exposes only the multithreaded test.
            # Keep the single-threaded methods as a programmatic API for callers
            # that need that scheduler explicitly.
            AppQAction(
                _('Test Download Speed'),
                callback=lambda: self.testSelectedItemDownloadSpeedMulti(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_M,
                ),
            ),
            AppQAction(
                _('Clear Test Results'),
                callback=lambda: self.clearSelectedItemTestResult(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_R,
                ),
            ),
            AppQSeparator(),
            self.advancedActionRef,
            AppQSeparator(),
            *importActionsFactory(),
            AppQSeparator(),
            AppQAction(
                _('Export Share Link To Clipboard'),
                callback=lambda: self.exportSelectedItemURI(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Export As QR Code'),
                icon=bootstrapIcon('qr-code.svg'),
                callback=lambda: self.exportSelectedItemQR(),
            ),
            AppQAction(
                _('Export JSON Configuration To Clipboard'),
                callback=lambda: self.exportSelectedItemJSON(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_J,
                ),
            ),
        ]

        self.contextMenu = AppQMenu(*contextMenuActions, parent=self)
        self.contextMenu.aboutToShow.connect(self._rebuildSubscriptionMenu)

        self._registerMenuShortcuts(self.contextMenu)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

        # Distinguish double-click and activated
        self.doubleClickedFlag = False

        # Signals
        self.selectionModel().selectionChanged.connect(self.handleItemSelectionChanged)
        self.activated.connect(self.handleItemActivated)
        self.doubleClicked.connect(self.handleItemDoubleClicked)

        self.flushAll()

        if self.activatedIndex().isValid():
            self.setCurrentIndex(self.activatedIndex())
            self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    @property
    def selectedIndex(self):
        """Return the selected index value."""
        indexes = list(
            self.sourceRowFromProxyIndex(index)
            for index in self.selectionModel().selectedRows()
        )

        return sorted(list(set(index for index in indexes if index >= 0)))

    def sourceIndexFromProxyIndex(self, index: QtCore.QModelIndex):
        """Return the source index from proxy index value used by the user servers Qt table view."""
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapToSource(index)

    def proxyIndexFromSourceIndex(self, index: QtCore.QModelIndex):
        """Return the proxy index from source index value used by the user servers Qt table view."""
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapFromSource(index)

    def sourceRowFromProxyIndex(self, index: QtCore.QModelIndex) -> int:
        """Return the source row from proxy index value used by the user servers Qt table view."""
        sourceIndex = self.sourceIndexFromProxyIndex(index)

        if sourceIndex.isValid():
            return sourceIndex.row()

        return -1

    def sourceRowFromProxyRow(self, row: int) -> int:
        """Return the source row from proxy row value used by the user servers Qt table view."""
        return self.sourceRowFromProxyIndex(self.proxyModel.index(row, 0))

    def proxyIndexFromSourceRow(self, row: int, column: int = 0):
        """Return the proxy index from source row value used by the user servers Qt table view."""
        if row < 0 or row >= self.sourceModel.rowCount():
            return QtCore.QModelIndex()

        return self.proxyIndexFromSourceIndex(self.sourceModel.index(row, column))

    def selectMultipleRows(self, indexes: list[int], clearCurrentSelection: bool):
        """Select multiple rows."""
        if clearCurrentSelection:
            self.selectionModel().clearSelection()

        selection = self.selectionModel().selection()

        for index in indexes:
            proxyIndex0 = self.proxyIndexFromSourceRow(index, 0)
            proxyIndex1 = self.proxyIndexFromSourceRow(index, len(self.Headers) - 1)

            if proxyIndex0.isValid() and proxyIndex1.isValid():
                selection.select(proxyIndex0, proxyIndex1)

        self.selectionModel().select(
            selection, QtCore.QItemSelectionModel.SelectionFlag.Select
        )

    def disconnectedCallback(self):
        """Update the user servers Qt table view for a disconnected state."""
        self.sourceModel.emitRowChanged(
            Storage.UserActivatedItemIndex(),
            roles=[QtCore.Qt.ItemDataRole.ForegroundRole],
        )

    def connectedCallback(self):
        """Update the user servers Qt table view for a connected state."""
        self.sourceModel.emitRowChanged(
            Storage.UserActivatedItemIndex(),
            roles=[QtCore.Qt.ItemDataRole.ForegroundRole],
        )

    def handleItemSelectionChanged(self, *args):
        """Handle item selection changed."""
        if len(self.selectedIndex) > 1:
            for action in [
                self.customizeJSONConfigActionRef,
                self.activateSelectedServerActionRef,
            ]:
                action.setDisabled(True)
        else:
            for action in [
                self.customizeJSONConfigActionRef,
                self.activateSelectedServerActionRef,
            ]:
                action.setDisabled(False)

    @QtCore.Slot(QtCore.QModelIndex)
    def handleItemActivated(self, index: QtCore.QModelIndex):
        """Handle item activated."""
        if self.doubleClickedFlag:
            # Ignore double-click
            self.doubleClickedFlag = False

            return

        oldIndex = Storage.UserActivatedItemIndex()
        newIndex = self.sourceRowFromProxyIndex(index)

        if newIndex < 0:
            return

        if oldIndex == newIndex:
            # Same item activated. Do nothing
            return

        if AppConnectionController().isConnecting():
            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
            mbox.setText(_('Connecting. Please wait...'))

            if PLATFORM != 'Darwin':
                # Show the MessageBox asynchronously
                mbox.open()
            else:
                # Show the MessageBox asynchronously
                # TODO: Verify
                mbox.open()

            return

        if oldIndex >= 0:
            self.activateItemByIndex(oldIndex, False)

        self.activateItemByIndex(newIndex, True)

        if AppConnectionController().isConnected():
            AppConnectionController().startReconnection()

    def getGuiEditorByFactory(
        self, factory, **kwargs
    ) -> Union[GuiEditorWidgetQDialog, None]:
        """Return GUI editor by factory."""
        editor = getPluginRegistry().createEditorForConfig(
            factory, parent=self, **kwargs
        )

        return editor

    @QtCore.Slot(QtCore.QModelIndex)
    def handleItemDoubleClicked(self, modelIndex: QtCore.QModelIndex):
        """Handle item double clicked."""
        self.doubleClickedFlag = True

        index = self.sourceRowFromProxyIndex(modelIndex)

        if index < 0:
            return

        factory = Storage.UserServers()[index]

        # Do not translate window title
        guiEditor = self.getGuiEditorByFactory(factory, translatable=False)

        if guiEditor is None:
            # Unrecognized.
            showMBoxUnrecognizedConfig()

            return

        guiEditor.setWindowTitle(f'{index + 1} - ' + factory.itemRemark)

        try:
            guiEditor.factoryToInput(factory)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        # Keep operation metadata on the transient editor. Weak dispatch avoids
        # process-lifetime protection of compiled table methods in Nuitka while
        # forwarding the transient sender explicitly to the operation slot.
        guiEditor._modContext = (index, factory)

        connectWeakly(
            guiEditor.accepted,
            self,
            'handleGuiEditorAccepted',
            sender=guiEditor,
            forwardSender=True,
        )
        connectWeakly(
            guiEditor.rejected,
            self,
            'handleGuiEditorRejected',
            sender=guiEditor,
            forwardSender=True,
        )

        guiEditor.open()

    @QtCore.Slot(object)
    def handleGuiEditorAccepted(self, editor):
        """Handle GUI editor accepted."""

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        index, factory = editor._modContext

        logger.debug(f'guiEditor accepted with index {index}')

        modified = editor.inputToFactory(factory)

        # Still flush to row since remark may be modified
        self.flushRow(index, factory)

        if modified and index == Storage.UserActivatedItemIndex():
            showMBoxNewChangesNextTime()

        del editor._modContext

    @QtCore.Slot(object)
    def handleGuiEditorRejected(self, editor):
        """Handle GUI editor rejected."""

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        if hasattr(editor, '_modContext'):
            del editor._modContext

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        """Handle custom context menu requested."""
        self.contextMenu.exec(self.viewport().mapToGlobal(point))

    def customSortFn(self, clickedIndex, **kwargs):
        """Handle custom sort fn for the user servers Qt table view."""
        order = (
            QtCore.Qt.SortOrder.DescendingOrder
            if kwargs.get('reverse', False)
            else QtCore.Qt.SortOrder.AscendingOrder
        )

        self.sortByColumn(clickedIndex, order)

    def activatedIndex(self):
        """Activate d index."""
        return self.proxyIndexFromSourceRow(Storage.UserActivatedItemIndex(), 0)

    def activateItemByIndex(self, index, activate):
        """Activate item by index."""
        oldIndex = Storage.UserActivatedItemIndex()
        changed = activate and oldIndex != int(index)

        if activate:
            AppSettings.set('ActivatedItemIndex', str(index))

        self.sourceModel.emitRowChanged(oldIndex)
        self.sourceModel.emitRowChanged(index)

        if changed:
            self.activeServerChanged.emit()

    def flushItem(self, row: int, column: int, item: ServerProfile):
        """Refresh item."""
        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        def searchIndex(start, stop, step=1):
            """Search index."""
            nonlocal itemIndex

            for _index in range(start, stop, step):
                if id(item) == id(Storage.UserServers()[_index]):
                    itemIndex = _index

                    item.index = itemIndex

                    return True

            return False

        if id(item) != id(Storage.UserServers()[itemIndex]):
            # itemIndex doesn't match
            if searchIndex(itemIndex - 1, -1, -1) or searchIndex(
                itemIndex + 1, len(Storage.UserServers())
            ):
                pass
            else:
                # Item isn't found in user servers. Do nothing
                return

        if row != itemIndex:
            # Adjust row value
            row = itemIndex
        else:
            pass

        self.sourceModel.emitRowChanged(row, column)

    def search(
        self,
        pattern: str,
        *,
        caseSensitive: bool = False,
        regex: bool = True,
    ):
        """Search the user servers Qt table view."""
        self.proxyModel.setSearchPattern(
            pattern,
            caseSensitive=caseSensitive,
            regex=regex,
        )

    def clearSearch(self):
        """Clear search."""
        self.search('')

    def filterBySubscription(self, unique: str | None):
        """Show all, manual, or one subscription group's profiles."""
        self.proxyModel.setSubscriptionFilter(unique)

    def addServerViaGui(self, protocol, **kwargs):
        """Add server via GUI."""
        factory = blankProfile(protocol)

        windowTitle, translatable = (
            kwargs.pop('windowTitle', APPLICATION_NAME),
            kwargs.pop('translatable', True),
        )

        if translatable is True:
            windowTitle = _(windowTitle)

        guiEditor = self.getGuiEditorByFactory(
            factory, windowTitle=windowTitle, translatable=translatable, **kwargs
        )

        if guiEditor is None:
            # Unrecognized. Do nothing
            return

        try:
            guiEditor.factoryToInput(factory)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        guiEditor._addContext = factory

        connectWeakly(
            guiEditor.accepted,
            self,
            'handleAddServerViaGuiAccepted',
            sender=guiEditor,
            forwardSender=True,
        )
        connectWeakly(
            guiEditor.rejected,
            self,
            'handleAddServerViaGuiRejected',
            sender=guiEditor,
            forwardSender=True,
        )

        guiEditor.open()

    @QtCore.Slot(object)
    def handleAddServerViaGuiAccepted(self, editor):
        """Handle add server via GUI accepted."""

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        factory = editor._addContext

        editor.inputToFactory(factory)

        self.appendNewItemByFactory(factory)

        del editor._addContext

    @QtCore.Slot(object)
    def handleAddServerViaGuiRejected(self, editor):
        """Handle add server via GUI rejected."""

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        if hasattr(editor, '_addContext'):
            del editor._addContext

    def flushRow(self, row: int, item: ServerProfile):
        """Refresh row."""
        # flushRow is the established commit notification for both structured
        # and JSON profile editors. Reconcile before presenting a replacement
        # or in-place connection mutation.
        self.reconcileProfileTestJobs()

        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        if row != itemIndex:
            row = itemIndex

        self.sourceModel.emitRowChanged(row)

        if row == Storage.UserActivatedItemIndex():
            self.activeServerChanged.emit()

    def flushAll(self):
        # Refresh index
        """Refresh all."""
        self.sourceModel.refreshIndexes()
        self.sourceModel.emitAllChanged()

    def _profileIdsForSourceRows(self, rows) -> list[str]:
        """Return stable identities for valid source rows."""
        profiles = Storage.UserServers()

        return [
            profiles[row].metadata.profileId for row in rows if 0 <= row < len(profiles)
        ]

    def _visibleProfileIds(self) -> list[str]:
        """Return stable identities in the current filtered display scope."""
        return self._profileIdsForSourceRows(
            self.sourceRowFromProxyRow(row) for row in range(self.proxyModel.rowCount())
        )

    def _selectedProfileIds(self) -> list[str]:
        """Return stable identities for the current row selection."""
        return self._profileIdsForSourceRows(self.selectedIndex)

    def _currentProfileId(self) -> str | None:
        """Return the stable identity represented by the current proxy index."""
        row = self.sourceRowFromProxyIndex(self.currentIndex())
        profileIds = self._profileIdsForSourceRows((row,))

        return profileIds[0] if profileIds else None

    @QtCore.Slot()
    def _captureSortSelection(self):
        """Remember semantic view state before the proxy rebuilds its mapping."""
        self._sortSelectionSnapshot = (
            self._selectedProfileIds(),
            self._currentProfileId(),
            self.hasFocus(),
        )

    @QtCore.Slot()
    def _restoreSortSelection(self):
        """Restore semantic view state after a source-backed header sort."""
        snapshot = self._sortSelectionSnapshot
        self._sortSelectionSnapshot = None

        if snapshot is not None:
            profileIds, currentProfileId, restoreFocus = snapshot

            self._restoreProfileSelection(
                profileIds,
                currentProfileId,
                restoreFocus=restoreFocus,
            )

    def _restoreProfileSelection(
        self,
        profileIds,
        currentProfileId=None,
        *,
        restoreFocus=True,
    ):
        """Restore visible selected rows and their current identity."""
        selected = set(profileIds)
        rows = [
            index
            for index, profile in enumerate(Storage.UserServers())
            if profile.metadata.profileId in selected
        ]

        with Mixins.QBlockSignalContext(self):
            self.selectMultipleRows(rows, True)

            if rows:
                currentRow = next(
                    (
                        row
                        for row in rows
                        if Storage.UserServers()[row].metadata.profileId
                        == currentProfileId
                    ),
                    rows[0],
                )
                current = self.proxyIndexFromSourceRow(currentRow)

                if current.isValid():
                    self.selectionModel().setCurrentIndex(
                        current,
                        QtCore.QItemSelectionModel.SelectionFlag.NoUpdate,
                    )

        if restoreFocus:
            self.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)

    def _applyRepositoryLayoutMutation(self, callback) -> bool:
        """Apply one repository reorder and preserve active and selected identities."""
        selectedProfileIds = self._selectedProfileIds()
        currentProfileId = self._currentProfileId()
        activatedIndex = Storage.UserActivatedItemIndex()
        profiles = Storage.UserServers()
        activatedProfileId = (
            profiles[activatedIndex].metadata.profileId
            if 0 <= activatedIndex < len(profiles)
            else None
        )

        self.sourceModel.layoutAboutToBeChanged.emit()

        try:
            changed = bool(callback())

            if changed and activatedProfileId is not None:
                for index, profile in enumerate(Storage.UserServers()):
                    if profile.metadata.profileId == activatedProfileId:
                        if index != activatedIndex:
                            AppSettings.set('ActivatedItemIndex', str(index))

                        break
        finally:
            self.sourceModel.layoutChanged.emit()

        if not changed:
            return False

        if (
            activatedProfileId is not None
            and Storage.UserActivatedItemIndex() != activatedIndex
        ):
            self.activeServerChanged.emit()

        self.proxyModel.invalidate()
        self._restoreProfileSelection(selectedProfileIds, currentProfileId)

        return True

    def newEmptyItem(self):
        """Handle new empty item for the user servers Qt table view."""
        self.appendNewItem(remark=_('Untitled'), acceptInvalid=True)

    def moveSelectedItems(self, position: str):
        """Move selected profiles inside the current filtered display scope."""
        selectedProfileIds, visibleProfileIds = (
            self._selectedProfileIds(),
            self._visibleProfileIds(),
        )

        if not selectedProfileIds:
            return

        self._applyRepositoryLayoutMutation(
            lambda: Storage.moveUserServers(
                selectedProfileIds,
                visibleProfileIds,
                position,
            )
        )

    def _registerMenuShortcuts(self, menu):
        """Activate every nested table action only while this view has focus."""
        for action in menu.actions():
            if action.isSeparator():
                continue

            if not action.shortcut().isEmpty():
                action.setShortcutContext(QtCore.Qt.ShortcutContext.WidgetShortcut)

            self.addAction(action)

            submenu = action.menu() if hasattr(action, 'menu') else None

            if submenu is not None:
                self._registerMenuShortcuts(submenu)

    def _clearSubscriptionActions(self):
        """Release callbacks and wrappers owned by the dynamic group submenu."""
        for action in self._subscriptionActions:
            self.moveToSubscriptionMenu.removeAction(action)

            action.callback = None
            action.deleteLater()

        self._subscriptionActions.clear()
        self.moveToSubscriptionMenu._actions.clear()

    @QtCore.Slot()
    def _rebuildSubscriptionMenu(self):
        """Rebuild subscription destinations from the live group repository."""
        self._clearSubscriptionActions()

        selectedProfileIds = self._selectedProfileIds()
        selected = set(selectedProfileIds)
        selectedSources = {
            profile.metadata.subscriptionSource
            for profile in Storage.UserServers()
            if profile.metadata.profileId in selected
        }
        destinations = [(_('No subscription'), '')]
        destinations.extend(
            (
                group.remark or group.webURL or group.id,
                group.id,
            )
            for group in Storage.SubscriptionGroups()
        )

        for label, unique in destinations:
            action = AppQAction(
                label,
                callback=functools.partial(
                    self.moveSelectedItemsToSubscription,
                    unique,
                ),
                checkable=True,
                checked=bool(selectedProfileIds) and selectedSources == {unique},
                translatable=not unique,
                parent=self.moveToSubscriptionMenu,
            )

            self._subscriptionActions.append(action)
            self.moveToSubscriptionMenu._actions.append(action)
            self.moveToSubscriptionMenu.addAction(action)

        self.moveToSubscriptionActionRef.setEnabled(
            bool(selectedProfileIds)
            and any(selectedSources != {unique} for _label, unique in destinations)
        )

    def moveSelectedItemsToSubscription(self, unique: str):
        """Move selected profiles to one group without transferring sync ownership."""
        selectedProfileIds, currentProfileId = (
            self._selectedProfileIds(),
            self._currentProfileId(),
        )

        if not selectedProfileIds:
            return

        if Storage.moveUserServersToSubscription(selectedProfileIds, unique):
            self.sourceModel.emitAllChanged()
            self.proxyModel.invalidateFilter()
            self._restoreProfileSelection(selectedProfileIds, currentProfileId)

    def duplicateSelectedItem(self):
        """Handle duplicate selected item for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            if 0 <= index < len(Storage.UserServers()):
                deepcopy = Storage.UserServers()[index].independentCopy()

                # A duplicate is a new manual profile, not another profile
                # managed by the source subscription.
                self.appendNewItem(
                    remark=deepcopy.itemRemark,
                    config=deepcopy,
                )

    def deleteItemByIndex(
        self, indexes, showTrayMessage=True, showProgress=True
    ) -> int:
        """Delete item by index."""
        indexes = sorted(set(indexes))

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return 0

        if showProgress and len(indexes) > 1:
            dialog = DeleteServersProgressDialog(
                self,
                indexes,
                showTrayMessage=showTrayMessage,
                parent=self.window(),
            )
            dialog.open()

            return 0

        if Storage.UserActivatedItemIndex() in indexes:
            deleteActivated = True
        else:
            deleteActivated = False

        # Note: param indexes must be sorted
        for i in range(len(indexes)):
            deleteIndex = indexes[i] - i

            self.sourceModel.beginRemoveRows(
                QtCore.QModelIndex(),
                deleteIndex,
                deleteIndex,
            )

            Storage.UserServers()[deleteIndex].deleted = True
            Storage.UserServers().pop(deleteIndex)

            self.sourceModel.endRemoveRows()

            if not deleteActivated and deleteIndex < Storage.UserActivatedItemIndex():
                AppSettings.set(
                    'ActivatedItemIndex', str(Storage.UserActivatedItemIndex() - 1)
                )

        self.reconcileProfileTestJobs()

        # Refresh index
        self.sourceModel.refreshIndexes()
        self.sourceModel.emitAllChanged()

        if deleteActivated:
            # Set invalid first
            AppSettings.set('ActivatedItemIndex', str(-1))

            self.activeServerChanged.emit()

            controller = AppConnectionController()

            if controller.isConnected():
                controller.startDisconnection(
                    _('Disconnected') if showTrayMessage else ''
                )

        return len(indexes)

    def deleteSelectedItem(self):
        """Delete selected item."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def handleResultCode(_indexes, code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                self.deleteItemByIndex(_indexes)
            else:
                pass

        if PLATFORM == 'Windows':
            # Windows
            mbox = MBoxQuestionDelete(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = MBoxQuestionDelete(
                icon=AppQMessageBox.Icon.Question, parent=self.parent()
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = (
            f'{indexes[0] + 1} - ' + Storage.UserServers()[indexes[0]].itemRemark
        )
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def editSelectedItemConfiguration(self):
        """Handle edit selected item configuration for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        if len(indexes) != 1:
            # Should not reach here
            return

        index = indexes[0]
        title = f'{index + 1} - ' + Storage.UserServers()[index].itemRemark

        self.configurationEditor.currentIndex = index
        self.configurationEditor.customWindowTitle = title
        self.configurationEditor.setWindowTitle(title)
        self.configurationEditor.setPlainText(
            Storage.UserServers()[index].toJSONString(), True
        )
        self.configurationEditor.show()

    def activateSelectedServer(self):
        """Activate selected server."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        if len(indexes) != 1:
            # Should not reach here
            return

        item = self.proxyIndexFromSourceRow(indexes[0])

        if item.isValid():
            self.handleItemActivated(item)

    def scrollToActivatedItem(self):
        """Handle scroll to activated item for the user servers Qt table view."""
        activatedItem = self.activatedIndex()

        if activatedItem.isValid():
            self.setCurrentIndex(activatedItem)
            self.scrollTo(activatedItem)

    @QtCore.Slot(object, object)
    def _handleProfileTestResultApplied(
        self,
        profile: ServerProfile,
        result: ProfileTestResult,
    ):
        """Repaint the one repository cell committed by the test service."""
        profiles = Storage.UserServers()
        row = profile.index

        if row < 0 or row >= len(profiles) or profiles[row] is not profile:
            return

        column = 'Latency' if result.field is ProfileTestField.Latency else 'Speed'

        self.flushItem(row, self.Headers.index(column), profile)

    def _selectedProfilesForTesting(self):
        """Resolve the current row selection into live repository profiles."""
        profiles = Storage.UserServers()

        return [
            profiles[index]
            for index in self.selectedIndex
            if 0 <= index < len(profiles)
        ]

    def reconcileProfileTestJobs(self):
        """Notify the test service after a live profile collection mutation."""
        self.profileTestManager.reconcileProfiles()

    def testSelectedItemPingLatency(self):
        """Request ICMP latency tests for selected profiles."""
        self.profileTestManager.testPing(self._selectedProfilesForTesting())

    def testSelectedItemTcpingLatency(self):
        """Request asynchronous TCP latency tests for selected profiles."""
        self.profileTestManager.testTcping(self._selectedProfilesForTesting())

    def testSelectedItemDownloadSpeedWithTimeout(self, timeout: int):
        """Request serial download tests for selected profiles."""
        self.profileTestManager.testDownloadSpeed(
            self._selectedProfilesForTesting(),
            timeoutMilliseconds=timeout,
            concurrent=False,
        )

    def testSelectedItemDownloadSpeedWithTimeoutMulti(self, timeout: int):
        """Request concurrent download tests for selected profiles."""
        self.profileTestManager.testDownloadSpeed(
            self._selectedProfilesForTesting(),
            timeoutMilliseconds=timeout,
            concurrent=True,
        )

    def testSelectedItemDownloadSpeed(self):
        """Run the retained serial download-test API for selected rows.

        The Home context menu uses the concurrent variant; this method remains
        available for programmatic callers that explicitly need serial scheduling.
        """
        self.testSelectedItemDownloadSpeedWithTimeout(5000)

    def testSelectedItemDownloadSpeedMulti(self):
        """Request concurrent download tests for selected profiles."""
        self.testSelectedItemDownloadSpeedWithTimeoutMulti(5000)

    def clearSelectedItemTestResult(self):
        """Clear selected item test result."""
        self.profileTestManager.clearResults(self._selectedProfilesForTesting())

    def cleanup(self):
        """Release resources owned by the user servers Qt table view."""
        self.subsManager.shutdown()
        self.profileTestManager.shutdown()
        self._clearSubscriptionActions()

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        """Update subs by unique."""
        self.updateSubscriptions((unique,), httpProxy, **kwargs)

    def updateSubscriptions(self, uniques, httpProxy: Union[str, None], **kwargs):
        """Update stable subscription IDs as one manager-owned batch."""
        kwargs.pop('parent', None)

        self.subsManager.configureHttpProxy(httpProxy)
        self.subsManager.updateSubscriptions(uniques, **kwargs)

    def updateSubs(self, httpProxy: Union[str, None], **kwargs):
        """Update subs."""
        self.selectionModel().clearSelection()
        self.updateSubscriptions(tuple(Storage.UserSubs()), httpProxy, **kwargs)

    @QtCore.Slot()
    def _handleSubscriptionsChanged(self):
        """Refresh the table after the service commits repository changes."""
        self.reconcileProfileTestJobs()

        self.sourceModel.beginResetModel()
        self.sourceModel.endResetModel()
        self.sourceModel.refreshIndexes()

        self.proxyModel.invalidate()

        self.flushAll()

        self.activeServerChanged.emit()

    @QtCore.Slot(str)
    def _handleSubscriptionCommitted(self, unique: str):
        """Clear results and invalidate only work owned by one committed group."""
        self.profileTestManager.invalidateSubscriptions(
            {unique},
            clearResults=True,
        )

    @QtCore.Slot(object)
    def _handleSubscriptionUpdateCompleted(self, batch: SubscriptionUpdateBatch):
        """Present one semantic subscription update result batch."""
        if not batch.showMessageBox:
            return

        mbox = MBoxUpdateSubsInfo(
            successArgs=list(batch.successful),
            failureArgs=list(batch.failed),
            parent=self.window(),
        )
        mbox.setIcon(
            AppQMessageBox.Icon.Information
            if batch.successful
            else AppQMessageBox.Icon.Critical
        )
        mbox.setText(mbox.customText())
        mbox.setColumnMinWidth()
        mbox.open()

    def appendNewItemByFactory(self, factory: CoreConfiguration | ServerProfile):
        """Append new item by factory."""
        factory = ensureProfile(factory)
        index = len(Storage.UserServers())

        # Set index
        factory.index = index

        self.sourceModel.beginInsertRows(QtCore.QModelIndex(), index, index)

        Storage.UserServers().append(factory)

        self.sourceModel.endInsertRows()
        self.sourceModel.refreshIndexes()

        self.flushRow(index, factory)

        if index == 0:
            # The first one. Click it
            self.setCurrentIndex(self.proxyIndexFromSourceRow(0))

            # Try to be user-friendly in some extreme cases
            if not AppConnectionController().isConnected():
                # Activate automatically
                self.activateItemByIndex(0, True)

    def appendNewItem(self, **kwargs):
        """Append new item."""
        acceptInvalid = kwargs.pop('acceptInvalid', False)

        model = {
            'remark': kwargs.pop('remark', ''),
            'config': kwargs.pop('config', ''),
            'subsId': kwargs.pop('subsId', ''),
        }
        factory = profileFromAny(model.pop('config', ''), **model)

        if factory.isValid():
            self.appendNewItemByFactory(factory)
        else:
            if acceptInvalid:
                self.appendNewItemByFactory(factory)
            else:
                # The rejected input may be a complete JSON configuration or
                # share URI containing credentials.
                logger.error('invalid server profile input')

    def exportSelectedItemURI(self):
        """Export selected item URI."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def toURI(factory) -> str:
            """Export the configuration as a share URI."""
            assert isinstance(factory, ServerProfile)

            try:
                return exportConfiguration(factory)
            except Exception:
                # Any non-exit exceptions

                return ''

        # TODO: MessageBox?
        QApplication.clipboard().setText(
            '\n'.join(list(toURI(Storage.UserServers()[index]) for index in indexes))
        )

    def exportSelectedItemQR(self):
        """Export selected item QR."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        window = self.qrCodeWindowFactory()

        return window.startExportByIndex(indexes)

    def exportSelectedItemJSON(self):
        """Export selected item JSON."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # TODO: MessageBox?
        QApplication.clipboard().setText(
            '\n'.join(
                list(Storage.UserServers()[index].toJSONString() for index in indexes)
            )
        )

    def showTabAndSpaces(self):
        """Show tab and spaces."""
        self.configurationEditor.showTabAndSpaces()

    def hideTabAndSpaces(self):
        """Hide tab and spaces."""
        self.configurationEditor.hideTabAndSpaces()

    def keyPressEvent(self, event):
        """Handle a key press for the user servers Qt table view."""
        if event.key() == QtCore.Qt.Key.Key_Return:
            if PLATFORM == 'Darwin':
                # Activate by Enter key on macOS
                self.handleItemActivated(self.currentIndex())
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def retranslate(self):
        """Refresh translated text for the user servers Qt table view."""
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            len(self.Headers) - 1,
        )
        self._rebuildSubscriptionMenu()
