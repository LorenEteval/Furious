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

from Furious.Core.Core import Core
from Furious.Utility.Constants import (
    APP,
    DATA_DIR,
    DEFAULT_TOR_SOCKS_PORT,
    DEFAULT_TOR_HTTPS_PORT,
)
from Furious.Utility.Utility import AsyncSubprocessMessage, runCommand

from PySide6 import QtCore

import re
import signal
import logging
import threading
import functools
import subprocess

logger = logging.getLogger(__name__)


class TorRelayStarter(AsyncSubprocessMessage):
    BOOTSTRAP_STATUS = re.compile(r'Bootstrapped ([0-9]+)%')

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


@functools.lru_cache(None)
def getTorRelayVersion():
    try:
        result = runCommand(
            ['tor', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        # First line, 3rd param...
        return result.stdout.decode().split('\n')[0].split()[2]
    except Exception:
        # Any non-exit exceptions

        return TorRelay.VERSION_NOT_FOUND


class TorRelay(Core):
    VERSION_NOT_FOUND = '0.0.0'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.starter = TorRelayStarter()

    @staticmethod
    def checkIfExists():
        return TorRelay.version() != TorRelay.VERSION_NOT_FOUND

    @staticmethod
    def name():
        return 'Tor Relay'

    @staticmethod
    def version():
        return getTorRelayVersion()

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
