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

from collections import OrderedDict, deque
from datetime import datetime
from heapq import merge
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


class _CategoryEntries:
    """Own one category's ordered entries and aggregate character count."""

    __slots__ = ('entries', 'characterCount')

    def __init__(self):
        """Initialize an empty category index."""
        self.entries: OrderedDict[int, LogEntry] = OrderedDict()
        self.characterCount = 0

    @property
    def entryCount(self) -> int:
        """Return the number of physically owned entries."""
        return len(self.entries)

    def append(self, entry: LogEntry, characterCount: int):
        """Append one entry and update aggregate accounting."""
        self.entries[entry.sequence] = entry
        self.characterCount += characterCount

    def remove(self, sequence: int) -> LogEntry:
        """Remove one known sequence and update aggregate accounting."""
        entry = self.entries.pop(sequence)
        self.characterCount -= len(entry.message)

        return entry

    def discardOldestPhysical(self) -> int:
        """Drop one retired entry and return its released character count."""
        _sequence, entry = self.entries.popitem(last=False)
        characterCount = len(entry.message)
        self.characterCount -= characterCount

        return characterCount


class _EntryGeneration:
    """Own one active or retired chronological generation of log entries."""

    __slots__ = (
        'identifier',
        'scope',
        'entries',
        'entriesByCategory',
        'characterCount',
    )

    def __init__(self, identifier: int, scope: str):
        """Initialize an empty generation for one fixed retention scope."""
        self.identifier = identifier
        self.scope = scope
        self.entries: OrderedDict[int, LogEntry] = OrderedDict()
        self.entriesByCategory: dict[str, _CategoryEntries] = {}
        self.characterCount = 0

    @property
    def entryCount(self) -> int:
        """Return the number of physically owned entries."""
        return len(self.entries)

    def categoryEntries(self, categoryId: str) -> Optional[_CategoryEntries]:
        """Return the active index for one category when it has entries."""
        return self.entriesByCategory.get(categoryId)

    def append(self, entry: LogEntry, characterCount: int):
        """Append the same immutable entry to global and category indexes."""
        categoryEntries = self.entriesByCategory.get(entry.categoryId)

        if categoryEntries is None:
            categoryEntries = _CategoryEntries()
            self.entriesByCategory[entry.categoryId] = categoryEntries

        self.entries[entry.sequence] = entry
        categoryEntries.append(entry, characterCount)
        self.characterCount += characterCount

    def removeOldest(self) -> LogEntry:
        """Remove the oldest entry from both live indexes in constant time."""
        sequence, entry = self.entries.popitem(last=False)
        categoryEntries = self.entriesByCategory[entry.categoryId]
        indexedEntry = categoryEntries.remove(sequence)

        if indexedEntry is not entry:
            raise RuntimeError('log generation indexes diverged')

        if not categoryEntries.entryCount:
            del self.entriesByCategory[entry.categoryId]

        self.characterCount -= len(entry.message)

        return entry

    def detachCategory(self, categoryId: str) -> Optional[_CategoryEntries]:
        """Detach one category while preserving its entries for deferred release.

        Selective deletion must unlink each sequence from this generation's flat
        chronological index. The detached category index retains the LogEntry
        objects so their final decrefs can still be performed in bounded batches.
        """
        categoryEntries = self.entriesByCategory.pop(categoryId, None)

        if categoryEntries is None:
            return None

        for sequence in categoryEntries.entries:
            del self.entries[sequence]

        self.characterCount -= categoryEntries.characterCount

        return categoryEntries

    def discardOldestPhysical(self) -> int:
        """Drop one entry from a retired generation's duplicate indexes."""
        entry = self.removeOldest()

        return len(entry.message)


class LogManager(QtCore.QObject):
    """Own globally ordered logs through small active generation streams.

    Application and runtime entries deliberately share the same hard count and
    character budgets. Generation rollover makes runtime-wide logical clearing
    independent of retained history size, while retired object destruction is
    spread across bounded cleanup batches.
    """

    DefaultMaximumEntries = 10_000
    DefaultAutoClearMaximumEntries = 5_000
    DefaultMaximumCharacters = 8 * 1024 * 1024
    DefaultMaximumEntryCharacters = 64 * 1024
    # At least one stale entry is reclaimed before every new entry is retained.
    # A larger fixed budget lets normal traffic drain old generations quickly;
    # because a clear cannot retire more live entries than maximumEntries, this
    # also bounds the live-plus-retired entry backlog under repeated fast clears.
    RetiredCleanupBudget = 64
    TruncationMarker = '\n... [log entry truncated]'

    categoryRegistered = QtCore.Signal(object)
    entryAdded = QtCore.Signal(object)
    entriesCleared = QtCore.Signal(object)
    entriesChanged = QtCore.Signal(int)

    _entriesChangedRequested = QtCore.Signal()
    _retiredCleanupRequested = QtCore.Signal()

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
        self._sequence = 0
        self._retainedEntryCount = 0
        self._retainedCharacters = 0
        self._generationSequence = 0
        # Three fixed active streams preserve exact global ordering with an O(n)
        # three-way merge and make oldest-live selection constant time. Runtime
        # categories are isolated so disconnect/runtime clear is one reference
        # swap; other non-Application categories use a second generation because
        # Core auto-clear historically clears them too, while runtimeOnly does not.
        self._applicationGeneration = self._newGenerationLocked('application')
        self._runtimeGeneration = self._newGenerationLocked('runtime')
        self._otherGeneration = self._newGenerationLocked('other')
        self._runtimeCategoryIds = frozenset()
        self._nonApplicationCategoryIds = frozenset()
        # Retired batches remain strongly owned until bounded cleanup removes
        # their entries. Merely dropping a large OrderedDict here would make the
        # clear caller synchronously execute thousands of CPython decrefs.
        self._retiredBatches = deque()
        self._retiredEntryCount = 0
        self._retiredCharacters = 0
        self._retiredCleanupPending = False
        self._changeNotificationPending = False

        # LogManager is one application-lifetime QObject parented to the desktop
        # application in production. These are intentional queued self-connections:
        # sender and receiver share one destruction boundary, no transient UI is
        # retained, and pending delivery is discarded when that QObject is destroyed.
        self._entriesChangedRequested.connect(
            self._publishEntriesChanged,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )
        self._retiredCleanupRequested.connect(
            self._cleanupRetired,
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
    def retiredEntryCount(self) -> int:
        """Return logically dead entries awaiting incremental physical release."""
        with self._lock:
            return self._retiredEntryCount

    @property
    def retiredCharacters(self) -> int:
        """Return message characters awaiting incremental physical release."""
        with self._lock:
            return self._retiredCharacters

    @property
    def autoClearMaximumEntries(self) -> int:
        """Return the automatic-clear threshold for replaceable runtime logs."""
        return self._autoClearMaximumEntries

    @property
    def autoClearEnabled(self) -> bool:
        """Return whether automatic clearing triggered by Core is active."""
        with self._lock:
            return self._autoClearEnabled

    def _newGenerationLocked(self, scope: str) -> _EntryGeneration:
        """Create one uniquely identified empty active generation."""
        self._generationSequence += 1

        return _EntryGeneration(self._generationSequence, scope)

    def _activeGenerationsLocked(self) -> tuple[_EntryGeneration, ...]:
        """Return the fixed active streams in merge-independent order."""
        return (
            self._applicationGeneration,
            self._runtimeGeneration,
            self._otherGeneration,
        )

    def _liveEntryCountLocked(self) -> int:
        """Return the incrementally maintained total live entry count."""
        return self._retainedEntryCount

    def _liveCharactersLocked(self) -> int:
        """Return the incrementally maintained total live character count."""
        return self._retainedCharacters

    @staticmethod
    def _generationAttributeForCategory(category: LogCategory) -> str:
        """Return the active generation attribute that owns one category."""
        if category.id == APPLICATION_LOG_CATEGORY:
            return '_applicationGeneration'

        return '_runtimeGeneration' if category.runtime else '_otherGeneration'

    def _generationForCategoryLocked(self, category: LogCategory) -> _EntryGeneration:
        """Return the active generation that owns one registered category."""
        if category.id == APPLICATION_LOG_CATEGORY:
            return self._applicationGeneration

        return self._runtimeGeneration if category.runtime else self._otherGeneration

    def _retireBatchLocked(self, batch):
        """Keep one logically dead non-empty batch for bounded reclamation."""
        if not batch.entryCount:
            return

        self._retiredBatches.append(batch)
        self._retiredEntryCount += batch.entryCount
        self._retiredCharacters += batch.characterCount

    def _rollGenerationLocked(self, attributeName: str) -> int:
        """Swap one active generation and retire its old entries in O(1)."""
        generation = getattr(self, attributeName)
        entryCount = generation.entryCount
        characterCount = generation.characterCount
        setattr(
            self,
            attributeName,
            self._newGenerationLocked(generation.scope),
        )
        self._retainedEntryCount -= entryCount
        self._retainedCharacters -= characterCount
        self._retireBatchLocked(generation)

        return entryCount

    def _clearNonApplicationLocked(self) -> bool:
        """Logically clear every non-Application stream with two swaps."""
        removedEntries = self._rollGenerationLocked('_runtimeGeneration')
        removedEntries += self._rollGenerationLocked('_otherGeneration')

        return bool(removedEntries)

    def _cleanupRetiredLocked(self, budget: Optional[int] = None) -> int:
        """Physically release at most one fixed batch of logically dead entries."""
        remaining = (
            max(1, int(self.RetiredCleanupBudget))
            if budget is None
            else max(0, int(budget))
        )
        cleaned = 0

        while remaining and self._retiredBatches:
            batch = self._retiredBatches[0]
            characterCount = batch.discardOldestPhysical()
            self._retiredEntryCount -= 1
            self._retiredCharacters -= characterCount
            cleaned += 1
            remaining -= 1

            if not batch.entryCount:
                if batch.characterCount:
                    raise RuntimeError('retired log accounting diverged')

                self._retiredBatches.popleft()

        return cleaned

    def _requestRetiredCleanup(self):
        """Queue one bounded reclamation turn when retired entries remain."""
        shouldNotify = False

        with self._lock:
            if self._retiredBatches and not self._retiredCleanupPending:
                self._retiredCleanupPending = True
                shouldNotify = True

        if shouldNotify:
            self._retiredCleanupRequested.emit()

    @QtCore.Slot()
    def _cleanupRetired(self):
        """Release one bounded retired batch on the manager's Qt thread."""
        with self._lock:
            self._retiredCleanupPending = False
            self._cleanupRetiredLocked()
            shouldContinue = bool(self._retiredBatches)

        if shouldContinue:
            self._requestRetiredCleanup()

    def _removeOldestLocked(self):
        """Remove the oldest live entry across three streams in constant time."""
        generations = tuple(
            generation
            for generation in self._activeGenerationsLocked()
            if generation.entryCount
        )

        if not generations:
            raise RuntimeError('cannot evict from an empty log manager')

        oldestGeneration = min(
            generations,
            key=lambda generation: next(iter(generation.entries)),
        )
        entry = oldestGeneration.removeOldest()
        self._retainedEntryCount -= 1
        self._retainedCharacters -= len(entry.message)

    def _enforceRetentionLimitsLocked(self):
        """Evict the oldest entries until every hard retention limit is met."""
        while self._liveEntryCountLocked() and (
            self._liveEntryCountLocked() > self._maximumEntries
            or self._liveCharactersLocked() > self._maximumCharacters
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

    def _markEntriesChangedLocked(self) -> bool:
        """Mark one coalesced presentation notification while already locked."""
        if self._changeNotificationPending:
            return False

        self._changeNotificationPending = True

        return True

    @QtCore.Slot()
    def _publishEntriesChanged(self):
        """Publish the newest sequence once on the manager's Qt thread."""
        with self._lock:
            self._changeNotificationPending = False
            sequence = self._sequence

        self.entriesChanged.emit(sequence)

    def setAutoClearEnabled(self, enabled: bool):
        """Apply Core-triggered clearing without involving presentation state."""
        clearedCategoryIds = frozenset()

        with self._lock:
            self._autoClearEnabled = bool(enabled)

            if (
                self._autoClearEnabled
                and self._categoryEntryCountLocked(CORE_LOG_CATEGORY)
                >= self._autoClearMaximumEntries
            ):
                clearedCategoryIds = self._nonApplicationCategoryIds
                self._clearNonApplicationLocked()

        if clearedCategoryIds:
            self._requestRetiredCleanup()
            self.entriesCleared.emit(clearedCategoryIds)

    def _categoryEntryCountLocked(self, categoryId: str) -> int:
        """Return one registered category's live count in constant time."""
        category = self._categories[categoryId]
        generation = self._generationForCategoryLocked(category)
        categoryEntries = generation.categoryEntries(categoryId)

        return categoryEntries.entryCount if categoryEntries is not None else 0

    def entryCount(self, categoryId: Optional[str] = None) -> int:
        """Return the retained total or one category count in constant time."""
        with self._lock:
            if categoryId in (None, ALL_LOGS_FILTER):
                return self._liveEntryCountLocked()

            if categoryId not in self._categories:
                raise KeyError(f'unknown log category {categoryId!r}')

            return self._categoryEntryCountLocked(categoryId)

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

            if category.id != APPLICATION_LOG_CATEGORY:
                self._nonApplicationCategoryIds = self._nonApplicationCategoryIds.union(
                    {category.id}
                )

            if category.runtime:
                self._runtimeCategoryIds = self._runtimeCategoryIds.union({category.id})

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
        """Append with fixed cleanup work and notify interested presenters."""
        clearedCategoryIds = frozenset()
        shouldNotifyEntriesChanged = False
        retiredCleanupNeeded = False

        with self._lock:
            category = self._categories.get(categoryId)

            if category is None:
                raise KeyError(f'unknown log category {categoryId!r}')

            # Reclamation is deliberately entry-budgeted rather than generation-
            # budgeted. Even if a previous clear retired thousands of objects,
            # this append performs at most RetiredCleanupBudget physical releases.
            if self._retiredBatches:
                self._cleanupRetiredLocked()

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
                and self._categoryEntryCountLocked(CORE_LOG_CATEGORY)
                >= self._autoClearMaximumEntries
            ):
                # When the next Core line would exceed its threshold, retain
                # only Application diagnostics. All other categories belong
                # to two replaceable streams that roll over without touching
                # their entries or performing synchronous object destruction.
                clearedCategoryIds = self._nonApplicationCategoryIds
                self._clearNonApplicationLocked()

            characterCount = len(entry.message)
            generation = self._generationForCategoryLocked(category)
            generation.append(entry, characterCount)
            self._retainedEntryCount += 1
            self._retainedCharacters += characterCount
            self._enforceRetentionLimitsLocked()
            shouldNotifyEntriesChanged = self._markEntriesChangedLocked()
            retiredCleanupNeeded = bool(self._retiredBatches)

        if clearedCategoryIds:
            self.entriesCleared.emit(clearedCategoryIds)

        self.entryAdded.emit(entry)

        if shouldNotifyEntriesChanged:
            self._entriesChangedRequested.emit()

        if retiredCleanupNeeded:
            self._requestRetiredCleanup()

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
        """Return an O(n) global or O(k) category-specific immutable snapshot."""
        with self._lock:
            if categoryId in (None, ALL_LOGS_FILTER):
                # Exactly three sorted active streams make heap merge O(n) with
                # a constant fan-in. Retired generations are never visited, so
                # logically cleared entries cannot tax or leak into snapshots.
                entries = tuple(
                    merge(
                        *(
                            generation.entries.values()
                            for generation in self._activeGenerationsLocked()
                        ),
                        key=lambda entry: entry.sequence,
                    )
                )
            else:
                category = self._categories.get(categoryId)

                if category is None:
                    entries = tuple()
                else:
                    generation = self._generationForCategoryLocked(category)
                    categoryEntries = generation.categoryEntries(categoryId)
                    entries = (
                        tuple(categoryEntries.entries.values())
                        if categoryEntries is not None
                        else tuple()
                    )

            return self._sequence, entries

    def clear(
        self,
        categoryId: Optional[str] = None,
        *,
        runtimeOnly: bool = False,
    ):
        """Logically clear a generation or selectively unlink one category.

        Whole-history, Application-only, runtime-only, and sole-category clears
        are O(1) generation swaps. A category sharing a generation with other
        live categories requires O(k) keyed unlinks to keep the active stream
        tombstone-free for exact oldest-live eviction and O(n) global snapshots.
        Its LogEntry destruction is still deferred in bounded cleanup batches.
        """
        if categoryId is not None and runtimeOnly:
            raise ValueError('categoryId and runtimeOnly cannot be combined')

        with self._lock:
            if runtimeOnly:
                clearedCategoryIds = self._runtimeCategoryIds
                changed = bool(self._rollGenerationLocked('_runtimeGeneration'))
            elif categoryId is None or categoryId == ALL_LOGS_FILTER:
                clearedCategoryIds = None
                changed = bool(self._liveEntryCountLocked())

                self._rollGenerationLocked('_applicationGeneration')
                self._rollGenerationLocked('_runtimeGeneration')
                self._rollGenerationLocked('_otherGeneration')
            else:
                category = self._categories.get(categoryId)

                if category is None:
                    raise KeyError(f'unknown log category {categoryId!r}')

                clearedCategoryIds = frozenset({categoryId})
                attributeName = self._generationAttributeForCategory(category)
                generation = getattr(self, attributeName)
                categoryEntries = generation.categoryEntries(categoryId)
                changed = categoryEntries is not None

                if changed and categoryEntries.entryCount == generation.entryCount:
                    self._rollGenerationLocked(attributeName)
                elif changed:
                    retiredCategory = generation.detachCategory(categoryId)

                    if retiredCategory is None:
                        raise RuntimeError(
                            'log category index disappeared during clear'
                        )

                    self._retainedEntryCount -= retiredCategory.entryCount
                    self._retainedCharacters -= retiredCategory.characterCount
                    self._retireBatchLocked(retiredCategory)

        if changed:
            self._requestRetiredCleanup()
            self.entriesCleared.emit(
                None if clearedCategoryIds is None else clearedCategoryIds
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
