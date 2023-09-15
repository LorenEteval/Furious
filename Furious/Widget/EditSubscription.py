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

from Furious.Widget.Widget import (
    Dialog,
    HeaderView,
    MainWindow,
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
    SubscriptionStorage,
    StateContext,
    SupportConnectedCallback,
    bootstrapIcon,
    moveToCenter,
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
        self.SubscriptionList = self.SubscriptionWidget.SubscriptionList

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

    def initTableFromData(self):
        for subscription in self.SubscriptionList:
            self.appendDataByColumn(
                lambda column: EditSubsTableWidget.HEADER_LABEL_GET_FUNC[column](
                    subscription
                )
            )

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing to do
            return

        self.questionDeleteBox.isMulti = bool(len(indexes) > 1)
        self.questionDeleteBox.possibleRemark = f'{self.item(indexes[0], 0).text()}'
        self.questionDeleteBox.setText(self.questionDeleteBox.getText())

        if self.questionDeleteBox.exec() == MessageBox.StandardButton.No.value:
            # Do not delete
            return

        for i in range(len(indexes)):
            takedRow = indexes[i] - i

            self.removeRow(takedRow)
            self.SubscriptionList.pop(takedRow)

            # TODO: Remove related server

        # Sync it
        SubscriptionStorage.sync()

    def appendDataByColumn(self, func):
        row = self.rowCount()

        self.insertRow(row)

        for column in range(self.columnCount()):
            item = QTableWidgetItem(func(column))

            item.setFont(QFont(APP().customFontName))
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            )

            self.setItem(row, column, item)

    def connectedCallback(self):
        self.setSelectionColor(Color.LIGHT_RED_)

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
            # Check model. Shallow copy
            self.SubscriptionList = self.StorageObj['model']
        except Exception:
            # Any non-exit exceptions

            self.StorageObj = SubscriptionStorage.init()
            # Shallow copy
            self.SubscriptionList = self.StorageObj['model']

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

        if choice == QDialog.DialogCode.Accepted.value:
            subscriptionRemark = self.addSubsDialog.subscriptionRemark()
            subscriptionWebURL = self.addSubsDialog.subscriptionWebURL()

            if subscriptionRemark:
                subscription = {
                    'remark': subscriptionRemark,
                    'webURL': subscriptionWebURL,
                    # Unique id. Used by display and deletion
                    'unique': str(uuid.uuid4()),
                }

                self.appendDataByColumn(
                    lambda column: EditSubsTableWidget.HEADER_LABEL_GET_FUNC[column](
                        subscription
                    )
                )

                self.SubscriptionList.append(subscription)

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
