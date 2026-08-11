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

from dataclasses import dataclass

__all__ = ['UserSubs']

registerAppSettings('CustomSubscription')


@dataclass
class UserSubEntry:
    """Describe one user sub entry."""

    remark: str = ''
    webURL: str = ''
    enabled: bool = True
    autoupdate: str = ''
    proxy: str = ''
    userAgent: str = ''
    filter: str = ''
    lastUpdated: str = ''


class UserSub:
    """Represent user sub."""

    unique: dict[str, dict]


class UserSubs(Mixins.CleanupOnExit, StorageBackend):
    # unique: { remark, webURL }
    """Manage the persisted subscription collection."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserSubs."""
        super().__init__(*args, **kwargs)

        def restore():
            """Restore the user subs."""
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('CustomSubscription'))
                )
            except Exception:
                # Any non-exit exceptions

                return {}

        self._data = restore()

    def sync(self):
        """Persist the current user subs data."""
        AppSettings.set(
            'CustomSubscription',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(self._data).encode(),
            ),
        )

    def data(self) -> dict[str, dict]:
        # Shallow copy
        """Return the data managed by the user subs."""
        return self._data

    def cleanup(self):
        """Release resources owned by the user subs."""
        self.sync()
