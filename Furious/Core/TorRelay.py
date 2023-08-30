from Furious.Core.Core import Core
from Furious.Utility.Constants import (
    APP,
    DATA_DIR,
    DEFAULT_TOR_SOCKS_PORT,
    DEFAULT_TOR_HTTPS_PORT,
)
from Furious.Utility.Utility import AsyncSubprocessMessage

from PySide6 import QtCore

import re
import signal
import logging
import threading
import subprocess

logger = logging.getLogger(__name__)


class TorRelayStarter(AsyncSubprocessMessage):
    BOOTSTRAP_STATUS = re.compile('Bootstrapped ([0-9]+)%')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.connectTimeoutCallback(self.processLine)

        self.torRelay = None

        self.bootstrapPercentage = 0

    @property
    def torRelayStorageObj(self):
        # Handy reference
        return APP().torRelaySettingsWidget.StorageObj

    def launch(self, proxyServer):
        self.torRelay = subprocess.Popen(
            ['tor', '-f', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        torConfig = (
            f'SocksPort {self.torRelayStorageObj.get("socksTunnelPort", DEFAULT_TOR_SOCKS_PORT)}\n'
            f'HTTPTunnelPort {self.torRelayStorageObj.get("httpsTunnelPort", DEFAULT_TOR_HTTPS_PORT)}\n'
            f'Log {self.torRelayStorageObj.get("logLevel", "notice")} stdout\n'
            f'DataDirectory {DATA_DIR / "tordata"}\n'
        )

        if proxyServer:
            logger.info(f'{TorRelay.name()} uses proxy server {proxyServer}')

            # Use proxy
            self.torRelay.stdin.write(f'{torConfig}HTTPSProxy {proxyServer}\n'.encode())
        else:
            self.torRelay.stdin.write(torConfig.encode())

        self.torRelay.stdin.close()

        self.startDaemonThread(self.torRelay.stdout)
        # Begin get message
        self.startTimer()

    @QtCore.Slot()
    def processLine(self):
        line = self.getLineNoWait()

        if line:
            APP().torViewerWidget.textBrowser.append(line)

            match = TorRelayStarter.BOOTSTRAP_STATUS.search(line)

            if match:
                percentage = int(match.group(1))

                self.bootstrapPercentage = percentage

                logger.info(f'{TorRelay.name()} bootstrapped {percentage}%')


def getTorRelayVersion():
    try:
        result = subprocess.run(
            ['tor', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # First line, 3rd param...
        return result.stdout.decode().split('\n')[0].split()[2]
    except Exception:
        # Any non-exit exceptions

        return '0.0.0'


CACHED_VERSION = getTorRelayVersion()


class TorRelay(Core):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.starter = TorRelayStarter()

    @staticmethod
    def checkIfExists():
        return CACHED_VERSION != '0.0.0'

    @staticmethod
    def name():
        return 'Tor Relay'

    @staticmethod
    def version():
        return CACHED_VERSION

    @property
    def bootstrapPercentage(self):
        return self.starter.bootstrapPercentage

    def start(self, *args, **kwargs):
        logger.info(f'{self.name()} {self.version()} started')

        self.starter.launch(kwargs.get('proxyServer', ''))

    def stop(self):
        if isinstance(self.starter.torRelay, subprocess.Popen):
            # Stop timer
            self.starter.stopTimer()

            # Terminated by signal SIGTERM
            self.starter.torRelay.send_signal(signal.SIGTERM)

            exitcode = self.starter.torRelay.wait()

            logger.info(f'{self.name()} terminated with exitcode {exitcode}')

            self.starter.bootstrapPercentage = 0
            # Reset relay
            self.starter.torRelay = None
