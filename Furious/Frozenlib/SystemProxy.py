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

"""Provide bundled system proxy."""

from __future__ import annotations

from Furious.Frozenlib.Constants import *
from Furious.Frozenlib.Enum import *
from Furious.Frozenlib.AppSettings import *
from Furious.Frozenlib.Utility import *
from Furious.Frozenlib.SystemRuntime import *

import logging
import threading
import subprocess

__all__ = ['SystemProxy']

logger = logging.getLogger(__name__)


def handleAppSystemProxyMode() -> bool:
    """Handle app system proxy mode."""
    try:
        if AppSettings.get('SystemProxyMode') == AppBuiltinProxyMode.Auto.value:
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
    """Handle linux proxy config for the application."""
    command = 'gsettings'

    if SystemRuntime.flatpakID():
        command = 'flatpak-spawn --host ' + command

    runExternalCommand(
        command.split()
        + [
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
    """Return the darwin proxy config value used by the application."""

    def getNetworkServices():
        """Return network services."""
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
    """Represent system proxy."""

    DaemonShutdownTimeout = 5.0

    def __init__(self):
        """Initialize the _SystemProxy."""
        self._daemonThread = None
        self._daemonLock = threading.RLock()

    def _runDaemon(self, daemonCallback):
        """Run the native daemon and release this exact thread on exit."""
        thread = threading.current_thread()

        try:
            daemonCallback()
        except Exception:
            # Any non-exit exceptions

            logger.exception('proxy daemon terminated with an error')
        finally:
            with self._daemonLock:
                if self._daemonThread is thread:
                    self._daemonThread = None

    @staticmethod
    def pac(pac_url):
        """Configure the system proxy with a PAC URL."""

        def _pac():
            """Return the pac value used by the system proxy."""
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
        """Set data managed by the system proxy."""

        def _set():
            """Return the set value used by the system proxy."""
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

                    if host is None or port is None:
                        raise

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
        """Disable the system proxy."""

        def _off():
            """Return the off value used by the system proxy."""
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
        """Return the daemon on value used by the system proxy."""

        def _daemonOn_():
            """Return the daemon on value used by the system proxy."""
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    with self._daemonLock:
                        if (
                            isinstance(self._daemonThread, threading.Thread)
                            and self._daemonThread.is_alive()
                        ):
                            # Daemon is alive. Do nothing
                            return False

                        self._daemonThread = None

                        thread = threading.Thread(
                            target=self._runDaemon,
                            args=(sysproxy.daemon_on_,),
                            daemon=True,
                        )

                        self._daemonThread = thread

                        try:
                            thread.start()
                        except Exception:
                            if self._daemonThread is thread:
                                self._daemonThread = None

                            raise

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
        """Return the daemon off value used by the system proxy."""

        def _daemonOff():
            """Return the daemon off value used by the system proxy."""
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    with self._daemonLock:
                        thread = self._daemonThread

                    if thread is None:
                        # Already in off state
                        return True

                    assert isinstance(thread, threading.Thread)

                    if sysproxy.daemon_off():
                        if thread is threading.current_thread():
                            logger.error('proxy daemon cannot join its own thread')

                            return False

                        thread.join(self.DaemonShutdownTimeout)

                        if thread.is_alive():
                            logger.error('proxy daemon did not stop before timeout')

                            return False

                        with self._daemonLock:
                            if self._daemonThread is thread:
                                self._daemonThread = None

                        return True
                    else:
                        return False
                except Exception:
                    # Any non-exit exceptions

                    return False

            # Note: try to solve non-Windows proxy daemon issue by
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
