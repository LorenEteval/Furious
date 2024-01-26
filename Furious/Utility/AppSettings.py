from __future__ import annotations

from Furious.Utility.Utility import BinarySettings

from PySide6 import QtCore

import logging

__all__ = ['AppSettings', 'registerAppSettings']

logger = logging.getLogger(__name__)


class AppSettings:
    SettingsPool: dict[str, AppSettings] = dict()

    def __init__(
        self,
        name: str,
        isBinary=False,
        validRange: list = None,
        default=None,
    ):
        self.name = name
        self.isBinary = isBinary

        if isBinary:
            self.validRange = BinarySettings.RANGE
            self.default = BinarySettings.OFF
        else:
            self.validRange = validRange

            if validRange is None:
                self.default = default
            else:
                self.default = validRange[0] if default is None else default

        if name in AppSettings.SettingsPool:
            raise ValueError(f'\'{name}\' already exists in AppSettings')

    def validate(self, value) -> bool:
        if self.validRange is None:
            return True
        else:
            return value in self.validRange

    @staticmethod
    def get(key: str):
        settings = AppSettings.SettingsPool.get(key)

        if settings is None:
            raise AttributeError(f'AppSettings \'{key}\' not found')

        assert isinstance(settings, AppSettings)

        value = QtCore.QSettings().value(settings.name)

        if settings.validate(value):
            return value
        else:
            logger.error(
                f'settings \'{settings.name}\' has value \'{value}\', '
                f'which is not in valid range {settings.validRange}. '
                f'Set to default \'{settings.default}\''
            )

            # Value not in valid range, set to default
            QtCore.QSettings().setValue(settings.name, settings.default)

            return settings.default

    @staticmethod
    def isStateON_(key: str) -> bool:
        value = AppSettings.get(key)

        if value == BinarySettings.ON_:
            return True
        else:
            return False

    @staticmethod
    def isStateOFF(key: str) -> bool:
        value = AppSettings.get(key)

        if value == BinarySettings.OFF:
            return True
        else:
            return False

    @staticmethod
    def set(key: str, value):
        settings = AppSettings.SettingsPool.get(key)

        if settings is None:
            raise AttributeError(f'AppSettings \'{key}\' not found')

        assert isinstance(settings, AppSettings)

        if settings.validate(value):
            QtCore.QSettings().setValue(settings.name, value)
        else:
            # Value not in valid range, raise exception
            raise ValueError(f'Invalid AppSettings value \'{value}\' for \'{key}\'')

    @staticmethod
    def turnON_(key: str):
        AppSettings.set(key, BinarySettings.ON_)

    @staticmethod
    def turnOFF(key: str):
        AppSettings.set(key, BinarySettings.OFF)


def registerAppSettings(name: str, *args, **kwargs):
    AppSettings.SettingsPool[name] = AppSettings(name, *args, **kwargs)


# TODO. Handy stuff
# SMART_CHOSEN_LANGUAGE = (
#     SYSTEM_LANGUAGE if SYSTEM_LANGUAGE in SUPPORTED_LANGUAGE else 'EN'
# )
#
# SUPPORTED_SETTINGS = (
#     # Connected last time or not
#     Settings('Connect', BinarySettings.RANGE),
#     # User Routing option
#     Settings('Routing', default=BUILTIN_ROUTING[0]),
#     # User VPN Mode
#     Settings('VPNMode', BinarySettings.RANGE),
#     # Hide editor or not
#     Settings('HideEditor', BinarySettings.RANGE),
#     # User Custom Routing object
#     Settings('CustomRouting'),
#     # User Configuration
#     Settings('Configuration'),
#     # User Custom Subscription object
#     Settings('CustomSubscription'),
#     # User Activated Server Index
#     Settings('ActivatedItemIndex'),
#     # TODO. User Tor Relay Settings. Abandoned. Not used!!!
#     # Settings('TorRelaySettings'),
#     # Server Widget Window Size
#     Settings('ServerWidgetWindowSize'),
#     # Routes Widget Window Size
#     Settings('RoutesWidgetWindowSize'),
#     # Subscription Widget Window Size
#     Settings('SubscriptionWidgetWindowSize'),
#     # Server Widget Section Size
#     Settings('ServerWidgetSectionSizeTable'),
#     # Routes Widget Section Size
#     Settings('RoutesWidgetSectionSizeTable'),
#     # Subscription Widget Section Size
#     Settings('SubscriptionWidgetSectionSizeTable'),
#     # Server Widget Font Point Size
#     Settings('ServerWidgetPointSize'),
#     # App Log Viewer Widget Font Point Size
#     Settings('AppLogViewerWidgetPointSize'),
#     # Core Log Viewer Widget Font Point Size
#     Settings('CoreLogViewerWidgetPointSize'),
#     # TODO. Tor Log Viewer Widget Font Point Size. Abandoned. Not used!!!
#     # Settings('TorLogViewerWidgetPointSize'),
#     # User selected language
#     Settings('Language', SUPPORTED_LANGUAGE, SMART_CHOSEN_LANGUAGE),
#     # Startup On Boot. On by default
#     Settings('StartupOnBoot', BinarySettings.RANGE, BinarySettings.ON_),
#     # Show Progressbar
#     Settings(
#         # For user experience: On by default
#         'ShowProgressBarWhenConnecting',
#         BinarySettings.RANGE,
#         BinarySettings.ON_,
#     ),
#     # Show Tab and spaces
#     Settings('ShowTabAndSpacesInEditor', BinarySettings.RANGE),
# )
#
# Memo = {settings.name: settings for settings in SUPPORTED_SETTINGS}
