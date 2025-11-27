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

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

__all__ = ['ConnectProgressBar']


class AutoUpdateProgressBar(Mixins.ConnectionAware, QProgressBar):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.setRange(0, 100)

        @QtCore.Slot()
        def update():
            # Update the progress bar value
            if self.value() < 90:
                self.setValue(self.value() + 1)

            # Stop the timer when the progress bar reaches 100%
            if self.value() > 99:
                self.timer.stop()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(update)

        self.setStyleSheet(self.getStyleSheet(AppHue.currentColor()))

    def start(self, msec: int):
        self.timer.start(msec)

    def stop(self):
        self.timer.stop()

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

    def disconnectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

    def connectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.connectedColor()))


class ConnectProgressBar(Mixins.QTranslatable, Mixins.ConnectionAware, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setWindowIcon(AppHue.currentWindowIcon())
        self.setFixedSize(280, 61)

        # Create a progress bar widget
        self._widget = AutoUpdateProgressBar(parent=self)
        self._widget.setRange(0, 100)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._widget)

        self.setLayout(self._layout)

    def setValue(self, value: int):
        self._widget.setValue(value)

    def start(self, msec: int):
        self._widget.start(msec)

    def stop(self):
        self._widget.stop()

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
