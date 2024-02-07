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

from Furious.Utility.Constants import *
from Furious.Utility.Utility import runExternalCommand

import re
import logging
import subprocess

__all__ = ['SystemRoutingTable']

logger = logging.getLogger(__name__)

if PLATFORM == 'Windows':
    if SYSTEM_LANGUAGE == 'ZH':
        SYSTEM_PREFERRED_ENCODING = 'gbk'
    else:
        SYSTEM_PREFERRED_ENCODING = 'utf-8'
else:
    SYSTEM_PREFERRED_ENCODING = 'utf-8'


def dictRepr(returncode, stdout, stderr):
    return {
        'returncode': returncode,
        'stdout': stdout.decode(SYSTEM_PREFERRED_ENCODING, 'replace').strip(),
        'stderr': stderr.decode(SYSTEM_PREFERRED_ENCODING, 'replace').strip(),
    }


class SystemRoutingTable:
    Relations = list()

    DEFAULT_GATEWAY_WIN32 = re.compile(
        r'0\.0\.0\.0.\s*0\.0\.0\.0.\s*(\S+)\s*(\S+)',
    )
    DEFAULT_GATEWAY_MACOS = re.compile(
        r'gateway:\s*(\S+)',
    )

    @staticmethod
    def add(sourceIP, destinationIP):
        def _add():
            if PLATFORM == 'Windows':
                try:
                    result = runExternalCommand(
                        ['route', 'add', sourceIP, destinationIP, 'metric', '5'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

            if PLATFORM == 'Darwin':
                try:
                    result = runExternalCommand(
                        ['route', 'add', '-net', sourceIP, destinationIP],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

        try:
            returncode, stdout, stderr = _add()
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'add rule {sourceIP}->{destinationIP} to routing table failed. {ex}'
            )
        else:
            if returncode == 0:
                logger.info(
                    f'add rule {sourceIP}->{destinationIP} to routing table success. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'add rule {sourceIP}->{destinationIP} to routing table failed. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )

    @staticmethod
    def addRelations():
        for sourceIP, destinationIP in SystemRoutingTable.Relations:
            SystemRoutingTable.add(sourceIP, destinationIP)

    @staticmethod
    def WIN32GetInterfaceAliasByIP(ipaddress) -> str:
        assert PLATFORM == 'Windows'

        try:
            # Note: Does not work on Windows 7 due to old powershell version

            result = runExternalCommand(
                f'powershell \"Get-NetIPAddress -IPAddress \'{ipaddress}\' | %{{$_.InterfaceAlias}};\"',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                check=True,
            )

            alias = result.stdout.decode(SYSTEM_PREFERRED_ENCODING, 'strict').strip()

            logger.info(f'get \'{ipaddress}\' interface alias success: {alias}')

            return alias
        except subprocess.CalledProcessError as err:
            logger.error(
                f'get \'{ipaddress}\' interface alias failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return ''
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'get \'{ipaddress}\' interface alias failed. {ex}')

            return ''

    @staticmethod
    def WIN32SetInterfaceDNS(name, address=None, dhcp=True):
        assert PLATFORM == 'Windows'

        try:
            if dhcp:
                result = runExternalCommand(
                    'netsh interface ip set dns'.split() + [f'name=\"{name}\"', 'dhcp'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            else:
                assert address is not None

                result = runExternalCommand(
                    'netsh interface ip set dns'.split()
                    + [f'name=\"{name}\"', 'static', f'{address}'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'set interface \'{name}\' DNS failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'set interface \'{name}\' DNS failed. {ex}')
        else:
            logger.info(
                f'set interface \'{name}\' DNS success. address: {address}. dhcp: {dhcp}. '
                f'{dictRepr(result.returncode, result.stdout, result.stderr)}'
            )

    @staticmethod
    def WIN32FlushDNSCache():
        assert PLATFORM == 'Windows'

        try:
            result = runExternalCommand(
                'ipconfig /flushdns'.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'flush system DNS cache failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'flush system DNS cache failed. {ex}')
        else:
            logger.info(
                f'flush system DNS cache success. '
                f'{dictRepr(result.returncode, result.stdout, result.stderr)}'
            )

    @staticmethod
    def DarwinGetDNSServers() -> list:
        def getNetworkServices():
            _command = runExternalCommand(
                ['networksetup', '-listallnetworkservices'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            # Replace with command.stdout.decode('utf-8', 'replace')...?
            _service = list(
                filter(lambda x: x != '', _command.stdout.decode().split('\n'))
            )

            return _service[1:]

        assert PLATFORM == 'Darwin'

        try:
            services = getNetworkServices()
            dnsservers = []

            for service in services:
                result = runExternalCommand(
                    'networksetup -getdnsservers'.split() + [service],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

                dnsserver = result.stdout.decode().strip()

                if dnsserver.find('DNS Servers') >= 0:
                    # 'There aren't any DNS Servers set on ...'
                    dnsservers.append('')
                else:
                    dnsservers.append(dnsserver)

            servers = list(zip(services, dnsservers))
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'get system DNS servers failed. {ex}')

            return []
        else:
            logger.info(f'get system DNS servers success. {servers}')

            return servers

    @staticmethod
    def DarwinSetDNSServers(service: str, dnsserver: str):
        assert PLATFORM == 'Darwin'

        dnsserverRepr = [dnsserver]

        try:
            if not dnsserver:
                result = runExternalCommand(
                    'networksetup -setdnsservers'.split() + [service, 'Empty'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
            else:
                result = runExternalCommand(
                    'networksetup -setdnsservers'.split()
                    + [service]
                    + dnsserver.split('\n'),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'set service \'{service}\' DNS server {dnsserverRepr} failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'set service \'{service}\' DNS server {dnsserverRepr} failed. {ex}'
            )
        else:
            logger.info(
                f'set service \'{service}\' DNS server {dnsserverRepr} success. '
                f'{dictRepr(result.returncode, result.stdout, result.stderr)}'
            )

    @staticmethod
    def getDefaultGateway() -> list:
        def _get():
            if PLATFORM == 'Windows':
                # Note: On Windows interface IP is also captured

                result = runExternalCommand(
                    'route print 0.0.0.0'.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

                return SystemRoutingTable.DEFAULT_GATEWAY_WIN32.findall(
                    result.stdout.decode(SYSTEM_PREFERRED_ENCODING, 'replace')
                )

            if PLATFORM == 'Darwin':
                result = runExternalCommand(
                    'route get default'.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

                return SystemRoutingTable.DEFAULT_GATEWAY_MACOS.findall(
                    result.stdout.decode(SYSTEM_PREFERRED_ENCODING, 'replace')
                )

        try:
            defaultGateway = _get()
        except subprocess.CalledProcessError as err:
            logger.error(
                f'get default gateway failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return []
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'get default gateway failed. {ex}')

            return []
        else:
            logger.info(f'get default gateway success. {defaultGateway}')

            return defaultGateway

    @staticmethod
    def setDeviceGateway(deviceName, deviceIP, deviceGateway):
        def _set():
            if PLATFORM == 'Windows':
                try:
                    result = runExternalCommand(
                        'netsh interface ip set address'.split()
                        + [
                            deviceName,
                            'static',
                            deviceIP,
                            '255.255.255.0',
                            deviceGateway,
                            '3',
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

            if PLATFORM == 'Darwin':
                try:
                    result = runExternalCommand(
                        ['ifconfig', deviceName, deviceIP, deviceGateway, 'up'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

        try:
            returncode, stdout, stderr = _set()
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'set device \'{deviceName}\' gateway \'{deviceGateway}\' failed. {ex}'
            )
        else:
            if returncode == 0:
                logger.info(
                    f'set device \'{deviceName}\' gateway \'{deviceGateway}\' success. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'set device \'{deviceName}\' gateway \'{deviceGateway}\' failed. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )

    @staticmethod
    def delete(sourceIP, destinationIP):
        def _delete():
            if PLATFORM == 'Windows':
                try:
                    result = runExternalCommand(
                        ['route', 'delete', sourceIP, destinationIP],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

            if PLATFORM == 'Darwin':
                try:
                    result = runExternalCommand(
                        ['route', 'delete', '-net', sourceIP, destinationIP],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                except Exception:
                    # Any non-exit exceptions

                    raise
                else:
                    return result.returncode, result.stdout, result.stderr

        try:
            returncode, stdout, stderr = _delete()
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'delete rule {sourceIP}->{destinationIP} from routing table failed. {ex}'
            )
        else:
            if returncode == 0:
                logger.info(
                    f'delete rule {sourceIP}->{destinationIP} from routing table success. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )
            else:
                logger.error(
                    f'delete rule {sourceIP}->{destinationIP} from routing table failed. '
                    f'{dictRepr(returncode, stdout, stderr)}'
                )

    @staticmethod
    def deleteRelations(clear=True):
        if PLATFORM == 'Windows':
            if len(SystemRoutingTable.Relations):
                SystemRoutingTable.delete('0.0.0.0', APPLICATION_TUN_GATEWAY_ADDRESS)

        for sourceIP, destinationIP in SystemRoutingTable.Relations[::-1]:
            SystemRoutingTable.delete(sourceIP, destinationIP)

        if clear:
            SystemRoutingTable.Relations.clear()
