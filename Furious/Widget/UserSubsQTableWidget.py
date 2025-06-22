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

from __future__ import annotations

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union, Callable

import logging
import functools

logger = logging.getLogger(__name__)

__all__ = ['UserSubsQTableWidget']

# Migrate legacy settings
registerAppSettings('SubscriptionWidgetSectionSizeTable')
registerAppSettings('UserSubsHeaderViewState')


class UserSubsQTableWidgetHorizontalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class UserSubsQTableWidgetVerticalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class UserSubsQTableWidgetHeaders:
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
        with QBlockSignals(self):
            super().retranslate()


# Headers VALUE
TRANSLATABLE_HEADERS = [
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


class UserSubsQTableWidget(QTranslatable, AppQTableWidget):
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
        'Use current proxy': lambda: connectedHttpProxyEndpoint(),
        'Force proxy': lambda: '127.0.0.1:10809',
        'No proxy': lambda: None,
    }

    Headers = [
        UserSubsQTableWidgetHeaders('Remark', lambda item: item.get('remark', '')),
        UserSubsQTableWidgetHeaders('URL', lambda item: item.get('webURL', '')),
        UserSubsQTableWidgetHeaders(
            'Auto Update', lambda item: item.get('autoupdate', '')
        ),
        UserSubsQTableWidgetHeaders(
            'Auto Update Use Proxy', lambda item: item.get('proxy', '')
        ),
    ]

    def __init__(self, *args, **kwargs):
        self.deleteUniqueCallback = kwargs.pop('deleteUniqueCallback', None)

        super().__init__(*args, **kwargs)

        self.timers = list(QtCore.QTimer() for i in range(len(AS_UserSubscription())))

        # Must set before flush all
        self.setColumnCount(len(self.Headers))

        # Flush all data to table
        self.flushAll()

        # Install custom header
        self.setHorizontalHeader(
            UserSubsQTableWidgetHorizontalHeader(
                parent=self,
                legacySectionSizeSettingsName='SubscriptionWidgetSectionSizeTable',
                sectionSizeSettingsName='UserSubsHeaderViewState',
            )
        )
        self.setVerticalHeader(UserSubsQTableWidgetVerticalHeader(self))

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.setHorizontalHeaderLabels(list(_(str(header)) for header in self.Headers))

        # Selection
        self.setSelectionColor(AppHue.disconnectedColor())
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

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
        self.itemChanged.connect(self.handleItemChanged)
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemChanged(self, item: QTableWidgetItem):
        unique = list(AS_UserSubscription().keys())[item.row()]
        # 'autoupdate', 'proxy' is not triggered here
        keyMap = ['remark', 'webURL', 'autoupdate', 'proxy']

        AS_UserSubscription()[unique][keyMap[item.column()]] = item.text()

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        def handleResultCode(_indexes, code):
            if code == PySide6LegacyEnumValueWrapper(AppQMessageBox.StandardButton.Yes):
                for i in range(len(_indexes)):
                    deleteIndex = _indexes[i] - i
                    deleteUnique = list(AS_UserSubscription().keys())[deleteIndex]

                    self.removeRow(deleteIndex)

                    AS_UserSubscription().pop(deleteUnique)

                    # Begin timer cleanup
                    qtimer = self.timers[deleteIndex]

                    assert isinstance(qtimer, QtCore.QTimer)

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

                    if callable(self.deleteUniqueCallback):
                        self.deleteUniqueCallback(deleteUnique)
            else:
                # Do not delete
                pass

        if PLATFORM == 'Windows':
            # Windows
            mbox = QuestionDeleteMBox(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = QuestionDeleteMBox(
                icon=AppQMessageBox.Icon.Question, parent=self.parent()
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = self.item(indexes[0], 0).text()
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def handleAutoUpdateComboBoxCurrentTextChanged(self, text: str, row: int):
        textEnglish = _(text, 'EN')

        unique = list(AS_UserSubscription().keys())[row]
        subsob = AS_UserSubscription()[unique]

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
            qtimer.start(timems)
        else:
            logger.info(f'stop auto update job for subscription ({remark}, {webURL})')

            try:
                qtimer.timeout.disconnect()
            except Exception as ex:
                # Any non-exit exceptions

                # Disconnect all previous signals if possible
                pass

            qtimer.stop()

        # Write to subs object
        subsob['autoupdate'] = textEnglish

        # Return potentially fixed value
        return textEnglish

    def handleProxyComboBoxCurrentTextChanged(self, text: str, row: int):
        textEnglish = _(text, 'EN')

        unique = list(AS_UserSubscription().keys())[row]
        subsob = AS_UserSubscription()[unique]

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

        # Return potentially fixed value
        return textEnglish

    def flushItem(self, row, column, item):
        if column == self.Headers.index('Auto Update'):
            header = self.Headers[column]

            oldItem = self.item(row, column)
            newItem = UserSubsAppQComboBox()
            newItem.addItems(list(_(key) for key in self.AutoUpdateOptions.keys()))

            if oldItem is None:
                # Item does not exist
                newItem.setFont(QFont(APP().customFontName))
            else:
                # Use existing
                newItem.setFont(oldItem.font())

            index = newItem.findText(
                _(self.handleAutoUpdateComboBoxCurrentTextChanged(header(item), row))
            )

            if index >= 0:
                newItem.setCurrentIndex(index)

            newItem.currentTextChanged.connect(
                functools.partial(
                    self.handleAutoUpdateComboBoxCurrentTextChanged,
                    row=row,
                )
            )

            self.setCellWidget(row, column, newItem)
        elif column == self.Headers.index('Auto Update Use Proxy'):
            header = self.Headers[column]

            oldItem = self.item(row, column)
            newItem = UserSubsAppQComboBox()
            newItem.addItems(list(_(key) for key in self.ProxyOptions.keys()))

            if oldItem is None:
                # Item does not exist
                newItem.setFont(QFont(APP().customFontName))
            else:
                # Use existing
                newItem.setFont(oldItem.font())

            index = newItem.findText(
                _(self.handleProxyComboBoxCurrentTextChanged(header(item), row))
            )

            if index >= 0:
                newItem.setCurrentIndex(index)

            newItem.currentTextChanged.connect(
                functools.partial(
                    self.handleProxyComboBoxCurrentTextChanged,
                    row=row,
                )
            )

            self.setCellWidget(row, column, newItem)
        else:
            header = self.Headers[column]

            oldItem = self.item(row, column)
            newItem = QTableWidgetItem(header(item))

            if oldItem is None:
                # Item does not exist
                newItem.setFont(QFont(APP().customFontName))
            else:
                # Use existing
                newItem.setFont(oldItem.font())
                newItem.setForeground(oldItem.foreground())

                if oldItem.textAlignment() != 0:
                    newItem.setTextAlignment(oldItem.textAlignment())

                # Editable
                newItem.setFlags(
                    QtCore.Qt.ItemFlag.ItemIsEnabled
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                    | QtCore.Qt.ItemFlag.ItemIsEditable
                )

            self.setItem(row, column, newItem)

    def flushRow(self, row, item):
        for column in list(range(self.columnCount())):
            self.flushItem(row, column, item)

    def flushAll(self):
        if self.rowCount() == 0:
            # Should insert row
            for index, key in enumerate(AS_UserSubscription()):
                self.insertRow(index)
                self.flushRow(index, AS_UserSubscription()[key])
        else:
            for index, key in enumerate(AS_UserSubscription()):
                self.flushRow(index, AS_UserSubscription()[key])

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

        # 'unique' should be unique in subscription storage,
        # but protect it anyway.
        if unique not in AS_UserSubscription():
            # Add timer
            self.timers.append(QtCore.QTimer())

        AS_UserSubscription().update(subsob)

        row = self.rowCount()

        self.insertRow(row)
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
        self.setHorizontalHeaderLabels(list(_(str(header)) for header in self.Headers))
