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

"""Define server profiles as metadata composed with connection documents."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any

import copy

from .Configuration import ConfigFactory

__all__ = [
    'ProfileMetadata',
    'ServerProfile',
    'connectionOf',
    'ensureProfile',
]


@dataclass
class ProfileMetadata:
    """Store user and subscription metadata outside a connection document."""

    displayName: str = ''
    group: str = ''
    tags: tuple[str, ...] = tuple()
    subscriptionSource: str = ''
    updatedAt: str = ''
    annotations: str = ''
    favorite: bool = False
    latency: str = ''
    speed: str = ''
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fromMapping(cls, value: Mapping[str, Any] | None = None, **kwargs):
        """Construct metadata from current or legacy persisted field names."""
        data = dict(value or {})
        data.update(kwargs)
        nestedExtras = data.pop('extras', {})
        tags = data.pop('tags', tuple()) or tuple()

        if isinstance(tags, str):
            tags = tuple(value.strip() for value in tags.split(',') if value.strip())
        else:
            tags = tuple(tags)

        favorite = data.pop('favorite', False)

        if isinstance(favorite, str):
            favorite = favorite.strip().casefold() in ('1', 'true', 'yes', 'on')

        known = {
            'displayName': data.pop('displayName', data.pop('remark', '')),
            'group': data.pop('group', ''),
            'tags': tags,
            'subscriptionSource': data.pop(
                'subscriptionSource', data.pop('subsId', '')
            ),
            'updatedAt': data.pop('updatedAt', ''),
            'annotations': data.pop('annotations', ''),
            'favorite': bool(favorite),
            'latency': data.pop('latency', data.pop('delayResult', '')),
            'speed': data.pop('speed', data.pop('speedResult', '')),
        }
        extras = dict(nestedExtras) if isinstance(nestedExtras, Mapping) else {}
        extras.update(data)

        return cls(**known, extras=extras)

    def toMapping(self) -> dict[str, Any]:
        """Return the normalized persisted metadata mapping."""
        return {
            'displayName': self.displayName,
            'group': self.group,
            'tags': list(self.tags),
            'subscriptionSource': self.subscriptionSource,
            'updatedAt': self.updatedAt,
            'annotations': self.annotations,
            'favorite': self.favorite,
            'latency': self.latency,
            'speed': self.speed,
            'extras': dict(self.extras),
        }

    def set(self, name: str, value):
        """Set a current or legacy metadata field."""
        aliases = {
            'remark': 'displayName',
            'subsId': 'subscriptionSource',
            'delayResult': 'latency',
            'speedResult': 'speed',
        }
        attribute = aliases.get(name, name)

        if attribute == 'tags':
            self.tags = (
                tuple(item.strip() for item in value.split(',') if item.strip())
                if isinstance(value, str)
                else tuple(value or tuple())
            )
        elif attribute == 'favorite' and isinstance(value, str):
            self.favorite = value.strip().casefold() in ('1', 'true', 'yes', 'on')
        elif attribute in self.__dataclass_fields__ and attribute != 'extras':
            setattr(self, attribute, value)
        else:
            self.extras[name] = value


@dataclass
class ServerProfile(MutableMapping[str, Any]):
    """Compose profile metadata with a core-neutral connection document."""

    connection: ConfigFactory
    metadata: ProfileMetadata = field(default_factory=ProfileMetadata)
    index: int = 0
    deleted: bool = False

    @classmethod
    def fromConfiguration(
        cls,
        configuration: ConfigFactory,
        metadata: ProfileMetadata | Mapping[str, Any] | None = None,
        *,
        index: int = 0,
        deleted: bool = False,
    ):
        """Move transient parser metadata into a separate profile object."""
        if isinstance(configuration, ServerProfile):
            return configuration

        if not isinstance(configuration, ConfigFactory):
            raise TypeError('profile connection must be a ConfigFactory')

        if isinstance(metadata, ProfileMetadata):
            profileMetadata = copy.deepcopy(metadata)
        else:
            profileMetadata = ProfileMetadata.fromMapping(metadata)

        connection = configuration.deepcopy()

        return cls(connection, profileMetadata, index, deleted)

    def __getitem__(self, key: str):
        """Return a connection-document value."""
        return self.connection[key]

    def __setitem__(self, key: str, value):
        """Set a connection-document value."""
        self.connection[key] = value

    def __delitem__(self, key: str):
        """Delete a connection-document value."""
        del self.connection[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over connection-document keys."""
        return iter(self.connection)

    def __len__(self) -> int:
        """Return the connection-document size."""
        return len(self.connection)

    def deepcopy(self):
        """Return an independent profile copy."""
        return copy.deepcopy(self)

    def replaceConnection(self, connection: ConfigFactory):
        """Return this profile's metadata composed with a new connection."""
        return ServerProfile.fromConfiguration(
            connection,
            self.metadata,
            index=self.index,
            deleted=self.deleted,
        )

    def coreName(self) -> str:
        """Return the runtime implementation name."""
        return self.connection.coreName()

    def isValid(self) -> bool:
        """Return whether the connection document is valid."""
        return self.connection.isValid()

    def toJSONString(self, **kwargs) -> str:
        """Serialize only the connection document as JSON."""
        return self.connection.toJSONString(**kwargs)

    def toURI(self, remark: str = '') -> str:
        """Serialize the connection document as a share URI."""
        return self.connection.toURI(remark or self.metadata.displayName)

    def httpProxy(self) -> str:
        """Return the connection's HTTP proxy endpoint."""
        return self.connection.httpProxy()

    def socksProxy(self) -> str:
        """Return the connection's SOCKS proxy endpoint."""
        return self.connection.socksProxy()

    def setHttpProxy(self, endpoint: str) -> bool:
        """Set the connection's HTTP proxy endpoint."""
        return self.connection.setHttpProxy(endpoint)

    def setSocksProxy(self, endpoint: str) -> bool:
        """Set the connection's SOCKS proxy endpoint."""
        return self.connection.setSocksProxy(endpoint)

    @property
    def itemRemark(self) -> str:
        """Return the profile display name."""
        return self.metadata.displayName

    @property
    def itemProtocol(self) -> str:
        """Return the connection protocol display value."""
        return str(getattr(self.connection, 'itemProtocol', ''))

    @property
    def itemAddress(self) -> str:
        """Return the connection address display value."""
        return str(getattr(self.connection, 'itemAddress', ''))

    @property
    def itemPort(self) -> str:
        """Return the connection port display value."""
        return str(getattr(self.connection, 'itemPort', ''))

    @property
    def itemTransport(self) -> str:
        """Return the connection transport display value."""
        return str(getattr(self.connection, 'itemTransport', ''))

    @property
    def itemTLS(self) -> str:
        """Return the connection TLS display value."""
        return str(getattr(self.connection, 'itemTLS', ''))

    @property
    def itemSubscription(self) -> str:
        """Return the subscription source identifier."""
        return self.metadata.subscriptionSource

    @property
    def itemLatency(self) -> str:
        """Return the last latency result."""
        return self.metadata.latency

    @property
    def itemSpeed(self) -> str:
        """Return the last speed result."""
        return self.metadata.speed


def connectionOf(value):
    """Return a server profile's connection document or *value* itself."""
    return value.connection if isinstance(value, ServerProfile) else value


def ensureProfile(value, **metadata) -> ServerProfile:
    """Return *value* as a profile, merging optional metadata fields."""
    if isinstance(value, ServerProfile):
        for name, item in metadata.items():
            value.metadata.set(name, item)

        return value

    return ServerProfile.fromConfiguration(value, metadata)
