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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Core.CoreProcessWorker import *

from enum import Enum
from typing import Union

import time
import logging
import functools
import multiprocessing

logger = logging.getLogger(__name__)

__all__ = ['Hysteria2']


def startHysteria2(jsonString: str, msgQueue: multiprocessing.Queue):
    try:
        import hysteria2
    except ImportError:
        # Fake running process
        while True:
            time.sleep(3600)
    else:
        if versionToValue(hysteria2.__version__) <= versionToValue('2.0.0.1'):
            redirect = False
        else:
            redirect = True

        ProcessOutputRedirector.launch(
            msgQueue,
            functools.partial(hysteria2.startFromJSON, jsonString),
            redirect,
        )


class Hysteria2(CoreProcessWorker):
    class ExitCode(Enum):
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

    def start(self, config: Union[str, dict], **kwargs) -> bool:
        param = self.toJSONString(config)

        if param:
            return super().start(
                target=startHysteria2,
                args=(
                    param,
                    self.msgQueue,
                ),
                **kwargs,
            )
        else:
            return False
