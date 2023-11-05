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

from Furious.Action import (
    ConnectAction,
    RoutingAction,
    ImportAction,
    EditConfigurationAction,
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
from Furious.Utility.Utility import (
    bootstrapIcon,
    StateContext,
    Switch,
    isAdministrator,
    isWindows7,
)
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

        # Some old version PySide6 does not have setMenu method
        # for QAction. Protect it. Currently only used in SystemTrayIcon
        if hasattr(Action, 'setMenu'):
            logger.info('contextMenu uses setMenu implementation')

            for action in actions:
                if isinstance(action, Action):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

            self._menu = Menu(*actions)
            self.setContextMenu(self._menu)
        else:
            logger.info('contextMenu uses addMenu implementation')

            self._refs = []
            self._menu = Menu()

            for action in actions:
                if isinstance(action, Action):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

                    if action._menu is None:
                        self._menu.addAction(action)
                    else:
                        menu = Menu(*action._menu._actions, title=action.text())
                        menu.setIcon(action.icon())

                        self._refs.append(menu)
                        self._menu.addMenu(menu)
                else:
                    self._menu.addSeparator()

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
        if PLATFORM == 'Darwin' or isWindows7():
            # Darker
            self.setIcon(bootstrapIcon('rocket-takeoff-dark.svg'))
        else:
            self.setIcon(bootstrapIcon('rocket-takeoff.svg'))

    def setConnectedIcon(self):
        if isAdministrator():
            self.setIcon(bootstrapIcon('rocket-takeoff-admin-connected.svg'))
        else:
            if PLATFORM == 'Darwin' or isWindows7():
                # Darker
                self.setIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
            else:
                self.setIcon(bootstrapIcon('rocket-takeoff-connected.svg'))

    @QtCore.Slot(QSystemTrayIcon.ActivationReason)
    def handleActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            APP().ServerWidget.show()

    def setApplicationToolTip(self):
        self.setToolTip(f'{_(APPLICATION_NAME)} {APPLICATION_VERSION}')

    def retranslate(self):
        # Nothing to do
        pass
