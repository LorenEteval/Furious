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

from Furious.Utility.Constants import PLATFORM

from abc import ABC
from typing import Callable, Union

import ujson

__all__ = ['CoreFactory']


class CoreFactory(ABC):
    class ExitCode:
        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, exitCallback: Callable[[CoreFactory, int], None] = None):
        self._exitCallback = exitCallback
        self._jsonConfig = ''

    def registerExitCallback(
        self, exitCallback: Callable[[CoreFactory, int], None]
    ) -> CoreFactory:
        self._exitCallback = exitCallback

        return self

    def registerCurrentJSONConfig(self, config: Union[str, dict]) -> CoreFactory:
        self._jsonConfig = config

        return self

    @staticmethod
    def name() -> str:
        raise NotImplementedError

    @staticmethod
    def version() -> str:
        raise NotImplementedError

    def jsonConfigString(self) -> str:
        if isinstance(self._jsonConfig, str):
            return self._jsonConfig
        if isinstance(self._jsonConfig, dict):
            try:
                return ujson.dumps(
                    self._jsonConfig,
                    ensure_ascii=False,
                    escape_forward_slashes=False,
                )
            except Exception:
                # Any non-exit exceptions

                return ''

        return ''

    def jsonConfigDict(self) -> dict:
        if isinstance(self._jsonConfig, str):
            try:
                return ujson.loads(self._jsonConfig)
            except Exception:
                # Any non-exit exceptions

                return {}
        if isinstance(self._jsonConfig, dict):
            return self._jsonConfig

        return {}

    def start(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError
