# Copyright (C) 2024-present  Loren Eteval & contributors <loren.eteval@proton.me>
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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union, Callable

import logging
import functools

logger = logging.getLogger(__name__)

__all__ = ['UserSubsQTableView']

# Migrate legacy settings
registerAppSettings('SubscriptionWidgetSectionSizeTable')
registerAppSettings('UserSubsHeaderViewState')


class UserSubsQTableViewHorizontalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class UserSubsQTableViewVerticalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class UserSubsQTableViewHeaders:
    def __init__(self, name: str, func: Callable[[dict], str] = None):
        self.name = name
        self.func = func

    def __call__(self, item: dict) -> str:
        if callable(self.func):
            return self.func(item)
        else:
            return ''

    def __eq__(self, other):
        return str(self) == str(other)

    def __str__(self):
        return self.name


class UserSubsAppQComboBox(AppQComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        # Do not emit 'currentTextChanged' when retranslate
        with Mixins.QBlockSignalContext(self):
            super().retranslate()


class UserSubsTableModel(QtCore.QAbstractTableModel):
    def __init__(
        self,
        headers: list[UserSubsQTableViewHeaders],
        itemKey: list[str],
        parent=None,
    ):
        super().__init__(parent)

        self.headers = headers
        self.itemKey = itemKey

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(Storage.UserSubs())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(self.headers)

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

        if self.itemKey[index.column()] not in ['autoupdate', 'proxy']:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable

        return flags

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
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

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if self.itemKey[column] in ['autoupdate', 'proxy']:
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
        if role != QtCore.Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        row = index.row()
        column = index.column()

        if row < 0 or row >= len(Storage.UserSubs()):
            return False

        mapped = self.itemKey[column]

        if mapped in ['autoupdate', 'proxy']:
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
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            if 0 <= section < len(self.headers):
                return _(str(self.headers[section]))

            return None

        return section + 1

    @staticmethod
    def uniqueByRow(row: int) -> str:
        return list(Storage.UserSubs().keys())[row]

    @classmethod
    def subsObjectByRow(cls, row: int) -> dict:
        return Storage.UserSubs()[cls.uniqueByRow(row)]

    def emitRowChanged(self, row: int, column: Union[int, None] = None):
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
]


class UserSubsQTableView(Mixins.QTranslatable, AppQTableView):
    AutoUpdateOptions = {
        '': None,
        'Never': None,
        'Every 5 mins': 5 * 60 * 1000,
        'Every 10 mins': 10 * 60 * 1000,
        'Every 15 mins': 15 * 60 * 1000,
        'Every 30 mins': 30 * 60 * 1000,
        'Every 45 mins': 45 * 60 * 1000,
        'Every 1 hour': 1 * 60 * 60 * 1000,
        'Every 2 hours': 2 * 60 * 60 * 1000,
        'Every 3 hours': 3 * 60 * 60 * 1000,
        'Every 6 hours': 6 * 60 * 60 * 1000,
        'Every 8 hours': 8 * 60 * 60 * 1000,
        'Every 10 hours': 10 * 60 * 60 * 1000,
        'Every 12 hours': 12 * 60 * 60 * 1000,
        'Every 24 hours': 24 * 60 * 60 * 1000,
    }

    ProxyOptions = {
        '': lambda: None,
        'Use current proxy': lambda: Storage.Extras.UserHttpProxy(),
        'Force proxy': lambda: '127.0.0.1:10809',
        'No proxy': lambda: None,
    }

    Headers = [
        UserSubsQTableViewHeaders('Remark', lambda item: item.get('remark', '')),
        UserSubsQTableViewHeaders('URL', lambda item: item.get('webURL', '')),
        UserSubsQTableViewHeaders(
            'Auto Update', lambda item: item.get('autoupdate', '')
        ),
        UserSubsQTableViewHeaders(
            'Auto Update Use Proxy', lambda item: item.get('proxy', '')
        ),
    ]

    # Corresponds to 'Headers'
    ItemKey = ['remark', 'webURL', 'autoupdate', 'proxy']

    def __init__(self, *args, **kwargs):
        self.deleteUniqueCallback = kwargs.pop('deleteUniqueCallback', None)

        super().__init__(*args, **kwargs)

        self.timers = list(QtCore.QTimer() for i in range(len(Storage.UserSubs())))
        self.timerConnected = list(False for i in range(len(Storage.UserSubs())))
        self.sourceModel = UserSubsTableModel(self.Headers, self.ItemKey, parent=self)
        self.setModel(self.sourceModel)

        # Install custom header
        self.setHorizontalHeader(
            UserSubsQTableViewHorizontalHeader(
                parent=self,
                legacySectionSizeSettingsName='SubscriptionWidgetSectionSizeTable',
                sectionSizeSettingsName='UserSubsHeaderViewState',
            )
        )
        self.setVerticalHeader(UserSubsQTableViewVerticalHeader(self))

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.setSortingEnabled(False)

        # Selection
        self.setSelectionColor(AppHue.disconnectedColor())
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        contextMenuActions = [
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
        return sorted(
            list(set(index.row() for index in self.selectionModel().selectedRows()))
        )

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        def handleResultCode(_indexes, code):
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

                    Storage.UserSubs().pop(deleteUnique)

                    # Begin timer cleanup
                    qtimer = self.timers[deleteIndex]

                    assert isinstance(qtimer, QtCore.QTimer)

                    if self.timerConnected[deleteIndex]:
                        try:
                            qtimer.timeout.disconnect()
                        except Exception as ex:
                            # Any non-exit exceptions

                            # Disconnect all previous signals if possible
                            pass

                    qtimer.stop()
                    # End timer cleanup

                    # Remove timer from list
                    self.timers.pop(deleteIndex)
                    self.timerConnected.pop(deleteIndex)

                    self.sourceModel.endRemoveRows()

                    if callable(self.deleteUniqueCallback):
                        self.deleteUniqueCallback(deleteUnique)

                self.flushAll()
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

    def handleAutoUpdateComboBoxCurrentTextChanged(self, text: str, row: int):
        textEnglish = _(text, 'EN')

        unique = list(Storage.UserSubs().keys())[row]
        subsob = Storage.UserSubs()[unique]

        remark, webURL = subsob['remark'], subsob['webURL']

        try:
            timems = self.AutoUpdateOptions[textEnglish]
        except KeyError:
            # Invalid key. Reset
            logger.error(f'\'{textEnglish}\' is not in auto update options. Reset')

            textEnglish = ''

            # Write to subs object
            subsob['autoupdate'] = textEnglish

            timems = self.AutoUpdateOptions[textEnglish]

        qtimer = self.timers[row]

        assert isinstance(qtimer, QtCore.QTimer)

        if timems is not None:
            logger.info(
                f'start auto update job for subscription ({remark}, {webURL}). '
                f'Interval is {timems // (60 * 1000)} mins'
            )

            def getHttpProxy(_subsob):
                return self.ProxyOptions[_subsob.get('proxy', '')]()

            if self.timerConnected[row]:
                try:
                    qtimer.timeout.disconnect()
                except Exception as ex:
                    # Any non-exit exceptions

                    # Disconnect all previous signals if possible
                    pass

            qtimer.timeout.connect(
                functools.partial(
                    self.updateSubsByUnique,
                    unique=unique,
                    httpProxy=functools.partial(getHttpProxy, subsob),
                )
            )
            self.timerConnected[row] = True
            qtimer.start(timems)
        else:
            logger.info(f'stop auto update job for subscription ({remark}, {webURL})')

            if self.timerConnected[row]:
                try:
                    qtimer.timeout.disconnect()
                except Exception as ex:
                    # Any non-exit exceptions

                    # Disconnect all previous signals if possible
                    pass

                self.timerConnected[row] = False

            qtimer.stop()

        # Write to subs object
        subsob['autoupdate'] = textEnglish
        self.sourceModel.emitRowChanged(row, self.Headers.index('Auto Update'))

        # Return potentially fixed value
        return textEnglish

    def handleProxyComboBoxCurrentTextChanged(self, text: str, row: int):
        textEnglish = _(text, 'EN')

        unique = list(Storage.UserSubs().keys())[row]
        subsob = Storage.UserSubs()[unique]

        try:
            proxyFn = self.ProxyOptions[textEnglish]
        except KeyError:
            # Invalid key. Reset
            logger.error(f'\'{textEnglish}\' is not in proxy options. Reset')

            textEnglish = ''

            # Write to subs object
            subsob['proxy'] = textEnglish

            proxyFn = self.ProxyOptions[textEnglish]

        assert callable(proxyFn)

        # Write to subs object
        subsob['proxy'] = textEnglish
        self.sourceModel.emitRowChanged(
            row, self.Headers.index('Auto Update Use Proxy')
        )

        # Return potentially fixed value
        return textEnglish

    def flushItem(self, row, column, item):
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        index = self.sourceModel.index(row, column)

        if column == self.Headers.index('Auto Update'):
            header = self.Headers[column]

            newItem = UserSubsAppQComboBox()
            newItem.addItems(list(_(key) for key in self.AutoUpdateOptions.keys()))
            newItem.setFont(QFont(AppFontName()))

            itemIndex = newItem.findText(
                _(self.handleAutoUpdateComboBoxCurrentTextChanged(header(item), row))
            )

            if itemIndex >= 0:
                newItem.setCurrentIndex(itemIndex)

            newItem.currentTextChanged.connect(
                functools.partial(
                    self.handleAutoUpdateComboBoxCurrentTextChanged,
                    row=row,
                )
            )

            self.setIndexWidget(index, newItem)
            self.sourceModel.emitRowChanged(row, column)
        elif column == self.Headers.index('Auto Update Use Proxy'):
            header = self.Headers[column]

            newItem = UserSubsAppQComboBox()
            newItem.addItems(list(_(key) for key in self.ProxyOptions.keys()))
            newItem.setFont(QFont(AppFontName()))

            itemIndex = newItem.findText(
                _(self.handleProxyComboBoxCurrentTextChanged(header(item), row))
            )

            if itemIndex >= 0:
                newItem.setCurrentIndex(itemIndex)

            newItem.currentTextChanged.connect(
                functools.partial(
                    self.handleProxyComboBoxCurrentTextChanged,
                    row=row,
                )
            )

            self.setIndexWidget(index, newItem)
            self.sourceModel.emitRowChanged(row, column)
        else:
            self.sourceModel.emitRowChanged(row, column)

    def flushRow(self, row, item):
        for column in list(range(self.sourceModel.columnCount())):
            self.flushItem(row, column, item)

    def flushAll(self):
        self.sourceModel.emitAllChanged()

        for index, key in enumerate(Storage.UserSubs()):
            self.flushRow(index, Storage.UserSubs()[key])

    def appendNewItem(self, **kwargs):
        unique, remark, webURL, autoupdate, proxy = (
            kwargs.pop('unique', ''),
            kwargs.pop('remark', ''),
            kwargs.pop('webURL', ''),
            # Below values are not filled when adding item via Gui
            kwargs.pop('autoupdate', ''),
            kwargs.pop('proxy', ''),
        )

        # The internal subs object
        subsob = {
            unique: {
                'remark': remark,
                'webURL': webURL,
                'autoupdate': autoupdate,
                'proxy': proxy,
            }
        }

        if unique in Storage.UserSubs():
            row = list(Storage.UserSubs().keys()).index(unique)
            Storage.UserSubs().update(subsob)
            self.flushRow(row, subsob[unique])
        else:
            row = self.sourceModel.rowCount()

            # Add timer
            self.timers.append(QtCore.QTimer())
            self.timerConnected.append(False)

            self.sourceModel.beginInsertRows(QtCore.QModelIndex(), row, row)
            Storage.UserSubs().update(subsob)
            self.sourceModel.endInsertRows()

            self.flushRow(row, subsob[unique])

    @staticmethod
    def updateSubsByUnique(
        unique: str, httpProxy: Union[str, Callable, None], **kwargs
    ):
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

        APP().mainWindow.updateSubsByUnique(
            unique, realHttpProxy, showMessageBox=showMessageBox, **kwargs
        )

    def retranslate(self):
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            len(self.Headers) - 1,
        )
