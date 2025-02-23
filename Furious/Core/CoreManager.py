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

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *
from Furious.Core import *

import uuid
import logging
import functools
import subprocess

__all__ = ['CoreManager']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Unable to connect',
    'Routing option with direct rules is not allowed in VPN mode',
)


def fixLogObjectPath(config: ConfigurationFactory, attr: str, value: str, log=True):
    try:
        path = config['log'][attr]
    except Exception:
        # Any non-exit exceptions

        config['log'][attr] = path = ''

    if not isinstance(path, str) and not isinstance(path, bytes):
        config['log'][attr] = path = ''

    if path == '':
        if isPythonw() and StdoutRedirectHelper.TemporaryDir.isValid():
            # Redirect implementation for pythonw environment
            config['log'][attr] = StdoutRedirectHelper.TemporaryDir.filePath(value)
    else:
        # Relative path fails if booting on start up
        # on Windows, when packed using nuitka...

        # Fix relative path if needed. User cannot feel this operation.
        config['log'][attr] = getAbsolutePath(path)

    result = config['log'][attr]

    if result:
        try:
            # Create a new file
            with open(result, 'x'):
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


class CoreManager(SupportExitCleanup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.coresPool = []

    def start(
        self,
        config: ConfigurationFactory,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTun_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        if deepcopy:
            configcopy = config.deepcopy()
        else:
            configcopy = config

        if isinstance(configcopy, ConfigurationXray):
            if configcopy.get('log') is None or not isinstance(configcopy['log'], dict):
                configcopy['log'] = {
                    'access': '',
                    'error': '',
                    'loglevel': 'warning',
                }

            logRedirectValue = str(uuid.uuid4())

            # Fix logObject
            for attr in ['access', 'error']:
                fixLogObjectPath(configcopy, attr, logRedirectValue, log)

            if routing == 'Bypass Mainland China':
                # VPN Mode handling
                if not proxyModeOnly and isVPNMode():
                    mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
                    mbox.setWindowTitle(_('Unable to connect'))
                    mbox.setText(
                        _('Routing option with direct rules is not allowed in VPN mode')
                    )

                    # Show the MessageBox asynchronously
                    mbox.open()

                    return False

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
            # elif routing == 'Bypass Iran':
            #     routingObject = {
            #         'domainStrategy': 'IPIfNonMatch',
            #         'domainMatcher': 'hybrid',
            #         'rules': [
            #             {
            #                 'type': 'field',
            #                 'domain': [
            #                     'geosite:category-ads-all',
            #                     'iran:ads',
            #                 ],
            #                 'outboundTag': 'block',
            #             },
            #             {
            #                 'type': 'field',
            #                 'domain': [
            #                     'iran:ir',
            #                     'iran:other',
            #                 ],
            #                 'outboundTag': 'direct',
            #             },
            #             {
            #                 'type': 'field',
            #                 'ip': [
            #                     'geoip:private',
            #                     'geoip:ir',
            #                 ],
            #                 'outboundTag': 'direct',
            #             },
            #             {
            #                 'type': 'field',
            #                 'port': '0-65535',
            #                 'outboundTag': 'proxy',
            #             },
            #         ],
            #     }
            elif routing == 'Global':
                routingObject = {}
            elif routing == 'Custom':
                routingObject = configcopy.get('routing', {})
            else:
                routingObject = {}

            if log:
                logger.info(f'core {XrayCore.name()} configured')
                logger.info(f'routing is {routing}')
                logger.info(f'RoutingObject: {routingObject}')

            configcopy['routing'] = routingObject

            coreProcess = XrayCore(
                exitCallback=exitCallback, msgCallback=msgCallbackCore
            )
            success = coreProcess.start(configcopy, **kwargs)
        elif isinstance(configcopy, ConfigurationHysteria1):
            if routing == 'Bypass Mainland China':
                # VPN Mode handling
                if not proxyModeOnly and isVPNMode():
                    mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
                    mbox.setWindowTitle(_('Unable to connect'))
                    mbox.setText(
                        _('Routing option with direct rules is not allowed in VPN mode')
                    )

                    # Show the MessageBox asynchronously
                    mbox.open()

                    return False

                routingObject = {
                    'rule': DATA_DIR / 'hysteria' / 'bypass-mainland-China.acl',
                    'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
                }
            # elif routing == 'Bypass Iran':
            #     routingObject = {
            #         'rule': DATA_DIR / 'hysteria' / 'bypass-Iran.acl',
            #         'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
            #     }
            elif routing == 'Global':
                routingObject = {
                    'rule': '',
                    'mmdb': '',
                }
            elif routing == 'Custom':
                routingObject = {
                    'rule': configcopy.get('acl', ''),
                    'mmdb': configcopy.get('mmdb', ''),
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

            coreProcess = Hysteria1(
                exitCallback=exitCallback, msgCallback=msgCallbackCore
            )
            success = coreProcess.start(
                configcopy,
                Hysteria1.rule(routingObject.get('rule', '')),
                Hysteria1.mmdb(routingObject.get('mmdb', '')),
                **kwargs,
            )
        elif isinstance(configcopy, ConfigurationHysteria2):
            if log:
                logger.info(f'core {Hysteria2.name()} configured')

            coreProcess = Hysteria2(
                exitCallback=exitCallback, msgCallback=msgCallbackCore
            )
            success = coreProcess.start(configcopy, **kwargs)
        else:
            coreProcess = None
            success = False

        if coreProcess is not None:
            self.coresPool.append(coreProcess)

        if not success:
            logger.error(f'core {coreProcess.name()} start failed')

            return success

        # VPN Mode handling
        if not proxyModeOnly and isVPNMode():
            # Currently VPN Mode is only supported on Windows and macOS
            if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
                if PLATFORM == 'Windows':
                    # cleanup first
                    SystemRoutingTable.delete(
                        '0.0.0.0', APPLICATION_TUN_GATEWAY_ADDRESS
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

                tunProcess = Tun2socks(
                    exitCallback=exitCallback, msgCallback=msgCallbackTun_
                )
                self.coresPool.append(tunProcess)

                if not tunProcess.start(
                    APPLICATION_TUN_DEVICE_NAME,
                    APPLICATION_TUN_NETWORK_INTERFACE_NAME,
                    'info',
                    f'socks5://{configcopy.socksProxyEndpoint()}',
                    '',
                ):
                    return False

                address = configcopy.itemAddress

                if not isValidIPAddress(address):
                    error, resolved = DNSResolver.resolve(
                        address, *parseHostPort(configcopy.httpProxyEndpoint())
                    )

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

                        PySide6LegacyEventLoopWait(100)

                    if not foundDevice:
                        logger.error(
                            f'find TUN device \'{APPLICATION_TUN_DEVICE_NAME}\' failed'
                        )

                        return False

                    alias = SystemRoutingTable.WIN32GetInterfaceAliasByIP(interfaceIP)

                    if alias:

                        def _windowsCleanup(_alias):
                            SystemRoutingTable.WIN32SetInterfaceDNS(_alias)
                            SystemRoutingTable.WIN32FlushDNSCache()

                        tunProcess.cleanup = functools.partial(_windowsCleanup, alias)

                        SystemRoutingTable.WIN32SetInterfaceDNS(
                            alias, '127.0.0.1', False
                        )

                    SystemRoutingTable.addRelations()
                    SystemRoutingTable.WIN32SetInterfaceDNS(
                        APPLICATION_TUN_DEVICE_NAME,
                        APPLICATION_TUN_INTERFACE_DNS_ADDRESS,
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

                    tunProcess.cleanup = functools.partial(_darwinCleanup, servers)

                    for service, dnsserver in servers:
                        SystemRoutingTable.DarwinSetDNSServers(
                            service,
                            APPLICATION_TUN_INTERFACE_DNS_ADDRESS,
                        )

                    SystemRoutingTable.setDeviceGateway(
                        APPLICATION_TUN_DEVICE_NAME,
                        APPLICATION_TUN_IP_ADDRESS,
                        APPLICATION_TUN_GATEWAY_ADDRESS,
                    )
                    SystemRoutingTable.addRelations()

        return True

    def allRunning(self) -> bool:
        return all(coreProcess.isAlive() for coreProcess in self.coresPool)

    def anyRunning(self) -> bool:
        return any(coreProcess.isAlive() for coreProcess in self.coresPool)

    def stopAll(self):
        if self.coresPool:
            for coreProcess in self.coresPool:
                if isinstance(coreProcess, CoreFactory):
                    coreProcess.stop()

            self.coresPool.clear()

    def cleanup(self):
        self.stopAll()
