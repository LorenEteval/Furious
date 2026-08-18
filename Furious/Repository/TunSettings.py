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

"""Persist user-defined TUN settings."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models.Encoding import *

__all__ = ['UserTUNSettings']

registerAppSettings('CustomTUNSettings')


class UserTUNSettings(Mixins.CleanupOnExit, StorageBackend):
    """Manage persisted TUN customization values."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserTUNSettings."""
        super().__init__(*args, **kwargs)

        def restore():
            """Restore the user TUN settings."""
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('CustomTUNSettings'))
                )
            except Exception:
                # Any non-exit exceptions

                return {}

        self._data = restore()

    def sync(self):
        """Persist the current user TUN settings data."""
        AppSettings.set(
            'CustomTUNSettings',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(self._data).encode(),
            ),
        )

    def data(self) -> dict[str, str]:
        """Return the live mutable collection managed by this repository."""
        return self._data

    def cleanup(self):
        """Release resources owned by the user TUN settings."""
        self.sync()
