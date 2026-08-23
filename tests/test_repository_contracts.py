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
from Furious.Repository.Storage import Storage
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


if __name__ == '__main__':
    unittest.main()
