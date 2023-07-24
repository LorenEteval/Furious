from PySide6 import QtCore
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


class HighlightRules:
    def __init__(self, regex, color, isBold=False, isJSONKey=False):
        self.regex = QtCore.QRegularExpression(regex)
        self.color = QColor(color)

        self.rules = QTextCharFormat()
        self.rules.setForeground(self.color)

        if isBold:
            self.rules.setFontWeight(QFont.Weight.Bold)

        self.isJSONKey = isJSONKey


class Theme(QSyntaxHighlighter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def getStyleSheet(*args, **kwargs):
        raise NotImplementedError


class DraculaTheme(Theme):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.highlightRules = [
            # Keywords: true, false, null. Pink. Bold
            HighlightRules(r'\b(true|false|null)\b', '#FF79C6', isBold=True),
            # Numbers. Purple
            HighlightRules(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?', '#BD93F9'),
            # Symbols: :, [, ], {, }. White
            HighlightRules(r'[:,\[\]\{\}]', '#F8F8F2'),
            # Double-quoted strings. Yellow
            HighlightRules(r'"[^"\\]*(\\.[^"\\]*)*"', '#F1FA8C'),
            # JSON keys. Green
            HighlightRules(r'"([^"\\]*(\\.[^"\\]*)*)"\s*:', '#50FA7B', isJSONKey=True),
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

    @staticmethod
    def getStyleSheet(widgetName, fontFamily):
        return (
            f'{widgetName} {{'
            f'    background-color: #282A36;'
            f'    color: #F8F8F2;'
            f'    font-family: \'{fontFamily}\';'
            f'}}'
        )
