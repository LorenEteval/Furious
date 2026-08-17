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

"""Protect isolated subscription-group synchronization semantics."""

from __future__ import annotations

from Furious.Models import ConfigFactory, ServerProfile
from Furious.Service.SubscriptionSync import SubscriptionSynchronizer

import unittest


def profile(
    name: str,
    address: str,
    *,
    source: str = '',
    managed: bool = False,
    key: str = '',
    favorite: bool = False,
):
    """Create one core-neutral profile with explicit ownership metadata."""
    return ServerProfile.fromConfiguration(
        ConfigFactory({'type': 'fixture', 'address': address, 'port': 443}),
        {
            'displayName': name,
            'subscriptionSource': source,
            'subscriptionManaged': managed,
            'subscriptionProfileKey': key,
            'favorite': favorite,
        },
    )


class SubscriptionSynchronizerTest(unittest.TestCase):
    """Verify one subscription can never mutate unrelated or manual profiles."""

    def testGroupUpdateIsAtomicAndPreservesLocalIdentityMetadata(self):
        """Update, add, and remove only the selected managed group."""
        manual = profile('Manual', 'manual.example')
        retained = profile(
            'Local label',
            'old.example',
            source='group-a',
            managed=True,
            key='upstream:one',
            favorite=True,
        )
        removed = profile(
            'Removed',
            'removed.example',
            source='group-a',
            managed=True,
            key='upstream:removed',
        )
        other = profile(
            'Other group',
            'other.example',
            source='group-b',
            managed=True,
            key='upstream:other',
        )
        originalId = retained.metadata.profileId
        profiles = [manual, retained, removed, other]
        incoming = [
            profile('Remote label', 'new.example', key='upstream:one'),
            profile('Added', 'added.example', key='upstream:two'),
        ]

        result = SubscriptionSynchronizer().reconcile(
            profiles,
            incoming,
            'group-a',
        )

        self.assertEqual((result.added, result.updated, result.removed), (1, 1, 1))
        self.assertIs(profiles[0], manual)
        self.assertIs(profiles[1], retained)
        self.assertIs(profiles[-1], other)
        self.assertEqual(retained.metadata.profileId, originalId)
        self.assertEqual(retained.itemRemark, 'Remote label')
        self.assertTrue(retained.metadata.favorite)
        self.assertEqual(retained.connection['address'], 'new.example')
        self.assertTrue(removed.deleted)
        self.assertEqual(
            tuple(item.index for item in profiles),
            tuple(range(len(profiles))),
        )
        self.assertEqual(manual.itemSubscription, '')
        self.assertFalse(manual.itemSubscriptionManaged)
        self.assertEqual(other.connection['address'], 'other.example')

    def testLegacyKeysAndDuplicateConnectionsAreDeterministic(self):
        """Assign stable occurrence keys without relying on row position alone."""
        first = profile('First', 'same.example', source='group', managed=True)
        second = profile('Second', 'same.example', source='group', managed=True)
        profiles = [first, second]

        SubscriptionSynchronizer._ensureKeys(profiles, 'group')

        firstKey = first.metadata.subscriptionProfileKey
        secondKey = second.metadata.subscriptionProfileKey

        self.assertTrue(firstKey.startswith('config:'))
        self.assertEqual(secondKey, f'{firstKey}#2')

        SubscriptionSynchronizer._ensureKeys(profiles, 'group')

        self.assertEqual(first.metadata.subscriptionProfileKey, firstKey)
        self.assertEqual(second.metadata.subscriptionProfileKey, secondKey)

    def testEmptyGroupFailsBeforeMutatingInput(self):
        """Reject ambiguous ownership without partially rewriting profiles."""
        existing = profile('Manual', 'manual.example')
        incoming = profile('Incoming', 'incoming.example')
        profiles = [existing]

        with self.assertRaisesRegex(ValueError, 'group ID'):
            SubscriptionSynchronizer().reconcile(profiles, [incoming], '')

        self.assertEqual(profiles, [existing])
        self.assertEqual(incoming.itemSubscription, '')
        self.assertFalse(incoming.itemSubscriptionManaged)


if __name__ == '__main__':
    unittest.main()
