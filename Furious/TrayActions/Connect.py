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
from Furious.Utility import *
from Furious.Library import *
from Furious.Core import *
from Furious.Widget.ConnectProgressBar import ConnectProgressBar

from PySide6 import QtCore

import queue
import logging
import functools

__all__ = ['ConnectAction']

logger = logging.getLogger(__name__)

registerAppSettings('Connect', isBinary=True)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Connect',
    'Connecting',
    'Disconnect',
    'Unable to connect',
    'Server configuration empty. Please configure your server first',
    'Select and press Enter to activate configuration and connect',
    f'{APPLICATION_NAME} cannot find any valid http proxy '
    f'endpoint in the configuration',
    'Please complete your server configuration',
    'Connected',
    'Unknown error',
    'Invalid server configuration',
    'Failed to start core',
    'Connection to server has been lost',
    'Core terminated unexpectedly',
    'Disconnected',
)


def validateProxyServer(server) -> bool:
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
    def __init__(self, **kwargs):
        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
            **kwargs,
        )

        self.actionQueue = queue.Queue()
        self.coreManager = CoreManager()
        self.progressBar = ConnectProgressBar()

        self.actionTimer = QtCore.QTimer()
        self.actionTimer.timeout.connect(lambda: self.callActionFromQueue())

    def reset(self):
        self.hideProgressBar(True)
        self.setText(_('Connect'))
        self.setIcon(bootstrapIcon('unlock-fill.svg'))
        self.setChecked(False)

        AppSettings.turnOFF('Connect')

        # Accept new action
        self.setDisabledAction(False)

    def showProgressBar(self):
        if AppSettings.isStateON_('ShowProgressBarWhenConnecting'):
            self.progressBar.setValue(0)
            # Update the progress bar every 50ms
            self.progressBar.start(50)
            self.progressBar.show()

        return self

    def hideProgressBar(self, done: bool):
        if done:
            self.progressBar.setValue(100)

        self.progressBar.hide()
        self.progressBar.stop()

        return self

    def setDisabledAction(self, value):
        self.setDisabled(value)

        APP().systemTray.RoutingAction.setDisabled(value)
        APP().systemTray.SystemProxyAction.setDisabled(value)

        if isAdministrator():
            VPNModeAction = APP().systemTray.SettingsAction.getVPNModeAction()

            if VPNModeAction is not None:
                VPNModeAction.setDisabled(value)

    def isConnected(self) -> bool:
        return self.textCompare('Disconnect')

    def isConnecting(self):
        return self.textCompare('Connecting')

    def doConnecting(self):
        self.setText(_('Connecting'))
        self.setIcon(bootstrapIcon('lock-fill.svg'))
        # Do not accept new action
        self.setDisabledAction(True)
        self.showProgressBar()

    def doConnected(self):
        self.hideProgressBar(True)
        # Connected
        self.setText(_('Disconnect'))

        AppSettings.turnON_('Connect')

        SupportConnectedCallback.callConnectedCallback()

        # Accept new action
        self.setDisabledAction(False)

    def doDisconnect(self):
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

        SupportConnectedCallback.callDisconnectedCallback()

    def doDisconnectWithTrayMessage(self, message: str):
        self.doDisconnect()

        APP().systemTray.showMessage(message)

    def doConnect(self):
        # Connect action
        assert self.textCompare('Connect')

        if not AS_UserServers():
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

        if AS_UserActivatedItemIndex() < 0:
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
            config = AS_UserServers()[AS_UserActivatedItemIndex()]
        except Exception:
            # Any non-exit exceptions

            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            return

        assert isinstance(config, ConfigurationFactory)

        if not validateProxyServer(config.httpProxyEndpoint()):
            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Unable to connect'))
            mbox.setText(
                _(
                    f'{APPLICATION_NAME} cannot find any valid http proxy '
                    f'endpoint in the configuration'
                )
            )
            mbox.setInformativeText(_('Please complete your server configuration'))

            # Show the MessageBox asynchronously
            mbox.open()

            return

        self.doConnecting()

        # Clear previous log
        APP().logViewerWindowCore.clear()
        APP().logViewerWindowTun_.clear()

        success = self.coreManager.start(
            config,
            routing=AppSettings.get('Routing'),
            exitCallback=self.coreExitCallback,
            msgCallback=lambda line: APP().logViewerWindowCore.appendLine(line),
            tunMsgCallback=lambda line: APP().logViewerWindowTun_.appendLine(line),
        )

        if self.actionQueue.empty():
            if success:
                SystemProxy.set(config.httpProxyEndpoint(), PROXY_SERVER_BYPASS)

                self.doConnected()

                APP().systemTray.showMessage(f'{config.coreName()}: ' + _('Connected'))

                self.actionTimer.start(CORE_CHECK_ALIVE_INTERVAL)
            else:
                logger.error('failed to start core manager')

                self.coreManager.stopAll()
                self.doDisconnectWithTrayMessage(
                    f'{config.coreName()}: ' + _('Unknown error')
                )
        else:
            while not self.actionQueue.empty():
                self.callActionFromQueue()

    def callActionFromQueue(self):
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

    def coreExitCallback(self, core: CoreFactory, exitcode: int):
        def putItem(item):
            try:
                self.actionQueue.put_nowait(item)
            except Exception:
                # Any non-exit exceptions

                pass

        if exitcode == CoreFactory.ExitCode.SystemShuttingDown:
            # System shutting down. Do nothing
            return

        if exitcode == CoreFactory.ExitCode.ConfigurationError:
            return putItem(
                functools.partial(
                    self.doDisconnectWithTrayMessage,
                    f'{core.name()}: ' + _('Invalid server configuration'),
                )
            )

        if exitcode == CoreFactory.ExitCode.ServerStartFailure:
            return putItem(
                functools.partial(
                    self.doDisconnectWithTrayMessage,
                    f'{core.name()}: ' + _('Failed to start core'),
                )
            )

        if isinstance(core, Hysteria1):
            if exitcode == Hysteria1.ExitCode.RemoteNetworkError:
                return putItem(
                    functools.partial(
                        self.doDisconnectWithTrayMessage,
                        f'{core.name()}: ' + _('Connection to server has been lost'),
                    )
                )

        return putItem(
            functools.partial(
                self.doDisconnectWithTrayMessage,
                f'{core.name()}: ' + _('Core terminated unexpectedly'),
            )
        )

    def triggeredCallback(self, checked):
        if checked:
            self.doConnect()
        else:
            # Disconnect action
            assert self.textCompare('Disconnect')

            self.doDisconnectWithTrayMessage(_('Disconnected'))
