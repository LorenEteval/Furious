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

from __future__ import annotations

from Furious.Core import *

from PySide6 import QtCore
from PySide6.QtGui import *

__all__ = [
    'DraculaEditorTheme',
    'DraculaJSONSyntaxHighlighter',
    'DraculaLoggerSyntaxHighlighter',
]


class EditorHighlightRules:
    def __init__(self, regex, color, isBold=False, isItalic=False, isJSONKey=False):
        self.regex = QtCore.QRegularExpression(regex)
        self.color = QColor(color)

        self.rules = QTextCharFormat()
        self.rules.setForeground(self.color)

        if isBold:
            self.rules.setFontWeight(QFont.Weight.Bold)

        if isItalic:
            self.rules.setFontItalic(True)

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


class AppQSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.highlightRules = list()

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

                capturedStart = match.capturedStart()
                captured = text[capturedStart : capturedStart + capturedLength]
                shouldHighlight = True

                for version in [
                    XrayCore.version(),
                    Hysteria1.version(),
                    Hysteria2.version(),
                    Tun2socks.version(),
                ]:
                    if captured == version:
                        # These x.y.z.u version values are not IPv4 addresses. Do not highlight
                        shouldHighlight = False

                        break

                if shouldHighlight:
                    self.setFormat(capturedStart, capturedLength, highlightRule.rules)


class DraculaJSONSyntaxHighlighter(AppQSyntaxHighlighter):
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
            EditorHighlightRules(r'^#.*', '#6272A4'),
        ]


class DraculaLoggerSyntaxHighlighter(AppQSyntaxHighlighter):
    # https://ihateregex.io/expr/ip/
    IPV4_REGEX = (
        r'(\b25[0-5]|\b2[0-4][0-9]|\b[01]?[0-9][0-9]?)'
        r'(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}(?::\d{1,5})?\b'
    )
    # https://vernon.mauery.com/content/2008/04/21/ipv6-regex/
    IPV6_REGEX = (
        r'(A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]{1,4}){1,6}Z)|'
        r'(A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,5}Z)|'
        r'(A([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,4}Z)|'
        r'(A([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,3}Z)|'
        r'(A([0-9a-f]{1,4}:){1,5}(:[0-9a-f]{1,4}){1,2}Z)|'
        r'(A([0-9a-f]{1,4}:){1,6}(:[0-9a-f]{1,4}){1,1}Z)|'
        r'(A(([0-9a-f]{1,4}:){1,7}|:):Z)|'
        r'(A:(:[0-9a-f]{1,4}){1,7}Z)|'
        r'(A((([0-9a-f]{1,4}:){6})(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3})Z)|'
        r'(A(([0-9a-f]{1,4}:){5}[0-9a-f]{1,4}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3})Z)|'
        r'(A([0-9a-f]{1,4}:){5}:[0-9a-f]{1,4}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A([0-9a-f]{1,4}:){1,1}(:[0-9a-f]{1,4}){1,4}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A([0-9a-f]{1,4}:){1,2}(:[0-9a-f]{1,4}){1,3}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A([0-9a-f]{1,4}:){1,3}(:[0-9a-f]{1,4}){1,2}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A([0-9a-f]{1,4}:){1,4}(:[0-9a-f]{1,4}){1,1}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A(([0-9a-f]{1,4}:){1,5}|:):(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)|'
        r'(A:(:[0-9a-f]{1,4}){1,5}:(25[0-5]|2[0-4]d|[0-1]?d?d)(.(25[0-5]|2[0-4]d|[0-1]?d?d)){3}Z)(?::\d{1,5})?'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.highlightRules = [
            # IP addresses (IPv4 & IPv6)
            EditorHighlightRules(
                DraculaLoggerSyntaxHighlighter.IPV4_REGEX
                + r'|'
                + DraculaLoggerSyntaxHighlighter.IPV6_REGEX,
                '#B4FFFF',
            ),
            # URLs
            EditorHighlightRules(r'(https?:)?\/\/[^\s,"\'>)\]]+', '#FFDD88'),
            # Timestamps
            EditorHighlightRules(
                # Application logging timestamp
                r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\]' + r'|'
                # Xray-core logging timestamp
                + r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}.\d{6}' + r'|'
                # hysteria2 logging timestamp
                + r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})' + r'|'
                # tun2socks logging timestamp
                + r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',
                '#7F7F7F',
            ),
            # Logger name: [X.Y.Z]
            EditorHighlightRules(
                r'\[[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+\]', '#FFB46E'
            ),
            # Log levels
            EditorHighlightRules(r'\[INFO\]|\[Info\]|INFO', '#A0C882', isBold=True),
            EditorHighlightRules(r'\[DEBUG\]|\[Debug\]|DEBUG', '#82B4FF', isBold=True),
            EditorHighlightRules(
                r'\[WARNING\]|\[Warning\]|WARNING', '#FFD75A', isBold=True
            ),
            EditorHighlightRules(r'\[ERROR\]|\[Error\]|ERROR', '#FF7878', isBold=True),
            EditorHighlightRules(
                r'\[CRITICAL\]|\[Critical\]|CRITICAL', '#FF5050', isBold=True
            ),
            # Quoted strings (single or double)
            EditorHighlightRules(r"'[^']*'", '#A0FFA0'),
            EditorHighlightRules(r'"[^"]*"', '#A0FFA0'),
        ]
