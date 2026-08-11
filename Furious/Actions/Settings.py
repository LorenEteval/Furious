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

"""Implement tray actions for settings."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

__all__ = ['SettingsAction', 'SettingsController', 'TUNModeAction']

registerAppSettings('VPNMode', isBinary=True)
registerAppSettings('DarkMode', isBinary=True)
registerAppSettings('UseMonochromeTrayIcon', isBinary=True)

if PLATFORM == 'Darwin':
    registerAppSettings('HideDockIcon', isBinary=True)

registerAppSettings('StartupOnBoot', isBinary=True, default=AppBinarySettings.ON_)
registerAppSettings('PowerSaveMode', isBinary=True, default=AppBinarySettings.ON_)
registerAppSettings(
    'ForceToLocalhostWhenSettingLocalProxy',
    isBinary=True,
    default=AppBinarySettings.OFF,
)
registerAppSettings(
    'AutoUpdateAssetFiles', isBinary=True, default=AppBinarySettings.ON_
)
registerAppSettings(
    'ShowProgressBarWhenConnecting', isBinary=True, default=AppBinarySettings.ON_
)
registerAppSettings('ShowTabAndSpacesInEditor', isBinary=True)


class SettingsController:
    """Apply application settings independently from their presentation."""

    @staticmethod
    def setTUNMode(enabled: bool):
        """Persist the global TUN mode and notify active workflows."""
        if PLATFORM != 'Linux':
            assert SystemRuntime.isAdmin()

        if enabled:
            AppSettings.turnON_('VPNMode')
        else:
            AppSettings.turnOFF('VPNMode')

        showMBoxNewChangesNextTime()

    @staticmethod
    def setDarkMode(enabled: bool):
        """Switch between the explicit dark theme and automatic mode."""
        if enabled:
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

    @staticmethod
    def setLanguage(language: str):
        """Persist a supported UI language and refresh translated objects."""
        if language not in SUPPORTED_LANGUAGE:
            return

        if AppSettings.get('Language') != language:
            AppSettings.set('Language', language)
            Mixins.QTranslatable.retranslateAll()

    @staticmethod
    def setMonochromeTrayIcon(enabled: bool):
        """Persist and immediately refresh the tray-icon presentation."""
        if enabled:
            AppSettings.turnON_('UseMonochromeTrayIcon')
            APP().systemTray.setMonochromeIcon()
        else:
            AppSettings.turnOFF('UseMonochromeTrayIcon')

            if APP().isSystemTrayConnected():
                APP().systemTray.setConnectedIcon()
            else:
                APP().systemTray.setDisconnectedIcon()

    @staticmethod
    def setDockIconHidden(enabled: bool):
        """Apply the macOS dock-icon visibility preference."""
        if enabled:
            APP().installDockIconVisibilityFeature()
            AppSettings.turnON_('HideDockIcon')
        else:
            APP().installDockIconVisibilityFeature(remove=True)
            AppSettings.turnOFF('HideDockIcon')

    @staticmethod
    def setStartupOnBoot(enabled: bool):
        """Apply the platform startup registration preference."""
        if enabled:
            StartupOnBoot.on_()
            AppSettings.turnON_('StartupOnBoot')
        else:
            StartupOnBoot.off()
            AppSettings.turnOFF('StartupOnBoot')

    @staticmethod
    def setPowerSaveMode(enabled: bool):
        """Persist power-saving behavior for the next connection."""
        if enabled:
            AppSettings.turnON_('PowerSaveMode')
        else:
            AppSettings.turnOFF('PowerSaveMode')

        showMBoxNewChangesNextTime()

    @staticmethod
    def setForceLocalProxy(enabled: bool):
        """Persist local system-proxy address normalization."""
        if enabled:
            AppSettings.turnON_('ForceToLocalhostWhenSettingLocalProxy')
        else:
            AppSettings.turnOFF('ForceToLocalhostWhenSettingLocalProxy')

        showMBoxNewChangesNextTime()

    @staticmethod
    def setAutoUpdateAssets(enabled: bool):
        """Persist automatic core-asset updates."""
        if enabled:
            AppSettings.turnON_('AutoUpdateAssetFiles')
        else:
            AppSettings.turnOFF('AutoUpdateAssetFiles')

    @staticmethod
    def setConnectionProgressVisible(enabled: bool):
        """Persist connection-progress visibility."""
        if enabled:
            AppSettings.turnON_('ShowProgressBarWhenConnecting')
        else:
            AppSettings.turnOFF('ShowProgressBarWhenConnecting')

    @staticmethod
    def setEditorWhitespaceVisible(enabled: bool):
        """Apply and persist editor whitespace visibility."""
        if enabled:
            APP().mainWindow.showTabAndSpaces()
            AppSettings.turnON_('ShowTabAndSpacesInEditor')
        else:
            APP().mainWindow.hideTabAndSpaces()
            AppSettings.turnOFF('ShowTabAndSpacesInEditor')


class TUNModeAction(AppQAction):
    """Handle the TUN mode action."""

    def __init__(self, **kwargs):
        """Initialize the TUNModeAction."""
        if PLATFORM == 'Linux':
            super().__init__(_('TUN Mode'), **kwargs)
        else:
            if SystemRuntime.isAdmin():
                super().__init__(_('TUN Mode'), **kwargs)
            else:
                if ADMINISTRATOR_NAME == 'Administrator':
                    text = _('TUN Mode Disabled (Administrator)')
                else:
                    text = _('TUN Mode Disabled (Superuser)')

                super().__init__(text, **kwargs)

                self.setDisabled(True)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        SettingsController.setTUNMode(checked)


class SettingsChildAction(AppQAction):
    """Handle the settings child action."""

    def __init__(self, *args, **kwargs):
        """Initialize the SettingsChildAction."""
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        if self.textCompare('Dark Mode'):
            SettingsController.setDarkMode(checked)
        elif self.textCompare('Use Monochrome Tray Icon'):
            SettingsController.setMonochromeTrayIcon(checked)
        elif self.textCompare('Hide Dock Icon'):
            SettingsController.setDockIconHidden(checked)
        elif self.textCompare('Startup On Boot'):
            SettingsController.setStartupOnBoot(checked)
        elif self.textCompare('Power Save Mode'):
            SettingsController.setPowerSaveMode(checked)
        elif self.textCompare('Force To 127.0.0.1 When Setting Local Proxy'):
            SettingsController.setForceLocalProxy(checked)
        elif self.textCompare('Automatically Update Asset Files'):
            SettingsController.setAutoUpdateAssets(checked)
        elif self.textCompare('Show Progress Bar When Connecting'):
            SettingsController.setConnectionProgressVisible(checked)
        elif self.textCompare('Show Tab And Spaces In Editor'):
            SettingsController.setEditorWhitespaceVisible(checked)


class SettingsAction(AppQAction):
    """Navigate from the system tray to the page-based settings UI."""

    def __init__(self, **kwargs):
        """Initialize the SettingsAction."""
        super().__init__(
            _('Settings'),
            icon=bootstrapIcon('gear-wide-connected.svg'),
            callback=lambda: APP().mainWindow.showSettingsPage(),
            **kwargs,
        )

    def getTUNModeAction(self) -> AppQAction:
        """Return the Settings page's compatibility TUN action."""
        return APP().mainWindow.settingsPage.tunModeAction
