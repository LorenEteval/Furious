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
    def loadOptionalFile(pathLike, fileType: str):
        if isinstance(pathLike, str) and pathLike == '':
            return ''

        try:
            path = absolutePath(str(pathLike))
        except Exception:
            # Any non-exit exceptions

            logger.error(f'invalid hysteria1 {fileType} path. Fall back to empty')

            return ''

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria1 {fileType} \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'hysteria1 {fileType} \'{path}\' load failed. {ex}. '
                f'Fall back to empty'
            )

            return ''

    @staticmethod
    def rule(rulePath):
        return Hysteria1.loadOptionalFile(rulePath, 'rule')

    @staticmethod
    def mmdb(mmdbPath):
        return Hysteria1.loadOptionalFile(mmdbPath, 'mmdb')

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

    def launchSpec(
        self, config: Union[str, dict], rule, mmdb, **kwargs
    ) -> Union[CoreLaunchSpec, None]:
        param = self.toJSONString(config)

        if not param:
            return None

        return CoreLaunchSpec(
            target=startHysteria1,
            args=(
                param,
                rule,
                mmdb,
                self.msgQueue,
            ),
            processKwargs=kwargs,
        )

    def start(self, config: Union[str, dict], rule, mmdb, **kwargs) -> bool:
        launchSpec = self.launchSpec(config, rule, mmdb, **kwargs)

        if launchSpec is None:
            return False

        return self.startWithSpec(launchSpec)
