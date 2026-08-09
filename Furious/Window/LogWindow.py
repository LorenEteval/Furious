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

"""Provide the application window for log viewer window."""

from __future__ import annotations

from Furious.Frozenlib import AppSettings, registerAppSettings
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service.LogManager import (
    ALL_LOGS_FILTER,
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    LogManager,
    formatLogEntry,
)

from PySide6 import QtCore
from PySide6.QtWidgets import *

__all__ = ['LogWindow']

registerAppSettings('LogViewerWidgetPointSize')
registerAppSettings('LogViewerSelectedCategory', default=ALL_LOGS_FILTER)

_LEGACY_POINT_SIZE_SETTINGS = (
    'LogViewerWidgetPointSizeSelf',
    'LogViewerWidgetPointSizeCore',
    'LogViewerWidgetPointSizeTun_',
)


def _migratePointSizeSettings():
    """Preserve one legacy size and remove the obsolete per-source settings."""
    settings = QtCore.QSettings()

    if settings.value('LogViewerWidgetPointSize') is None:
        for name in _LEGACY_POINT_SIZE_SETTINGS:
            value = settings.value(name)

            if value is not None:
                settings.setValue('LogViewerWidgetPointSize', value)

                break

    for name in _LEGACY_POINT_SIZE_SETTINGS:
        settings.remove(name)


class MBoxSaveError(AppQMessageBox):
    """Represent m box save error."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxSaveError."""
        super().__init__(*args, **kwargs)

        self.saveError = ''

    def customText(self):
        """Return the user-facing message text for the m box save error."""
        if self.saveError:
            return _('Unable to save log') + f'\n\n{self.saveError}'
        else:
            return _('Unable to save log')

    def retranslate(self):
        """Refresh translated text for the m box save error."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


def saveAsFile(content: str):
    """Save as file."""
    filename, selectedFilter = QFileDialog.getSaveFileName(
        None, _('Save File'), filter=_('Text files (*.txt);;All files (*)')
    )

    if filename:
        try:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content)
        except Exception as ex:
            # Any non-exit exceptions

            mbox = MBoxSaveError(icon=AppQMessageBox.Icon.Critical)
            mbox.saveError = str(ex)
            mbox.setWindowTitle(_('Error saving log'))
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()


class LogWindow(AppQMainWindow):
    """Present and filter the unified application log stream."""

    def __init__(self, *args, **kwargs):
        """Initialize the log window."""
        manager, fontFamily = (
            kwargs.pop('manager', None),
            kwargs.pop('fontFamily', ''),
        )

        super().__init__(*args, **kwargs)

        if not isinstance(manager, LogManager):
            raise TypeError('manager must be a LogManager')

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        _migratePointSizeSettings()

        self.manager = manager
        self._preferredFilter = str(AppSettings.get('LogViewerSelectedCategory'))

        self.setWindowTitle(_('Log Viewer'))

        self.filterLabel = AppQLabel(_('Log Type'))
        self.filterComboBox = QComboBox()
        self.filterComboBox.setMinimumWidth(180)

        self.textBrowser = DraculaTextBrowser(
            fontFamily=fontFamily,
            pointSizeSettingsName='LogViewerWidgetPointSize',
        )
        self.textBrowser.setLineWrapMode(DraculaTextBrowser.LineWrapMode.NoWrap)

        filterLayout = QHBoxLayout()
        filterLayout.addWidget(self.filterLabel)
        filterLayout.addWidget(self.filterComboBox)
        filterLayout.addStretch()

        centralLayout = QVBoxLayout()
        centralLayout.addLayout(filterLayout)
        centralLayout.addWidget(self.textBrowser)

        centralWidget = QWidget()
        centralWidget.setLayout(centralLayout)

        self.setCentralWidget(centralWidget)

        self._fileMenu = AppQMenu(
            AppQAction(
                _('Save As...'),
                callback=lambda: saveAsFile(self.textBrowser.toPlainText()),
            ),
            AppQSeperator(),
            AppQAction(
                _('Exit'),
                callback=lambda: self.close(),
            ),
            title=_('File'),
            parent=self,
        )

        self._editMenu = AppQMenu(
            AppQAction(
                _('Copy'),
                icon=bootstrapIcon('files.svg'),
                callback=lambda: self.textBrowser.copy(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.textBrowser.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            title=_('Edit'),
            parent=self,
        )

        self._viewMenu = AppQMenu(
            AppQAction(
                _('Zoom In'),
                callback=lambda: self.textBrowser.zoomIn(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Plus,
                ),
            ),
            AppQAction(
                _('Zoom Out'),
                callback=lambda: self.textBrowser.zoomOut(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Minus,
                ),
            ),
            title=_('View'),
            parent=self,
        )

        self.menuBar().addMenu(self._fileMenu)
        self.menuBar().addMenu(self._editMenu)
        self.menuBar().addMenu(self._viewMenu)

        self._populateFilters(self._preferredFilter)
        self._refreshEntries()

        self.filterComboBox.currentIndexChanged.connect(self._filterChanged)
        self.manager.categoryRegistered.connect(self._categoryRegistered)
        self.manager.entryAdded.connect(self._entryAdded)
        self.manager.entriesCleared.connect(self._entriesCleared)

    def _categoryText(self, category) -> str:
        """Return a category's translated or literal display label."""
        if category.id == APPLICATION_LOG_CATEGORY:
            return _('Application')

        return (
            _(category.displayName) if category.translatable else category.displayName
        )

    def _populateFilters(self, selectedCategoryId: str):
        """Rebuild filter choices from the registered category collection."""
        self.filterComboBox.blockSignals(True)

        try:
            self.filterComboBox.clear()
            self.filterComboBox.addItem(_('All Logs'), ALL_LOGS_FILTER)

            for category in self.manager.categories():
                self.filterComboBox.addItem(
                    self._categoryText(category),
                    category.id,
                )

            index = self.filterComboBox.findData(selectedCategoryId)

            self.filterComboBox.setCurrentIndex(max(index, 0))
        finally:
            self.filterComboBox.blockSignals(False)

    def _refreshEntries(self):
        """Render the current immutable filtered-entry snapshot."""
        selectedCategoryId = self.filterComboBox.currentData()

        content = '\n'.join(
            formatLogEntry(entry) for entry in self.manager.entries(selectedCategoryId)
        )
        self.textBrowser.setPlainText(content)

        scrollbar = self.textBrowser.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @QtCore.Slot(int)
    def _filterChanged(self, _index: int):
        """Persist and apply the category selected by the user."""
        categoryId = self.filterComboBox.currentData()

        if not isinstance(categoryId, str):
            categoryId = ALL_LOGS_FILTER

        self._preferredFilter = categoryId

        AppSettings.set('LogViewerSelectedCategory', categoryId)

        self._refreshEntries()

    @QtCore.Slot(object)
    def _categoryRegistered(self, category):
        """Add a newly registered component without rebuilding the window."""
        if self.filterComboBox.findData(category.id) == -1:
            self.filterComboBox.addItem(self._categoryText(category), category.id)

        if category.id == self._preferredFilter:
            self.filterComboBox.setCurrentIndex(
                self.filterComboBox.findData(category.id)
            )

    @QtCore.Slot(object)
    def _entryAdded(self, entry):
        """Append an entry when it matches the active filter."""
        categoryId = self.filterComboBox.currentData()

        if categoryId in (ALL_LOGS_FILTER, entry.categoryId):
            self.textBrowser.appendLine(formatLogEntry(entry))

    @QtCore.Slot(object)
    def _entriesCleared(self, _categoryIds):
        """Refresh the presentation after the underlying collection changes."""
        self._refreshEntries()

    def showEvent(self, event):
        """Focus the window itself instead of an untouched child control."""
        super().showEvent(event)

        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def plainText(self) -> str:
        """Return the plain text currently shown by the selected filter."""
        return self.textBrowser.toPlainText()

    def clear(self):
        """Remove all entries through the unified logging service."""
        self.manager.clear()

    def retranslate(self):
        """Refresh translated window and filter labels."""
        super().retranslate()

        selectedCategoryId = self.filterComboBox.currentData()

        self._populateFilters(selectedCategoryId)
        self._refreshEntries()
