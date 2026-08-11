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

"""Reconcile subscription-owned profiles without affecting other groups."""

from __future__ import annotations

from Furious.Models import ServerProfile, profileConnectionFingerprint

from dataclasses import dataclass

__all__ = ['SubscriptionSyncResult', 'SubscriptionSynchronizer']


@dataclass(frozen=True)
class SubscriptionSyncResult:
    """Describe one atomic subscription-group synchronization."""

    groupId: str
    added: int
    updated: int
    removed: int
    profileIds: tuple[str, ...]
    removedProfileIds: tuple[str, ...]
    changedProfileIds: tuple[str, ...]


class SubscriptionSynchronizer:
    """Own stable, group-scoped profile reconciliation semantics."""

    LocalMetadataFields = (
        'annotations',
        'favorite',
        'group',
        'latency',
        'speed',
        'tags',
    )

    @staticmethod
    def _ensureKeys(profiles: list[ServerProfile], groupId: str):
        """Migrate legacy group profiles to deterministic occurrence keys."""
        occurrences = {}

        for profile in profiles:
            metadata = profile.metadata

            if metadata.subscriptionSource != groupId:
                continue

            if not metadata.subscriptionManaged:
                continue

            if metadata.subscriptionProfileKey:
                continue

            baseIdentity = f'config:{profileConnectionFingerprint(profile)}'
            occurrence = occurrences.get(baseIdentity, 0)
            occurrences[baseIdentity] = occurrence + 1
            metadata.subscriptionProfileKey = (
                baseIdentity if occurrence == 0 else f'{baseIdentity}#{occurrence + 1}'
            )

    def reconcile(
        self,
        profiles: list[ServerProfile],
        incomingProfiles,
        groupId: str,
    ) -> SubscriptionSyncResult:
        """Atomically replace only profiles managed by *groupId*."""
        if not groupId:
            raise ValueError('subscription group ID must not be empty')

        incoming = list(incomingProfiles)

        self._ensureKeys(profiles, groupId)

        managedIndexes = [
            index
            for index, profile in enumerate(profiles)
            if profile.itemSubscription == groupId and profile.itemSubscriptionManaged
        ]
        insertionIndex = min(managedIndexes) if managedIndexes else len(profiles)
        existingByKey = {
            profiles[index].metadata.subscriptionProfileKey: profiles[index]
            for index in managedIndexes
        }
        synchronized = []
        updated = 0
        added = 0
        changedProfileIds = []

        for profile in incoming:
            metadata = profile.metadata
            metadata.subscriptionSource = groupId
            metadata.subscriptionManaged = True

            if not metadata.subscriptionProfileKey:
                metadata.subscriptionProfileKey = (
                    f'config:{profileConnectionFingerprint(profile)}'
                )

            existing = existingByKey.pop(metadata.subscriptionProfileKey, None)

            if existing is None:
                added += 1
                synchronized.append(profile)

                continue

            oldFingerprint = profileConnectionFingerprint(existing)

            for fieldName in self.LocalMetadataFields:
                setattr(metadata, fieldName, getattr(existing.metadata, fieldName))

            metadata.profileId = existing.metadata.profileId

            existing.connection = profile.connection
            existing.metadata = metadata
            existing.deleted = False

            synchronized.append(existing)
            updated += 1

            if oldFingerprint != profileConnectionFingerprint(existing):
                changedProfileIds.append(metadata.profileId)

        removedProfiles = tuple(existingByKey.values())

        for profile in removedProfiles:
            profile.deleted = True

        unmanagedOrOther = [
            profile
            for profile in profiles
            if not (
                profile.itemSubscription == groupId and profile.itemSubscriptionManaged
            )
        ]
        profiles[:] = (
            unmanagedOrOther[:insertionIndex]
            + synchronized
            + unmanagedOrOther[insertionIndex:]
        )

        for index, profile in enumerate(profiles):
            profile.index = index
            profile.deleted = False

        return SubscriptionSyncResult(
            groupId=groupId,
            added=added,
            updated=updated,
            removed=len(removedProfiles),
            profileIds=tuple(profile.metadata.profileId for profile in synchronized),
            removedProfileIds=tuple(
                profile.metadata.profileId for profile in removedProfiles
            ),
            changedProfileIds=tuple(changedProfileIds),
        )
