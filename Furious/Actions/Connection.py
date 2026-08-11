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

"""Implement tray actions for connect."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import *
from Furious.Repository import *
from Furious.Plugins import getPluginRegistry
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import (
    TUN2SOCKS_LOG_CATEGORY,
    ConnectionManager,
    UpdateManager,
    coreLogCallback,
)
from Furious.Widget.ConnectionProgressWidget import ConnectionProgressWidget

from PySide6 import QtCore

from enum import Enum

import queue
import logging
import functools

__all__ = ['ConnectionState', 'ConnectAction']

logger = logging.getLogger(__name__)

registerAppSettings('Connect', isBinary=True)


class ConnectionState(Enum):
    """Describe the shared application connection lifecycle."""

    Disconnected = 'Connect'
    Connecting = 'Connecting'
    Connected = 'Disconnect'
    Disconnecting = 'Disconnecting'


_TRANSLATABLE_CONNECTION_STATES = (
    _('Connect'),
    _('Connecting'),
    _('Disconnect'),
    _('Disconnecting'),
)


def validateProxyServer(server) -> bool:
    """Validate proxy server."""
    try:
        host, port = parseHostPort(server)

        if int(port) < 0 or int(port) > 65535:
            raise ValueError
    except Exception:
        # Any non-exit exceptions

        return False
    else:
        return True


class ConnectAction(AppQAction):
    """Own connection operations and expose their state to every UI surface."""

    stateChanged = QtCore.Signal(object)

    def __init__(self, **kwargs):
        """Initialize the ConnectAction."""
        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
            **kwargs,
        )

        self.actionQueue = queue.Queue()
        self.coreManager = ConnectionManager()
        self.progressBar = ConnectionProgressWidget()
        self._state = ConnectionState.Disconnected
        self._activeConfiguration = None

        self.actionTimer = QtCore.QTimer()
        self.actionTimer.timeout.connect(lambda: self.callActionFromQueue())

        self.updatesManager = UpdateManager()

    @property
    def state(self) -> ConnectionState:
        """Return the current connection lifecycle state."""
        return self._state

    @property
    def activeConfiguration(self):
        """Return the configuration owned by the current connection attempt."""
        return self._activeConfiguration

    def _applyStatePresentation(self):
        """Apply the tray action presentation for the shared lifecycle state."""
        state = self.state
        self.setText(_(state.value))
        self.setChecked(
            state
            in (
                ConnectionState.Connecting,
                ConnectionState.Connected,
            )
        )

        if state in (ConnectionState.Connecting, ConnectionState.Connected):
            self.setIcon(bootstrapIcon('lock-fill.svg'))
        else:
            self.setIcon(bootstrapIcon('unlock-fill.svg'))

        self.setDisabledAction(
            state in (ConnectionState.Connecting, ConnectionState.Disconnecting)
        )

    def _setState(self, state: ConnectionState):
        """Publish one atomic lifecycle transition and its action presentation."""
        changed = state is not self._state
        self._state = state
        self._applyStatePresentation()

        if changed:
            self.stateChanged.emit(state)

    def reset(self):
        """Restore the connect action to its initial state."""
        self.hideProgressBar(True)
        self._activeConfiguration = None

        AppSettings.turnOFF('Connect')

        self._setState(ConnectionState.Disconnected)

    def showProgressBar(self):
        """Show progress bar."""
        if AppSettings.isStateON_('ShowProgressBarWhenConnecting'):
            self.progressBar.setValue(0)
            # Update the progress bar every 50ms
            self.progressBar.start(50)
            self.progressBar.show()

        return self

    def hideProgressBar(self, done: bool):
        """Hide progress bar."""
        if done:
            self.progressBar.setValue(100)

        self.progressBar.close()
        self.progressBar.stop()

        return self

    def setDisabledAction(self, value):
        """Set disabled action."""
        self.setDisabled(value)

        try:
            APP().systemTray.RoutingAction.setDisabled(value)
        except (AttributeError, RuntimeError):
            pass

        try:
            APP().mainWindow.settingsPage.setConnectionControlsEnabled(not value)
        except (AttributeError, RuntimeError):
            pass

    def isConnected(self) -> bool:
        """Return whether connected."""
        return self.state is ConnectionState.Connected

    def isConnecting(self):
        """Return whether connecting."""
        return self.state is ConnectionState.Connecting

    def isDisconnecting(self):
        """Return whether disconnecting."""
        return self.state is ConnectionState.Disconnecting

    def doConnecting(self):
        """Handle do connecting for the connect action."""
        self._setState(ConnectionState.Connecting)
        self.showProgressBar()

    def doConnected(self):
        """Handle do connected for the connect action."""
        self.hideProgressBar(True)

        AppSettings.turnON_('Connect')

        self._setState(ConnectionState.Connected)

        Mixins.ConnectionAware.callConnectedCallback()

    def doDisconnect(self):
        """Handle do disconnect for the connect action."""
        if self.state is ConnectionState.Disconnected:
            return

        self._setState(ConnectionState.Disconnecting)

        SystemProxy.off()

        self.actionTimer.stop()

        self.coreManager.stopAll()
        self.reset()

        while not self.actionQueue.empty():
            try:
                unused = self.actionQueue.get_nowait()
            except Exception:
                # Any non-exit exceptions

                pass

        Mixins.ConnectionAware.callDisconnectedCallback()

    def doDisconnectWithTrayMessage(self, message: str):
        """Handle do disconnect with tray message for the connect action."""
        self.doDisconnect()

        APP().systemTray.showMessage(message)

    def doReconnect(self, message=''):
        """Handle do reconnect for the connect action."""
        self.doDisconnectWithTrayMessage(message)
        self.trigger()

    def doConnect(self):
        # Connect action
        """Return the do connect value used by the connect action."""
        assert self.state is ConnectionState.Disconnected

        if not Storage.UserServers():
            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Unable to connect'))
            mbox.setText(
                _('Server configuration empty. Please configure your server first')
            )

            # Show the MessageBox asynchronously
            mbox.open()

            return

        if Storage.UserActivatedItemIndex() < 0:
            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Unable to connect'))
            mbox.setText(
                _('Select and press Enter to activate configuration and connect')
            )

            # Show the MessageBox asynchronously
            mbox.open()

            return

        try:
            config = Storage.UserServers()[Storage.UserActivatedItemIndex()]
        except Exception:
            # Any non-exit exceptions

            AppSettings.turnOFF('Connect')

            self.setChecked(False)
        else:
            assert isinstance(config, ServerProfile)

            @forceToLocalhostIfPossible()
            def getHttpProxy() -> str:
                """Return HTTP proxy."""
                return config.httpProxy()

            httpProxy = getHttpProxy()

            if not validateProxyServer(httpProxy):
                # Proxy server is not valid. Do not connect

                AppSettings.turnOFF('Connect')

                self.setChecked(False)

                mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
                mbox.setWindowTitle(_('Unable to connect'))
                mbox.setText(
                    _(
                        f'{APPLICATION_NAME} cannot find any valid http proxy endpoint in the configuration'
                    )
                )
                mbox.setInformativeText(_('Please complete your server configuration'))

                # Show the MessageBox asynchronously
                mbox.open()

                return

            self._activeConfiguration = config
            self.doConnecting()

            logManager = AppLogManager()
            # Retain application diagnostics while starting a fresh runtime log.
            logManager.clear(runtimeOnly=True)

            success = self.coreManager.start(
                config,
                routing=AppSettings.get('Routing'),
                exitCallback=self.coreExitCallback,
                msgCallbackCore=coreLogCallback(logManager),
                msgCallbackTUN_=logManager.callback(
                    TUN2SOCKS_LOG_CATEGORY,
                    source='Tun2socks',
                ),
            )

            if self.actionQueue.empty():
                if success:
                    # Use custom proxy bypass address if possible
                    settings = AppSettings.get('CustomProxyBypass')

                    if isinstance(settings, str):
                        proxyServerBypass = settings
                    else:
                        proxyServerBypass = PROXY_SERVER_BYPASS

                    try:
                        SystemProxy.set(httpProxy, proxyServerBypass)
                    except Exception as ex:
                        # Any non-exit exceptions

                        logger.error(f'error while setting http proxy: {ex}')
                        logger.error(
                            f'failed to connect successfully. '
                            f'This may be due to improper proxy '
                            f'server bypass settings: {proxyServerBypass}'
                        )

                        self.coreManager.stopAll()
                        self.doDisconnectWithTrayMessage(
                            f'{config.coreName()}: ' + _('Unknown error')
                        )
                    else:
                        self.doConnected()

                        APP().systemTray.showMessage(
                            f'{config.coreName()}: ' + _('Connected')
                        )

                        if AppSettings.isStateON_('PowerSaveMode'):
                            # Power optimization
                            self.actionTimer.start(CORE_CHECK_ALIVE_INTERVAL * 2)
                        else:
                            self.actionTimer.start(CORE_CHECK_ALIVE_INTERVAL)

                        self.doConnectedCallOnceOnly()
                else:
                    logger.error('failed to start core manager')

                    self.coreManager.stopAll()
                    self.doDisconnectWithTrayMessage(
                        f'{config.coreName()}: ' + _('Unknown error')
                    )
            else:
                while not self.actionQueue.empty():
                    self.callActionFromQueue()

    @callOnceOnly
    def doConnectedCallOnceOnly(self):
        """Handle do connected call once only for the connect action."""

        def newVersionCallback(newVersion):
            """Handle the new version callback."""
            APP().systemTray.showMessage(
                f'{APPLICATION_NAME} {newVersion} ' + _('is available to download')
            )

        connectedHttpProxy = Storage.Extras.UserHttpProxy()

        # Check for updates
        self.updatesManager.configureHttpProxy(connectedHttpProxy)
        self.updatesManager.checkForUpdates(
            showMessageBox=False,
            hasNewVersionCallback=newVersionCallback,
        )

        getPluginRegistry().afterConnected(connectedHttpProxy)

    def callActionFromQueue(self):
        """Call action from queue."""
        try:
            action = self.actionQueue.get_nowait()
        except queue.Empty:
            # Queue is empty

            pass
        except Exception:
            # Any non-exit exceptions

            pass
        else:
            if callable(action):
                action()

    def coreExitCallback(self, core: CoreProcess, exitcode: int):
        """Handle the core exit callback."""

        def putItem(item):
            """Handle put item for the connect action."""
            try:
                self.actionQueue.put_nowait(item)
            except Exception:
                # Any non-exit exceptions

                pass

        if exitcode == CoreProcess.ExitCode.SystemShuttingDown.value:
            # System shutting down. Do nothing
            return None

        if exitcode == CoreProcess.ExitCode.ConfigurationError.value:
            putItem(
                functools.partial(
                    self.doDisconnectWithTrayMessage,
                    f'{core.name()}: ' + _('Invalid server configuration'),
                )
            )

            return None

        if exitcode == CoreProcess.ExitCode.ServerStartFailure.value:
            putItem(
                functools.partial(
                    self.doDisconnectWithTrayMessage,
                    f'{core.name()}: ' + _('Failed to start core'),
                )
            )

            return None

        pluginMessage = getPluginRegistry().coreExitMessage(core, exitcode)
        if pluginMessage:
            putItem(
                functools.partial(
                    self.doDisconnectWithTrayMessage,
                    f'{core.name()}: ' + _(pluginMessage),
                )
            )

            return None

        putItem(
            functools.partial(
                self.doDisconnectWithTrayMessage,
                f'{core.name()}: ' + _('Core terminated unexpectedly'),
            )
        )

        return None

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        if self.state is ConnectionState.Disconnected:
            self.doConnect()
        elif self.state is ConnectionState.Connected:
            self.doDisconnectWithTrayMessage(_('Disconnected'))
        else:
            # A disabled transition action should not normally be triggered.
            # Restore its checked presentation if code triggered it directly.
            self._applyStatePresentation()

    def retranslate(self):
        """Refresh the state-derived action text."""
        self._applyStatePresentation()
