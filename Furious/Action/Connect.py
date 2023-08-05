from Furious.Core.Core import XrayCore, Hysteria
from Furious.Core.Intellisense import Intellisense
from Furious.Core.Configuration import Configuration
from Furious.Action.Routing import SUPPORTED_ROUTING_DETAIL
from Furious.Gui.Action import Action
from Furious.Widget.ConnectingProgressBar import ConnectingProgressBar
from Furious.Widget.Widget import MessageBox
from Furious.Utility.Constants import APPLICATION_NAME, PROXY_SERVER_BYPASS
from Furious.Utility.Utility import (
    Switch,
    SupportConnectedCallback,
    bootstrapIcon,
    getAbsolutePath,
)
from Furious.Utility.Translator import gettext as _
from Furious.Utility.Proxy import Proxy

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication
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


class HttpProxyServerError(Exception):
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
        self.httpProxyConfErrorBox = MessageBox()

        self.proxyServer = ''

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
        self.Hysteria = Hysteria()

    def XrayCoreExitCallback(self, exitcode):
        if self.coreName:
            # If core is running
            assert self.coreRunning
            assert self.coreName == XrayCore.name()

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

    def HysteriaExitCallback(self, exitcode):
        if self.coreName:
            # If core is running
            assert self.coreRunning
            assert self.coreName == Hysteria.name()

        if exitcode == Hysteria.ExitCode.ConfigurationError:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{Hysteria.name()}: {_("Invalid server configuration")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{Hysteria.name()}: {_("Invalid server configuration")}'
                )

                return

        if exitcode == Hysteria.ExitCode.RemoteNetworkError:
            if not self.isConnecting():
                # Protect connecting action. Mandatory
                return self.disconnectAction(
                    f'{Hysteria.name()}: {_("Connection to server has been lost")}'
                )
            else:
                self.coreRunning = False
                self.disconnectReason = (
                    f'{Hysteria.name()}: {_("Connection to server has been lost")}'
                )

                return

        if not self.isConnecting():
            # Protect connecting action. Mandatory
            self.disconnectAction(
                f'{Hysteria.name()}: {_("Core terminated unexpectedly")}'
            )
        else:
            self.coreRunning = False
            self.disconnectReason = (
                f'{Hysteria.name()}: {_("Core terminated unexpectedly")}'
            )

    def stopCore(self):
        # Stop any potentially running core
        self.XrayCore.stop()
        self.Hysteria.stop()

    def showConnectingProgressBar(self):
        if QApplication.instance().ShowProgressBarWhenConnecting == Switch.ON_:
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

        QApplication.instance().tray.RoutingAction.setDisabled(value)

    def setConnectingStatus(self, showProgressBar=True):
        if showProgressBar:
            self.showConnectingProgressBar()

        # Do not accept new action
        self.setDisabledAction(True)
        self.setText(_('Connecting'))
        self.setIcon(bootstrapIcon('lock-fill.svg'))

        QApplication.instance().tray.setPlainIcon()

    def setConnectedStatus(self):
        self.hideConnectingProgressBar(done=True)
        self.setDisabledAction(False)

        QApplication.instance().tray.setConnectedIcon()

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

        self.XrayCore.registerExitCallback(None)
        self.Hysteria.registerExitCallback(None)

        self.stopCore()

        self.hideConnectingProgressBar()
        self.setText(_('Connect'))
        self.setIcon(bootstrapIcon('unlock-fill.svg'))
        self.setChecked(False)

        QApplication.instance().Connect = Switch.OFF
        QApplication.instance().tray.setPlainIcon()

        self.proxyServer = ''

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
    def MainWidget(self):
        # Handy reference
        return QApplication.instance().MainWidget

    @property
    def activatedServer(self):
        try:
            activatedIndex = int(QApplication.instance().ActivatedItemIndex)

            if activatedIndex < 0:
                return None
            else:
                return self.MainWidget.ServerList[activatedIndex]['config']

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

    def errorHttpProxyConf(self):
        self.httpProxyConfErrorBox.setIcon(MessageBox.Icon.Critical)
        self.httpProxyConfErrorBox.setWindowTitle(_('Unable to connect'))
        self.httpProxyConfErrorBox.setText(
            _(
                f'{APPLICATION_NAME} cannot find any valid http proxy '
                f'endpoint in your server configuration.'
            )
        )
        self.httpProxyConfErrorBox.setInformativeText(
            _('Please complete your server configuration.')
        )

        # Show the MessageBox and wait for user to close it
        self.httpProxyConfErrorBox.exec()

    def configureCore(self):
        def validateProxyServer(server):
            # Validate proxy server
            try:
                host, port = server.split(':')

                if int(port) < 0 or int(port) > 65535:
                    raise ValueError
            except Exception:
                # Any non-exit exceptions

                self.reset()
                self.errorHttpProxyConf()

                return False
            else:
                self.proxyServer = server

                return True

        self.stopCore()

        self.XrayCore.registerExitCallback(
            lambda exitcode: self.XrayCoreExitCallback(exitcode)
        )
        self.Hysteria.registerExitCallback(
            lambda exitcode: self.HysteriaExitCallback(exitcode)
        )

        proxyServer = None

        if Intellisense.getCoreType(self.coreJSON) == XrayCore.name():
            # Assuming is XrayCore configuration
            proxyHost = None
            proxyPort = None

            try:
                for inbound in self.coreJSON['inbounds']:
                    if inbound['protocol'] == 'http':
                        proxyHost = inbound['listen']
                        proxyPort = inbound['port']

                        # Note: If there are multiple http inbounds
                        # satisfied, the first one will be chosen.
                        break

                if proxyHost is None or proxyPort is None:
                    # No HTTP proxy endpoint configured
                    raise HttpProxyServerError

                proxyServer = f'{proxyHost}:{proxyPort}'
            except (KeyError, HttpProxyServerError):
                self.reset()
                self.errorHttpProxyConf()
            else:
                if validateProxyServer(proxyServer):
                    self.coreRunning = True

                    routing = QApplication.instance().Routing

                    logger.info(f'Core {XrayCore.name()} configured')
                    logger.info(f'Routing is {routing}')

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

                    if routing == 'Bypass':
                        self.coreJSON['routing'] = {
                            'domainStrategy': 'IPIfNonMatch',
                            'domainMatcher': 'hybrid',
                            'rules': (
                                # ads
                                {
                                    'type': 'field',
                                    'outboundTag': 'block',
                                    'domain': ['geosite:category-ads-all'],
                                },
                                # geosite
                                {
                                    'type': 'field',
                                    'outboundTag': 'direct',
                                    'domain': ['geosite:cn'],
                                },
                                # geoip
                                {
                                    'type': 'field',
                                    'outboundTag': 'direct',
                                    'ip': ['geoip:private', 'geoip:cn'],
                                },
                                # Proxy everything
                                {
                                    'type': 'field',
                                    'port': '0-65535',
                                    'outboundTag': 'proxy',
                                },
                            ),
                        }
                    if routing == 'Global':
                        self.coreJSON['routing'] = {
                            'domainStrategy': 'IPIfNonMatch',
                            'domainMatcher': 'hybrid',
                            'rules': (
                                # Proxy everything
                                {
                                    'type': 'field',
                                    'port': '0-65535',
                                    'outboundTag': 'proxy',
                                },
                            ),
                        }
                    if routing == 'Custom':
                        # Assign user routing
                        self.coreJSON['routing'] = self.XrayRouting

                    # Refresh configuration modified before. User cannot feel
                    self.coreText = ujson.dumps(
                        self.coreJSON, ensure_ascii=False, escape_forward_slashes=False
                    )
                    # Start core
                    self.XrayCore.start(self.coreText)

            return XrayCore.name()

        if Intellisense.getCoreType(self.coreJSON) == Hysteria.name():
            # Assuming is Hysteria configuration
            try:
                proxyServer = self.coreJSON['http']['listen']

                if proxyServer is None:
                    # No HTTP proxy endpoint configured
                    raise HttpProxyServerError
            except (KeyError, HttpProxyServerError):
                self.reset()
                self.errorHttpProxyConf()
            else:
                if validateProxyServer(proxyServer):
                    self.coreRunning = True

                    routing = QApplication.instance().Routing

                    logger.info(f'Core {Hysteria.name()} configured')
                    logger.info(f'Routing is {routing}')

                    if routing == 'Bypass':
                        self.Hysteria.start(
                            self.coreText, Hysteria.rule(), Hysteria.mmdb()
                        )
                    if routing == 'Global':
                        self.Hysteria.start(self.coreText, '', '')
                    if routing == 'Custom':
                        if self.coreJSON.get('acl') is not None:
                            # acl specified
                            if self.coreJSON.get('mmdb') is not None:
                                # mmdb specified. Start "as is"
                                self.Hysteria.start(
                                    self.coreText,
                                    Hysteria.rule(self.coreJSON['acl']),
                                    Hysteria.mmdb(self.coreJSON['mmdb']),
                                )
                            else:
                                # mmdb not specified. Route as global
                                self.Hysteria.start(self.coreText, '', '')
                        else:
                            # acl not specified. Route as global
                            self.Hysteria.start(self.coreText, '', '')

            return Hysteria.name()

        # No matching core
        return ''

    def startConnectionTest(self, showRoutingChangedMessage=False):
        selected = self.testPool[self.testTime]

        self.testTime += 1

        logger.info(f'start connection test. Try: {selected}')

        # Checked. split should not throw exceptions
        proxyHost, proxyPort = self.proxyServer.split(':')

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
                    self.startConnectionTest(showRoutingChangedMessage)
                else:
                    if self.disconnectReason:
                        self.disconnectAction(self.disconnectReason)
                    else:
                        self.disconnectAction(
                            f'{self.coreName}: {_("Connection test failed")}'
                        )
            else:
                logger.info(f'{self.coreName}: connection test success. Connected')

                QApplication.instance().Connect = Switch.ON_

                # Connected status
                self.setConnectedStatus()

                if showRoutingChangedMessage:
                    # Routing changed
                    QApplication.instance().tray.showMessage(
                        _('Routing changed: ')
                        + _(
                            f'{SUPPORTED_ROUTING_DETAIL[QApplication.instance().Routing]}'
                        )
                    )
                else:
                    # Connected
                    QApplication.instance().tray.showMessage(
                        f'{self.coreName}: {_("Connected")}'
                    )

        self.networkReply.finished.connect(finishedCallback)

    def connectAction(self):
        # Connect action
        assert self.textCompare('Connect')

        # Connecting
        self.connectingFlag = True

        if (
            not QApplication.instance().Configuration
            or len(self.MainWidget.ServerList) == 0
        ):
            QApplication.instance().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationEmpty()

            return

        myText = self.activatedServer

        if myText is None:
            QApplication.instance().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationNotActivated()

            return

        if myText == '':
            QApplication.instance().Connect = Switch.OFF

            self.setChecked(False)
            self.connectingFlag = False
            self.errorConfigurationEmpty()

            return

        try:
            myJSON = Configuration.toJSON(myText)
        except Exception:
            # Any non-exit exceptions

            QApplication.instance().Connect = Switch.OFF

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

    def connectingAction(self, showProgressBar=True, showRoutingChangedMessage=False):
        # Connecting status
        self.setConnectingStatus(showProgressBar)

        # Configure connect
        self.coreName = self.configureCore()

        if not self.coreName:
            # No matching core
            self.reset()
            self.errorConfiguration()

            return

        if not self.coreRunning:
            # 1. No valid HTTP proxy endpoint. reset / disconnect has been called

            if self.isConnecting():
                # 2. Core has exited. disconnectReason must not be empty
                assert self.disconnectReason

                self.disconnectAction(self.disconnectReason)

            return

        try:
            Proxy.set(self.proxyServer, PROXY_SERVER_BYPASS)
        except Exception:
            # Any non-exit exceptions

            Proxy.off()

            self.reset()
            self.errorConfiguration()
        else:
            self.moveConnectingProgressBar()
            # Reset try time
            self.testTime = 0
            self.startConnectionTest(showRoutingChangedMessage)

    def disconnectAction(self, reason=''):
        Proxy.off()

        self.reset()

        SupportConnectedCallback.callDisconnectedCallback()

        QApplication.instance().tray.showMessage(reason)

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
