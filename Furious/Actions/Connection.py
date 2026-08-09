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
from Furious.Service import ConnectionManager, UpdateManager
from Furious.Widget.ConnectionProgressWidget import ConnectionProgressWidget

from PySide6 import QtCore

import queue
import logging
import functools

__all__ = ['ConnectAction']

logger = logging.getLogger(__name__)

registerAppSettings('Connect', isBinary=True)


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
    """Handle the connect action."""

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

        self.actionTimer = QtCore.QTimer()
        self.actionTimer.timeout.connect(lambda: self.callActionFromQueue())

        self.updatesManager = UpdateManager()

    def reset(self):
        """Restore the connect action to its initial state."""
        self.hideProgressBar(True)
        self.setText(_('Connect'))
        self.setIcon(bootstrapIcon('unlock-fill.svg'))
        self.setChecked(False)

        AppSettings.turnOFF('Connect')

        # Accept new action
        self.setDisabledAction(False)

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

        APP().systemTray.RoutingAction.setDisabled(value)
        APP().systemTray.SystemProxyAction.setDisabled(value)

        # TODO: Need this?
        if PLATFORM == 'Linux' or SystemRuntime.isAdmin():
            TUNModeAction = APP().systemTray.SettingsAction.getTUNModeAction()
            TUNModeAction.setDisabled(value)

    def isConnected(self) -> bool:
        """Return whether connected."""
        return self.textCompare('Disconnect')

    def isConnecting(self):
        """Return whether connecting."""
        return self.textCompare('Connecting')

    def doConnecting(self):
        """Handle do connecting for the connect action."""
        self.setText(_('Connecting'))
        self.setIcon(bootstrapIcon('lock-fill.svg'))
        # Do not accept new action
        self.setDisabledAction(True)
        self.showProgressBar()

    def doConnected(self):
        """Handle do connected for the connect action."""
        self.hideProgressBar(True)
        # Connected
        self.setText(_('Disconnect'))

        AppSettings.turnON_('Connect')

        Mixins.ConnectionAware.callConnectedCallback()

        # Accept new action
        self.setDisabledAction(False)

    def doDisconnect(self):
        """Handle do disconnect for the connect action."""
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
        assert self.textCompare('Connect')

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

            self.doConnecting()

            # Clear previous log
            AppLoggerWindow.Core().clear()
            AppLoggerWindow.TUN_().clear()

            success = self.coreManager.start(
                config,
                routing=AppSettings.get('Routing'),
                exitCallback=self.coreExitCallback,
                msgCallbackCore=lambda line: AppLoggerWindow.Core().appendLine(line),
                msgCallbackTUN_=lambda line: AppLoggerWindow.TUN_().appendLine(line),
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
        if checked:
            self.doConnect()
        else:
            # Disconnect action
            assert self.textCompare('Disconnect')

            self.doDisconnectWithTrayMessage(_('Disconnected'))
