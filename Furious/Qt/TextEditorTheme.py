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

"""Provide Qt support for text editor theme."""

from __future__ import annotations

from Furious.Frozenlib.Mixins import Mixins
from Furious.Qt.AppStyleSheet import AppStyleSheet

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import QApplication

__all__ = [
    'DraculaEditorTheme',
    'DraculaJSONSyntaxHighlighter',
    'DraculaLoggerSyntaxHighlighter',
    'configureEditorLogMetadata',
]

_coreVersionsProvider = lambda: tuple()
_logTimestampPatternsProvider = lambda: tuple()


def configureEditorLogMetadata(coreVersionsProvider, timestampPatternsProvider):
    """Install application-owned metadata providers used for log highlighting."""
    if not callable(coreVersionsProvider) or not callable(timestampPatternsProvider):
        raise TypeError('editor log metadata providers must be callable')

    global _coreVersionsProvider, _logTimestampPatternsProvider
    _coreVersionsProvider = coreVersionsProvider
    _logTimestampPatternsProvider = timestampPatternsProvider


def _currentTheme():
    """Return the application's active theme without coupling to its concrete type."""
    app = QApplication.instance()

    if app is not None:
        themeGetter = getattr(app, 'theme', None)

        if callable(themeGetter):
            try:
                return AppStyleSheet.normalizeTheme(themeGetter())
            except Exception:
                # A partially initialized application falls back to the safe default.
                pass

    return AppStyleSheet.Light


class EditorHighlightRules:
    """Represent editor highlight rules."""

    def __init__(self, regex, color, isBold=False, isItalic=False, isJSONKey=False):
        """Initialize the EditorHighlightRules."""
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
    """Represent editor theme."""

    def __init__(self, *args, **kwargs):
        """Initialize the EditorTheme."""
        super().__init__(*args, **kwargs)

    @staticmethod
    def getStyleSheet(*args, **kwargs):
        """Return style sheet."""
        raise NotImplementedError


class DraculaEditorTheme(EditorTheme):
    """Compatibility facade for the application-owned editor theme."""

    def __init__(self, *args, **kwargs):
        """Initialize the DraculaEditorTheme."""
        super().__init__(*args, **kwargs)

    @staticmethod
    def getStyleSheet(widgetName, fontFamily, theme=None):
        """Return token-driven editor styling while preserving the legacy API."""
        if theme is None:
            theme = _currentTheme()

        return AppStyleSheet.editorStyleSheet(
            widgetName=widgetName,
            fontFamily=fontFamily,
            theme=theme,
        )


class AppQSyntaxHighlighter(Mixins.ThemeAware, QSyntaxHighlighter):
    """Apply syntax highlighting for app q syntax text."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQSyntaxHighlighter."""
        self._theme = AppStyleSheet.normalizeTheme(kwargs.pop('theme', _currentTheme()))

        super().__init__(*args, **kwargs)

        self.highlightRules = list()

    def buildHighlightRules(self, palette):
        """Return highlight rules for *palette*."""
        return list()

    def applyTheme(self, theme):
        """Rebuild formats from semantic tokens and rehighlight the document."""
        self._theme = AppStyleSheet.normalizeTheme(theme)
        palette = AppStyleSheet.paletteForTheme(self._theme)
        self.highlightRules = self.buildHighlightRules(palette)
        self.rehighlight()

    def themeChangedCallback(self, theme: str):
        """Refresh syntax formats after an application theme change."""
        self.applyTheme(theme)

    def highlightBlock(self, text):
        """Handle highlight block for the app q syntax highlighter."""
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

                for version in _coreVersionsProvider():
                    if captured == version:
                        # These x.y.z.u version values are not IPv4 addresses. Do not highlight
                        shouldHighlight = False

                        break

                if shouldHighlight:
                    self.setFormat(capturedStart, capturedLength, highlightRule.rules)


class DraculaJSONSyntaxHighlighter(AppQSyntaxHighlighter):
    """Apply application-themed JSON syntax highlighting."""

    def __init__(self, *args, **kwargs):
        """Initialize the DraculaJSONSyntaxHighlighter."""
        super().__init__(*args, **kwargs)

        self.applyTheme(self._theme)

    def buildHighlightRules(self, palette):
        """Return JSON rules resolved from editor semantic tokens."""
        return [
            EditorHighlightRules(
                r'\b(true|false|null)\b', palette['editor_keyword'], isBold=True
            ),
            EditorHighlightRules(
                r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?',
                palette['editor_number'],
            ),
            EditorHighlightRules(r'[:,\[\]\{\}]', palette['editor_symbol']),
            EditorHighlightRules(r'"[^"\\]*(\\.[^"\\]*)*"', palette['editor_string']),
            EditorHighlightRules(
                r'"([^"\\]*(\\.[^"\\]*)*)"\s*:',
                palette['editor_key'],
                isJSONKey=True,
            ),
            EditorHighlightRules(r'^#.*', palette['editor_comment'], isItalic=True),
        ]


class DraculaLoggerSyntaxHighlighter(AppQSyntaxHighlighter):
    """Apply application-themed network logger syntax highlighting."""

    # Keep IPv4 strict enough to avoid highlighting malformed octets in logs.
    _IPV4_OCTET_REGEX = r'(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])'
    _IPV4_ADDRESS_REGEX = rf'(?:{_IPV4_OCTET_REGEX}\.){{3}}{_IPV4_OCTET_REGEX}'
    IPV4_REGEX = rf'(?<![\w.]){_IPV4_ADDRESS_REGEX}' rf'(?::[0-9]{{1,5}})?(?![\w.:])'

    _IPV6_HEXTET_REGEX = r'[0-9A-Fa-f]{1,4}'
    _IPV6_ADDRESS_REGEX = (
        rf'(?:'
        # Full, uncompressed address.
        rf'(?:{_IPV6_HEXTET_REGEX}:){{7}}{_IPV6_HEXTET_REGEX}|'
        # Compressed forms with one or more omitted hextets.
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,7}}:|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,6}}:{_IPV6_HEXTET_REGEX}|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,5}}'
        rf'(?::{_IPV6_HEXTET_REGEX}){{1,2}}|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,4}}'
        rf'(?::{_IPV6_HEXTET_REGEX}){{1,3}}|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,3}}'
        rf'(?::{_IPV6_HEXTET_REGEX}){{1,4}}|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,2}}'
        rf'(?::{_IPV6_HEXTET_REGEX}){{1,5}}|'
        rf'{_IPV6_HEXTET_REGEX}:'
        rf'(?:(?::{_IPV6_HEXTET_REGEX}){{1,6}})|'
        rf':(?:(?::{_IPV6_HEXTET_REGEX}){{1,7}}|:)|'
        # IPv4-embedded and IPv4-mapped forms.
        rf'(?:(?:{_IPV6_HEXTET_REGEX}:){{6}}|'
        rf'::(?:{_IPV6_HEXTET_REGEX}:){{0,5}}|'
        rf'(?:{_IPV6_HEXTET_REGEX}:){{1,5}}:)'
        rf'{_IPV4_ADDRESS_REGEX}'
        rf')'
    )
    _IPV6_HOST_REGEX = rf'{_IPV6_ADDRESS_REGEX}(?:%[0-9A-Za-z_.~-]+)?'
    # A port is only recognized on bracketed IPv6, where it is unambiguous.
    IPV6_REGEX = (
        rf'(?:'
        # Bracketed endpoints commonly follow a transport prefix such as "tcp:".
        rf'(?<!\w)\[{_IPV6_HOST_REGEX}\](?::[0-9]{{1,5}})?(?![\w:])|'
        rf'(?<![\w:\[]){_IPV6_HOST_REGEX}(?![\w:\]])'
        rf')'
    )

    LOGGER_NAME_REGEX = (
        r'\[(?:[A-Za-z_][A-Za-z0-9_]*)' r'(?:\.[A-Za-z_][A-Za-z0-9_]*)+\]'
    )

    def __init__(self, *args, **kwargs):
        """Initialize the DraculaLoggerSyntaxHighlighter."""
        super().__init__(*args, **kwargs)

        self.applyTheme(self._theme)

    def buildHighlightRules(self, palette):
        """Return network-log rules resolved from editor semantic tokens."""
        return [
            EditorHighlightRules(
                DraculaLoggerSyntaxHighlighter.IPV4_REGEX
                + r'|'
                + DraculaLoggerSyntaxHighlighter.IPV6_REGEX,
                palette['editor_ip'],
            ),
            EditorHighlightRules(
                r'(https?:)?\/\/[^\s,"\'>)\]]+', palette['editor_url']
            ),
            EditorHighlightRules(
                # Application logging timestamp
                r'|'.join(
                    (
                        # Application logging timestamp
                        r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}\]',
                        *_logTimestampPatternsProvider(),
                        # tun2socks logging timestamp
                        r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',
                    )
                ),
                palette['editor_timestamp'],
            ),
            EditorHighlightRules(
                DraculaLoggerSyntaxHighlighter.LOGGER_NAME_REGEX,
                palette['editor_logger'],
            ),
            EditorHighlightRules(
                r'\[INFO\]|\[Info\]|INFO', palette['editor_info'], isBold=True
            ),
            EditorHighlightRules(
                r'\[DEBUG\]|\[Debug\]|DEBUG',
                palette['editor_debug'],
                isBold=True,
            ),
            EditorHighlightRules(
                r'\[WARNING\]|\[Warning\]|WARNING|WARN',
                palette['editor_warning'],
                isBold=True,
            ),
            EditorHighlightRules(
                r'\[ERROR\]|\[Error\]|ERROR',
                palette['editor_error'],
                isBold=True,
            ),
            EditorHighlightRules(
                r'\[CRITICAL\]|\[Critical\]|CRITICAL',
                palette['editor_critical'],
                isBold=True,
            ),
            EditorHighlightRules(r"'[^']*'", palette['editor_string']),
            EditorHighlightRules(r'"[^"]*"', palette['editor_string']),
        ]
