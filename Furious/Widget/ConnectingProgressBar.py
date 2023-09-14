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

from Furious.Utility.Constants import APPLICATION_NAME, Color
from Furious.Utility.Utility import (
    bootstrapIcon,
    StateContext,
    SupportConnectedCallback,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QWidget


class ConnectingProgressBar(Translatable, SupportConnectedCallback, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
        self.setFixedSize(280, 61)

        @QtCore.Slot()
        def updateProgressBar():
            # Update the progress bar value
            if self.progressBar.value() < 90:
                self.progressBar.setValue(self.progressBar.value() + 1)

            # Stop the timer when the progress bar reaches 100%
            if self.progressBar.value() >= 100:
                self.timer.stop()

        # Create a progress bar widget
        self.progressBar = QProgressBar(self)
        self.progressBar.setRange(0, 100)
        self.progressBar.setStyleSheet(self.getStyleSheet(Color.LIGHT_BLUE))

        # create a timer to update the progress bar
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(updateProgressBar)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.progressBar)

        self.setLayout(self.layout)

    @staticmethod
    def getStyleSheet(color):
        return (
            f'QProgressBar {{'
            f'    border-radius: 2px;'
            f'    text-align: center;'
            f'}}'
            f''
            f'QProgressBar::chunk {{'
            f'    background-color: {color};'
            f'    width: 10px;'
            f'    margin: 0.5px;'
            f'}}'
        )

    def closeEvent(self, event):
        event.ignore()

        self.hide()

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
        self.progressBar.setStyleSheet(self.getStyleSheet(Color.LIGHT_RED_))

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
        self.progressBar.setStyleSheet(self.getStyleSheet(Color.LIGHT_BLUE))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
