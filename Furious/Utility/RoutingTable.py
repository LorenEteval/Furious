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

from Furious.Utility.Constants import PLATFORM, APPLICATION_TUN_GATEWAY_ADDRESS
from Furious.Utility.Utility import runCommand

import re
import logging
import subprocess

logger = logging.getLogger(__name__)


class RoutingTable:
    Relations = list()

    DEFAULT_GATEWAY_WINDOWS = re.compile(
        r'0\.0\.0\.0.*?0\.0\.0\.0.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
    )
    DEFAULT_GATEWAY_DARWIN = re.compile(
        r'gateway:\s*(\S+)',
    )

    @staticmethod
    def add(source, destination):
        def _add():
            if PLATFORM == 'Windows':
                try:
                    runCommand(
                        ['route', 'add', source, destination, 'metric', '5'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    runCommand(
                        ['route', 'add', '-net', source, destination],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _add():
            logger.info(f'add rule {source}->{destination} to routing table success')
        else:
            logger.error(f'add rule {source}->{destination} to routing table failed')

    @staticmethod
    def addRelations():
        for source, destination in RoutingTable.Relations:
            RoutingTable.add(source, destination)

    @staticmethod
    def getDefaultGatewayAddress():
        def _get():
            if PLATFORM == 'Windows':
                try:
                    result = runCommand(
                        [
                            'route',
                            'PRINT',
                            '0.0.0.0',
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )

                    return RoutingTable.DEFAULT_GATEWAY_WINDOWS.findall(
                        result.stdout.decode('utf-8', 'replace')
                    )
                except Exception:
                    # Any non-exit exceptions

                    return []

            if PLATFORM == 'Darwin':
                try:
                    result = runCommand(
                        'route get default'.split(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )

                    return RoutingTable.DEFAULT_GATEWAY_DARWIN.findall(
                        result.stdout.decode('utf-8', 'replace')
                    )
                except Exception:
                    # Any non-exit exceptions

                    return []

        defaultGateway = _get()

        if defaultGateway:
            logger.info(f'get default gateway address success. {defaultGateway}')
        else:
            logger.error('get default gateway address failed')

        return defaultGateway

    @staticmethod
    def setDeviceGatewayAddress(deviceName, ipAddress, gatewayAddress):
        def _set():
            if PLATFORM == 'Windows':
                try:
                    runCommand(
                        'netsh interface ip set address'.split()
                        + [
                            deviceName,
                            'static',
                            ipAddress,
                            '255.255.255.0',
                            gatewayAddress,
                            '3',
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    runCommand(
                        [
                            'ifconfig',
                            deviceName,
                            ipAddress,
                            gatewayAddress,
                            'up',
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _set():
            logger.info(
                f'set device \'{deviceName}\' gateway address \'{gatewayAddress}\' success'
            )
        else:
            logger.error(
                f'set device \'{deviceName}\' gateway address \'{gatewayAddress}\' failed'
            )

    @staticmethod
    def delete(source, destination):
        def _delete():
            if PLATFORM == 'Windows':
                try:
                    runCommand(
                        ['route', 'delete', source, destination],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    runCommand(
                        ['route', 'delete', '-net', source, destination],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _delete():
            logger.info(
                f'delete rule {source}->{destination} from routing table success'
            )
        else:
            logger.error(
                f'delete rule {source}->{destination} from routing table failed'
            )

    @staticmethod
    def deleteRelations(clear=True):
        if PLATFORM == 'Windows':
            if len(RoutingTable.Relations):
                RoutingTable.delete('0.0.0.0', APPLICATION_TUN_GATEWAY_ADDRESS)

        for source, destination in RoutingTable.Relations[::-1]:
            RoutingTable.delete(source, destination)

        if clear:
            RoutingTable.Relations.clear()
