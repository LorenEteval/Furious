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

"""Define the common proxy-core process interface."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface.ConfigFactory import *

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Union

import ujson
import functools

__all__ = ['CoreProcessFactory']


class CoreProcessFactory(ABC):
    """Define the interface and shared behavior for core process objects."""

    class ExitCode(Enum):
        """Enumerate process exit codes."""

        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(
        self,
        exitCallback: Union[Callable[[CoreProcessFactory, int], None], None] = None,
    ):
        """Initialize the CoreProcessFactory."""
        super().__init__()

        self._exitCallback = exitCallback

    def callExitCallback(self, exitcode: int):
        """Call exit callback."""
        if callable(self._exitCallback):
            self._exitCallback(self, exitcode)

    @functools.singledispatchmethod
    def toJSONString(self, config, **kwargs) -> str:
        """Serialize the configuration as JSON text."""
        return ''

    @toJSONString.register(str)
    def _(self, config, **kwargs) -> str:
        """Handle the registered singledispatch variant."""
        return config

    @toJSONString.register(ConfigFactory)
    def _(self, config, **kwargs) -> str:
        """Handle the registered singledispatch variant."""
        return config.toJSONString(**kwargs)

    @toJSONString.register(dict)
    def _(self, config, **kwargs) -> str:
        """Handle the registered singledispatch variant."""
        try:
            ensure_ascii = kwargs.pop('ensure_ascii', False)
            escape_forward_slashes = kwargs.pop('escape_forward_slashes', False)

            return ujson.dumps(
                config,
                ensure_ascii=ensure_ascii,
                escape_forward_slashes=escape_forward_slashes,
                **kwargs,
            )
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    @abstractmethod
    def name() -> str:
        """Return the process implementation name."""
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def version() -> str:
        """Return the bundled core version."""
        raise NotImplementedError

    @abstractmethod
    def start(self, *args, **kwargs) -> bool:
        """Start the core process factory."""
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """Stop the core process factory."""
        raise NotImplementedError
