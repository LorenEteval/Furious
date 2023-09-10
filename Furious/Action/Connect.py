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

from Furious.Core.Core import XrayCore, Hysteria1
from Furious.Core.TorRelay import TorRelay
from Furious.Core.Tun2socks import Tun2socks
from Furious.Core.Intellisense import Intellisense
from Furious.Core.Configuration import Configuration
from Furious.Action.Routing import BUILTIN_ROUTING_TABLE, BUILTIN_ROUTING
from Furious.Gui.Action import Action
from Furious.Widget.ConnectingProgressBar import ConnectingProgressBar
from Furious.Widget.Widget import MessageBox
from Furious.Utility.Constants import (
    APP,
    PLATFORM,
    APPLICATION_NAME,
    PROXY_SERVER_BYPASS,
    APPLICATION_TUN_DEVICE_NAME,
    APPLICATION_TUN_NETWORK_INTERFACE_NAME,
    APPLICATION_TUN_IP_ADDRESS,
    APPLICATION_TUN_GATEWAY_ADDRESS,
    DEFAULT_TOR_HTTPS_PORT,
    DEFAULT_TOR_SOCKS_PORT,
    DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT,
)
from Furious.Utility.Utility import (
    Switch,
    SupportConnectedCallback,
    bootstrapIcon,
    getAbsolutePath,
    isValidIPAddress,
    isAdministrator,
    isVPNMode,
)
from Furious.Utility.Translator import gettext as _
from Furious.Utility.Proxy import Proxy
from Furious.Utility.RoutingTable import RoutingTable

from PySide6 import QtCore
from PySide6.QtTest import QTest
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
    QNetworkProxy,
)

import ujson
import random
import logging

logger = logging.getLogger(__name__)


class HttpsProxyServerError(Exception):
    pass


class SocksProxyServerError(Exception):
    pass


class ConnectAction(Action):
    def __init__(self):
        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
        )

        self.connectingProgressBar = ConnectingProgressBar()

        self.configurationEmptyBox = MessageBox()
        self.configurationIcingBox = MessageBox()
        self.configurationErrorBox = MessageBox()
        self.configurationTampered = MessageBox()
        self.configurationProxyErr = MessageBox()

        self.httpsProxyServer = ''
        self.socksProxyServer = ''

        self.networkAccessManager = QNetworkAccessManager(parent=self)
        self.networkReply = None

        self.coreName = ''
        self.coreText = ''
        self.coreJSON = {}
        self.coreRunning = False
        self.XrayRouting = {}

        self.connectingFlag = False

        self.disconnectReason = ''

        # Note: The connection test is carried out item by item
        # from top to bottom. If any of these succeed,
        # connected action will be executed.

        # "Popular" sites that's been endorsed by some government.
        self.testPool = [
            # Messaging
            'https://telegram.org/',
            # Social media
            'https://twitter.com/',
            # Videos
            'https://www.youtube.com/',
        ]
        self.testTime = 0

        self.XrayCore = XrayCore()
        self.Hysteria1 = Hysteria1()
        self.Tun2socks = Tun2socks()
        self.TorRelay = TorRelay()

    def XrayCoreExitCallback(self, exitcode):
        if self.coreName:
            # If core is running
            assert self.coreRunning
            assert self.coreName == XrayCore.name()

        if exitcode == XrayCore.ExitCode.SystemShuttingDown:
            # System shutting down. Do nothing
            return

        if exitcode == XrayCore.ExitCode.ConfigurationError:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{XrayCore.name()}: {_("Invalid server configuration")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{XrayCore.name()}: {_("Invalid server configuration")}'
                )

                return

        if exitcode == XrayCore.ExitCode.ServerStartFailure:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{XrayCore.name()}: {_("Failed to start core")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{XrayCore.name()}: {_("Failed to start core")}'
                )

                return

        if not self.isConnecting():
            # Protect connecting action. Mandatory
            self.disconnectAction(
                f'{XrayCore.name()}: {_("Core terminated unexpectedly")}'
            )
        else:
            self.coreRunning = False
            self.disconnectReason = (
                f'{XrayCore.name()}: {_("Core terminated unexpectedly")}'
            )

    def Hysteria1ExitCallback(self, exitcode):
        if self.coreName:
            # If core is running
            assert self.coreRunning
            assert self.coreName == Hysteria1.name()

        if exitcode == Hysteria1.ExitCode.SystemShuttingDown:
            # System shutting down. Do nothing
            return

        if exitcode == Hysteria1.ExitCode.ConfigurationError:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{Hysteria1.name()}: {_("Invalid server configuration")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{Hysteria1.name()}: {_("Invalid server configuration")}'
                )

                return

        if exitcode == Hysteria1.ExitCode.RemoteNetworkError:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{Hysteria1.name()}: {_("Connection to server has been lost")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{Hysteria1.name()}: {_("Connection to server has been lost")}'
                )

                return

        if not self.isConnecting():
            # Protect connecting action. Mandatory
            self.disconnectAction(
                f'{Hysteria1.name()}: {_("Core terminated unexpectedly")}'
            )
        else:
            self.coreRunning = False
            self.disconnectReason = (
                f'{Hysteria1.name()}: {_("Core terminated unexpectedly")}'
            )

    def Tun2socksExitCallback(self, exitcode):
        if exitcode == Tun2socks.ExitCode.SystemShuttingDown:
            # System shutting down. Do nothing
            return

        if not self.isConnecting():
            # Protect connecting action. Mandatory
            self.disconnectAction(
                f'{Tun2socks.name()}: {_("Core terminated unexpectedly")}'
            )
        else:
            self.coreRunning = False
            self.disconnectReason = (
                f'{Tun2socks.name()}: {_("Core terminated unexpectedly")}'
            )

    def stopCore(self):
        self.stopTun2socks()

        self.TorRelay.stop()

        self.XrayCore.registerExitCallback(None)
        self.Hysteria1.registerExitCallback(None)

        # Stop any potentially running core
        self.XrayCore.stop()
        self.Hysteria1.stop()

        self.coreRunning = False

    def showConnectingProgressBar(self):
        if APP().ShowProgressBarWhenConnecting == Switch.ON_:
            self.connectingProgressBar.progressBar.setValue(0)
            # Update the progress bar every 50ms
            self.connectingProgressBar.timer.start(50)
            self.connectingProgressBar.show()

        return self

    def hideConnectingProgressBar(self, done=False):
        if done:
            self.connectingProgressBar.progressBar.setValue(100)

        self.connectingProgressBar.hide()
        self.connectingProgressBar.timer.stop()

        return self

    def moveConnectingProgressBar(self):
        # Progressing
        if self.connectingProgressBar.progressBar.value() <= 45:
            self.connectingProgressBar.progressBar.setValue(random.randint(45, 50))
        # Lower timer frequency
        self.connectingProgressBar.timer.start(250)

        return self

    def setDisabledAction(self, value):
        self.setDisabled(value)

        APP().tray.RoutingAction.setDisabled(value)

        if (PLATFORM == 'Windows' or PLATFORM == 'Darwin') and isAdministrator():
            VPNModeAction = APP().tray.SettingsAction.getVPNModeAction()

            assert VPNModeAction is not None

            VPNModeAction.setDisabled(value)

    def setConnectingStatus(self, showProgressBar=True):
        if showProgressBar:
            self.showConnectingProgressBar()

        # Do not accept new action
        self.setDisabledAction(True)
        self.setText(_('Connecting'))
        self.setIcon(bootstrapIcon('lock-fill.svg'))

    def setConnectedStatus(self):
        self.hideConnectingProgressBar(done=True)
        self.setDisabledAction(False)

        APP().tray.setConnectedIcon()

        # Finished. Reset connecting flag
        self.connectingFlag = False

        # Connected
        self.setText(_('Disconnect'))

        SupportConnectedCallback.callConnectedCallback()

    def isConnecting(self):
        return self.connectingFlag

    def isConnected(self):
        return self.textCompare('Disconnect')

    def reset(self):
        # Reset everything

        self.stopCore()

        self.hideConnectingProgressBar()
        self.setText(_('Connect'))
        self.setIcon(bootstrapIcon('unlock-fill.svg'))
        self.setChecked(False)

        APP().Connect = Switch.OFF
        APP().tray.setPlainIcon()

        self.httpsProxyServer = ''
        self.socksProxyServer = ''

        self.coreName = ''
        self.coreText = ''
        self.coreJSON = {}
        self.coreRunning = False
        self.XrayRouting = {}

        # Accept new action
        self.setDisabledAction(False)

        self.disconnectReason = ''

        self.connectingFlag = False

    @property
    def activatedServer(self):
        try:
            activatedIndex = int(APP().ActivatedItemIndex)

            if activatedIndex < 0:
                return None
            else:
                return APP().ServerWidget.ServerList[activatedIndex]['config']

        except Exception:
            # Any non-exit exceptions

            return None

    def errorConfiguration(self):
        self.configurationErrorBox.setIcon(MessageBox.Icon.Critical)
        self.configurationErrorBox.setWindowTitle(_('Unable to connect'))
        self.configurationErrorBox.setText(_('Invalid server configuration.'))

        # Show the MessageBox and wait for user to close it
        self.configurationErrorBox.exec()

    def errorConfigurationEmpty(self):
        self.configurationEmptyBox.setIcon(MessageBox.Icon.Critical)
        self.configurationEmptyBox.setWindowTitle(_('Unable to connect'))
        self.configurationEmptyBox.setText(
            _('Server configuration empty. Please configure your server first.')
        )

        # Show the MessageBox and wait for user to close it
        self.configurationEmptyBox.exec()

    def errorConfigurationNotActivated(self):
        self.configurationIcingBox.setIcon(MessageBox.Icon.Information)
        self.configurationIcingBox.setWindowTitle(_('Unable to connect'))
        self.configurationIcingBox.setText(
            _('Select and double click to activate configuration and connect.')
        )

        # Show the MessageBox and wait for user to close it
        self.configurationIcingBox.exec()

    def errorProxyConf(self, proxyType):
        assert proxyType == 'http' or proxyType == 'socks'

        self.configurationProxyErr.setIcon(MessageBox.Icon.Critical)
        self.configurationProxyErr.setWindowTitle(_('Unable to connect'))
        self.configurationProxyErr.setText(
            _(
                f'{APPLICATION_NAME} cannot find any valid {proxyType} proxy '
                f'endpoint in your server configuration.'
            )
        )
        self.configurationProxyErr.setInformativeText(
            _('Please complete your server configuration.')
        )

        # Show the MessageBox and wait for user to close it
        self.configurationProxyErr.exec()

    def errorHttpsProxyConf(self):
        self.errorProxyConf('http')

    def errorSocksProxyConf(self):
        self.errorProxyConf('socks')

    @property
    def torRelayStorageObj(self):
        # Handy reference
        return APP().torRelaySettingsWidget.StorageObj

    def configureCore(self):
        def validateHttpsProxyServer(server):
            # Validate https proxy server
            try:
                host, port = server.split(':')

                if int(port) < 0 or int(port) > 65535:
                    raise ValueError
            except Exception:
                # Any non-exit exceptions

                self.reset()
                self.errorHttpsProxyConf()

                return False
            else:
                self.httpsProxyServer = server

                return True

        def validateSocksProxyServer(server):
            # Validate socks proxy server
            try:
                host, port = server.split(':')

                if int(port) < 0 or int(port) > 65535:
                    raise ValueError
            except Exception:
                # Any non-exit exceptions

                self.reset()
                self.errorSocksProxyConf()

                return False
            else:
                self.socksProxyServer = server

                return True

        self.stopCore()

        self.XrayCore.registerExitCallback(
            lambda exitcode: self.XrayCoreExitCallback(exitcode)
        )
        self.Hysteria1.registerExitCallback(
            lambda exitcode: self.Hysteria1ExitCallback(exitcode)
        )
        self.Tun2socks.registerExitCallback(
            lambda exitcode: self.Tun2socksExitCallback(exitcode)
        )

        httpsProxyServer = None
        socksProxyServer = None

        if Intellisense.getCoreType(self.coreJSON) == XrayCore.name():
            # Assuming is XrayCore configuration
            httpsProxyHost = None
            httpsProxyPort = None
            socksProxyHost = None
            socksProxyPort = None

            if isVPNMode():
                # Check socks inbound is valid
                try:
                    for inbound in self.coreJSON['inbounds']:
                        if inbound['protocol'] == 'socks':
                            socksProxyHost = inbound['listen']
                            socksProxyPort = inbound['port']

                            # Note: If there are multiple socks inbounds
                            # satisfied, the first one will be chosen.
                            break

                    if socksProxyHost is None or socksProxyPort is None:
                        # No HTTP proxy endpoint configured
                        raise SocksProxyServerError

                    socksProxyServer = f'{socksProxyHost}:{socksProxyPort}'
                except (KeyError, SocksProxyServerError):
                    self.reset()
                    self.errorSocksProxyConf()

                    # Return to caller
                    return XrayCore.name()
                else:
                    # Validate socks proxy server
                    if not validateSocksProxyServer(socksProxyServer):
                        # Return to caller
                        return XrayCore.name()

            try:
                for inbound in self.coreJSON['inbounds']:
                    if inbound['protocol'] == 'http':
                        httpsProxyHost = inbound['listen']
                        httpsProxyPort = inbound['port']

                        # Note: If there are multiple http inbounds
                        # satisfied, the first one will be chosen.
                        break

                if httpsProxyHost is None or httpsProxyPort is None:
                    # No HTTP proxy endpoint configured
                    raise HttpsProxyServerError

                httpsProxyServer = f'{httpsProxyHost}:{httpsProxyPort}'
            except (KeyError, HttpsProxyServerError):
                self.reset()
                self.errorHttpsProxyConf()
            else:
                if validateHttpsProxyServer(httpsProxyServer):
                    routing = APP().Routing

                    logger.info(f'core {XrayCore.name()} configured')

                    def fixLoggingRelativePath(attr):
                        # Relative path fails if booting on start up
                        # on Windows, when packed using nuitka...

                        # Fix relative path if needed. User cannot feel this operation.

                        try:
                            path = self.coreJSON['log'][attr]
                        except KeyError:
                            pass
                        else:
                            if path and (
                                isinstance(path, str) or isinstance(path, bytes)
                            ):
                                fix = getAbsolutePath(path)

                                logger.info(
                                    f'{XrayCore.name()}: {attr} log is specified as \'{path}\'. '
                                    f'Fixed to \'{fix}\''
                                )

                                self.coreJSON['log'][attr] = fix

                    fixLoggingRelativePath('access')
                    fixLoggingRelativePath('error')

                    # Filter Route My Traffic Through Tor, Custom
                    if routing in list(
                        filter(
                            lambda x: x != 'Route My Traffic Through Tor'
                            and x != 'Custom',
                            BUILTIN_ROUTING,
                        )
                    ):
                        routingObject = BUILTIN_ROUTING_TABLE[routing][XrayCore.name()]

                        logger.info(f'routing is {routing}')
                        logger.info(f'RoutingObject: {routingObject}')

                        self.coreJSON['routing'] = routingObject
                    elif routing == 'Route My Traffic Through Tor':
                        logger.info(f'routing is {routing}')

                        if TorRelay.checkIfExists():
                            logger.info(
                                f'find Tor CLI in path success. Version: {TorRelay.version()}'
                            )

                            routingObject = {}

                            logger.info(f'RoutingObject: {routingObject}')

                            self.coreJSON['routing'] = routingObject
                        else:
                            logger.error('find Tor CLI in path failed')

                            self.coreRunning = False
                            self.disconnectReason = (
                                f'{XrayCore.name()}: {_("Cannot find Tor CLI in PATH")}'
                            )

                            return XrayCore.name()
                    elif routing == 'Custom':
                        logger.info(f'routing is {routing}')
                        logger.info(f'RoutingObject: {self.XrayRouting}')

                        # Assign user routing
                        self.coreJSON['routing'] = self.XrayRouting
                    else:
                        try:
                            routesWidget = APP().RoutesWidget

                            route = routesWidget.RoutesList[int(routing)]

                            logger.info(f'routing is {route["remark"]}')
                            logger.info(f'RoutingObject: {route[XrayCore.name()]}')

                            self.coreJSON['routing'] = route[XrayCore.name()]
                        except Exception as ex:
                            # Any non-exit exceptions

                            logger.error(
                                f'get custom routing object failed: {ex}. Fast fail'
                            )

                            # Fast fail
                            self.coreJSON = {}

                    self.coreRunning = True

                    # Refresh configuration modified before. User cannot feel
                    self.coreText = ujson.dumps(
                        self.coreJSON, ensure_ascii=False, escape_forward_slashes=False
                    )
                    # Start core
                    if self.coreJSON:
                        self.XrayCore.start(self.coreText)

                        if routing == 'Route My Traffic Through Tor':
                            # Must start Tor Relay first since it will redirect proxy for us
                            self.startTorRelay(XrayCore.name(), httpsProxyServer)

                        if isVPNMode():
                            if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
                                # Currently VPN Mode is only supported on Windows and macOS
                                self.startTun2socks()
                    else:
                        # Fast fail
                        self.XrayCore.start(self.coreText, waitTime=1000)

            return XrayCore.name()

        if Intellisense.getCoreType(self.coreJSON) == Hysteria1.name():
            # Assuming is Hysteria1 configuration

            if isVPNMode():
                # Check socks inbound is valid
                try:
                    socksProxyServer = self.coreJSON['socks5']['listen']

                    if socksProxyServer is None:
                        # No SOCKS proxy endpoint configured
                        raise SocksProxyServerError
                except (KeyError, SocksProxyServerError):
                    self.reset()
                    self.errorSocksProxyConf()

                    # Return to caller
                    return Hysteria1.name()
                else:
                    # Validate socks proxy server
                    if not validateSocksProxyServer(socksProxyServer):
                        # Return to caller
                        return Hysteria1.name()

            try:
                httpsProxyServer = self.coreJSON['http']['listen']

                if httpsProxyServer is None:
                    # No HTTP proxy endpoint configured
                    raise HttpsProxyServerError
            except (KeyError, HttpsProxyServerError):
                self.reset()
                self.errorHttpsProxyConf()
            else:
                if validateHttpsProxyServer(httpsProxyServer):
                    self.coreRunning = True

                    routing = APP().Routing

                    logger.info(f'core {Hysteria1.name()} configured')

                    # Filter Route My Traffic Through Tor, Global, Custom
                    if routing in list(
                        filter(
                            lambda x: x != 'Route My Traffic Through Tor'
                            and x != 'Global'
                            and x != 'Custom',
                            BUILTIN_ROUTING,
                        )
                    ):
                        logger.info(f'routing is {routing}')

                        routingObject = BUILTIN_ROUTING_TABLE[routing][Hysteria1.name()]

                        self.Hysteria1.start(
                            self.coreText,
                            Hysteria1.rule(routingObject.get('acl')),
                            Hysteria1.mmdb(routingObject.get('mmdb')),
                        )
                    elif routing == 'Route My Traffic Through Tor':
                        logger.info(f'routing is {routing}')

                        if TorRelay.checkIfExists():
                            logger.info(
                                f'find Tor CLI in path success. Version: {TorRelay.version()}'
                            )

                            self.Hysteria1.start(self.coreText, '', '')

                            self.startTorRelay(Hysteria1.name(), httpsProxyServer)
                        else:
                            logger.error('find Tor CLI in path failed')

                            self.coreRunning = False
                            self.disconnectReason = f'{Hysteria1.name()}: {_("Cannot find Tor CLI in PATH")}'

                            return Hysteria1.name()
                    elif routing == 'Global':
                        logger.info(f'routing is {routing}')

                        self.Hysteria1.start(self.coreText, '', '')
                    elif routing == 'Custom':
                        logger.info(f'routing is {routing}')

                        self.Hysteria1.start(
                            self.coreText,
                            Hysteria1.rule(self.coreJSON.get('acl')),
                            Hysteria1.mmdb(self.coreJSON.get('mmdb')),
                        )
                    else:
                        try:
                            routesWidget = APP().RoutesWidget

                            route = routesWidget.RoutesList[int(routing)]

                            logger.info(f'routing is {route["remark"]}')
                            logger.info(f'RoutingObject: {route[Hysteria1.name()]}')

                            self.Hysteria1.start(
                                self.coreText,
                                Hysteria1.rule(route[Hysteria1.name()].get('acl')),
                                Hysteria1.mmdb(route[Hysteria1.name()].get('mmdb')),
                            )
                        except Exception as ex:
                            # Any non-exit exceptions

                            logger.error(
                                f'get custom routing object failed: {ex}. Fast fail'
                            )

                            # Fast fail
                            self.coreJSON = {}
                            self.coreText = ''

                            self.Hysteria1.start(self.coreText, '', '', waitTime=1000)

                    if self.coreJSON:
                        if isVPNMode():
                            if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
                                # Currently VPN Mode is only supported on Windows and macOS
                                self.startTun2socks()

            return Hysteria1.name()

        # No matching core
        return ''

    def startTun2socks(self, successCallback=None):
        if not self.coreRunning:
            # Core has exited. Do nothing
            return

        defaultGateway = list(
            # Filter TUN Gateway
            filter(
                lambda x: x != APPLICATION_TUN_GATEWAY_ADDRESS,
                RoutingTable.getDefaultGatewayAddress(),
            )
        )

        if len(defaultGateway) != 1:
            logger.error(f'found multiple gateway addresses: {defaultGateway}')

            self.coreRunning = False
            self.disconnectReason = (
                _('Unable to connect') + ': ' + _('Multiple gateway addresses found')
            )

            return

        coreAddr = Intellisense.getCoreAddr(self.coreJSON)

        if not coreAddr:
            logger.error(f'invalid server address: {coreAddr}')

            self.coreRunning = False
            self.disconnectReason = _('Server address invalid') + f': {coreAddr}'

            return

        def start():
            assert RoutingTable.Relations

            if PLATFORM == 'Darwin':
                for source in [
                    *list(f'{2 ** (8 - x)}.0.0.0/{x}' for x in range(8, 0, -1)),
                    '198.18.0.0/15',
                ]:
                    RoutingTable.Relations.append(
                        [source, APPLICATION_TUN_GATEWAY_ADDRESS]
                    )

            self.Tun2socks.start(
                APPLICATION_TUN_DEVICE_NAME,
                APPLICATION_TUN_NETWORK_INTERFACE_NAME,
                'silent',
                f'socks5://{self.socksProxyServer}',
                '',
            )

            if PLATFORM == 'Windows':
                RoutingTable.addRelations()
                RoutingTable.setDeviceGatewayAddress(
                    APPLICATION_TUN_DEVICE_NAME,
                    APPLICATION_TUN_IP_ADDRESS,
                    APPLICATION_TUN_GATEWAY_ADDRESS,
                )

            if PLATFORM == 'Darwin':
                RoutingTable.setDeviceGatewayAddress(
                    APPLICATION_TUN_DEVICE_NAME,
                    APPLICATION_TUN_IP_ADDRESS,
                    APPLICATION_TUN_GATEWAY_ADDRESS,
                )
                RoutingTable.addRelations()

            if callable(successCallback):
                successCallback()

        if not isValidIPAddress(coreAddr):
            logger.info(f'dns resolve uses proxy server {self.httpsProxyServer}')

            # Checked. split should not throw exceptions
            proxyHost, proxyPort = self.httpsProxyServer.split(':')

            # Checked. int(proxyPort) should not throw exceptions
            self.networkAccessManager.setProxy(
                QNetworkProxy(
                    QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort)
                )
            )

            request = QNetworkRequest(
                QtCore.QUrl(f'https://cloudflare-dns.com/dns-query?name={coreAddr}')
            )
            request.setRawHeader('accept'.encode(), 'application/dns-json'.encode())

            self.networkReply = self.networkAccessManager.get(request)

            @QtCore.Slot()
            def finishedCallback():
                if self.networkReply is None:
                    # Interrupted externally. Do nothing
                    logger.info(f'dns resolve for {coreAddr} interrupted externally')

                    return

                assert isinstance(self.networkReply, QNetworkReply)

                if self.networkReply.error() != QNetworkReply.NetworkError.NoError:
                    logger.error(
                        f'DNS resolution for {coreAddr} failed. {self.networkReply.errorString()}'
                    )

                    self.coreRunning = False
                    self.disconnectReason = _('DNS resolution failed') + f': {coreAddr}'
                    # Reset reply
                    self.networkReply = None
                else:
                    logger.info(f'dns resolve for {coreAddr} success')

                    replyObject = ujson.loads(self.networkReply.readAll().data())

                    # Reset reply
                    self.networkReply = None

                    for record in replyObject['Answer']:
                        address = record['data']

                        logger.info(f'{coreAddr} resolved to {address}')

                        RoutingTable.Relations.append([address, defaultGateway[0]])

                    start()

            self.networkReply.finished.connect(finishedCallback)
        else:
            # Reset reply
            self.networkReply = None

            RoutingTable.Relations.append([coreAddr, defaultGateway[0]])

            start()

        self.waitForDNSResolutionIfNecessary()

    def stopTun2socks(self):
        self.Tun2socks.registerExitCallback(None)
        self.Tun2socks.stop()

    def waitForDNSResolutionIfNecessary(self, startCounter=0, timeout=10000, step=1):
        # Wait for potentially DNS resolve in VPN Mode
        if self.coreRunning and self.networkReply is not None:
            logger.info('dns resolve in progress. Wait')
        else:
            return

        while (
            self.coreRunning
            and startCounter < timeout
            and self.networkReply is not None
        ):
            QTest.qWait(step)

            startCounter += step

        if self.networkReply is not None:
            if self.coreRunning:
                logger.error('DNS resolution timeout')

                self.coreRunning = False
                self.disconnectReason = _('DNS resolution timeout')

            # Reset reply
            self.networkReply = None

    def startTorRelay(self, core, proxyServer, startCounter=0, step=1):
        # Redirect Proxy
        self.httpsProxyServer = f'127.0.0.1:{self.torRelayStorageObj.get("httpsTunnelPort", DEFAULT_TOR_HTTPS_PORT)}'
        self.socksProxyServer = f'127.0.0.1:{self.torRelayStorageObj.get("socksTunnelPort", DEFAULT_TOR_SOCKS_PORT)}'

        try:
            timeout = 1000 * int(
                self.torRelayStorageObj.get(
                    'relayEstablishTimeout', DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT
                )
            )
        except Exception:
            # Any non-exit exceptions

            timeout = 1000 * DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT

        logger.info(f'{TorRelay.name()} bootstrap timeout is {timeout // 1000}s')

        # Start Tor Relay
        if self.torRelayStorageObj.get('useProxy', True):
            # Use proxy
            self.TorRelay.start(proxyServer=proxyServer)
        else:
            # Do not use proxy
            self.TorRelay.start()

        while (
            self.coreRunning
            and startCounter < timeout
            and self.TorRelay.bootstrapPercentage != 100
        ):
            QTest.qWait(step)

            startCounter += step

        if not self.coreRunning:
            # Interrupted externally. Return
            return

        if self.TorRelay.bootstrapPercentage != 100:
            # bootstrap timeout
            self.stopCore()
            # Assign disconnect reason
            self.disconnectReason = (
                f'{core}: {_(f"{TorRelay.name()} establish timeout")}'
            )

            logger.error(f'{TorRelay.name()} establish failed')
        else:
            logger.info(f'{TorRelay.name()} establish success')

    def startConnectionTest(
        self, showRoutingChangedMessage=False, currentRouting='', isBuiltinRouting=False
    ):
        selected = self.testPool[self.testTime]

        self.testTime += 1

        logger.info(f'start connection test. Try: {selected}')
        logger.info(f'connection test uses proxy server {self.httpsProxyServer}')

        # Checked. split should not throw exceptions
        proxyHost, proxyPort = self.httpsProxyServer.split(':')

        # Checked. int(proxyPort) should not throw exceptions
        self.networkAccessManager.setProxy(
            QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort))
        )

        self.networkReply = self.networkAccessManager.get(
            QNetworkRequest(QtCore.QUrl(selected))
        )

        @QtCore.Slot()
        def finishedCallback():
            assert isinstance(self.networkReply, QNetworkReply)

            if self.networkReply.error() != QNetworkReply.NetworkError.NoError:
                logger.error(
                    f'{self.coreName}: connection test failed. {self.networkReply.errorString()}'
                )

                if self.testTime < len(self.testPool) and self.coreRunning:
                    # Try next
                    self.startConnectionTest(
                        showRoutingChangedMessage, currentRouting, isBuiltinRouting
                    )
                else:
                    if self.disconnectReason:
                        self.disconnectAction(self.disconnectReason)
                    else:
                        self.disconnectAction(
                            f'{self.coreName}: {_("Connection test failed")}'
                        )
            else:
                logger.info(f'{self.coreName}: connection test success. Connected')

                APP().Connect = Switch.ON_

                # Connected status
                self.setConnectedStatus()

                if showRoutingChangedMessage:
                    # Routing changed
                    if isBuiltinRouting:
                        APP().tray.showMessage(
                            _('Routing changed: ') + _(currentRouting)
                        )
                    else:
                        APP().tray.showMessage(_('Routing changed: ') + currentRouting)
                else:
                    # Connected
                    APP().tray.showMessage(f'{self.coreName}: {_("Connected")}')

        self.networkReply.finished.connect(finishedCallback)

    def connectAction(self):
        # Connect action
        assert self.textCompare('Connect')

        # Connecting
        self.connectingFlag = True

        if not APP().Configuration or len(APP().ServerWidget.ServerList) == 0:
            APP().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationEmpty()

            return

        myText = self.activatedServer

        if myText is None:
            APP().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationNotActivated()

            return

        if myText == '':
            APP().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationEmpty()

            return

        try:
            myJSON = Configuration.toJSON(myText)
        except Exception:
            # Any non-exit exceptions

            APP().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False

            # Invalid configuratoin
            self.errorConfiguration()
        else:
            # Get server configuration success. Continue.
            # Note: use self.reset() to restore state

            self.coreText = myText
            self.coreJSON = myJSON

            # Memorize user routing if possible
            self.XrayRouting = myJSON.get('routing', {})

            self.connectingAction()

    def connectingAction(
        self,
        showProgressBar=True,
        showRoutingChangedMessage=False,
        currentRouting='',
        isBuiltinRouting=False,
        **kwargs,
    ):
        # Connecting. Redefined
        self.connectingFlag = True

        # Connecting status
        self.setConnectingStatus(showProgressBar)

        # Reset reply. Mandatory
        self.networkReply = None

        # Configure connect
        self.coreName = self.configureCore()

        if not self.coreName:
            # No matching core
            self.reset()
            self.errorConfiguration()

            return

        if not self.coreRunning:
            # 1. No valid HTTP/Socks proxy endpoint. reset / disconnect has been called

            if self.isConnecting():
                # 2. Core has exited

                self.disconnectAction(self.disconnectReason)

            return

        try:
            Proxy.set(self.httpsProxyServer, PROXY_SERVER_BYPASS)
        except Exception:
            # Any non-exit exceptions

            Proxy.off()

            self.reset()
            self.errorConfiguration()
        else:
            self.moveConnectingProgressBar()
            # Reset try time
            self.testTime = 0
            self.startConnectionTest(
                showRoutingChangedMessage, currentRouting, isBuiltinRouting
            )

    def disconnectAction(self, reason=''):
        Proxy.off()

        self.reset()

        SupportConnectedCallback.callDisconnectedCallback()

        APP().tray.showMessage(reason)

    def reconnectAction(self, reason=''):
        self.disconnectAction(reason)
        self.trigger()

    def triggeredCallback(self, checked):
        if checked:
            self.connectAction()
        else:
            # Disconnect action
            assert self.textCompare('Disconnect')
            assert self.connectingFlag is False

            self.disconnectAction(f'{self.coreName}: {_("Disconnected")}')
