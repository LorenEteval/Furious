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

from Furious.Utility.Constants import (
    PLATFORM,
    SYSTEM_LANGUAGE,
    APPLICATION_TUN_GATEWAY_ADDRESS,
)
from Furious.Utility.Utility import runCommand

import re
import logging
import subprocess

logger = logging.getLogger(__name__)


def getDictTuple(returncode, stdout, stderr):
    return {
        'returncode': returncode,
        'stdout': stdout,
        'stderr': stderr,
    }


class RoutingTable:
    Relations = list()

    DEFAULT_GATEWAY_WINDOWS = re.compile(
        r'0\.0\.0\.0.\s*0\.0\.0\.0.\s*(\S+)',
    )
    DEFAULT_GATEWAY_DARWIN = re.compile(
        r'gateway:\s*(\S+)',
    )

    @staticmethod
    def add(source, destination):
        def _add():
            if PLATFORM == 'Windows':
                try:
                    result = runCommand(
                        ['route', 'add', source, destination, 'metric', '5'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    if SYSTEM_LANGUAGE == 'ZH':
                        return (
                            result.returncode,
                            result.stdout.decode('gbk', 'replace').strip(),
                            result.stderr.decode('gbk', 'replace').strip(),
                        )
                    else:
                        return (
                            result.returncode,
                            result.stdout.decode('utf-8', 'replace').strip(),
                            result.stderr.decode('utf-8', 'replace').strip(),
                        )

            if PLATFORM == 'Darwin':
                try:
                    result = runCommand(
                        ['route', 'add', '-net', source, destination],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    return (
                        result.returncode,
                        result.stdout.decode('utf-8', 'replace'),
                        result.stderr.decode('utf-8', 'replace'),
                    )

        try:
            returncode, stdout, stderr = _add()
        except Exception:
            # Any non-exit exceptions

            logger.error(f'add rule {source}->{destination} to routing table failed')
        else:
            if returncode == 0:
                logger.info(
                    f'add rule {source}->{destination} to routing table success. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'add rule {source}->{destination} to routing table failed. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
                )

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
                    result = runCommand(
                        'netsh interface ip set address'.split()
                        + [
                            deviceName,
                            'static',
                            ipAddress,
                            '255.255.255.0',
                            gatewayAddress,
                            '3',
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    if SYSTEM_LANGUAGE == 'ZH':
                        return (
                            result.returncode,
                            result.stdout.decode('gbk', 'replace').strip(),
                            result.stderr.decode('gbk', 'replace').strip(),
                        )
                    else:
                        return (
                            result.returncode,
                            result.stdout.decode('utf-8', 'replace').strip(),
                            result.stderr.decode('utf-8', 'replace').strip(),
                        )

            if PLATFORM == 'Darwin':
                try:
                    result = runCommand(
                        [
                            'ifconfig',
                            deviceName,
                            ipAddress,
                            gatewayAddress,
                            'up',
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    return (
                        result.returncode,
                        result.stdout.decode('utf-8', 'replace'),
                        result.stderr.decode('utf-8', 'replace'),
                    )

        try:
            returncode, stdout, stderr = _set()
        except Exception:
            # Any non-exit exceptions

            logger.error(
                f'set device \'{deviceName}\' gateway address \'{gatewayAddress}\' failed'
            )
        else:
            if returncode == 0:
                logger.info(
                    f'set device \'{deviceName}\' gateway address \'{gatewayAddress}\' success. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'set device \'{deviceName}\' gateway address \'{gatewayAddress}\' failed. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
                )

    @staticmethod
    def delete(source, destination):
        def _delete():
            if PLATFORM == 'Windows':
                try:
                    result = runCommand(
                        ['route', 'delete', source, destination],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    if SYSTEM_LANGUAGE == 'ZH':
                        return (
                            result.returncode,
                            result.stdout.decode('gbk', 'replace').strip(),
                            result.stderr.decode('gbk', 'replace').strip(),
                        )
                    else:
                        return (
                            result.returncode,
                            result.stdout.decode('utf-8', 'replace').strip(),
                            result.stderr.decode('utf-8', 'replace').strip(),
                        )

            if PLATFORM == 'Darwin':
                try:
                    result = runCommand(
                        ['route', 'delete', '-net', source, destination],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    return -1, '', ''
                else:
                    return (
                        result.returncode,
                        result.stdout.decode('utf-8', 'replace'),
                        result.stderr.decode('utf-8', 'replace'),
                    )

        try:
            returncode, stdout, stderr = _delete()
        except Exception:
            # Any non-exit exceptions

            logger.error(
                f'delete rule {source}->{destination} from routing table failed'
            )
        else:
            if returncode == 0:
                logger.info(
                    f'delete rule {source}->{destination} from routing table success. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'delete rule {source}->{destination} from routing table failed. '
                    f'{getDictTuple(returncode, stdout, stderr)}'
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
