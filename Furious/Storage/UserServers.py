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

__all__ = ['UserServers']

registerAppSettings('Configuration')


class UserServers(SupportExitCleanup, StorageFactory):
    # remark, config, subsId. (subsId corresponds to unique in user subscription)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def restore():
            try:
                return UJSONEncoder.decode(
                    PyBase64Encoder.decode(AppSettings.get('Configuration'))
                )
            except Exception:
                # Any non-exit exceptions

                return {'model': []}

        self._data = restore()
        self._list = list(
            constructFromAny(model.pop('config', ''), **model)
            for model in self._data['model']
        )

    def sync(self):
        AppSettings.set(
            'Configuration',
            PyBase64Encoder.encode(
                UJSONEncoder.encode(
                    {'model': list(factory.toStorageObject() for factory in self._list)}
                ).encode()
            ),
        )

    def data(self) -> list[ConfigurationFactory]:
        # Shallow copy
        return self._list

    def cleanup(self):
        self.sync()
