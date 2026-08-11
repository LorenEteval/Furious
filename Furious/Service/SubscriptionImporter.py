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

"""Convert decoded subscription payloads into metadata-separated profiles."""

from __future__ import annotations

from Furious.Models import ServerProfile, profileConnectionFingerprint
from Furious.Plugins import getPluginRegistry, profileFromAny

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Tuple

__all__ = [
    'SubscriptionImportResult',
    'SubscriptionImportService',
    'SubscriptionSource',
]


@dataclass(frozen=True)
class SubscriptionSource:
    """Describe where a subscription payload came from."""

    id: str
    location: str = ''
    displayName: str = ''
    decoderId: Optional[str] = None
    updatedAt: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class SubscriptionImportResult:
    """Return profiles generated from one decoded subscription payload."""

    decoderId: str
    profiles: Tuple[ServerProfile, ...]
    rejectedItems: int = 0


class SubscriptionImportService:
    """Separate payload decoding from protocol profile construction."""

    def __init__(self, registry=None):
        """Use the supplied capability registry or the application registry."""
        self.registry = registry or getPluginRegistry()

    def importPayload(self, data: bytes, source: SubscriptionSource):
        """Decode *data* and construct supported profiles for *source*."""
        result = self.registry.decodeSubscription(data, source.decoderId)

        if result is None:
            return None

        profiles = []
        rejected = 0
        identityOccurrences = {}

        for item in result.items:
            value = item.configuration if item.configuration is not None else item.uri
            metadata = {
                **dict(item.metadata),
                'subscriptionSource': source.id,
                'subscriptionManaged': True,
                'updatedAt': source.updatedAt,
            }

            if item.name:
                metadata['displayName'] = item.name

            profile = profileFromAny(
                value,
                registry=self.registry,
                **metadata,
            )

            baseIdentity = (
                f'upstream:{item.upstreamId}'
                if item.upstreamId
                else f'config:{profileConnectionFingerprint(profile)}'
            )
            occurrence = identityOccurrences.get(baseIdentity, 0)
            identityOccurrences[baseIdentity] = occurrence + 1
            profile.metadata.subscriptionProfileKey = (
                baseIdentity if occurrence == 0 else f'{baseIdentity}#{occurrence + 1}'
            )

            if not self.registry.validateConfig(profile):
                profiles.append(profile)
            else:
                rejected += 1

        return SubscriptionImportResult(result.decoderId, tuple(profiles), rejected)
