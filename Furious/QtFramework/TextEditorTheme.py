# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from PySide6 import QtCore
from PySide6.QtGui import *

__all__ = ['DraculaEditorTheme', 'DraculaJSONSyntaxHighlighter']


class EditorHighlightRules:
    def __init__(self, regex, color, isBold=False, isJSONKey=False):
        self.regex = QtCore.QRegularExpression(regex)
        self.color = QColor(color)

        self.rules = QTextCharFormat()
        self.rules.setForeground(self.color)

        if isBold:
            self.rules.setFontWeight(QFont.Weight.Bold)

        self.isJSONKey = isJSONKey


class EditorTheme:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def getStyleSheet(*args, **kwargs):
        raise NotImplementedError


class DraculaEditorTheme(EditorTheme):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def getStyleSheet(widgetName, fontFamily):
        return (
            f'{widgetName} {{'
            f'    background-color: #282A36;'
            f'    color: #F8F8F2;'
            f'    font-family: \'{fontFamily}\';'
            f'}}'
        )


class DraculaJSONSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.highlightRules = [
            # Keywords: true, false, null. Pink. Bold
            EditorHighlightRules(r'\b(true|false|null)\b', '#FF79C6', isBold=True),
            # Numbers. Purple
            EditorHighlightRules(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?', '#BD93F9'),
            # Symbols: :, [, ], {, }. White
            EditorHighlightRules(r'[:,\[\]\{\}]', '#F8F8F2'),
            # Double-quoted strings. Yellow
            EditorHighlightRules(r'"[^"\\]*(\\.[^"\\]*)*"', '#F1FA8C'),
            # JSON keys. Green
            EditorHighlightRules(
                r'"([^"\\]*(\\.[^"\\]*)*)"\s*:', '#50FA7B', isJSONKey=True
            ),
            # Comments(only for hints on display). Grey
            EditorHighlightRules(r'^#.*', '#6272a4'),
        ]

    def highlightBlock(self, text):
        for highlightRule in self.highlightRules:
            iterator = highlightRule.regex.globalMatch(text)

            while iterator.hasNext():
                match = iterator.next()

                if highlightRule.isJSONKey:
                    # JSON keys. Ignore trailing :
                    capturedLength = match.capturedLength() - 1
                else:
                    capturedLength = match.capturedLength()

                self.setFormat(
                    match.capturedStart(), capturedLength, highlightRule.rules
                )
