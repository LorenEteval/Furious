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

"""Coordinate proxy cores, TUN mode, DNS, and platform routing."""

from __future__ import annotations

from Furious.Frozenlib import (
    APPLICATION_TUN2SOCKS_DEVICE_NAME,
    APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
    APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS,
    APPLICATION_TUN2SOCKS_IP_ADDRESS,
    APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME,
    Mixins,
    PLATFORM,
    PySide6Legacy,
    SystemRoutingTable,
    SystemRuntime,
    isValidIPAddress,
)
from Furious.Interface import CoreRuntime
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Repository import Storage
from Furious.Plugins import TUNPreparationError, getPluginRegistry
from Furious.Service.DnsResolver import DnsResolver
from Furious.Core.CoreProcessWorker import CoreProcessWorker
from Furious.Core.Tun2socks import Tun2socks

from typing import Callable, Tuple, Union
from dataclasses import dataclass, field

import os
import logging
import tempfile
import functools

__all__ = ['ConnectionManager']

logger = logging.getLogger(__name__)


@dataclass
class _ConnectionStartAttempt:
    """Track resources acquired by one connection startup attempt."""

    manager: 'ConnectionManager'
    runtimeConfiguration: CoreConfiguration | ServerProfile
    runtimes: list[CoreRuntime] = field(default_factory=list)
    nativeTUNHandled: bool = False
    applicationTun2socks: bool = False
    committed: bool = False

    def ownRuntime(self, runtime: CoreRuntime | None):
        """Retain one newly acquired runtime until the attempt commits."""
        if runtime is None:
            return

        self.runtimes.append(runtime)

    def rollback(self, message: str = '') -> bool:
        """Release this attempt's resources in reverse acquisition order."""
        if message:
            logger.error(message)

        if self.committed:
            return False

        for runtime in reversed(self.runtimes):
            self.manager._stopAndDisposeRuntime(runtime)

        self.runtimes.clear()

        return False

    def commit(self):
        """Atomically transfer acquired runtimes to the manager lifecycle."""
        if self.committed:
            return

        self.manager.runtimes.extend(self.runtimes)
        self.runtimes.clear()

        self.committed = True


def getUserTUNSettings(*args, **kwargs):
    """Return one user-defined TUN setting or its fallback value."""
    return Storage.UserTUNSettings().get(*args, **kwargs)


(
    userPrimaryAdapterInterfaceName,
    userPrimaryAdapterInterfaceIP,
    userDefaultPrimaryGatewayIP,
    userTunAdapterInterfaceDNS,
    userBypassTUNAdapterInterfaceIP,
    userDisablePrimaryAdapterInterfaceDNS,
    userTcpSendBufferSize,
    userTcpReceiveBufferSize,
    userTcpAutoTuning,
) = (
    functools.partial(getUserTUNSettings, 'primaryAdapterInterfaceName', ''),
    functools.partial(getUserTUNSettings, 'primaryAdapterInterfaceIP', ''),
    functools.partial(getUserTUNSettings, 'defaultPrimaryGatewayIP', ''),
    functools.partial(getUserTUNSettings, 'tunAdapterInterfaceDNS', ''),
    functools.partial(getUserTUNSettings, 'bypassTUNAdapterInterfaceIP', ''),
    functools.partial(getUserTUNSettings, 'disablePrimaryAdapterInterfaceDNS', 'True'),
    functools.partial(getUserTUNSettings, 'tcpSendBufferSize', 1),
    functools.partial(getUserTUNSettings, 'tcpReceiveBufferSize', 1),
    functools.partial(getUserTUNSettings, 'tcpAutoTuning', 'False'),
)


class ConnectionManager(Mixins.CleanupOnExit):
    """Coordinate proxy cores, TUN setup, DNS changes, and routing cleanup."""

    def __init__(self, *args, **kwargs):
        """Initialize the connection manager."""
        self._dnsResolver = kwargs.pop('dnsResolver', None)

        super().__init__(*args, **kwargs)

        self.uniqueCleanup = False
        self.runtimes = list()
        self._lastStartError = ''

    def _connectionDnsResolver(self) -> DnsResolver:
        """Return the resolver owned by this connection-manager lifecycle."""
        if self._dnsResolver is None:
            # Creating QNetworkAccessManager during module import is invalid:
            # QApplication does not exist yet.  DNS is needed only for the
            # application-managed TUN path, so acquire it at that boundary.
            self._dnsResolver = DnsResolver()

        return self._dnsResolver

    @property
    def lastStartError(self) -> str:
        """Return the concise failure reported by the latest runtime start."""
        return self._lastStartError

    def _startCoreRuntime(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> Tuple[Union[CoreRuntime, None], bool]:
        """Construct and start the core runtime selected for a configuration."""
        return getPluginRegistry().startCoreRuntime(
            config,
            routing,
            exitCallback=exitCallback,
            messageCallback=msgCallback,
            proxyModeOnly=proxyModeOnly,
            log=log,
            **kwargs,
        )

    @staticmethod
    def _runtimeConfiguration(config, deepcopy: bool):
        """Return the attempt-scoped configuration used for runtime preparation."""
        return config.deepcopy() if deepcopy else config

    def _prepareTUNPolicy(self, config, proxyModeOnly: bool) -> tuple[bool, bool]:
        """Prepare plugin-native TUN and decide whether tun2socks is required."""
        tunModeRequested = not proxyModeOnly and SystemRuntime.isTUNMode()

        if not tunModeRequested:
            return False, False

        registry = getPluginRegistry()
        pluginTUN = registry.prepareTUN(config)

        if pluginTUN:
            return True, False

        useAppTun2socks = registry.usesApplicationTun2socks(config)

        if useAppTun2socks:
            logger.info(
                f'application-managed tun2socks selected. Remote '
                f'address: {config.remoteAddress()!r}'
            )
        else:
            logger.info(
                'application-managed tun2socks skipped by the active '
                'core runtime configuration'
            )

        return False, useAppTun2socks

    def _startPrimaryRuntime(
        self,
        attempt: _ConnectionStartAttempt,
        routing,
        exitCallback,
        msgCallbackCore,
        proxyModeOnly,
        log,
        **kwargs,
    ) -> bool:
        """Start and track the plugin-selected primary runtime."""
        runtime, success = self._startCoreRuntime(
            attempt.runtimeConfiguration,
            routing,
            exitCallback,
            msgCallbackCore,
            proxyModeOnly,
            log,
            **kwargs,
        )

        attempt.ownRuntime(runtime)

        if success:
            return True

        if isinstance(runtime, CoreRuntime):
            startError = getattr(runtime, 'startError', None)

            if callable(startError):
                self._lastStartError = startError()

        if isinstance(runtime, CoreProcessWorker):
            logger.error(f'core {runtime.name()} start failed')

        return False

    @staticmethod
    def waitForTUNDeviceBroughtUp(func: Callable[[str], bool], deviceName: str) -> bool:
        """Wait for the platform to expose the configured TUN device."""
        for counter in range(0, 10000, 100):
            if func(deviceName):
                logger.info(
                    f'find TUN device \'{deviceName}\' success. Counter: {counter}'
                )

                return True

            PySide6Legacy.eventLoopWait(100)

        logger.error(f'find TUN device \'{deviceName}\' failed')

        return False

    def start(
        self,
        config: CoreConfiguration | ServerProfile,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        """Run one staged connection attempt and roll it back on any failure."""
        self._lastStartError = ''

        attempt = _ConnectionStartAttempt(
            self, self._runtimeConfiguration(config, deepcopy)
        )

        try:
            return self._startAttempt(
                attempt,
                routing,
                exitCallback=exitCallback,
                msgCallbackCore=msgCallbackCore,
                msgCallbackTUN_=msgCallbackTUN_,
                proxyModeOnly=proxyModeOnly,
                log=log,
                **kwargs,
            )
        except Exception:
            # Any non-exit exceptions

            attempt.rollback('unexpected error during connection startup')

            raise

    def _startAttempt(
        self,
        attempt: _ConnectionStartAttempt,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        """Execute the semantic stages for one prepared connection attempt."""
        configcopy = attempt.runtimeConfiguration

        def abortStart(message: str = ''):
            """Roll back only resources acquired by this startup attempt."""
            return attempt.rollback(message)

        try:
            (
                attempt.nativeTUNHandled,
                attempt.applicationTun2socks,
            ) = self._prepareTUNPolicy(configcopy, proxyModeOnly)
        except TUNPreparationError as ex:
            self._lastStartError = str(ex)

            return abortStart(f'native TUN preparation failed: {self._lastStartError}')

        tunModeRequested = not proxyModeOnly and SystemRuntime.isTUNMode()

        if not self._startPrimaryRuntime(
            attempt,
            routing,
            exitCallback,
            msgCallbackCore,
            proxyModeOnly,
            log,
            **kwargs,
        ):
            return abortStart()

        if tunModeRequested and attempt.applicationTun2socks:
            if not self._startApplicationTun2socks(
                attempt, exitCallback, msgCallbackTUN_
            ):
                return False

        attempt.commit()

        return True

    def _startApplicationTun2socks(
        self,
        attempt: _ConnectionStartAttempt,
        exitCallback,
        msgCallbackTUN_,
    ) -> bool:
        """Acquire the application-managed tun2socks and host-network stage."""
        configcopy = attempt.runtimeConfiguration

        def abortStart(message: str = ""):
            return attempt.rollback(message)

        if PLATFORM == 'Windows':
            # cleanup first
            SystemRoutingTable.delete('0.0.0.0', APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS)

        # Handle user defined settings
        userGateway, userInterfaceIP = (
            userDefaultPrimaryGatewayIP(),
            userPrimaryAdapterInterfaceIP(),
        )

        if userGateway and userInterfaceIP:
            logger.info(
                f'got user defined TUN settings. '
                f'\'DefaultPrimaryGatewayIP\': {userGateway}. '
                f'\'PrimaryAdapterInterfaceIP\': {userInterfaceIP}'
            )

            gateway, interface = userGateway, userInterfaceIP
        else:
            logger.info(
                f'automatically fetching TUN settings: '
                f'\'DefaultPrimaryGatewayIP\' and \'PrimaryAdapterInterfaceIP\''
            )

            defaultGateway = SystemRoutingTable.getDefaultGateway()

            if PLATFORM == 'Darwin':
                # Need this?
                defaultGateway = list(
                    # Filter TUN Gateway
                    filter(
                        lambda x: x != APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
                        defaultGateway,
                    )
                )

            if len(defaultGateway) != 1:
                return abortStart(f'bad default gateway: {defaultGateway}')

            if PLATFORM == 'Windows' or PLATFORM == 'Linux':
                # On Linux the 'interface' is a name
                gateway, interface = defaultGateway[0]
            elif PLATFORM == 'Darwin':
                gateway, interface = defaultGateway[0], None
            else:
                return abortStart(f'unrecognized platform: {PLATFORM}')

        tun = Tun2socks(exitCallback=exitCallback, msgCallback=msgCallbackTUN_)

        attempt.ownRuntime(tun)

        tcpSendBufferSize, tcpReceiveBufferSize, tcpAutoTuning = (
            userTcpSendBufferSize(),
            userTcpReceiveBufferSize(),
            userTcpAutoTuning(),
        )

        if tcpSendBufferSize != 1:
            logger.info(
                f'got user defined TUN settings. TcpSendBufferSize: {tcpSendBufferSize}'
            )

        if tcpReceiveBufferSize != 1:
            logger.info(
                f'got user defined TUN settings. TCPReceiveBufferSize: {tcpReceiveBufferSize}'
            )

        if tcpAutoTuning == 'False':
            tcpAutoTuning = False
        elif tcpAutoTuning == 'True':
            tcpAutoTuning = True

            logger.info(
                f'got user defined TUN settings. TcpAutoTuning: {tcpAutoTuning}'
            )
        else:
            tcpAutoTuning = False

        if PLATFORM != 'Linux':
            interfaceArg = APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME
        else:
            interfaceArg = interface

        startTUN = functools.partial(
            tun.start,
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            interfaceArg,
            'error',
            f'socks5://{configcopy.socksProxy()}',
            '',
            f'{tcpSendBufferSize}MB',
            f'{tcpReceiveBufferSize}MB',
            tcpAutoTuning,
        )

        if PLATFORM != 'Linux':
            # Windows & macOS: bring up TUN first
            if not startTUN():
                return abortStart(f'core {Tun2socks.name()} start failed')

        # Handle user defined settings
        bypassTUN = userBypassTUNAdapterInterfaceIP()

        if bypassTUN:
            try:
                bypassSplit = bypassTUN.split(',')
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'error when processing user TUN bypass settings: {ex}')

                SystemRoutingTable.managedRoutes.clear()

                return abortStart()
            else:
                for bypass in bypassSplit:
                    if isValidIPAddress(bypass):
                        logger.info(f'processing user TUN bypass IP: {bypass}')

                        SystemRoutingTable.managedRoutes.append([bypass, gateway])
                    else:
                        logger.error(
                            f'invalid IP address when processing '
                            f'user TUN bypass settings: {bypass}'
                        )

                        SystemRoutingTable.managedRoutes.clear()

                        return abortStart()
        else:
            logger.info(
                f'automatically fetching TUN settings: '
                f'\'BypassTUNAdapterInterfaceIP\''
            )

            address = configcopy.remoteAddress()

            if not isValidIPAddress(address):
                dnsResolver = self._connectionDnsResolver()
                dnsResolver.configureHttpProxy(configcopy.httpProxy())

                error, resolved = dnsResolver.resolve(address)

                if error:
                    SystemRoutingTable.managedRoutes.clear()

                    return abortStart(f'DNS resolution failed: {address}')
                else:
                    for address in resolved:
                        SystemRoutingTable.managedRoutes.append([address, gateway])
            else:
                SystemRoutingTable.managedRoutes.append([address, gateway])

        # Platform specific implementation
        if PLATFORM == 'Windows':
            if not self.waitForTUNDeviceBroughtUp(
                SystemRoutingTable.WIN32IpconfigFindContent,
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
            ):
                return abortStart()

            # Handle user defined settings
            userInterfaceName = userPrimaryAdapterInterfaceName()

            if userInterfaceName:
                logger.info(
                    f'got user defined TUN settings. '
                    f'\'PrimaryAdapterInterfaceName\': {userInterfaceName}'
                )

                alias = userInterfaceName
            else:
                logger.info(
                    f'automatically fetching TUN settings: '
                    f'\'PrimaryAdapterInterfaceName\''
                )

                alias = SystemRoutingTable.WIN32GetInterfaceAliasByIP(interface)

            if alias:

                def _windowsCleanup(_alias):
                    """Handle windows cleanup for the core manager."""
                    SystemRoutingTable.WIN32SetInterfaceDNS(_alias)
                    SystemRoutingTable.WIN32FlushDNSCache()

                tun.cleanup = functools.partial(_windowsCleanup, alias)

                # Handle user defined settings
                userDisableInterfaceDNS = userDisablePrimaryAdapterInterfaceDNS()

                logger.info(f'DisablePrimaryInterfaceDNS: {userDisableInterfaceDNS}')

                if userDisableInterfaceDNS != 'False':
                    SystemRoutingTable.WIN32SetInterfaceDNS(alias, '127.0.0.1', False)

            # Handle user defined settings
            userTunInterfaceDNS = userTunAdapterInterfaceDNS()

            if userTunInterfaceDNS == '':
                userTunInterfaceDNS = APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
            else:
                logger.info(
                    f'got user defined TUN settings. '
                    f'TunAdapterInterfaceDNS: {userTunInterfaceDNS}'
                )

            SystemRoutingTable.addRelations()
            SystemRoutingTable.WIN32SetInterfaceDNS(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                userTunInterfaceDNS,
                False,
            )
            SystemRoutingTable.setDeviceGateway(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                APPLICATION_TUN2SOCKS_IP_ADDRESS,
                APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
            )
            SystemRoutingTable.WIN32FlushDNSCache()

        # Platform specific implementation
        if PLATFORM == 'Darwin':
            for address in [
                *list(f'{2 ** (8 - x)}.0.0.0/{x}' for x in range(8, 0, -1)),
                '198.18.0.0/15',
            ]:
                SystemRoutingTable.managedRoutes.append(
                    [address, APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS]
                )

            servers = SystemRoutingTable.DarwinGetDNSServers()

            def _darwinCleanup(_servers):
                """Handle darwin cleanup for the core manager."""
                for _service, _dnsserver in _servers:
                    SystemRoutingTable.DarwinSetDNSServers(_service, _dnsserver)

            tun.cleanup = functools.partial(_darwinCleanup, servers)

            # Handle user defined settings
            userTunInterfaceDNS = userTunAdapterInterfaceDNS()

            if userTunInterfaceDNS == '':
                userTunInterfaceDNS = APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
            else:
                logger.info(
                    f'got user defined TUN settings. '
                    f'TunAdapterInterfaceDNS: {userTunInterfaceDNS}'
                )

            for service, dnsserver in servers:
                SystemRoutingTable.DarwinSetDNSServers(
                    service,
                    userTunInterfaceDNS,
                )

            SystemRoutingTable.setDeviceGateway(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                APPLICATION_TUN2SOCKS_IP_ADDRESS,
                APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
            )
            SystemRoutingTable.addRelations()

        # Platform specific implementation
        if PLATFORM == 'Linux':

            def _linuxCleanup():
                """Handle linux cleanup for the core manager."""
                SystemRoutingTable.LinuxDeleteTUNDevice(
                    APPLICATION_TUN2SOCKS_DEVICE_NAME
                )

            tun.cleanup = functools.partial(_linuxCleanup)

            if SystemRoutingTable.LinuxFindTUNDevice(APPLICATION_TUN2SOCKS_DEVICE_NAME):
                logger.info(
                    f'find TUN device {APPLICATION_TUN2SOCKS_DEVICE_NAME} success. '
                    f'Will not try to bring up TUN device again'
                )

                commandBringUpTUN = ''
            else:
                logger.info(
                    f'find TUN device {APPLICATION_TUN2SOCKS_DEVICE_NAME} failed. '
                    f'Will try to bring up TUN device'
                )

                commandBringUpTUN = (
                    f'ip tuntap add mode tun dev {APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                    f'ip addr add 10.10.10.10/24 dev {APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                    f'ip link set dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} up'
                )

            commandAddDefaultRoute = (
                f'ip route add default dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} '
                'metric 5'
            )

            def route(source, destination) -> str:
                """Configure platform routing for the active proxy connection."""
                return f'{source} via {destination} dev {interface}'

            iproute = SystemRoutingTable.LinuxGetIpRoute()

            commandBypass = '\n'.join(
                list(
                    f'ip route add {route(sourceIP, destinationIP)}'
                    for sourceIP, destinationIP in SystemRoutingTable.managedRoutes
                    if iproute.find(route(sourceIP, destinationIP)) == -1
                )
            )

            if SystemRuntime.flatpakID():
                tempdir = os.environ.get('TMPDIR')
            else:
                tempdir = None

            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.sh', dir=tempdir, delete=True
            ) as file:
                content = '\n'.join(
                    filter(
                        lambda x: x != '',
                        [commandBringUpTUN, commandAddDefaultRoute, commandBypass],
                    )
                )

                file.write(content)
                file.flush()

                if not SystemRoutingTable.LinuxExecutePrivilegedScript(
                    file.name, shell='bash'
                ):
                    return abortStart()

                if not self.waitForTUNDeviceBroughtUp(
                    SystemRoutingTable.LinuxFindTUNDevice,
                    APPLICATION_TUN2SOCKS_DEVICE_NAME,
                ):
                    return abortStart()

            # Now bring up TUN
            if not startTUN():
                return abortStart(f'core {Tun2socks.name()} start failed')

        return True

    def allRunning(self) -> bool:
        """Return whether every managed core runtime is running."""
        return all(runtime.isAlive() for runtime in self.runtimes)

    def anyRunning(self) -> bool:
        """Return whether any managed core runtime is running."""
        return any(runtime.isAlive() for runtime in self.runtimes)

    @staticmethod
    def _stopAndDisposeRuntime(runtime):
        """Stop and dispose one exact runtime without changing an owner list."""
        try:
            if isinstance(runtime, CoreRuntime):
                runtime.stop()
        except Exception as ex:
            # Any non-exit exceptions

            # Cleanup must continue for the remaining attempt resources.
            logger.error(f'error stopping core runtime: {ex}')
        finally:
            dispose = getattr(runtime, 'dispose', None)

            if callable(dispose):
                try:
                    dispose()
                except Exception as ex:
                    # Any non-exit exceptions

                    logger.error(f'error disposing core runtime: {ex}')

    def _releaseRuntime(self, runtime):
        """Stop, dispose, and forget one exact runtime owned by this manager."""
        self._stopAndDisposeRuntime(runtime)

        try:
            self.runtimes.remove(runtime)
        except ValueError:
            pass

    def stopAll(self):
        """Stop every managed proxy-core and TUN runtime."""
        for runtime in reversed(list(self.runtimes)):
            self._releaseRuntime(runtime)

    def cleanup(self):
        """Release resources owned by the core manager."""
        self.stopAll()

        if self._dnsResolver is not None:
            dispose = getattr(self._dnsResolver, 'dispose', None)

            if callable(dispose):
                dispose()

            self._dnsResolver = None
