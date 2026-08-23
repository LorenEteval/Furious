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

"""Collect, classify, and publish logs independently from their presentation."""

from __future__ import annotations

from Furious.Models.Logging import LogCategory, LogEntry

from PySide6 import QtCore

from collections import deque
from datetime import datetime
from typing import Optional

import logging
import threading

__all__ = [
    'ALL_LOGS_FILTER',
    'APPLICATION_LOG_CATEGORY',
    'CORE_LOG_CATEGORY',
    'TUN2SOCKS_LOG_CATEGORY',
    'ApplicationLogHandler',
    'LogManager',
    'coreLogCallback',
    'formatLogEntry',
]

ALL_LOGS_FILTER = 'all'
APPLICATION_LOG_CATEGORY = 'application'
CORE_LOG_CATEGORY = 'core'
TUN2SOCKS_LOG_CATEGORY = 'component.tun2socks'


def formatLogEntry(entry: LogEntry) -> str:
    """Return the producer-formatted text stored by one structured entry."""
    return entry.message


class LogManager(QtCore.QObject):
    """Own the application-wide categorized log stream."""

    DefaultMaximumEntries = 10_000
    DefaultAutoClearMaximumEntries = 5_000
    DefaultMaximumCharacters = 8 * 1024 * 1024
    DefaultMaximumEntryCharacters = 64 * 1024
    TruncationMarker = '\n... [log entry truncated]'

    categoryRegistered = QtCore.Signal(object)
    entryAdded = QtCore.Signal(object)
    entriesCleared = QtCore.Signal(object)
    entriesChanged = QtCore.Signal(int)

    _entriesChangedRequested = QtCore.Signal()

    def __init__(
        self,
        parent=None,
        *,
        maximumEntries=DefaultMaximumEntries,
        autoClearMaximumEntries=DefaultAutoClearMaximumEntries,
        autoClearEnabled=True,
        maximumCharacters=DefaultMaximumCharacters,
        maximumEntryCharacters=DefaultMaximumEntryCharacters,
    ):
        """Initialize the category registry and thread-safe entry collection."""
        super().__init__(parent)

        if (
            isinstance(maximumEntries, bool)
            or not isinstance(maximumEntries, int)
            or maximumEntries <= 0
        ):
            raise ValueError('maximumEntries must be a positive integer')

        if (
            isinstance(maximumCharacters, bool)
            or not isinstance(maximumCharacters, int)
            or maximumCharacters <= 0
        ):
            raise ValueError('maximumCharacters must be a positive integer')

        if (
            isinstance(maximumEntryCharacters, bool)
            or not isinstance(maximumEntryCharacters, int)
            or maximumEntryCharacters <= 0
        ):
            raise ValueError('maximumEntryCharacters must be a positive integer')

        if maximumEntryCharacters > maximumCharacters:
            raise ValueError('maximumEntryCharacters cannot exceed maximumCharacters')

        if (
            isinstance(autoClearMaximumEntries, bool)
            or not isinstance(autoClearMaximumEntries, int)
            or autoClearMaximumEntries <= 0
        ):
            raise ValueError('autoClearMaximumEntries must be a positive integer')

        self._lock = threading.RLock()
        self._categories: dict[str, LogCategory] = {}
        self._maximumEntries = maximumEntries
        self._maximumCharacters = maximumCharacters
        self._maximumEntryCharacters = maximumEntryCharacters
        self._autoClearMaximumEntries = autoClearMaximumEntries
        self._autoClearEnabled = bool(autoClearEnabled)
        self._entries: deque[LogEntry] = deque()
        self._categoryEntryCounts: dict[str, int] = {}
        self._retainedCharacters = 0
        self._sequence = 0
        self._changeNotificationPending = False

        self._entriesChangedRequested.connect(
            self._publishEntriesChanged,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        self.registerCategory(
            LogCategory(
                APPLICATION_LOG_CATEGORY,
                'Application',
                translatable=True,
            )
        )
        self.registerCategory(
            LogCategory(
                CORE_LOG_CATEGORY,
                'Core',
                translatable=True,
                runtime=True,
            )
        )
        self.registerCategory(
            LogCategory(
                TUN2SOCKS_LOG_CATEGORY,
                'Tun2socks',
                runtime=True,
            )
        )

    @property
    def maximumEntries(self) -> int:
        """Return the maximum number of structured entries retained in memory."""
        return self._maximumEntries

    @property
    def maximumCharacters(self) -> int:
        """Return the hard character budget for retained log messages."""
        return self._maximumCharacters

    @property
    def maximumEntryCharacters(self) -> int:
        """Return the maximum number of characters retained from one entry."""
        return self._maximumEntryCharacters

    @property
    def retainedCharacters(self) -> int:
        """Return the current retained message-character count in constant time."""
        with self._lock:
            return self._retainedCharacters

    @property
    def autoClearMaximumEntries(self) -> int:
        """Return the automatic-clear threshold for replaceable runtime logs."""
        return self._autoClearMaximumEntries

    @property
    def autoClearEnabled(self) -> bool:
        """Return whether automatic clearing triggered by Core is active."""
        with self._lock:
            return self._autoClearEnabled

    def _nonApplicationCategoryIdsLocked(self) -> set[str]:
        """Return every registered category except the persistent Application log."""
        return set(self._categories).difference({APPLICATION_LOG_CATEGORY})

    def _removeCategoriesLocked(self, categoryIds: set[str]):
        """Remove selected categories while the caller owns ``_lock``."""
        retainedEntries = deque()
        retainedCharacters = 0

        for entry in self._entries:
            if entry.categoryId in categoryIds:
                continue

            retainedEntries.append(entry)
            retainedCharacters += len(entry.message)

        self._entries = retainedEntries
        self._retainedCharacters = retainedCharacters

        for categoryId in categoryIds:
            self._categoryEntryCounts[categoryId] = 0

    def _removeOldestLocked(self):
        """Remove and account for the oldest entry while holding the lock."""
        entry = self._entries.popleft()

        self._categoryEntryCounts[entry.categoryId] -= 1
        self._retainedCharacters -= len(entry.message)

    def _enforceRetentionLimitsLocked(self):
        """Evict the oldest entries until every hard retention limit is met."""
        while self._entries and (
            len(self._entries) > self._maximumEntries
            or self._retainedCharacters > self._maximumCharacters
        ):
            self._removeOldestLocked()

    def _normalizeMessage(self, message) -> str:
        """Return one newline-trimmed message within the per-entry hard limit."""
        text = str(message).rstrip('\r\n')

        if len(text) <= self._maximumEntryCharacters:
            return text

        marker = self.TruncationMarker

        if len(marker) >= self._maximumEntryCharacters:
            return text[: self._maximumEntryCharacters]

        return text[: self._maximumEntryCharacters - len(marker)] + marker

    def _requestEntriesChanged(self):
        """Queue at most one cross-thread presentation notification."""
        shouldNotify = False

        with self._lock:
            if not self._changeNotificationPending:
                self._changeNotificationPending = True

                shouldNotify = True

        if shouldNotify:
            self._entriesChangedRequested.emit()

    @QtCore.Slot()
    def _publishEntriesChanged(self):
        """Publish the newest sequence once on the manager's Qt thread."""
        with self._lock:
            self._changeNotificationPending = False
            sequence = self._sequence

        self.entriesChanged.emit(sequence)

    def setAutoClearEnabled(self, enabled: bool):
        """Apply Core-triggered clearing without involving presentation state."""
        clearedCategoryIds = set()

        with self._lock:
            self._autoClearEnabled = bool(enabled)

            if (
                self._autoClearEnabled
                and self._categoryEntryCounts.get(CORE_LOG_CATEGORY, 0)
                >= self._autoClearMaximumEntries
            ):
                clearedCategoryIds = self._nonApplicationCategoryIdsLocked()

                self._removeCategoriesLocked(clearedCategoryIds)

        if clearedCategoryIds:
            self.entriesCleared.emit(frozenset(clearedCategoryIds))

    def entryCount(self, categoryId: Optional[str] = None) -> int:
        """Return the retained total or one category count in constant time."""
        with self._lock:
            if categoryId in (None, ALL_LOGS_FILTER):
                return len(self._entries)

            if categoryId not in self._categories:
                raise KeyError(f'unknown log category {categoryId!r}')

            return self._categoryEntryCounts.get(categoryId, 0)

    def registerCategory(self, category: LogCategory) -> LogCategory:
        """Register a filterable category and publish it exactly once."""
        if not isinstance(category, LogCategory):
            raise TypeError('category must be a LogCategory')

        with self._lock:
            existing = self._categories.get(category.id)

            if existing is not None:
                if existing != category:
                    raise ValueError(
                        f'log category {category.id!r} is already registered '
                        f'with different metadata'
                    )

                return existing

            self._categories[category.id] = category
            self._categoryEntryCounts[category.id] = 0

        self.categoryRegistered.emit(category)

        return category

    def registerComponent(
        self,
        identifier: str,
        displayName: str,
        *,
        runtime: bool = True,
        translatable: bool = False,
    ) -> LogCategory:
        """Register a component using its stable identifier and display label."""
        return self.registerCategory(
            LogCategory(
                identifier,
                displayName,
                translatable=translatable,
                runtime=runtime,
            )
        )

    def category(self, categoryId: str) -> Optional[LogCategory]:
        """Return a registered category by stable identifier."""
        with self._lock:
            return self._categories.get(categoryId)

    def categories(self) -> tuple[LogCategory, ...]:
        """Return registered categories in registration order."""
        with self._lock:
            return tuple(self._categories.values())

    def append(
        self,
        message,
        categoryId: str = APPLICATION_LOG_CATEGORY,
        *,
        timestamp: Optional[datetime] = None,
        source: str = '',
        severity: str = '',
    ) -> LogEntry:
        """Append a structured entry and notify interested presenters."""
        clearedCategoryIds = set()

        with self._lock:
            category = self._categories.get(categoryId)

            if category is None:
                raise KeyError(f'unknown log category {categoryId!r}')

            if timestamp is None:
                timestamp = datetime.now()
            elif not isinstance(timestamp, datetime):
                raise TypeError('log timestamp must be a datetime')

            self._sequence += 1

            entry = LogEntry(
                message=self._normalizeMessage(message),
                timestamp=timestamp,
                categoryId=category.id,
                categoryLabel=category.displayName,
                categoryTranslatable=category.translatable,
                source=str(source) if source else '',
                severity=str(severity) if severity else '',
                sequence=self._sequence,
            )

            if (
                category.id == CORE_LOG_CATEGORY
                and self._autoClearEnabled
                and self._categoryEntryCounts[CORE_LOG_CATEGORY]
                >= self._autoClearMaximumEntries
            ):
                # When the next Core line would exceed its threshold, retain
                # only Application diagnostics. All other categories belong
                # to the replaceable runtime stream for this policy.
                clearedCategoryIds = self._nonApplicationCategoryIdsLocked()

                self._removeCategoriesLocked(clearedCategoryIds)

            self._entries.append(entry)
            self._categoryEntryCounts[entry.categoryId] += 1
            self._retainedCharacters += len(entry.message)
            self._enforceRetentionLimitsLocked()

        if clearedCategoryIds:
            self.entriesCleared.emit(frozenset(clearedCategoryIds))

        self.entryAdded.emit(entry)

        self._requestEntriesChanged()

        return entry

    def callback(
        self,
        categoryId: str,
        *,
        source: str = '',
        severity: str = '',
    ):
        """Return a safe line callback for a process or another log producer."""

        def appendLine(line):
            """Append one externally produced line without affecting its producer."""
            try:
                self.append(
                    line,
                    categoryId,
                    source=source,
                    severity=severity,
                )
            except Exception:
                # Any non-exit exceptions

                pass

        return appendLine

    def entries(self, categoryId: Optional[str] = None) -> tuple[LogEntry, ...]:
        """Return an immutable snapshot, optionally filtered by category."""
        return self.snapshot(categoryId)[1]

    def snapshot(
        self,
        categoryId: Optional[str] = None,
    ) -> tuple[int, tuple[LogEntry, ...]]:
        """Return the current sequence and its immutable filtered entries."""
        with self._lock:
            if categoryId in (None, ALL_LOGS_FILTER):
                entries = tuple(self._entries)
            else:
                entries = tuple(
                    entry for entry in self._entries if entry.categoryId == categoryId
                )

            return self._sequence, entries

    def clear(
        self,
        categoryId: Optional[str] = None,
        *,
        runtimeOnly: bool = False,
    ):
        """Clear all, one category, or every transient runtime category."""
        if categoryId is not None and runtimeOnly:
            raise ValueError('categoryId and runtimeOnly cannot be combined')

        with self._lock:
            if runtimeOnly:
                clearedCategoryIds = {
                    category.id
                    for category in self._categories.values()
                    if category.runtime
                }
            elif categoryId is None or categoryId == ALL_LOGS_FILTER:
                clearedCategoryIds = None
            else:
                if categoryId not in self._categories:
                    raise KeyError(f'unknown log category {categoryId!r}')

                clearedCategoryIds = {categoryId}

            if clearedCategoryIds is None:
                changed = bool(self._entries)

                self._entries.clear()
                self._retainedCharacters = 0

                for registeredCategoryId in self._categoryEntryCounts:
                    self._categoryEntryCounts[registeredCategoryId] = 0
            else:
                oldLength = len(self._entries)

                self._removeCategoriesLocked(clearedCategoryIds)

                changed = len(self._entries) != oldLength

        if changed:
            self.entriesCleared.emit(
                None if clearedCategoryIds is None else frozenset(clearedCategoryIds)
            )

    def plainText(
        self,
        categoryId: Optional[str] = None,
    ) -> str:
        """Return a plain-text snapshot for exporting or crash diagnostics."""
        return '\n'.join(formatLogEntry(entry) for entry in self.entries(categoryId))


class ApplicationLogHandler(logging.Handler):
    """Convert standard-library log records into structured application entries."""

    def __init__(self, manager: LogManager):
        """Bind the handler to the application-wide log manager."""
        super().__init__()

        if not isinstance(manager, LogManager):
            raise TypeError('manager must be a LogManager')

        self.manager = manager

    def emit(self, record: logging.LogRecord):
        """Publish one logging record without coupling it to a widget."""
        try:
            self.manager.append(
                self.format(record),
                APPLICATION_LOG_CATEGORY,
                timestamp=datetime.fromtimestamp(record.created),
                source=record.name,
                severity=record.levelname,
            )
        except Exception:
            # Any non-exit exceptions

            self.handleError(record)


def coreLogCallback(manager: LogManager):
    """Create a callback for output from the currently selected proxy core."""
    return manager.callback(CORE_LOG_CATEGORY)
