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

"""Provide extensible collapsible navigation for application pages."""

from __future__ import annotations

from Furious.Frozenlib import APP, Mixins
from Furious.Qt import (
    AppStyleSheet,
    IconTextPushButton,
    bootstrapIcon,
    bootstrapIconWhite,
)
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

from dataclasses import dataclass

__all__ = ['NavigationView']


class _NavigationButton(IconTextPushButton):
    """Present one navigation item with layout-managed icon spacing."""

    IconSize = QtCore.QSize(20, 20)
    IconTextSpacing = 12
    HorizontalMargin = 12
    SelectionIndicatorWidth = 3

    def __init__(self, parent=None, *, hasSelectionIndicator=False):
        """Initialize the icon and text presentation."""
        super().__init__(
            parent,
            iconTextSpacing=self.IconTextSpacing,
            horizontalMargin=self.HorizontalMargin,
            verticalMargin=0,
            iconSize=self.IconSize,
        )

        self.selectionIndicator = None

        if hasSelectionIndicator:
            # Qt does not reliably evaluate a button pseudo-state when that
            # state appears on the ancestor side of a descendant QSS selector.
            # Keep the visible label's selected state on the label itself so
            # checked and disabled colors remain independent.
            self._textLabel.setObjectName('NavigationPageButtonText')
            self._textLabel.setProperty('selected', False)

            self.selectionIndicator = QFrame(parent=self)
            self.selectionIndicator.setObjectName('NavigationSelectionIndicator')
            self.selectionIndicator.setFixedWidth(self.SelectionIndicatorWidth)
            self.selectionIndicator.setAttribute(
                QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            self.selectionIndicator.hide()
            self.toggled.connect(self._selectionChanged)

    def setExpanded(self, expanded: bool):
        """Show the text label only in expanded navigation mode."""
        self.setTextVisible(expanded)

    @QtCore.Slot(bool)
    def _selectionChanged(self, selected: bool):
        """Show the independent indicator for a selected page."""
        self._textLabel.setProperty('selected', selected)

        style = self._textLabel.style()
        style.unpolish(self._textLabel)
        style.polish(self._textLabel)

        self._textLabel.update()

        self.selectionIndicator.setVisible(selected)

        if selected:
            self.selectionIndicator.raise_()

    def resizeEvent(self, event):
        """Keep the selection indicator straight along the left edge."""
        super().resizeEvent(event)

        if self.selectionIndicator is not None:
            indicatorHeight = min(self.IconSize.height(), self.height())
            indicatorTop = (self.height() - indicatorHeight) // 2

            self.selectionIndicator.setGeometry(
                0,
                indicatorTop,
                self.SelectionIndicatorWidth,
                indicatorHeight,
            )


@dataclass
class _NavigationPage:
    """Describe one registered page and its navigation control."""

    id: str
    title: str
    iconFileName: str
    widget: QWidget
    button: _NavigationButton
    translatable: bool = True
    placement: str = 'top'


class NavigationView(Mixins.QTranslatable, Mixins.ThemeAware, QWidget):
    """Route registered pages through a collapsible left navigation rail."""

    pageChanged = QtCore.Signal(str)
    expandedChanged = QtCore.Signal(bool)

    CollapsedWidth = 56
    ExpandedWidth = 220
    IconSize = _NavigationButton.IconSize
    AnimationDuration = 150

    def __init__(self, parent=None):
        """Initialize an empty page registry and its navigation controls."""
        super().__init__(parent)

        self._pages: dict[str, _NavigationPage] = {}
        self._currentPageId = ''
        self._expanded = False
        self._navigationWidth = self.CollapsedWidth
        self._outsideClickFilterInstalled = False

        self.setObjectName('NavigationView')

        self.navigationPanel = QFrame(parent=self)
        self.navigationPanel.setObjectName('NavigationPanel')

        self.toggleButton = _NavigationButton(parent=self.navigationPanel)
        self.toggleButton.setObjectName('NavigationToggleButton')
        self.toggleButton.setExpanded(False)
        self.toggleButton.setToolTip(_('Expand Navigation'))
        self.toggleButton.clicked.connect(self.toggleExpanded)

        self.navigationLayout = QVBoxLayout(self.navigationPanel)
        self.navigationLayout.setContentsMargins(6, 8, 6, 8)
        self.navigationLayout.setSpacing(4)
        self.navigationLayout.addWidget(self.toggleButton)

        self.pageButtonLayout = QVBoxLayout()
        self.pageButtonLayout.setContentsMargins(0, 6, 0, 0)
        self.pageButtonLayout.setSpacing(4)

        self.navigationLayout.addLayout(self.pageButtonLayout)
        self.navigationLayout.addStretch()

        self.bottomPageButtonLayout = QVBoxLayout()
        self.bottomPageButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.bottomPageButtonLayout.setSpacing(4)

        self.navigationLayout.addLayout(self.bottomPageButtonLayout)

        self.pageButtonGroup = QButtonGroup(self)
        self.pageButtonGroup.setExclusive(True)

        self.pageStack = QStackedWidget(parent=self)
        self.pageStack.setObjectName('ApplicationPageStack')

        # Keep the layout's navigation reservation at the compact rail width.
        # The real panel is a sibling overlay, mirroring Fluent NavigationView:
        # expanding it changes only the panel geometry, never the page geometry.
        self.navigationRail = QFrame(parent=self)
        self.navigationRail.setObjectName('NavigationRailPlaceholder')
        self.navigationRail.setFixedWidth(self.CollapsedWidth)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.navigationRail)
        self._layout.addWidget(self.pageStack, 1)

        self.navigationPanel.raise_()

        self._widthAnimation = QtCore.QPropertyAnimation(
            self,
            b'navigationWidth',
            parent=self,
        )
        self._widthAnimation.setDuration(self.AnimationDuration)
        self._widthAnimation.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)
        self._widthAnimation.finished.connect(self._widthAnimationFinished)

        self.setExpanded(False, animated=False)
        self.setIconByTheme(APP().theme())

    def addPage(
        self,
        pageId: str,
        widget: QWidget,
        title: str,
        iconFileName: str,
        *,
        translatable: bool = True,
        placement: str = 'top',
    ):
        """Register a page and create its navigation control."""
        if not isinstance(pageId, str) or not pageId:
            raise ValueError('pageId must be a non-empty string')

        if pageId in self._pages:
            raise ValueError(f'page is already registered: {pageId}')

        if not isinstance(widget, QWidget):
            raise TypeError('widget must be a QWidget')

        if placement not in ('top', 'bottom'):
            raise ValueError("placement must be either 'top' or 'bottom'")

        button = _NavigationButton(
            parent=self.navigationPanel,
            hasSelectionIndicator=True,
        )
        button.setObjectName('NavigationPageButton')
        button.setProperty('pageId', pageId)
        button.setCheckable(True)
        button.setExpanded(self._expanded)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        button.clicked.connect(
            lambda _checked=False, selectedPageId=pageId: self.setCurrentPage(
                selectedPageId
            )
        )

        page = _NavigationPage(
            pageId,
            title,
            iconFileName,
            widget,
            button,
            translatable,
            placement,
        )

        self._pages[pageId] = page
        self.pageButtonGroup.addButton(button)

        if placement == 'bottom':
            self.bottomPageButtonLayout.addWidget(button)
        else:
            self.pageButtonLayout.addWidget(button)

        self.pageStack.addWidget(widget)

        self._updatePageText(page)
        self._updatePageIcon(page, APP().theme())

        if not self._currentPageId:
            self.setCurrentPage(pageId)

    def page(self, pageId: str) -> QWidget | None:
        """Return the registered widget for *pageId*."""
        page = self._pages.get(pageId)

        return page.widget if page is not None else None

    def currentPageId(self) -> str:
        """Return the identifier of the visible page."""
        return self._currentPageId

    @QtCore.Slot(str)
    def setCurrentPage(self, pageId: str):
        """Show the page registered under *pageId*."""
        page = self._pages.get(pageId)

        if page is None:
            return

        changed = pageId != self._currentPageId
        self._currentPageId = pageId
        page.button.setChecked(True)
        self.pageStack.setCurrentWidget(page.widget)

        if changed:
            self.pageChanged.emit(pageId)

    def isExpanded(self) -> bool:
        """Return whether labels are visible beside navigation icons."""
        return self._expanded

    @QtCore.Slot()
    def toggleExpanded(self):
        """Toggle between the compact rail and expanded navigation menu."""
        self.setExpanded(not self._expanded)

    def setExpanded(self, expanded: bool, *, animated: bool = True):
        """Set expansion state, optionally animating the panel width."""
        expanded = bool(expanded)
        changed = expanded != self._expanded

        self._expanded = expanded

        self.toggleButton.setToolTip(
            _('Collapse Navigation') if expanded else _('Expand Navigation')
        )
        self.toggleButton.setProperty('expanded', expanded)
        self._refreshWidgetStyle(self.toggleButton)
        self.setIconByTheme(APP().theme())

        for page in self._pages.values():
            if expanded:
                page.button.setExpanded(True)

            self._updatePageText(page)

        targetWidth = self.ExpandedWidth if expanded else self.CollapsedWidth

        self._widthAnimation.stop()

        if changed and animated:
            self._widthAnimation.setStartValue(self._navigationWidth)
            self._widthAnimation.setEndValue(targetWidth)
            self._widthAnimation.start()
        else:
            self._setNavigationWidth(targetWidth)

            if not expanded:
                self._setPageButtonsExpanded(False)

        if changed:
            self._setOutsideClickFilterEnabled(expanded and self.isVisible())
            self.expandedChanged.emit(expanded)

    def _setOutsideClickFilterEnabled(self, enabled: bool):
        """Observe application clicks only while the overlay is expanded."""
        application = QApplication.instance()

        if application is None or enabled == self._outsideClickFilterInstalled:
            return

        if enabled:
            application.installEventFilter(self)
        else:
            application.removeEventFilter(self)

        self._outsideClickFilterInstalled = enabled

    def _isOutsideNavigationClick(self, watched, event) -> bool:
        """Return whether *event* targets this window outside the panel."""
        if not self._expanded or not isinstance(watched, QWidget):
            return False

        if watched.window() is not self.window():
            # Popup menus, combo-box popups, message boxes, and child dialogs
            # are separate top-level windows and keep their normal behavior.
            return False

        (
            globalPosition,
            panelTopLeft,
        ) = (
            event.globalPosition().toPoint(),
            self.navigationPanel.mapToGlobal(QtCore.QPoint()),
        )

        panelGeometry = QtCore.QRect(panelTopLeft, self.navigationPanel.size())

        return not panelGeometry.contains(globalPosition)

    def eventFilter(self, watched, event):
        """Animate closed after an outside press without consuming the click."""
        if (
            event.type() == QtCore.QEvent.Type.MouseButtonPress
            and self._isOutsideNavigationClick(watched, event)
        ):
            self.setExpanded(False)

        return False

    def _getNavigationWidth(self) -> int:
        """Return the width exposed to the property animation."""
        return self._navigationWidth

    def _setNavigationWidth(self, width: int):
        """Apply an animated overlay width without resizing the page stack."""
        self._navigationWidth = int(width)

        self.navigationPanel.setGeometry(
            0,
            0,
            self._navigationWidth,
            self.height(),
        )
        self.navigationPanel.raise_()

    navigationWidth = QtCore.Property(
        int,
        _getNavigationWidth,
        _setNavigationWidth,
    )

    def _setPageButtonsExpanded(self, expanded: bool):
        """Set label visibility for all registered page buttons."""
        for page in self._pages.values():
            page.button.setExpanded(expanded)

    @QtCore.Slot()
    def _widthAnimationFinished(self):
        """Finish label compaction after a collapse animation."""
        if not self._expanded:
            self._setPageButtonsExpanded(False)

    def resizeEvent(self, event):
        """Keep the navigation overlay as tall as the page container."""
        super().resizeEvent(event)

        self._setNavigationWidth(self._navigationWidth)

    def showEvent(self, event):
        """Resume outside-click observation when an expanded view is shown."""
        super().showEvent(event)

        self._setOutsideClickFilterEnabled(self._expanded)

    def hideEvent(self, event):
        """Suspend the application filter while this view cannot be used."""
        self._setOutsideClickFilterEnabled(False)

        super().hideEvent(event)

    @staticmethod
    def _refreshWidgetStyle(widget: QWidget):
        """Re-polish a widget after a dynamic property changes."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def _updatePageText(self, page: _NavigationPage):
        """Apply translated navigation text and compact-mode tooltips."""
        text = _(page.title) if page.translatable else page.title

        page.button.setText(text)
        page.button.setToolTip('' if self._expanded else text)

    @staticmethod
    def _iconFactory(theme: str):
        """Return the icon factory appropriate for *theme*."""
        return bootstrapIconWhite if theme == AppStyleSheet.Dark else bootstrapIcon

    def _updatePageIcon(self, page: _NavigationPage, theme: str):
        """Apply one page icon for the active theme."""
        page.button.setIcon(self._iconFactory(theme)(page.iconFileName))

    def setIconByTheme(self, theme: str):
        """Refresh navigation icons for the active theme."""
        iconFactory = self._iconFactory(theme)

        self.toggleButton.setIcon(iconFactory('list.svg'))

        for page in self._pages.values():
            self._updatePageIcon(page, theme)

    def themeChangedCallback(self, theme: str):
        """Refresh icons after an application theme change."""
        self.setIconByTheme(theme)

    def retranslate(self):
        """Refresh navigation labels and expansion affordances."""
        self.toggleButton.setToolTip(
            _('Collapse Navigation') if self._expanded else _('Expand Navigation')
        )

        for page in self._pages.values():
            self._updatePageText(page)
