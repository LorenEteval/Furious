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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Utility import *
from Furious.Core.CoreProcessWorker import *
from Furious.Core.XrayCore import *
from Furious.Core.Hysteria1 import *
from Furious.Core.Hysteria2 import *
from Furious.Core.Tun2socks import *

from typing import Tuple, Union

import uuid
import logging
import functools
import subprocess

__all__ = ['CoreManager']

logger = logging.getLogger(__name__)


def fixLogObjectPath(config: ConfigFactory, attr: str, value: str, log=True):
    try:
        path = config['log'][attr]
    except Exception:
        # Any non-exit exceptions

        config['log'][attr] = path = ''

    if not isinstance(path, str) and not isinstance(path, bytes):
        config['log'][attr] = path = ''

    if path == '':
        if SystemRuntime.isPythonw() and ProcessOutputRedirector.TemporaryDir.isValid():
            # Redirect implementation for pythonw environment
            config['log'][attr] = ProcessOutputRedirector.TemporaryDir.filePath(value)
    else:
        # Relative path fails if booting on start up
        # on Windows, when packed using nuitka...

        # Fix relative path if needed. User cannot feel this operation.
        config['log'][attr] = absolutePath(path)

    result = config['log'][attr]

    if result:
        try:
            # Create a new file
            with open(result, 'x', encoding='utf-8'):
                pass
        except FileExistsError:
            pass
        except Exception:
            # Any non-exit exceptions

            pass

    if log:
        logger.info(
            f'{XrayCore.name()}: {attr} log is specified as \'{path}\'. '
            f'Fixed to \'{result}\''
        )


def getUserTUNSettings(*args, **kwargs):
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


class CoreManager(Mixins.CleanupOnExit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.uniqueCleanup = False
        self.processesPool = list()

    @functools.singledispatchmethod
    def _startCore(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> Tuple[Union[CoreProcessWorker, None], bool]:
        return None, False

    @_startCore.register(ConfigXray)
    def _(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        if config.get('log') is None or not isinstance(config['log'], dict):
            config['log'] = {
                'access': '',
                'error': '',
                'loglevel': 'warning',
            }

        logRedirectValue = str(uuid.uuid4())

        # Fix logObject
        for attr in ['access', 'error']:
            fixLogObjectPath(config, attr, logRedirectValue, log)

        if routing == AppBuiltinRouting.BypassMainlandChina.value:
            # TUN Mode handling
            if not proxyModeOnly and SystemRuntime.isTUNMode():
                showMBoxDirectRulesNotAllowed()

                return None, False

            routingObject = {
                'domainStrategy': 'IPIfNonMatch',
                'domainMatcher': 'hybrid',
                'rules': [
                    {
                        'type': 'field',
                        'domain': [
                            'geosite:category-ads-all',
                        ],
                        'outboundTag': 'block',
                    },
                    {
                        'type': 'field',
                        'domain': [
                            'geosite:cn',
                        ],
                        'outboundTag': 'direct',
                    },
                    {
                        'type': 'field',
                        'ip': [
                            'geoip:private',
                            'geoip:cn',
                        ],
                        'outboundTag': 'direct',
                    },
                    {
                        'type': 'field',
                        'port': '0-65535',
                        'outboundTag': 'proxy',
                    },
                ],
            }
        elif routing == AppBuiltinRouting.Global.value:
            routingObject = {}
        elif routing == AppBuiltinRouting.Custom.value:
            routingObject = config.get('routing', {})
        else:
            routingObject = {}

        if log:
            logger.info(f'core {XrayCore.name()} configured')
            logger.info(f'routing is {routing}')
            logger.info(f'RoutingObject: {routingObject}')

        config['routing'] = routingObject

        process = XrayCore(exitCallback=exitCallback, msgCallback=msgCallback)
        success = process.start(config, **kwargs)

        return process, success

    @_startCore.register(ConfigHysteria1)
    def _(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        if routing == AppBuiltinRouting.BypassMainlandChina.value:
            # TUN Mode handling
            if not proxyModeOnly and SystemRuntime.isTUNMode():
                showMBoxDirectRulesNotAllowed()

                return None, False

            routingObject = {
                'rule': DATA_DIR / 'hysteria' / 'bypass-mainland-China.acl',
                'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
            }
        elif routing == AppBuiltinRouting.Global.value:
            routingObject = {
                'rule': '',
                'mmdb': '',
            }
        elif routing == AppBuiltinRouting.Custom.value:
            routingObject = {
                'rule': config.get('acl', ''),
                'mmdb': config.get('mmdb', ''),
            }
        else:
            routingObject = {
                'rule': '',
                'mmdb': '',
            }

        if log:
            logger.info(f'core {Hysteria1.name()} configured')
            logger.info(f'routing is {routing}')
            logger.info(f'RoutingObject: {routingObject}')

        process = Hysteria1(exitCallback=exitCallback, msgCallback=msgCallback)
        success = process.start(
            config,
            Hysteria1.rule(routingObject.get('rule', '')),
            Hysteria1.mmdb(routingObject.get('mmdb', '')),
            **kwargs,
        )

        return process, success

    @_startCore.register(ConfigHysteria2)
    def _(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        if log:
            logger.info(f'core {Hysteria2.name()} configured')

        process = Hysteria2(exitCallback=exitCallback, msgCallback=msgCallback)
        success = process.start(config, **kwargs)

        return process, success

    def start(
        self,
        config: ConfigFactory,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        if deepcopy:
            configcopy = config.deepcopy()
        else:
            configcopy = config

        process, success = self._startCore(
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

            return success

        # TUN Mode handling
        if not proxyModeOnly and SystemRuntime.isTUNMode():
            # Currently TUN Mode is only supported on Windows and macOS
            if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
                if PLATFORM == 'Windows':
                    # cleanup first
                    SystemRoutingTable.delete(
                        '0.0.0.0', APPLICATION_TUN_GATEWAY_ADDRESS
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

                    gateway, interfaceIP = userGateway, userInterfaceIP
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
                                lambda x: x != APPLICATION_TUN_GATEWAY_ADDRESS,
                                defaultGateway,
                            )
                        )

                    if len(defaultGateway) != 1:
                        logger.error(f'bad default gateway: {defaultGateway}')

                        return False

                    if PLATFORM == 'Windows':
                        gateway, interfaceIP = defaultGateway[0]
                    else:
                        gateway, interfaceIP = defaultGateway[0], None

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

                if not tun.start(
                    APPLICATION_TUN_DEVICE_NAME,
                    APPLICATION_TUN_NETWORK_INTERFACE_NAME,
                    'error',
                    f'socks5://{configcopy.socksProxy()}',
                    '',
                    f'{tcpSendBufferSize}MB',
                    f'{tcpReceiveBufferSize}MB',
                    tcpAutoTuning,
                ):
                    return False

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

                        return False
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

                                return False
                else:
                    logger.info(
                        f'automatically fetching TUN settings: '
                        f'\'BypassTUNAdapterInterfaceIP\''
                    )

                    address = configcopy.itemAddress

                    if not isValidIPAddress(address):
                        DNSResolver.configureHttpProxy(configcopy.httpProxy())

                        error, resolved = DNSResolver.resolve(address)

                        if error:
                            logger.error(f'DNS resolution failed: {address}')

                            SystemRoutingTable.Relations.clear()

                            return False
                        else:
                            for address in resolved:
                                SystemRoutingTable.Relations.append([address, gateway])
                    else:
                        SystemRoutingTable.Relations.append([address, gateway])

                if PLATFORM == 'Windows':
                    foundDevice = False

                    for counter in range(0, 10000, 100):
                        try:
                            result = runExternalCommand(
                                'ipconfig',
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True,
                            )
                        except Exception:
                            # Any non-exit exceptions

                            break
                        else:
                            stdout = result.stdout.decode('utf-8', 'replace')

                            if stdout.find(APPLICATION_TUN_DEVICE_NAME) >= 0:
                                foundDevice = True

                                logger.info(
                                    f'find TUN device \'{APPLICATION_TUN_DEVICE_NAME}\' success. '
                                    f'Counter: {counter}'
                                )

                                break

                        PySide6Legacy.eventLoopWait(100)

                    if not foundDevice:
                        logger.error(
                            f'find TUN device \'{APPLICATION_TUN_DEVICE_NAME}\' failed'
                        )

                        return False

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

                        alias = SystemRoutingTable.WIN32GetInterfaceAliasByIP(
                            interfaceIP
                        )

                    if alias:

                        def _windowsCleanup(_alias):
                            SystemRoutingTable.WIN32SetInterfaceDNS(_alias)
                            SystemRoutingTable.WIN32FlushDNSCache()

                        tun.cleanup = functools.partial(_windowsCleanup, alias)

                        # Handle user defined settings
                        userDisableInterfaceDNS = (
                            userDisablePrimaryAdapterInterfaceDNS()
                        )

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
                        userTunInterfaceDNS = APPLICATION_TUN_INTERFACE_DNS_ADDRESS
                    else:
                        logger.info(
                            f'got user defined TUN settings. '
                            f'TunAdapterInterfaceDNS: {userTunInterfaceDNS}'
                        )

                    SystemRoutingTable.addRelations()
                    SystemRoutingTable.WIN32SetInterfaceDNS(
                        APPLICATION_TUN_DEVICE_NAME,
                        userTunInterfaceDNS,
                        False,
                    )
                    SystemRoutingTable.setDeviceGateway(
                        APPLICATION_TUN_DEVICE_NAME,
                        APPLICATION_TUN_IP_ADDRESS,
                        APPLICATION_TUN_GATEWAY_ADDRESS,
                    )
                    SystemRoutingTable.WIN32FlushDNSCache()

                if PLATFORM == 'Darwin':
                    for source in [
                        *list(f'{2 ** (8 - x)}.0.0.0/{x}' for x in range(8, 0, -1)),
                        '198.18.0.0/15',
                    ]:
                        SystemRoutingTable.Relations.append(
                            [source, APPLICATION_TUN_GATEWAY_ADDRESS]
                        )

                    servers = SystemRoutingTable.DarwinGetDNSServers()

                    def _darwinCleanup(_servers):
                        for _service, _dnsserver in _servers:
                            SystemRoutingTable.DarwinSetDNSServers(_service, _dnsserver)

                    tun.cleanup = functools.partial(_darwinCleanup, servers)

                    # Handle user defined settings
                    userTunInterfaceDNS = userTunAdapterInterfaceDNS()

                    if userTunInterfaceDNS == '':
                        userTunInterfaceDNS = APPLICATION_TUN_INTERFACE_DNS_ADDRESS
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
                        APPLICATION_TUN_DEVICE_NAME,
                        APPLICATION_TUN_IP_ADDRESS,
                        APPLICATION_TUN_GATEWAY_ADDRESS,
                    )
                    SystemRoutingTable.addRelations()

        return True

    def allRunning(self) -> bool:
        return all(process.isAlive() for process in self.processesPool)

    def anyRunning(self) -> bool:
        return any(process.isAlive() for process in self.processesPool)

    def stopAll(self):
        if self.processesPool:
            for process in self.processesPool:
                if isinstance(process, CoreProcessFactory):
                    process.stop()

            self.processesPool.clear()

    def cleanup(self):
        self.stopAll()
