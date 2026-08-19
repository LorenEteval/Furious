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

from Furious.Frozenlib.Constants import PLATFORM
from Furious.Models.Encoding import UJSONEncoder

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Union

import logging
import functools

__all__ = ['CoreProcess', 'RuntimeKernel']

logger = logging.getLogger(__name__)

_INVALID_CONFIGURATION_ERROR = 'Invalid server configuration'


class RuntimeKernel(ABC):
    """Define the lifecycle shared by plugin-created runtime kernels."""

    class ExitCode(Enum):
        """Enumerate process exit codes."""

        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(
        self,
        exitCallback: Union[Callable[[RuntimeKernel, int], None], None] = None,
    ):
        """Initialize the core process."""
        super().__init__()

        self._exitCallback = exitCallback
        self._startError = ''

    def callExitCallback(self, exitcode: int):
        """Call exit callback."""
        if callable(self._exitCallback):
            self._exitCallback(self, exitcode)

    def startError(self) -> str:
        """Return the most recent concise startup failure, if any."""
        return self._startError

    def setStartError(self, message: str):
        """Store a concise user-facing startup failure."""
        self._startError = str(message or '')

    def clearStartError(self):
        """Clear a startup failure before another launch attempt."""
        self._startError = ''

    @functools.singledispatchmethod
    def toJSONString(self, config, **kwargs) -> str:
        """Serialize the configuration as JSON text."""
        self.setStartError(_INVALID_CONFIGURATION_ERROR)

        logger.error(
            f'cannot serialize {type(config).__name__} '
            f'configuration for {self.name()}',
        )

        return ''

    @toJSONString.register(str)
    def _(self, config, **kwargs) -> str:
        """Handle the registered singledispatch variant."""
        if not config:
            self.setStartError(_INVALID_CONFIGURATION_ERROR)

            logger.error(f'cannot start {self.name()} with an empty configuration')

            return ''

        self.clearStartError()

        return config

    @toJSONString.register(dict)
    def _(self, config, **kwargs) -> str:
        """Handle the registered singledispatch variant."""
        serializer = getattr(config, 'toJSONString', None)

        try:
            if callable(serializer):
                result = serializer(**kwargs)
            else:
                result = UJSONEncoder.encode(config, **kwargs)
        except Exception:
            # Any non-exit exceptions
            self.setStartError(_INVALID_CONFIGURATION_ERROR)

            logger.exception(f'failed to serialize configuration for {self.name()}')

            return ''

        if not isinstance(result, str) or not result:
            diagnostic = ''
            serializationError = getattr(config, 'serializationError', None)

            if callable(serializationError):
                diagnostic = str(serializationError() or '')

            self.setStartError(diagnostic or _INVALID_CONFIGURATION_ERROR)

            logger.error(
                f'configuration serializer for {self.name()} returned no JSON'
                + (f': {diagnostic}' if diagnostic else '')
            )

            return ''

        self.clearStartError()

        return result

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
        """Start the runtime kernel."""
        raise NotImplementedError

    @abstractmethod
    def stop(self):
        """Stop the runtime kernel."""
        raise NotImplementedError


# Compatibility name retained for existing process implementations.
CoreProcess = RuntimeKernel
