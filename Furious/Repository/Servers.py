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

"""Persist and reconstruct user server configurations."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import ProfileMetadata, ServerProfile
from Furious.Models.Encoding import *
from Furious.Plugins import configurationFromAny

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from typing import Any

import logging

__all__ = ['UserServer', 'UserServers']

logger = logging.getLogger(__name__)

registerAppSettings('Configuration')


@dataclass
class UserServer:
    """Represent one serialized user-server storage record."""

    remark: str
    config: str
    subsId: str
    profileMetadata: dict[str, Any]
    delayResult: str = ''
    speedResult: str = ''
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def fromProfile(cls, profile: ServerProfile) -> UserServer:
        """Build a storage record from a server profile."""
        metadata = profile.metadata

        return cls(
            remark=metadata.displayName,
            config=profile.connection.toJSONString(),
            subsId=metadata.subscriptionSource,
            profileMetadata=metadata.toMapping(),
            delayResult=metadata.latency,
            speedResult=metadata.speed,
            extras=dict(metadata.extras),
        )

    @staticmethod
    def metadataFromMapping(value: Mapping[str, Any]) -> ProfileMetadata:
        """Restore metadata with legacy fields taking precedence."""
        record = dict(value)
        nested = record.pop('profileMetadata', {})
        metadata = dict(nested) if isinstance(nested, Mapping) else {}
        nestedExtras = metadata.pop('extras', {})
        extras = dict(nestedExtras) if isinstance(nestedExtras, Mapping) else {}
        aliases = {
            'remark': 'displayName',
            'subsId': 'subscriptionSource',
            'delayResult': 'latency',
            'speedResult': 'speed',
        }

        for legacyName, currentName in aliases.items():
            if legacyName in record:
                metadata[currentName] = record.pop(legacyName)

        for metadataField in fields(ProfileMetadata):
            currentName = metadataField.name

            if currentName in record and currentName != 'extras':
                metadata[currentName] = record.pop(currentName)

        extras.update(record)
        metadata['extras'] = extras

        return ProfileMetadata.fromMapping(metadata)

    def toMapping(self) -> dict[str, Any]:
        """Return the backward-compatible JSON storage mapping."""
        result = dict(self.extras)
        result.update(
            {
                'remark': self.remark,
                'config': self.config,
                'subsId': self.subsId,
                'delayResult': self.delayResult,
                'speedResult': self.speedResult,
                'profileMetadata': dict(self.profileMetadata),
            }
        )

        return result


class UserServers(Mixins.CleanupOnExit, StorageBackend):
    """Manage the persisted list of server configurations."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserServers."""
        super().__init__(*args, **kwargs)

        self._restoreFailed = False

        def restore():
            """Restore the user servers."""
            raw = AppSettings.get('Configuration')

            if raw is None:
                return {'model': []}

            try:
                data = UJSONEncoder.decode(PyBase64Encoder.decode(raw))

                if isinstance(data, dict) and isinstance(data.get('model', []), list):
                    return data

                raise TypeError('server repository root must contain a model list')
            except Exception:
                self._restoreFailed = True
                logger.exception('failed to restore persisted server configurations')

                return {'model': []}

        self._data = restore()
        self._list = []

        records = self._data.get('model', [])

        for index, value in enumerate(records):
            record = dict(value)

            if 'connection' in record:
                connection = configurationFromAny(record.get('connection', ''))
                metadata = ProfileMetadata.fromMapping(record.get('metadata', {}))
            else:
                connection = configurationFromAny(record.pop('config', ''))
                metadata = UserServer.metadataFromMapping(record)

            self._list.append(
                ServerProfile.fromConfiguration(
                    connection,
                    metadata,
                    index=index,
                )
            )

    def sync(self):
        """Persist the current user servers data."""
        AppSettings.set(
            'Configuration',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(
                    {
                        'model': [
                            UserServer.fromProfile(profile).toMapping()
                            for profile in self._list
                        ],
                    }
                ).encode()
            ),
        )
        self._restoreFailed = False

    def data(self) -> list[ServerProfile]:
        """Return the live mutable collection managed by this repository."""
        return self._list

    @staticmethod
    def _profileId(profile: ServerProfile) -> str:
        """Return one profile's stable repository identity."""
        return profile.metadata.profileId

    def _replaceVisibleOrder(
        self,
        visibleProfileIds: set[str],
        orderedProfiles: list[ServerProfile],
    ):
        """Replace only visible slots while leaving filtered-out rows fixed."""
        iterator = iter(orderedProfiles)

        for index, profile in enumerate(self._list):
            if self._profileId(profile) in visibleProfileIds:
                self._list[index] = next(iterator)

        for index, profile in enumerate(self._list):
            profile.index = index

    def moveProfiles(
        self,
        profileIds,
        visibleProfileIds,
        position: str,
    ) -> bool:
        """Move selected profiles within the caller's current visible scope."""
        selected = set(profileIds)
        visible = set(visibleProfileIds)
        visibleOrder = [
            profile for profile in self._list if self._profileId(profile) in visible
        ]
        selected.intersection_update(
            self._profileId(profile) for profile in visibleOrder
        )

        if not selected or position not in ('top', 'up', 'down', 'bottom'):
            return False

        originalOrder = list(visibleOrder)

        def isSelected(profile):
            """Return whether the profile belongs to the selected identity set."""
            return self._profileId(profile) in selected

        if position == 'top':
            visibleOrder = [
                profile for profile in visibleOrder if isSelected(profile)
            ] + [profile for profile in visibleOrder if not isSelected(profile)]
        elif position == 'bottom':
            visibleOrder = [
                profile for profile in visibleOrder if not isSelected(profile)
            ] + [profile for profile in visibleOrder if isSelected(profile)]
        elif position == 'up':
            for index in range(1, len(visibleOrder)):
                if isSelected(visibleOrder[index]) and not isSelected(
                    visibleOrder[index - 1]
                ):
                    visibleOrder[index - 1], visibleOrder[index] = (
                        visibleOrder[index],
                        visibleOrder[index - 1],
                    )
        else:
            for index in range(len(visibleOrder) - 2, -1, -1):
                if isSelected(visibleOrder[index]) and not isSelected(
                    visibleOrder[index + 1]
                ):
                    visibleOrder[index], visibleOrder[index + 1] = (
                        visibleOrder[index + 1],
                        visibleOrder[index],
                    )

        if visibleOrder == originalOrder:
            return False

        self._replaceVisibleOrder(visible, visibleOrder)

        return True

    def moveProfilesToSubscription(self, profileIds, unique: str) -> bool:
        """Assign profiles to a group as local entries, preserving sync ownership."""
        selected = set(profileIds)
        changed = False

        for profile in self._list:
            if self._profileId(profile) not in selected:
                continue

            metadata = profile.metadata

            if metadata.subscriptionSource == unique:
                continue

            metadata.subscriptionSource = unique
            metadata.subscriptionManaged = False
            metadata.subscriptionProfileKey = ''

            changed = True

        return changed

    def cleanup(self):
        """Release resources owned by the user servers."""
        if self._restoreFailed and not self._list:
            logger.warning(
                'preserving unreadable persisted server configurations during cleanup'
            )

            return

        self.sync()
