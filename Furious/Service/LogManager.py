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
from dataclasses import dataclass
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
    'LogCursor',
    'LogEntryBatch',
    'LogManager',
    'formatLogEntry',
]

ALL_LOGS_FILTER = 'all'
APPLICATION_LOG_CATEGORY = 'application'
CORE_LOG_CATEGORY = 'core'
TUN2SOCKS_LOG_CATEGORY = 'component.tun2socks'


@dataclass(frozen=True)
class LogCursor:
    """Opaque synchronization position for one filtered live-log view.

    Instances are issued by :meth:`LogManager.entriesSince`. Callers should
    retain and pass them back unchanged rather than construct them or interpret
    their fields. In particular, ``generationStates`` encodes private generation
    identities and revisions whose representation may change independently of
    this API.
    """

    sequence: int
    categoryId: str
    generationStates: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class LogEntryBatch:
    """Describe one incremental suffix or a required full resynchronization."""

    cursor: LogCursor
    entries: tuple[LogEntry, ...]
    firstRetainedSequence: Optional[int]
    resetRequired: bool = False


def formatLogEntry(entry: LogEntry) -> str:
    """Return the producer-formatted text stored by one structured entry."""
    return entry.message


class _LogCallback:
    """Adapt one fixed log route to single-line and batch producers."""

    __slots__ = ('manager', 'categoryId', 'source', 'severity')

    def __init__(self, manager, categoryId: str, source: str, severity: str):
        """Capture one application-lifetime manager route."""
        self.manager = manager
        self.categoryId = categoryId
        self.source = source
        self.severity = severity

    def __call__(self, line):
        """Append one line safely and return its entry, or ``None`` on failure."""
        try:
            return self.manager.append(
                line,
                self.categoryId,
                source=self.source,
                severity=self.severity,
            )
        except Exception:
            # Any non-exit exceptions

            return None

    def appendMany(self, lines):
        """Append one natural producer batch under the same safe contract."""
        try:
            return self.manager.appendMany(
                lines,
                self.categoryId,
                source=self.source,
                severity=self.severity,
            )
        except Exception:
            # Any non-exit exceptions

            return tuple()


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
        'revision',
    )

    def __init__(self, identifier: int, scope: str):
        """Initialize an empty generation for one fixed retention scope."""
        self.identifier = identifier
        self.scope = scope
        self.entries: OrderedDict[int, LogEntry] = OrderedDict()
        self.entriesByCategory: dict[str, _CategoryEntries] = {}
        self.characterCount = 0
        self.revision = 0

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
        self.revision += 1

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
    # Append-side cleanup charges one small unit per accepted input to keep
    # producer latency stable. Queued Qt cleanup uses a larger bounded turn to
    # drain idle backlogs. Together they bound live-plus-retired entries under
    # repeated fast clears without making a rollover release its own generation.
    RetiredCleanupBudget = 64
    AppendRetiredCleanupBudget = 1
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
        """Release a bounded number of retired entries in global FIFO order.

        The bound counts entries, not retired batches, and may therefore cross
        batch boundaries. ``RetiredCleanupBudget`` supplies the default bound.
        """
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

    @staticmethod
    def _normalizedCategoryId(categoryId: Optional[str]) -> str:
        """Return the canonical filter identifier used by incremental cursors."""
        return ALL_LOGS_FILTER if categoryId in (None, ALL_LOGS_FILTER) else categoryId

    def _generationStatesLocked(
        self,
        categoryId: str,
    ) -> tuple[tuple[int, int], ...]:
        """Return the active structural state relevant to one filtered view."""
        if categoryId == ALL_LOGS_FILTER:
            return tuple(
                (generation.identifier, generation.revision)
                for generation in self._activeGenerationsLocked()
            )

        category = self._categories.get(categoryId)

        if category is None:
            return tuple()

        generation = self._generationForCategoryLocked(category)

        return ((generation.identifier, generation.revision),)

    def _entriesLocked(self, categoryId: str) -> tuple[LogEntry, ...]:
        """Return the complete active entries for one canonical filter."""
        if categoryId == ALL_LOGS_FILTER:
            return tuple(
                merge(
                    *(
                        generation.entries.values()
                        for generation in self._activeGenerationsLocked()
                    ),
                    key=lambda entry: entry.sequence,
                )
            )

        category = self._categories.get(categoryId)

        if category is None:
            return tuple()

        generation = self._generationForCategoryLocked(category)
        categoryEntries = generation.categoryEntries(categoryId)

        return (
            tuple(categoryEntries.entries.values())
            if categoryEntries is not None
            else tuple()
        )

    @staticmethod
    def _orderedEntriesAfter(entries, sequence: int) -> tuple[LogEntry, ...]:
        """Read only the suffix newer than *sequence* from one ordered index."""
        suffix = []

        for entry in reversed(entries.values()):
            if entry.sequence <= sequence:
                break

            suffix.append(entry)

        suffix.reverse()

        return tuple(suffix)

    def _entriesAfterLocked(
        self,
        sequence: int,
        categoryId: str,
    ) -> tuple[LogEntry, ...]:
        """Return only active entries newer than one valid cursor sequence."""
        if categoryId == ALL_LOGS_FILTER:
            return tuple(
                merge(
                    *(
                        self._orderedEntriesAfter(generation.entries, sequence)
                        for generation in self._activeGenerationsLocked()
                    ),
                    key=lambda entry: entry.sequence,
                )
            )

        category = self._categories.get(categoryId)

        if category is None:
            return tuple()

        generation = self._generationForCategoryLocked(category)
        categoryEntries = generation.categoryEntries(categoryId)

        return (
            self._orderedEntriesAfter(categoryEntries.entries, sequence)
            if categoryEntries is not None
            else tuple()
        )

    def _firstRetainedSequenceLocked(self, categoryId: str) -> Optional[int]:
        """Return the oldest sequence still visible through one filter."""
        if categoryId == ALL_LOGS_FILTER:
            heads = (
                next(iter(generation.entries))
                for generation in self._activeGenerationsLocked()
                if generation.entryCount
            )

            return min(heads, default=None)

        category = self._categories.get(categoryId)

        if category is None:
            return None

        generation = self._generationForCategoryLocked(category)
        categoryEntries = generation.categoryEntries(categoryId)

        if categoryEntries is None:
            return None

        return next(iter(categoryEntries.entries))

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
        """Append one entry while preserving the compatibility signal contract."""
        return self.appendMany(
            (message,),
            categoryId,
            timestamp=timestamp,
            source=source,
            severity=severity,
        )[0]

    def appendMany(
        self,
        messages,
        categoryId: str = APPLICATION_LOG_CATEGORY,
        *,
        timestamp: Optional[datetime] = None,
        source: str = '',
        severity: str = '',
    ) -> tuple[LogEntry, ...]:
        """Atomically append a batch, then emit compatibility events in order.

        ``entryAdded`` observers see the fully committed batch, never an
        intermediate collection state. Presenters should use ``entriesChanged``
        and ``entriesSince`` instead of treating ``entryAdded`` as UI state.
        """
        messages = tuple(messages)

        if not messages:
            return tuple()

        if timestamp is not None and not isinstance(timestamp, datetime):
            raise TypeError('log timestamp must be a datetime')

        events = []
        shouldNotifyEntriesChanged = False
        retiredCleanupNeeded = False

        with self._lock:
            category = self._categories.get(categoryId)

            if category is None:
                raise KeyError(f'unknown log category {categoryId!r}')

            # Validate every caller-controlled conversion before changing the
            # collection so a malformed item cannot leave a silent partial batch.
            normalizedMessages = tuple(
                self._normalizeMessage(message) for message in messages
            )
            normalizedSource = str(source) if source else ''
            normalizedSeverity = str(severity) if severity else ''

            for normalizedMessage in normalizedMessages:
                # Reclaim before accepting the next input so a Core-triggering
                # append itself retains O(1) generation-rollover latency. A
                # tiny per-input charge still bounds backlog across large batches.
                if self._retiredBatches:
                    self._cleanupRetiredLocked(
                        max(1, int(self.AppendRetiredCleanupBudget))
                    )

                entryTimestamp = datetime.now() if timestamp is None else timestamp
                self._sequence += 1

                entry = LogEntry(
                    message=normalizedMessage,
                    timestamp=entryTimestamp,
                    categoryId=category.id,
                    categoryLabel=category.displayName,
                    categoryTranslatable=category.translatable,
                    source=normalizedSource,
                    severity=normalizedSeverity,
                    sequence=self._sequence,
                )
                clearedCategoryIds = frozenset()

                if (
                    category.id == CORE_LOG_CATEGORY
                    and self._autoClearEnabled
                    and self._categoryEntryCountLocked(CORE_LOG_CATEGORY)
                    >= self._autoClearMaximumEntries
                ):
                    # Preserve repeated-append Core rollover semantics within
                    # the batch, including the clear-before-entry signal order.
                    clearedCategoryIds = self._nonApplicationCategoryIds

                    self._clearNonApplicationLocked()

                characterCount = len(entry.message)
                generation = self._generationForCategoryLocked(category)
                generation.append(entry, characterCount)

                self._retainedEntryCount += 1
                self._retainedCharacters += characterCount
                self._enforceRetentionLimitsLocked()

                events.append((clearedCategoryIds, entry))

            shouldNotifyEntriesChanged = self._markEntriesChangedLocked()
            retiredCleanupNeeded = bool(self._retiredBatches)

        for clearedCategoryIds, entry in events:
            if clearedCategoryIds:
                self.entriesCleared.emit(clearedCategoryIds)

            # Kept for compatibility and non-presentation observers. LogPage
            # deliberately pulls a coalesced batch through entriesSince().
            self.entryAdded.emit(entry)

        if shouldNotifyEntriesChanged:
            self._entriesChangedRequested.emit()

        if retiredCleanupNeeded:
            self._requestRetiredCleanup()

        return tuple(entry for _clearedCategoryIds, entry in events)

    def callback(
        self,
        categoryId: str,
        *,
        source: str = '',
        severity: str = '',
    ):
        """Return a safe callable supporting single lines and natural batches."""
        return _LogCallback(self, categoryId, source, severity)

    def entries(self, categoryId: Optional[str] = None) -> tuple[LogEntry, ...]:
        """Return an immutable snapshot, optionally filtered by category."""
        return self.snapshot(categoryId)[1]

    def snapshot(
        self,
        categoryId: Optional[str] = None,
    ) -> tuple[int, tuple[LogEntry, ...]]:
        """Return an O(n) global or O(k) category-specific immutable snapshot."""
        with self._lock:
            return (
                self._sequence,
                self._entriesLocked(self._normalizedCategoryId(categoryId)),
            )

    def entriesSince(
        self,
        cursor: Optional[LogCursor] = None,
        categoryId: Optional[str] = None,
    ) -> LogEntryBatch:
        """Return one atomic filtered suffix and its next synchronization cursor.

        Treat ``LogEntryBatch.cursor`` as opaque and pass it back unchanged with
        the same filter on the next call.

        A missing or structurally invalid cursor returns the complete retained
        view with ``resetRequired`` set. Retention-only prefix eviction keeps the
        cursor valid; ``firstRetainedSequence`` lets a presenter prune exactly
        that obsolete prefix without rebuilding or copying retained history.
        """
        if cursor is not None and not isinstance(cursor, LogCursor):
            raise TypeError('cursor must be a LogCursor or None')

        normalizedCategoryId = self._normalizedCategoryId(categoryId)

        with self._lock:
            generationStates = self._generationStatesLocked(normalizedCategoryId)
            resetRequired = (
                cursor is None
                or cursor.categoryId != normalizedCategoryId
                or cursor.generationStates != generationStates
                or cursor.sequence > self._sequence
            )
            entries = (
                self._entriesLocked(normalizedCategoryId)
                if resetRequired
                else self._entriesAfterLocked(cursor.sequence, normalizedCategoryId)
            )
            nextCursor = LogCursor(
                sequence=self._sequence,
                categoryId=normalizedCategoryId,
                generationStates=generationStates,
            )

            return LogEntryBatch(
                cursor=nextCursor,
                entries=entries,
                firstRetainedSequence=self._firstRetainedSequenceLocked(
                    normalizedCategoryId
                ),
                resetRequired=resetRequired,
            )

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
