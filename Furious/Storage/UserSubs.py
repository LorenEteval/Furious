# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from __future__ import annotations

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.Utility import *
from Furious.Library import *

__all__ = ['UserSubs']

registerAppSettings('CustomSubscription')


class UserSubs(SupportExitCleanup, StorageFactory):
    # unique: remark, webURL
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def restore():
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('CustomSubscription'))
                )
            except Exception:
                # Any non-exit exceptions

                return {}

        self._data = restore()

    def sync(self):
        AppSettings.set(
            'CustomSubscription',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(self._data).encode(),
            ),
        )

    def data(self) -> dict[str, dict]:
        # Shallow copy
        return self._data

    def cleanup(self):
        self.sync()
