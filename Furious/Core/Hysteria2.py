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
from Furious.QtFramework import *
from Furious.Library import *
from Furious.Utility import *

from typing import Union

import time
import logging
import multiprocessing

logger = logging.getLogger(__name__)

__all__ = ['Hysteria2']


def startHysteria2(jsonString: str, msgQueue: multiprocessing.Queue):
    try:
        import hysteria2
    except ImportError:
        # Fake running process
        while True:
            time.sleep(1)
    else:
        if versionToValue(hysteria2.__version__) <= versionToValue('2.0.0.1'):
            redirect = False
        else:
            redirect = True

        StdoutRedirectHelper.launch(
            msgQueue, lambda: hysteria2.startFromJSON(jsonString), redirect
        )


class Hysteria2(CoreProcess):
    class ExitCode:
        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def name() -> str:
        return 'Hysteria2'

    @staticmethod
    def version() -> str:
        try:
            import hysteria2

            return hysteria2.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def startFromArgs(self, jsonString: str, **kwargs) -> bool:
        self.registerCurrentJSONConfig(jsonString)

        return super().start(
            target=startHysteria2, args=(jsonString, self.msgQueue), **kwargs
        )

    def start(self, config: Union[str, dict], **kwargs) -> bool:
        if isinstance(config, str):
            return self.startFromArgs(config, **kwargs)
        elif isinstance(config, ConfigurationFactory):
            return self.startFromArgs(config.toJSONString(), **kwargs)
        elif isinstance(config, dict):
            try:
                jsonString = UJSONEncoder.encode(config)
            except Exception:
                # Any non-exit exceptions

                return False
            else:
                return self.startFromArgs(jsonString, **kwargs)
        else:
            return False
