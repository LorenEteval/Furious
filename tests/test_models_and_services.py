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
from Furious.Frozenlib import AppBinarySettings, AppSettings, ApplicationTheme
from Furious.Models import ConfigFactory, ProfileMetadata, ServerProfile
from Furious.Repository.Servers import UserServer, UserServers
from Furious.Repository.Subscriptions import SubscriptionGroup, UserSubs
from Furious.Service.LogManager import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)
from Furious.Service.MetricsDataManager import (
    DOWNLOAD_SPEED_METRIC,
    DOWNLOAD_USAGE_METRIC,
    MetricsDataManager,
)

from PySide6 import QtCore

import threading
import unittest

from tests.support import isolatedSettings


class ProfileModelTest(unittest.TestCase):
    """Verify metadata separation, compatibility, and copy semantics."""

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

    def testIndependentCopyGetsNewIdentityAndNoSubscriptionOwner(self):
        """Keep manual copies independent from subscription synchronization."""
        original = ServerProfile.fromConfiguration(
            ConfigFactory({'type': 'fixture', 'address': 'example.com'}),
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

    def testUserServerMappingRemainsBackwardCompatible(self):
        """Persist the canonical legacy record shape plus per-profile metadata."""
        profile = ServerProfile.fromConfiguration(
            ConfigFactory({'type': 'fixture', 'port': 1080}),
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
                    ConfigFactory({'type': 'fixture', 'value': 9}),
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


class LogManagerTest(unittest.TestCase):
    """Verify bounded, categorized, and thread-safe structured logging."""

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


class MetricsDataManagerTest(unittest.TestCase):
    """Verify bounded history and metric-specific aggregation semantics."""

    def testPruningNormalizationAndAggregation(self):
        """Prune stale values, average speed, and retain latest usage."""
        manager = MetricsDataManager(maximumHistorySeconds=10)
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
        manager = MetricsDataManager()
        changed = []
        manager.historyChanged.connect(lambda: changed.append(True))

        manager.recordSample({'unknown': 1}, sampledAt=1)
        manager.recordSample({DOWNLOAD_SPEED_METRIC: float('nan')}, sampledAt=2)

        self.assertEqual(manager.rawSamples(), tuple())
        self.assertEqual(changed, [])


if __name__ == '__main__':
    unittest.main()
