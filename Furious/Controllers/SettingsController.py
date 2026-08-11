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

"""Apply persistent application preferences independently from their UI."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.DynamicTranslate import SUPPORTED_LANGUAGE
from Furious.Qt.QtWidgets import showMBoxNewChangesNextTime
from Furious.Service.TrafficStatsManager import (
    CLEAR_TRAFFIC_USAGE_ON_RECONNECT_SETTING,
    METRICS_COLLECTION_SETTING,
)

__all__ = ['SettingsController']

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
registerAppSettings(
    'SystemProxyMode',
    validRange=list(mode.value for mode in AppBuiltinProxyMode),
)


class SettingsController:
    """Apply application settings independently from their presentation."""

    @staticmethod
    def _setBinary(settingName: str, enabled: bool):
        """Persist one registered binary setting."""
        if enabled:
            AppSettings.turnON_(settingName)
        else:
            AppSettings.turnOFF(settingName)

    @classmethod
    def setTUNMode(cls, enabled: bool):
        """Persist the global TUN mode and notify active workflows."""
        if PLATFORM != 'Linux':
            assert SystemRuntime.isAdmin()

        cls._setBinary('VPNMode', enabled)
        showMBoxNewChangesNextTime()

    @classmethod
    def setDarkMode(cls, enabled: bool):
        """Switch between the explicit dark theme and automatic mode."""
        cls._setBinary('DarkMode', enabled)

        try:
            if enabled:
                APP().switchToDarkMode()
            else:
                APP().switchToAutoMode()
        except Exception:
            # The controller can be exercised before the full desktop UI exists.
            pass

    @staticmethod
    def setLanguage(language: str):
        """Persist a supported UI language and refresh translated objects."""
        if language not in SUPPORTED_LANGUAGE:
            return

        if AppSettings.get('Language') != language:
            AppSettings.set('Language', language)
            Mixins.QTranslatable.retranslateAll()

    @classmethod
    def setMonochromeTrayIcon(cls, enabled: bool):
        """Persist and immediately refresh the tray-icon presentation."""
        cls._setBinary('UseMonochromeTrayIcon', enabled)

        try:
            if enabled:
                APP().systemTray.setMonochromeIcon()
            elif APP().isSystemTrayConnected():
                APP().systemTray.setConnectedIcon()
            else:
                APP().systemTray.setDisconnectedIcon()
        except (AttributeError, RuntimeError):
            pass

    @classmethod
    def setDockIconHidden(cls, enabled: bool):
        """Apply the macOS dock-icon visibility preference."""
        if enabled:
            APP().installDockIconVisibilityFeature()
        else:
            APP().installDockIconVisibilityFeature(remove=True)

        cls._setBinary('HideDockIcon', enabled)

    @classmethod
    def setStartupOnBoot(cls, enabled: bool):
        """Apply the platform startup registration preference."""
        if enabled:
            StartupOnBoot.on_()
        else:
            StartupOnBoot.off()

        cls._setBinary('StartupOnBoot', enabled)

    @classmethod
    def setPowerSaveMode(cls, enabled: bool):
        """Persist power-saving behavior for the next connection."""
        cls._setBinary('PowerSaveMode', enabled)
        showMBoxNewChangesNextTime()

    @classmethod
    def setForceLocalProxy(cls, enabled: bool):
        """Persist local system-proxy address normalization."""
        cls._setBinary('ForceToLocalhostWhenSettingLocalProxy', enabled)
        showMBoxNewChangesNextTime()

    @staticmethod
    def setSystemProxyMode(mode: str):
        """Persist how Furious manages the operating-system proxy."""
        validModes = tuple(item.value for item in AppBuiltinProxyMode)

        if mode in validModes:
            AppSettings.set('SystemProxyMode', mode)

    @classmethod
    def setAutoUpdateAssets(cls, enabled: bool):
        """Persist automatic core-asset updates."""
        cls._setBinary('AutoUpdateAssetFiles', enabled)

    @classmethod
    def setConnectionProgressVisible(cls, enabled: bool):
        """Persist connection-progress visibility."""
        cls._setBinary('ShowProgressBarWhenConnecting', enabled)

    @classmethod
    def setClearTrafficUsageOnReconnect(cls, enabled: bool):
        """Persist whether reconnecting starts a fresh usage session."""
        cls._setBinary(CLEAR_TRAFFIC_USAGE_ON_RECONNECT_SETTING, enabled)

    @classmethod
    def setMetricsCollectionEnabled(cls, enabled: bool):
        """Persist and immediately apply network metrics collection."""
        cls._setBinary(METRICS_COLLECTION_SETTING, enabled)

        try:
            APP().mainWindow.trafficStatsManager.setCollectionEnabled(enabled)
        except (AttributeError, RuntimeError):
            pass

    @classmethod
    def setEditorWhitespaceVisible(cls, enabled: bool):
        """Apply and persist editor whitespace visibility."""
        cls._setBinary('ShowTabAndSpacesInEditor', enabled)

        try:
            if enabled:
                APP().mainWindow.showTabAndSpaces()
            else:
                APP().mainWindow.hideTabAndSpaces()
        except (AttributeError, RuntimeError):
            pass
