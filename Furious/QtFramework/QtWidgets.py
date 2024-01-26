from __future__ import annotations

from Furious.QtFramework.Ancestors import *
from Furious.QtFramework.DynamicTheme import AppHue
from Furious.QtFramework.DynamicTranslate import gettext as _
from Furious.QtFramework.QtGui import AppQAction, AppQSeperator
from Furious.PyFramework import *
from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

__all__ = [
    'moveToCenter',
    'AppQDialog',
    'AppQGroupBox',
    'AppQHeaderView',
    'AppQLabel',
    'AppQListWidget',
    'AppQMainWindow',
    'AppQMenu',
    'AppQMenuBar',
    'AppQMessageBox',
    'AppQPushButton',
    'AppQStyledItemDelegate',
    'AppQTableWidget',
    'AppQTabWidget',
    'AppQToolBar',
    'QuestionDeleteMBox',
]


def moveToCenter(widget, parent=None):
    geometry = widget.geometry()

    if parent is None:
        center = QApplication.primaryScreen().availableGeometry().center()
    else:
        center = parent.geometry().center()

    geometry.moveCenter(center)

    widget.move(geometry.topLeft())


class AppQDialog(QTranslatable, SupportConnectedCallback, QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

        self.setWindowIcon(AppHue.currentWindowIcon())

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

    def retranslate(self):
        pass

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQGroupBox(QTranslatable, QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setTitle(_(self.title()))


class AppQHeaderView(SupportExitCleanup, SupportConnectedCallback, QHeaderView):
    def sectionSizeSettingsEmpty(self):
        return self.sectionSizeSettingsName == ''

    def __init__(self, *args, **kwargs):
        self.sectionSizeSettingsName = kwargs.pop('sectionSizeSettingsName', '')

        super().__init__(*args, **kwargs)

        self.columnCount = self.parent().columnCount()
        self.sectionSizeTable = {}

        self.setSectionsClickable(True)
        self.setStyleSheet(self.getStyleSheet(AppHue.currentColor()))
        self.setFont(QFont(APP().customFontName))

        self.sectionResized.connect(self.handleSectionResized)

    def restoreSectionSize(self):
        if self.sectionSizeSettingsEmpty():
            return

        try:
            self.sectionSizeTable = UJSONEncoder.decode(
                AppSettings.get(self.sectionSizeSettingsName)
            )

            # Fill missing value
            for column in range(self.columnCount):
                if self.sectionSizeTable.get(str(column)) is None:
                    self.sectionSizeTable[str(column)] = self.defaultSectionSize()

            with QBlockSignals(self):
                for key, value in self.sectionSizeTable.items():
                    self.resizeSection(int(key), value)
        except Exception:
            # Any non-exit exceptions

            # Leave keys as strings since they will be
            # loaded as string from json
            self.sectionSizeTable = {
                str(column): self.defaultSectionSize()
                for column in range(self.columnCount)
            }

    def setCustomSectionResizeMode(self):
        # Horizontal header resize mode
        for index in range(self.columnCount):
            if index < self.columnCount - 1:
                self.setSectionResizeMode(index, AppQHeaderView.ResizeMode.Interactive)
            else:
                self.setSectionResizeMode(index, AppQHeaderView.ResizeMode.Stretch)

    @staticmethod
    def getStyleSheet(color):
        return f'QHeaderView::section:hover {{ background-color: {color}; }}'

    def disconnectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

    def connectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.connectedColor()))

    @QtCore.Slot(int, int, int)
    def handleSectionResized(self, index: int, oldSize: int, newSize: int):
        if self.sectionSizeSettingsEmpty():
            return

        # Keys are string when loaded from json
        self.sectionSizeTable[str(index)] = newSize

    def cleanup(self):
        if self.sectionSizeSettingsEmpty():
            return

        AppSettings.set(
            self.sectionSizeSettingsName,
            UJSONEncoder.encode(self.sectionSizeTable),
        )


class AppQLabel(QTranslatable, QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class AppQListWidget(SupportConnectedCallback, QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSelectionColor(AppHue.disconnectedColor())

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

    def disconnectedCallback(self):
        self.setSelectionColor(AppHue.disconnectedColor())

    def connectedCallback(self):
        self.setSelectionColor(AppHue.connectedColor())


class AppQMainWindow(
    QTranslatable,
    SupportConnectedCallback,
    SupportExitCleanup,
    QMainWindow,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowIcon(AppHue.currentWindowIcon())

        self._menuBar = AppQMenuBar(parent=self)
        self.setMenuBar(self._menuBar)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

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

        self.hide()

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())

    def cleanup(self):
        pass


class AppQMenu(QTranslatable, SupportConnectedCallback, QMenu):
    def __init__(self, *actions, **kwargs):
        super().__init__(**kwargs)

        # In some old version PySide6, the self.actions() method
        # does not return with seperators. _actions list append
        # them all
        self._actions = []

        for action in actions:
            if isinstance(action, AppQSeperator):
                self._actions.append(action)
                self.addSeparator()
            elif isinstance(action, AppQAction):
                self._actions.append(action)
                self.addAction(action)
            else:
                # Do nothing
                pass

        self.setStyleSheet(self.getStyleSheet(AppHue.currentColor()))

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

    def retranslate(self):
        self.setTitle(_(self.title()))

    def disconnectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

    def connectedCallback(self):
        self.setStyleSheet(self.getStyleSheet(AppHue.connectedColor()))


class AppQMenuBar(SupportConnectedCallback, QMenuBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSelectionColor(AppHue.currentColor())

    @staticmethod
    def getStyleSheet(color):
        return (
            f'QMenuBar::item:selected {{'
            f'    background: {color};'
            f'}}'
            f''
            f'QMenuBar::item:hover {{'
            f'    background: {color};'
            f'}}'
        )

    def setSelectionColor(self, color):
        self.setStyleSheet(self.getStyleSheet(color))

    def disconnectedCallback(self):
        self.setSelectionColor(AppHue.disconnectedColor())

    def connectedCallback(self):
        self.setSelectionColor(AppHue.connectedColor())


class AppQMessageBox(QTranslatable, SupportConnectedCallback, QMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowIcon(AppHue.currentWindowIcon())

    def moveToCenter(self):
        moveToCenter(self, self.parentWidget())

        return self

    def exec(self):
        self.show()
        self.moveToCenter()

        return super().exec()

    def open(self):
        self.show()
        self.moveToCenter()

        return super().open()

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(_(self.text()))

        try:
            self.setInformativeText(_(self.informativeText()))
        except KeyError:
            # Any translatable informative text
            pass

        for button in self.buttons():
            if button.text().find('OK') != -1:
                # &OK...
                pass
            else:
                button.setText(_(button.text()))

        self.moveToCenter()

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQPushButton(QTranslatable, QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class AppQStyledItemDelegate(QStyledItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFont(QFont(APP().customFontName))

        return editor


class AppQTableWidget(SupportConnectedCallback, QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWordWrap(False)

    @property
    def selectedIndex(self):
        return sorted(list(set(index.row() for index in self.selectedIndexes())))

    @staticmethod
    def getStyleSheet(color):
        return f'QTableWidget {{ selection-background-color: {color}; }}'

    def setSelectionColor(self, color):
        self.setStyleSheet(self.getStyleSheet(color))

    def activateItemByIndex(self, index, activate):
        if activate:
            for column in range(self.columnCount()):
                item = self.item(int(index), column)

                if item is None:
                    # Do nothing
                    continue

                font = item.font()
                font.setBold(True)

                item.setFont(font)
                item.setForeground(QColor(AppHue.currentColor()))
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

    def selectMultipleRows(self, indexes: list[int], clearCurrentSelection: bool):
        if clearCurrentSelection:
            self.selectionModel().clearSelection()

        selection = self.selectionModel().selection()

        for index in indexes:
            selection.select(
                self.model().index(index, 0),
                self.model().index(index, self.columnCount() - 1),
            )

        self.selectionModel().select(
            selection, QtCore.QItemSelectionModel.SelectionFlag.Select
        )

    def disconnectedCallback(self):
        self.setSelectionColor(AppHue.disconnectedColor())

    def connectedCallback(self):
        self.setSelectionColor(AppHue.connectedColor())


class AppQTabWidget(QTranslatable, QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for index in range(self.count()):
            self.setTabText(index, _(self.tabText(index)))


class AppQToolBar(QToolBar):
    def __init__(self, title, *actions, **kwargs):
        super().__init__(title, **kwargs)

        self._actions = []

        for action in actions:
            if isinstance(action, AppQSeperator):
                self._actions.append(action)
                self.addSeparator()
            elif isinstance(action, AppQAction):
                self._actions.append(action)
                self.addAction(action)
            else:
                # Do nothing
                pass

        self.setStyleSheet(self.getStyleSheet())

    @staticmethod
    def getStyleSheet():
        return f'QToolBar {{ spacing: 5px; }}'


class QuestionDeleteMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.isMulti = False
        self.possibleRemark = ''

        self.setWindowTitle(_('Delete'))
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def customText(self) -> str:
        if self.isMulti:
            return _('Delete these configuration?')
        else:
            return _('Delete this configuration?') + f'\n\n{self.possibleRemark}'

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()
