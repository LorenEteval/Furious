from Furious.Action import (
    ConnectAction,
    EditConfigurationAction,
    RoutingAction,
    ImportAction,
    LanguageAction,
    SettingsAction,
    ExitAction,
)
from Furious.Gui.Action import Action, Seperator
from Furious.Widget.Widget import Menu
from Furious.Utility.Constants import (
    APP,
    APPLICATION_NAME,
    APPLICATION_VERSION,
    PLATFORM,
)
from Furious.Utility.Utility import bootstrapIcon, StateContext, Switch
from Furious.Utility.Translator import Translatable, gettext as _
from Furious.Utility.Proxy import Proxy
from Furious.Utility.StartupOnBoot import StartupOnBoot

from PySide6 import QtCore
from PySide6.QtWidgets import QSystemTrayIcon

import logging

logger = logging.getLogger(__name__)


class SystemTrayIcon(Translatable, QSystemTrayIcon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setPlainIcon()
        self.activated.connect(self.handleActivated)

        actions = [
            ConnectAction(),
            RoutingAction(),
            Seperator(),
            ImportAction(),
            EditConfigurationAction(),
            Seperator(),
            LanguageAction(),
            SettingsAction(),
            Seperator(),
            ExitAction(),
        ]

        for action in actions:
            if isinstance(action, Action):
                if hasattr(self, f'{action}'):
                    logger.warning(f'{self} already has action {action}')

                setattr(self, f'{action}', action)

        self._menu = Menu(*actions)

        self.setContextMenu(self._menu)

    def bootstrap(self):
        if APP().StartupOnBoot == Switch.ON_:
            # Rrefresh startup application location
            StartupOnBoot.on_()

        if APP().Connect == Switch.ON_:
            # Trigger connect action
            self.ConnectAction.trigger()

    def showMessage(self, msg, *args, **kwargs):
        if msg:
            super().showMessage(_(APPLICATION_NAME), msg, *args, **kwargs)

    def setPlainIcon(self):
        if PLATFORM == 'Darwin':
            # Darker
            self.setIcon(bootstrapIcon('rocket-takeoff-dark.svg'))
        else:
            self.setIcon(bootstrapIcon('rocket-takeoff.svg'))

    def setConnectedIcon(self):
        if PLATFORM == 'Darwin':
            # Darker
            self.setIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
        else:
            self.setIcon(bootstrapIcon('rocket-takeoff-connected.svg'))

    @QtCore.Slot(QSystemTrayIcon.ActivationReason)
    def handleActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            APP().MainWidget.show()

    def setApplicationToolTip(self):
        self.setToolTip(f'{_(APPLICATION_NAME)} {APPLICATION_VERSION}')

    def retranslate(self):
        # Nothing to do
        pass
