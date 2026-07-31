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

"""Provide Qt support for qt widgets."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt.AppStyleSheet import *
from Furious.Qt.DynamicTheme import *
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Qt.QtGui import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union

import functools

__all__ = [
    'moveToCenter',
    'AppQCheckBox',
    'AppQComboBox',
    'AppQDialog',
    'AppQDialogButtonBox',
    'AppQGroupBox',
    'AppQHeaderView',
    'AppQLabel',
    'AppQLineEdit',
    'AppQListWidget',
    'AppQMainWindow',
    'AppQMenu',
    'AppQMenuBar',
    'AppQMessageBox',
    'AppQPushButton',
    'AppQSpinBox',
    'AppQTableView',
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
    """Move to center."""
    geometry = widget.frameGeometry()

    if parent is not None:
        if parent.isWindow():
            center = parent.frameGeometry().center()
        else:
            center = parent.mapToGlobal(parent.rect().center())
    else:
        screen = widget.screen() or QApplication.primaryScreen()
        center = screen.availableGeometry().center()

    geometry.moveCenter(center)

    widget.move(geometry.topLeft())


class AppQCheckBox(Mixins.QTranslatable, QCheckBox):
    """Represent app q check box."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQCheckBox."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q check box."""
        self.setText(_(self.text()))


class AppQComboBox(Mixins.QTranslatable, QComboBox):
    """Represent app q combo box."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQComboBox."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q combo box."""
        for index in range(self.count()):
            self.setItemText(index, _(self.itemText(index)))


class AppQDialog(Mixins.QTranslatable, Mixins.ConnectionAware, QDialog):
    """Present the app Qt dialog."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQDialog."""
        super().__init__(*args, **kwargs)

        self._firstShowCall = True

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

        self.setWindowIcon(AppHue.currentWindowIcon())

    def setWidthAndHeight(self):
        """Apply the default size for the app Qt dialog."""
        pass

    def exec(self):
        """Show and execute the app Qt dialog modally."""
        self.show()

        return super().exec()

    def open(self):
        """Open the app Qt dialog asynchronously."""
        self.show()

        return super().open()

    def show(self):
        """Show and position the app Qt dialog."""
        super().show()

        if PLATFORM == 'Darwin':
            if self._firstShowCall:
                self.setWidthAndHeight()

                self._firstShowCall = False

        moveToCenter(self)

    def retranslate(self):
        """Refresh translated text for the app Qt dialog."""
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        """Update the app Qt dialog for a disconnected state."""
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        """Update the app Qt dialog for a connected state."""
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQDialogButtonBox(Mixins.QTranslatable, QDialogButtonBox):
    """Represent app Qt dialog button box."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQDialogButtonBox."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app Qt dialog button box."""
        for button in self.buttons():
            button.setText(_(button.text()))


class AppQGroupBox(Mixins.QTranslatable, QGroupBox):
    """Group the app q editor controls."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQGroupBox."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q group box."""
        self.setTitle(_(self.title()))


class AppQHeaderView(Mixins.CleanupOnExit, Mixins.ConnectionAware, QHeaderView):
    """Represent app q header view."""
    def sectionSizeSettingsEmpty(self):
        """Return the section size settings empty value used by the app q header view."""
        return (
            self.legacySectionSizeSettingsName == ''
            and self.sectionSizeSettingsName == ''
        )

    def __init__(self, *args, **kwargs):
        """Initialize the AppQHeaderView."""
        self.legacySectionSizeSettingsName = kwargs.pop(
            'legacySectionSizeSettingsName', ''
        )
        self.sectionSizeSettingsName = kwargs.pop('sectionSizeSettingsName', '')

        super().__init__(*args, **kwargs)

        parent = self.parent()

        assert isinstance(parent, QTableWidget) or isinstance(parent, QTableView)

        if isinstance(parent, QTableWidget):
            self.columnCount = parent.columnCount()
        elif parent.model() is not None:
            self.columnCount = parent.model().columnCount()
        else:
            self.columnCount = 0
        self.sectionSizeTable = {}

        self.setSectionsClickable(True)
        # self.setStyleSheet(self.getStyleSheet(AppHue.currentColor()))
        self.setFont(QFont(AppFontName()))

        # self.sectionResized.connect(self.handleSectionResized)

    def restoreSectionSize(self):
        """Restore section size."""
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
        """Set custom section resize mode."""
        for index in range(self.columnCount):
            if index < self.columnCount - 1:
                self.setSectionResizeMode(index, AppQHeaderView.ResizeMode.Interactive)
            else:
                self.setSectionResizeMode(index, AppQHeaderView.ResizeMode.Stretch)

    @staticmethod
    def getStyleSheet(color):
        """Return style sheet."""
        return f'QHeaderView::section:hover {{ background-color: {color}; }}'

    def disconnectedCallback(self):
        # self.setStyleSheet(self.getStyleSheet(AppHue.disconnectedColor()))

        """Update the app q header view for a disconnected state."""
        pass

    def connectedCallback(self):
        # self.setStyleSheet(self.getStyleSheet(AppHue.connectedColor()))

        """Update the app q header view for a connected state."""
        pass

    # Legacy method. Not used
    # @QtCore.Slot(int, int, int)
    # def handleSectionResized(self, index: int, oldSize: int, newSize: int):
    #     if self.sectionSizeSettingsEmpty():
    #         return
    #
    #     # Keys are string when loaded from json
    #     self.sectionSizeTable[str(index)] = newSize

    def cleanup(self):
        """Release resources owned by the app q header view."""
        if self.sectionSizeSettingsEmpty():
            return

        # AppSettings.set(
        #     self.sectionSizeSettingsName,
        #     UJSONEncoder.encode(self.sectionSizeTable),
        # )

        AppSettings.set(self.sectionSizeSettingsName, self.saveState())


class AppQLabel(Mixins.QTranslatable, QLabel):
    """Represent app q label."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQLabel."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q label."""
        self.setText(_(self.text()))


class AppQLineEdit(Mixins.QTranslatable, QLineEdit):
    """Represent app q line edit."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQLineEdit."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q line edit."""
        self.setPlaceholderText(_(self.placeholderText()))


class AppQListWidget(Mixins.ConnectionAware, QListWidget):
    """Provide the app Qt list widget."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQListWidget."""
        super().__init__(*args, **kwargs)

        # self.setSelectionColor(AppHue.disconnectedColor())

    def setSelectionColor(self, color):
        """Set selection color."""
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
        """Return the selected index value."""
        return sorted(list(set(index.row() for index in self.selectedIndexes())))

    def disconnectedCallback(self):
        # self.setSelectionColor(AppHue.disconnectedColor())

        """Update the app Qt list widget for a disconnected state."""
        pass

    def connectedCallback(self):
        # self.setSelectionColor(AppHue.connectedColor())

        """Update the app Qt list widget for a connected state."""
        pass


class AppQMainWindow(
    Mixins.QTranslatable,
    Mixins.ConnectionAware,
    Mixins.CleanupOnExit,
    QMainWindow,
):
    """Present the app q main window."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQMainWindow."""
        super().__init__(*args, **kwargs)

        self._firstShowCall = True

        self.setWindowIcon(AppHue.currentWindowIcon())

        self._menuBar = AppQMenuBar(parent=self)
        self.setMenuBar(self._menuBar)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

    def setWidthAndHeight(self):
        """Apply the default size for the app q main window."""
        pass

    def show(self):
        """Show and position the app q main window."""
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
        """Refresh translated text for the app q main window."""
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        """Update the app q main window for a disconnected state."""
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        """Update the app q main window for a connected state."""
        self.setWindowIcon(AppHue.connectedWindowIcon())

    def cleanup(self):
        """Release resources owned by the app q main window."""
        pass


class AppQMenu(Mixins.QTranslatable, QMenu):
    """Represent app q menu."""
    def __init__(self, *actions, **kwargs):
        """Initialize the AppQMenu."""
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

    def retranslate(self):
        """Refresh translated text for the app q menu."""
        self.setTitle(_(self.title()))


class AppQMenuBar(QMenuBar):
    """Represent app q menu bar."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQMenuBar."""
        super().__init__(*args, **kwargs)


class AppQMessageBox(Mixins.QTranslatable, Mixins.ConnectionAware, QMessageBox):
    """Represent app q message box."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQMessageBox."""
        super().__init__(*args, **kwargs)

        self.setWindowIcon(AppHue.currentWindowIcon())

    def moveToCenter(self):
        """Move to center."""
        moveToCenter(self, self.parentWidget())

        return self

    def exec(self):
        """Show and execute the app q message box modally."""
        self.show()
        self.moveToCenter()

        return super().exec()

    def open(self):
        """Open the app q message box asynchronously."""
        self.show()
        self.moveToCenter()

        return super().open()

    def retranslate(self):
        """Refresh translated text for the app q message box."""
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
        """Update the app q message box for a disconnected state."""
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        """Update the app q message box for a connected state."""
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQPushButton(Mixins.QTranslatable, Mixins.ThemeAware, QPushButton):
    """Represent app q push button."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQPushButton."""
        icon = kwargs.pop('icon', None)

        super().__init__(*args, **kwargs)

        self.iconFileName = ''

        if icon is not None:
            self.setIcon(icon)

    @staticmethod
    @functools.lru_cache(None)
    def getIconFileName(fileName):
        """Return icon file name."""
        try:
            return fileName.split('/')[-1]
        except Exception:
            # Any non-exit exceptions

            return ''

    def setIconByTheme(self, theme):
        """Set icon by theme."""
        if not self.iconFileName:
            return

        if AppSettings.isStateON_('DarkMode'):
            # Custom dark mode
            super().setIcon(bootstrapIconWhite(self.iconFileName))

            return

        if theme == 'Dark':
            if PLATFORM == 'Windows':
                # Windows
                if versionToValue(PYSIDE6_VERSION) < versionToValue('6.7.0'):
                    # PySide6 < 6.7.0 has no system theme handling on Windows.
                    # Always use black icon
                    super().setIcon(bootstrapIcon(self.iconFileName))
                else:
                    # PySide6 has system theme handling.
                    super().setIcon(bootstrapIconWhite(self.iconFileName))
            else:
                super().setIcon(bootstrapIconWhite(self.iconFileName))
        else:
            super().setIcon(bootstrapIcon(self.iconFileName))

    def setIcon(self, icon: AppQIcon):
        """Set icon."""
        self.iconFileName = self.getIconFileName(icon.iconFileName)

        if not self.iconFileName:
            # Fall back
            super().setIcon(icon)
        else:
            self.setIconByTheme(APP().theme())

    def themeChangedCallback(self, theme):
        """Update the app q push button for a theme change."""
        self.setIconByTheme(theme)

    def retranslate(self):
        """Refresh translated text for the app q push button."""
        self.setText(_(self.text()))


class AppQSpinBox(QSpinBox):
    """Represent app q spin box."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQSpinBox."""
        super().__init__(*args, **kwargs)

    def resizeHints(self):
        """Handle resize hints for the app q spin box."""
        self.setMinimumWidth(
            max(
                self.sizeHint().width(),
                self.fontMetrics().horizontalAdvance(str(self.maximum())) + 100,
            )
        )

    def setRange(self, *args, **kwargs):
        """Set range."""
        super().setRange(*args, **kwargs)

        self.resizeHints()


class AppQTableView(Mixins.ConnectionAware, QTableView):
    """Represent app Qt table view."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQTableView."""
        super().__init__(*args, **kwargs)

        self.setWordWrap(False)
        self.setAlternatingRowColors(True)

    def setDefaultRowHeight(self, height: int):
        """Set default row height."""
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(height)

    @staticmethod
    def getStyleSheet(color):
        """Return style sheet."""
        return f'QTableView {{ selection-background-color: {color}; }}'

    def setSelectionColor(self, color):
        # self.setStyleSheet(self.getStyleSheet(color))

        """Set selection color."""
        pass

    def disconnectedCallback(self):
        """Update the app Qt table view for a disconnected state."""
        self.setSelectionColor(AppHue.disconnectedColor())

    def connectedCallback(self):
        """Update the app Qt table view for a connected state."""
        self.setSelectionColor(AppHue.connectedColor())


class AppQTableWidget(Mixins.ConnectionAware, QTableWidget):
    """Provide the app Qt table widget."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQTableWidget."""
        super().__init__(*args, **kwargs)

        self.setWordWrap(False)
        self.setAlternatingRowColors(True)

    @property
    def selectedIndex(self):
        """Return the selected index value."""
        return sorted(list(set(index.row() for index in self.selectedIndexes())))

    @staticmethod
    def getStyleSheet(color):
        """Return style sheet."""
        return f'QTableWidget {{ selection-background-color: {color}; }}'

    def setSelectionColor(self, color):
        # self.setStyleSheet(self.getStyleSheet(color))

        """Set selection color."""
        pass

    def activateItemByIndex(self, index, activate):
        """Activate item by index."""
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
        """Select multiple rows."""
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
        """Update the app Qt table widget for a disconnected state."""
        self.setSelectionColor(AppHue.disconnectedColor())

    def connectedCallback(self):
        """Update the app Qt table widget for a connected state."""
        self.setSelectionColor(AppHue.connectedColor())


class AppQTabWidget(Mixins.QTranslatable, QTabWidget):
    """Provide the app q tab widget."""
    def __init__(self, *args, **kwargs):
        """Initialize the AppQTabWidget."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the app q tab widget."""
        for index in range(self.count()):
            self.setTabText(index, _(self.tabText(index)))


class AppQToolBar(Mixins.QTranslatable, QToolBar):
    """Represent app q tool bar."""
    def __init__(self, *actions, **kwargs):
        """Initialize the AppQToolBar."""
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
        """Show menu below."""
        def toolBarWidgetForAction() -> Union[QWidget | None]:
            # Walk through the toolbar to find the widget for the action
            """Return the tool bar widget for action value used by the app q tool bar."""
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
        """Return style sheet."""
        return f'QToolBar {{ spacing: 5px; }}'

    def retranslate(self):
        """Refresh translated text for the app q tool bar."""
        self.setWindowTitle(_(self.windowTitle()))


class MBoxQuestionDelete(AppQMessageBox):
    """Represent m box question delete."""
    def __init__(self, *args, **kwargs):
        """Initialize the MBoxQuestionDelete."""
        super().__init__(*args, **kwargs)

        self.isMulti = False
        self.possibleRemark = ''

        self.setWindowTitle(_('Delete'))
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def customText(self) -> str:
        """Return the user-facing message text for the m box question delete."""
        if self.isMulti:
            return _('Delete these items?')
        else:
            return _('Delete this item?') + f'\n\n{self.possibleRemark}'

    def retranslate(self):
        """Refresh translated text for the m box question delete."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxNewChangesNextTime(AppQMessageBox):
    """Represent m box new changes next time."""
    def __init__(self, *args, **kwargs):
        """Initialize the MBoxNewChangesNextTime."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setIcon(AppQMessageBox.Icon.Information)
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )
        self.setText(self.customText())

    @staticmethod
    def customText() -> str:
        """Return the user-facing message text for the m box new changes next time."""
        return (
            _('New changes will take effect next time') + '\n\n' + _('Reconnect now?')
        )

    def retranslate(self):
        """Refresh translated text for the m box new changes next time."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


def showMBoxNewChangesNextTime(**kwargs):

    """Show m box new changes next time."""
    @QtCore.Slot(int)
    def handleResultCode(code):
        """Handle result code."""
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
    """Represent m box direct rules not allowed."""
    def __init__(self, *args, **kwargs):
        """Initialize the MBoxDirectRulesNotAllowed."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Unable to connect'))
        self.setIcon(AppQMessageBox.Icon.Critical)
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )
        self.setText(self.customText())

    @staticmethod
    def customText() -> str:
        """Return the user-facing message text for the m box direct rules not allowed."""
        return (
            _('Routing option with direct rules is not allowed in TUN mode')
            + '\n\n'
            + _('Switch to global and reconnect?')
        )

    def retranslate(self):
        """Refresh translated text for the m box direct rules not allowed."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


def showMBoxDirectRulesNotAllowed(**kwargs):
    """Show m box direct rules not allowed."""
    @QtCore.Slot(int)
    def handleResultCode(code):
        """Handle result code."""
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
    """Represent m box unrecognized config."""
    def __init__(self, *args, **kwargs):
        """Initialize the MBoxUnrecognizedConfig."""
        super().__init__(*args, **kwargs)

        self.setIcon(AppQMessageBox.Icon.Critical)
        self.setText(_('Unrecognized Configuration. Please modify it in the editor'))


def showMBoxUnrecognizedConfig(**kwargs):
    """Show m box unrecognized config."""
    mbox = MBoxUnrecognizedConfig(**kwargs)

    if isinstance(mbox.parent(), QMainWindow):
        mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    else:
        mbox.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

    # Show the MessageBox asynchronously
    mbox.open()
