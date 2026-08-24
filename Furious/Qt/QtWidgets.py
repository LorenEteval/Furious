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
from Furious.Qt.Signals import connectWeakly

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union

import functools

__all__ = [
    'moveToCenter',
    'AppQSwitch',
    'AppQComboBox',
    'AppQComboBoxSeparatorDelegate',
    'AppQDialog',
    'AppQTransientDialog',
    'AppQDialogButtonBox',
    'AppQGroupBox',
    'AppQHeaderView',
    'AppQLabel',
    'AppQLineEdit',
    'AppQListView',
    'AppQMainWindow',
    'AppQMenu',
    'AppQMenuBar',
    'AppQMessageBox',
    'AppQIconTextPushButton',
    'AppQMenuPushButton',
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


class AppQSwitch(Mixins.ThemeAware, QCheckBox):
    """Paint one compact, animated Fluent-style binary switch."""

    ControlSize = QtCore.QSize(38, 22)
    CompactControlSize = QtCore.QSize(34, 20)
    AnimationDuration = 160

    def __init__(self, parent=None, *, compact=False):
        """Initialize the reusable switch and its owned thumb animation."""
        super().__init__(parent)

        self.setObjectName('SettingsToggle')
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.CompactControlSize if compact else self.ControlSize)

        self._thumbPosition = 0.0

        self._animation = QtCore.QPropertyAnimation(
            self,
            b'thumbPosition',
            parent=self,
        )
        self._animation.setDuration(self.AnimationDuration)
        self._animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        connectWeakly(self.toggled, self, '_animateToggle')

    def _getThumbPosition(self) -> float:
        """Return the normalized thumb position used by the animation."""
        return self._thumbPosition

    def _setThumbPosition(self, position: float):
        """Update the animated thumb position and repaint the switch."""
        self._thumbPosition = min(max(float(position), 0.0), 1.0)
        self.update()

    thumbPosition = QtCore.Property(
        float,
        _getThumbPosition,
        _setThumbPosition,
    )

    @QtCore.Slot(bool)
    def _animateToggle(self, checked: bool):
        """Animate the Fluent thumb and track to the requested state."""
        self._animation.stop()
        self._animation.setStartValue(self._thumbPosition)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def syncChecked(self, checked: bool):
        """Synchronize external state without playing an entrance animation."""
        blocker = QtCore.QSignalBlocker(self)

        self.setChecked(bool(checked))
        self._animation.stop()
        self._setThumbPosition(1.0 if checked else 0.0)

        del blocker

    @staticmethod
    def _blendColor(start, end, progress: float) -> QColor:
        """Interpolate two theme colors for a smooth track transition."""
        startColor, endColor = QColor(start), QColor(end)

        return QColor.fromRgbF(
            startColor.redF() + (endColor.redF() - startColor.redF()) * progress,
            startColor.greenF() + (endColor.greenF() - startColor.greenF()) * progress,
            startColor.blueF() + (endColor.blueF() - startColor.blueF()) * progress,
            startColor.alphaF() + (endColor.alphaF() - startColor.alphaF()) * progress,
        )

    def paintEvent(self, event):
        """Draw the theme-aware track and animated thumb."""
        del event

        palette = AppStyleSheet.Palettes[APP().theme()]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = QtCore.QRectF(1, 2, self.width() - 2, self.height() - 4)
        radius = track.height() / 2

        if not self.isEnabled():
            background, border, thumb = (
                palette['raised'],
                palette['border'],
                palette['disabled'],
            )
        else:
            background, border, thumb = (
                self._blendColor(
                    palette['raised'],
                    palette['accent'],
                    self._thumbPosition,
                ),
                self._blendColor(
                    palette['border_strong'],
                    palette['accent'],
                    self._thumbPosition,
                ),
                self._blendColor(
                    palette['muted'],
                    palette['accent_text'],
                    self._thumbPosition,
                ),
            )

        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(track, radius, radius)

        thumbDiameter = track.height() - 6
        thumbStart = track.left() + 3
        thumbEnd = track.right() - thumbDiameter - 3
        thumbX = thumbStart + ((thumbEnd - thumbStart) * self._thumbPosition)
        thumbRect = QtCore.QRectF(
            thumbX,
            track.top() + 3,
            thumbDiameter,
            thumbDiameter,
        )

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QColor(thumb))
        painter.drawEllipse(thumbRect)

        if self.hasFocus():
            focusRect = track.adjusted(-0.5, -0.5, 0.5, 0.5)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(palette['accent']), 1))
            painter.drawRoundedRect(focusRect, radius, radius)

    def themeChangedCallback(self, _theme: str):
        """Repaint the custom-drawn control for the active theme."""
        self.update()


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

    def setContentWidthAdjustable(self, adjustable: bool = True):
        """Opt into content-aware width hints without imposing a fixed width."""
        policy = (
            QComboBox.SizeAdjustPolicy.AdjustToContents
            if adjustable
            else QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )

        self.setSizeAdjustPolicy(policy)
        self.refreshContentGeometry()

    def refreshContentGeometry(self):
        """Notify the owning layout that changed item text may need more width."""
        self.updateGeometry()
        self.view().updateGeometry()

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

        self.refreshContentGeometry()


class AppQDialog(Mixins.QTranslatable, Mixins.ConnectionAware, QDialog):
    """Present the app Qt dialog."""

    DEFAULT_DIALOG_SIZE, FIXED_DIALOG_SIZE = (
        QtCore.QSize(),
        QtCore.QSize(),
    )

    _openDialogs = {}
    RETAIN_UNTIL_DESTROYED = False

    @staticmethod
    def _releaseOpenDialog(key, *_args):
        """Release an asynchronously opened dialog after its owned lifetime."""
        AppQDialog._openDialogs.pop(key, None)

    @staticmethod
    def _scheduleOpenDialogRelease(key, *_args):
        """Release an async wrapper after the current Qt signal dispatch."""
        QtCore.QTimer.singleShot(
            0,
            functools.partial(AppQDialog._releaseOpenDialog, key),
        )

    def __init__(self, *args, **kwargs):
        """Initialize the AppQDialog."""
        super().__init__(*args, **kwargs)

        # Use a per-instance token rather than id(self).  A finished transient
        # can release its Python wrapper before Qt processes deleteLater(); an
        # ID reused by a newer dialog must not let the older destroyed signal
        # evict that newer dialog from the asynchronous lifetime registry.
        self._lifetimeKey = object()

        # Signal callbacks carry only the lifetime token, never this dialog.
        # That avoids a Python self-cycle around the complete native widget tree.
        # A reusable QDialog merely hides when it finishes, so its async owner
        # can release it after that signal dispatch. A delete-on-close dialog is
        # different: finished precedes deferred native destruction. Keep that
        # wrapper strongly owned until destruction has fully returned to Qt.
        scheduleRelease = functools.partial(
            AppQDialog._scheduleOpenDialogRelease,
            self._lifetimeKey,
        )

        if not self.RETAIN_UNTIL_DESTROYED:
            self.finished.connect(scheduleRelease)

        self.destroyed.connect(scheduleRelease)

        self.setWindowIcon(AppHue.currentWindowIcon())

    def prepareInitialGeometry(self):
        """Apply declarative geometry before the first native presentation."""
        if self.FIXED_DIALOG_SIZE.isValid():
            self.setFixedSize(self.FIXED_DIALOG_SIZE)
        elif self.DEFAULT_DIALOG_SIZE.isValid():
            self.resize(self.DEFAULT_DIALOG_SIZE)

    @callOnceOnly
    def _prepareInitialGeometry(self):
        """Prepare initial geometry exactly once after subclass construction."""
        self.prepareInitialGeometry()

    def centerForPresentation(self):
        """Center this dialog after each native presentation."""
        moveToCenter(self)

    def exec(self):
        """Prepare and execute the app Qt dialog modally."""
        self._prepareInitialGeometry()

        return super().exec()

    def open(self):
        """Open and retain the dialog until it finishes or is destroyed."""
        key = self._lifetimeKey
        AppQDialog._openDialogs[key] = self

        try:
            self._prepareInitialGeometry()

            return super().open()
        except Exception:
            # Any non-exit exceptions

            AppQDialog._releaseOpenDialog(key)

            raise

    def show(self):
        """Prepare and show the app Qt dialog."""
        self._prepareInitialGeometry()

        super().show()

    def showEvent(self, event):
        """Center the dialog after each native show on every platform."""
        super().showEvent(event)

        self.centerForPresentation()

    def retranslate(self):
        """Refresh translated text for the app Qt dialog."""
        self.setWindowTitle(_(self.windowTitle()))

    def disconnectedCallback(self):
        """Update the app Qt dialog for a disconnected state."""
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        """Update the app Qt dialog for a connected state."""
        self.setWindowIcon(AppHue.connectedWindowIcon())


class AppQTransientDialog(AppQDialog):
    """Present a one-shot dialog that destroys its Qt object when closed."""

    RETAIN_UNTIL_DESTROYED = True

    def __init__(self, *args, **kwargs):
        """Initialize a dialog whose accepted/rejected lifetime is transient."""
        super().__init__(*args, **kwargs)

        # QDialog normally hides on accept/reject.  A long-lived Qt parent then
        # keeps each closed dialog in its child tree indefinitely.  Transient
        # dialogs opt into native deletion so both Qt and Python ownership end.
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)


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


class _AppQItemViewSelectionDelegate(QStyledItemDelegate):
    """Paint a Fluent-style rounded item selection."""

    HorizontalInset = 4
    VerticalInset = 2
    Radius = 5

    def _selectionRect(self, option):
        """Return the rounded selection rectangle for one list item."""
        return QtCore.QRectF(option.rect).adjusted(
            self.HorizontalInset,
            self.VerticalInset,
            -self.HorizontalInset,
            -self.VerticalInset,
        )

    @staticmethod
    def _selectionColor(option):
        """Return the active or inactive theme-aware selection color."""
        colorName = (
            'selection' if option.state & QStyle.StateFlag.State_Active else 'raised'
        )

        try:
            return QColor(AppStyleSheet.paletteForTheme(APP().theme())[colorName])
        except (AttributeError, RuntimeError):
            return option.palette.color(QPalette.ColorRole.Highlight)

    def paint(self, painter, option, index):
        """Paint the rounded selection before native item contents."""
        if option.state & QStyle.StateFlag.State_Selected:
            selectionRect = self._selectionRect(option)

            if not selectionRect.isEmpty():
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setClipRect(option.rect)
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(self._selectionColor(option))
                painter.drawRoundedRect(selectionRect, self.Radius, self.Radius)
                painter.restore()

        super().paint(painter, option, index)


class _AppQTableSelectionDelegate(_AppQItemViewSelectionDelegate):
    """Paint one rounded background across a selected table row."""

    def _selectionRect(self, option):
        """Return the full visible-column span for the option's row."""
        table = self.parent()
        header = table.horizontalHeader()
        sections = [
            logical
            for logical in range(header.count())
            if not header.isSectionHidden(logical)
        ]

        if not sections:
            return QtCore.QRectF()

        left, right = (
            min(header.sectionViewportPosition(logical) for logical in sections),
            max(
                header.sectionViewportPosition(logical) + header.sectionSize(logical)
                for logical in sections
            ),
        )

        return QtCore.QRectF(
            left + self.HorizontalInset,
            option.rect.top() + self.VerticalInset,
            max(0, right - left - (2 * self.HorizontalInset)),
            max(0, option.rect.height() - (2 * self.VerticalInset)),
        )


def _installRoundedSelectionDelegate(view, delegateType):
    """Install one persistent, view-owned rounded selection delegate."""
    view.setProperty('selectionShape', 'rounded')
    view.selectionDelegate = delegateType(parent=view)
    view.setItemDelegate(view.selectionDelegate)


class AppQListView(QListView):
    """Provide a model-based app Qt list view."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQListView."""
        super().__init__(*args, **kwargs)

        _installRoundedSelectionDelegate(self, _AppQItemViewSelectionDelegate)

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

    DEFAULT_WINDOW_SIZE = QtCore.QSize()
    CENTER_ON_INITIAL_SHOW = True

    _openWindows = {}

    @staticmethod
    def _releaseOpenWindow(key, *_args):
        """Release a shown main window after it closes or is destroyed."""
        AppQMainWindow._openWindows.pop(key, None)

    def __init__(self, *args, **kwargs):
        """Initialize the AppQMainWindow."""
        super().__init__(*args, **kwargs)

        self._lifetimeKey = object()
        self._initialPositionAuthoritative = False

        release = functools.partial(
            AppQMainWindow._releaseOpenWindow,
            self._lifetimeKey,
        )
        self.destroyed.connect(release)

        self.setWindowIcon(AppHue.currentWindowIcon())

        self._menuBar = AppQMenuBar(parent=self)
        self.setMenuBar(self._menuBar)

    def prepareInitialGeometry(self):
        """Apply declarative default geometry before the first native show."""
        if self.DEFAULT_WINDOW_SIZE.isValid():
            self.resize(self.DEFAULT_WINDOW_SIZE)

    def restoreInitialGeometry(self, geometry) -> bool:
        """Restore saved geometry and mark its position as authoritative."""
        restored = bool(self.restoreGeometry(geometry))

        if restored:
            self._initialPositionAuthoritative = True

        return restored

    def shouldCenterOnInitialShow(self) -> bool:
        """Return whether the first show should center this window."""
        return self.CENTER_ON_INITIAL_SHOW and not self._initialPositionAuthoritative

    @callOnceOnly
    def _prepareInitialGeometry(self):
        """Prepare initial geometry once after subclass construction."""
        self.prepareInitialGeometry()

    @callOnceOnly
    def _centerOnInitialShow(self):
        """Apply the initial centering policy once after native presentation."""
        if self.shouldCenterOnInitialShow():
            moveToCenter(self)

    def show(self):
        """Show, position, and retain the window until it closes."""
        self._prepareInitialGeometry()

        key = self._lifetimeKey
        AppQMainWindow._openWindows[key] = self

        try:
            super().show()
        except Exception:
            # Any non-exit exceptions

            AppQMainWindow._releaseOpenWindow(key)

            raise

        self._centerOnInitialShow()

        # Preserve the established synchronous post-show flush for callers;
        # initial geometry and centering above do not depend on this event pump.
        APP().processEvents()

        if PLATFORM == 'Darwin':
            self.activateWindow()
            self.raise_()

    def event(self, event):
        """Release this window after Qt accepts its close event."""
        closes = event.type() == QtCore.QEvent.Type.Close
        result = super().event(event)

        if closes and event.isAccepted():
            AppQMainWindow._releaseOpenWindow(self._lifetimeKey)

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
        menuRole = kwargs.pop('menuRole', '')

        super().__init__(**kwargs)

        # In some old version PySide6, the self.actions() method
        # does not return with seperators. _actions list append
        # them all
        self._actions = []

        for action in actions:
            if isinstance(action, AppQSeparator):
                self._actions.append(action)
                self.addSeparator()
            elif isinstance(action, AppQAction):
                self._actions.append(action)
                self.addAction(action)
            else:
                # Do nothing
                pass

        if menuRole:
            self.setMenuRole(menuRole)

    def setMenuRole(self, role: str, recursive=False):
        """Apply a reusable visual role to this menu and its submenus."""
        self.setProperty('menuRole', str(role))

        if recursive:
            for action in self.actions():
                submenu = action.menu() if hasattr(action, 'menu') else None

                if isinstance(submenu, AppQMenu):
                    submenu.setMenuRole(role, recursive=True)

        # Dynamic properties participate in QSS selector matching only after
        # the widget is repolished when an application stylesheet is active.
        style = self.style()
        style.unpolish(self)
        style.polish(self)

        self.update()

    def retranslate(self):
        """Refresh translated text for the app q menu."""
        self.setTitle(_(self.title()))


class AppQMenuBar(QMenuBar):
    """Represent app q menu bar."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQMenuBar."""
        super().__init__(*args, **kwargs)


class _AppMessageBoxMask(QFrame):
    """Dim the owning window while a Fluent message box is active."""

    def __init__(self, parent):
        """Cover *parent* without participating in its layout."""
        super().__init__(parent)

        self.setObjectName('AppMessageBoxMask')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setGeometry(parent.rect())

        parent.installEventFilter(self)

    def eventFilter(self, watched, event):
        """Follow the owning window when it is resized."""
        if watched is self.parentWidget() and event.type() == QtCore.QEvent.Type.Resize:
            self.setGeometry(watched.rect())

        return super().eventFilter(watched, event)

    def dispose(self):
        """Detach from the long-lived owner before scheduling destruction."""
        owner = self.parentWidget()

        if owner is not None:
            try:
                owner.removeEventFilter(self)
            except RuntimeError:
                # The owner can be destroyed as part of the same close path.
                pass

        self.deleteLater()


class AppQMessageBox(AppQTransientDialog):
    """Present a Fluent message box with separate metadata and visible layers.

    ``title``/``windowTitle`` remain native window metadata for compatibility;
    ``heading``, ``text``, and ``informativeText`` form the visible hierarchy.
    """

    Icon = QMessageBox.Icon
    StandardButton = QMessageBox.StandardButton
    StandardButtons = QMessageBox.StandardButtons
    ButtonRole = QMessageBox.ButtonRole

    buttonClicked = QtCore.Signal(QAbstractButton)

    ButtonSpacing = 14
    ButtonMinimumWidth = 104
    ButtonMaximumWidth = 220
    SingleActionBaseWidth = 380
    DoubleActionBaseWidth = 460
    MultipleActionBaseWidth = 520
    MaximumSurfaceWidth = 720

    # AppQDialog already wires a cleanup callback for its asynchronous registry.
    # This message-box-specific registry repeats that cleanup so open() can bypass
    # AppQDialog.open() while preserving QMessageBox-compatible show behavior.
    # The duplicate cleanup is harmless and idempotent, but future changes must
    # keep both registries synchronized or consolidate them deliberately.
    _openMessageBoxes = {}
    _standardButtonOrder = (
        StandardButton.Ok,
        StandardButton.Save,
        StandardButton.SaveAll,
        StandardButton.Open,
        StandardButton.Yes,
        StandardButton.YesToAll,
        StandardButton.No,
        StandardButton.NoToAll,
        StandardButton.Abort,
        StandardButton.Retry,
        StandardButton.Ignore,
        StandardButton.Close,
        StandardButton.Cancel,
        StandardButton.Discard,
        StandardButton.Help,
        StandardButton.Apply,
        StandardButton.Reset,
        StandardButton.RestoreDefaults,
    )

    @staticmethod
    def _releaseOpenMessageBox(key, *_args):
        """Release an asynchronously opened message box after destruction."""
        AppQMessageBox._openMessageBoxes.pop(key, None)

    @staticmethod
    def _scheduleOpenMessageBoxRelease(key, *_args):
        """Release an async message box after destroyed-signal dispatch."""
        QtCore.QTimer.singleShot(
            0,
            functools.partial(AppQMessageBox._releaseOpenMessageBox, key),
        )

    def __init__(self, *args, **kwargs):
        """Initialize the message box while preserving QMessageBox arguments."""
        windowTitle = kwargs.pop('windowTitle', None)

        icon, parent, title, heading, text, buttons = (
            kwargs.pop('icon', self.Icon.NoIcon),
            kwargs.pop('parent', None),
            kwargs.pop(
                'title',
                APPLICATION_NAME if windowTitle is None else windowTitle,
            ),
            kwargs.pop('heading', ''),
            kwargs.pop('text', ''),
            kwargs.pop('buttons', self.StandardButton.NoButton),
        )

        if args:
            if isinstance(args[0], self.Icon):
                icon = args[0]
                title = args[1] if len(args) > 1 else title
                text = args[2] if len(args) > 2 else text
                buttons = args[3] if len(args) > 3 else buttons
                parent = args[4] if len(args) > 4 else parent
            else:
                parent = args[0]

        super().__init__(parent=parent, **kwargs)

        self._lifetimeKey = object()
        self._windowMask = None
        self._icon = self.Icon.NoIcon
        self._heading = ''
        self._text = ''
        self._informativeText = ''
        self._minimumContentWidth = 0
        self._standardButtons = self.StandardButton.NoButton
        self._standardButtonMap = {}
        self._buttonRoles = {}
        self._defaultButton = None
        self._escapeButton = None
        self._clickedButton = None
        self._handlingButton = False

        scheduleRelease = functools.partial(
            AppQMessageBox._scheduleOpenMessageBoxRelease,
            self._lifetimeKey,
        )

        # Message boxes are delete-on-close. Their asynchronous owner releases
        # them only after native destruction and its signal dispatch complete.
        self.destroyed.connect(scheduleRelease)

        self.setObjectName('AppMessageBox')

        windowFlags = (
            QtCore.Qt.WindowType.Window
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.NoDropShadowWindowHint
        )
        self.setWindowFlags(windowFlags)

        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setAutoFillBackground(False)

        windowPalette = self.palette()
        windowPalette.setColor(
            QPalette.ColorRole.Window,
            QColor(QtCore.Qt.GlobalColor.transparent),
        )
        self.setPalette(windowPalette)

        self.setModal(True)

        self.surface = QFrame(self)
        self.surface.setObjectName('AppMessageBoxSurface')

        self.contentFrame = QFrame(self.surface)
        self.contentFrame.setObjectName('AppMessageBoxContent')

        self.iconLabel = QLabel(self.contentFrame)
        self.iconLabel.setObjectName('AppMessageBoxIcon')
        self.iconLabel.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop
        )

        self.textViewport = QScrollArea(self.contentFrame)
        self.textViewport.setObjectName('AppMessageBoxTextViewport')
        self.textViewport.setFrameShape(QFrame.Shape.NoFrame)
        self.textViewport.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.textViewport.setWidgetResizable(False)

        self.textWidget = QWidget()
        self.textWidget.setObjectName('AppMessageBoxTextWidget')

        self.headingLabel = QLabel(self.textWidget)
        self.headingLabel.setObjectName('AppMessageBoxHeading')
        self.headingLabel.setWordWrap(False)
        self.headingLabel.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.headingLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.textLabel = QLabel(self.textWidget)
        self.textLabel.setObjectName('AppMessageBoxText')
        self.textLabel.setWordWrap(True)
        self.textLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.informativeLabel = QLabel(self.textWidget)
        self.informativeLabel.setObjectName('AppMessageBoxBody')
        self.informativeLabel.setWordWrap(True)
        self.informativeLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.textLayout = QVBoxLayout(self.textWidget)
        self.textLayout.setContentsMargins(0, 0, 0, 0)
        self.textLayout.setSpacing(8)
        self.textLayout.addWidget(self.headingLabel)
        self.textLayout.addWidget(self.textLabel)
        self.textLayout.addWidget(self.informativeLabel)

        self.textViewport.setWidget(self.textWidget)

        self.contentLayout = QHBoxLayout(self.contentFrame)
        self.contentLayout.setContentsMargins(28, 24, 28, 22)
        self.contentLayout.setSpacing(18)
        self.contentLayout.addWidget(
            self.iconLabel,
            0,
            QtCore.Qt.AlignmentFlag.AlignTop,
        )
        self.contentLayout.addWidget(self.textViewport, 1)

        self.buttonFrame = QFrame(self.surface)
        self.buttonFrame.setObjectName('AppMessageBoxButtonBar')

        self.buttonLayout = QHBoxLayout(self.buttonFrame)
        self.buttonLayout.setContentsMargins(24, 14, 24, 14)
        self.buttonLayout.setSpacing(self.ButtonSpacing)

        self.surfaceLayout = QVBoxLayout(self.surface)
        self.surfaceLayout.setContentsMargins(0, 0, 0, 0)
        self.surfaceLayout.setSpacing(0)
        self.surfaceLayout.addWidget(self.contentFrame)
        self.surfaceLayout.addWidget(self.buttonFrame)

        self.dialogLayout = QVBoxLayout(self)
        self.dialogLayout.setContentsMargins(0, 0, 0, 0)
        self.dialogLayout.addWidget(self.surface)

        self.setWindowTitle(title)
        self.setHeading(heading)
        self.setText(text)
        self.setIcon(icon)

        if buttons != self.StandardButton.NoButton:
            self.setStandardButtons(buttons)

    @staticmethod
    def _dialogStandardButton(button):
        """Map a QMessageBox standard button to QDialogButtonBox."""
        return getattr(QDialogButtonBox.StandardButton, button.name)

    def _standardButtonText(self, standardButton):
        """Use Qt's translated platform text for a standard button."""
        btnBox = QDialogButtonBox(self._dialogStandardButton(standardButton))
        result = btnBox.button(self._dialogStandardButton(standardButton)).text()

        btnBox.deleteLater()

        return result

    def _createButton(self, text, role, standardButton=None):
        """Create and register one semantic action button."""
        button = QPushButton(str(text), self.buttonFrame)
        button.setMinimumHeight(34)
        button.setAttribute(QtCore.Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

        connectWeakly(
            button.clicked,
            self,
            '_handleButtonClicked',
            sender=button,
            forwardSender=True,
        )

        self._buttonRoles[button] = role

        if standardButton is not None:
            self._standardButtonMap[standardButton] = button

        self._rebuildButtonLayout()

        return button

    def _rebuildButtonLayout(self):
        """Lay out actions with Fluent-style margins and equal stretch."""
        while self.buttonLayout.count():
            self.buttonLayout.takeAt(0)

        buttons = self.buttons()

        if len(buttons) == 1:
            # A single action occupies the middle third of the footer while
            # remaining bounded by its translated size and maximum width.
            self.buttonLayout.addStretch(1)
            self.buttonLayout.addWidget(buttons[0], 1)
            self.buttonLayout.addStretch(1)
        else:
            # This mirrors the standard Qt composition used by Fluent
            # dialogs: every action shares the available row evenly and the
            # layout's spacing provides a stable visual gap.
            for button in buttons:
                self.buttonLayout.addWidget(button, 1)

        self._refreshButtonRoles()

    def _preferredButtonWidth(self, button):
        """Return a slim button width that accommodates translated text."""
        iconWidth = button.iconSize().width() + 8 if not button.icon().isNull() else 0
        naturalWidth = button.fontMetrics().horizontalAdvance(button.text()) + 40

        return max(
            self.ButtonMinimumWidth,
            min(self.ButtonMaximumWidth, naturalWidth + iconWidth),
        )

    def _preferredButtonRowWidth(self):
        """Return the equal-width row required by translated action labels."""
        buttons = self.buttons()

        if not buttons:
            return 0

        if len(buttons) == 1:
            return self._preferredButtonWidth(buttons[0])

        return (
            max(self._preferredButtonWidth(button) for button in buttons) * len(buttons)
            + max(0, len(buttons) - 1) * self.ButtonSpacing
        )

    def _applyButtonWidths(self, surfaceWidth):
        """Apply bounded single-action or equal expanding button policies."""
        buttons = self.buttons()

        if not buttons:
            return

        if len(buttons) == 1:
            button = buttons[0]
            button.setMinimumWidth(self._preferredButtonWidth(button))
            button.setMaximumWidth(self.ButtonMaximumWidth)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
        else:
            margins = self.buttonLayout.contentsMargins()
            availableWidth = max(
                len(buttons),
                surfaceWidth
                - margins.left()
                - margins.right()
                - self.ButtonSpacing * (len(buttons) - 1),
            )
            constrainedMinimum = min(
                self.ButtonMinimumWidth,
                availableWidth // len(buttons),
            )

            for button in buttons:
                button.setMinimumWidth(constrainedMinimum)
                button.setMaximumWidth(self.MaximumSurfaceWidth)
                button.setSizePolicy(
                    QSizePolicy.Policy.Expanding,
                    QSizePolicy.Policy.Fixed,
                )

        self.buttonLayout.invalidate()

    def _refreshButtonRoles(self):
        """Choose primary, secondary, and destructive Fluent presentations."""
        buttons = self.buttons()
        primaryButton = self._defaultButton

        if primaryButton is None:
            primaryButton = next(
                (
                    button
                    for button in buttons
                    if self.buttonRole(button)
                    in (
                        self.ButtonRole.AcceptRole,
                        self.ButtonRole.YesRole,
                    )
                ),
                buttons[0] if buttons else None,
            )

        for button in buttons:
            role = self.buttonRole(button)

            if role == self.ButtonRole.DestructiveRole:
                visualRole = 'destructive'
            elif button is primaryButton:
                visualRole = 'primary'
            else:
                visualRole = 'secondary'

            button.setProperty('messageBoxRole', visualRole)

            style = button.style()
            style.unpolish(button)
            style.polish(button)

    def _ensureButtons(self):
        """Match QMessageBox by supplying OK when no actions were configured."""
        if not self.buttons():
            self.setStandardButtons(self.StandardButton.Ok)

    def setHeading(self, heading):
        """Set the optional visible semantic heading."""
        self._heading = str(heading)
        self.headingLabel.setText(self._heading)
        self.headingLabel.setVisible(bool(self._heading))

        if self.isVisible():
            self._updateDialogSize()

    def heading(self):
        """Return the visible semantic heading."""
        return self._heading

    def setText(self, text):
        """Set the primary message text."""
        self._text = str(text)
        self.textLabel.setText(self._text)
        self.textLabel.setVisible(bool(self._text))

        if self.isVisible():
            self._updateDialogSize()

    def text(self):
        """Return the primary message text."""
        return self._text

    def setInformativeText(self, text):
        """Set secondary supporting text."""
        self._informativeText = str(text)
        self.informativeLabel.setText(self._informativeText)
        self.informativeLabel.setVisible(bool(self._informativeText))

        if self.isVisible():
            self._updateDialogSize()

    def informativeText(self):
        """Return secondary supporting text."""
        return self._informativeText

    def setIcon(self, icon):
        """Set the semantic message icon."""
        self._icon = self.Icon(icon)

        standardPixmap = {
            self.Icon.Information: QStyle.StandardPixmap.SP_MessageBoxInformation,
            self.Icon.Warning: QStyle.StandardPixmap.SP_MessageBoxWarning,
            self.Icon.Critical: QStyle.StandardPixmap.SP_MessageBoxCritical,
            self.Icon.Question: QStyle.StandardPixmap.SP_MessageBoxQuestion,
        }.get(self._icon)

        if standardPixmap is None:
            self.iconLabel.clear()
            self.iconLabel.hide()
        else:
            pixmap = self.style().standardIcon(standardPixmap).pixmap(36, 36)

            self.iconLabel.setPixmap(pixmap)
            self.iconLabel.setFixedSize(40, 40)
            self.iconLabel.show()

        if self.isVisible():
            self._updateDialogSize()

    def icon(self):
        """Return the semantic message icon."""
        return self._icon

    def setIconPixmap(self, pixmap):
        """Set a custom message icon pixmap."""
        self._icon = self.Icon.NoIcon
        self.iconLabel.setPixmap(pixmap)
        self.iconLabel.setFixedSize(pixmap.size())
        self.iconLabel.setVisible(not pixmap.isNull())

    def iconPixmap(self):
        """Return the currently displayed icon pixmap."""
        return self.iconLabel.pixmap()

    def addButton(self, button, role=None):
        """Add a standard button or a custom text/role button."""
        if isinstance(button, self.StandardButton):
            standardButton = button

            existing = self._standardButtonMap.get(standardButton)

            if existing is not None:
                return existing

            standardRole = {
                self.StandardButton.Ok: self.ButtonRole.AcceptRole,
                self.StandardButton.Save: self.ButtonRole.AcceptRole,
                self.StandardButton.SaveAll: self.ButtonRole.AcceptRole,
                self.StandardButton.Open: self.ButtonRole.AcceptRole,
                self.StandardButton.Yes: self.ButtonRole.YesRole,
                self.StandardButton.YesToAll: self.ButtonRole.YesRole,
                self.StandardButton.No: self.ButtonRole.NoRole,
                self.StandardButton.NoToAll: self.ButtonRole.NoRole,
                self.StandardButton.Abort: self.ButtonRole.RejectRole,
                self.StandardButton.Retry: self.ButtonRole.AcceptRole,
                self.StandardButton.Ignore: self.ButtonRole.AcceptRole,
                self.StandardButton.Close: self.ButtonRole.RejectRole,
                self.StandardButton.Cancel: self.ButtonRole.RejectRole,
                self.StandardButton.Discard: self.ButtonRole.DestructiveRole,
                self.StandardButton.Help: self.ButtonRole.HelpRole,
                self.StandardButton.Apply: self.ButtonRole.ApplyRole,
                self.StandardButton.Reset: self.ButtonRole.ResetRole,
                self.StandardButton.RestoreDefaults: self.ButtonRole.ResetRole,
            }.get(standardButton, self.ButtonRole.InvalidRole)

            self._standardButtons |= standardButton

            return self._createButton(
                self._standardButtonText(standardButton),
                standardRole,
                standardButton,
            )

        if isinstance(button, QAbstractButton):
            customButton = button
            customButton.setParent(self.buttonFrame)
            customButton.setAttribute(QtCore.Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)

            connectWeakly(
                customButton.clicked,
                self,
                '_handleButtonClicked',
                sender=customButton,
                forwardSender=True,
            )

            self._buttonRoles[customButton] = role
            self._rebuildButtonLayout()

            return customButton

        if role is None:
            raise TypeError('a custom button requires a QMessageBox.ButtonRole')

        return self._createButton(button, role)

    @QtCore.Slot(object, bool)
    def _handleButtonClicked(self, button, _checked=False):
        """Dispatch a child button through sender-based QObject ownership."""
        if isinstance(button, QAbstractButton):
            self._buttonWasClicked(button)

    def removeButton(self, button):
        """Remove one custom or standard button."""
        self._buttonRoles.pop(button, None)

        for standardButton, candidate in tuple(self._standardButtonMap.items()):
            if candidate is button:
                self._standardButtons &= ~standardButton
                self._standardButtonMap.pop(standardButton, None)

        button.setParent(None)
        self._rebuildButtonLayout()

    def buttons(self):
        """Return the registered action buttons in semantic order."""
        return list(self._buttonRoles)

    def button(self, standardButton):
        """Return the button for one standard result."""
        return self._standardButtonMap.get(standardButton)

    def buttonRole(self, button):
        """Return the semantic role registered for *button*."""
        return self._buttonRoles.get(button, self.ButtonRole.InvalidRole)

    def standardButton(self, button):
        """Return the standard result represented by *button*."""
        for standardButton, candidate in self._standardButtonMap.items():
            if candidate is button:
                return standardButton

        return self.StandardButton.NoButton

    def setStandardButtons(self, buttons):
        """Replace the current standard-button set."""
        for button in tuple(self._standardButtonMap.values()):
            self.removeButton(button)
            button.deleteLater()

        requested = self.StandardButtons(buttons)

        for standardButton in self._standardButtonOrder:
            if requested & standardButton:
                self.addButton(standardButton)

    def standardButtons(self):
        """Return the configured standard-button flags."""
        return self.StandardButtons(self._standardButtons)

    def setDefaultButton(self, button):
        """Set the button activated by Return and styled as primary."""
        if isinstance(button, self.StandardButton):
            button = self.button(button)

        self._defaultButton = button

        if button is not None:
            button.setDefault(True)
            button.setFocus()

        self._refreshButtonRoles()

    def defaultButton(self):
        """Return the configured default button."""
        return self._defaultButton

    def setEscapeButton(self, button):
        """Set the button represented by Escape/window close."""
        if isinstance(button, self.StandardButton):
            button = self.button(button)

        self._escapeButton = button

    def escapeButton(self):
        """Return the configured escape button."""
        return self._escapeButton

    def clickedButton(self):
        """Return the action that most recently completed the dialog."""
        return self._clickedButton

    def _buttonWasClicked(self, button):
        """Emit compatibility signals and finish with a QMessageBox result."""
        if self._handlingButton:
            return

        self._handlingButton = True
        self._clickedButton = button

        try:
            self.buttonClicked.emit(button)
        finally:
            self._handlingButton = False

        standardButton = self.standardButton(button)

        if standardButton != self.StandardButton.NoButton:
            result = int(standardButton)
        elif self.buttonRole(button) in (
            self.ButtonRole.RejectRole,
            self.ButtonRole.NoRole,
        ):
            result = int(QDialog.DialogCode.Rejected)
        else:
            result = int(QDialog.DialogCode.Accepted)

        self.done(result)

    def _effectiveEscapeButton(self):
        """Resolve the action used for Escape and window close."""
        if self._escapeButton in self.buttons():
            return self._escapeButton

        return next(
            (
                button
                for button in reversed(self.buttons())
                if self.buttonRole(button)
                in (
                    self.ButtonRole.RejectRole,
                    self.ButtonRole.NoRole,
                )
            ),
            None,
        )

    def reject(self):
        """Complete through the semantic escape action when available."""
        escapeButton = self._effectiveEscapeButton()

        if escapeButton is not None:
            self._buttonWasClicked(escapeButton)
        else:
            self.done(int(QDialog.DialogCode.Rejected))

    def closeEvent(self, event):
        """Avoid a nested close while a button callback is still executing."""
        if self._handlingButton:
            event.ignore()
        else:
            super().closeEvent(event)

    def setContentMinimumWidth(self, width: int):
        """Set a bounded content preference for summary-style messages."""
        self._minimumContentWidth = max(0, int(width))

        if self.isVisible():
            self._updateDialogSize()

    @staticmethod
    def _wrappedHeight(label, width):
        """Return QLabel's wrapped height for a fixed content width."""
        label.setFixedWidth(width)

        height = max(label.fontMetrics().height(), label.heightForWidth(width))

        label.setFixedHeight(height)

        return height

    def _textContentHeight(self, width):
        """Measure visible heading, primary, and supporting text blocks."""
        blocks = (
            (self.headingLabel, self._heading),
            (self.textLabel, self._text),
            (self.informativeLabel, self._informativeText),
        )
        heights = []

        for label, value in blocks:
            if value:
                heights.append(self._wrappedHeight(label, width))
            else:
                label.setFixedHeight(0)

        return sum(heights) + self.textLayout.spacing() * max(0, len(heights) - 1)

    def _updateDialogSize(self):
        """Fit short content compactly and bound translated/long content."""
        # QSS frame widths and button size hints participate in the geometry
        # calculation, so resolve them before the dialog's first native show.
        self.ensurePolished()
        self.surface.ensurePolished()
        self.buttonFrame.ensurePolished()

        for button in self.buttons():
            button.ensurePolished()

        owner = self.parentWidget().window() if self.parentWidget() else None
        screen = self.screen() or QApplication.primaryScreen()

        available = owner.size() if owner is not None else screen.availableSize()

        buttonMargins = self.buttonLayout.contentsMargins()
        preferredButtonsWidth = (
            self._preferredButtonRowWidth()
            + buttonMargins.left()
            + buttonMargins.right()
            + self.surface.frameWidth() * 2
        )
        parentWidthLimit = max(240, available.width() - 24)
        relativeWidthLimit = max(
            240,
            min(
                self.MaximumSurfaceWidth,
                int(available.width() * 0.78),
                parentWidthLimit,
            ),
        )
        # Text wraps at the normal parent-relative limit.  Buttons cannot wrap,
        # so a narrow owner may lend the dialog more width (up to its usable
        # area) when translated action labels require it.
        maximumSurfaceWidth = min(
            self.MaximumSurfaceWidth,
            parentWidthLimit,
            max(relativeWidthLimit, preferredButtonsWidth),
        )
        buttonCount = len(self.buttons())

        if buttonCount <= 1:
            baseSurfaceWidth = self.SingleActionBaseWidth
        elif buttonCount == 2:
            baseSurfaceWidth = self.DoubleActionBaseWidth
        else:
            baseSurfaceWidth = self.MultipleActionBaseWidth

        baseSurfaceWidth = min(baseSurfaceWidth, maximumSurfaceWidth)
        hasIcon = not self.iconLabel.isHidden()
        iconSpace = 58 if hasIcon else 0
        horizontalChrome = 56 + iconSpace
        maximumTextWidth = max(120, maximumSurfaceWidth - horizontalChrome)
        comfortableTextWidth = min(260, maximumTextWidth)

        textWidths = [
            self.headingLabel.fontMetrics().horizontalAdvance(line)
            for line in self._heading.splitlines()
        ]
        textWidths.extend(
            self.textLabel.fontMetrics().horizontalAdvance(line)
            for line in self._text.splitlines() or ['']
        )
        textWidths.extend(
            self.informativeLabel.fontMetrics().horizontalAdvance(line)
            for line in self._informativeText.splitlines()
        )

        naturalTextWidth = max(textWidths or [240]) + 4
        preferredTextWidth = max(
            comfortableTextWidth,
            self._minimumContentWidth - horizontalChrome,
            naturalTextWidth,
        )
        textWidth = min(maximumTextWidth, preferredTextWidth)
        textHeight = self._textContentHeight(textWidth)
        maximumTextHeight = max(
            72,
            min(
                320,
                int(available.height() * 0.46),
                available.height() - 150,
            ),
        )
        needsScrollBar = textHeight > maximumTextHeight

        if needsScrollBar:
            scrollBarWidth = self.style().pixelMetric(
                QStyle.PixelMetric.PM_ScrollBarExtent,
                None,
                self.textViewport,
            )
            textWidth = max(220, textWidth - scrollBarWidth)
            textHeight = self._textContentHeight(textWidth)
        else:
            scrollBarWidth = 0

        viewportHeight = min(textHeight, maximumTextHeight)

        self.textWidget.setFixedSize(textWidth, textHeight)
        self.textViewport.setFixedSize(
            textWidth + scrollBarWidth,
            viewportHeight + 2,
        )

        surfaceWidth = max(
            baseSurfaceWidth,
            horizontalChrome + textWidth + scrollBarWidth,
            preferredButtonsWidth,
        )
        surfaceWidth = min(maximumSurfaceWidth, surfaceWidth)
        contentMargins = self.contentLayout.contentsMargins()
        contentHeight = (
            max(40 if hasIcon else 0, viewportHeight + 2)
            + contentMargins.top()
            + contentMargins.bottom()
        )
        buttonHeight = (
            max(
                (button.sizeHint().height() for button in self.buttons()),
                default=34,
            )
            + buttonMargins.top()
            + buttonMargins.bottom()
        )

        self._applyButtonWidths(surfaceWidth)
        self.contentFrame.setFixedHeight(contentHeight)
        self.buttonFrame.setFixedHeight(buttonHeight)
        self.surface.setFixedSize(surfaceWidth, contentHeight + buttonHeight)
        self.setFixedSize(self.surface.size())

    def _showWindowMask(self):
        """Create one theme-aware mask over the owning window."""
        parent = self.parentWidget()

        if parent is None:
            return

        owner = parent.window()

        if owner is self or not owner.isVisible():
            return

        self._removeWindowMask()
        self._windowMask = _AppMessageBoxMask(owner)
        self._windowMask.show()
        self._windowMask.raise_()

    def _removeWindowMask(self, *_args):
        """Remove the transient mask without retaining its owner."""
        mask = self._windowMask

        self._windowMask = None

        if mask is not None:
            mask.dispose()

    def moveToCenter(self):
        """Move to center."""
        moveToCenter(self, self.parentWidget())

        return self

    def centerForPresentation(self):
        """Center the message box over its owning widget."""
        self.moveToCenter()

    def _prepareForPresentation(self):
        """Refresh adaptive content and owner mask before each presentation."""
        self._ensureButtons()
        self._updateDialogSize()
        self._showWindowMask()

    def show(self):
        """Prepare and show the app q message box."""
        self._prepareForPresentation()

        QDialog.show(self)

    def exec(self):
        """Prepare and execute the app q message box modally."""
        self._prepareForPresentation()

        return QDialog.exec(self)

    def open(self):
        """Open and retain the message box until it finishes or is destroyed."""
        key = self._lifetimeKey
        AppQMessageBox._openMessageBoxes[key] = self

        try:
            self._prepareForPresentation()

            return QDialog.open(self)
        except Exception:
            # Any non-exit exceptions

            AppQMessageBox._releaseOpenMessageBox(key)

            raise

    def done(self, result):
        """Release the dimming mask before completing the transient dialog."""
        self._removeWindowMask()

        QDialog.done(self, result)

    def retranslate(self):
        """Refresh translated text for the app q message box."""
        self.setWindowTitle(_(self.windowTitle()))

        try:
            self.setHeading(_(self.heading()))
        except KeyError:
            # Runtime headings may already be localized by their owning layer.
            pass

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
    @functools.lru_cache(256)
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

        if APP().usesForcedDarkTheme():
            # Explicit dark theme
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
        """Refresh translated text and tooltip for the app q push button."""
        self.setText(_(self.text()))
        self.setToolTip(_(self.toolTip()))


class AppQMenuPushButton(AppQPushButton):
    """Open a popup menu from a regular Fluent-style push button."""

    def __init__(self, *args, popupMenu=None, **kwargs):
        """Initialize a button without Qt's native menu indicator."""
        super().__init__(*args, **kwargs)

        self._popupMenu = None
        self.setPopupMenu(popupMenu)
        self.clicked.connect(self.showPopupMenu)

    def popupMenu(self):
        """Return the menu presented by this button."""
        return self._popupMenu

    def setPopupMenu(self, menu):
        """Set the menu presented below this button."""
        if menu is not None and not isinstance(menu, QMenu):
            raise TypeError('popupMenu must be a QMenu or None')

        self._popupMenu = menu

    @QtCore.Slot()
    def showPopupMenu(self):
        """Open the configured menu immediately below the button."""
        if self._popupMenu is None:
            return

        position = self.mapToGlobal(QtCore.QPoint(0, self.height() + 2))

        self._popupMenu.popup(position)


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

        if APP().usesForcedDarkTheme():
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

        _installRoundedSelectionDelegate(self, _AppQTableSelectionDelegate)

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
            if isinstance(action, AppQSeparator):
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

        self.setHeading(_('Unable to connect'))
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
        self.setHeading(_(self.heading()))
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
