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

__all__ = ['UserServer', 'UserServers']

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

        def restore():
            """Restore the user servers."""
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('Configuration'))
                )
            except Exception:
                # Any non-exit exceptions

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

    def data(self) -> list[ServerProfile]:
        """Return the live mutable collection managed by this repository."""
        return self._list

    def cleanup(self):
        """Release resources owned by the user servers."""
        self.sync()
