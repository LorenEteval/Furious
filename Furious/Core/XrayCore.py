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

import io
import time
import threading
import multiprocessing

__all__ = ['XrayCore']


def startXrayCore(jsonString: str, msgQueue: multiprocessing.Queue):
    try:
        import xray
    except ImportError:
        # Fake running process
        while True:
            time.sleep(1)
    else:
        if versionToValue(xray.__version__) <= versionToValue('1.8.4'):
            redirect = False
        else:
            # Can be redirected
            redirect = True

        if not isPythonw():
            return StdoutRedirectHelper.launch(
                msgQueue, lambda: xray.startFromJSON(jsonString), redirect
            )

        if not redirect:
            return xray.startFromJSON(jsonString)

        def xrayPythonwProduceMsg():
            try:
                jsonObject = UJSONEncoder.decode(jsonString)
            except Exception:
                # Any non-exit exceptions

                xray.startFromJSON(jsonString)
            else:
                loggingPath = []
                fileStreams = []

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
                                        msgQueue.put_nowait(
                                            line.decode('utf-8', 'replace')
                                        )
                                    except Exception:
                                        # Any non-exit exceptions

                                        pass

                        time.sleep(CoreProcess.MSG_PRODUCE_THRESHOLD / 1000)

                try:
                    if fileStreams:
                        msgThread = threading.Thread(target=produceMsg, daemon=True)
                        msgThread.start()

                    xray.startFromJSON(jsonString)
                finally:
                    for stream in fileStreams:
                        stream.close()

        xrayPythonwProduceMsg()


class XrayCore(CoreProcess):
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
        return 'Xray-core'

    @staticmethod
    def version() -> str:
        try:
            import xray

            return xray.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def startFromArgs(self, jsonString: str, **kwargs) -> bool:
        self.registerCurrentJSONConfig(jsonString)

        return super().start(
            target=startXrayCore, args=(jsonString, self.msgQueue), **kwargs
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
