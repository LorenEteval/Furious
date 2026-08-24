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
from Furious.Models.Encoding import *

import logging

__all__ = ['UserRoutings']

logger = logging.getLogger(__name__)

registerAppSettings('CustomRouting')


class UserRoutings(Mixins.CleanupOnExit, StorageBackend):
    """Manage the persisted custom-routing collection."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserRoutings."""
        super().__init__(*args, **kwargs)

        self._restoreFailed = False

        def restore():
            """Restore the user routings."""
            raw = AppSettings.get('CustomRouting')

            if raw is None:
                return {}

            try:
                data = UJSONEncoder.decode(PyBase64Encoder.decode(raw))

                if isinstance(data, dict):
                    return data

                raise TypeError('routing repository root must be an object')
            except Exception:
                self._restoreFailed = True
                logger.exception('failed to restore persisted routings')

            return {}

        self._data = restore()

    def sync(self):
        """Persist the current user routings data."""
        AppSettings.set(
            'CustomRouting',
            PyBase64Encoder.encode(UJSONEncoder.encode(self._data).encode()),
        )
        self._restoreFailed = False

    def data(self) -> dict[str, dict]:
        """Return the live mutable collection managed by this repository."""
        return self._data

    def cleanup(self):
        """Release resources owned by the user routings."""
        if self._restoreFailed and not self._data:
            logger.warning('preserving unreadable persisted routings during cleanup')

            return

        self.sync()
