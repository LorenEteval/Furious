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

"""Own the application connection lifecycle independently from its UI."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import ServerProfile
from Furious.Plugins import getPluginRegistry
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Repository import Storage
from Furious.Service import (
    TUN2SOCKS_LOG_CATEGORY,
    ConnectionManager,
    UpdateManager,
    coreLogCallback,
)

from PySide6 import QtCore

from dataclasses import dataclass
from enum import Enum

import queue
import logging
import functools

__all__ = ['ConnectionController', 'ConnectionError', 'ConnectionState']

logger = logging.getLogger(__name__)

registerAppSettings('Connect', isBinary=True)
registerAppSettings('CustomProxyBypass')


class ConnectionState(Enum):
    """Describe the application connection lifecycle."""

    Disconnected = 'Connect'
    Connecting = 'Connecting'
    Connected = 'Disconnect'
    Disconnecting = 'Disconnecting'


@dataclass(frozen=True)
class ConnectionError:
    """Describe a user-facing connection error without presenting it."""

    title: str
    message: str
    details: str = ''


def validateProxyServer(server) -> bool:
    """Return whether *server* is a valid host and TCP port pair."""
    try:
        _host, port = parseHostPort(server)

        if int(port) < 0 or int(port) > 65535:
            raise ValueError
    except Exception:
        return False

    return True


class ConnectionController(QtCore.QObject):
    """Coordinate one connection lifecycle and publish observable state."""

    stateChanged = QtCore.Signal(object)
    activeConfigurationChanged = QtCore.Signal(object)
    interactionEnabledChanged = QtCore.Signal(bool)
    processesChanged = QtCore.Signal(object)
    progressStarted = QtCore.Signal()
    progressFinished = QtCore.Signal(bool)
    notificationRequested = QtCore.Signal(str)
    errorOccurred = QtCore.Signal(object)

    def __init__(self, parent=None, *, coreManager=None, updatesManager=None):
        """Initialize reusable runtime services and a disconnected state."""
        super().__init__(parent)

        self._actionQueue = queue.Queue()
        self._coreManager = coreManager or ConnectionManager()
        self._updatesManager = updatesManager or UpdateManager()
        self._state = ConnectionState.Disconnected
        self._activeConfiguration = None
        self._lastError = None

        self._actionTimer = QtCore.QTimer(self)
        self._actionTimer.timeout.connect(self._callActionFromQueue)

    @property
    def state(self) -> ConnectionState:
        """Return the current connection lifecycle state."""
        return self._state

    @property
    def activeConfiguration(self):
        """Return the profile owned by the current connection lifecycle."""
        return self._activeConfiguration

    @property
    def processes(self):
        """Return an immutable snapshot of managed core processes."""
        return tuple(self._coreManager.processesPool)

    @property
    def lastError(self):
        """Return the last user-facing connection error, if any."""
        return self._lastError

    @property
    def interactionEnabled(self) -> bool:
        """Return whether connection-dependent settings may be changed."""
        return self.state not in (
            ConnectionState.Connecting,
            ConnectionState.Disconnecting,
        )

    def isConnected(self) -> bool:
        """Return whether the connection is established."""
        return self.state is ConnectionState.Connected

    def isConnecting(self) -> bool:
        """Return whether the connection is starting."""
        return self.state is ConnectionState.Connecting

    def isDisconnecting(self) -> bool:
        """Return whether the connection is stopping."""
        return self.state is ConnectionState.Disconnecting

    def _setState(self, state: ConnectionState):
        """Publish an atomic lifecycle transition."""
        if state is self._state:
            return

        interactionWasEnabled = self.interactionEnabled

        self._state = state
        self.stateChanged.emit(state)

        if self.interactionEnabled != interactionWasEnabled:
            self.interactionEnabledChanged.emit(self.interactionEnabled)

    def _setActiveConfiguration(self, configuration):
        """Publish the profile owned by the current lifecycle."""
        if configuration is self._activeConfiguration:
            return

        self._activeConfiguration = configuration
        self.activeConfigurationChanged.emit(configuration)

    def _setProcessesChanged(self):
        """Publish a stable process snapshot after runtime changes."""
        self.processesChanged.emit(self.processes)

    def _reportError(self, message: str, details: str = ''):
        """Publish a user-facing error without choosing its presentation."""
        self._lastError = ConnectionError(_('Unable to connect'), message, details)
        self.errorOccurred.emit(self._lastError)

    def _reset(self):
        """Restore disconnected state after all runtime resources stop."""
        self.progressFinished.emit(True)
        self._setActiveConfiguration(None)

        AppSettings.turnOFF('Connect')

        self._setState(ConnectionState.Disconnected)

    def _startConnecting(self):
        """Enter the connecting state and request progress presentation."""
        self._setState(ConnectionState.Connecting)
        self.progressStarted.emit()

    def _finishConnecting(self):
        """Enter the connected state and notify connection-aware consumers."""
        self.progressFinished.emit(True)

        AppSettings.turnON_('Connect')

        self._setState(ConnectionState.Connected)

        Mixins.ConnectionAware.callConnectedCallback()

    def startConnection(self, configuration=None) -> bool:
        """Start *configuration* or the active repository profile."""
        # QObject already exposes a legacy ``connect`` attribute in PySide.
        # Using an explicit operation name avoids shadowing Qt signal plumbing.
        if self.state is not ConnectionState.Disconnected:
            return False

        if configuration is None:
            servers = Storage.UserServers()

            if not servers:
                AppSettings.turnOFF('Connect')

                self._reportError(
                    _('Server configuration empty. Please configure your server first')
                )

                return False

            activeIndex = Storage.UserActivatedItemIndex()

            if activeIndex < 0 or activeIndex >= len(servers):
                AppSettings.turnOFF('Connect')

                self._reportError(
                    _('Select and press Enter to activate configuration and connect')
                )

                return False

            configuration = servers[activeIndex]

        if not isinstance(configuration, ServerProfile):
            AppSettings.turnOFF('Connect')

            self._reportError(_('Please complete your server configuration'))

            return False

        @forceToLocalhostIfPossible()
        def getHttpProxy() -> str:
            """Return the system-proxy endpoint for this connection."""
            return configuration.httpProxy()

        httpProxy = getHttpProxy()

        if not validateProxyServer(httpProxy):
            AppSettings.turnOFF('Connect')

            self._reportError(
                _(
                    f'{APPLICATION_NAME} cannot find any valid http proxy endpoint in the configuration'
                ),
                _('Please complete your server configuration'),
            )

            return False

        self._lastError = None
        self._setActiveConfiguration(configuration)
        self._startConnecting()

        logManager = AppLogManager()
        # Retain application diagnostics while starting a fresh runtime log.
        logManager.clear(runtimeOnly=True)

        try:
            success = self._coreManager.start(
                configuration,
                routing=AppSettings.get('Routing'),
                exitCallback=self.coreExitCallback,
                msgCallbackCore=coreLogCallback(logManager),
                msgCallbackTUN_=logManager.callback(
                    TUN2SOCKS_LOG_CATEGORY,
                    source='Tun2socks',
                ),
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'failed to start core manager: {ex}')

            success = False

        self._setProcessesChanged()

        if not self._actionQueue.empty():
            while not self._actionQueue.empty():
                self._callActionFromQueue()

            return False

        if not success:
            logger.error('failed to start core manager')

            self.startDisconnection(
                f'{configuration.coreName()}: ' + _('Unknown error')
            )

            return False

        settings = AppSettings.get('CustomProxyBypass')

        proxyServerBypass = (
            settings if isinstance(settings, str) else PROXY_SERVER_BYPASS
        )

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

            self.startDisconnection(
                f'{configuration.coreName()}: ' + _('Unknown error')
            )

            return False

        self._finishConnecting()
        self.notificationRequested.emit(
            f'{configuration.coreName()}: ' + _('Connected')
        )

        interval = CORE_CHECK_ALIVE_INTERVAL

        if AppSettings.isStateON_('PowerSaveMode'):
            interval *= 2

        self._actionTimer.start(interval)
        self._runPostConnectTasksOnce()

        return True

    def startDisconnection(self, notification: str = '') -> bool:
        """Stop the active runtime and optionally request a notification."""
        if self.state is ConnectionState.Disconnected:
            return False

        self._setState(ConnectionState.Disconnecting)
        self._actionTimer.stop()

        try:
            SystemProxy.off()
        except Exception as ex:
            logger.error(f'failed to turn off system proxy: {ex}')

        try:
            self._coreManager.stopAll()
        except Exception as ex:
            # Always complete the state transition. A cleanup failure must not
            # strand every connection UI in the disabled Disconnecting state.
            logger.error(f'failed to stop connection runtime: {ex}')

        self._setProcessesChanged()
        self._reset()

        while not self._actionQueue.empty():
            try:
                self._actionQueue.get_nowait()
            except Exception:
                pass

        Mixins.ConnectionAware.callDisconnectedCallback()

        if notification:
            self.notificationRequested.emit(notification)

        return True

    def startReconnection(self, notification: str = '') -> bool:
        """Restart the active repository profile when lifecycle state permits."""
        if self.state in (
            ConnectionState.Connecting,
            ConnectionState.Disconnecting,
        ):
            return False

        if self.isConnected():
            self.startDisconnection(notification)

        return self.startConnection()

    def restoreStartupState(self) -> bool:
        """Restore the persisted connection preference during application startup."""
        if not AppSettings.isStateON_('Connect'):
            return False

        return self.startConnection()

    def shutdown(self):
        """Stop runtime resources without changing the next-start preference."""
        reconnectOnStartup = AppSettings.isStateON_('Connect')

        if self.state is not ConnectionState.Disconnected:
            self.startDisconnection()

        if reconnectOnStartup:
            AppSettings.turnON_('Connect')

    def toggle(self) -> bool:
        """Perform the operation represented by the current stable state."""
        if self.state is ConnectionState.Disconnected:
            return self.startConnection()

        if self.state is ConnectionState.Connected:
            return self.startDisconnection(_('Disconnected'))

        return False

    @callOnceOnly
    def _runPostConnectTasksOnce(self):
        """Run application update and plugin maintenance after first connect."""

        def newVersionCallback(newVersion):
            """Request a notification when a newer version is available."""
            self.notificationRequested.emit(
                f'{APPLICATION_NAME} {newVersion} ' + _('is available to download')
            )

        connectedHttpProxy = Storage.Extras.UserHttpProxy()

        self._updatesManager.configureHttpProxy(connectedHttpProxy)
        self._updatesManager.checkForUpdates(
            showMessageBox=False,
            hasNewVersionCallback=newVersionCallback,
        )

        getPluginRegistry().afterConnected(connectedHttpProxy)

    @QtCore.Slot()
    def _callActionFromQueue(self):
        """Run one core-thread action on the controller's Qt thread."""
        try:
            action = self._actionQueue.get_nowait()
        except queue.Empty:
            return
        except Exception:
            # Any non-exit exceptions

            return

        if callable(action):
            action()

    def coreExitCallback(self, core: CoreProcess, exitcode: int):
        """Translate a core exit into a queued lifecycle operation."""

        def putItem(item):
            """Queue an operation without allowing worker failures to escape."""
            try:
                self._actionQueue.put_nowait(item)
            except Exception:
                # Any non-exit exceptions

                pass

        if exitcode == CoreProcess.ExitCode.SystemShuttingDown.value:
            return None

        if exitcode == CoreProcess.ExitCode.ConfigurationError.value:
            message = f'{core.name()}: ' + _('Invalid server configuration')
        elif exitcode == CoreProcess.ExitCode.ServerStartFailure.value:
            message = f'{core.name()}: ' + _('Failed to start core')
        else:
            pluginMessage = getPluginRegistry().coreExitMessage(core, exitcode)

            message = (
                f'{core.name()}: ' + _(pluginMessage)
                if pluginMessage
                else f'{core.name()}: ' + _('Core terminated unexpectedly')
            )

        putItem(functools.partial(self.startDisconnection, message))

        return None
