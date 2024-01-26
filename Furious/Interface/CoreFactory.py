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
