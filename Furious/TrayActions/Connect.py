from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Library import *
from Furious.Core import *
from Furious.Widget.ConnectProgressBar import ConnectProgressBar

__all__ = ['ConnectAction']

registerAppSettings('Connect', isBinary=True)


class ConnectAction(AppQAction):
    def __init__(self):
        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
        )

        self.coreManager = CoreManager()
        self.progressBar = ConnectProgressBar()

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

        APP().tray.RoutingAction.setDisabled(value)

        if isAdministrator():
            VPNModeAction = APP().tray.SettingsAction.getVPNModeAction()

            if VPNModeAction is not None:
                VPNModeAction.setDisabled(value)

    def doneConnected(self) -> bool:
        return self.textCompare('Disconnect')

    def doConnecting(self):
        self.showProgressBar()
        # Do not accept new action
        self.setDisabledAction(True)
        self.setText(_('Connecting'))
        self.setIcon(bootstrapIcon('lock-fill.svg'))

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

        self.coreManager.stopAll()
        self.reset()

        SupportConnectedCallback.callDisconnectedCallback()

    def doConnect(self):
        # Connect action
        assert self.textCompare('Connect')

        if not AS_UserServers():
            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            mbox = AppQMessageBox()
            mbox.setIcon(AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Unable to connect'))
            mbox.setText(
                _('Server configuration empty. Please configure your server first.')
            )

            # Show the MessageBox and wait for user to close it
            mbox.exec()

            return

        if AS_UserActivatedItemIndex() < 0:
            AppSettings.turnOFF('Connect')

            self.setChecked(False)

            mbox = AppQMessageBox()
            mbox.setIcon(AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Unable to connect'))
            mbox.setText(
                _('Select and double click to activate configuration and connect.')
            )

            # Show the MessageBox and wait for user to close it
            mbox.exec()

            return

        try:
            config = AS_UserServers()[AS_UserActivatedItemIndex()]
        except Exception:
            # Any non-exit exceptions

            self.setChecked(False)

            return

        self.doConnecting()

        assert isinstance(config, ConfigurationFactory)

        success = self.coreManager.start(
            config,
            routing=AppSettings.get('Routing'),
            exitCallback=None,
        )

        SystemProxy.set(config.httpProxyEndpoint(), PROXY_SERVER_BYPASS)

        self.doConnected()

        APP().tray.showMessage(f'{config.coreName()}: ' + _('Connected'))

    def triggeredCallback(self, checked):
        if checked:
            self.doConnect()
        else:
            # Disconnect action
            assert self.textCompare('Disconnect')

            self.doDisconnect()

            APP().tray.showMessage(_('Disconnected'))
