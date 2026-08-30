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

"""Provide widgets for user subs Qt table view."""

from __future__ import annotations

from Furious.Frozenlib import (
    PLATFORM,
    AppFontName,
    AppMainWindow,
    AppSettings,
    Mixins,
    PySide6Legacy,
    registerAppSettings,
)
from Furious.Models import UJSONEncoder
from Furious.Repository import Storage, SubscriptionGroup
from Furious.Service import (
    SUBSCRIPTION_AUTO_UPDATE_OPTIONS,
    SUBSCRIPTION_PROXY_OPTIONS,
    resolveSubscriptionProxy,
)
from Furious.Qt import (
    MBoxQuestionDelete,
    AppQAction,
    AppQHeaderView,
    AppQMenu,
    AppQMessageBox,
    AppQSeparator,
    AppQTableView,
)
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QFont, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from typing import Union, Callable

import logging
import functools

logger = logging.getLogger(__name__)

__all__ = ['SubscriptionTableView']

# Keep the original setting names. The primary value now stores semantic widths
# instead of QHeaderView's schema-dependent opaque state.
LEGACY_SUBSCRIPTION_SECTION_SIZE_SETTING = 'SubscriptionWidgetSectionSizeTable'
SUBSCRIPTION_HEADER_STATE_SETTING = 'UserSubsHeaderViewState'

registerAppSettings(LEGACY_SUBSCRIPTION_SECTION_SIZE_SETTING)
registerAppSettings(SUBSCRIPTION_HEADER_STATE_SETTING)


class SubscriptionTableHorizontalHeader(AppQHeaderView):
    """Provide the user subs Qt table view horizontal table header."""

    ColumnKeys = (
        'remark',
        'webURL',
        'enabled',
        'lastSyncStatus',
        'lastUpdated',
        'profiles',
    )
    DefaultSectionSizes = (260, 520, 120, 150, 220, 140)
    LegacyColumnKeys = ('remark', 'webURL', 'autoupdate', 'proxy')

    # Format discriminator for the semantic JSON stored under
    # UserSubsHeaderViewState. The namespace and version let us reject
    # unrelated strings or a future incompatible semantic format.
    StateFormat = 'Furious.SubscriptionHeaderWidths/1'

    def __init__(self, *args, **kwargs):
        """Initialize the SubscriptionTableHorizontalHeader."""
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

    def _configureInteractiveSections(self):
        """Normalize interaction without changing the logical column order."""
        self.setSectionsMovable(False)
        self.setCascadingSectionResizes(False)
        self.setMinimumSectionSize(80)
        self.setStretchLastSection(False)
        self.setCustomSectionResizeMode()

    def _applyDefaultSectionSizes(self):
        """Apply balanced widths for the concise subscription table."""
        self.setStretchLastSection(False)

        for section, size in enumerate(self.DefaultSectionSizes):
            if section < self.count():
                self.resizeSection(section, size)

    @classmethod
    def _semanticWidths(cls, state) -> dict[str, int]:
        """Decode the schema-independent header format, if present."""
        if not isinstance(state, str):
            return {}

        try:
            decoded = UJSONEncoder.decode(state)
        except Exception:
            # Any non-exit exceptions

            return {}

        if not isinstance(decoded, dict) or decoded.get('format') != cls.StateFormat:
            return {}

        widths = decoded.get('widths')

        if not isinstance(widths, dict):
            return {}

        return {
            key: width
            for key, width in widths.items()
            if key in cls.ColumnKeys
            and isinstance(width, (int, float))
            and not isinstance(width, bool)
            and width > 0
        }

    @classmethod
    def _legacyHeaderWidths(cls, state) -> dict[str, int]:
        """Extract widths from a legacy Qt state without touching this header."""
        if state is None or isinstance(state, str):
            return {}

        probe = QTableView()
        probeModel = QStandardItemModel(0, 1, probe)
        probe.setModel(probeModel)
        probeHeader = probe.horizontalHeader()

        # restoreState() is intentionally used only on this disposable probe
        # as a read-only, one-time compatibility path for the original
        # four-column UserSubsHeaderViewState. Applying the opaque Qt state to
        # the live five-column header could recreate phantom sections, legacy
        # ordering, hidden state, and incompatible resize behavior.
        try:
            if not probeHeader.restoreState(state):
                return {}
        except Exception:
            # Any non-exit exceptions

            return {}

        if probeHeader.count() != len(cls.LegacyColumnKeys):
            return {}

        for section in range(probeHeader.count()):
            probeHeader.showSection(section)

        return {
            key: probeHeader.sectionSize(section)
            for section, key in enumerate(cls.LegacyColumnKeys)
            if key in cls.ColumnKeys and section < probeHeader.count()
        }

    @classmethod
    def _oldestSectionWidths(cls) -> dict[str, int]:
        """Read the original index-based width table as a final fallback."""
        try:
            widths = UJSONEncoder.decode(
                AppSettings.get(LEGACY_SUBSCRIPTION_SECTION_SIZE_SETTING)
            )
        except Exception:
            # Any non-exit exceptions

            return {}

        if not isinstance(widths, dict):
            return {}

        result = {}

        for section, key in enumerate(cls.LegacyColumnKeys):
            width = widths.get(str(section))

            if (
                key in cls.ColumnKeys
                and isinstance(width, (int, float))
                and not isinstance(width, bool)
                and width > 0
            ):
                result[key] = width

        return result

    def _applyWidths(self, widths: dict[str, int]):
        """Apply semantic widths to the matching logical sections."""
        for section, key in enumerate(self.ColumnKeys):
            width = widths.get(key)

            if width is not None:
                self.resizeSection(
                    section,
                    max(self.minimumSectionSize(), round(width)),
                )

    def configureSections(self):
        """Restore semantic widths or safely read either historical format."""
        self._configureInteractiveSections()
        self._applyDefaultSectionSizes()

        state = AppSettings.get(SUBSCRIPTION_HEADER_STATE_SETTING)
        widths = self._semanticWidths(state) or self._legacyHeaderWidths(state)

        if not widths:
            widths = self._oldestSectionWidths()

        self._applyWidths(widths)

        # Saved Qt state may contain moved, hidden, or non-interactive sections.
        # It is never restored onto the live header; the current schema owns
        # order and interaction behavior.
        for section in range(self.count()):
            self.showSection(section)

        self._configureInteractiveSections()

    def cleanup(self):
        """Persist semantic widths under the established setting name."""
        # Do not use QHeaderView.saveState() here. Its opaque binary data also
        # records the section count, order, visibility, and resize modes, so it
        # is unsafe to restore after the table schema changes. Persist only
        # widths keyed by stable field names instead.
        AppSettings.set(
            SUBSCRIPTION_HEADER_STATE_SETTING,
            UJSONEncoder.encode(
                {
                    'format': self.StateFormat,
                    'widths': {
                        key: self.sectionSize(section)
                        for section, key in enumerate(self.ColumnKeys)
                        if section < self.count()
                    },
                }
            ),
        )


class SubscriptionTableVerticalHeader(AppQHeaderView):
    """Provide the user subs Qt table view vertical table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the SubscriptionTableVerticalHeader."""
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class SubscriptionTableColumn:
    """Describe and render user subs Qt table view table columns."""

    def __init__(self, name: str, func: Callable[[dict], str] = None):
        """Initialize the SubscriptionTableColumn."""
        self.name = name
        self.func = func

    def __call__(self, item: dict) -> str:
        """Invoke the user subs Qt table view headers as a callable."""
        if callable(self.func):
            return self.func(item)
        else:
            return ''

    def __eq__(self, other):
        """Compare the user subs Qt table view headers with another value."""
        return str(self) == str(other)

    def __str__(self):
        """Return the display text for the user subs Qt table view headers."""
        return self.name


def subscriptionSyncStatusText(item: dict) -> str:
    """Return one concise, localized subscription synchronization state."""
    return {
        'syncing': _('Updating...'),
        'success': _('Updated'),
        'error': _('Update Failed'),
    }.get(str(item.get('lastSyncStatus', '')), _('Never'))


class UserSubsTableModel(QtCore.QAbstractTableModel):
    """Expose user subs table data through a Qt item model."""

    def __init__(
        self,
        headers: list[SubscriptionTableColumn],
        itemKey: list[str],
        parent=None,
    ):
        """Initialize the UserSubsTableModel."""
        super().__init__(parent)

        self.headers = headers
        self.itemKey = itemKey

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of rows exposed by the model."""
        if parent.isValid():
            return 0

        return len(Storage.UserSubs())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of columns exposed by the model."""
        if parent.isValid():
            return 0

        return len(self.headers)

    def flags(self, index):
        """Return the Qt item flags for a model index."""
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

        if self.itemKey[index.column()] not in [
            'autoupdate',
            'proxy',
            'enabled',
            'lastSyncStatus',
            'lastUpdated',
            'profiles',
        ]:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable

        return flags

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Return the data managed by the user subs table model."""
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()

        if row < 0 or row >= len(Storage.UserSubs()):
            return None

        if column < 0 or column >= len(self.headers):
            return None

        subsob = self.subsObjectByRow(row)
        text = self.headers[column](subsob)
        mapped = self.itemKey[column]

        if mapped == 'profiles':
            unique = self.uniqueByRow(row)
            text = str(
                sum(
                    1
                    for profile in Storage.UserServers()
                    if profile.itemSubscription == unique
                    and profile.itemSubscriptionManaged
                )
            )

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if mapped in ['autoupdate', 'proxy', 'enabled']:
                return _(text)

            return text

        if role == QtCore.Qt.ItemDataRole.EditRole:
            return text

        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return text

        if role == QtCore.Qt.ItemDataRole.FontRole:
            return QFont(AppFontName())

        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Update model data for the requested role."""
        if role != QtCore.Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        row = index.row()
        column = index.column()

        if row < 0 or row >= len(Storage.UserSubs()):
            return False

        mapped = self.itemKey[column]

        if mapped in [
            'autoupdate',
            'proxy',
            'enabled',
            'lastSyncStatus',
            'lastUpdated',
            'profiles',
        ]:
            return False

        self.subsObjectByRow(row)[mapped] = str(value)
        self.dataChanged.emit(index, index, [])

        return True

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
    def uniqueByRow(row: int) -> str:
        """Return the unique by row value used by the user subs table model."""
        return list(Storage.UserSubs().keys())[row]

    @classmethod
    def subsObjectByRow(cls, row: int) -> dict:
        """Return the subs object by row value used by the user subs table model."""
        return Storage.UserSubs()[cls.uniqueByRow(row)]

    def emitRowChanged(self, row: int, column: Union[int, None] = None):
        """Handle emit row changed for the user subs table model."""
        if row < 0 or row >= self.rowCount():
            return

        if column is None:
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
        else:
            left = self.index(row, column)
            right = left

        self.dataChanged.emit(left, right, [])

    def emitAllChanged(self):
        """Handle emit all changed for the user subs table model."""
        if self.rowCount() == 0 or self.columnCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            [],
        )


# Headers VALUE
_TRANSLATABLE_HEADERS = [
    _('Never'),
    _('Every 5 mins'),
    _('Every 10 mins'),
    _('Every 15 mins'),
    _('Every 30 mins'),
    _('Every 45 mins'),
    _('Every 1 hour'),
    _('Every 2 hours'),
    _('Every 3 hours'),
    _('Every 6 hours'),
    _('Every 8 hours'),
    _('Every 10 hours'),
    _('Every 12 hours'),
    _('Every 24 hours'),
    _('Use current proxy'),
    _('Force proxy'),
    _('No proxy'),
    _('Remark'),
    _('Auto Update'),
    _('Auto Update Use Proxy'),
    _('Enabled'),
    _('Disabled'),
    _('Sync Status'),
    _('Updating...'),
    _('Updated'),
    _('Update Failed'),
    _('Last Updated'),
    _('Profiles'),
]


class SubscriptionTableView(Mixins.QTranslatable, AppQTableView):
    """Represent user subs Qt table view."""

    groupsChanged = QtCore.Signal()
    RowHeight = 42

    AutoUpdateOptions = SUBSCRIPTION_AUTO_UPDATE_OPTIONS
    ProxyOptions = {
        option: functools.partial(resolveSubscriptionProxy, option)
        for option in SUBSCRIPTION_PROXY_OPTIONS
    }

    Headers = [
        SubscriptionTableColumn('Remark', lambda item: item.get('remark', '')),
        SubscriptionTableColumn('URL', lambda item: item.get('webURL', '')),
        SubscriptionTableColumn(
            'Enabled',
            lambda item: 'Enabled' if item.get('enabled', True) else 'Disabled',
        ),
        SubscriptionTableColumn('Sync Status', subscriptionSyncStatusText),
        SubscriptionTableColumn(
            'Last Updated',
            lambda item: item.get('lastUpdated', ''),
        ),
        SubscriptionTableColumn('Profiles'),
    ]

    # Corresponds to 'Headers'
    ItemKey = [
        'remark',
        'webURL',
        'enabled',
        'lastSyncStatus',
        'lastUpdated',
        'profiles',
    ]

    def __init__(self, *args, **kwargs):
        """Initialize the subscription table view."""
        self.deleteUniqueCallback, self.subsManager = (
            kwargs.pop('deleteUniqueCallback', None),
            kwargs.pop('subscriptionManager', None),
        )

        super().__init__(*args, **kwargs)

        self.sourceModel = UserSubsTableModel(self.Headers, self.ItemKey, parent=self)
        self.setModel(self.sourceModel)

        # Install custom header
        self.setHorizontalHeader(
            SubscriptionTableHorizontalHeader(
                parent=self,
                sectionSizeSettingsName=SUBSCRIPTION_HEADER_STATE_SETTING,
            )
        )
        self.setVerticalHeader(SubscriptionTableVerticalHeader(self))
        self.setDefaultRowHeight(self.RowHeight)

        header = self.horizontalHeader()
        header.configureSections()

        self.setSortingEnabled(False)

        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        contextMenuActions = [
            AppQAction(
                _('Move Up'),
                callback=lambda: self.moveSelectedGroup(-1),
            ),
            AppQAction(
                _('Move Down'),
                callback=lambda: self.moveSelectedGroup(1),
            ),
            AppQSeparator(),
            AppQAction(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
            ),
        ]

        self.contextMenu = AppQMenu(*contextMenuActions)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Signals
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

        # Flush all data to table
        self.flushAll()

    @property
    def selectedIndex(self):
        """Return the selected index value."""
        return sorted(
            list(set(index.row() for index in self.selectionModel().selectedRows()))
        )

    @property
    def selectedUniques(self):
        """Return stable subscription IDs for the selected rows."""
        keys = tuple(Storage.UserSubs())

        return tuple(keys[row] for row in self.selectedIndex if row < len(keys))

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        """Handle custom context menu requested."""
        self.contextMenu.exec(self.viewport().mapToGlobal(point))

    def deleteSelectedItem(self):
        """Delete selected item."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        def handleResultCode(_indexes, code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                for i in range(len(_indexes)):
                    deleteIndex = _indexes[i] - i
                    deleteUnique = list(Storage.UserSubs().keys())[deleteIndex]

                    self.sourceModel.beginRemoveRows(
                        QtCore.QModelIndex(),
                        deleteIndex,
                        deleteIndex,
                    )

                    Storage.removeSubscriptionGroup(deleteUnique)

                    if self.subsManager is not None:
                        self.subsManager.removeAutoUpdate(deleteUnique)

                    self.sourceModel.endRemoveRows()

                    if callable(self.deleteUniqueCallback):
                        self.deleteUniqueCallback(deleteUnique)

                for order, value in enumerate(Storage.UserSubs().values()):
                    value['sortOrder'] = order

                self.flushAll()
                self.groupsChanged.emit()
            else:
                # Do not delete
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
        mbox.possibleRemark = self.sourceModel.data(
            self.sourceModel.index(indexes[0], 0),
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def moveSelectedGroup(self, offset: int):
        """Move one group while preserving its stable ID and timer."""
        indexes = self.selectedIndex

        if len(indexes) != 1 or offset not in (-1, 1):
            return

        source = indexes[0]
        target = source + offset

        items = list(Storage.UserSubs().items())

        if target < 0 or target >= len(items):
            return

        self.sourceModel.layoutAboutToBeChanged.emit()

        item = items.pop(source)

        items.insert(target, item)

        Storage.UserSubs().clear()
        Storage.UserSubs().update(items)

        for order, (unique, value) in enumerate(items):
            value['sortOrder'] = order

        self.sourceModel.layoutChanged.emit()
        self.selectRow(target)
        self.groupsChanged.emit()

    def flushItem(self, row, column, item):
        """Refresh item."""
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        self.sourceModel.emitRowChanged(row, column)

    def flushRow(self, row, item):
        """Refresh row."""
        for column in list(range(self.sourceModel.columnCount())):
            self.flushItem(row, column, item)

    def flushAll(self):
        """Refresh all."""
        for item in Storage.UserSubs().values():
            item.setdefault('enabled', True)
            item.setdefault('userAgent', '')
            item.setdefault('filter', '')
            item.setdefault('lastUpdated', '')
            item.setdefault('lastSyncStatus', '')

        self.sourceModel.emitAllChanged()

        for index, key in enumerate(Storage.UserSubs()):
            self.flushRow(index, Storage.UserSubs()[key])

    def appendNewItem(self, **kwargs):
        """Append new item."""
        (
            unique,
            remark,
            webURL,
            enabled,
            autoupdate,
            proxy,
            userAgent,
            profileFilter,
            lastUpdated,
        ) = (
            kwargs.pop('unique', ''),
            kwargs.pop('remark', ''),
            kwargs.pop('webURL', ''),
            kwargs.pop('enabled', True),
            kwargs.pop('autoupdate', ''),
            kwargs.pop('proxy', ''),
            kwargs.pop('userAgent', ''),
            kwargs.pop('filter', ''),
            kwargs.pop('lastUpdated', ''),
        )

        group = Storage.SubscriptionGroup(unique) or SubscriptionGroup(
            id=unique,
            sortOrder=len(Storage.UserSubs()),
        )
        group.remark = remark
        group.webURL = webURL
        group.enabled = bool(enabled)
        group.autoupdate = autoupdate
        group.proxy = proxy
        group.userAgent = userAgent
        group.filter = profileFilter
        group.lastUpdated = lastUpdated

        subsob = {unique: group.toMapping()}

        if unique in Storage.UserSubs():
            row = list(Storage.UserSubs().keys()).index(unique)

            Storage.upsertSubscriptionGroup(group)

            self.flushRow(row, subsob[unique])
        else:
            row = self.sourceModel.rowCount()

            self.sourceModel.beginInsertRows(QtCore.QModelIndex(), row, row)
            Storage.upsertSubscriptionGroup(group)
            self.sourceModel.endInsertRows()

            self.flushRow(row, subsob[unique])

        if self.subsManager is not None:
            self.subsManager.configureAutoUpdate(unique)

        self.groupsChanged.emit()

    @staticmethod
    def updateSubsByUnique(
        unique: str, httpProxy: Union[str, Callable, None], **kwargs
    ):
        """Update subs by unique."""
        showMessageBox = kwargs.pop('showMessageBox', False)

        if callable(httpProxy):
            try:
                realHttpProxy = httpProxy()
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'error while configuring http proxy: {ex}. '
                    f'Update subscription uses no proxy'
                )

                realHttpProxy = None
        else:
            realHttpProxy = httpProxy

        AppMainWindow().updateSubsByUnique(
            unique, realHttpProxy, showMessageBox=showMessageBox, **kwargs
        )

    def retranslate(self):
        """Refresh translated text for the user subs Qt table view."""
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            len(self.Headers) - 1,
        )
