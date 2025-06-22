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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from typing import Union

import functools

__all__ = ['SettingsAction']

registerAppSettings('VPNMode', isBinary=True)
registerAppSettings('DarkMode', isBinary=True)
registerAppSettings('UseMonochromeTrayIcon', isBinary=True)

if PLATFORM == 'Darwin':
    registerAppSettings('HideDockIcon', isBinary=True)

registerAppSettings('StartupOnBoot', isBinary=True, default=BinarySettings.ON_)
registerAppSettings('PowerSaveMode', isBinary=True, default=BinarySettings.ON_)
registerAppSettings(
    'ShowProgressBarWhenConnecting', isBinary=True, default=BinarySettings.ON_
)
registerAppSettings('ShowTabAndSpacesInEditor', isBinary=True)

# Administrator, root
TRANSLATABLE_TUN_MODE = [
    _('TUN Mode Disabled (Administrator)'),
    _('TUN Mode Disabled (root)'),
]


class TUNModeAction(AppQAction):
    def __init__(self, **kwargs):
        if isAdministrator():
            super().__init__(_('TUN Mode'), **kwargs)
        else:
            super().__init__(_(f'TUN Mode Disabled ({ADMINISTRATOR_NAME})'), **kwargs)

            self.setDisabled(True)

    def triggeredCallback(self, checked):
        assert isAdministrator()

        if checked:
            AppSettings.turnON_('VPNMode')
        else:
            AppSettings.turnOFF('VPNMode')

        showNewChangesNextTimeMBox()


class SettingsChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Dark Mode'):
            # Settings turn on/off order matters here
            if checked:
                AppSettings.turnON_('DarkMode')

                try:
                    APP().switchToDarkMode()
                except Exception:
                    # Any non-exit exceptions

                    pass
            else:
                AppSettings.turnOFF('DarkMode')

                try:
                    APP().switchToAutoMode()
                except Exception:
                    # Any non-exit exceptions

                    pass
        elif self.textCompare('Use Monochrome Tray Icon'):
            # Settings turn on/off order matters here
            if checked:
                AppSettings.turnON_('UseMonochromeTrayIcon')

                APP().systemTray.setMonochromeIcon()
            else:
                AppSettings.turnOFF('UseMonochromeTrayIcon')

                if APP().isSystemTrayConnected():
                    APP().systemTray.setConnectedIcon()
                else:
                    APP().systemTray.setDisconnectedIcon()
        elif self.textCompare('Hide Dock Icon'):
            if checked:
                APP().installDockIconVisibilityFeature()

                AppSettings.turnON_('HideDockIcon')
            else:
                APP().installDockIconVisibilityFeature(remove=True)

                AppSettings.turnOFF('HideDockIcon')
        elif self.textCompare('Startup On Boot'):
            if checked:
                StartupOnBoot.on_()

                AppSettings.turnON_('StartupOnBoot')
            else:
                StartupOnBoot.off()

                AppSettings.turnOFF('StartupOnBoot')
        elif self.textCompare('Power Save Mode'):
            if checked:
                AppSettings.turnON_('PowerSaveMode')
            else:
                AppSettings.turnOFF('PowerSaveMode')

            showNewChangesNextTimeMBox()
        elif self.textCompare('Show Progress Bar When Connecting'):
            if checked:
                AppSettings.turnON_('ShowProgressBarWhenConnecting')
            else:
                AppSettings.turnOFF('ShowProgressBarWhenConnecting')
        elif self.textCompare('Show Tab And Spaces In Editor'):
            if checked:
                APP().mainWindow.showTabAndSpaces()

                AppSettings.turnON_('ShowTabAndSpacesInEditor')
            else:
                APP().mainWindow.hideTabAndSpaces()

                AppSettings.turnOFF('ShowTabAndSpacesInEditor')


class SettingsAction(AppQAction):
    def __init__(self, **kwargs):
        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            tunActions = [
                TUNModeAction(
                    checkable=True,
                    checked=AppSettings.isStateON_('VPNMode'),
                ),
                AppQAction(
                    _('Customize TUN Settings...'),
                    icon=bootstrapIcon('diagram-3.svg'),
                    checkable=False,
                    callback=lambda: APP().mainWindow.getGuiTUNSettings().open(),
                ),
                AppQSeperator(),
            ]
        else:
            tunActions = [None]

        if PLATFORM == 'Darwin':
            hideDockIconAction = [
                SettingsChildAction(
                    _('Hide Dock Icon'),
                    checkable=True,
                    checked=AppSettings.isStateON_('HideDockIcon'),
                )
            ]
        else:
            hideDockIconAction = [None]

        super().__init__(
            _('Settings'),
            icon=bootstrapIcon('gear-wide-connected.svg'),
            menu=AppQMenu(
                *tunActions,
                SettingsChildAction(
                    _('Dark Mode'),
                    checkable=True,
                    checked=AppSettings.isStateON_('DarkMode'),
                ),
                SettingsChildAction(
                    _('Use Monochrome Tray Icon'),
                    checkable=True,
                    checked=AppSettings.isStateON_('UseMonochromeTrayIcon'),
                ),
                *hideDockIconAction,
                AppQSeperator(),
                SettingsChildAction(
                    _('Startup On Boot'),
                    checkable=True,
                    checked=AppSettings.isStateON_('StartupOnBoot'),
                ),
                SettingsChildAction(
                    _('Power Save Mode'),
                    checkable=True,
                    checked=AppSettings.isStateON_('PowerSaveMode'),
                ),
                AppQSeperator(),
                SettingsChildAction(
                    _('Show Progress Bar When Connecting'),
                    checkable=True,
                    checked=AppSettings.isStateON_('ShowProgressBarWhenConnecting'),
                ),
                SettingsChildAction(
                    _('Show Tab And Spaces In Editor'),
                    checkable=True,
                    checked=AppSettings.isStateON_('ShowTabAndSpacesInEditor'),
                ),
            ),
            useActionGroup=False,
            **kwargs,
        )

    def getTUNModeAction(self) -> Union[AppQAction, None]:
        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            # 1st action
            return self._menu.actions()[0]
        else:
            return None
