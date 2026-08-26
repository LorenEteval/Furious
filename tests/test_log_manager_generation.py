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

"""Adversarial contracts for the generation-based structured log store.

The fast tests emphasize structural evidence and an independent reference
model.  The opt-in class adds high-count timing, reclamation, and soak probes;
enable it with the repository-wide ``FURIOUS_VERY_HEAVY_TESTS`` switch.
"""

from __future__ import annotations

from Furious.Models import LogCategory
from Furious.Service.LogManager import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)
from Furious.Window.LogPage import LogPage

from collections import OrderedDict
from datetime import datetime
from statistics import median

import gc
import json
import os
import random
import subprocess
import threading
import time
import types
import unittest
import weakref

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    resourceSnapshot,
    veryHeavyEnabled,
    waitFor,
)


class _ObservedEntries(OrderedDict):
    """Count container primitives without changing OrderedDict semantics."""

    def __init__(self, entries=()):
        self.iterations = 0
        self.deletions = 0
        self.oldestRemovals = 0
        super().__init__(entries)

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()

    def values(self):
        self.iterations += 1
        return super().values()

    def items(self):
        self.iterations += 1
        return super().items()

    def keys(self):
        self.iterations += 1
        return super().keys()

    def __delitem__(self, key):
        self.deletions += 1
        return super().__delitem__(key)

    def popitem(self, last=True):
        if not last:
            self.oldestRemovals += 1
        return super().popitem(last=last)


class _ReferenceLog:
    """Slow, deliberately flat model of public LogManager semantics."""

    def __init__(self, manager):
        self.maximumEntries = manager.maximumEntries
        self.maximumCharacters = manager.maximumCharacters
        self.autoClearMaximumEntries = manager.autoClearMaximumEntries
        self.autoClearEnabled = manager.autoClearEnabled
        self.categories = {category.id: category for category in manager.categories()}
        self.entries = []

    def register(self, category):
        self.categories.setdefault(category.id, category)

    def beforeAppend(self, categoryId):
        if (
            categoryId == CORE_LOG_CATEGORY
            and self.autoClearEnabled
            and self.count(CORE_LOG_CATEGORY) >= self.autoClearMaximumEntries
        ):
            self.entries = [
                entry
                for entry in self.entries
                if entry.categoryId == APPLICATION_LOG_CATEGORY
            ]

    def accept(self, entry):
        self.entries.append(entry)
        while self.entries and (
            len(self.entries) > self.maximumEntries
            or sum(len(item.message) for item in self.entries) > self.maximumCharacters
        ):
            del self.entries[0]

    def clear(self, categoryId=None, *, runtimeOnly=False):
        if categoryId is None:
            if runtimeOnly:
                self.entries = [
                    entry
                    for entry in self.entries
                    if not self.categories[entry.categoryId].runtime
                ]
            else:
                self.entries.clear()
            return

        self.entries = [
            entry for entry in self.entries if entry.categoryId != categoryId
        ]

    def setAutoClearEnabled(self, enabled):
        self.autoClearEnabled = bool(enabled)
        if (
            self.autoClearEnabled
            and self.count(CORE_LOG_CATEGORY) >= self.autoClearMaximumEntries
        ):
            self.entries = [
                entry
                for entry in self.entries
                if entry.categoryId == APPLICATION_LOG_CATEGORY
            ]

    def count(self, categoryId):
        return sum(entry.categoryId == categoryId for entry in self.entries)


def _batchEntries(batch):
    """Enumerate one retired owner without trusting manager counters."""
    return tuple(batch.entries.values())


def _assertManagerInvariants(testCase, manager, model=None):
    """Independently prove ownership, indexing, accounting, and ordering.

    This helper intentionally derives truth from the actual entry objects in
    both ownership indexes.  It then compares the public API and every cached
    aggregate against that derivation, so a defect cannot hide merely because
    two manager counters drift in the same direction.
    """
    with manager._lock:
        generations = manager._activeGenerationsLocked()
        testCase.assertEqual(len(generations), 3)
        testCase.assertEqual(len({id(item) for item in generations}), 3)
        testCase.assertEqual(len({item.identifier for item in generations}), 3)
        testCase.assertEqual(
            tuple(item.scope for item in generations),
            ('application', 'runtime', 'other'),
        )

        liveEntries = []
        liveObjectIds = set()
        categoryTruth = {category.id: [] for category in manager.categories()}

        for generation in generations:
            chronological = tuple(generation.entries.values())
            testCase.assertEqual(
                tuple(entry.sequence for entry in chronological),
                tuple(sorted(entry.sequence for entry in chronological)),
            )
            testCase.assertEqual(
                generation.characterCount,
                sum(len(entry.message) for entry in chronological),
            )

            indexedSequences = []
            for categoryId, categoryEntries in generation.entriesByCategory.items():
                category = manager._categories[categoryId]
                testCase.assertIs(
                    manager._generationForCategoryLocked(category), generation
                )
                indexed = tuple(categoryEntries.entries.values())
                testCase.assertTrue(indexed)
                testCase.assertEqual(
                    tuple(entry.sequence for entry in indexed),
                    tuple(sorted(entry.sequence for entry in indexed)),
                )
                testCase.assertTrue(
                    all(entry.categoryId == categoryId for entry in indexed)
                )
                testCase.assertEqual(
                    categoryEntries.characterCount,
                    sum(len(entry.message) for entry in indexed),
                )
                indexedSequences.extend(entry.sequence for entry in indexed)
                categoryTruth[categoryId].extend(indexed)

            testCase.assertCountEqual(
                indexedSequences,
                (entry.sequence for entry in chronological),
            )
            for entry in chronological:
                testCase.assertNotIn(id(entry), liveObjectIds)
                liveObjectIds.add(id(entry))
            liveEntries.extend(chronological)

        liveEntries.sort(key=lambda entry: entry.sequence)
        testCase.assertEqual(
            tuple(entry.sequence for entry in liveEntries),
            tuple(sorted({entry.sequence for entry in liveEntries})),
        )
        testCase.assertEqual(manager._retainedEntryCount, len(liveEntries))
        testCase.assertEqual(
            manager._retainedCharacters,
            sum(len(entry.message) for entry in liveEntries),
        )
        testCase.assertGreaterEqual(manager._retainedEntryCount, 0)
        testCase.assertGreaterEqual(manager._retainedCharacters, 0)

        retiredEntries = []
        for batch in manager._retiredBatches:
            entries = _batchEntries(batch)
            testCase.assertEqual(
                batch.characterCount,
                sum(len(entry.message) for entry in entries),
            )
            retiredEntries.extend(entries)

        retiredIds = {id(entry) for entry in retiredEntries}
        testCase.assertTrue(liveObjectIds.isdisjoint(retiredIds))
        testCase.assertEqual(len(retiredEntries), manager._retiredEntryCount)
        testCase.assertEqual(
            sum(len(entry.message) for entry in retiredEntries),
            manager._retiredCharacters,
        )
        testCase.assertGreaterEqual(manager._retiredEntryCount, 0)
        testCase.assertGreaterEqual(manager._retiredCharacters, 0)

        publicEntries = manager.entries()
        testCase.assertEqual(publicEntries, tuple(liveEntries))
        testCase.assertTrue(retiredIds.isdisjoint(id(entry) for entry in publicEntries))
        testCase.assertEqual(manager.entryCount(), len(liveEntries))
        testCase.assertEqual(
            manager.retainedCharacters,
            sum(len(entry.message) for entry in liveEntries),
        )

        for category in manager.categories():
            expected = tuple(categoryTruth[category.id])
            testCase.assertEqual(manager.entries(category.id), expected)
            testCase.assertEqual(manager.entryCount(category.id), len(expected))

    if model is not None:
        testCase.assertEqual(
            tuple(entry.sequence for entry in manager.entries()),
            tuple(entry.sequence for entry in model.entries),
        )
        testCase.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            tuple(entry.message for entry in model.entries),
        )


def _percentile(samples, percentage):
    """Return a nearest-rank percentile from nanosecond samples."""
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * percentage))
    return ordered[index] / 1_000


class GenerationLogManagerContractTest(unittest.TestCase):
    """Exercise exact semantics and structural complexity in the fast tier."""

    @classmethod
    def setUpClass(cls):
        application()

    def makeManager(self, **kwargs):
        defaults = {
            'maximumEntries': 37,
            'maximumCharacters': 400,
            'maximumEntryCharacters': 80,
            'autoClearMaximumEntries': 5,
        }
        defaults.update(kwargs)
        manager = LogManager(**defaults)
        manager.registerComponent('runtime.extra', 'Runtime extra', runtime=True)
        manager.registerComponent('other.extra', 'Other extra', runtime=False)
        return manager

    def appendBoth(self, manager, model, message, categoryId):
        model.beforeAppend(categoryId)
        entry = manager.append(message, categoryId)
        model.accept(entry)
        _assertManagerInvariants(self, manager, model)
        return entry

    def testDeterministicStateTransitionMatrix(self):
        """Mix every clear kind, rollover, retention mode, and stream."""
        manager = self.makeManager(
            maximumEntries=7,
            maximumCharacters=35,
            maximumEntryCharacters=35,
        )
        model = _ReferenceLog(manager)
        operations = (
            ('a', APPLICATION_LOG_CATEGORY),
            ('r', 'runtime.extra'),
            ('o', 'other.extra'),
            ('c1', CORE_LOG_CATEGORY),
            ('t', TUN2SOCKS_LOG_CATEGORY),
            ('c2', CORE_LOG_CATEGORY),
        )
        for message, categoryId in operations:
            self.appendBoth(manager, model, message, categoryId)

        manager.clear('runtime.extra')
        model.clear('runtime.extra')
        _assertManagerInvariants(self, manager, model)
        manager.clear(runtimeOnly=True)
        model.clear(runtimeOnly=True)
        _assertManagerInvariants(self, manager, model)

        for index in range(9):
            self.appendBoth(manager, model, f'core-{index}', CORE_LOG_CATEGORY)

        manager.setAutoClearEnabled(False)
        model.setAutoClearEnabled(False)
        manager.clear('other.extra')
        model.clear('other.extra')
        self.appendBoth(manager, model, 'x' * 80, 'other.extra')
        self.appendBoth(manager, model, 'y' * 81, APPLICATION_LOG_CATEGORY)
        manager.clear()
        model.clear()
        _assertManagerInvariants(self, manager, model)
        self.appendBoth(manager, model, 'after-clear', APPLICATION_LOG_CATEGORY)

    def testSeededModelBasedStateMachine(self):
        """Compare arbitrary public transitions to a flat reference model."""
        seeds = (0, 1, 7, 19, 41, 97, 313, 997)
        for seed in seeds:
            with self.subTest(seed=seed):
                randomizer = random.Random(seed)
                manager = self.makeManager()
                manager.RetiredCleanupBudget = randomizer.choice((1, 2, 64))
                model = _ReferenceLog(manager)
                categories = tuple(model.categories)
                history = []

                for operationIndex in range(350):
                    operation = randomizer.randrange(100)
                    try:
                        if operation < 66:
                            categoryId = randomizer.choice(categories)
                            message = randomizer.choice(
                                ('', 'x', 'line\n', '😀é', '\0', 'z' * 93)
                            )
                            history.append(('append', categoryId, len(message)))
                            self.appendBoth(manager, model, message, categoryId)
                        elif operation < 73:
                            categoryId = randomizer.choice(categories)
                            history.append(('clear-category', categoryId))
                            manager.clear(categoryId)
                            model.clear(categoryId)
                        elif operation < 80:
                            history.append(('clear-runtime',))
                            manager.clear(runtimeOnly=True)
                            model.clear(runtimeOnly=True)
                        elif operation < 84:
                            history.append(('clear-all',))
                            manager.clear()
                            model.clear()
                        elif operation < 91:
                            enabled = bool(randomizer.getrandbits(1))
                            history.append(('auto-clear', enabled))
                            manager.setAutoClearEnabled(enabled)
                            model.setAutoClearEnabled(enabled)
                        else:
                            history.append(('read',))
                            manager.snapshot(randomizer.choice((None, *categories)))

                        _assertManagerInvariants(self, manager, model)
                    except Exception as error:
                        self.fail(
                            f'seed={seed} operation={operationIndex} error={error!r} '
                            f'history={history!r}'
                        )

    def testRolloverAndClearUseConstantStructuralWork(self):
        """Prove logical swaps never traverse, unlink, or pop old entries."""
        for size in (1, 100, 1_000, 10_000):
            with self.subTest(size=size):
                manager = self.makeManager(
                    maximumEntries=size * 3 + 10,
                    maximumCharacters=size * 30 + 100,
                    autoClearMaximumEntries=size,
                )
                for index in range(size):
                    manager.append(f'core {index}', CORE_LOG_CATEGORY)
                    manager.append(f'other {index}', 'other.extra')

                observed = []
                for generation in manager._activeGenerationsLocked():
                    index = _ObservedEntries(generation.entries)
                    generation.entries = index
                    observed.append(index)

                manager.append('trigger', CORE_LOG_CATEGORY)
                self.assertEqual(sum(item.iterations for item in observed), 0)
                self.assertEqual(sum(item.deletions for item in observed), 0)
                self.assertEqual(sum(item.oldestRemovals for item in observed), 0)
                self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 1)
                self.assertEqual(manager.entryCount('other.extra'), 0)

                for index in range(size):
                    manager.append(f'runtime {index}', 'runtime.extra')
                runtime = manager._runtimeGeneration
                watchedRuntime = _ObservedEntries(runtime.entries)
                runtime.entries = watchedRuntime
                manager.clear(runtimeOnly=True)
                self.assertEqual(watchedRuntime.iterations, 0)
                self.assertEqual(watchedRuntime.oldestRemovals, 0)

                manager.append('application', APPLICATION_LOG_CATEGORY)
                watched = []
                for generation in manager._activeGenerationsLocked():
                    index = _ObservedEntries(generation.entries)
                    generation.entries = index
                    watched.append(index)
                manager.clear()
                self.assertEqual(sum(item.iterations for item in watched), 0)
                self.assertEqual(sum(item.oldestRemovals for item in watched), 0)
                _assertManagerInvariants(self, manager)

    def testEmptyRolloversDoNotQueueBatchesOrReuseGenerationIds(self):
        """Swap empty streams repeatedly without retired-queue amplification."""
        manager = self.makeManager(autoClearEnabled=False)
        identifiers = set()
        for _index in range(2_000):
            manager.clear()
            current = tuple(
                generation.identifier
                for generation in manager._activeGenerationsLocked()
            )
            self.assertTrue(identifiers.isdisjoint(current))
            identifiers.update(current)
            self.assertEqual(manager.retiredEntryCount, 0)
            self.assertEqual(len(manager._retiredBatches), 0)
        _assertManagerInvariants(self, manager)

    def testSnapshotAndOldestEvictionInspectOnlyFixedIndexes(self):
        """Count one category traversal and at most three live stream heads."""
        manager = self.makeManager(
            maximumEntries=3,
            maximumCharacters=100,
            maximumEntryCharacters=100,
            autoClearEnabled=False,
        )
        for categoryId in (
            APPLICATION_LOG_CATEGORY,
            CORE_LOG_CATEGORY,
            'other.extra',
        ):
            manager.append(categoryId, categoryId)

        globalIndexes = []
        categoryIndexes = []
        for generation in manager._activeGenerationsLocked():
            observed = _ObservedEntries(generation.entries)
            generation.entries = observed
            globalIndexes.append(observed)
            for categoryEntries in generation.entriesByCategory.values():
                observed = _ObservedEntries(categoryEntries.entries)
                categoryEntries.entries = observed
                categoryIndexes.append(observed)

        manager.snapshot(CORE_LOG_CATEGORY)
        self.assertEqual(sum(index.iterations for index in globalIndexes), 0)
        self.assertEqual(sum(index.iterations for index in categoryIndexes), 1)
        for index in (*globalIndexes, *categoryIndexes):
            index.iterations = 0

        manager.snapshot()
        self.assertEqual(sum(index.iterations for index in globalIndexes), 3)
        self.assertEqual(sum(index.iterations for index in categoryIndexes), 0)
        for index in globalIndexes:
            index.iterations = 0

        manager.append('evict', CORE_LOG_CATEGORY)
        self.assertLessEqual(sum(index.iterations for index in globalIndexes), 3)
        self.assertEqual(sum(index.oldestRemovals for index in globalIndexes), 1)
        _assertManagerInvariants(self, manager)

    def testCleanupBudgetIsGlobalFifoAndHandlesBoundaries(self):
        """Limit one invocation across all batches, resuming the FIFO head."""
        for backlog, budget in ((1, 64), (63, 64), (64, 64), (65, 64), (130, 64)):
            with self.subTest(backlog=backlog, budget=budget):
                manager = self.makeManager(maximumEntries=200)
                manager.RetiredCleanupBudget = budget
                for index in range(backlog):
                    manager.append(str(index), CORE_LOG_CATEGORY)
                    if index in (1, 4):
                        manager.clear(runtimeOnly=True)
                manager.clear(runtimeOnly=True)
                before = manager.retiredEntryCount
                identifiers = tuple(
                    getattr(batch, 'identifier', None)
                    for batch in manager._retiredBatches
                )
                with manager._lock:
                    released = manager._cleanupRetiredLocked()
                self.assertEqual(released, min(budget, before))
                self.assertEqual(manager.retiredEntryCount, before - released)
                if manager._retiredBatches and identifiers:
                    self.assertIn(
                        getattr(manager._retiredBatches[0], 'identifier', None),
                        identifiers,
                    )
                _assertManagerInvariants(self, manager)

        manager = self.makeManager()
        manager.append('retired', CORE_LOG_CATEGORY)
        manager.clear(runtimeOnly=True)
        with manager._lock:
            self.assertEqual(manager._cleanupRetiredLocked(0), 0)
        manager.RetiredCleanupBudget = 0
        with manager._lock:
            self.assertEqual(manager._cleanupRetiredLocked(), 1)

    def testRetiredGenerationCleanupIsStrictlyFifo(self):
        """Finish each older clear-all stream before touching the next one."""
        manager = self.makeManager(autoClearEnabled=False)
        manager.RetiredCleanupBudget = 1
        manager.append('application 1', APPLICATION_LOG_CATEGORY)
        manager.append('application 2', APPLICATION_LOG_CATEGORY)
        manager.append('runtime 1', CORE_LOG_CATEGORY)
        manager.append('runtime 2', CORE_LOG_CATEGORY)
        manager.append('other 1', 'other.extra')
        manager.append('other 2', 'other.extra')
        expectedIdentifiers = tuple(
            generation.identifier for generation in manager._activeGenerationsLocked()
        )
        manager.clear()
        self.assertEqual(
            tuple(batch.identifier for batch in manager._retiredBatches),
            expectedIdentifiers,
        )
        observedHeads = []
        while manager.retiredEntryCount:
            observedHeads.append(manager._retiredBatches[0].identifier)
            with manager._lock:
                self.assertEqual(manager._cleanupRetiredLocked(), 1)
        self.assertEqual(
            observedHeads,
            [
                expectedIdentifiers[0],
                expectedIdentifiers[0],
                expectedIdentifiers[1],
                expectedIdentifiers[1],
                expectedIdentifiers[2],
                expectedIdentifiers[2],
            ],
        )

    def testWeakReferencesSnapshotsAndExternalOwners(self):
        """Separate manager ownership from snapshot and caller ownership."""
        for size in (1, 63, 64, 65, 1_000, 10_000):
            with self.subTest(size=size):
                manager = self.makeManager(
                    maximumEntries=size + 2,
                    maximumCharacters=(size + 2) * 16,
                    maximumEntryCharacters=16,
                    autoClearEnabled=False,
                )
                manager.RetiredCleanupBudget = 64
                for index in range(size):
                    manager.append(f'entry {index}', CORE_LOG_CATEGORY)
                historical = manager.entries(CORE_LOG_CATEGORY)
                self.assertEqual(len(historical), size)
                references = tuple(weakref.ref(entry) for entry in historical)
                externallyOwned = historical[-1]
                manager.clear(runtimeOnly=True)
                self.assertTrue(
                    all(reference() is not None for reference in references)
                )
                while manager.retiredEntryCount:
                    with manager._lock:
                        manager._cleanupRetiredLocked()
                self.assertTrue(
                    all(reference() is not None for reference in references)
                )
                del historical
                gc.collect()
                self.assertTrue(
                    all(reference() is None for reference in references[:-1])
                )
                self.assertIs(references[-1](), externallyOwned)
                del externallyOwned
                gc.collect()
                self.assertIsNone(references[-1]())

    def testRetentionThreeWayMergeAndLargeSequences(self):
        """Evict only the global oldest live head across all active streams."""
        manager = self.makeManager(
            maximumEntries=5,
            maximumCharacters=19,
            maximumEntryCharacters=10,
            autoClearEnabled=False,
        )
        manager._sequence = 10**40
        categories = (
            APPLICATION_LOG_CATEGORY,
            CORE_LOG_CATEGORY,
            'other.extra',
            APPLICATION_LOG_CATEGORY,
            'runtime.extra',
            'other.extra',
            CORE_LOG_CATEGORY,
        )
        expected = []
        for index, categoryId in enumerate(categories):
            entry = manager.append(str(index) * (index % 4 + 1), categoryId)
            expected.append(entry)
            while (
                len(expected) > manager.maximumEntries
                or sum(len(item.message) for item in expected)
                > manager.maximumCharacters
            ):
                del expected[0]
            self.assertEqual(manager.entries(), tuple(expected))
            _assertManagerInvariants(self, manager)
        self.assertTrue(all(entry.sequence > 10**40 for entry in manager.entries()))

    def testSelectiveClearAndRegistrationStress(self):
        """Keep shared stream indexes exact for tiny and dominant categories."""
        manager = self.makeManager(
            maximumEntries=5_000,
            maximumCharacters=100_000,
            autoClearEnabled=False,
        )
        categoryIds = []
        for index in range(100):
            category = manager.registerCategory(
                LogCategory(
                    f'dynamic.{index}',
                    f'Dynamic {index}',
                    runtime=bool(index % 2),
                    translatable=bool(index % 3),
                )
            )
            categoryIds.append(category.id)
        for index in range(2_000):
            manager.append(str(index), categoryIds[index % len(categoryIds)])
        for categoryId in (categoryIds[0], categoryIds[-1], categoryIds[51]):
            expected = tuple(
                entry for entry in manager.entries() if entry.categoryId != categoryId
            )
            manager.clear(categoryId)
            self.assertEqual(manager.entries(), expected)
            _assertManagerInvariants(self, manager)
        duplicate = manager.category(categoryIds[1])
        self.assertIs(manager.registerCategory(duplicate), duplicate)
        with self.assertRaises(ValueError):
            manager.registerCategory(LogCategory(categoryIds[1], 'Different'))

    def testPathologicalMessagesAndRejectedOperationsAreAtomic(self):
        """Account normalized storage and preserve state after bad input."""
        manager = self.makeManager(maximumEntryCharacters=32)
        messages = ('', 'x', 'line\r\n', '😀é', 'a\0b', 'n\n' * 20, 'z' * 33)
        for message in messages:
            entry = manager.append(message)
            self.assertLessEqual(len(entry.message), 32)
            _assertManagerInvariants(self, manager)

        class RaisingString:
            def __str__(self):
                raise RuntimeError('conversion failed')

        before = manager.entries()
        with self.assertRaises(RuntimeError):
            manager.append(RaisingString())
        with self.assertRaises(TypeError):
            manager.append('bad timestamp', timestamp='not a datetime')
        with self.assertRaises(KeyError):
            manager.append('unknown', 'missing')
        with self.assertRaises(ValueError):
            manager.clear(CORE_LOG_CATEGORY, runtimeOnly=True)
        self.assertEqual(manager.entries(), before)
        _assertManagerInvariants(self, manager)

    def testSignalsAreOutsideLockReentrantAndCoalesced(self):
        """Allow querying/clearing slots without deadlock or stale UI truth."""
        manager = self.makeManager(autoClearEnabled=False)
        added = []
        cleared = []
        changed = []
        lockWasFreeDuringSignal = []

        def onAdded(entry):
            added.append(entry.sequence)
            manager.snapshot()
            manager.entryCount()
            if not lockWasFreeDuringSignal:
                completed = threading.Event()

                def queryFromAnotherThread():
                    manager.entryCount()
                    completed.set()

                worker = threading.Thread(target=queryFromAnotherThread)
                worker.start()
                lockWasFreeDuringSignal.append(completed.wait(2))
                worker.join(2)
            if entry.categoryId == CORE_LOG_CATEGORY:
                manager.clear(runtimeOnly=True)

        manager.entryAdded.connect(onAdded)
        manager.entriesCleared.connect(cleared.append)
        manager.entriesChanged.connect(changed.append)
        manager.append('core', CORE_LOG_CATEGORY)
        for index in range(20):
            manager.append(f'application {index}')
        processQtEvents()
        self.assertEqual(len(added), 21)
        self.assertEqual(cleared, [manager._runtimeCategoryIds])
        self.assertEqual(changed, [21])
        self.assertEqual(lockWasFreeDuringSignal, [True])
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 0)
        _assertManagerInvariants(self, manager)

    def testAppendAndClearCannotSplitOneAtomicMutation(self):
        """Force clear to wait while append has selected its generation."""
        manager = self.makeManager(autoClearEnabled=False)
        selected = threading.Event()
        release = threading.Event()
        appendThreadId = []
        original = manager._generationForCategoryLocked

        def observedGeneration(category):
            generation = original(category)
            if threading.get_ident() in appendThreadId and not selected.is_set():
                selected.set()
                self.assertTrue(release.wait(5))
            return generation

        manager._generationForCategoryLocked = observedGeneration
        errors = []

        def append():
            appendThreadId.append(threading.get_ident())
            try:
                manager.append('racing', CORE_LOG_CATEGORY)
            except Exception as error:
                errors.append(error)

        producer = threading.Thread(target=append)
        clearer = threading.Thread(target=lambda: manager.clear(runtimeOnly=True))
        producer.start()
        self.assertTrue(selected.wait(5))
        clearer.start()
        time.sleep(0.01)
        self.assertTrue(clearer.is_alive())
        release.set()
        producer.join(5)
        clearer.join(5)
        self.assertFalse(producer.is_alive())
        self.assertFalse(clearer.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(manager.entries(CORE_LOG_CATEGORY), tuple())
        _assertManagerInvariants(self, manager)

    def testConcurrentReadersWritersAndMutatorsFinishConsistently(self):
        """Stress every supported locked operation with deterministic seeds."""
        for producerCount in (1, 2, 4, 8, 16):
            with self.subTest(producers=producerCount):
                manager = self.makeManager(
                    maximumEntries=500,
                    maximumCharacters=20_000,
                    autoClearMaximumEntries=17,
                )
                errors = []
                returnedSequences = []
                sequenceLock = threading.Lock()
                # Producers plus the reader and mutator are the complete
                # participant set.  Keeping the exact cardinality here makes a
                # failed synchronization a real deadlock signal rather than a
                # test harness waiting for a thread that was never created.
                start = threading.Barrier(producerCount + 2)

                def producer(workerIndex):
                    randomizer = random.Random(10_000 + workerIndex)
                    try:
                        start.wait(5)
                        for index in range(300):
                            categoryId = randomizer.choice(
                                (
                                    APPLICATION_LOG_CATEGORY,
                                    CORE_LOG_CATEGORY,
                                    TUN2SOCKS_LOG_CATEGORY,
                                    'runtime.extra',
                                    'other.extra',
                                )
                            )
                            entry = manager.append(f'{workerIndex}:{index}', categoryId)
                            with sequenceLock:
                                returnedSequences.append(entry.sequence)
                    except Exception as error:
                        errors.append(error)

                def reader():
                    try:
                        start.wait(5)
                        for _index in range(500):
                            entries = manager.entries()
                            self.assertEqual(
                                tuple(item.sequence for item in entries),
                                tuple(sorted(item.sequence for item in entries)),
                            )
                            manager.entryCount(CORE_LOG_CATEGORY)
                    except Exception as error:
                        errors.append(error)

                def mutator():
                    randomizer = random.Random(77)
                    try:
                        start.wait(5)
                        for index in range(180):
                            choice = randomizer.randrange(4)
                            if choice == 0:
                                manager.clear(runtimeOnly=True)
                            elif choice == 1:
                                manager.clear('other.extra')
                            elif choice == 2:
                                manager.setAutoClearEnabled(bool(index % 2))
                            else:
                                manager.snapshot(CORE_LOG_CATEGORY)
                    except Exception as error:
                        errors.append(error)

                threads = [
                    threading.Thread(target=producer, args=(index,))
                    for index in range(producerCount)
                ]
                threads.extend(
                    (threading.Thread(target=reader), threading.Thread(target=mutator))
                )
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(20)
                    self.assertFalse(thread.is_alive(), 'possible LogManager deadlock')
                self.assertEqual(errors, [])
                self.assertEqual(len(returnedSequences), producerCount * 300)
                self.assertEqual(len(set(returnedSequences)), len(returnedSequences))
                _assertManagerInvariants(self, manager)

    def testLogPageMatchesTruthAcrossPruneRolloverAndFilters(self):
        """Keep the incremental document exact through generation mutations."""
        with isolatedSettings():
            manager = self.makeManager(
                maximumEntries=120,
                maximumCharacters=10_000,
                autoClearMaximumEntries=40,
            )
            page = LogPage(manager=manager)
            page.resize(900, 420)
            page.show()
            for index in range(400):
                categoryId = (
                    APPLICATION_LOG_CATEGORY if index % 7 == 0 else CORE_LOG_CATEGORY
                )
                manager.append(f'line {index:04d}', categoryId)
            self.assertTrue(waitFor(lambda: not page._entriesDirty))
            self.assertEqual(
                page.plainText().splitlines(),
                [entry.message for entry in manager.entries()],
            )
            for categoryId in (CORE_LOG_CATEGORY, APPLICATION_LOG_CATEGORY, 'all'):
                page.filterComboBox.setCurrentIndex(
                    page.filterComboBox.findData(categoryId)
                )
                self.assertTrue(waitFor(lambda: not page._entriesDirty))
                self.assertEqual(
                    page.plainText().splitlines(),
                    [entry.message for entry in manager.entries(categoryId)],
                )
            manager.clear(runtimeOnly=True)
            page.filterComboBox.setCurrentIndex(page.filterComboBox.findData('all'))
            self.assertTrue(waitFor(lambda: not page._entriesDirty))
            self.assertEqual(
                page.plainText().splitlines(),
                [entry.message for entry in manager.entries()],
            )
            page.close()
            page.deleteLater()
            collectAtBoundary()


@unittest.skipUnless(
    veryHeavyEnabled(),
    'set FURIOUS_VERY_HEAVY_TESTS=1 for generation stress/benchmarks',
)
class VeryHeavyGenerationLogManagerTest(unittest.TestCase):
    """Run release-confidence scaling, latency, backlog, and soak probes."""

    @classmethod
    def setUpClass(cls):
        application()

    def report(self, name, **values):
        print(
            'GENERATION_CAMPAIGN_REPORT='
            + json.dumps({'name': name, **values}, sort_keys=True),
            flush=True,
        )

    def testScalingAndStructuralComplexity(self):
        """Measure geometric scaling while structural assertions guard O(1)."""
        results = []
        for size in (100, 1_000, 10_000, 100_000):
            manager = LogManager(
                maximumEntries=size + 10,
                maximumCharacters=(size + 10) * 16,
                maximumEntryCharacters=16,
                autoClearMaximumEntries=size,
            )
            for index in range(size):
                manager.append(str(index), CORE_LOG_CATEGORY)
            samples = []
            synchronousTraversals = 0
            synchronousRemovals = 0
            for repetition in range(7):
                if repetition:
                    for index in range(size):
                        manager.append(str(index), CORE_LOG_CATEGORY)
                watched = _ObservedEntries(manager._runtimeGeneration.entries)
                manager._runtimeGeneration.entries = watched
                started = time.perf_counter_ns()
                manager.clear(runtimeOnly=True)
                samples.append(time.perf_counter_ns() - started)
                synchronousTraversals += watched.iterations
                synchronousRemovals += watched.oldestRemovals
                self.assertEqual(watched.iterations, 0)
                self.assertEqual(watched.oldestRemovals, 0)
            results.append(
                {
                    'n': size,
                    'runtime_clear_us': median(samples) / 1_000,
                    'synchronous_traversals': synchronousTraversals,
                    'synchronous_removals': synchronousRemovals,
                }
            )
        ratio = results[-1]['runtime_clear_us'] / max(
            results[0]['runtime_clear_us'], 0.001
        )
        self.assertLess(ratio, 100)
        self.report('scaling', samples=results, endpoint_ratio=ratio)

    def testOperationScalingMatrix(self):
        """Report medians for every claimed constant, linear, or bounded path."""

        def elapsed(operation):
            started = time.perf_counter_ns()
            operation()
            return time.perf_counter_ns() - started

        matrix = []
        for size in (100, 1_000, 10_000):
            samples = {
                name: []
                for name in (
                    'normal_append',
                    'core_rollover',
                    'runtime_clear',
                    'clear_all',
                    'sole_category_clear',
                    'shared_category_clear',
                    'cleanup_64',
                    'category_snapshot',
                    'global_snapshot',
                    'oldest_eviction',
                )
            }
            for _repetition in range(5):
                manager = LogManager(
                    maximumEntries=size * 2 + 10,
                    autoClearMaximumEntries=size,
                )
                for index in range(size):
                    manager.append(str(index), CORE_LOG_CATEGORY)
                samples['normal_append'].append(
                    elapsed(lambda: manager.append('ordinary'))
                )
                samples['core_rollover'].append(
                    elapsed(lambda: manager.append('trigger', CORE_LOG_CATEGORY))
                )

                manager = LogManager(maximumEntries=size + 10, autoClearEnabled=False)
                for index in range(size):
                    manager.append(str(index), CORE_LOG_CATEGORY)
                samples['category_snapshot'].append(
                    elapsed(lambda: manager.snapshot(CORE_LOG_CATEGORY))
                )
                samples['runtime_clear'].append(
                    elapsed(lambda: manager.clear(runtimeOnly=True))
                )
                with manager._lock:
                    samples['cleanup_64'].append(
                        elapsed(lambda: manager._cleanupRetiredLocked())
                    )

                manager = LogManager(maximumEntries=size + 10, autoClearEnabled=False)
                for index in range(size):
                    manager.append(str(index), APPLICATION_LOG_CATEGORY)
                samples['sole_category_clear'].append(
                    elapsed(lambda: manager.clear(APPLICATION_LOG_CATEGORY))
                )

                manager = LogManager(
                    maximumEntries=size * 2 + 10,
                    autoClearEnabled=False,
                )
                for index in range(size):
                    manager.append(str(index), CORE_LOG_CATEGORY)
                manager.append('shared', TUN2SOCKS_LOG_CATEGORY)
                samples['shared_category_clear'].append(
                    elapsed(lambda: manager.clear(CORE_LOG_CATEGORY))
                )

                manager = LogManager(maximumEntries=size + 10, autoClearEnabled=False)
                for index in range(size):
                    manager.append(
                        str(index),
                        (
                            APPLICATION_LOG_CATEGORY,
                            CORE_LOG_CATEGORY,
                            TUN2SOCKS_LOG_CATEGORY,
                        )[index % 3],
                    )
                samples['global_snapshot'].append(elapsed(lambda: manager.snapshot()))
                samples['clear_all'].append(elapsed(lambda: manager.clear()))

                manager = LogManager(maximumEntries=size, autoClearEnabled=False)
                for index in range(size):
                    manager.append(
                        str(index),
                        (
                            APPLICATION_LOG_CATEGORY,
                            CORE_LOG_CATEGORY,
                            TUN2SOCKS_LOG_CATEGORY,
                        )[index % 3],
                    )
                samples['oldest_eviction'].append(
                    elapsed(lambda: manager.append('evict'))
                )

            matrix.append(
                {
                    'n': size,
                    **{
                        name + '_us': median(values) / 1_000
                        for name, values in samples.items()
                    },
                }
            )

        ratios = {
            name: matrix[-1][name] / max(matrix[0][name], 0.001)
            for name in matrix[0]
            if name != 'n'
        }
        for name in (
            'normal_append_us',
            'core_rollover_us',
            'runtime_clear_us',
            'clear_all_us',
            'sole_category_clear_us',
            'cleanup_64_us',
            'oldest_eviction_us',
        ):
            self.assertLess(ratios[name], 50)
        self.report('operation-scaling-matrix', samples=matrix, ratios=ratios)

    def testAppendLatencyWithRolloverRetentionAndBacklog(self):
        """Report latency distribution by append-path condition."""
        manager = LogManager(
            maximumEntries=5_000,
            maximumCharacters=200_000,
            maximumEntryCharacters=128,
            autoClearMaximumEntries=100,
        )
        manager.RetiredCleanupBudget = 64
        ordinary = []
        rollover = []
        retention = []
        maximumRetired = 0
        maximumBatches = 0
        for index in range(50_000):
            categoryId = CORE_LOG_CATEGORY if index % 3 else APPLICATION_LOG_CATEGORY
            triggersRollover = (
                categoryId == CORE_LOG_CATEGORY
                and manager.entryCount(CORE_LOG_CATEGORY)
                >= manager.autoClearMaximumEntries
            )
            atRetention = manager.entryCount() >= manager.maximumEntries
            message = f'{index:06d}-' + 'x' * (index % 97)
            causesRetention = (
                manager.entryCount() + 1 > manager.maximumEntries
                or manager.retainedCharacters + len(message) > manager.maximumCharacters
            )
            started = time.perf_counter_ns()
            manager.append(message, categoryId)
            elapsed = time.perf_counter_ns() - started
            if triggersRollover:
                rollover.append(elapsed)
            elif atRetention or causesRetention:
                retention.append(elapsed)
            else:
                ordinary.append(elapsed)
            maximumRetired = max(maximumRetired, manager.retiredEntryCount)
            maximumBatches = max(maximumBatches, len(manager._retiredBatches))

        def distribution(samples):
            return {
                'count': len(samples),
                'median_us': median(samples) / 1_000,
                'p95_us': _percentile(samples, 0.95),
                'p99_us': _percentile(samples, 0.99),
                'p999_us': _percentile(samples, 0.999),
                'max_us': max(samples) / 1_000,
            }

        self.assertTrue(ordinary)
        self.assertTrue(rollover)
        self.assertLessEqual(maximumRetired, manager.maximumEntries)
        _assertManagerInvariants(self, manager)
        self.report(
            'append-latency',
            ordinary=distribution(ordinary),
            rollover=distribution(rollover),
            retention=distribution(retention) if retention else None,
            maximum_retired=maximumRetired,
            maximum_retired_batches=maximumBatches,
        )

    def testCleanupLatencyDoesNotScaleWithBacklog(self):
        """Keep append cleanup capped at 64 for geometrically larger queues."""
        results = []
        for backlog in (64, 1_000, 10_000):
            samples = []
            for _repetition in range(9):
                manager = LogManager(
                    maximumEntries=backlog + 10,
                    maximumCharacters=(backlog + 10) * 8,
                    maximumEntryCharacters=8,
                    autoClearEnabled=False,
                )
                manager.RetiredCleanupBudget = 64
                for index in range(backlog):
                    manager.append(str(index), CORE_LOG_CATEGORY)
                manager.clear(runtimeOnly=True)
                before = manager.retiredEntryCount
                started = time.perf_counter_ns()
                manager.append('new')
                samples.append(time.perf_counter_ns() - started)
                self.assertEqual(manager.retiredEntryCount, max(0, before - 64))
            results.append({'backlog': backlog, 'median_us': median(samples) / 1_000})
        ratio = results[-1]['median_us'] / max(results[0]['median_us'], 0.001)
        self.assertLess(ratio, 20)
        self.report('cleanup-backlog-latency', samples=results, endpoint_ratio=ratio)

    def testAdversarialClearRateCannotGrowPhysicalBacklog(self):
        """Retire generations as fast as the minimum cleanup rate permits."""
        capacity = 2_000
        manager = LogManager(maximumEntries=capacity, autoClearEnabled=False)
        manager.RetiredCleanupBudget = 1
        maximumRetired = 0
        maximumPhysical = 0
        maximumBatches = 0
        for cycle in range(100):
            for index in range(capacity):
                manager.append(f'{cycle}:{index}', CORE_LOG_CATEGORY)
                maximumRetired = max(maximumRetired, manager.retiredEntryCount)
                maximumPhysical = max(
                    maximumPhysical,
                    manager.entryCount() + manager.retiredEntryCount,
                )
            manager.clear(runtimeOnly=True)
            maximumRetired = max(maximumRetired, manager.retiredEntryCount)
            maximumPhysical = max(
                maximumPhysical,
                manager.entryCount() + manager.retiredEntryCount,
            )
            maximumBatches = max(maximumBatches, len(manager._retiredBatches))
            self.assertLessEqual(maximumPhysical, capacity)
        while manager.retiredEntryCount:
            with manager._lock:
                manager._cleanupRetiredLocked()
        self.assertEqual(manager.retiredCharacters, 0)
        self.assertEqual(len(manager._retiredBatches), 0)
        self.report(
            'adversarial-backlog',
            operations=capacity * 100,
            cleanup_budget=1,
            maximum_retired=maximumRetired,
            maximum_physical_entries=maximumPhysical,
            maximum_retired_batches=maximumBatches,
            final_retired=manager.retiredEntryCount,
        )

    def testLongRunningModelSoakTracksMemoryAndBacklog(self):
        """Sustain mixed operations while checking invariants and RSS plateaus."""
        seed = 0xF017105
        randomizer = random.Random(seed)
        manager = LogManager(
            maximumEntries=2_000,
            maximumCharacters=200_000,
            maximumEntryCharacters=256,
            autoClearMaximumEntries=400,
        )
        manager.RetiredCleanupBudget = 64
        manager.registerComponent('soak.runtime', 'Soak runtime', runtime=True)
        manager.registerComponent('soak.other', 'Soak other', runtime=False)
        categories = (
            APPLICATION_LOG_CATEGORY,
            CORE_LOG_CATEGORY,
            TUN2SOCKS_LOG_CATEGORY,
            'soak.runtime',
            'soak.other',
        )
        rssSamples = []
        maximumRetired = 0
        maximumRetiredCharacters = 0
        maximumBatches = 0
        maximumLive = 0
        maximumPhysical = 0
        started = time.perf_counter()
        for index in range(250_000):
            operation = randomizer.randrange(100)
            if operation < 70:
                manager.append(
                    f'{index}:{randomizer.randrange(10**9)}',
                    randomizer.choice(categories),
                )
            elif operation < 80:
                manager.snapshot(randomizer.choice((None, *categories)))
            elif operation < 85:
                manager.clear(randomizer.choice(categories))
            elif operation < 90:
                manager.clear(runtimeOnly=True)
            elif operation < 95:
                manager.setAutoClearEnabled(bool(randomizer.getrandbits(1)))
            else:
                manager.entryCount(randomizer.choice((None, *categories)))

            maximumRetired = max(maximumRetired, manager.retiredEntryCount)
            maximumRetiredCharacters = max(
                maximumRetiredCharacters, manager.retiredCharacters
            )
            maximumBatches = max(maximumBatches, len(manager._retiredBatches))
            maximumLive = max(maximumLive, manager.entryCount())
            maximumPhysical = max(
                maximumPhysical,
                manager.entryCount() + manager.retiredEntryCount,
            )
            if (index + 1) % 10_000 == 0:
                _assertManagerInvariants(self, manager)
                rssSamples.append(resourceSnapshot()['rss'])

        while manager.retiredEntryCount:
            with manager._lock:
                manager._cleanupRetiredLocked()
        _assertManagerInvariants(self, manager)
        self.assertLessEqual(maximumRetired, manager.maximumEntries)
        rssValues = [value for value in rssSamples if value is not None]
        rssGrowth = rssValues[-1] - rssValues[0] if len(rssValues) > 1 else None
        self.report(
            'soak',
            seed=seed,
            operations=250_000,
            duration_seconds=time.perf_counter() - started,
            maximum_live=maximumLive,
            maximum_retired=maximumRetired,
            maximum_retired_characters=maximumRetiredCharacters,
            maximum_physical_entries=maximumPhysical,
            maximum_retired_batches=maximumBatches,
            final_retired=manager.retiredEntryCount,
            rss_samples=rssSamples,
            rss_growth=rssGrowth,
        )

    def testHundredThousandEntryMergeAndClearAll(self):
        """Validate a large interleaved merge and constant-work clear-all."""
        count = 100_000
        manager = LogManager(
            maximumEntries=count,
            maximumCharacters=count * 8,
            maximumEntryCharacters=8,
            autoClearEnabled=False,
        )
        categories = (
            APPLICATION_LOG_CATEGORY,
            CORE_LOG_CATEGORY,
            TUN2SOCKS_LOG_CATEGORY,
        )
        for index in range(count):
            manager.append(str(index), categories[index % 3])
        started = time.perf_counter_ns()
        entries = manager.entries()
        snapshotUs = (time.perf_counter_ns() - started) / 1_000
        self.assertEqual(
            tuple(entry.sequence for entry in entries), tuple(range(1, count + 1))
        )
        watched = []
        for generation in manager._activeGenerationsLocked():
            index = _ObservedEntries(generation.entries)
            generation.entries = index
            watched.append(index)
        started = time.perf_counter_ns()
        manager.clear()
        clearUs = (time.perf_counter_ns() - started) / 1_000
        self.assertEqual(sum(index.iterations for index in watched), 0)
        self.assertEqual(manager.entries(), tuple())
        self.assertEqual(manager.retiredEntryCount, count)
        self.report(
            'large-merge-clear',
            entries=count,
            snapshot_us=snapshotUs,
            clear_all_us=clearUs,
            synchronous_traversals=0,
        )

    @unittest.skipUnless(
        os.environ.get('FURIOUS_LOG_MANAGER_BASELINE'),
        'set FURIOUS_LOG_MANAGER_BASELINE to a Git revision for comparison',
    )
    def testIdenticalWorkloadAgainstPreviousImplementation(self):
        """Compare the same steady, rollover, snapshot, and retention workloads."""
        revision = os.environ['FURIOUS_LOG_MANAGER_BASELINE']
        source = subprocess.run(
            ['git', 'show', f'{revision}:Furious/Service/LogManager.py'],
            cwd=os.getcwd(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        baselineModule = types.ModuleType('tests._baseline_log_manager')
        exec(
            compile(source, f'<LogManager:{revision}>', 'exec'), baselineModule.__dict__
        )

        def benchmark(managerClass):
            results = {}
            manager = managerClass(maximumEntries=50_000, autoClearEnabled=False)
            started = time.perf_counter_ns()
            for index in range(50_000):
                manager.append(str(index), APPLICATION_LOG_CATEGORY)
            results['steady_append_ms'] = (time.perf_counter_ns() - started) / 1e6

            manager = managerClass(
                maximumEntries=50_000,
                autoClearMaximumEntries=20_000,
            )
            for index in range(20_000):
                manager.append(str(index), CORE_LOG_CATEGORY)
            for index in range(20_000):
                manager.append(str(index), TUN2SOCKS_LOG_CATEGORY)
            started = time.perf_counter_ns()
            manager.append('trigger', CORE_LOG_CATEGORY)
            results['core_rollover_us'] = (time.perf_counter_ns() - started) / 1e3

            manager = managerClass(maximumEntries=50_000, autoClearEnabled=False)
            for index in range(30_000):
                manager.append(
                    str(index),
                    CORE_LOG_CATEGORY if index % 5 == 0 else APPLICATION_LOG_CATEGORY,
                )
            started = time.perf_counter_ns()
            manager.snapshot(CORE_LOG_CATEGORY)
            results['category_snapshot_us'] = (time.perf_counter_ns() - started) / 1e3
            started = time.perf_counter_ns()
            manager.snapshot()
            results['global_snapshot_us'] = (time.perf_counter_ns() - started) / 1e3

            manager = managerClass(maximumEntries=1_000, autoClearEnabled=False)
            started = time.perf_counter_ns()
            for index in range(50_000):
                manager.append(str(index), APPLICATION_LOG_CATEGORY)
            results['retention_heavy_ms'] = (time.perf_counter_ns() - started) / 1e6
            return results

        current = benchmark(LogManager)
        baseline = benchmark(baselineModule.LogManager)
        self.assertEqual(LogManager(maximumEntries=1).entries(), tuple())
        self.report(
            'baseline-comparison',
            baseline_revision=revision,
            current=current,
            baseline=baseline,
            ratios={key: current[key] / max(baseline[key], 0.001) for key in current},
        )


if __name__ == '__main__':
    unittest.main()
