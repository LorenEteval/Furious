from Furious.Gui.Action import Action, Seperator
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import (
    StateContext,
    SupportConnectedCallback,
    NeedSyncSettings,
    bootstrapIcon,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTabWidget,
    QTextBrowser,
)


class HeaderView(SupportConnectedCallback, QHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSectionsClickable(True)

        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: #008AE1; }}'
        )

    def connectedCallback(self):
        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: #EB212E; }}'
        )

    def disconnectedCallback(self):
        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: #008AE1; }}'
        )


class ListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def selectedIndex(self):
        return sorted(list(set(index.row() for index in self.selectedIndexes())))


class MainWindow(Translatable, SupportConnectedCallback, NeedSyncSettings, QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def syncSettings(self):
        pass

    def closeEvent(self, event):
        event.ignore()

        # Sync partial
        self.syncSettings()
        self.hide()

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))


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
                if button.text().count('OK') > 0:
                    # &OK...
                    pass
                else:
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


class StyledItemDelegate(QStyledItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFont(QFont(APP().customFontName))

        return editor


class TableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def selectedIndex(self):
        return sorted(list(set(index.row() for index in self.selectedIndexes())))

    def setSelectionColor(self, color):
        self.setStyleSheet(f'QTableWidget {{ selection-background-color: {color}; }}')

    def activateItemByIndex(self, index, activate=True):
        if activate:
            for column in range(self.columnCount()):
                item = self.item(int(index), column)

                if item is None:
                    # Do nothing
                    continue

                font = item.font()
                font.setBold(True)

                item.setFont(font)

                if APP().tray is None:
                    # Initializing
                    item.setForeground(QColor('#008AE1'))
                else:
                    if APP().tray.ConnectAction.isConnected():
                        item.setForeground(QColor('#EB212E'))
                    else:
                        item.setForeground(QColor('#008AE1'))
        else:
            for column in range(self.columnCount()):
                item = self.item(int(index), column)

                if item is None:
                    # Do nothing
                    continue

                font = item.font()
                font.setBold(False)

                item.setFont(font)
                item.setForeground(QBrush())


class TabWidget(Translatable, QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for index in range(self.count()):
            self.setTabText(index, _(self.tabText(index)))


class ZoomablePlainTextEdit(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def getIndent(line):
        indent = ''

        for char in line:
            if char.isspace():
                indent += char
            else:
                break

        return indent

    def smartIndent(self, event):
        cursor = self.textCursor()
        indent = self.getIndent(cursor.block().text())

        # Do newline action
        super().keyPressEvent(event)

        # Add last line indent
        cursor.insertText(indent)

        self.setTextCursor(cursor)

    def keyPressEvent(self, event):
        if (
            event.key() == QtCore.Qt.Key.Key_Return
            or event.key() == QtCore.Qt.Key.Key_Enter
        ):
            self.smartIndent(event)
        else:
            super().keyPressEvent(event)

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
