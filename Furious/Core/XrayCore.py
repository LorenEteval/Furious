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
from Furious.Interface import *
from Furious.Library import *
from Furious.Utility import *
from Furious.Core.CoreProcessWorker import *

from enum import Enum
from typing import Union

import io
import time
import threading
import functools
import multiprocessing

__all__ = ['XrayCore']


def startXrayCore(jsonString: str, msgQueue: multiprocessing.Queue):
    try:
        import xray
    except ImportError:
        # Fake running process
        while True:
            time.sleep(3600)
    else:
        if versionToValue(xray.__version__) <= versionToValue('1.8.4'):
            redirect = False
        else:
            # Can be redirected
            redirect = True

        if not SystemRuntime.isPythonw():
            return ProcessOutputRedirector.launch(
                msgQueue,
                functools.partial(xray.startFromJSON, jsonString),
                redirect,
            )

        if not redirect:
            return xray.startFromJSON(jsonString)

        try:
            jsonObject = UJSONEncoder.decode(jsonString)
        except Exception:
            # Any non-exit exceptions

            xray.startFromJSON(jsonString)
        else:
            loggingPath = list()
            fileStreams = list()

            for loggingAttr in ['access', 'error']:
                try:
                    path = jsonObject['log'][loggingAttr]
                except Exception:
                    # Any non-exit exceptions

                    continue

                if path not in loggingPath:
                    loggingPath.append(path)

                    try:
                        stream = open(path, 'rb')
                    except Exception:
                        # Any non-exit exceptions

                        pass
                    else:
                        stream.seek(0, io.SEEK_END)

                        fileStreams.append(stream)

            def produceMsg():
                while True:
                    for file in fileStreams:
                        for line in iter(file.readline, b''):
                            if line and not line.isspace():
                                try:
                                    msgQueue.put_nowait(line.decode('utf-8', 'replace'))
                                except Exception:
                                    # Any non-exit exceptions

                                    pass

                    time.sleep(MsgQueue.MSG_PRODUCE_THRESHOLD / 1000)

            try:
                if fileStreams:
                    msgThread = threading.Thread(target=produceMsg, daemon=True)
                    msgThread.start()

                xray.startFromJSON(jsonString)
            finally:
                for stream in fileStreams:
                    stream.close()


class XrayCore(CoreProcessWorker):
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
        return 'Xray-core'

    @staticmethod
    def version() -> str:
        try:
            import xray

            return xray.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, config: Union[str, ConfigFactory, dict], **kwargs) -> bool:
        param = self.toJSONString(config)

        if param:
            return super().start(
                target=startXrayCore,
                args=(
                    param,
                    self.msgQueue,
                ),
                **kwargs,
            )
        else:
            return False
