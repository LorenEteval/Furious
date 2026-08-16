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

    categoryRegistered = QtCore.Signal(object)
    entryAdded = QtCore.Signal(object)
    entriesCleared = QtCore.Signal(object)

    def __init__(self, parent=None, *, maximumEntries=DefaultMaximumEntries):
        """Initialize the category registry and thread-safe entry collection."""
        super().__init__(parent)

        if (
            isinstance(maximumEntries, bool)
            or not isinstance(maximumEntries, int)
            or maximumEntries <= 0
        ):
            raise ValueError('maximumEntries must be a positive integer')

        self._lock = threading.RLock()
        self._categories: dict[str, LogCategory] = {}
        self._maximumEntries = maximumEntries
        self._entries: deque[LogEntry] = deque(maxlen=maximumEntries)
        self._sequence = 0

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
                message=str(message).rstrip('\r\n'),
                timestamp=timestamp,
                categoryId=category.id,
                categoryLabel=category.displayName,
                categoryTranslatable=category.translatable,
                source=str(source) if source else '',
                severity=str(severity) if severity else '',
                sequence=self._sequence,
            )

            self._entries.append(entry)

        self.entryAdded.emit(entry)

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
            else:
                oldLength = len(self._entries)

                self._entries = deque(
                    (
                        entry
                        for entry in self._entries
                        if entry.categoryId not in clearedCategoryIds
                    ),
                    maxlen=self._maximumEntries,
                )

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
            categoryId = getattr(
                record,
                'furiousCategory',
                APPLICATION_LOG_CATEGORY,
            )

            if self.manager.category(categoryId) is None:
                categoryId = APPLICATION_LOG_CATEGORY

            self.manager.append(
                self.format(record),
                categoryId,
                timestamp=datetime.fromtimestamp(record.created),
                source=getattr(record, 'furiousSource', record.name),
                severity=record.levelname,
            )
        except Exception:
            # Any non-exit exceptions

            self.handleError(record)


def coreLogCallback(manager: LogManager):
    """Create a callback for output from the currently selected proxy core."""
    return manager.callback(CORE_LOG_CATEGORY)
