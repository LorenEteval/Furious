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

"""Persist subscription definitions."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models.Encoding import *

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import logging

__all__ = ['SubscriptionGroup', 'UserSubs']

logger = logging.getLogger(__name__)

registerAppSettings('CustomSubscription')


@dataclass
class SubscriptionGroup:
    """Describe a subscription source and the profiles that it owns."""

    remark: str = ''
    webURL: str = ''
    enabled: bool = True
    autoupdate: str = ''
    proxy: str = ''
    userAgent: str = ''
    filter: str = ''
    lastUpdated: str = ''
    id: str = ''
    sortOrder: int = 0
    lastDecoderId: str = ''
    lastSyncStatus: str = ''
    lastSyncError: str = ''
    profileCount: int = 0
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def fromMapping(cls, unique: str, value: Mapping[str, Any] | None = None):
        """Restore a group while preserving fields from newer installations."""
        data = dict(value or {})
        nestedExtras = data.pop('extras', {})
        known = {
            name: data.pop(name, default)
            for name, default in (
                ('remark', ''),
                ('webURL', ''),
                ('enabled', True),
                ('autoupdate', ''),
                ('proxy', ''),
                ('userAgent', ''),
                ('filter', ''),
                ('lastUpdated', ''),
                ('sortOrder', 0),
                ('lastDecoderId', data.pop('decoderId', '')),
                ('lastSyncStatus', ''),
                ('lastSyncError', ''),
                ('profileCount', 0),
            )
        }

        for name in (
            'remark',
            'webURL',
            'autoupdate',
            'proxy',
            'userAgent',
            'filter',
            'lastUpdated',
            'lastDecoderId',
            'lastSyncStatus',
            'lastSyncError',
        ):
            known[name] = str(known[name] or '')

        if isinstance(known['enabled'], str):
            known['enabled'] = known['enabled'].strip().casefold() in (
                '1',
                'true',
                'yes',
                'on',
            )
        else:
            known['enabled'] = bool(known['enabled'])

        for name in ('sortOrder', 'profileCount'):
            try:
                known[name] = max(0, int(known[name]))
            except (TypeError, ValueError):
                known[name] = 0

        extras = dict(nestedExtras) if isinstance(nestedExtras, Mapping) else {}
        extras.update(data)

        return cls(id=str(unique), **known, extras=extras)

    def toMapping(self) -> dict[str, Any]:
        """Return the backward-compatible persisted group mapping."""
        result = dict(self.extras)
        result.update(
            {
                'remark': self.remark,
                'webURL': self.webURL,
                'enabled': self.enabled,
                'autoupdate': self.autoupdate,
                'proxy': self.proxy,
                'userAgent': self.userAgent,
                'filter': self.filter,
                'lastUpdated': self.lastUpdated,
                'sortOrder': self.sortOrder,
                'lastDecoderId': self.lastDecoderId,
                'lastSyncStatus': self.lastSyncStatus,
                'lastSyncError': self.lastSyncError,
                'profileCount': self.profileCount,
            }
        )

        return result


class UserSubs(Mixins.CleanupOnExit, StorageBackend):
    # unique: { remark, webURL }
    """Manage the persisted subscription collection."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserSubs."""
        super().__init__(*args, **kwargs)

        self._restoreFailed = False

        def restore():
            """Restore the user subs."""
            raw = AppSettings.get('CustomSubscription')

            if raw is None:
                return {}

            try:
                data = UJSONEncoder.decode(PyBase64Encoder.decode(raw))

                if isinstance(data, dict):
                    return data

                raise TypeError('subscription repository root must be an object')
            except Exception:
                self._restoreFailed = True
                logger.exception('failed to restore persisted subscriptions')

                return {}

        restored = restore()

        self._data = restored

        # Normalize legacy URL-only entries into the current group schema. The
        # dictionary key remains the stable group ID used by existing profiles.
        for order, (unique, value) in enumerate(tuple(self._data.items())):
            group = SubscriptionGroup.fromMapping(unique, value)

            if not group.sortOrder:
                group.sortOrder = order

            self._data[unique] = group.toMapping()

    def sync(self):
        """Persist the current user subs data."""
        AppSettings.set(
            'CustomSubscription',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(self._data).encode(),
            ),
        )
        self._restoreFailed = False

    def data(self) -> dict[str, dict]:
        """Return the live mutable collection managed by this repository."""
        return self._data

    def groups(self) -> tuple[SubscriptionGroup, ...]:
        """Return subscription groups ordered independently from table rows."""
        return tuple(
            sorted(
                (
                    SubscriptionGroup.fromMapping(unique, value)
                    for unique, value in self._data.items()
                ),
                key=lambda group: (group.sortOrder, group.remark.casefold(), group.id),
            )
        )

    def group(self, unique: str) -> SubscriptionGroup | None:
        """Return one group by stable ID."""
        value = self._data.get(unique)

        return (
            SubscriptionGroup.fromMapping(unique, value)
            if isinstance(value, Mapping)
            else None
        )

    def upsertGroup(self, group: SubscriptionGroup):
        """Insert or replace one group without changing its identity."""
        if not group.id:
            raise ValueError('subscription group ID must not be empty')

        self._data[group.id] = group.toMapping()

    def removeGroup(self, unique: str) -> SubscriptionGroup | None:
        """Remove and return one group definition."""
        value = self._data.pop(unique, None)

        return (
            SubscriptionGroup.fromMapping(unique, value)
            if isinstance(value, Mapping)
            else None
        )

    def cleanup(self):
        """Release resources owned by the user subs."""
        if self._restoreFailed and not self._data:
            logger.warning(
                'preserving unreadable persisted subscriptions during cleanup'
            )

            return

        self.sync()
