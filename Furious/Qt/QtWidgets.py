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
from Furious.Models import *
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
    'AppQComboBoxSeparatorDelegate',
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
    'AppQIconTextPushButton',
    'AppQPushButton',
    'AppQSpinBox',
    'AppQTableView',
    'AppQTabWidget',
    'AppQToolBar',
    'IconTextPushButton',
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


class AppQComboBoxSeparatorDelegate(Mixins.ThemeAware, QAbstractItemDelegate):
    """Paint real combo-box separators with application theme tokens."""

    SeparatorRoleValue = 'separator'
    HorizontalMargin = 8

    def __init__(self, wrappedDelegate, comboBox):
        """Wrap Qt's native delegate without changing normal item painting."""
        self.wrappedDelegate = wrappedDelegate
        self.comboBox = comboBox

        super().__init__(comboBox)

    @staticmethod
    def isSeparator(index) -> bool:
        """Return whether *index* was created by QComboBox.insertSeparator()."""
        return (
            index.data(QtCore.Qt.ItemDataRole.AccessibleDescriptionRole)
            == AppQComboBoxSeparatorDelegate.SeparatorRoleValue
        )

    def paint(self, painter, option, index):
        """Paint separators and preserve Qt's native rendering for all items."""
        if not self.isSeparator(index):
            self.wrappedDelegate.paint(painter, option, index)

            return

        try:
            color = QColor(
                AppStyleSheet.paletteForTheme(APP().theme())['border_strong']
            )
        except (AttributeError, RuntimeError):
            color = option.palette.color(QPalette.ColorRole.Mid)

        line = option.rect.adjusted(self.HorizontalMargin, 0, -self.HorizontalMargin, 0)
        y = line.center().y()

        painter.fillRect(line.left(), y, max(0, line.width()), 1, color)

    def sizeHint(self, option, index):
        """Keep the native popup's item and separator geometry unchanged."""
        return self.wrappedDelegate.sizeHint(option, index)

    def themeChangedCallback(self, theme: str):
        """Repaint the popup viewport after an application theme change."""
        self.comboBox.view().viewport().update()


class AppQComboBox(Mixins.QTranslatable, QComboBox):
    """Represent app q combo box."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQComboBox."""
        super().__init__(*args, **kwargs)

        self._themedSeparatorDelegate = None

    def enableThemedSeparators(self):
        """Theme real insertSeparator() rows while preserving native items."""
        if self._themedSeparatorDelegate is not None:
            return

        self._themedSeparatorDelegate = AppQComboBoxSeparatorDelegate(
            self.itemDelegate(), self
        )
        self.setItemDelegate(self._themedSeparatorDelegate)

    def retranslate(self):
        """Refresh translated text for the app q combo box."""
        for index in range(self.count()):
            self.setItemText(index, _(self.itemText(index)))


class AppQDialog(Mixins.QTranslatable, Mixins.ConnectionAware, QDialog):
    """Present the app Qt dialog."""

    _openDialogs = {}

    @staticmethod
    def _releaseOpenDialog(key, *_args):
        """Release an asynchronously opened dialog after it finishes."""
        AppQDialog._openDialogs.pop(key, None)

    def __init__(self, *args, **kwargs):
        """Initialize the AppQDialog."""
        super().__init__(*args, **kwargs)

        @callOnceOnly
        def connect(key):
            """Connect the lifetime release signals once."""
            release = functools.partial(AppQDialog._releaseOpenDialog, key)

            self.finished.connect(release)
            self.destroyed.connect(release)

        @callOnceOnly
        def firstShow():
            """Apply the first-show sizing once."""
            self.setWidthAndHeight()

        self._connectOnce = connect
        self._firstShow = firstShow

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
        """Open and retain the dialog until it finishes or is destroyed."""
        key = id(self)
        AppQDialog._openDialogs[key] = self

        self._connectOnce(key)

        try:
            self.show()

            return super().open()
        except Exception:
            # Any non-exit exceptions

            AppQDialog._releaseOpenDialog(key)

            raise

    def show(self):
        """Show and position the app Qt dialog."""
        super().show()

        if PLATFORM == 'Darwin':
            self._firstShow()

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


class AppQHeaderView(Mixins.CleanupOnExit, QHeaderView):
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


class AppQListWidget(QListWidget):
    """Provide the app Qt list widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQListWidget."""
        super().__init__(*args, **kwargs)

    @property
    def selectedIndex(self):
        """Return the selected index value."""
        return sorted(list(set(index.row() for index in self.selectedIndexes())))


class AppQMainWindow(
    Mixins.QTranslatable,
    Mixins.ConnectionAware,
    Mixins.CleanupOnExit,
    QMainWindow,
):
    """Present the app q main window."""

    _openWindows = {}

    @staticmethod
    def _releaseOpenWindow(key, *_args):
        """Release a shown main window after it closes or is destroyed."""
        AppQMainWindow._openWindows.pop(key, None)

    def __init__(self, *args, **kwargs):
        """Initialize the AppQMainWindow."""
        super().__init__(*args, **kwargs)

        @callOnceOnly
        def connect(key):
            """Connect the lifetime release signal once."""
            release = functools.partial(AppQMainWindow._releaseOpenWindow, key)
            self.destroyed.connect(release)

        @callOnceOnly
        def firstShow():
            """Apply the first-show sizing once."""
            self.setWidthAndHeight()

        self._connectOnce = connect
        self._firstShow = firstShow

        self.setWindowIcon(AppHue.currentWindowIcon())

        self._menuBar = AppQMenuBar(parent=self)
        self.setMenuBar(self._menuBar)

        if PLATFORM != 'Darwin':
            self.setWidthAndHeight()

    def setWidthAndHeight(self):
        """Apply the default size for the app q main window."""
        pass

    def show(self):
        """Show, position, and retain the window until it closes."""
        key = id(self)
        AppQMainWindow._openWindows[key] = self

        self._connectOnce(key)

        try:
            super().show()
        except Exception:
            # Any non-exit exceptions

            AppQMainWindow._releaseOpenWindow(key)

            raise

        if PLATFORM == 'Darwin':
            self._firstShow()

        moveToCenter(self)

        APP().processEvents()

        if PLATFORM == 'Darwin':
            self.activateWindow()
            self.raise_()

    def event(self, event):
        """Release this window after Qt accepts its close event."""
        closes = event.type() == QtCore.QEvent.Type.Close
        result = super().event(event)

        if closes and event.isAccepted():
            AppQMainWindow._releaseOpenWindow(id(self))

        return result

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

    _openMessageBoxes = {}

    @staticmethod
    def _releaseOpenMessageBox(key, *_args):
        """Release an asynchronously opened message box after it finishes."""
        AppQMessageBox._openMessageBoxes.pop(key, None)

    def __init__(self, *args, **kwargs):
        """Initialize the AppQMessageBox."""
        super().__init__(*args, **kwargs)

        @callOnceOnly
        def connect(key):
            """Connect the lifetime release signals once."""
            release = functools.partial(AppQMessageBox._releaseOpenMessageBox, key)

            self.finished.connect(release)
            self.destroyed.connect(release)

        self._connectOnce = connect

        self.setWindowIcon(AppHue.currentWindowIcon())

    def moveToCenter(self):
        """Move to center."""
        moveToCenter(self, self.parentWidget())

        return self

    def show(self):
        """Show the app q message box."""
        return super().show()

    def exec(self):
        """Show and execute the app q message box modally."""
        self.show()
        self.moveToCenter()

        return super().exec()

    def open(self):
        """Open and retain the message box until it finishes or is destroyed."""
        key = id(self)
        AppQMessageBox._openMessageBoxes[key] = self

        self._connectOnce(key)

        try:
            self.show()
            self.moveToCenter()

            return super().open()
        except Exception:
            # Any non-exit exceptions

            AppQMessageBox._releaseOpenMessageBox(key)

            raise

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


class IconTextPushButton(QPushButton):
    """Present a push-button icon and label through an explicit layout."""

    def __init__(
        self,
        *args,
        iconTextSpacing=12,
        horizontalMargin=13,
        verticalMargin=3,
        iconSize=QtCore.QSize(16, 16),
        **kwargs,
    ):
        """Initialize layout-managed icon and text presentation."""
        icon = kwargs.pop('icon', None)

        super().__init__(*args, **kwargs)

        text = QPushButton.text(self)

        QPushButton.setText(self, '')
        QPushButton.setIcon(self, QIcon())
        QPushButton.setIconSize(self, iconSize)

        self._text = ''
        self._icon = QIcon()

        self._iconLabel = QLabel(parent=self)
        self._iconLabel.setObjectName('IconTextPushButtonIcon')
        self._iconLabel.setFixedSize(iconSize)
        self._iconLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._iconLabel.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self._textLabel = QLabel(parent=self)
        self._textLabel.setObjectName('IconTextPushButtonText')
        self._textLabel.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self._iconTextLayout = QHBoxLayout(self)
        self._iconTextLayout.setContentsMargins(
            horizontalMargin,
            verticalMargin,
            horizontalMargin,
            verticalMargin,
        )
        self._iconTextLayout.setSpacing(iconTextSpacing)
        self._iconTextLayout.addWidget(self._iconLabel)
        self._iconTextLayout.addWidget(self._textLabel)
        self._iconTextLayout.addStretch()

        self.setText(text)

        if icon is not None:
            self.setIcon(icon)

    def setIcon(self, icon: QIcon):
        """Render *icon* in the layout-managed icon label."""
        self._icon = icon
        self._iconLabel.setPixmap(icon.pixmap(self.iconSize()))

    def icon(self) -> QIcon:
        """Return the displayed icon."""
        return self._icon

    def setIconSize(self, size: QtCore.QSize):
        """Resize and rerender the layout-managed icon."""
        QPushButton.setIconSize(self, size)

        if not hasattr(self, '_iconLabel'):
            return

        self._iconLabel.setFixedSize(size)
        self._iconLabel.setPixmap(self._icon.pixmap(size))

    def setText(self, text: str):
        """Set the visible and accessible button label."""
        self._text = text
        self._textLabel.setText(text)
        self.setAccessibleName(text)
        self.updateGeometry()

    def text(self) -> str:
        """Return the button label."""
        return self._text

    def setTextVisible(self, visible: bool):
        """Set whether the text label participates in the layout."""
        self._textLabel.setVisible(visible)
        self.updateGeometry()

    def iconTextSpacing(self) -> int:
        """Return the space between the icon and text label."""
        return self._iconTextLayout.spacing()

    def sizeHint(self):
        """Include the managed icon and text layout in the preferred size."""
        baseHint = super().sizeHint()
        layoutHint = self._iconTextLayout.sizeHint()

        return QtCore.QSize(
            max(baseHint.width(), layoutHint.width()),
            max(baseHint.height(), layoutHint.height()),
        )


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


class AppQIconTextPushButton(
    Mixins.QTranslatable,
    Mixins.ThemeAware,
    IconTextPushButton,
):
    """Provide a theme-aware application icon-text push button."""

    def __init__(self, *args, **kwargs):
        """Initialize a button with an optional application icon."""
        icon = kwargs.pop('icon', None)
        super().__init__(*args, **kwargs)

        self.iconFileName = ''

        if icon is not None:
            self.setIcon(icon)

    def setIconByTheme(self, theme):
        """Apply the stored application icon for *theme*."""
        if not self.iconFileName:
            return

        if AppSettings.isStateON_('DarkMode'):
            IconTextPushButton.setIcon(
                self,
                bootstrapIconWhite(self.iconFileName),
            )

            return

        if theme == 'Dark':
            if PLATFORM == 'Windows' and versionToValue(
                PYSIDE6_VERSION
            ) < versionToValue('6.7.0'):
                icon = bootstrapIcon(self.iconFileName)
            else:
                icon = bootstrapIconWhite(self.iconFileName)
        else:
            icon = bootstrapIcon(self.iconFileName)

        IconTextPushButton.setIcon(self, icon)

    def setIcon(self, icon: AppQIcon):
        """Store an application icon and apply its themed variant."""
        self.iconFileName = AppQPushButton.getIconFileName(icon.iconFileName)

        if not self.iconFileName:
            IconTextPushButton.setIcon(self, icon)
        else:
            self.setIconByTheme(APP().theme())

    def themeChangedCallback(self, theme):
        """Refresh the icon after an application theme change."""
        self.setIconByTheme(theme)

    def retranslate(self):
        """Refresh translated button text."""
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


class AppQTableView(QTableView):
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
            AppConnectionController().startReconnection()
        else:
            # Do nothing
            pass

    try:
        method = kwargs.pop('method', 'open')

        if AppConnectionController().isConnected():
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
            controller, wasConnected = (
                AppRoutingController(),
                AppConnectionController().isConnected(),
            )

            changed = controller.selectRouting(AppBuiltinRouting.Global.value)

            if changed or controller.routing == AppBuiltinRouting.Global.value:
                # Selecting a route reconnects an established connection itself.
                # During an initial connection attempt, resume that attempt here.
                if not wasConnected:
                    AppConnectionController().startConnection()
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
