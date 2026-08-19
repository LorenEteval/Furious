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

"""Provide bundled system routing table."""

from __future__ import annotations

from Furious.Frozenlib.Constants import *
from Furious.Frozenlib.Utility import *
from Furious.Frozenlib.SystemRuntime import *

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
    """Return the dict repr value used by the application."""
    return {
        'returncode': returncode,
        'stdout': stdout.decode(SYSTEM_PREFERRED_ENCODING, 'replace').strip(),
        'stderr': stderr.decode(SYSTEM_PREFERRED_ENCODING, 'replace').strip(),
    }


class SystemRoutingTable:
    """Represent system routing table."""

    managedRoutes = list()

    DEFAULT_GATEWAY_WIN32 = re.compile(
        r'0\.0\.0\.0.\s*0\.0\.0\.0.\s*(\S+)\s*(\S+)',
    )
    DEFAULT_GATEWAY_MACOS = re.compile(
        r'gateway:\s*(\S+)',
    )
    DEFAULT_GATEWAY_LINUX = re.compile(
        r'default\s+via\s+(\S+)\s+dev\s+(\S+)',
    )

    @staticmethod
    def add(sourceIP, destinationIP):
        """Add the system routing table."""

        def _add():
            """Return the add value used by the system routing table."""
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
        """Add relations."""
        for sourceIP, destinationIP in SystemRoutingTable.managedRoutes:
            SystemRoutingTable.add(sourceIP, destinationIP)

    @staticmethod
    def WIN32GetInterfaceAliasByIP(ipaddress) -> str:
        """Return the win32 get interface alias by ip value."""
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
        """Return the win32 set interface DNS value."""
        assert PLATFORM == 'Windows'

        try:
            if dhcp:
                result = runExternalCommand(
                    f'netsh interface ip set dns name=\"{name}\" dhcp',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    check=True,
                )
            else:
                assert address is not None

                result = runExternalCommand(
                    f'netsh interface ip set dns name=\"{name}\" static {address}',
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
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
        """Return the win32 flush DNS cache value."""
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
    def WIN32IpconfigFindContent(content: str) -> bool:
        """Return the win32 ipconfig find content value."""
        assert PLATFORM == 'Windows'

        try:
            result = runExternalCommand(
                ['ipconfig'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'run ipconfig failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return False
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'run ipconfig failed. {ex}')

            return False
        else:
            stdout = result.stdout.decode('utf-8', 'replace').strip()

            return stdout.find(content) >= 0

    @staticmethod
    def DarwinGetDNSServers() -> list:
        """Return the darwin get DNS servers value."""

        def getNetworkServices():
            """Return network services."""
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

                dnsserver = result.stdout.decode('utf-8', 'replace').strip()

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
        """Return the darwin set DNS servers value."""
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
    def LinuxFindTUNDevice(deviceName: str) -> bool:
        """Return the linux find TUN device value."""
        assert PLATFORM == 'Linux'

        command = 'ip tuntap show'

        if SystemRuntime.flatpakID():
            command = 'flatpak-spawn --host ' + command

        try:
            result = runExternalCommand(
                command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'find TUN device {deviceName} failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return False
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'find TUN device {deviceName} failed. {ex}')

            return False
        else:
            stdout = result.stdout.decode('utf-8', 'replace').strip()

            return stdout.find(deviceName) >= 0

    @staticmethod
    def LinuxDeleteTUNDevice(deviceName: str) -> bool:
        """Return the linux delete TUN device value."""
        assert PLATFORM == 'Linux'

        command = 'ip tuntap del mode tun dev'

        if SystemRuntime.flatpakID():
            command = 'flatpak-spawn --host ' + command

        try:
            result = runExternalCommand(
                command.split() + [deviceName],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'delete TUN device {deviceName} failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return False
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'delete TUN device {deviceName} failed. {ex}')

            return False
        else:
            logger.info(
                f'delete TUN device {deviceName} success. '
                f'{dictRepr(result.returncode, result.stdout, result.stderr)}'
            )

            return True

    @staticmethod
    def LinuxExecutePrivilegedScript(filepath, shell='bash') -> bool:
        """Return the linux execute privileged script value."""
        assert PLATFORM == 'Linux'

        command = 'pkexec'

        if SystemRuntime.flatpakID():
            command = 'flatpak-spawn --host ' + command

        try:
            result = runExternalCommand(
                command.split() + [shell, filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'execute privileged script failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return False
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'execute privileged script failed. {ex}')

            return False
        else:
            logger.info(
                f'execute privileged script success. '
                f'{dictRepr(result.returncode, result.stdout, result.stderr)}'
            )

            return True

    @staticmethod
    def LinuxGetIpRoute() -> str:
        """Return the linux get ip route value."""
        assert PLATFORM == 'Linux'

        command = 'ip route show'

        if SystemRuntime.flatpakID():
            command = 'flatpak-spawn --host ' + command

        try:
            result = runExternalCommand(
                command.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(
                f'show IP route failed. '
                f'{dictRepr(err.returncode, err.stdout, err.stderr)}'
            )

            return ''
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'show IP route failed. {ex}')

            return ''
        else:
            stdout = result.stdout.decode('utf-8', 'replace').strip()

            return stdout

    @staticmethod
    def getDefaultGateway() -> list:
        """Return default gateway."""

        def _get():
            """Return the get value used by the system routing table."""
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

            if PLATFORM == 'Linux':
                command = 'ip route show default'

                if SystemRuntime.flatpakID():
                    command = 'flatpak-spawn --host ' + command

                result = runExternalCommand(
                    command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

                return SystemRoutingTable.DEFAULT_GATEWAY_LINUX.findall(
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
        """Set device gateway."""

        def _set():
            """Return the set value used by the system routing table."""
            if PLATFORM == 'Windows':
                try:
                    result = runExternalCommand(
                        'netsh interface ip set address'.split()
                        + [
                            f'\"{deviceName}\"',
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
        """Delete the system routing table."""

        def _delete():
            """Return the delete value used by the system routing table."""
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

        if PLATFORM == 'Linux':
            # TODO: Do nothing under Linux
            return

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
        """Delete relations."""
        if PLATFORM == 'Windows':
            if len(SystemRoutingTable.managedRoutes):
                SystemRoutingTable.delete(
                    '0.0.0.0', APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS
                )

        for sourceIP, destinationIP in SystemRoutingTable.managedRoutes[::-1]:
            SystemRoutingTable.delete(sourceIP, destinationIP)

        if clear:
            SystemRoutingTable.managedRoutes.clear()
