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

from dataclasses import asdict, dataclass

__all__ = ['UserServer', 'UserServers']

registerAppSettings('Configuration')


@dataclass
class UserServer:
    """Represent one serialized user-server storage record."""

    metadata: dict
    connection: str

    @classmethod
    def fromProfile(cls, profile: ServerProfile):
        """Build a storage record from a server profile."""
        return cls(profile.metadata.toMapping(), profile.connection.toJSONString())

    def toMapping(self) -> dict:
        """Return the record as a JSON-compatible mapping."""
        return asdict(self)


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
        records = self._data.get('profiles', self._data.get('model', []))
        self._list = []

        for index, value in enumerate(records):
            record = dict(value)

            if 'connection' in record:
                connection = configurationFromAny(record.get('connection', ''))
                metadata = ProfileMetadata.fromMapping(record.get('metadata', {}))
            else:
                connection = configurationFromAny(record.pop('config', ''))
                metadata = ProfileMetadata.fromMapping(record)

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
                        'schemaVersion': 2,
                        'profiles': [
                            UserServer.fromProfile(profile).toMapping()
                            for profile in self._list
                        ],
                    }
                ).encode()
            ),
        )

    def data(self) -> list[ServerProfile]:
        # Shallow copy
        """Return the data managed by the user servers."""
        return self._list

    def cleanup(self):
        """Release resources owned by the user servers."""
        self.sync()
