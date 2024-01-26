from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtWidgets import QHBoxLayout, QProgressBar, QWidget

__all__ = ['ConnectProgressBar']


class ConnectProgressBar(QTranslatable, SupportConnectedCallback, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setWindowIcon(AppHue.currentWindowIcon())
        self.setFixedSize(280, 61)

        @QtCore.Slot()
        def updateProgressBar():
            # Update the progress bar value
            if self._progressBar.value() < 90:
                self._progressBar.setValue(self._progressBar.value() + 1)

            # Stop the timer when the progress bar reaches 100%
            if self._progressBar.value() >= 100:
                self._timer.stop()

        # Create a progress bar widget
        self._progressBar = QProgressBar(self)
        self._progressBar.setRange(0, 100)
        self._progressBar.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

        # Create a timer to update the progress bar
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(updateProgressBar)

        self._layout = QHBoxLayout()
        self._layout.addWidget(self._progressBar)

        self.setLayout(self._layout)

    def setValue(self, value: int):
        self._progressBar.setValue(value)

    def start(self, msec: int):
        self._timer.start(msec)

    def stop(self):
        self._timer.stop()

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

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())
        self._progressBar.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())
        self._progressBar.setStyleSheet(self.getStyleSheet(AppHue.connectedColor()))

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
