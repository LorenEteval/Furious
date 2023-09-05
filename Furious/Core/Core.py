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

from Furious.Utility.Constants import PLATFORM
from Furious.Utility.Utility import getAbsolutePath

from PySide6 import QtCore
from PySide6.QtTest import QTest

import logging
import multiprocessing

logger = logging.getLogger(__name__)


class Core:
    def __init__(self, *args, exitCallback=None, **kwargs):
        super().__init__(*args, **kwargs)

        self._process = None
        self._exitCallback = exitCallback

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

    def checkAlive(self):
        assert isinstance(self._process, multiprocessing.Process)

        if self._process.is_alive():
            return True
        else:
            logger.error(
                f'{self.name()} stopped unexpectedly with exitcode {self._process.exitcode}'
            )

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
            self._daemonTimer.start(1)

    def stop(self):
        if (
            isinstance(self._process, multiprocessing.Process)
            and self._process.is_alive()
        ):
            self._daemonTimer.stop()

            self._process.terminate()
            self._process.join()

            logger.info(
                f'{self.name()} terminated with exitcode {self._process.exitcode}'
            )


def startXrayCore(json):
    try:
        import xray
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        xray.startFromJSON(json)


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
    def version():
        try:
            import xray

            return xray.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, json, **kwargs):
        super().start(target=startXrayCore, args=(json,), **kwargs)


def startHysteria(json, rule, mmdb):
    try:
        import hysteria
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        hysteria.startFromJSON(json, rule, mmdb)


class Hysteria(Core):
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

            logger.info(f'hysteria rule \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'hysteria rule \'{path}\' load failed. {ex}')

            return ''

    @staticmethod
    def mmdb(mmdbPath):
        path = getAbsolutePath(str(mmdbPath))

        try:
            with open(path, 'rb') as file:
                data = file.read()

            logger.info(f'hysteria mmdb \'{path}\' load success')

            return data
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'hysteria mmdb \'{path}\' load failed. {ex}')

            return ''

    @staticmethod
    def name():
        return 'Hysteria'

    @staticmethod
    def version():
        try:
            import hysteria

            return hysteria.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, json, rule, mmdb, **kwargs):
        super().start(target=startHysteria, args=(json, rule, mmdb), **kwargs)
