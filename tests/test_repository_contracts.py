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

"""Protect repository isolation, live-collection, and compatibility contracts."""

from __future__ import annotations

from Furious.Frozenlib import AppSettings
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Models.Encoding import PyBase64Encoder, UJSONEncoder
from Furious.Repository.Routings import UserRoutings
from Furious.Repository.Servers import UserServers
from Furious.Repository.Storage import Storage
from Furious.Repository.Subscriptions import SubscriptionGroup, UserSubs
from Furious.Repository.TunSettings import UserTUNSettings

from tests.support import application, isolatedSettings

from types import SimpleNamespace
from unittest import mock

import importlib
import unittest

StorageModule = importlib.import_module('Furious.Repository.Storage')


class RepositoryContractTest(unittest.TestCase):
    """Verify every persisted collection stays isolated and backward compatible."""

    @classmethod
    def setUpClass(cls):
        """Create the application required by the process-lifetime storage cache."""
        application()

    def tearDown(self):
        """Release application-lifetime repository cache entries between tests."""
        self._clearStorageCaches()

    @staticmethod
    def _clearStorageCaches():
        """Clear only finite cache entries created by this test process."""
        for name in (
            '_UserServersStorage',
            '_UserSubsStorage',
            '_UserTUNSettingsStorage',
            '_UserRoutingsStorage',
        ):
            getattr(Storage, name).cache_clear()

    @staticmethod
    def _profile(
        name: str,
        *,
        source='',
        managed=False,
        profileKey='',
    ):
        """Build one profile with deterministic metadata for repository tests."""
        return ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture'}),
            {
                'displayName': name,
                'subscriptionSource': source,
                'subscriptionManaged': managed,
                'subscriptionProfileKey': profileKey,
            },
        )

    def testRoutingRepositoryRoundTripPreservesUnknownDocuments(self):
        """Persist arbitrary core-owned routing fields without normalization."""
        with isolatedSettings():
            repository = UserRoutings()
            repository.data()['custom-id'] = {
                'remark': 'Custom route',
                'routing': {
                    'domainStrategy': 'future-strategy',
                    'futureField': {'enabled': True},
                },
            }
            repository.sync()

            restored = UserRoutings().data()

            self.assertEqual(restored, repository.data())
            self.assertEqual(
                restored['custom-id']['routing']['futureField'],
                {'enabled': True},
            )

    def testTunSettingsRoundTripAndRejectsNonObjectRoots(self):
        """Keep valid unknown fields while treating incompatible roots as empty."""
        with isolatedSettings():
            repository = UserTUNSettings()
            repository.data().update(
                {
                    'interfaceName': 'fixture-tun',
                    'futureOption': {'mode': 'future'},
                }
            )
            repository.sync()

            self.assertEqual(UserTUNSettings().data(), repository.data())

            encodedList = PyBase64Encoder.encode(
                UJSONEncoder.encode(['not', 'an', 'object']).encode()
            )
            AppSettings.set('CustomTUNSettings', encodedList)

            self.assertEqual(UserTUNSettings().data(), {})

    def testStorageCachesOneLiveOwnerPerRepositoryType(self):
        """Return one intentional process-lifetime owner and its live collection."""
        with isolatedSettings():
            self._clearStorageCaches()

            routings = Storage.UserRoutings()
            tunSettings = Storage.UserTUNSettings()

            self.assertIs(routings, Storage.UserRoutings())
            self.assertIs(tunSettings, Storage.UserTUNSettings())

            routings['fixture'] = {'remark': 'Route'}
            tunSettings['interfaceName'] = 'fixture-tun'

            self.assertEqual(Storage.UserRoutings()['fixture']['remark'], 'Route')
            self.assertEqual(
                Storage.UserTUNSettings()['interfaceName'],
                'fixture-tun',
            )

    def testVisibleMovesPreserveHiddenSlotsAndSelectedOrder(self):
        """Reorder a filtered scope without moving hidden repository entries."""
        with isolatedSettings():
            repository = UserServers()
            profiles = [self._profile(name) for name in ('A', 'Hidden', 'B', 'C', 'D')]
            repository.data().extend(profiles)
            visibleIds = [
                profile.metadata.profileId
                for profile in profiles
                if profile.metadata.displayName != 'Hidden'
            ]
            selectedIds = [
                profiles[2].metadata.profileId,
                profiles[3].metadata.profileId,
            ]

            self.assertTrue(repository.moveProfiles(selectedIds, visibleIds, 'top'))
            self.assertEqual(
                [profile.metadata.displayName for profile in repository.data()],
                ['B', 'Hidden', 'C', 'A', 'D'],
            )
            self.assertEqual(
                [profile.index for profile in repository.data()],
                list(range(5)),
            )

            self.assertTrue(repository.moveProfiles(selectedIds, visibleIds, 'down'))
            self.assertEqual(
                [profile.metadata.displayName for profile in repository.data()],
                ['A', 'Hidden', 'B', 'C', 'D'],
            )

    def testMovingBetweenSubscriptionGroupsDetachesSyncOwnership(self):
        """Keep no-op ownership but make cross-group moves locally managed."""
        with isolatedSettings():
            repository = UserServers()
            unchanged = self._profile(
                'Same source',
                source='source-a',
                managed=True,
                profileKey='owned-a',
            )
            moved = self._profile(
                'Moved',
                source='source-a',
                managed=True,
                profileKey='owned-b',
            )
            repository.data().extend((unchanged, moved))

            self.assertFalse(
                repository.moveProfilesToSubscription(
                    [unchanged.metadata.profileId],
                    'source-a',
                )
            )
            self.assertTrue(unchanged.metadata.subscriptionManaged)
            self.assertEqual(
                unchanged.metadata.subscriptionProfileKey,
                'owned-a',
            )

            self.assertTrue(
                repository.moveProfilesToSubscription(
                    [moved.metadata.profileId],
                    'source-b',
                )
            )
            self.assertEqual(moved.metadata.subscriptionSource, 'source-b')
            self.assertFalse(moved.metadata.subscriptionManaged)
            self.assertEqual(moved.metadata.subscriptionProfileKey, '')

    def testStorageRejectsUnknownSubscriptionDestination(self):
        """Do not write a dangling group identity through the public facade."""
        profile = self._profile('Manual')

        with (
            mock.patch.object(Storage, 'SubscriptionGroup', return_value=None),
            mock.patch.object(
                Storage,
                '_UserServersStorage',
                return_value=SimpleNamespace(moveProfilesToSubscription=mock.Mock()),
            ) as repositoryFactory,
        ):
            self.assertFalse(
                Storage.moveUserServersToSubscription(
                    [profile.metadata.profileId],
                    'missing',
                )
            )
            repositoryFactory.return_value.moveProfilesToSubscription.assert_not_called()

    def testActiveServerRemarkUsesTheExactControllerProfile(self):
        """Render the selected live profile instead of swallowing a name error."""

        class DisplayConfiguration(CoreConfiguration):
            @property
            def itemRemark(self):
                """Expose the profile remark through the configuration contract."""
                return 'Active profile'

        profile = ServerProfile.fromConfiguration(
            DisplayConfiguration({'type': 'fixture'}),
            {'displayName': 'Active profile'},
        )
        controller = SimpleNamespace(
            activeProfile=profile,
            isConnected=mock.Mock(return_value=True),
        )

        with (
            mock.patch.object(
                StorageModule,
                'AppConnectionController',
                return_value=controller,
            ),
            mock.patch.object(Storage, 'UserServers', return_value=[profile]),
        ):
            self.assertEqual(
                Storage.Extras.UserServerRemark(),
                '1 - Active profile',
            )

    def testActiveServerRemarkOmitsIndexForNonRepositoryProfile(self):
        """Keep an active ad-hoc profile visible without inventing a row index."""
        profile = ServerProfile.fromConfiguration(
            CoreConfiguration({'type': 'fixture'}),
            {'displayName': 'Ad hoc'},
        )
        controller = SimpleNamespace(
            activeProfile=profile,
            isConnected=mock.Mock(return_value=True),
        )

        with (
            mock.patch.object(
                StorageModule,
                'AppConnectionController',
                return_value=controller,
            ),
            mock.patch.object(Storage, 'UserServers', return_value=[]),
        ):
            self.assertEqual(Storage.Extras.UserServerRemark(), 'Ad hoc')

    def testActivatedIndexMalformedInputFallsBackWithoutMutation(self):
        """Treat incompatible persisted input as no selection."""
        with isolatedSettings() as settings:
            settings.setValue('ActivatedItemIndex', 'not-an-index')

            self.assertEqual(Storage.UserActivatedItemIndex(), -1)
            self.assertEqual(settings.value('ActivatedItemIndex'), 'not-an-index')

    def testFailedRestoreIsNotOverwrittenByAutomaticCleanup(self):
        """Preserve recoverable persisted bytes when decoding fails at startup."""
        corrupt = b'eA=='

        with isolatedSettings():
            for setting, repositoryType, emptyValue in (
                ('Configuration', UserServers, []),
                ('CustomSubscription', UserSubs, {}),
                ('CustomRouting', UserRoutings, {}),
                ('CustomTUNSettings', UserTUNSettings, {}),
            ):
                with self.subTest(setting=setting):
                    AppSettings.set(setting, corrupt)
                    repository = repositoryType()

                    self.assertEqual(repository.data(), emptyValue)

                    repository.cleanup()

                    self.assertEqual(AppSettings.get(setting), corrupt)

    def testExplicitMutationCanReplaceAFailedRestoreFallback(self):
        """Allow a deliberate repository change to recover unreadable storage."""
        corrupt = b'eA=='

        with isolatedSettings():
            AppSettings.set('CustomTUNSettings', corrupt)
            repository = UserTUNSettings()
            repository.data()['interfaceName'] = 'replacement-tun'

            repository.cleanup()

            self.assertNotEqual(AppSettings.get('CustomTUNSettings'), corrupt)
            self.assertEqual(
                UserTUNSettings().data(),
                {'interfaceName': 'replacement-tun'},
            )


if __name__ == '__main__':
    unittest.main()
