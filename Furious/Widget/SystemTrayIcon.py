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

from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.TrayActions import *

from PySide6 import QtCore
from PySide6.QtWidgets import QSystemTrayIcon

import logging
import platform
import darkdetect

logger = logging.getLogger(__name__)

__all__ = ['SystemTrayIcon']


class SystemTrayIcon(
    QTranslatable,
    SupportConnectedCallback,
    SupportThemeChangedCallback,
    QSystemTrayIcon,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        actions = [
            ConnectAction(isTrayAction=True),
            RoutingAction(isTrayAction=True),
            SystemProxyAction(isTrayAction=True),
            AppQSeperator(),
            ImportAction(isTrayAction=True),
            EditConfigurationAction(isTrayAction=True),
            AppQSeperator(),
            LanguageAction(isTrayAction=True),
            SettingsAction(isTrayAction=True),
            AppQSeperator(),
            ExitAction(isTrayAction=True),
        ]

        # Some old version PySide6 does not have setMenu method
        # for QAction. Protect it. Currently only used in SystemTrayIcon
        if hasattr(AppQAction, 'setMenu'):
            logger.info('contextMenu uses setMenu implementation')

            for action in actions:
                if isinstance(action, AppQAction):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

            self._menu = AppQMenu(*actions)
            self.setContextMenu(self._menu)
        else:
            logger.info('contextMenu uses addMenu implementation')

            self._refs = []
            self._menu = AppQMenu()

            for action in actions:
                if isinstance(action, AppQAction):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

                    if action._menu is None:
                        self._menu.addAction(action)
                    else:
                        menu = AppQMenu(*action._menu._actions, title=action.text())
                        menu.setIcon(action.icon())

                        self._refs.append(menu)
                        self._menu.addMenu(menu)
                else:
                    self._menu.addSeparator()

            self.setContextMenu(self._menu)

        self.setDisconnectedIcon()
        self.activated.connect(self.handleActivated)

    def bootstrap(self):
        if AppSettings.isStateON_('StartupOnBoot'):
            # Rrefresh startup application location
            StartupOnBoot.on_()

        if AppSettings.isStateON_('Connect'):
            self.ConnectAction.trigger()

    def showMessage(self, message: str, *args, **kwargs):
        if message:
            super().showMessage(_(APPLICATION_NAME), message, *args, **kwargs)

    def setMonochromeIconByTheme(self, theme):
        def switchMonochrome():
            if theme == 'Dark':
                self.setIcon(bootstrapIconWhite('monochrome-rocket-takeoff.svg'))
            else:
                self.setIcon(bootstrapIcon('monochrome-rocket-takeoff.svg'))

        if PLATFORM == 'Linux':
            # linux. Always use white icon
            self.setIcon(bootstrapIconWhite('monochrome-rocket-takeoff.svg'))
        elif PLATFORM == 'Darwin':
            try:
                release, versioninfo, machine = platform.mac_ver()
                majorRelease = int(release.split('.')[0])

                if majorRelease <= 13:
                    switchMonochrome()
                else:
                    # macOS 14+. Always use white icon
                    self.setIcon(bootstrapIconWhite('monochrome-rocket-takeoff.svg'))
            except Exception:
                # Any non-exit exceptions

                # Fall back to switch
                switchMonochrome()
        else:
            switchMonochrome()

    def setMonochromeIcon(self):
        self.setMonochromeIconByTheme(darkdetect.theme())

    def setDisconnectedIcon(self):
        if AppSettings.isStateON_('UseMonochromeTrayIcon'):
            self.setMonochromeIcon()

            return

        if (
            PLATFORM == 'Darwin'
            or isWindows7()
            or (PLATFORM == 'Windows' and darkdetect.theme() == 'Light')
        ):
            # Darker
            self.setIcon(bootstrapIcon('rocket-takeoff-dark.svg'))
        else:
            self.setIcon(bootstrapIcon('rocket-takeoff.svg'))

    def setConnectedIcon(self):
        if AppSettings.isStateON_('UseMonochromeTrayIcon'):
            self.setMonochromeIcon()

            return

        if isAdministrator():
            self.setIcon(bootstrapIcon('rocket-takeoff-admin-connected.svg'))
        else:
            if (
                PLATFORM == 'Darwin'
                or isWindows7()
                or (PLATFORM == 'Windows' and darkdetect.theme() == 'Light')
            ):
                # Darker
                self.setIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
            else:
                self.setIcon(bootstrapIcon('rocket-takeoff-connected.svg'))

    @QtCore.Slot(QSystemTrayIcon.ActivationReason)
    def handleActivated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            APP().mainWindow.show()

    def setCustomToolTip(self):
        self.setToolTip(f'{_(APPLICATION_NAME)} {APPLICATION_VERSION}')

    def disconnectedCallback(self):
        self.setDisconnectedIcon()

    def connectedCallback(self):
        self.setConnectedIcon()

    def themeChangedCallback(self, theme):
        if AppSettings.isStateON_('UseMonochromeTrayIcon'):
            # 'theme' is not used. Instead, always query current theme
            self.setMonochromeIconByTheme(darkdetect.theme())

            return

        if APP().isSystemTrayConnected():
            self.setConnectedIcon()
        else:
            self.setDisconnectedIcon()

    def retranslate(self):
        # Nothing to do
        pass
