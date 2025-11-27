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

__all__ = ['Hysteria1']


def startHysteria1(jsonString, rule, mmdb, msgQueue: multiprocessing.Queue):
    try:
        import hysteria
    except ImportError:
        # Fake running process
        while True:
            time.sleep(3600)
    else:
        if versionToValue(hysteria.__version__) <= versionToValue('1.3.5'):
            redirect = False
        else:
            redirect = True

        ProcessOutputRedirector.launch(
            msgQueue,
            functools.partial(hysteria.startFromJSON, jsonString, rule, mmdb),
            redirect,
        )


class Hysteria1(CoreProcessWorker):
    class ExitCode(Enum):
        ConfigurationError = 23
        RemoteNetworkError = 3
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def rule(rulePath):
        if isinstance(rulePath, str) and rulePath == '':
            return ''

        try:
            path = absolutePath(str(rulePath))
        except Exception:
            # Any non-exit exceptions

            logger.error('invalid hysteria1 rule path. Fall back to empty')

            return ''

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria1 rule \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'hysteria1 rule \'{path}\' load failed. {ex}. Fall back to empty'
            )

            return ''

    @staticmethod
    def mmdb(mmdbPath):
        if isinstance(mmdbPath, str) and mmdbPath == '':
            return ''

        try:
            path = absolutePath(str(mmdbPath))
        except Exception:
            # Any non-exit exceptions

            logger.error('invalid hysteria1 mmdb path. Fall back to empty')

            return ''

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria1 mmdb \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'hysteria1 mmdb \'{path}\' load failed. {ex}. Fall back to empty'
            )

            return ''

    @staticmethod
    def name() -> str:
        return 'Hysteria1'

    @staticmethod
    def version() -> str:
        try:
            import hysteria

            return hysteria.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, config: Union[str, dict], rule, mmdb, **kwargs) -> bool:
        param = self.toJSONString(config)

        if param:
            return super().start(
                target=startHysteria1,
                args=(
                    param,
                    rule,
                    mmdb,
                    self.msgQueue,
                ),
                **kwargs,
            )
        else:
            return False
