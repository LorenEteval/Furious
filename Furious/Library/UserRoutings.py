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

"""Persist custom routing definitions."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library.Encoder import *

__all__ = ['UserRoutings']

registerAppSettings('CustomRouting')


class UserRoutings(Mixins.CleanupOnExit, StorageFactory):
    """Manage the persisted custom-routing collection."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserRoutings."""
        super().__init__(*args, **kwargs)

        def restore():
            """Restore the user routings."""
            try:
                data = UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('CustomRouting'))
                )

                if isinstance(data, dict):
                    return data
            except Exception:
                # Any non-exit exceptions

                pass

            return {}

        self._data = restore()

    def sync(self):
        """Persist the current user routings data."""
        AppSettings.set(
            'CustomRouting',
            PyBase64Encoder.encode(UJSONEncoder.encode(self._data).encode()),
        )

    def data(self) -> dict[str, dict]:
        # Shallow copy
        """Return the data managed by the user routings."""
        return self._data

    def cleanup(self):
        """Release resources owned by the user routings."""
        self.sync()
