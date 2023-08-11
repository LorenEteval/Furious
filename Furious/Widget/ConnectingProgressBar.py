from Furious.Utility.Constants import APPLICATION_NAME, GOLDEN_RATIO
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
        self.setFixedSize(280, int(100 * GOLDEN_RATIO))

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
        self.progressBar.setStyleSheet(
            f'QProgressBar {{'
            f'    border-radius: 2px;'
            f'    text-align: center;'
            f'}}'
            f''
            f'QProgressBar::chunk {{'
            f'    background-color: #43ACED;'
            f'      width: 10px;'
            f'      margin: 0.5px;'
            f'}}'
        )

        # create a timer to update the progress bar
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(updateProgressBar)

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.progressBar)

        self.setLayout(self.layout)

    def closeEvent(self, event):
        event.ignore()

        self.hide()

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))

        self.progressBar.setStyleSheet(
            f'QProgressBar {{'
            f'    border-radius: 2px;'
            f'    text-align: center;'
            f'}}'
            f''
            f'QProgressBar::chunk {{'
            f'    background-color: #EB212E;'
            f'      width: 10px;'
            f'      margin: 0.5px;'
            f'}}'
        )

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.progressBar.setStyleSheet(
            f'QProgressBar {{'
            f'    border-radius: 2px;'
            f'    text-align: center;'
            f'}}'
            f''
            f'QProgressBar::chunk {{'
            f'    background-color: #43ACED;'
            f'      width: 10px;'
            f'      margin: 0.5px;'
            f'}}'
        )

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
