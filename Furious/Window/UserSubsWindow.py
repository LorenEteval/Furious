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

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Widget.UserSubsQTableWidget import *

from PySide6 import QtCore
from PySide6.QtWidgets import *

import uuid
import functools

__all__ = ['UserSubsWindow']

# Migrate legacy settings
registerAppSettings('SubscriptionWidgetWindowSize')
registerAppSettings('UserSubsWindowGeometry')
registerAppSettings('UserSubsWindowState')


class AddSubsDialog(AppQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Add Subscription'))

        self.remarkText = AppQLabel(_('Enter subscription remark:'))
        self.remarkEdit = QLineEdit()

        self.webURLText = AppQLabel(_('Enter subscription URL:'))
        self.webURLEdit = QLineEdit()

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
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
        self.resize(456, 150)

    def subsRemark(self):
        return self.remarkEdit.text()

    def subsWebURL(self):
        return self.webURLEdit.text()


class UserSubsWindow(AppQMainWindow):
    DEFAULT_WINDOW_SIZE = QtCore.QSize(1120, 600)

    def __init__(self, *args, **kwargs):
        callback = kwargs.pop('deleteUniqueCallback', None)

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Subscription'))

        self.userSubsQTableWidget = UserSubsQTableWidget(
            deleteUniqueCallback=callback, parent=self
        )

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

    def addSubs(self):
        def handleResultCode(_addSubsDialog, code):
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                remark = _addSubsDialog.subsRemark()
                webURL = _addSubsDialog.subsWebURL()

                if remark:
                    # Unique id. Used by display and deletion
                    unique = str(uuid.uuid4())

                    self.userSubsQTableWidget.appendNewItem(
                        unique=unique, remark=remark, webURL=webURL
                    )
            else:
                # Do nothing
                pass

        addSubsDialog = AddSubsDialog(parent=self)
        addSubsDialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        addSubsDialog.finished.connect(
            functools.partial(handleResultCode, addSubsDialog)
        )

        # Show the MessageBox asynchronously
        addSubsDialog.open()

    def deleteSelectedItem(self):
        self.userSubsQTableWidget.deleteSelectedItem()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)

    def setWidthAndHeight(self):
        if AppSettings.get('UserSubsWindowGeometry') is None:
            # Migrate legacy settings
            try:
                windowSize = AppSettings.get('SubscriptionWidgetWindowSize').split(',')

                width, height = tuple(int(size) for size in windowSize)

                if (width, height) == (640, 480):
                    self.resize(UserSubsWindow.DEFAULT_WINDOW_SIZE)
                else:
                    self.resize(width, height)
            except Exception:
                # Any non-exit exceptions

                self.resize(UserSubsWindow.DEFAULT_WINDOW_SIZE)
        else:
            if PLATFORM == 'Darwin':
                self.resize(UserSubsWindow.DEFAULT_WINDOW_SIZE)
            else:
                try:
                    self.restoreGeometry(AppSettings.get('UserSubsWindowGeometry'))
                except Exception:
                    # Any non-exit exceptions

                    self.resize(UserSubsWindow.DEFAULT_WINDOW_SIZE)

                try:
                    self.restoreState(AppSettings.get('UserSubsWindowState'))
                except Exception:
                    # Any non-exit exceptions

                    pass

    def cleanup(self):
        AppSettings.set('UserSubsWindowGeometry', self.saveGeometry())
        AppSettings.set('UserSubsWindowState', self.saveState())
