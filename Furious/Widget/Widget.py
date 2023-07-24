from Furious.Gui.Action import Action, Seperator
from Furious.Utility.Utility import (
    StateContext,
    SupportConnectedCallback,
    bootstrapIcon,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextBrowser,
)


class Menu(Translatable, QMenu):
    def __init__(self, *actions, **kwargs):
        super().__init__(**kwargs)

        for action in actions:
            if isinstance(action, Seperator):
                self.addSeparator()
            else:
                assert isinstance(action, Action)

                self.addAction(action)

        self.setStyleSheet(
            f'QMenu::item {{'
            f'    background-color: solid;'
            f'}}'
            f''
            f'QMenu::item:selected {{'
            f'    background-color: #43ACED;'
            f'}}'
        )

    def retranslate(self):
        with StateContext(self):
            self.setTitle(_(self.title()))


class MessageBox(Translatable, SupportConnectedCallback, QMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

    def moveToCenter(self):
        moveToCenter(self, self.parentWidget())

        return self

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(_(self.text()))

            try:
                self.setInformativeText(_(self.informativeText()))
            except KeyError:
                # Any translatable informative text
                pass

            for button in self.buttons():
                button.setText(_(button.text()))

            self.moveToCenter()

    def exec(self):
        self.show()
        self.moveToCenter()

        return super().exec()

    def open(self):
        self.show()
        self.moveToCenter()

        return super().open()


class PushButton(Translatable, QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class TabWidget(Translatable, QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for i in range(self.tabBar().count()):
            self.tabBar().setTabText(i, _(self.tabBar().tabText(i)))


class ZoomablePlainTextEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoomIn()
            if delta < 0:
                self.zoomOut()
        else:
            super().wheelEvent(event)


class ZoomableTextBrowser(QTextBrowser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoomIn()
            if delta < 0:
                self.zoomOut()
        else:
            super().wheelEvent(event)
