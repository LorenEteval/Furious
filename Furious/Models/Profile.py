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
import hashlib
import json
import uuid

from .Configuration import ConfigFactory

__all__ = [
    'ProfileMetadata',
    'ServerProfile',
    'connectionOf',
    'ensureProfile',
    'profileConnectionFingerprint',
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
    profileId: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscriptionManaged: bool = False
    subscriptionProfileKey: str = ''

    @classmethod
    def fromMapping(cls, value: Mapping[str, Any] | None = None, **kwargs):
        """Construct metadata from current or legacy persisted field names."""
        explicit = dict(value or {})
        nestedExtras = explicit.pop('extras', {})
        explicit.update(kwargs)

        data = dict(nestedExtras) if isinstance(nestedExtras, Mapping) else {}
        data.update(explicit)

        for legacyName, currentName in {
            'remark': 'displayName',
            'subsId': 'subscriptionSource',
            'delayResult': 'latency',
            'speedResult': 'speed',
        }.items():
            if currentName not in explicit and legacyName in explicit:
                data[currentName] = explicit[legacyName]
            elif currentName not in data and legacyName in data:
                data[currentName] = data[legacyName]

            data.pop(legacyName, None)

        tags = data.pop('tags', tuple()) or tuple()

        if isinstance(tags, str):
            tags = tuple(value.strip() for value in tags.split(',') if value.strip())
        else:
            tags = tuple(tags)

        favorite = data.pop('favorite', False)

        if isinstance(favorite, str):
            favorite = favorite.strip().casefold() in ('1', 'true', 'yes', 'on')

        subscriptionSource = str(
            data.pop('subscriptionSource', data.pop('subsId', '')) or ''
        )
        subscriptionManaged = data.pop('subscriptionManaged', None)

        if subscriptionManaged is None:
            # Before managed ownership was explicit, a non-empty subsId was
            # written only for profiles imported from that subscription.
            subscriptionManaged = bool(subscriptionSource)
        elif isinstance(subscriptionManaged, str):
            subscriptionManaged = subscriptionManaged.strip().casefold() in (
                '1',
                'true',
                'yes',
                'on',
            )

        subscriptionProfileKey = str(data.pop('subscriptionProfileKey', '') or '')

        known = {
            'profileId': str(data.pop('profileId', '') or uuid.uuid4()),
            'displayName': data.pop('displayName', ''),
            'group': data.pop('group', ''),
            'tags': tags,
            'subscriptionSource': subscriptionSource,
            'subscriptionManaged': bool(subscriptionManaged),
            'subscriptionProfileKey': subscriptionProfileKey,
            'updatedAt': data.pop('updatedAt', ''),
            'annotations': data.pop('annotations', ''),
            'favorite': bool(favorite),
            'latency': data.pop('latency', ''),
            'speed': data.pop('speed', ''),
        }

        return cls(**known, extras=data)

    def toMapping(self) -> dict[str, Any]:
        """Return the normalized persisted metadata mapping."""
        return {
            'profileId': self.profileId,
            'displayName': self.displayName,
            'group': self.group,
            'tags': list(self.tags),
            'subscriptionSource': self.subscriptionSource,
            'subscriptionManaged': self.subscriptionManaged,
            'subscriptionProfileKey': self.subscriptionProfileKey,
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
        elif attribute == 'subscriptionSource':
            self.subscriptionSource = str(value or '')

            if not self.subscriptionSource:
                self.subscriptionManaged = False
                self.subscriptionProfileKey = ''
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

    def independentCopy(self):
        """Return a manual copy with a new identity and no source owner."""
        profile = self.deepcopy()
        profile.metadata.profileId = str(uuid.uuid4())
        profile.metadata.subscriptionSource = ''
        profile.metadata.subscriptionManaged = False
        profile.metadata.subscriptionProfileKey = ''

        return profile

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

    def remoteAddress(self) -> str:
        """Return the connection's operational remote host."""
        return self.connection.remoteAddress()

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
    def itemSubscriptionManaged(self) -> bool:
        """Return whether a subscription synchronizer owns this profile."""
        return self.metadata.subscriptionManaged

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


def profileConnectionFingerprint(value) -> str:
    """Return a deterministic identity for a profile connection document."""
    connection = connectionOf(value)

    try:
        serialized = json.dumps(
            connection,
            allow_nan=False,
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )
    except (TypeError, ValueError) as ex:
        raise TypeError(
            'profile connection must contain deterministic JSON-compatible values'
        ) from ex

    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()
