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

from Furious.Gui.Action import Action, Seperator
from Furious.Utility.Constants import APP, PLATFORM, Color
from Furious.Utility.Utility import (
    StateContext,
    SupportConnectedCallback,
    NeedSyncSettings,
    bootstrapIcon,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QBrush, QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTabWidget,
    QTextBrowser,
)

import functools


class Dialog(Translatable, SupportConnectedCallback, QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

    def setWidthAndHeight(self):
        pass

    def exec(self):
        self.show()

        return super().exec()

    def open(self):
        self.show()

        return super().open()

    def show(self):
        super().show()

        if PLATFORM == 'Darwin':
            self.setWidthAndHeight()

        moveToCenter(self)

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

    def retranslate(self):
        pass


class GroupBox(Translatable, QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        with StateContext(self):
            self.setTitle(_(self.title()))


class HeaderView(SupportConnectedCallback, QHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSectionsClickable(True)

        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: {Color.LIGHT_BLUE}; }}'
        )

    def connectedCallback(self):
        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: {Color.LIGHT_RED_}; }}'
        )

    def disconnectedCallback(self):
        self.setStyleSheet(
            f'QHeaderView::section:hover {{ background-color: {Color.LIGHT_BLUE}; }}'
        )


class Label(Translatable, QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        with StateContext(self):
            self.setText(_(self.text()))


class ListWidget(SupportConnectedCallback, QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSelectionColor(Color.LIGHT_BLUE)

    def setSelectionColor(self, color):
        self.setStyleSheet(
            f'QListWidget::item:selected {{'
            f'    background: {color};'
            f'}}'
            f''
            f'QListWidget::item:hover {{'
            f'    background: {color};'
            f'}}'
        )

    @property
    def selectedIndex(self):
        return sorted(list(set(index.row() for index in self.selectedIndexes())))

    def connectedCallback(self):
        self.setSelectionColor(Color.LIGHT_RED_)

    def disconnectedCallback(self):
        self.setSelectionColor(Color.LIGHT_BLUE)


class MainWindow(Translatable, SupportConnectedCallback, NeedSyncSettings, QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._menuBar = MenuBar(parent=self)
        self.setMenuBar(self._menuBar)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

    def syncSettings(self):
        pass

    def setWidthAndHeight(self):
        pass

    def show(self):
        super().show()

        if PLATFORM == 'Darwin':
            APP().processEvents()

            self.setWidthAndHeight()

        moveToCenter(self)

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


class Menu(Translatable, SupportConnectedCallback, QMenu):
    def __init__(self, *actions, **kwargs):
        super().__init__(**kwargs)

        for action in actions:
            if isinstance(action, Seperator):
                self.addSeparator()
            elif isinstance(action, Action):
                self.addAction(action)
            else:
                # Do nothing
                pass

        if APP().isConnected():
            self.setStyleSheet(self.getStyleSheet(Color.LIGHT_RED_))
        else:
            self.setStyleSheet(self.getStyleSheet(Color.LIGHT_BLUE))

    @staticmethod
    def getStyleSheet(color):
        return (
            f'QMenu::item {{'
            f'    background-color: solid;'
            f'}}'
            f''
            f'QMenu::item:selected {{'
            f'    background-color: {color};'
            f'}}'
        )

    def connectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(Color.LIGHT_RED_))

    def disconnectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(Color.LIGHT_BLUE))

    def retranslate(self):
        with StateContext(self):
            self.setTitle(_(self.title()))


class MenuBar(SupportConnectedCallback, QMenuBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if APP().isConnected():
            self.setSelectionColor(Color.LIGHT_RED_)
        else:
            self.setSelectionColor(Color.LIGHT_BLUE)

    def setSelectionColor(self, color):
        self.setStyleSheet(
            f'QMenuBar::item:selected {{'
            f'    background: {color};'
            f'}}'
            f''
            f'QMenuBar::item:hover {{'
            f'    background: {color};'
            f'}}'
        )

    def connectedCallback(self):
        self.setSelectionColor(Color.LIGHT_RED_)

    def disconnectedCallback(self):
        self.setSelectionColor(Color.LIGHT_BLUE)


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

        self.setWordWrap(False)

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

                if APP().isConnected():
                    item.setForeground(QColor(Color.LIGHT_RED_))
                else:
                    item.setForeground(QColor(Color.LIGHT_BLUE))
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
    @functools.lru_cache(128)
    def getIndent(line):
        indent = ''

        for char in line:
            if char.isspace():
                indent += char
            else:
                break

        return indent

    def getPrevAndNextChar(self, cursor):
        plainText = self.toPlainText()

        cursor.movePosition(QTextCursor.MoveOperation.Left)

        try:
            prevChar = plainText[cursor.position()]
        except Exception:
            # Any non-exit exceptions

            prevChar = ''

        # Move the cursor to the next character position
        cursor.movePosition(QTextCursor.MoveOperation.Right)

        try:
            nextChar = plainText[cursor.position()]
        except Exception:
            # Any non-exit exceptions

            nextChar = ''

        return prevChar + nextChar

    def smartIndent(self, event):
        cursor = self.textCursor()
        indent = self.getIndent(cursor.block().text())

        # Do newline action
        super().keyPressEvent(event)

        # Add last line indent
        cursor.insertText(indent)

        self.setTextCursor(cursor)

    def smartSymbolPair(self, event, pair):
        plainText = self.toPlainText()

        cursor = self.textCursor()

        if (
            cursor.position() < len(plainText)
            and plainText[cursor.position()] == pair[0]
        ):
            # Do pair0 action
            super().keyPressEvent(event)
        else:
            # Do pair0 action
            super().keyPressEvent(event)

            # Do pair1 action
            cursor.insertText(pair[1])
            # Move to middle
            cursor.movePosition(QTextCursor.MoveOperation.Left)

            self.setTextCursor(cursor)

    def smartBackspace(self, event):
        cursor = self.textCursor()
        chPair = self.getPrevAndNextChar(cursor)

        if chPair == '""' or chPair == '{}' or chPair == '[]':
            cursor.deleteChar()
            cursor.deletePreviousChar()
        else:
            super().keyPressEvent(event)

    def keyPressEvent(self, event):
        if (
            event.key() == QtCore.Qt.Key.Key_Return
            or event.key() == QtCore.Qt.Key.Key_Enter
        ):
            self.smartIndent(event)
        elif event.key() == QtCore.Qt.Key.Key_Backspace:
            self.smartBackspace(event)
        elif event.key() == QtCore.Qt.Key.Key_QuoteDbl:
            self.smartSymbolPair(event, '""')
        elif event.key() == QtCore.Qt.Key.Key_BraceLeft:
            self.smartSymbolPair(event, '{}')
        elif event.key() == QtCore.Qt.Key.Key_BracketLeft:
            self.smartSymbolPair(event, '[]')
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
