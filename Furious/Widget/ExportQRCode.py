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

from Furious.Widget.Widget import MainWindow
from Furious.Utility.Constants import APPLICATION_NAME
from Furious.Utility.Utility import SupportConnectedCallback, bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QTabWidget

import io
import pyqrcode


class ExportQRCode(MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.labelList = []

        self.editorTab = QTabWidget(self)
        self.editorTab.setTabsClosable(True)
        self.editorTab.tabCloseRequested.connect(self.handleTabCloseRequested)

        self.setCentralWidget(self.editorTab)

    def initTabWithData(self, data):
        for text, link in data:
            qrdata = io.BytesIO()

            qrcode = pyqrcode.create(link)
            qrcode.png(qrdata, scale=5)

            pixmap = QPixmap()
            pixmap.loadFromData(qrdata.getvalue(), 'PNG')

            label = QLabel(parent=self.editorTab)
            label.setPixmap(pixmap)

            self.labelList.append(label)
            self.editorTab.addTab(label, text)

    @QtCore.Slot(int)
    def handleTabCloseRequested(self, index):
        self.editorTab.removeTab(index)

        if self.editorTab.count() == 0:
            self.hide()
