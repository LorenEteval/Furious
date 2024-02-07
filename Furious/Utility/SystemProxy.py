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
from Furious.Utility.Utility import parseHostPort, runExternalCommand
from Furious.Utility.AppSettings import *

import logging
import subprocess

__all__ = ['SystemProxy']

logger = logging.getLogger(__name__)


def handleAppSystemProxyMode() -> bool:
    try:
        if AppSettings.get('SystemProxyMode') == 'Auto':
            # Automatically configure
            return True
        else:
            # Do not change
            return False
    except Exception:
        # Any non-exit exceptions

        # Automatically configure
        return True


def linuxProxyConfig(proxy_args, arg0, arg1):
    runExternalCommand(
        [
            'gsettings',
            'set',
            'org.gnome.system.' + proxy_args,
            arg0,
            arg1,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def darwinProxyConfig(operation, *args):
    def getNetworkServices():
        command = runExternalCommand(
            ['networksetup', '-listallnetworkservices'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        # Replace with command.stdout.decode('utf-8', 'replace')...?
        service = list(filter(lambda x: x != '', command.stdout.decode().split('\n')))

        return service[1:]

    for serviceName in getNetworkServices():
        runExternalCommand(
            [
                'networksetup',
                f'-{operation}',
                serviceName,
                *args,
            ]
        )


class _SystemProxy:
    def __init__(self):
        self._daemonThread = None

    @staticmethod
    def pac(pac_url):
        def _pac():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.pac(pac_url)
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    linuxProxyConfig('proxy', 'autoconfig-url', pac_url)
                    linuxProxyConfig('proxy', 'mode', 'auto')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setautoproxyurl', pac_url)
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if not handleAppSystemProxyMode():
            logger.info(f'ignore proxy PAC \'{pac_url}\' request')

            return

        if _pac():
            logger.info(f'set proxy PAC \'{pac_url}\' success')
        else:
            logger.error(f'set proxy PAC \'{pac_url}\' failed')

    @staticmethod
    def set(server, bypass):
        def _set():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.set(server, bypass)
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    host, port = parseHostPort(server)

                    linuxProxyConfig('proxy.http', 'host', host)
                    linuxProxyConfig('proxy.http', 'port', port)
                    linuxProxyConfig('proxy.https', 'host', host)
                    linuxProxyConfig('proxy.https', 'port', port)
                    linuxProxyConfig(
                        'proxy', 'ignore-hosts', str(list(bypass.split(';')))
                    )
                    linuxProxyConfig('proxy', 'mode', 'manual')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setwebproxy', *parseHostPort(server))
                    darwinProxyConfig('setsecurewebproxy', *parseHostPort(server))
                    darwinProxyConfig('setproxybypassdomains', *bypass.split(';'))
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if not handleAppSystemProxyMode():
            logger.info(f'ignore proxy server {server} request')

            return

        if _set():
            logger.info(f'set proxy server {server} success')
        else:
            logger.error(f'set proxy server {server} failed')

    @staticmethod
    def off():
        def _off():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.off()
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    linuxProxyConfig('proxy', 'mode', 'none')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setwebproxystate', 'off')
                    darwinProxyConfig('setsecurewebproxystate', 'off')
                    darwinProxyConfig('setautoproxystate', 'off')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if not handleAppSystemProxyMode():
            logger.info('ignore turn off proxy request')

            return

        if _off():
            logger.info('turn off proxy success')
        else:
            logger.error('turn off proxy failed')

    def daemonOn_(self):
        def _daemonOn_():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy
                    import threading

                    if self._daemonThread is not None:
                        return False

                    self._daemonThread = threading.Thread(
                        target=lambda: sysproxy.daemon_on_(), daemon=True
                    )
                    self._daemonThread.start()

                    return True
                except Exception:
                    # Any non-exit exceptions

                    return False

        if not handleAppSystemProxyMode():
            logger.info('ignore turn on proxy daemon request')

            return

        if _daemonOn_():
            logger.info('turn on proxy daemon success')
        else:
            logger.error('turn on proxy daemon failed')

    def daemonOff(self):
        def _daemonOff():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy
                    import threading

                    if self._daemonThread is None:
                        # Already in off state
                        return True

                    assert isinstance(self._daemonThread, threading.Thread)

                    if sysproxy.daemon_off():
                        self._daemonThread.join()
                        # Reset it
                        self._daemonThread = None

                        return True
                    else:
                        return False
                except Exception:
                    # Any non-exit exceptions

                    return False

            # Note: try to resolve non-Windows proxy daemon issue by
            # turning on StartupOnBoot by default. This should be
            # friendly for most of the users

        if not handleAppSystemProxyMode():
            logger.info('ignore turn off proxy daemon request')

            return

        if _daemonOff():
            logger.info('turn off proxy daemon success')
        else:
            logger.error('turn off proxy daemon failed')


SystemProxy = _SystemProxy()
