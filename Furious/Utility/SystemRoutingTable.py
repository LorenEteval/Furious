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
                f'powershell \"Get-NetIPAddress -IPAddress \'{ipaddress}\' | %{{$_.InterfaceAlias}};\"'.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            alias = result.stdout.decode(SYSTEM_PREFERRED_ENCODING, 'strict')

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
                    + [f'name=\"{name}\"', 'static', f'{address}']
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
                f'set interface \'{name}\' DNS success. address: {address}. dhcp: {dhcp}'
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
