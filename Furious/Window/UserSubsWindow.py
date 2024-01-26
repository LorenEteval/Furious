from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *
from Furious.Widget.UserSubsQTableWidget import *

from PySide6 import QtWidgets
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

import uuid

__all__ = ['UserSubsWindow']

registerAppSettings('SubscriptionWidgetWindowSize')


class AddSubsDialog(AppQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Add subscription'))

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

    def subsRemark(self):
        return self.remarkEdit.text()

    def subsWebURL(self):
        return self.webURLEdit.text()

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))

        self.remarkText.setText(_(self.remarkText.text()))
        self.webURLText.setText(_(self.webURLText.text()))

        for button in self.dialogBtns.buttons():
            button.setText(_(button.text()))

        moveToCenter(self)


class UserSubsWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        callback = kwargs.pop('deleteUniqueCallback', None)

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Subscription'))

        self.addSubsDialog = AddSubsDialog()
        self.userSubsQTableWidget = UserSubsQTableWidget(deleteUniqueCallback=callback)

        self.userSubsTab = AppQTabWidget(self)
        self.userSubsTab.addTab(self.userSubsQTableWidget, _('Subscription List'))

        # Buttons
        self.addButton = AppQPushButton(_('Add'))
        self.addButton.clicked.connect(lambda: self.addSubs())
        self.deleteButton = AppQPushButton(_('Delete'))
        self.deleteButton.clicked.connect(lambda: self.deleteSelectedItem())

        # Button Layout
        self.buttonWidget = QWidget()
        self.buttonWidgetLayout = QGridLayout(parent=self.buttonWidget)
        self.buttonWidgetLayout.addWidget(self.addButton, 0, 0)
        self.buttonWidgetLayout.addWidget(self.deleteButton, 0, 1)

        self.fakeCentralWidget = QWidget()
        self.fakeCentralWidgetLayout = QVBoxLayout(self.fakeCentralWidget)
        self.fakeCentralWidgetLayout.addWidget(self.userSubsTab)
        self.fakeCentralWidgetLayout.addWidget(self.buttonWidget)

        self.setCentralWidget(self.fakeCentralWidget)

    def setWidthAndHeight(self):
        try:
            windowSize = AppSettings.get('SubscriptionWidgetWindowSize').split(',')

            self.setGeometry(100, 100, *list(int(size) for size in windowSize))
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 360 * GOLDEN_RATIO, 360)

    def addSubs(self):
        choice = self.addSubsDialog.exec()

        if choice == PySide6LegacyEnumValueWrapper(QDialog.DialogCode.Accepted):
            remark = self.addSubsDialog.subsRemark()
            webURL = self.addSubsDialog.subsWebURL()

            if remark:
                # Unique id. Used by display and deletion
                unique = str(uuid.uuid4())

                self.userSubsQTableWidget.appendNewItem(
                    unique=unique, remark=remark, webURL=webURL
                )
        else:
            # Do nothing
            pass

    def deleteSelectedItem(self):
        self.userSubsQTableWidget.deleteSelectedItem()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)

    def cleanup(self):
        AppSettings.set(
            'SubscriptionWidgetWindowSize',
            f'{self.geometry().width()},{self.geometry().height()}',
        )
