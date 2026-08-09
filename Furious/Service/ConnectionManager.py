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

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Domain import *
from Furious.Repository import *
from Furious.Plugins import *
from Furious.Qt import *
from Furious.Service.DnsResolver import DnsResolver
from Furious.Core.CoreProcessWorker import *
from Furious.Core.Tun2socks import *

from typing import Callable, Tuple, Union

import os
import logging
import tempfile
import functools

__all__ = ['ConnectionManager']

logger = logging.getLogger(__name__)


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
        super().__init__(*args, **kwargs)

        self.uniqueCleanup = False
        self.processesPool = list()

    def _startKernel(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> Tuple[Union[CoreProcessWorker, None], bool]:
        """Construct and start the runtime kernel selected for a configuration."""
        return getPluginRegistry().startKernel(
            config,
            routing,
            exitCallback=exitCallback,
            messageCallback=msgCallback,
            proxyModeOnly=proxyModeOnly,
            log=log,
            **kwargs,
        )

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
        config: ConfigFactory | ServerProfile,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        """Start the selected proxy core and configure TUN mode when requested."""
        if deepcopy:
            configcopy = config.deepcopy()
        else:
            configcopy = config

        def abortStart(message: str = ''):
            """Return the abort start value used by the core manager."""
            if message:
                logger.error(message)

            self.stopAll()

            return False

        pluginTUN = False
        if not proxyModeOnly and SystemRuntime.isTUNMode():
            pluginTUN = getPluginRegistry().prepareTUN(configcopy)

        process, success = self._startKernel(
            configcopy,
            routing,
            exitCallback,
            msgCallbackCore,
            proxyModeOnly,
            log,
            **kwargs,
        )

        if process is not None:
            self.processesPool.append(process)

        if not success:
            if isinstance(process, CoreProcessWorker):
                logger.error(f'core {process.name()} start failed')

            self.stopAll()

            return False

        # TUN Mode handling
        if not proxyModeOnly and SystemRuntime.isTUNMode() and not pluginTUN:
            if PLATFORM == 'Windows':
                # cleanup first
                SystemRoutingTable.delete(
                    '0.0.0.0', APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS
                )

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
            self.processesPool.append(tun)

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

                    logger.error(
                        f'error when processing user TUN bypass settings: {ex}'
                    )

                    SystemRoutingTable.Relations.clear()

                    return abortStart()
                else:
                    for bypass in bypassSplit:
                        if isValidIPAddress(bypass):
                            logger.info(f'processing user TUN bypass IP: {bypass}')

                            SystemRoutingTable.Relations.append([bypass, gateway])
                        else:
                            logger.error(
                                f'invalid IP address when processing '
                                f'user TUN bypass settings: {bypass}'
                            )

                            SystemRoutingTable.Relations.clear()

                            return abortStart()
            else:
                logger.info(
                    f'automatically fetching TUN settings: '
                    f'\'BypassTUNAdapterInterfaceIP\''
                )

                address = configcopy.itemAddress

                if not isValidIPAddress(address):
                    DnsResolver.configureHttpProxy(configcopy.httpProxy())

                    error, resolved = DnsResolver.resolve(address)

                    if error:
                        SystemRoutingTable.Relations.clear()

                        return abortStart(f'DNS resolution failed: {address}')
                    else:
                        for address in resolved:
                            SystemRoutingTable.Relations.append([address, gateway])
                else:
                    SystemRoutingTable.Relations.append([address, gateway])

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

                    logger.info(
                        f'DisablePrimaryInterfaceDNS: {userDisableInterfaceDNS}'
                    )

                    if userDisableInterfaceDNS != 'False':
                        SystemRoutingTable.WIN32SetInterfaceDNS(
                            alias, '127.0.0.1', False
                        )

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
                    SystemRoutingTable.Relations.append(
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

                if SystemRoutingTable.LinuxFindTUNDevice(
                    APPLICATION_TUN2SOCKS_DEVICE_NAME
                ):
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
                        for sourceIP, destinationIP in SystemRoutingTable.Relations
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
        """Return whether every managed process is running."""
        return all(process.isAlive() for process in self.processesPool)

    def anyRunning(self) -> bool:
        """Return whether any managed process is running."""
        return any(process.isAlive() for process in self.processesPool)

    def stopAll(self):
        """Stop every managed proxy and TUN process."""
        try:
            for process in list(self.processesPool):
                if not isinstance(process, CoreProcess):
                    continue

                try:
                    process.stop()
                except Exception as ex:
                    logger.error(f'error stopping core process: {ex}')
        finally:
            self.processesPool.clear()

    def cleanup(self):
        """Release resources owned by the core manager."""
        self.stopAll()
