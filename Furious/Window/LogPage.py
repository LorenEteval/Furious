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

"""Provide the unified logging page."""

from __future__ import annotations

from Furious.Controllers.SettingsController import (
    LOG_AUTO_CLEAR_SETTING,
    LOG_AUTO_SCROLL_DOWN_SETTING,
    SettingsController,
)
from Furious.Frozenlib import AppSettings, Mixins, registerAppSettings
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service.LogManager import (
    ALL_LOGS_FILTER,
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    LogManager,
    formatLogEntry,
)
from Furious.Widget.WaitingSpinner import WaitingSpinner

from PySide6 import QtCore, QtGui
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import *

from collections import deque
from dataclasses import dataclass

import logging

__all__ = ['LogPage']

logger = logging.getLogger(__name__)

registerAppSettings('LogViewerWidgetPointSize')
registerAppSettings('LogViewerSelectedCategory', default=ALL_LOGS_FILTER)

_LEGACY_POINT_SIZE_SETTINGS = (
    'LogViewerWidgetPointSizeSelf',
    'LogViewerWidgetPointSizeCore',
    'LogViewerWidgetPointSizeTun_',
)


@dataclass(frozen=True)
class _RenderedEntryMetadata:
    """Track one normalized entry's sequence and owned document paragraphs.

    LogManager strips terminal CR/LF before entries are joined by one newline.
    The first entry's base block owns the document's initial block; each later
    entry's base block owns its preceding inter-entry separator. Any additional
    blocks counted in ``blockCount`` belong to paragraph breaks inside that
    entry, so the per-entry counts remain additive for prefix removal.
    """

    sequence: int
    blockCount: int


class _DocumentBlockAccountingError(RuntimeError):
    """Report a recoverable mismatch between rendered metadata and Qt blocks."""


def _documentBlockCount(text: str) -> int:
    """Return the QTextDocument block count produced by plain *text*."""
    blockCount = 1 + text.count('\n') + text.count('\u2029')

    for index, character in enumerate(text):
        if character == '\r' and (index + 1 == len(text) or text[index + 1] != '\n'):
            blockCount += 1

    return blockCount


def _renderedEntryMetadata(entry) -> _RenderedEntryMetadata:
    """Return immutable block ownership for one normalized log entry."""
    return _RenderedEntryMetadata(
        sequence=entry.sequence,
        blockCount=_documentBlockCount(formatLogEntry(entry)),
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
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()


class LogPage(Mixins.QTranslatable, QMainWindow):
    """Present and filter the unified application log stream as a page."""

    UpdateDelay = 25
    HighlightBatchSize = 64
    HighlightTimeBudget = 8
    HighlightBusyThreshold = 100
    BusyIndicatorDelay = 16
    TailTolerance = 10

    def __init__(self, *args, **kwargs):
        """Initialize the logging page."""
        manager, fontFamily = (
            kwargs.pop('manager', None),
            kwargs.pop('fontFamily', ''),
        )

        super().__init__(*args, **kwargs)

        if not isinstance(manager, LogManager):
            raise TypeError('manager must be a LogManager')

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        _migratePointSizeSettings()

        self._preferredFilter = str(AppSettings.get('LogViewerSelectedCategory'))
        self._autoScrollDown = AppSettings.isStateON_(LOG_AUTO_SCROLL_DOWN_SETTING)

        self.manager = manager
        self.manager.setAutoClearEnabled(AppSettings.isStateON_(LOG_AUTO_CLEAR_SETTING))

        self.pageTitleLabel = AppQLabel(_('Log'))
        self.pageTitleLabel.setObjectName('LogPageTitle')
        self.filterLabel = AppQLabel(_('Log Type'))
        # Category names can be either translated built-ins or literal plugin
        # metadata, so LogPage rebuilds this application-styled selector with
        # the correct per-category translation policy.
        self.filterComboBox = AppQComboBox(translatable=False)
        self.filterComboBox.setContentWidthAdjustable()
        self.filterComboBox.setMinimumWidth(180)

        self.textBrowser = DraculaTextBrowser(
            fontFamily=fontFamily,
            pointSizeSettingsName='LogViewerWidgetPointSize',
        )
        self.textBrowser.setLineWrapMode(DraculaTextBrowser.LineWrapMode.NoWrap)
        self.textBrowser.setUndoRedoEnabled(False)

        self.highlightOverlay = QFrame(self.textBrowser.viewport())
        self.highlightOverlay.setObjectName('LogHighlightOverlay')
        self.highlightOverlay.setAutoFillBackground(True)
        self.highlightOverlay.setBackgroundRole(QtGui.QPalette.ColorRole.Base)
        self.highlightOverlay.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )

        self.highlightSpinner = WaitingSpinner(
            self.highlightOverlay,
            center_on_parent=False,
            lines=12,
            line_length=7,
            line_width=3,
            radius=5,
        )
        self.highlightStatusLabel = AppQLabel(_('Processing...'))

        highlightLayout = QHBoxLayout(self.highlightOverlay)
        highlightLayout.setContentsMargins(16, 16, 16, 16)
        highlightLayout.setSpacing(10)
        highlightLayout.addStretch(1)
        highlightLayout.addWidget(self.highlightSpinner)
        highlightLayout.addWidget(self.highlightStatusLabel)
        highlightLayout.addStretch(1)

        self.highlightOverlay.hide()

        self._entriesDirty = True
        self._representationInvalid = True
        self._renderedSequence = 0
        self._entryCursor = None
        self._renderedCategoryId = None
        self._renderedEntries = deque()
        self._followTail = self._autoScrollDown
        self._documentMutation = False
        self._highlightNextBlock = None
        self._pendingScrollRatio = None

        self._updateTimer = QtCore.QTimer(self)
        self._updateTimer.setSingleShot(True)
        self._updateTimer.timeout.connect(self._renderPendingEntries)

        self._highlightTimer = QtCore.QTimer(self)
        self._highlightTimer.setSingleShot(True)
        self._highlightTimer.timeout.connect(self._highlightNextBatch)

        self._scrollTimer = QtCore.QTimer(self)
        self._scrollTimer.setSingleShot(True)
        self._scrollTimer.timeout.connect(self._restoreScrollPosition)

        self._followStateTimer = QtCore.QTimer(self)
        self._followStateTimer.setSingleShot(True)
        self._followStateTimer.timeout.connect(self._updateFollowTailFromScrollbar)

        filterLayout = QHBoxLayout()
        filterLayout.setContentsMargins(0, 0, 0, 0)
        filterLayout.setSpacing(8)
        filterLayout.addWidget(self.pageTitleLabel)
        filterLayout.addStretch(1)
        filterLayout.addWidget(self.filterLabel)
        filterLayout.addWidget(self.filterComboBox)

        centralLayout = QVBoxLayout()
        centralLayout.setContentsMargins(20, 18, 20, 20)
        centralLayout.setSpacing(14)
        centralLayout.addLayout(filterLayout)
        centralLayout.addWidget(self.textBrowser)

        centralWidget = QWidget()
        centralWidget.setObjectName('LogPageContent')
        centralWidget.setLayout(centralLayout)

        self.setCentralWidget(centralWidget)

        self._fileMenu = AppQMenu(
            AppQAction(
                _('Save As...'),
                callback=lambda: saveAsFile(self.textBrowser.toPlainText()),
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
            AppQSeparator(),
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

        self.fileButton = AppQMenuPushButton(
            _('File'),
            icon=bootstrapIcon('file-earmark.svg'),
            popupMenu=self._fileMenu,
        )
        self.editButton = AppQMenuPushButton(
            _('Edit'),
            icon=bootstrapIcon('pencil-square.svg'),
            popupMenu=self._editMenu,
        )
        self.viewButton = AppQMenuPushButton(
            _('View'),
            icon=bootstrapIcon('eye.svg'),
            popupMenu=self._viewMenu,
        )

        self.autoScrollLabel = AppQLabel(_('Auto Scroll Down'))

        self.autoScrollSwitch = AppQSwitch()
        self.autoScrollSwitch.syncChecked(self._autoScrollDown)

        self.autoClearLabel = AppQLabel(_('Auto Clear Log'))

        self.autoClearSwitch = AppQSwitch()
        self.autoClearSwitch.syncChecked(self.manager.autoClearEnabled)

        actionLayout = QHBoxLayout()
        actionLayout.setContentsMargins(0, 0, 0, 0)
        actionLayout.setSpacing(8)
        actionLayout.addWidget(self.fileButton)
        actionLayout.addWidget(self.editButton)
        actionLayout.addWidget(self.viewButton)
        actionLayout.addStretch(1)
        actionLayout.addWidget(self.autoScrollLabel)
        actionLayout.addWidget(self.autoScrollSwitch)
        actionLayout.addSpacing(12)
        actionLayout.addWidget(self.autoClearLabel)
        actionLayout.addWidget(self.autoClearSwitch)

        centralLayout.insertLayout(1, actionLayout)

        for menu in (self._fileMenu, self._editMenu, self._viewMenu):
            self._registerMenuShortcuts(menu)

        self._populateFilters(self._preferredFilter)

        self.filterComboBox.currentIndexChanged.connect(self._filterChanged)
        self.autoScrollSwitch.toggled.connect(self._autoScrollChanged)
        self.autoClearSwitch.toggled.connect(self._autoClearChanged)
        self.manager.categoryRegistered.connect(self._categoryRegistered)
        # Do not drive the document directly from entryAdded: cross-thread Qt
        # delivery can occur after that entry was evicted or its generation was
        # cleared, and one queued signal per line defeats batching under a burst.
        # entriesChanged coalesces producers, then one cursor query returns only
        # the missing suffix plus an eviction boundary for prefix pruning.
        self.manager.entriesChanged.connect(self._entriesChanged)
        self.manager.entriesCleared.connect(self._entriesCleared)

        scrollbar = self.textBrowser.verticalScrollBar()
        scrollbar.actionTriggered.connect(self._scrollActionTriggered)
        scrollbar.sliderReleased.connect(self._scrollActionTriggered)

        self.retranslate()

    def _registerMenuShortcuts(self, menu):
        """Associate popup actions with the page so shortcuts stay active."""
        for action in menu.actions():
            if action.isSeparator():
                continue

            self.addAction(action)

            submenu = action.menu() if hasattr(action, 'menu') else None

            if submenu is not None:
                self._registerMenuShortcuts(submenu)

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

    def _pageCanRender(self) -> bool:
        """Return whether document work can currently reach the screen."""
        window = self.window()

        return self.isVisible() and not (
            hasattr(window, 'isMinimized') and window.isMinimized()
        )

    def _requestRefresh(self, *, invalidate=False, immediate=False):
        """Mark the presentation stale and coalesce visible catch-up work."""
        self._entriesDirty = True

        if invalidate:
            self._representationInvalid = True

        if not self._pageCanRender():
            return

        if self._representationInvalid:
            self._setHighlightBusy(True)

        if immediate:
            self._updateTimer.stop()
            self._updateTimer.start(
                self.BusyIndicatorDelay if self.highlightSpinner.is_spinning else 0
            )
        elif not self._updateTimer.isActive():
            self._updateTimer.start(self.UpdateDelay)

    def _syncHighlightOverlayGeometry(self):
        """Cover the log viewport without affecting its layout or scrollbars."""
        self.highlightOverlay.setGeometry(self.textBrowser.viewport().rect())

    def _setHighlightBusy(self, busy: bool):
        """Show or hide the cooperative highlighting progress presentation."""
        if busy and self._pageCanRender():
            self.highlightSpinner.color = self.palette().color(
                QtGui.QPalette.ColorRole.Text
            )

            self._syncHighlightOverlayGeometry()

            self.highlightOverlay.raise_()
            self.highlightOverlay.show()
            self.highlightSpinner.start()
        else:
            self.highlightSpinner.stop()
            self.highlightOverlay.hide()

    def _scrollRatio(self) -> float:
        """Return the current vertical position as a bounded range ratio."""
        scrollbar = self.textBrowser.verticalScrollBar()

        if scrollbar.maximum() <= 0:
            return 1.0

        return min(1.0, max(0.0, scrollbar.value() / scrollbar.maximum()))

    def _removeLeadingDocumentBlocks(self, blockCount: int, *, removeAll=False):
        """Remove an exact owned paragraph prefix in one document edit."""
        if blockCount <= 0:
            return

        if removeAll:
            self.textBrowser.clear()

            return

        document = self.textBrowser.document()
        firstRetainedBlock = document.findBlockByNumber(blockCount)

        if not firstRetainedBlock.isValid():
            raise _DocumentBlockAccountingError(
                'rendered log block accounting diverged'
            )

        cursor = QTextCursor(document)
        cursor.setPosition(0)
        cursor.setPosition(
            firstRetainedBlock.position(),
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()

    def _appendEntries(self, entries, *, hasExistingEntries: bool):
        """Append one formatted batch and return its first block number."""
        if not entries:
            return None

        content = '\n'.join(formatLogEntry(entry) for entry in entries)

        if not hasExistingEntries:
            self.textBrowser.setPlainText(content)

            return 0

        document = self.textBrowser.document()

        firstChangedBlock = max(0, document.blockCount() - 1)

        cursor = QTextCursor(document)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertBlock()
        cursor.insertText(content)

        # Inserting the paragraph separator also invalidates the previous last
        # block, so progressive highlighting must resume there rather than at
        # the first newly inserted block.
        return firstChangedBlock

    def _replaceEntries(self, entries):
        """Replace the text in one cheap unhighlighted document operation."""
        self._highlightTimer.stop()
        self._highlightNextBlock = None

        content = '\n'.join(formatLogEntry(entry) for entry in entries)

        self.textBrowser.setPlainText(content)

        return 0 if entries else None

    def _synchronizeDocument(self, batch, categoryId: str):
        """Apply one incremental manager batch with the smallest safe mutation."""
        fullRebuild = (
            self._representationInvalid
            or self._renderedCategoryId != categoryId
            or batch.resetRequired
        )

        oldRatio = self._scrollRatio()
        firstHighlightBlock = None
        restoreManualPosition = fullRebuild
        leadingBoundaryChanged = False

        self._documentMutation = True
        self.textBrowser.setUpdatesEnabled(False)
        self.textBrowser.setSyntaxHighlightingEnabled(False)

        try:
            if fullRebuild:
                firstHighlightBlock = self._replaceEntries(batch.entries)

                self._renderedEntries = deque(
                    _renderedEntryMetadata(entry) for entry in batch.entries
                )
            else:
                firstRetainedSequence = batch.firstRetainedSequence

                if firstRetainedSequence is None:
                    dropEntryCount = len(self._renderedEntries)
                    droppedBlockCount = sum(
                        metadata.blockCount for metadata in self._renderedEntries
                    )
                else:
                    dropEntryCount = 0
                    droppedBlockCount = 0

                    for metadata in self._renderedEntries:
                        if metadata.sequence >= firstRetainedSequence:
                            break

                        dropEntryCount += 1
                        droppedBlockCount += metadata.blockCount

                self._removeLeadingDocumentBlocks(
                    droppedBlockCount,
                    removeAll=bool(dropEntryCount)
                    and dropEntryCount == len(self._renderedEntries),
                )

                for _index in range(dropEntryCount):
                    self._renderedEntries.popleft()

                if self._highlightNextBlock is not None and droppedBlockCount:
                    self._highlightNextBlock = max(
                        0,
                        self._highlightNextBlock - droppedBlockCount,
                    )

                leadingBoundaryChanged = bool(dropEntryCount)

                firstHighlightBlock = self._appendEntries(
                    batch.entries,
                    hasExistingEntries=bool(self._renderedEntries),
                )

                self._renderedEntries.extend(
                    _renderedEntryMetadata(entry) for entry in batch.entries
                )

                restoreManualPosition = bool(dropEntryCount)
        finally:
            self.textBrowser.setSyntaxHighlightingEnabled(True)

            if leadingBoundaryChanged:
                firstBlock = self.textBrowser.document().firstBlock()

                if firstBlock.isValid():
                    # Removing a retained prefix invalidates the new leading
                    # paragraph independently from the appended tail range.
                    self.textBrowser.rehighlightBlock(firstBlock)

            self.textBrowser.setUpdatesEnabled(True)
            self._documentMutation = False

        self.textBrowser.viewport().update()
        self._renderedCategoryId = categoryId
        self._representationInvalid = False

        if firstHighlightBlock is not None:
            self._scheduleHighlight(firstHighlightBlock)
        else:
            self._setHighlightBusy(False)

        if self._followTail:
            self._scheduleScrollRestore()
        elif restoreManualPosition:
            self._scheduleScrollRestore(oldRatio)

    @QtCore.Slot()
    def _renderPendingEntries(self):
        """Catch the visible document up to one immutable manager snapshot."""
        if not self._entriesDirty or not self._pageCanRender():
            return

        selectedCategoryId = self.filterComboBox.currentData()

        if not isinstance(selectedCategoryId, str):
            selectedCategoryId = ALL_LOGS_FILTER

        cursor = (
            None
            if self._representationInvalid
            or self._renderedCategoryId != selectedCategoryId
            else self._entryCursor
        )
        batch = self.manager.entriesSince(cursor, selectedCategoryId)

        try:
            self._synchronizeDocument(batch, selectedCategoryId)
        except _DocumentBlockAccountingError:
            logger.exception(
                'rendered log block accounting diverged; rebuilding document'
            )

            self._entryCursor = None
            self._requestRefresh(invalidate=True, immediate=True)

            return

        self._entryCursor = batch.cursor
        self._renderedSequence = batch.cursor.sequence
        self._entriesDirty = False

    def _scheduleHighlight(self, firstBlock: int):
        """Coalesce incremental highlighting from the earliest changed block."""
        if self._highlightNextBlock is None:
            self._highlightNextBlock = firstBlock
        else:
            self._highlightNextBlock = min(self._highlightNextBlock, firstBlock)

        if (
            self.textBrowser.document().blockCount() - self._highlightNextBlock
            >= self.HighlightBusyThreshold
        ):
            self._setHighlightBusy(True)

        if self._pageCanRender() and not self._highlightTimer.isActive():
            self._highlightTimer.start(0)

    @QtCore.Slot()
    def _highlightNextBatch(self):
        """Format a bounded block batch and yield back to the event loop."""
        if self._highlightNextBlock is None or not self._pageCanRender():
            return

        document = self.textBrowser.document()
        start = self._highlightNextBlock
        maximumEnd = min(document.blockCount(), start + self.HighlightBatchSize)
        elapsed = QtCore.QElapsedTimer()
        elapsed.start()
        end = start

        while end < maximumEnd:
            block = document.findBlockByNumber(end)

            if block.isValid():
                self.textBrowser.rehighlightBlock(block)

            end += 1

            if elapsed.elapsed() >= self.HighlightTimeBudget:
                break

        if end < document.blockCount():
            self._highlightNextBlock = end
            self._highlightTimer.start(0)
        else:
            self._highlightNextBlock = None
            self._setHighlightBusy(False)

        if self._followTail:
            self._scheduleScrollRestore()

    def _scheduleScrollRestore(self, ratio=None):
        """Restore tail or reading position after document layout settles."""
        self._pendingScrollRatio = ratio

        if self._pageCanRender():
            self._scrollTimer.start(0)

    @QtCore.Slot()
    def _restoreScrollPosition(self):
        """Apply a coalesced post-layout scroll position without changing intent."""
        if not self._pageCanRender():
            return

        scrollbar = self.textBrowser.verticalScrollBar()

        self._documentMutation = True

        try:
            if self._followTail:
                scrollbar.setValue(scrollbar.maximum())

                self.textBrowser.horizontalScrollBar().setValue(0)
            elif self._pendingScrollRatio is not None:
                scrollbar.setValue(
                    round(scrollbar.maximum() * self._pendingScrollRatio)
                )
        finally:
            self._documentMutation = False
            self._pendingScrollRatio = None

    @QtCore.Slot()
    def _updateFollowTailFromScrollbar(self):
        """Capture whether the user's viewport is following the newest entry."""
        if self._documentMutation:
            return

        if not self._autoScrollDown:
            self._followTail = False

            return

        scrollbar = self.textBrowser.verticalScrollBar()

        self._followTail = scrollbar.maximum() - scrollbar.value() <= self.TailTolerance

    @QtCore.Slot(bool)
    def _autoScrollChanged(self, enabled: bool):
        """Persist and immediately apply the master tail-follow preference."""
        self._autoScrollDown = bool(enabled)
        self._followTail = self._autoScrollDown

        SettingsController.setLogAutoScrollDown(self._autoScrollDown)

        if self._followTail:
            self._scheduleScrollRestore()
        else:
            self._scrollTimer.stop()
            self._pendingScrollRatio = None

    @QtCore.Slot(bool)
    def _autoClearChanged(self, enabled: bool):
        """Persist and immediately apply Core-triggered log clearing."""
        SettingsController.setLogAutoClear(enabled, manager=self.manager)

    def _scrollActionTriggered(self, *_args):
        """Defer follow-state capture until the user scroll action is applied."""
        if self._documentMutation:
            return

        self._scrollTimer.stop()
        self._pendingScrollRatio = None
        self._followStateTimer.start(0)

    @QtCore.Slot(int)
    def _filterChanged(self, _index: int):
        """Persist and apply the category selected by the user."""
        categoryId = self.filterComboBox.currentData()

        if not isinstance(categoryId, str):
            categoryId = ALL_LOGS_FILTER

        self._preferredFilter = categoryId
        self._followTail = self._autoScrollDown

        AppSettings.set('LogViewerSelectedCategory', categoryId)

        self._requestRefresh(invalidate=True, immediate=True)

    @QtCore.Slot(object)
    def _categoryRegistered(self, category):
        """Add a newly registered component without rebuilding the page."""
        if self.filterComboBox.findData(category.id) == -1:
            self.filterComboBox.addItem(self._categoryText(category), category.id)

        if category.id == self._preferredFilter:
            self.filterComboBox.setCurrentIndex(
                self.filterComboBox.findData(category.id)
            )

    @QtCore.Slot(int)
    def _entriesChanged(self, sequence: int):
        """Coalesce newly collected entries into the visible presentation."""
        if sequence <= self._renderedSequence:
            return

        self._requestRefresh()

    @QtCore.Slot(object)
    def _entriesCleared(self, _categoryIds):
        """Refresh the presentation after the underlying collection changes."""
        self._requestRefresh(immediate=True)

    def showEvent(self, event):
        """Render entries accumulated while the page was hidden."""
        super().showEvent(event)

        if self._entriesDirty:
            self._setHighlightBusy(True)
            self._requestRefresh(immediate=True)
        elif self._highlightNextBlock is not None:
            self._setHighlightBusy(True)
            self._highlightTimer.start(0)

        if self._followTail:
            self._scheduleScrollRestore()

    def hideEvent(self, event):
        """Pause presentation work while preserving collection and scroll intent."""
        self._updateFollowTailFromScrollbar()
        self._updateTimer.stop()
        self._highlightTimer.stop()
        self._scrollTimer.stop()
        self._followStateTimer.stop()
        self._setHighlightBusy(False)

        super().hideEvent(event)

    def resizeEvent(self, event):
        """Keep the highlighting overlay aligned with the log viewport."""
        super().resizeEvent(event)

        if hasattr(self, 'highlightOverlay'):
            self._syncHighlightOverlayGeometry()

    def plainText(self) -> str:
        """Return the plain text currently shown by the selected filter."""
        return self.textBrowser.toPlainText()

    def clear(self):
        """Remove all entries through the unified logging service."""
        self.manager.clear()

    def retranslate(self):
        """Refresh mixed-policy filter labels and rendered log text."""

        selectedCategoryId = self.filterComboBox.currentData()

        self._populateFilters(selectedCategoryId)
        self._requestRefresh(immediate=True)
