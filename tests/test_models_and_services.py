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

"""Exercise models, persistence, logging, metrics, and settings migration."""

from __future__ import annotations

from Furious.Controllers.SettingsController import (
    APPLICATION_THEME_SETTING,
    SettingsController,
)
from Furious.Frozenlib import (
    AppBinarySettings,
    AppBuiltinProxyMode,
    AppSettings,
    ApplicationTheme,
)
from Furious.Models import (
    CoreConfiguration,
    ProfileMetadata,
    ServerProfile,
    profileConnectionFingerprint,
)
from Furious.Repository.Servers import UserServer, UserServers
from Furious.Repository.Subscriptions import SubscriptionGroup, UserSubs
from Furious.Service.LogManager import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)
from Furious.Service.MetricsHistory import (
    DOWNLOAD_SPEED_METRIC,
    DOWNLOAD_USAGE_METRIC,
    MetricsHistory,
)

from PySide6 import QtCore

from collections import OrderedDict
import threading
import unittest
import weakref
from unittest import mock

from tests.support import application, isolatedSettings, processQtEvents


class _ObservedEntryIndex(OrderedDict):
    """Record global-index traversal and removal requested by one operation."""

    def __init__(self, entries=()):
        """Copy existing entries before beginning operation instrumentation."""
        self.iterationRequests = 0
        self.deletedKeys = []
        self.oldestRemovals = 0

        super().__init__(entries)

    def __iter__(self):
        """Count direct traversal of the global chronological index."""
        self.iterationRequests += 1

        return super().__iter__()

    def items(self):
        """Count item traversal of the global chronological index."""
        self.iterationRequests += 1

        return super().items()

    def keys(self):
        """Count key traversal of the global chronological index."""
        self.iterationRequests += 1

        return super().keys()

    def values(self):
        """Count value traversal of the global chronological index."""
        self.iterationRequests += 1

        return super().values()

    def __delitem__(self, key):
        """Record direct sequence-key deletion during category clearing."""
        self.deletedKeys.append(key)

        return super().__delitem__(key)

    def popitem(self, last=True):
        """Record global oldest-entry eviction without counting it as a scan."""
        if not last:
            self.oldestRemovals += 1

        return super().popitem(last=last)


class ProfileModelTest(unittest.TestCase):
    """Verify metadata separation, compatibility, and copy semantics."""

    def testCoreConfigurationRejectsNonObjectJSONWithoutRaising(self):
        """Treat valid non-object JSON roots as invalid connection documents."""
        for value in ('[]', 'null', '42', '"text"'):
            with self.subTest(value=value):
                configuration = CoreConfiguration(value)

                self.assertEqual(configuration, {})
                self.assertTrue(configuration.constructionError())

        configuration = CoreConfiguration({1: 'value'})

        self.assertEqual(configuration, {})
        self.assertEqual(
            configuration.constructionError(),
            'configuration keys must be strings',
        )

    def testCoreConfigurationReportsSerializationFailure(self):
        """Keep the empty sentinel while exposing a useful diagnostic."""
        configuration = CoreConfiguration({'unsupported': object()})

        self.assertEqual(configuration.toJSONString(), '')
        self.assertTrue(configuration.serializationError())

        configuration['unsupported'] = 'supported'

        self.assertTrue(configuration.toJSONString())
        self.assertEqual(configuration.serializationError(), '')

    def testLegacyMetadataPreservesUnknownFields(self):
        """Promote known legacy fields while retaining forward-only metadata."""
        metadata = ProfileMetadata.fromMapping(
            {
                'remark': 'Legacy name',
                'subsId': 'subscription-id',
                'delayResult': '42 ms',
                'speedResult': '8 MiB/s',
                'tags': 'work, ipv6',
                'favorite': 'true',
                'futureMetadata': {'value': 7},
            }
        )

        self.assertEqual(metadata.displayName, 'Legacy name')
        self.assertEqual(metadata.subscriptionSource, 'subscription-id')
        self.assertTrue(metadata.subscriptionManaged)
        self.assertEqual(metadata.latency, '42 ms')
        self.assertEqual(metadata.speed, '8 MiB/s')
        self.assertEqual(metadata.tags, ('work', 'ipv6'))
        self.assertTrue(metadata.favorite)
        self.assertEqual(metadata.extras['futureMetadata'], {'value': 7})
        self.assertEqual(
            ProfileMetadata.fromMapping(metadata.toMapping()).toMapping(),
            metadata.toMapping(),
        )

    def testMetadataPromotesKnownExtrasWithoutCollisions(self):
        """Migrate newly recognized fields out of nested forward metadata."""
        metadata = ProfileMetadata.fromMapping(
            {
                'remark': 'Explicit legacy name',
                'subsId': 'subscription-id',
                'extras': {
                    'displayName': 'Previously unknown name',
                    'favorite': True,
                    'subscriptionManaged': True,
                    'subscriptionProfileKey': 'stale:key',
                    'futureMetadata': 7,
                },
            }
        )

        self.assertEqual(metadata.displayName, 'Explicit legacy name')
        self.assertTrue(metadata.favorite)
        self.assertEqual(metadata.subscriptionSource, 'subscription-id')
        self.assertTrue(metadata.subscriptionManaged)
        self.assertEqual(metadata.subscriptionProfileKey, 'stale:key')
        self.assertEqual(metadata.extras, {'futureMetadata': 7})

    def testIndependentCopyGetsNewIdentityAndNoSubscriptionOwner(self):
        """Keep manual copies independent from subscription synchronization."""
        original = ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture', 'address': 'example.com'}),
            {
                'displayName': 'Managed',
                'subscriptionSource': 'source',
                'subscriptionManaged': True,
                'subscriptionProfileKey': 'upstream:1',
            },
        )
        copied = original.independentCopy()

        self.assertNotEqual(copied.metadata.profileId, original.metadata.profileId)
        self.assertEqual(copied.connection, original.connection)
        self.assertIsNot(copied.connection, original.connection)
        self.assertEqual(copied.metadata.subscriptionSource, '')
        self.assertFalse(copied.metadata.subscriptionManaged)
        self.assertEqual(copied.metadata.subscriptionProfileKey, '')

    def testProfileExportAndRemoteAddressRemainCoreNeutral(self):
        """Delegate generic profile behavior without protocol-specific options."""

        class Configuration(CoreConfiguration):
            @property
            def itemProtocol(self):
                return 'Shadowsocks'

            @property
            def itemAddress(self):
                return 'display.example'

            def remoteAddress(self):
                return 'routing.example'

            def toURI(self, remark=''):
                return f'fixture://{remark}'

        profile = ServerProfile.fromConfiguration(
            Configuration({'type': 'fixture'}),
            {'displayName': 'Profile'},
        )

        self.assertEqual(profile.toURI(), 'fixture://Profile')
        self.assertEqual(profile.itemAddress, 'display.example')
        self.assertEqual(profile.remoteAddress(), 'routing.example')

    def testConnectionFingerprintIsCanonicalAndRejectsUnsupportedValues(self):
        """Hash only canonical JSON connection semantics."""
        first = ServerProfile.fromConfiguration(
            CoreConfiguration({'address': 'example.com', 'port': 443}),
            {'displayName': 'First'},
        )
        second = ServerProfile.fromConfiguration(
            CoreConfiguration({'port': 443, 'address': 'example.com'}),
            {'displayName': 'Second'},
        )

        self.assertEqual(
            profileConnectionFingerprint(first),
            profileConnectionFingerprint(second),
        )

        with self.assertRaisesRegex(TypeError, 'JSON-compatible'):
            profileConnectionFingerprint(CoreConfiguration({'value': object()}))

    def testUserServerMappingRemainsBackwardCompatible(self):
        """Persist the canonical legacy record shape plus per-profile metadata."""
        profile = ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture', 'port': 1080}),
            {
                'displayName': 'Fixture',
                'group': 'Tests',
                'annotations': 'local only',
                'favorite': True,
                'futureField': 'preserved',
            },
        )
        mapping = UserServer.fromProfile(profile).toMapping()
        restored = UserServer.metadataFromMapping(mapping)

        self.assertEqual(set(('remark', 'config', 'subsId')) - set(mapping), set())
        self.assertEqual(restored.displayName, 'Fixture')
        self.assertEqual(restored.group, 'Tests')
        self.assertEqual(restored.annotations, 'local only')
        self.assertTrue(restored.favorite)
        self.assertEqual(restored.extras['futureField'], 'preserved')


class IsolatedRepositoryTest(unittest.TestCase):
    """Prove repositories round-trip exclusively through temporary QSettings."""

    def testServerRepositoryRoundTripUsesCanonicalModel(self):
        """Restore connection and metadata without touching production state."""
        with isolatedSettings() as settings:
            repository = UserServers()
            repository.data().append(
                ServerProfile.fromConfiguration(
                    CoreConfiguration({'type': 'fixture', 'value': 9}),
                    {
                        'displayName': 'Temporary profile',
                        'tags': ('one', 'two'),
                        'favorite': True,
                        'unknown': 'retained',
                    },
                )
            )
            repository.sync()

            self.assertTrue(settings.contains('Configuration'))

            restored = UserServers().data()

            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0].connection['value'], 9)
            self.assertEqual(restored[0].itemRemark, 'Temporary profile')
            self.assertEqual(restored[0].metadata.tags, ('one', 'two'))
            self.assertTrue(restored[0].metadata.favorite)
            self.assertEqual(restored[0].metadata.extras['unknown'], 'retained')

    def testSubscriptionRepositoryNormalizesAndOrdersLegacyGroups(self):
        """Keep future fields while migrating URL-era subscription records."""
        with isolatedSettings():
            repository = UserSubs()
            repository.upsertGroup(
                SubscriptionGroup.fromMapping(
                    'second',
                    {
                        'remark': 'Zulu',
                        'webURL': 'https://two.invalid',
                        'sortOrder': 2,
                        'futureField': 'two',
                    },
                )
            )
            repository.upsertGroup(
                SubscriptionGroup.fromMapping(
                    'first',
                    {
                        'remark': 'Alpha',
                        'webURL': 'https://one.invalid',
                        'sortOrder': 1,
                        'enabled': 'false',
                    },
                )
            )
            repository.sync()

            restored = UserSubs()
            groups = restored.groups()

            self.assertEqual(tuple(group.id for group in groups), ('first', 'second'))
            self.assertFalse(groups[0].enabled)
            self.assertEqual(groups[1].extras['futureField'], 'two')
            self.assertEqual(restored.removeGroup('first').remark, 'Alpha')
            self.assertIsNone(restored.group('first'))


class SettingsMigrationTest(unittest.TestCase):
    """Verify forward/backward-compatible application-theme persistence."""

    def testLegacyDarkModeMigratesWithoutRemovingLegacyValue(self):
        """Create the new preference while retaining the old binary key."""
        with isolatedSettings() as settings:
            settings.setValue('DarkMode', AppBinarySettings.ON_)

            SettingsController()

            self.assertEqual(
                AppSettings.get(APPLICATION_THEME_SETTING),
                ApplicationTheme.Dark.value,
            )
            self.assertEqual(settings.value('DarkMode'), AppBinarySettings.ON_)

    def testNewPreferenceSynchronizesLegacyReaders(self):
        """Keep older releases able to read forced dark and non-dark choices."""
        with isolatedSettings() as settings:
            SettingsController()

            SettingsController.setApplicationTheme(ApplicationTheme.Dark)

            self.assertEqual(settings.value('DarkMode'), AppBinarySettings.ON_)

            SettingsController.setApplicationTheme(ApplicationTheme.Light)

            self.assertEqual(settings.value('DarkMode'), AppBinarySettings.OFF)
            self.assertEqual(
                settings.value(APPLICATION_THEME_SETTING),
                ApplicationTheme.Light.value,
            )

    def testSharedNetworkPreferencesEmitOnlyRealChanges(self):
        """Synchronize multiple views without publishing duplicate mutations."""
        application()

        with (
            isolatedSettings(),
            mock.patch(
                'Furious.Controllers.SettingsController.PLATFORM',
                'Linux',
            ),
            mock.patch(
                'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
            ),
        ):
            AppSettings.turnOFF('VPNMode')
            AppSettings.set(
                'SystemProxyMode',
                AppBuiltinProxyMode.Auto.value,
            )
            controller = SettingsController()
            tunStates = []
            proxyModes = []

            controller.tunModeChanged.connect(tunStates.append)
            controller.systemProxyModeChanged.connect(proxyModes.append)

            controller.setTUNMode(True)
            controller.setTUNMode(True)
            controller.setSystemProxyMode(AppBuiltinProxyMode.NoChanges.value)
            controller.setSystemProxyMode(AppBuiltinProxyMode.NoChanges.value)

            self.assertEqual(tunStates, [True])
            self.assertEqual(
                proxyModes,
                [AppBuiltinProxyMode.NoChanges.value],
            )
            self.assertTrue(AppSettings.isStateON_('VPNMode'))
            self.assertEqual(
                AppSettings.get('SystemProxyMode'),
                AppBuiltinProxyMode.NoChanges.value,
            )


class LogManagerTest(unittest.TestCase):
    """Verify bounded, categorized, and thread-safe structured logging."""

    def _assertIndexesConsistent(self, manager):
        """Verify active/retired indexes and aggregate accounting agree."""
        with manager._lock:
            liveSequences = []
            liveCharacters = 0

            for generation in manager._activeGenerationsLocked():
                generationSequences = tuple(generation.entries)
                categorySequences = []
                categoryCharacters = 0

                self.assertEqual(
                    generationSequences,
                    tuple(sorted(generationSequences)),
                )

                for categoryId, categoryEntries in generation.entriesByCategory.items():
                    self.assertEqual(
                        categoryEntries.characterCount,
                        sum(
                            len(entry.message)
                            for entry in categoryEntries.entries.values()
                        ),
                    )

                    for sequence, entry in categoryEntries.entries.items():
                        self.assertEqual(entry.categoryId, categoryId)
                        self.assertIs(generation.entries[sequence], entry)
                        categorySequences.append(sequence)

                    categoryCharacters += categoryEntries.characterCount

                self.assertEqual(
                    tuple(sorted(categorySequences)),
                    generationSequences,
                )
                self.assertEqual(generation.characterCount, categoryCharacters)
                liveSequences.extend(generationSequences)
                liveCharacters += generation.characterCount

            self.assertEqual(
                tuple(entry.sequence for entry in manager.entries()),
                tuple(sorted(liveSequences)),
            )
            self.assertEqual(manager.entryCount(), len(liveSequences))
            self.assertEqual(manager._retainedEntryCount, len(liveSequences))
            self.assertEqual(
                manager.retainedCharacters,
                liveCharacters,
            )
            self.assertEqual(manager._retainedCharacters, liveCharacters)
            self.assertEqual(
                manager._retiredEntryCount,
                sum(batch.entryCount for batch in manager._retiredBatches),
            )
            self.assertEqual(
                manager._retiredCharacters,
                sum(batch.characterCount for batch in manager._retiredBatches),
            )

    def testBoundedBufferCategoriesAndRuntimeClear(self):
        """Retain only the newest entries and clear runtime categories alone."""
        manager = LogManager(maximumEntries=4)
        manager.append('application 1')
        manager.append('core 1', CORE_LOG_CATEGORY)
        manager.append('application 2')
        manager.append('core 2', CORE_LOG_CATEGORY)
        manager.append('application 3')

        sequence, entries = manager.snapshot()

        self.assertEqual(sequence, 5)
        self.assertEqual(
            tuple(entry.message for entry in entries),
            ('core 1', 'application 2', 'core 2', 'application 3'),
        )
        self.assertEqual(
            tuple(entry.message for entry in manager.entries(CORE_LOG_CATEGORY)),
            ('core 1', 'core 2'),
        )

        manager.clear(runtimeOnly=True)

        self.assertEqual(
            tuple(entry.categoryId for entry in manager.entries()),
            (APPLICATION_LOG_CATEGORY, APPLICATION_LOG_CATEGORY),
        )

    def testConcurrentProducersReceiveUniqueOrderedSequences(self):
        """Serialize worker-thread appends without losing or duplicating entries."""
        manager = LogManager(maximumEntries=500)

        def produce(prefix):
            """Append one deterministic worker batch."""
            for index in range(100):
                manager.append(f'{prefix}-{index}')

        workers = tuple(
            threading.Thread(target=produce, args=(prefix,))
            for prefix in ('a', 'b', 'c')
        )

        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(5)

        entries = manager.entries()
        sequences = tuple(entry.sequence for entry in entries)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(entries), 300)
        self.assertEqual(sequences, tuple(range(1, 301)))
        self.assertEqual(len({entry.message for entry in entries}), 300)

    def testAutoClearRetainsOnlyApplicationHistoryAtCoreThreshold(self):
        """Clear every non-Application category at the Core threshold."""
        manager = LogManager(
            maximumEntries=20,
            autoClearMaximumEntries=3,
        )
        cleared = []
        componentCategory = manager.registerComponent(
            'component.fixture',
            'Fixture',
        )

        manager.entriesCleared.connect(cleared.append)
        manager.append('application retained', APPLICATION_LOG_CATEGORY)

        for index in range(3):
            manager.append(f'old core {index}', CORE_LOG_CATEGORY)

        manager.append('old tun2socks', TUN2SOCKS_LOG_CATEGORY)
        manager.append('old component', componentCategory.id)

        manager.append('new core after clear', CORE_LOG_CATEGORY)

        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application retained', 'new core after clear'),
        )
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 1)
        self.assertEqual(manager.entryCount(TUN2SOCKS_LOG_CATEGORY), 0)
        self.assertEqual(manager.entryCount(componentCategory.id), 0)
        self.assertEqual(manager.entryCount(APPLICATION_LOG_CATEGORY), 1)
        self.assertEqual(
            cleared,
            [
                frozenset(
                    {
                        CORE_LOG_CATEGORY,
                        TUN2SOCKS_LOG_CATEGORY,
                        componentCategory.id,
                    }
                )
            ],
        )

    def testDisablingAutoClearLeavesOnlyGlobalBoundActive(self):
        """Do not apply the Core threshold while automatic clearing is disabled."""
        manager = LogManager(
            maximumEntries=10,
            autoClearMaximumEntries=3,
            autoClearEnabled=False,
        )
        manager.append('application retained', APPLICATION_LOG_CATEGORY)

        for index in range(3):
            manager.append(f'core {index}', CORE_LOG_CATEGORY)
            manager.append(f'tun2socks {index}', TUN2SOCKS_LOG_CATEGORY)

        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 3)

        manager.setAutoClearEnabled(True)

        self.assertTrue(manager.autoClearEnabled)
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 0)
        self.assertEqual(manager.entryCount(TUN2SOCKS_LOG_CATEGORY), 0)
        self.assertEqual(manager.entryCount(APPLICATION_LOG_CATEGORY), 1)

    def testCharacterBudgetsRemainHardWhenAutoClearIsDisabled(self):
        """Bound both total text and one hostile entry independently of count."""
        manager = LogManager(
            maximumEntries=100,
            maximumCharacters=80,
            maximumEntryCharacters=32,
            autoClearEnabled=False,
        )

        manager.append('a' * 100, CORE_LOG_CATEGORY)

        self.assertEqual(len(manager.entries()[0].message), 32)
        self.assertIn('truncated', manager.entries()[0].message)

        for index in range(20):
            manager.append(f'{index:02d}-' + ('x' * 17), CORE_LOG_CATEGORY)

        self.assertLessEqual(manager.retainedCharacters, 80)
        self.assertLessEqual(manager.entryCount(), 4)
        self.assertEqual(
            manager.retainedCharacters,
            sum(len(entry.message) for entry in manager.entries()),
        )
        self.assertEqual(
            manager.entryCount(CORE_LOG_CATEGORY),
            manager.entryCount(),
        )

        self._assertIndexesConsistent(manager)

    def testCategoryOperationsDoNotTraverseUnrelatedApplicationHistory(self):
        """Make Core rollover constant regardless of runtime/history skew."""
        cases = (
            (1_000, 7_000, 2_000),
            (9_000, 900, 100),
        )

        for applicationCount, coreCount, tunCount in cases:
            with self.subTest(
                application=applicationCount,
                core=coreCount,
                tun2socks=tunCount,
            ):
                manager = LogManager(
                    maximumEntries=20_000,
                    autoClearMaximumEntries=coreCount,
                )

                for index in range(applicationCount):
                    manager.append(
                        f'application {index}',
                        APPLICATION_LOG_CATEGORY,
                    )

                for index in range(coreCount):
                    manager.append(f'core {index}', CORE_LOG_CATEGORY)

                for index in range(tunCount):
                    manager.append(f'tun2socks {index}', TUN2SOCKS_LOG_CATEGORY)

                applicationGeneration = manager._applicationGeneration
                runtimeGeneration = manager._runtimeGeneration
                observedIndexes = []

                for generation in manager._activeGenerationsLocked():
                    observedEntries = _ObservedEntryIndex(generation.entries)
                    generation.entries = observedEntries
                    observedIndexes.append(observedEntries)

                    for categoryEntries in generation.entriesByCategory.values():
                        observedCategory = _ObservedEntryIndex(categoryEntries.entries)
                        categoryEntries.entries = observedCategory
                        observedIndexes.append(observedCategory)

                sequence, coreEntries = manager.snapshot(CORE_LOG_CATEGORY)

                self.assertEqual(
                    sequence,
                    applicationCount + coreCount + tunCount,
                )
                self.assertEqual(len(coreEntries), coreCount)
                self.assertEqual(
                    sum(index.iterationRequests for index in observedIndexes),
                    1,
                )

                for index in observedIndexes:
                    index.iterationRequests = 0

                manager.append('new core after clear', CORE_LOG_CATEGORY)

                self.assertIs(manager._applicationGeneration, applicationGeneration)
                self.assertIsNot(manager._runtimeGeneration, runtimeGeneration)
                self.assertEqual(
                    sum(index.iterationRequests for index in observedIndexes),
                    0,
                )
                self.assertEqual(
                    sum(len(index.deletedKeys) for index in observedIndexes),
                    0,
                )
                self.assertEqual(
                    sum(index.oldestRemovals for index in observedIndexes),
                    0,
                )
                self.assertEqual(
                    manager.retiredEntryCount,
                    coreCount + tunCount,
                )
                self.assertEqual(
                    manager.entryCount(APPLICATION_LOG_CATEGORY),
                    applicationCount,
                )
                self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 1)
                self.assertEqual(manager.entryCount(TUN2SOCKS_LOG_CATEGORY), 0)
                self.assertEqual(
                    tuple(entry.message for entry in manager.entries()),
                    tuple(f'application {index}' for index in range(applicationCount))
                    + ('new core after clear',),
                )
                self._assertIndexesConsistent(manager)

    def testWholeGenerationClearDoesNoPhysicalEntryWorkOnCaller(self):
        """Swap every active stream without traversing or destroying its entries."""
        manager = LogManager(maximumEntries=1_000, autoClearEnabled=False)
        otherCategory = manager.registerComponent(
            'component.persistent',
            'Persistent',
            runtime=False,
        )

        for index in range(100):
            manager.append(f'application {index}', APPLICATION_LOG_CATEGORY)
            manager.append(f'core {index}', CORE_LOG_CATEGORY)
            manager.append(f'other {index}', otherCategory.id)

        observedIndexes = []

        for generation in manager._activeGenerationsLocked():
            observedEntries = _ObservedEntryIndex(generation.entries)
            generation.entries = observedEntries
            observedIndexes.append(observedEntries)

            for categoryEntries in generation.entriesByCategory.values():
                observedCategory = _ObservedEntryIndex(categoryEntries.entries)
                categoryEntries.entries = observedCategory
                observedIndexes.append(observedCategory)

        self.assertEqual(manager.entryCount(), 300)
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 100)
        self.assertGreater(manager.retainedCharacters, 0)
        self.assertEqual(
            sum(index.iterationRequests for index in observedIndexes),
            0,
        )

        manager.append('application after observation', APPLICATION_LOG_CATEGORY)

        self.assertEqual(
            sum(index.iterationRequests for index in observedIndexes),
            0,
        )

        manager.clear()

        self.assertEqual(manager.entryCount(), 0)
        self.assertEqual(manager.retainedCharacters, 0)
        self.assertEqual(manager.retiredEntryCount, 301)
        self.assertEqual(manager.entries(), tuple())
        self.assertEqual(
            sum(index.iterationRequests for index in observedIndexes),
            0,
        )
        self.assertEqual(
            sum(len(index.deletedKeys) for index in observedIndexes),
            0,
        )
        self.assertEqual(
            sum(index.oldestRemovals for index in observedIndexes),
            0,
        )
        self._assertIndexesConsistent(manager)

    def testSnapshotsNeverTraverseRetiredGenerations(self):
        """Materialize only live streams after an immediate runtime rollover."""
        manager = LogManager(maximumEntries=100, autoClearEnabled=False)
        manager.append('application', APPLICATION_LOG_CATEGORY)
        manager.append('core', CORE_LOG_CATEGORY)
        manager.append('tun2socks', TUN2SOCKS_LOG_CATEGORY)
        retiredGeneration = manager._runtimeGeneration
        observedGlobal = _ObservedEntryIndex(retiredGeneration.entries)
        observedCore = _ObservedEntryIndex(
            retiredGeneration.entriesByCategory[CORE_LOG_CATEGORY].entries
        )
        retiredGeneration.entries = observedGlobal
        retiredGeneration.entriesByCategory[CORE_LOG_CATEGORY].entries = observedCore

        manager.clear(runtimeOnly=True)

        self.assertEqual(manager.entries(CORE_LOG_CATEGORY), tuple())
        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application',),
        )
        self.assertEqual(observedGlobal.iterationRequests, 0)
        self.assertEqual(observedCore.iterationRequests, 0)
        self.assertEqual(observedGlobal.oldestRemovals, 0)
        self.assertEqual(manager.retiredEntryCount, 2)

    def testSelectiveCategoryClearUsesDocumentedSharedStreamFallback(self):
        """Unlink only k selected entries when another category shares a stream."""
        manager = LogManager(maximumEntries=1_000, autoClearEnabled=False)

        for index in range(100):
            manager.append(f'core {index}', CORE_LOG_CATEGORY)

        for index in range(10):
            manager.append(f'tun2socks {index}', TUN2SOCKS_LOG_CATEGORY)

        runtimeGeneration = manager._runtimeGeneration
        observedGlobal = _ObservedEntryIndex(runtimeGeneration.entries)
        observedCore = _ObservedEntryIndex(
            runtimeGeneration.entriesByCategory[CORE_LOG_CATEGORY].entries
        )
        runtimeGeneration.entries = observedGlobal
        runtimeGeneration.entriesByCategory[CORE_LOG_CATEGORY].entries = observedCore

        manager.clear(CORE_LOG_CATEGORY)

        self.assertIs(manager._runtimeGeneration, runtimeGeneration)
        self.assertEqual(observedCore.iterationRequests, 1)
        self.assertEqual(len(observedGlobal.deletedKeys), 100)
        self.assertEqual(observedGlobal.oldestRemovals, 0)
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 0)
        self.assertEqual(manager.entryCount(TUN2SOCKS_LOG_CATEGORY), 10)
        self.assertEqual(manager.retiredEntryCount, 100)

        observedGlobal.iterationRequests = 0
        observedGlobal.deletedKeys.clear()

        manager.clear(TUN2SOCKS_LOG_CATEGORY)

        self.assertIsNot(manager._runtimeGeneration, runtimeGeneration)
        self.assertEqual(observedGlobal.iterationRequests, 0)
        self.assertEqual(observedGlobal.deletedKeys, [])
        self.assertEqual(observedGlobal.oldestRemovals, 0)
        self.assertEqual(manager.entryCount(), 0)
        self.assertEqual(manager.retiredEntryCount, 110)
        self._assertIndexesConsistent(manager)

    def testRetiredCleanupIsBoundedAndEventuallyReleasesEntries(self):
        """Release at most the fixed budget from a retired generation per turn."""
        manager = LogManager(maximumEntries=100, autoClearEnabled=False)
        manager.RetiredCleanupBudget = 3
        manager.AppendRetiredCleanupBudget = 1
        entryReferences = []

        for index in range(10):
            entry = manager.append(f'core {index}', CORE_LOG_CATEGORY)
            entryReferences.append(weakref.ref(entry))

        del entry

        runtimeGeneration = manager._runtimeGeneration
        observedEntries = _ObservedEntryIndex(runtimeGeneration.entries)
        runtimeGeneration.entries = observedEntries

        manager.clear(runtimeOnly=True)

        self.assertEqual(manager.retiredEntryCount, 10)
        self.assertEqual(observedEntries.oldestRemovals, 0)
        self.assertTrue(all(reference() is not None for reference in entryReferences))

        manager.append('application', APPLICATION_LOG_CATEGORY)

        self.assertEqual(manager.retiredEntryCount, 9)
        self.assertEqual(observedEntries.oldestRemovals, 1)

        cleanupTurns = 0

        while manager.retiredEntryCount:
            before = manager.retiredEntryCount

            with manager._lock:
                cleaned = manager._cleanupRetiredLocked()

            cleanupTurns += 1
            self.assertLessEqual(cleaned, manager.RetiredCleanupBudget)
            self.assertEqual(manager.retiredEntryCount, before - cleaned)

        self.assertEqual(cleanupTurns, 3)
        self.assertEqual(observedEntries.oldestRemovals, 10)
        self.assertEqual(manager.retiredCharacters, 0)
        self.assertEqual(len(manager._retiredBatches), 0)
        self.assertTrue(all(reference() is None for reference in entryReferences))
        self._assertIndexesConsistent(manager)

    def testQueuedCleanupEventuallyDrainsWithoutFurtherLogging(self):
        """Finish physical reclamation through bounded queued manager turns."""
        application()
        manager = LogManager(maximumEntries=100, autoClearEnabled=False)
        manager.RetiredCleanupBudget = 2
        entryReferences = []

        for index in range(9):
            entry = manager.append(f'core {index}', CORE_LOG_CATEGORY)
            entryReferences.append(weakref.ref(entry))

        del entry

        manager.clear(runtimeOnly=True)

        self.assertEqual(manager.retiredEntryCount, 9)

        processQtEvents()

        self.assertEqual(manager.retiredEntryCount, 0)
        self.assertEqual(manager.retiredCharacters, 0)
        self.assertTrue(all(reference() is None for reference in entryReferences))

    def testQueuedCleanupDoesNotOutliveDestroyedManager(self):
        """Discard pending self-delivery at the manager's QObject boundary."""
        application()
        manager = LogManager(maximumEntries=100, autoClearEnabled=False)
        manager.RetiredCleanupBudget = 1
        destroyed = []
        manager.destroyed.connect(lambda: destroyed.append(True))

        for index in range(20):
            manager.append(f'core {index}', CORE_LOG_CATEGORY)

        manager.clear(runtimeOnly=True)

        managerReference = weakref.ref(manager)
        manager.deleteLater()
        del manager

        processQtEvents()

        self.assertEqual(destroyed, [True])
        self.assertIsNone(managerReference())

    def testRepeatedFastClearsKeepRetiredEntryBacklogBounded(self):
        """Prevent retired generations from accumulating beyond live capacity."""
        manager = LogManager(maximumEntries=128, autoClearEnabled=False)
        manager.RetiredCleanupBudget = 1

        for index in range(manager.maximumEntries):
            manager.append(f'initial {index}', CORE_LOG_CATEGORY)

        manager.clear(runtimeOnly=True)

        self.assertEqual(manager.retiredEntryCount, manager.maximumEntries)

        for index in range(500):
            manager.append(f'replacement {index}', CORE_LOG_CATEGORY)
            manager.clear(runtimeOnly=True)

            self.assertLessEqual(
                manager.retiredEntryCount,
                manager.maximumEntries,
            )
            self.assertLessEqual(
                manager.entryCount() + manager.retiredEntryCount,
                manager.maximumEntries,
            )
            self.assertLessEqual(
                len(manager._retiredBatches),
                manager.retiredEntryCount,
            )

        while manager.retiredEntryCount:
            with manager._lock:
                manager._cleanupRetiredLocked()

        self.assertEqual(manager.retiredCharacters, 0)
        self.assertEqual(len(manager._retiredBatches), 0)
        self._assertIndexesConsistent(manager)

    def testRepeatedCoreAutoClearKeepsOnlyTheNewestRuntimeEpoch(self):
        """Roll over repeatedly without exposing or accumulating older Core lines."""
        manager = LogManager(
            maximumEntries=100,
            autoClearMaximumEntries=1,
        )
        manager.RetiredCleanupBudget = 1
        manager.append('application', APPLICATION_LOG_CATEGORY)
        firstGenerationId = manager._runtimeGeneration.identifier

        for index in range(100):
            manager.append(f'core {index}', CORE_LOG_CATEGORY)

            self.assertEqual(
                tuple(entry.message for entry in manager.entries(CORE_LOG_CATEGORY)),
                (f'core {index}',),
            )
            self.assertLessEqual(manager.retiredEntryCount, 1)

        self.assertGreater(manager._runtimeGeneration.identifier, firstGenerationId)
        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application', 'core 99'),
        )
        self.assertEqual(manager.entryCount(APPLICATION_LOG_CATEGORY), 1)
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 1)
        self._assertIndexesConsistent(manager)

    def testRetentionEvictsOldestEntriesFromBothIndexes(self):
        """Keep category indexes synchronized through repeated global eviction."""
        manager = LogManager(
            maximumEntries=4,
            maximumCharacters=20,
            maximumEntryCharacters=20,
            autoClearEnabled=False,
        )
        categoryIds = (
            APPLICATION_LOG_CATEGORY,
            CORE_LOG_CATEGORY,
            TUN2SOCKS_LOG_CATEGORY,
        )

        for index in range(3):
            manager.append(f'{index:04d}', categoryIds[index])

        observedIndexes = []

        for generation in manager._activeGenerationsLocked():
            observedEntries = _ObservedEntryIndex(generation.entries)
            generation.entries = observedEntries
            observedIndexes.append(observedEntries)

        for index in range(3, 20):
            manager.append(f'{index:04d}', categoryIds[index % len(categoryIds)])

        entries = manager.entries()

        self.assertEqual(
            tuple(entry.message for entry in entries),
            ('0016', '0017', '0018', '0019'),
        )
        self.assertEqual(
            sum(index.oldestRemovals for index in observedIndexes),
            16,
        )
        self.assertEqual(manager.retainedCharacters, 16)
        self._assertIndexesConsistent(manager)

    def testGlobalRetentionIgnoresRetiredGenerations(self):
        """Evict the oldest live stream head across a runtime rollover."""
        manager = LogManager(
            maximumEntries=4,
            maximumCharacters=100,
            maximumEntryCharacters=100,
            autoClearEnabled=False,
        )
        manager.RetiredCleanupBudget = 1

        manager.append('application 1', APPLICATION_LOG_CATEGORY)
        manager.append('old core', CORE_LOG_CATEGORY)
        manager.append('application 2', APPLICATION_LOG_CATEGORY)
        manager.append('old tun2socks', TUN2SOCKS_LOG_CATEGORY)

        manager.clear(runtimeOnly=True)

        self.assertEqual(manager.retiredEntryCount, 2)
        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application 1', 'application 2'),
        )

        manager.append('new core', CORE_LOG_CATEGORY)
        manager.append('application 3', APPLICATION_LOG_CATEGORY)
        manager.append('new tun2socks', TUN2SOCKS_LOG_CATEGORY)

        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            (
                'application 2',
                'new core',
                'application 3',
                'new tun2socks',
            ),
        )
        self.assertEqual(manager.retiredEntryCount, 0)
        self.assertEqual(manager.entryCount(APPLICATION_LOG_CATEGORY), 2)
        self.assertEqual(manager.entryCount(CORE_LOG_CATEGORY), 1)
        self.assertEqual(manager.entryCount(TUN2SOCKS_LOG_CATEGORY), 1)
        self._assertIndexesConsistent(manager)

    def testRegisteredCategoryClearAndClearAllPreserveSignals(self):
        """Clear one late category and then all entries with compatible signals."""
        manager = LogManager(maximumEntries=20, autoClearEnabled=False)
        category = manager.registerComponent(
            'component.audit',
            'Audit',
            runtime=False,
        )
        cleared = []
        manager.entriesCleared.connect(cleared.append)

        manager.append('application', APPLICATION_LOG_CATEGORY)
        manager.append('audit 1', category.id)
        manager.append('core', CORE_LOG_CATEGORY)
        manager.append('audit 2', category.id)

        self.assertEqual(manager.snapshot('unknown.category')[1], tuple())
        self.assertEqual(manager.entryCount(category.id), 2)
        self.assertEqual(manager.plainText(category.id), 'audit 1\naudit 2')

        manager.clear(runtimeOnly=True)

        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application', 'audit 1', 'audit 2'),
        )
        self.assertEqual(
            cleared,
            [frozenset({CORE_LOG_CATEGORY, TUN2SOCKS_LOG_CATEGORY})],
        )

        manager.clear(category.id)

        self.assertEqual(
            tuple(entry.message for entry in manager.entries()),
            ('application',),
        )
        self.assertEqual(
            cleared,
            [
                frozenset({CORE_LOG_CATEGORY, TUN2SOCKS_LOG_CATEGORY}),
                frozenset({category.id}),
            ],
        )
        self._assertIndexesConsistent(manager)

        manager.clear()
        manager.clear()

        self.assertEqual(manager.entries(), tuple())
        self.assertEqual(
            cleared,
            [
                frozenset({CORE_LOG_CATEGORY, TUN2SOCKS_LOG_CATEGORY}),
                frozenset({category.id}),
                None,
            ],
        )
        self._assertIndexesConsistent(manager)

    def testConcurrentAppendClearAndSnapshotsKeepIndexesConsistent(self):
        """Serialize snapshots and category clears racing with log producers."""
        manager = LogManager(maximumEntries=5_000, autoClearEnabled=False)
        category = manager.registerComponent('component.concurrent', 'Concurrent')
        started = threading.Event()
        finished = threading.Event()
        failures = []
        observations = []

        def produce():
            """Append interleaved categories while the observer reads and clears."""
            try:
                started.set()

                categoryIds = (
                    APPLICATION_LOG_CATEGORY,
                    CORE_LOG_CATEGORY,
                    category.id,
                )

                for index in range(3_000):
                    manager.append(
                        f'entry {index}',
                        categoryIds[index % len(categoryIds)],
                    )
            except Exception as error:
                failures.append(error)
            finally:
                finished.set()

        def observeAndClear():
            """Take filtered snapshots and clear one category during ingestion."""
            try:
                started.wait(5)

                while True:
                    manager.snapshot(CORE_LOG_CATEGORY)
                    manager.snapshot(category.id)
                    manager.clear(category.id)
                    observations.append(True)

                    if finished.wait(0.0001):
                        break
            except Exception as error:
                failures.append(error)

        observer = threading.Thread(target=observeAndClear)
        producer = threading.Thread(target=produce)
        observer.start()
        producer.start()
        producer.join(10)
        observer.join(10)

        self.assertFalse(producer.is_alive())
        self.assertFalse(observer.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(observations)

        sequences = tuple(entry.sequence for entry in manager.entries())

        self.assertEqual(sequences, tuple(sorted(sequences)))
        self.assertEqual(len(sequences), len(set(sequences)))
        self._assertIndexesConsistent(manager)

    def testEntrySignalsAndCrossThreadChangeNotificationsRemainCompatible(self):
        """Emit every entry and coalesce presentation refreshes by producer batch."""
        application()
        manager = LogManager(maximumEntries=100, autoClearEnabled=False)
        added = []
        changed = []
        manager.entryAdded.connect(added.append)
        manager.entriesChanged.connect(changed.append)

        def produce():
            """Publish one batch without allowing the Qt queue to drain midway."""
            for index in range(50):
                manager.append(f'worker {index}', CORE_LOG_CATEGORY)

        worker = threading.Thread(target=produce)
        worker.start()
        worker.join(5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(added, [])
        self.assertEqual(changed, [])

        processQtEvents()

        self.assertEqual(len(added), 50)
        self.assertEqual(
            tuple(entry.message for entry in added),
            tuple(f'worker {index}' for index in range(50)),
        )
        self.assertEqual(changed, [50])

        manager.append('application 1', APPLICATION_LOG_CATEGORY)
        manager.append('application 2', APPLICATION_LOG_CATEGORY)

        self.assertEqual(len(added), 52)

        processQtEvents()

        self.assertEqual(changed, [50, 52])


class MetricsHistoryTest(unittest.TestCase):
    """Verify bounded history and metric-specific aggregation semantics."""

    def testPruningNormalizationAndAggregation(self):
        """Prune stale values, average speed, and retain latest usage."""
        manager = MetricsHistory(maximumHistorySeconds=10)
        changed = []
        manager.historyChanged.connect(lambda: changed.append(True))

        manager.recordSample(
            {
                DOWNLOAD_SPEED_METRIC: -5,
                DOWNLOAD_USAGE_METRIC: 100,
                'unknown': 9,
            },
            sampledAt=0,
        )
        manager.recordSample(
            {
                DOWNLOAD_SPEED_METRIC: 20,
                DOWNLOAD_USAGE_METRIC: 150,
            },
            sampledAt=11,
        )
        manager.recordSample(
            {
                DOWNLOAD_SPEED_METRIC: 40,
                DOWNLOAD_USAGE_METRIC: 190,
            },
            sampledAt=19,
        )

        self.assertEqual(manager.sampleCount(), 2)
        self.assertEqual(len(changed), 3)
        self.assertEqual(
            tuple(
                point.value
                for point in manager.series(
                    DOWNLOAD_SPEED_METRIC,
                    20,
                    granularitySeconds=20,
                    now=19,
                )
            ),
            (30.0,),
        )
        self.assertEqual(
            tuple(
                point.value
                for point in manager.series(
                    DOWNLOAD_USAGE_METRIC,
                    20,
                    granularitySeconds=20,
                    now=21,
                )
            ),
            (190.0,),
        )

    def testInvalidSamplesDoNotPolluteHistory(self):
        """Ignore unsupported and non-finite values without emitting changes."""
        manager = MetricsHistory()
        changed = []
        manager.historyChanged.connect(lambda: changed.append(True))

        manager.recordSample({'unknown': 1}, sampledAt=1)
        manager.recordSample({DOWNLOAD_SPEED_METRIC: float('nan')}, sampledAt=2)

        self.assertEqual(manager.rawSamples(), tuple())
        self.assertEqual(changed, [])

    def testDefensiveSampleCeilingBoundsBurstCadence(self):
        """Retain only the newest samples even when time does not advance."""
        manager = MetricsHistory(
            maximumHistorySeconds=24 * 60 * 60,
            maximumSampleCount=25,
        )

        for index in range(1000):
            manager.recordSample({DOWNLOAD_SPEED_METRIC: index}, sampledAt=1)

        self.assertEqual(manager.sampleCount(), 25)
        self.assertEqual(manager.rawSamples()[0].values[DOWNLOAD_SPEED_METRIC], 975)
        self.assertEqual(manager.rawSamples()[-1].values[DOWNLOAD_SPEED_METRIC], 999)


class TranslationExtractorTest(unittest.TestCase):
    """Verify static translation extraction and constant interpolation."""

    def testApplicationConstantFStringIsExtractedAndResolved(self):
        """Accept constant-only f-strings while rejecting runtime formatting."""
        import Translation

        content = """
_(f'{APPLICATION_NAME} is ready')
_(f'{runtimeValue} is not static')
_(f'{APPLICATION_NAME!r} is not supported')
"""

        keys = tuple(Translation.getTranslationKeys(content))

        self.assertEqual(keys, ('{APPLICATION_NAME} is ready',))
        self.assertEqual(
            Translation.resolveAppConstants(keys[0]),
            f'{Translation.APPLICATION_NAME} is ready',
        )


if __name__ == '__main__':
    unittest.main()
