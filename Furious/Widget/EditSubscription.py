# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Gui.Action import Action
from Furious.Widget.Widget import (
    Dialog,
    HeaderView,
    MainWindow,
    Menu,
    MessageBox,
    PushButton,
    StyledItemDelegate,
    TableWidget,
    TabWidget,
)
from Furious.Widget.EditConfiguration import QuestionDeleteBox
from Furious.Utility.Constants import (
    APP,
    PLATFORM,
    GOLDEN_RATIO,
    Color,
)
from Furious.Utility.Utility import (
    ServerStorage,
    SubscriptionStorage,
    StateContext,
    SupportConnectedCallback,
    bootstrapIcon,
    enumValueWrapper,
    moveToCenter,
    getConnectedColor,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import uuid
import ujson
import logging

logger = logging.getLogger(__name__)


class EditSubsHorizontalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

        self.sectionResized.connect(self.handleSectionResized)

    @QtCore.Slot(int, int, int)
    def handleSectionResized(self, index, oldSize, newSize):
        # Keys are string when loaded from json
        self.parent().sectionSizeTable[str(index)] = newSize


class EditSubsVerticalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class EditSubsTableWidget(Translatable, SupportConnectedCallback, TableWidget):
    # Might be extended in the future
    HEADER_LABEL = [
        'Remark',
        'URL',
    ]

    # Corresponds to header label
    HEADER_LABEL_GET_FUNC = [
        lambda subscription: subscription['remark'],
        lambda subscription: subscription['webURL'],
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.SubscriptionWidget = kwargs.get('parent')

        self.questionDeleteBox = QuestionDeleteBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )

        # Handy reference
        self.SubscriptionDict = self.SubscriptionWidget.SubscriptionDict

        # Column count
        self.setColumnCount(len(EditSubsTableWidget.HEADER_LABEL))

        # Delegate
        self.delegate = StyledItemDelegate(parent=self)
        self.setItemDelegate(self.delegate)

        # Install custom header
        self.setHorizontalHeader(EditSubsHorizontalHeader(self))

        self.initTableFromData()

        # Horizontal header resize mode
        for index in range(self.columnCount()):
            if index < self.columnCount() - 1:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Interactive
                )
            else:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Stretch
                )

        try:
            # Restore horizontal section size
            self.sectionSizeTable = ujson.loads(
                APP().SubscriptionWidgetSectionSizeTable
            )

            # Fill missing value
            for column in range(self.columnCount()):
                if self.sectionSizeTable.get(str(column)) is None:
                    self.sectionSizeTable[
                        str(column)
                    ] = self.horizontalHeader().defaultSectionSize()

            # Block resize callback
            self.horizontalHeader().blockSignals(True)

            for key, value in self.sectionSizeTable.items():
                self.horizontalHeader().resizeSection(int(key), value)

            # Unblock resize callback
            self.horizontalHeader().blockSignals(False)
        except Exception:
            # Any non-exit exceptions

            # Leave keys as strings since they will be
            # loaded as string from json
            self.sectionSizeTable = {
                str(row): self.horizontalHeader().defaultSectionSize()
                for row in range(self.columnCount())
            }

        self.setHorizontalHeaderLabels(
            list(_(label) for label in EditSubsTableWidget.HEADER_LABEL)
        )

        for column in range(self.horizontalHeader().count()):
            self.horizontalHeaderItem(column).setFont(QFont(APP().customFontName))

        # Install custom header
        self.setVerticalHeader(EditSubsVerticalHeader(self))

        # Selection
        self.setSelectionColor(Color.LIGHT_BLUE)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        contextMenuActions = [
            Action(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
                parent=self,
            ),
        ]

        self.contextMenu = Menu(*contextMenuActions)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Signals
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)
        self.itemChanged.connect(self.handleItemChanged)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemChanged(self, item):
        unique = self.getUniqueByIndex(item.row())

        keyMap = ['remark', 'webURL']

        if self.SubscriptionDict[unique][keyMap[item.column()]] != item.text():
            # Modified. Update value
            self.SubscriptionDict[unique][keyMap[item.column()]] = item.text()

            # Sync it
            SubscriptionStorage.sync()

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def getUniqueByIndex(self, index):
        return list(self.SubscriptionDict.keys())[index]

    def initTableFromData(self):
        for key, value in self.SubscriptionDict.items():
            self.appendDataByColumn(
                lambda column: EditSubsTableWidget.HEADER_LABEL_GET_FUNC[column](value)
            )

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        if APP().ServerWidget is not None and APP().ServerWidget.modified:
            APP().ServerWidget.saveChangeFirst.exec()

            return

        self.questionDeleteBox.isMulti = bool(len(indexes) > 1)
        self.questionDeleteBox.possibleRemark = self.item(indexes[0], 0).text()
        self.questionDeleteBox.setText(self.questionDeleteBox.getText())

        if self.questionDeleteBox.exec() == enumValueWrapper(
            MessageBox.StandardButton.No
        ):
            # Do not delete
            return

        deleted = 0

        for i in range(len(indexes)):
            takedRow = indexes[i] - i
            takedUnique = self.getUniqueByIndex(takedRow)

            self.removeRow(takedRow)
            self.SubscriptionDict.pop(takedUnique)

            deleted += APP().ServerWidget.deleteItemByUnique(
                takedUnique, syncStorage=False
            )

        if deleted:
            # At least on server has been deleted. Sync it
            ServerStorage.sync()

        # Sync it
        SubscriptionStorage.sync()

    def appendDataByColumn(self, func):
        row = self.rowCount()

        self.insertRow(row)

        for column in range(self.columnCount()):
            item = QTableWidgetItem(func(column))

            item.setFont(QFont(APP().customFontName))
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled
                | QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsEditable
            )

            self.setItem(row, column, item)

    def connectedCallback(self):
        self.setSelectionColor(getConnectedColor())

    def disconnectedCallback(self):
        self.setSelectionColor(Color.LIGHT_BLUE)

    def retranslate(self):
        self.setHorizontalHeaderLabels(
            list(_(label) for label in EditSubsTableWidget.HEADER_LABEL)
        )


class AddSubsDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Add subscription'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.remarkText = QLabel(_('Enter subscription remark:'))
        self.remarkEdit = QLineEdit()

        self.webURLText = QLabel(_('Enter subscription URL:'))
        self.webURLEdit = QLineEdit()

        self.dialogBtns = QDialogButtonBox(QtCore.Qt.Orientation.Horizontal)

        self.dialogBtns.addButton(_('OK'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(_('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()

        layout.addRow(self.remarkText)
        layout.addRow(self.remarkEdit)
        layout.addRow(self.webURLText)
        layout.addRow(self.webURLEdit)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.setGeometry(100, 100, 456, 150)

    def subscriptionRemark(self):
        return self.remarkEdit.text()

    def subscriptionWebURL(self):
        return self.webURLEdit.text()

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))

            self.remarkText.setText(_(self.remarkText.text()))
            self.webURLText.setText(_(self.webURLText.text()))

            for button in self.dialogBtns.buttons():
                button.setText(_(button.text()))

            moveToCenter(self)


class EditSubscriptionWidget(MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Subscription'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.addSubsDialog = AddSubsDialog()

        try:
            self.StorageObj = SubscriptionStorage.toObject(APP().CustomSubscription)
            # Shallow copy
            self.SubscriptionDict = self.StorageObj
        except Exception:
            # Any non-exit exceptions

            self.StorageObj = SubscriptionStorage.init()
            # Shallow copy
            self.SubscriptionDict = self.StorageObj

            # Clear it
            SubscriptionStorage.clear()

        self.editSubsTableWidget = EditSubsTableWidget(parent=self)

        self.editorTab = TabWidget(self)
        self.editorTab.addTab(self.editSubsTableWidget, _('Subscription List'))

        # Buttons
        self.addButton = PushButton(_('Add'))
        self.addButton.clicked.connect(lambda: self.addSubscription())
        self.deleteButton = PushButton(_('Delete'))
        self.deleteButton.clicked.connect(lambda: self.deleteSelectedItem())

        # Button Layout
        self.buttonWidget = QWidget()
        self.buttonWidgetLayout = QGridLayout(parent=self.buttonWidget)
        self.buttonWidgetLayout.addWidget(self.addButton, 0, 0)
        self.buttonWidgetLayout.addWidget(self.deleteButton, 0, 1)

        self.fakeCentralWidget = QWidget()
        self.fakeCentralWidgetLayout = QVBoxLayout(self.fakeCentralWidget)
        self.fakeCentralWidgetLayout.addWidget(self.editorTab)
        self.fakeCentralWidgetLayout.addWidget(self.buttonWidget)

        self.setCentralWidget(self.fakeCentralWidget)

    def setWidthAndHeight(self):
        try:
            self.setGeometry(
                100,
                100,
                *list(
                    int(size) for size in APP().SubscriptionWidgetWindowSize.split(',')
                ),
            )
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 360 * GOLDEN_RATIO, 360)

    def addSubscription(self):
        choice = self.addSubsDialog.exec()

        if choice == enumValueWrapper(QDialog.DialogCode.Accepted):
            subscriptionRemark = self.addSubsDialog.subscriptionRemark()
            subscriptionWebURL = self.addSubsDialog.subscriptionWebURL()

            if subscriptionRemark:
                # Unique id. Used by display and deletion
                unique = str(uuid.uuid4())

                subscription = {
                    unique: {
                        'remark': subscriptionRemark,
                        'webURL': subscriptionWebURL,
                    }
                }

                self.SubscriptionDict.update(subscription)

                self.appendDataByColumn(
                    lambda column: EditSubsTableWidget.HEADER_LABEL_GET_FUNC[column](
                        subscription[unique]
                    )
                )

                # Sync it
                SubscriptionStorage.sync()
        else:
            # Do nothing
            pass

    def appendDataByColumn(self, func):
        self.editSubsTableWidget.appendDataByColumn(func)

    def deleteSelectedItem(self):
        self.editSubsTableWidget.deleteSelectedItem()

    def syncSettings(self):
        APP().SubscriptionWidgetWindowSize = (
            f'{self.geometry().width()},{self.geometry().height()}'
        )

        APP().SubscriptionWidgetSectionSizeTable = ujson.dumps(
            self.editSubsTableWidget.sectionSizeTable,
            ensure_ascii=False,
            escape_forward_slashes=False,
        )

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)
