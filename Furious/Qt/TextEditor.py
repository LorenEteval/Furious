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

"""Provide Qt support for text editor."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.TextEditorTheme import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Callable

import functools

__all__ = [
    'AppQPlainTextEdit',
    'AppQTextBrowser',
    'DraculaTextEditor',
    'DraculaJSONTextEditor',
    'DraculaTextBrowser',
]


class SupportPointSizeSettings(Mixins.CleanupOnExit):
    """Store and validate support point size settings."""
    def pointSizeSettingsEmpty(self):
        """Return the point size settings empty value used by the support point size settings."""
        return self.pointSizeSettingsName == ''

    def __init__(self, *args, **kwargs):
        """Initialize the SupportPointSizeSettings."""
        self.pointSizeSettingsName = kwargs.pop('pointSizeSettingsName', '')

        super().__init__(*args, **kwargs)

        self.uniqueCleanup = False

        self.restorePointSize()

    def restorePointSize(self):
        """Restore point size."""
        raise NotImplementedError

    def cleanup(self):
        """Release resources owned by the support point size settings."""
        raise NotImplementedError


class AppQPlainTextEdit(SupportPointSizeSettings, QPlainTextEdit):
    """Represent app q plain text edit."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQPlainTextEdit."""
        super().__init__(*args, **kwargs)

    def restorePointSize(self):
        """Restore point size."""
        if self.pointSizeSettingsEmpty():
            return

        try:
            # Restore point size
            font = self.font()
            font.setPointSize(int(AppSettings.get(self.pointSizeSettingsName)))

            self.setFont(font)
        except Exception:
            # Any non-exit exceptions

            pass

    @staticmethod
    @functools.lru_cache(128)
    def getIndent(line):
        """Return indent."""
        indent = ''

        for char in line:
            if char.isspace():
                indent += char
            else:
                break

        return indent

    def getPrevAndNextChar(self, cursor):
        """Return prev and next char."""
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
        """Handle smart indent for the app q plain text edit."""
        cursor = self.textCursor()
        indent = self.getIndent(cursor.block().text())

        # Do newline action
        super().keyPressEvent(event)

        # Add last line indent
        cursor.insertText(indent)

        self.setTextCursor(cursor)

    def smartSymbolPair(self, event, pair):
        """Handle smart symbol pair for the app q plain text edit."""
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
        """Handle smart backspace for the app q plain text edit."""
        cursor = self.textCursor()
        chPair = self.getPrevAndNextChar(cursor)

        if chPair == '""' or chPair == '{}' or chPair == '[]':
            cursor.deleteChar()
            cursor.deletePreviousChar()
        else:
            super().keyPressEvent(event)

    def hideTabAndSpaces(self):
        """Hide tab and spaces."""
        textOption = QTextOption()

        self.document().setDefaultTextOption(textOption)
        # Reset. Set
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def showTabAndSpaces(self):
        """Show tab and spaces."""
        textOption = QTextOption()
        textOption.setFlags(QTextOption.Flag.ShowTabsAndSpaces)

        self.document().setDefaultTextOption(textOption)
        # Reset. Set
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def keyPressEvent(self, event):
        """Handle a key press for the app q plain text edit."""
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
        """Handle the wheel event."""
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoomIn()
            if delta < 0:
                self.zoomOut()
        else:
            super().wheelEvent(event)

    def cleanup(self):
        """Release resources owned by the app q plain text edit."""
        if self.pointSizeSettingsEmpty():
            return

        AppSettings.set(self.pointSizeSettingsName, str(self.font().pointSize()))


class AppQTextBrowser(SupportPointSizeSettings, QTextBrowser):
    """Represent app q text browser."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQTextBrowser."""
        super().__init__(*args, **kwargs)

    def appendLine(self, line: str):
        """Append line."""
        hScrollBar = self.horizontalScrollBar()
        vScrollBar = self.verticalScrollBar()
        scrollEnds = vScrollBar.maximum() - vScrollBar.value() <= 10

        # Fix insertPlainText bug if user cursor is present
        self.append(line.rstrip())

        if scrollEnds:
            vScrollBar.setValue(vScrollBar.maximum())  # Scrolls to the bottom
            hScrollBar.setValue(0)  # scroll to the left

    def restorePointSize(self):
        """Restore point size."""
        if self.pointSizeSettingsEmpty():
            return

        try:
            # Restore point size
            font = self.font()
            font.setPointSize(int(AppSettings.get(self.pointSizeSettingsName)))

            self.setFont(font)
        except Exception:
            # Any non-exit exceptions

            pass

    def wheelEvent(self, event):
        """Handle the wheel event."""
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoomIn()
            if delta < 0:
                self.zoomOut()
        else:
            super().wheelEvent(event)

    def cleanup(self):
        """Release resources owned by the app q text browser."""
        if self.pointSizeSettingsEmpty():
            return

        AppSettings.set(self.pointSizeSettingsName, str(self.font().pointSize()))


class DraculaTextEditor(AppQPlainTextEdit):
    """Represent dracula text editor."""
    def __init__(self, *args, **kwargs):
        """Initialize the DraculaTextEditor."""
        fontFamily = kwargs.pop('fontFamily', '')

        super().__init__(*args, **kwargs)

        self._modificationChangedCb = None
        self._cursorPositionChangedCb = None

        # Theme
        self.setStyleSheet(
            DraculaEditorTheme.getStyleSheet(
                widgetName='QPlainTextEdit', fontFamily=fontFamily
            )
        )

        @QtCore.Slot(bool)
        def handleModificationChanged(changed):
            """Handle modification changed."""
            if changed:
                self.document().setModified(False)

                if callable(self._modificationChangedCb):
                    self._modificationChangedCb()

        @QtCore.Slot()
        def handleCursorPositionChanged():
            """Handle cursor position changed."""
            if callable(self._cursorPositionChangedCb):
                self._cursorPositionChangedCb(self.textCursor())

        self.modificationChanged.connect(handleModificationChanged)
        self.cursorPositionChanged.connect(handleCursorPositionChanged)

    def registerCursorPositionChangedCb(self, callback: Callable[[QTextCursor], None]):
        """Handle register cursor position changed cb for the dracula text editor."""
        self._cursorPositionChangedCb = callback

    def registerModificationChangedCb(self, callback: Callable[[], None]):
        """Handle register modification changed cb for the dracula text editor."""
        self._modificationChangedCb = callback


class DraculaJSONTextEditor(DraculaTextEditor):
    """Represent dracula JSON text editor."""
    def __init__(self, *args, **kwargs):
        """Initialize the DraculaJSONTextEditor."""
        super().__init__(*args, **kwargs)

        self._syntaxHighlighter = DraculaJSONSyntaxHighlighter(self.document())


class DraculaTextBrowser(AppQTextBrowser):
    """Represent dracula text browser."""
    def __init__(self, *args, **kwargs):
        """Initialize the DraculaTextBrowser."""
        fontFamily = kwargs.pop('fontFamily', '')

        super().__init__(*args, **kwargs)

        self._syntaxHighlighter = DraculaLoggerSyntaxHighlighter(self.document())

        # Theme
        self.setStyleSheet(
            DraculaEditorTheme.getStyleSheet(
                widgetName='QTextBrowser', fontFamily=fontFamily
            )
        )
