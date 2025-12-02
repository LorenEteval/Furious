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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt.DynamicTheme import *
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Qt.QtGui import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union

__all__ = [
    'moveToCenter',
    'AppQCheckBox',
    'AppQComboBox',
    'AppQDialog',
    'AppQDialogButtonBox',
    'AppQGroupBox',
    'AppQHeaderView',
    'AppQLabel',
    'AppQListWidget',
    'AppQMainWindow',
    'AppQMenu',
    'AppQMenuBar',
    'AppQMessageBox',
    'AppQPushButton',
    'AppQTableWidget',
    'AppQTabWidget',
    'AppQToolBar',
    'MBoxQuestionDelete',
    'MBoxNewChangesNextTime',
    'MBoxDirectRulesNotAllowed',
    'MBoxUnrecognizedConfig',
    'showMBoxNewChangesNextTime',
    'showMBoxDirectRulesNotAllowed',
    'showMBoxUnrecognizedConfig',
]


def moveToCenter(widget, parent=None):
    geometry = widget.geometry()

    if parent is None:
        center = QApplication.primaryScreen().availableGeometry().center()
    else:
        center = parent.geometry().center()

    geometry.moveCenter(center)

    widget.move(geometry.topLeft())


class AppQCheckBox(Mixins.QTranslatable, QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class AppQComboBox(Mixins.QTranslatable, QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for index in range(self.count()):
            self.setItemText(index, _(self.itemText(index)))


class AppQDialog(Mixins.QTranslatable, Mixins.ConnectionAware, QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._firstShowCall = True

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
            if self._firstShowCall:
                self.setWidthAndHeight()

                self._firstShowCall = False

        moveToCenter(self)

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQDialogButtonBox(Mixins.QTranslatable, QDialogButtonBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for button in self.buttons():
            button.setText(_(button.text()))


class AppQGroupBox(Mixins.QTranslatable, QGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setTitle(_(self.title()))


class AppQHeaderView(Mixins.CleanupOnExit, Mixins.ConnectionAware, QHeaderView):
    def sectionSizeSettingsEmpty(self):
        return (
            self.legacySectionSizeSettingsName == ''
            and self.sectionSizeSettingsName == ''
        )

    def __init__(self, *args, **kwargs):
        self.legacySectionSizeSettingsName = kwargs.pop(
            'legacySectionSizeSettingsName', ''
        )
        self.sectionSizeSettingsName = kwargs.pop('sectionSizeSettingsName', '')

        super().__init__(*args, **kwargs)

        parent = self.parent()

        assert isinstance(parent, QTableWidget)

        self.columnCount = parent.columnCount()
        self.sectionSizeTable = {}

        self.setSectionsClickable(True)
        self.setStyleSheet(self.getStyleSheet(AppHue.currentColor()))
        self.setFont(QFont(AppFontName()))

        # self.sectionResized.connect(self.handleSectionResized)

    def restoreSectionSize(self):
        if self.sectionSizeSettingsEmpty():
            return

        if AppSettings.get(self.sectionSizeSettingsName) is not None:
            try:
                self.restoreState(AppSettings.get(self.sectionSizeSettingsName))
            except Exception:
                # Any non-exit exceptions

                # Fall back to legacy restore method
                pass
            else:
                return

        # Fall back to legacy restore method
        try:
            # https://bugreports.qt.io/browse/QTBUG-119862
            # Affected: PySide6 6.6.1+
            self.setDefaultSectionSize(self.defaultSectionSize())

            self.sectionSizeTable = UJSONEncoder.decode(
                AppSettings.get(self.legacySectionSizeSettingsName)
            )

            # Fill missing value
            for column in range(self.columnCount):
                if self.sectionSizeTable.get(str(column)) is None:
                    self.sectionSizeTable[str(column)] = self.defaultSectionSize()

            with Mixins.QBlockSignalContext(self):
                for key, value in reversed(self.sectionSizeTable.items()):
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

    # Legacy method. Not used
    # @QtCore.Slot(int, int, int)
    # def handleSectionResized(self, index: int, oldSize: int, newSize: int):
    #     if self.sectionSizeSettingsEmpty():
    #         return
    #
    #     # Keys are string when loaded from json
    #     self.sectionSizeTable[str(index)] = newSize

    def cleanup(self):
        if self.sectionSizeSettingsEmpty():
            return

        # AppSettings.set(
        #     self.sectionSizeSettingsName,
        #     UJSONEncoder.encode(self.sectionSizeTable),
        # )

        AppSettings.set(self.sectionSizeSettingsName, self.saveState())


class AppQLabel(Mixins.QTranslatable, QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class AppQListWidget(Mixins.ConnectionAware, QListWidget):
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
    Mixins.QTranslatable,
    Mixins.ConnectionAware,
    Mixins.CleanupOnExit,
    QMainWindow,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._firstShowCall = True

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
            if self._firstShowCall:
                self.setWidthAndHeight()

                self._firstShowCall = False

        moveToCenter(self)

        APP().processEvents()

        if PLATFORM == 'Darwin':
            self.activateWindow()
            self.raise_()

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        self.setWindowIcon(AppHue.connectedWindowIcon())

    def cleanup(self):
        pass


class AppQMenu(Mixins.QTranslatable, Mixins.ConnectionAware, QMenu):
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
            f'QMenu {{'
            f'    padding: 6px;'
            f'}}'
            f''
            f'QMenu::item {{'
            f'    padding: 6px 12px;'
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


class AppQMenuBar(Mixins.ConnectionAware, QMenuBar):
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


class AppQMessageBox(Mixins.QTranslatable, Mixins.ConnectionAware, QMessageBox):
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


class AppQPushButton(Mixins.QTranslatable, QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        self.setText(_(self.text()))


class AppQTableWidget(Mixins.ConnectionAware, QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWordWrap(False)
        self.setAlternatingRowColors(True)

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


class AppQTabWidget(Mixins.QTranslatable, QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def retranslate(self):
        for index in range(self.count()):
            self.setTabText(index, _(self.tabText(index)))


class AppQToolBar(Mixins.QTranslatable, QToolBar):
    def __init__(self, *actions, **kwargs):
        super().__init__(**kwargs)

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

        self.actionTriggered.connect(self.showMenuBelow)

    @QtCore.Slot(AppQAction)
    def showMenuBelow(self, action: AppQAction):
        def toolBarWidgetForAction() -> Union[QWidget | None]:
            # Walk through the toolbar to find the widget for the action
            for child in self.children():
                if hasattr(child, 'defaultAction'):
                    # PySide6.QtWidgets.QMenu.defaultAction
                    assert isinstance(child, QWidget)

                    if child.defaultAction() == action:
                        return child

            return None

        button = toolBarWidgetForAction()

        if button is not None:
            menu = action._menu

            if isinstance(menu, AppQMenu):
                menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    @staticmethod
    def getStyleSheet():
        return f'QToolBar {{ spacing: 5px; }}'

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))


class MBoxQuestionDelete(AppQMessageBox):
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
            return _('Delete these items?')
        else:
            return _('Delete this item?') + f'\n\n{self.possibleRemark}'

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxNewChangesNextTime(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setIcon(AppQMessageBox.Icon.Information)
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )
        self.setText(self.customText())

    @staticmethod
    def customText() -> str:
        return (
            _('New changes will take effect next time') + '\n\n' + _('Reconnect now?')
        )

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


def showMBoxNewChangesNextTime(**kwargs):

    @QtCore.Slot(int)
    def handleResultCode(code):
        if code == PySide6Legacy.enumValueWrapper(AppQMessageBox.StandardButton.Yes):
            APP().systemTray.ConnectAction.doReconnect()
        else:
            # Do nothing
            pass

    try:
        method = kwargs.pop('method', 'open')

        if APP().isSystemTrayConnected():
            mbox = MBoxNewChangesNextTime(**kwargs)

            if isinstance(mbox.parent(), QMainWindow):
                mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            else:
                mbox.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

            if method == 'open':
                mbox.finished.connect(handleResultCode)
                # Show the MessageBox asynchronously
                mbox.open()
            else:
                # Show the MessageBox and wait for the user to close it
                handleResultCode(mbox.exec())
    except Exception:
        # Any non-exit exceptions

        pass


class MBoxDirectRulesNotAllowed(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Unable to connect'))
        self.setIcon(AppQMessageBox.Icon.Critical)
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )
        self.setText(self.customText())

    @staticmethod
    def customText() -> str:
        return (
            _('Routing option with direct rules is not allowed in TUN mode')
            + '\n\n'
            + _('Switch to global and reconnect?')
        )

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


def showMBoxDirectRulesNotAllowed(**kwargs):
    @QtCore.Slot(int)
    def handleResultCode(code):
        if code == PySide6Legacy.enumValueWrapper(AppQMessageBox.StandardButton.Yes):
            APP().systemTray.RoutingAction.getGlobalAction().trigger()
            APP().systemTray.ConnectAction.trigger()
        else:
            # Do nothing
            pass

    mbox = MBoxDirectRulesNotAllowed(**kwargs)
    mbox.finished.connect(handleResultCode)

    if isinstance(mbox.parent(), QMainWindow):
        mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    else:
        mbox.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

    # Show the MessageBox asynchronously
    mbox.open()


class MBoxUnrecognizedConfig(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setIcon(AppQMessageBox.Icon.Critical)
        self.setText(_('Unrecognized Configuration. Please modify it in the editor'))


def showMBoxUnrecognizedConfig(**kwargs):
    mbox = MBoxUnrecognizedConfig(**kwargs)

    if isinstance(mbox.parent(), QMainWindow):
        mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    else:
        mbox.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

    # Show the MessageBox asynchronously
    mbox.open()
