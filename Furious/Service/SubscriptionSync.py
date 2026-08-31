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

import copy

from dataclasses import dataclass

__all__ = [
    'SubscriptionSyncPlan',
    'SubscriptionSyncResult',
    'SubscriptionSyncSnapshot',
    'SubscriptionSynchronizer',
]


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


@dataclass(frozen=True)
class SubscriptionSyncSnapshot:
    """Hold copied group profiles and the live source revision they represent."""

    groupId: str
    profiles: tuple[ServerProfile, ...]
    sourceRevision: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class SubscriptionSyncPlan:
    """Describe a worker-prepared replacement for one subscription group."""

    groupId: str
    sourceRevision: tuple[tuple[str, str, str], ...]
    profiles: tuple[ServerProfile, ...]
    result: SubscriptionSyncResult


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
    def _sourceRevision(profiles, groupId: str):
        """Fingerprint the relevant live group state without using row identity."""
        return tuple(
            (
                profile.metadata.profileId,
                profile.metadata.subscriptionProfileKey,
                profileConnectionFingerprint(profile),
            )
            for profile in profiles
            if profile.itemSubscription == groupId and profile.itemSubscriptionManaged
        )

    def snapshot(self, profiles, groupId: str) -> SubscriptionSyncSnapshot:
        """Copy only the live profiles owned by *groupId* for worker preparation."""
        if not groupId:
            raise ValueError('subscription group ID must not be empty')

        owned = tuple(
            copy.deepcopy(profile)
            for profile in profiles
            if profile.itemSubscription == groupId and profile.itemSubscriptionManaged
        )

        return SubscriptionSyncSnapshot(
            groupId,
            owned,
            self._sourceRevision(profiles, groupId),
        )

    def prepare(
        self,
        snapshot: SubscriptionSyncSnapshot,
        incomingProfiles,
    ) -> SubscriptionSyncPlan:
        """Build a reconciliation plan using copied profiles only."""
        working = list(snapshot.profiles)
        result = self.reconcile(working, incomingProfiles, snapshot.groupId)

        return SubscriptionSyncPlan(
            snapshot.groupId,
            snapshot.sourceRevision,
            tuple(working),
            result,
        )

    def commit(self, profiles, plan: SubscriptionSyncPlan) -> SubscriptionSyncResult:
        """Atomically apply a current worker plan while preserving live identities."""
        groupId = plan.groupId

        if self._sourceRevision(profiles, groupId) != plan.sourceRevision:
            raise RuntimeError('subscription profile source changed during preparation')

        managedIndexes = [
            index
            for index, profile in enumerate(profiles)
            if profile.itemSubscription == groupId and profile.itemSubscriptionManaged
        ]
        insertionIndex = min(managedIndexes) if managedIndexes else len(profiles)
        existingById = {
            profiles[index].metadata.profileId: profiles[index]
            for index in managedIndexes
        }
        synchronized = []

        for prepared in plan.profiles:
            existing = existingById.pop(prepared.metadata.profileId, None)

            if existing is None:
                synchronized.append(prepared)

                continue

            metadata = copy.deepcopy(prepared.metadata)

            for fieldName in self.LocalMetadataFields:
                setattr(metadata, fieldName, getattr(existing.metadata, fieldName))

            existing.connection = prepared.connection
            existing.metadata = metadata
            synchronized.append(existing)

        for removed in existingById.values():
            removed.deleted = True

        unmanagedOrOther = [
            profile
            for profile in profiles
            if not (
                profile.itemSubscription == groupId and profile.itemSubscriptionManaged
            )
        ]
        finalProfiles = (
            unmanagedOrOther[:insertionIndex]
            + synchronized
            + unmanagedOrOther[insertionIndex:]
        )

        profiles[:] = finalProfiles

        for index, profile in enumerate(finalProfiles):
            profile.index = index
            profile.deleted = False

        return plan.result

    @staticmethod
    def _keyAssignments(profiles: list[ServerProfile], groupId: str):
        """Plan deterministic keys for legacy profiles without mutating them."""
        occurrences = {}
        assignments = []

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
            key = (
                baseIdentity if occurrence == 0 else f'{baseIdentity}#{occurrence + 1}'
            )

            assignments.append((profile, key))

        return assignments

    @classmethod
    def _ensureKeys(cls, profiles: list[ServerProfile], groupId: str):
        """Migrate legacy group profiles to deterministic occurrence keys."""
        for profile, key in cls._keyAssignments(profiles, groupId):
            profile.metadata.subscriptionProfileKey = key

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

        legacyKeyAssignments = self._keyAssignments(profiles, groupId)
        legacyKeys = {id(profile): key for profile, key in legacyKeyAssignments}

        managedIndexes = [
            index
            for index, profile in enumerate(profiles)
            if profile.itemSubscription == groupId and profile.itemSubscriptionManaged
        ]
        insertionIndex = min(managedIndexes) if managedIndexes else len(profiles)
        existingByKey = {
            legacyKeys.get(
                id(profiles[index]),
                profiles[index].metadata.subscriptionProfileKey,
            ): profiles[index]
            for index in managedIndexes
        }
        synchronized = []
        incomingMetadata = []
        existingUpdates = []
        updated = 0
        added = 0
        changedProfileIds = []

        for profile in incoming:
            metadata = copy.deepcopy(profile.metadata)
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
                incomingMetadata.append((profile, metadata))

                continue

            oldFingerprint = profileConnectionFingerprint(existing)
            newFingerprint = profileConnectionFingerprint(profile)

            for fieldName in self.LocalMetadataFields:
                setattr(metadata, fieldName, getattr(existing.metadata, fieldName))

            metadata.profileId = existing.metadata.profileId

            synchronized.append(existing)
            existingUpdates.append((existing, profile.connection, metadata))
            updated += 1

            if oldFingerprint != newFingerprint:
                changedProfileIds.append(metadata.profileId)

        removedProfiles = tuple(existingByKey.values())

        unmanagedOrOther = [
            profile
            for profile in profiles
            if not (
                profile.itemSubscription == groupId and profile.itemSubscriptionManaged
            )
        ]
        finalProfiles = (
            unmanagedOrOther[:insertionIndex]
            + synchronized
            + unmanagedOrOther[insertionIndex:]
        )

        result = SubscriptionSyncResult(
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

        # Everything above is preparation and may fail.  The assignments below
        # are the commit point and preserve existing profile object identities.
        for profile, key in legacyKeyAssignments:
            profile.metadata.subscriptionProfileKey = key

        for profile, metadata in incomingMetadata:
            profile.metadata = metadata

        for profile, connection, metadata in existingUpdates:
            profile.connection = connection
            profile.metadata = metadata

        for profile in removedProfiles:
            profile.deleted = True

        profiles[:] = finalProfiles

        for index, profile in enumerate(finalProfiles):
            profile.index = index
            profile.deleted = False

        return result
