# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Utility.Constants import APP, PLATFORM, LogType
from Furious.Utility.Utility import getAbsolutePath, isPythonw

from PySide6 import QtCore
from PySide6.QtTest import QTest

import io
import os
import sys
import uuid
import ujson
import logging
import functools
import threading
import multiprocessing

logger = logging.getLogger(__name__)


class Core:
    class ExitCode:
        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, *args, exitCallback=None, **kwargs):
        self._process = None
        self._exitCallback = exitCallback
        self._msgQueue = multiprocessing.Queue()

        @QtCore.Slot()
        def appendCoreLog():
            line = self.getLineNoWait()

            if line and not line.isspace():
                APP().logViewerWidget.appendLog(LogType.Core, line)

        self._stdoutTimer = QtCore.QTimer()
        self._stdoutTimer.timeout.connect(appendCoreLog)

        @QtCore.Slot()
        def timeoutCallback():
            self.checkAlive()

        self._daemonTimer = QtCore.QTimer()
        self._daemonTimer.timeout.connect(timeoutCallback)

    @staticmethod
    def name():
        raise NotImplementedError

    @staticmethod
    def version():
        raise NotImplementedError

    def registerExitCallback(self, exitCallback):
        self._exitCallback = exitCallback

    def isAlive(self):
        if isinstance(self._process, multiprocessing.Process):
            return self._process.is_alive()
        else:
            return False

    def checkAlive(self):
        assert isinstance(self._process, multiprocessing.Process)

        if self._process.is_alive():
            return True
        else:
            logger.error(
                f'{self.name()} stopped unexpectedly with exitcode {self._process.exitcode}'
            )

            self._stdoutTimer.stop()
            self._daemonTimer.stop()

            if callable(self._exitCallback):
                self._exitCallback(self._process.exitcode)

            return False

    def start(self, *args, **kwargs):
        logger.info(f'{self.name()} {self.version()} started')

        waitCore = kwargs.pop('waitCore', True)
        waitTime = kwargs.pop('waitTime', 2000)

        self._process = multiprocessing.Process(**kwargs, daemon=True)
        self._process.start()

        if waitCore:
            # Wait for the core to start up completely
            QTest.qWait(waitTime)

        if self.checkAlive():
            # Start core daemon
            self._stdoutTimer.start()
            self._daemonTimer.start()

    def stop(self):
        if self.isAlive():
            self._stdoutTimer.stop()
            self._daemonTimer.stop()

            self._process.terminate()
            self._process.join()

            logger.info(
                f'{self.name()} terminated with exitcode {self._process.exitcode}'
            )

    def getLineNoWait(self):
        try:
            return self._msgQueue.get_nowait()
        except Exception:
            # Any non-exit exceptions

            return ''


class StdoutRedirectHelper:
    TemporaryDir = QtCore.QTemporaryDir()

    @staticmethod
    def launch(msgQueue, entrypoint, redirect):
        if not callable(entrypoint):
            return

        if (
            not StdoutRedirectHelper.TemporaryDir.isValid()
            or not redirect
            # pythonw.exe
            or isPythonw()
        ):
            # Call entrypoint directly
            entrypoint()

            return

        temporaryFile = StdoutRedirectHelper.TemporaryDir.filePath(str(uuid.uuid4()))
        tmpFileStream = open(temporaryFile, 'w+b')
        stdoutFileno_ = sys.stdout.fileno()
        stderrFileno_ = sys.stderr.fileno()

        sys.stdout.close()
        sys.stderr.close()

        # Redirect
        os.dup2(tmpFileStream.fileno(), stdoutFileno_)
        os.dup2(tmpFileStream.fileno(), stderrFileno_)

        sys.stdout = tmpFileStream
        sys.stderr = tmpFileStream

        def produceMsg():
            with open(temporaryFile, 'rb') as file:
                while True:
                    for line in iter(file.readline, b''):
                        if line and not line.isspace():
                            try:
                                msgQueue.put_nowait(line.decode('utf-8', 'replace'))
                            except Exception:
                                # Any non-exit exceptions

                                pass

        msgThread = threading.Thread(target=produceMsg, daemon=True)
        msgThread.start()

        with tmpFileStream:
            entrypoint()


def startXrayCore(json, msgQueue):
    try:
        import xray
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        if xray.__version__ <= '1.8.4':
            redirect = False
        else:
            redirect = True

        # Can be redirected

        if not isPythonw():
            StdoutRedirectHelper.launch(
                msgQueue, lambda: xray.startFromJSON(json), redirect
            )

            return

        if not redirect:
            xray.startFromJSON(json)

            return

        def xrayPythonwProduceMsg():
            try:
                jsonObject = ujson.loads(json)
            except Exception:
                # Any non-exit exceptions

                xray.startFromJSON(json)

                return

            loggerPath = []
            fileStream = []

            for attr in ['access', 'error']:
                try:
                    path = jsonObject['log'][attr]
                except Exception:
                    # Any non-exit exceptions

                    continue

                if path not in loggerPath:
                    loggerPath.append(path)

                    try:
                        stream = open(path, 'rb')
                    except Exception:
                        # Any non-exit exceptions

                        pass
                    else:
                        stream.seek(0, io.SEEK_END)

                        fileStream.append(stream)

            def produceMsg():
                while True:
                    for file in fileStream:
                        for line in iter(file.readline, b''):
                            if line and not line.isspace():
                                try:
                                    msgQueue.put_nowait(line.decode('utf-8', 'replace'))
                                except Exception:
                                    # Any non-exit exceptions

                                    pass

            try:
                msgThread = threading.Thread(target=produceMsg, daemon=True)
                msgThread.start()

                xray.startFromJSON(json)
            finally:
                for stream in fileStream:
                    stream.close()

        xrayPythonwProduceMsg()


class XrayCore(Core):
    class ExitCode:
        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def name():
        return 'Xray-core'

    @staticmethod
    @functools.lru_cache(None)
    def version():
        try:
            import xray

            return xray.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, json, **kwargs):
        super().start(target=startXrayCore, args=(json, self._msgQueue), **kwargs)


def startHysteria1(json, rule, mmdb, msgQueue):
    try:
        import hysteria
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        if hysteria.__version__ <= '1.3.5':
            redirect = False
        else:
            redirect = True

        StdoutRedirectHelper.launch(
            msgQueue, lambda: hysteria.startFromJSON(json, rule, mmdb), redirect
        )


class Hysteria1(Core):
    class ExitCode:
        ConfigurationError = 23
        RemoteNetworkError = 3
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def rule(rulePath):
        path = getAbsolutePath(str(rulePath))

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria1 rule \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'hysteria1 rule \'{path}\' load failed. {ex}')

            return ''

    @staticmethod
    def mmdb(mmdbPath):
        path = getAbsolutePath(str(mmdbPath))

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria1 mmdb \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'hysteria1 mmdb \'{path}\' load failed. {ex}')

            return ''

    @staticmethod
    def name():
        return 'Hysteria1'

    @staticmethod
    @functools.lru_cache(None)
    def version():
        try:
            import hysteria

            return hysteria.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, json, rule, mmdb, **kwargs):
        super().start(
            target=startHysteria1, args=(json, rule, mmdb, self._msgQueue), **kwargs
        )


def startHysteria2(json, msgQueue):
    try:
        import hysteria2
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        if hysteria2.__version__ <= '2.0.0.1':
            redirect = False
        else:
            redirect = True

        StdoutRedirectHelper.launch(
            msgQueue, lambda: hysteria2.startFromJSON(json), redirect
        )


class Hysteria2(Core):
    class ExitCode:
        ConfigurationError = 23
        # Windows: 4294967295. Darwin, Linux: 255 (-1)
        ServerStartFailure = 4294967295 if PLATFORM == 'Windows' else 255
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def name():
        return 'Hysteria2'

    @staticmethod
    @functools.lru_cache(None)
    def version():
        try:
            import hysteria2

            return hysteria2.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, json, **kwargs):
        super().start(target=startHysteria2, args=(json, self._msgQueue), **kwargs)
