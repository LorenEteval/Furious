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

__all__ = ['Hysteria1']


def startHysteria1(jsonString, rule, mmdb, msgQueue: multiprocessing.Queue):
    try:
        import hysteria
    except ImportError:
        # Fake running process
        while True:
            time.sleep(1)
    else:
        if versionToValue(hysteria.__version__) <= versionToValue('1.3.5'):
            redirect = False
        else:
            redirect = True

        StdoutRedirectHelper.launch(
            msgQueue, lambda: hysteria.startFromJSON(jsonString, rule, mmdb), redirect
        )


class Hysteria1(CoreProcess):
    class ExitCode:
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
            path = getAbsolutePath(str(rulePath))
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
            path = getAbsolutePath(str(mmdbPath))
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

    def startFromArgs(self, jsonString: str, rule, mmdb, **kwargs) -> bool:
        self.registerCurrentJSONConfig(jsonString)

        return super().start(
            target=startHysteria1,
            args=(jsonString, rule, mmdb, self.msgQueue),
            **kwargs,
        )

    def start(self, config: Union[str, dict], rule, mmdb, **kwargs) -> bool:
        if isinstance(config, str):
            return self.startFromArgs(config, rule, mmdb, **kwargs)
        elif isinstance(config, ConfigurationFactory):
            return self.startFromArgs(config.toJSONString(), rule, mmdb, **kwargs)
        elif isinstance(config, dict):
            try:
                jsonString = UJSONEncoder.encode(config)
            except Exception:
                # Any non-exit exceptions

                return False
            else:
                return self.startFromArgs(jsonString, rule, mmdb, **kwargs)
        else:
            return False
