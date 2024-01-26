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

from typing import Callable

__all__ = ['UserSubsQTableWidget']

registerAppSettings('SubscriptionWidgetSectionSizeTable')


class UserSubsQTableWidgetHorizontalHeader(AppQHeaderView):
    def sectionSizeSettingsEmpty(self):
        return self.sectionSizeSettingsName == ''

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


class UserSubsQTableWidget(QTranslatable, AppQTableWidget):
    Headers = [
        UserSubsQTableWidgetHeaders('Remark', lambda item: item.get('remark', '')),
        UserSubsQTableWidgetHeaders('URL', lambda item: item.get('webURL', '')),
    ]

    def __init__(self, *args, **kwargs):
        self.deleteUniqueCallback = kwargs.pop('deleteUniqueCallback', None)

        super().__init__(*args, **kwargs)

        # Delegate
        self._delegate = AppQStyledItemDelegate(parent=self)
        self.setItemDelegate(self._delegate)

        # Must set before flush all
        self.setColumnCount(len(self.Headers))

        # Flush all data to table
        self.flushAll()

        # Install custom header
        self.setHorizontalHeader(
            UserSubsQTableWidgetHorizontalHeader(
                parent=self,
                sectionSizeSettingsName='SubscriptionWidgetSectionSizeTable',
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
                parent=self,
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
        keyMap = ['remark', 'webURL']

        AS_UserSubscription()[unique][keyMap[item.column()]] = item.text()

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        mbox = QuestionDeleteMBox(icon=AppQMessageBox.Icon.Question)
        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = self.item(indexes[0], 0).text()
        mbox.setText(mbox.customText())

        if mbox.exec() == PySide6LegacyEnumValueWrapper(
            AppQMessageBox.StandardButton.No
        ):
            # Do not delete
            return

        for i in range(len(indexes)):
            deleteIndex = indexes[i] - i
            deleteUnique = list(AS_UserSubscription().keys())[deleteIndex]

            self.removeRow(deleteIndex)

            AS_UserSubscription().pop(deleteUnique)

            if callable(self.deleteUniqueCallback):
                self.deleteUniqueCallback(deleteUnique)

    def flushItem(self, row, column, item):
        header = self.Headers[column]

        oldItem = self.item(row, column)
        newItem = QTableWidgetItem(header(item))

        if oldItem is None:
            # Item does not exists
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
        unique = kwargs.pop('unique', '')
        remark = kwargs.pop('remark', '')
        webURL = kwargs.pop('webURL', '')

        subs = {
            unique: {
                'remark': remark,
                'webURL': webURL,
            }
        }

        AS_UserSubscription().update(subs)

        row = self.rowCount()

        self.insertRow(row)
        self.flushRow(row, subs[unique])

    def retranslate(self):
        self.setHorizontalHeaderLabels(list(_(header) for header in self.Headers))
