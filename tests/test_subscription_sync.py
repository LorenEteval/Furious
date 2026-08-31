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

from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Service.SubscriptionSync import SubscriptionSynchronizer

import unittest
from unittest import mock


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
        CoreConfiguration({'type': 'fixture', 'address': address, 'port': 443}),
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

    def testPreparationFailureLeavesExistingAndIncomingProfilesUntouched(self):
        """Do not expose partial key or metadata changes before the commit point."""
        retained = profile(
            'Retained',
            'old.example',
            source='group',
            managed=True,
        )
        incoming = profile('Incoming', 'new.example')
        profiles = [retained]
        originalMetadata = retained.metadata.toMapping()
        originalConnection = retained.connection.deepcopy()

        with mock.patch(
            'Furious.Service.SubscriptionSync.profileConnectionFingerprint',
            side_effect=('legacy-key', RuntimeError('injected preparation failure')),
        ):
            with self.assertRaisesRegex(RuntimeError, 'injected preparation failure'):
                SubscriptionSynchronizer().reconcile(
                    profiles,
                    [incoming],
                    'group',
                )

        self.assertEqual(profiles, [retained])
        self.assertEqual(retained.metadata.toMapping(), originalMetadata)
        self.assertEqual(retained.connection, originalConnection)
        self.assertFalse(retained.deleted)
        self.assertEqual(incoming.itemSubscription, '')
        self.assertFalse(incoming.itemSubscriptionManaged)

    def testPreparedCommitPreservesLiveIdentityAndNewerLocalMetadata(self):
        """Apply worker data without replacing live retained profile objects."""
        retained = profile(
            'Before',
            'old.example',
            source='group',
            managed=True,
            key='upstream:one',
        )
        unrelated = profile('Manual', 'manual.example')
        profiles = [retained, unrelated]
        snapshot = SubscriptionSynchronizer().snapshot(profiles, 'group')
        incoming = profile('After', 'new.example', key='upstream:one')
        plan = SubscriptionSynchronizer().prepare(snapshot, (incoming,))

        retained.metadata.annotations = 'edited while preparing'
        retained.metadata.latency = '41 ms'

        result = SubscriptionSynchronizer().commit(profiles, plan)

        self.assertIs(profiles[0], retained)
        self.assertIs(profiles[1], unrelated)
        self.assertEqual(retained.connection['address'], 'new.example')
        self.assertEqual(retained.itemRemark, 'After')
        self.assertEqual(retained.metadata.annotations, 'edited while preparing')
        self.assertEqual(retained.metadata.latency, '41 ms')
        self.assertEqual(result.changedProfileIds, (retained.metadata.profileId,))

    def testPreparedCommitRejectsChangedGroupSource(self):
        """Never apply a plan after relevant live profile state diverges."""
        retained = profile(
            'Before',
            'old.example',
            source='group',
            managed=True,
            key='upstream:one',
        )
        profiles = [retained]
        synchronizer = SubscriptionSynchronizer()
        snapshot = synchronizer.snapshot(profiles, 'group')
        plan = synchronizer.prepare(
            snapshot,
            (profile('After', 'new.example', key='upstream:one'),),
        )

        retained.connection['address'] = 'locally-changed.example'

        with self.assertRaisesRegex(RuntimeError, 'source changed'):
            synchronizer.commit(profiles, plan)

        self.assertIs(profiles[0], retained)
        self.assertEqual(retained.connection['address'], 'locally-changed.example')


if __name__ == '__main__':
    unittest.main()
