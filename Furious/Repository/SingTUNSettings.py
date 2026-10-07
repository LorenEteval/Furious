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

"""Persist sing-tun's independent native and host configuration."""

from __future__ import annotations

from Furious.Frozenlib import AppSettings, Mixins, registerAppSettings
from Furious.Interface import StorageBackend
from Furious.Models.Encoding import PyBase64Encoder, UJSONEncoder

import logging

__all__ = ['UserSingTUNSettings']

logger = logging.getLogger(__name__)

# Keep sing-tun customizations independent of the legacy CustomTUNSettings.
# 0.8.2 ignores this key and preserves it during ordinary settings writes;
# an explicit settings reset clears both engines' customizations.
registerAppSettings('CustomSingTUNSettings')


class UserSingTUNSettings(Mixins.CleanupOnExit, StorageBackend):
    """Own only the sing-tun document, including its host options."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._restoreFailed = False

        raw = AppSettings.get('CustomSingTUNSettings')

        self._data = {}

        if raw is None:
            return

        try:
            data = UJSONEncoder.decode(PyBase64Encoder.decode(raw))

            if not isinstance(data, dict):
                raise TypeError('sing-tun settings repository root must be an object')

            self._data = data
        except Exception:
            # Any non-exit exceptions

            self._restoreFailed = True

            logger.exception('failed to restore persisted sing-tun settings')

    def data(self) -> dict:
        return self._data

    def sync(self):
        AppSettings.set(
            'CustomSingTUNSettings',
            PyBase64Encoder.encode(UJSONEncoder.encode(self._data).encode()),
        )

        self._restoreFailed = False

    def cleanup(self):
        if self._restoreFailed and not self._data:
            logger.warning('preserving unreadable sing-tun settings during cleanup')

            return

        self.sync()
