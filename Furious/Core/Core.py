from Furious.Utility.Constants import PLATFORM, ROOT_DIR, DATA_DIR
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

        self._process = multiprocessing.Process(*args, **kwargs, daemon=True)
        self._process.start()

        # Wait for the core to start up completely
        QTest.qWait(2000)

        if self.checkAlive():
            # Start core daemon
            self._daemonTimer.start(100)

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

    def start(self, json):
        super().start(
            target=startXrayCore,
            args=(json,),
        )


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

    def start(self, json, rule, mmdb):
        super().start(
            target=startHysteria,
            args=(json, rule, mmdb),
        )
