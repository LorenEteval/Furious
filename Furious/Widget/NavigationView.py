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

    def __init__(self, parent=None):
        """Initialize the icon and text presentation."""
        super().__init__(
            parent,
            iconTextSpacing=self.IconTextSpacing,
            horizontalMargin=self.HorizontalMargin,
            verticalMargin=0,
            iconSize=self.IconSize,
        )

    def setExpanded(self, expanded: bool):
        """Show the text label only in expanded navigation mode."""
        self.setTextVisible(expanded)


@dataclass
class _NavigationPage:
    """Describe one registered page and its navigation control."""

    id: str
    title: str
    iconFileName: str
    widget: QWidget
    button: _NavigationButton
    translatable: bool = True


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

        self.pageButtonGroup = QButtonGroup(self)
        self.pageButtonGroup.setExclusive(True)

        self.pageStack = QStackedWidget(parent=self)
        self.pageStack.setObjectName('ApplicationPageStack')

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self.navigationPanel)
        self._layout.addWidget(self.pageStack, 1)

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
    ):
        """Register a page and create its navigation control."""
        if not isinstance(pageId, str) or not pageId:
            raise ValueError('pageId must be a non-empty string')

        if pageId in self._pages:
            raise ValueError(f'page is already registered: {pageId}')

        if not isinstance(widget, QWidget):
            raise TypeError('widget must be a QWidget')

        button = _NavigationButton(parent=self.navigationPanel)
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
        )
        self._pages[pageId] = page
        self.pageButtonGroup.addButton(button)
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
            self.expandedChanged.emit(expanded)

    def _getNavigationWidth(self) -> int:
        """Return the width exposed to the property animation."""
        return self._navigationWidth

    def _setNavigationWidth(self, width: int):
        """Apply an animated width to the navigation panel."""
        self._navigationWidth = int(width)
        self.navigationPanel.setFixedWidth(self._navigationWidth)

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
