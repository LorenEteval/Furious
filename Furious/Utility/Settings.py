from Furious.Action.Language import SUPPORTED_LANGUAGE
from Furious.Action.Routing import BUILTIN_ROUTING
from Furious.Utility.Constants import SYSTEM_LANGUAGE
from Furious.Utility.Utility import Switch

from PySide6 import QtCore


class Settings:
    def __init__(self, name, protectedRange=None, default=None):
        self.name = name
        self.protectedRange = protectedRange

        if protectedRange is None:
            self.default = default
        else:
            self.default = protectedRange[0] if default is None else default

    @staticmethod
    def get(key):
        if key in Memo:
            settings = Memo[key]

            value = QtCore.QSettings().value(settings.name)

            if value is not None and (
                settings.protectedRange is None or value in settings.protectedRange
            ):
                return value

            # Value not in protected range. Set to default
            QtCore.QSettings().setValue(settings.name, settings.default)

            return settings.default
        else:
            raise AttributeError(f'Settings \'{key}\' not found')

    @staticmethod
    def set(key, value):
        if key in Memo:
            settings = Memo[key]

            if settings.protectedRange is None or value in settings.protectedRange:
                QtCore.QSettings().setValue(settings.name, value)
            else:
                # Value not in protected range. Raise exception
                raise ValueError(f'Invalid settings value {value}')
        else:
            raise AttributeError(f'Settings \'{key}\' not found')


# Handy stuff
SMART_CHOSEN_LANGUAGE = (
    SYSTEM_LANGUAGE if SYSTEM_LANGUAGE in SUPPORTED_LANGUAGE else 'EN'
)

SUPPORTED_SETTINGS = (
    # Connected last time or not
    Settings('Connect', Switch.RANGE),
    # User Routing option
    Settings('Routing', default=BUILTIN_ROUTING[0]),
    # User Custom Routing object
    Settings('CustomRouting'),
    # User Configuration
    Settings('Configuration'),
    # User Activated Server Index
    Settings('ActivatedItemIndex'),
    # Main Widget Window Size
    Settings('MainWidgetWindowSize'),
    # Edit Routing Widget Window Size
    Settings('RoutesWidgetWindowSize'),
    # Main Widget Section Size
    Settings('ServerWidgetSectionSizeTable'),
    # Edit Routing Widget Section Size
    Settings('RoutesWidgetSectionSizeTable'),
    # Main Widget Font Point Size
    Settings('EditorWidgetPointSize'),
    # Log Viewer Widget Font Point Size
    Settings('ViewerWidgetPointSize'),
    # User selected language
    Settings('Language', SUPPORTED_LANGUAGE, SMART_CHOSEN_LANGUAGE),
    # Startup On Boot
    Settings('StartupOnBoot', Switch.RANGE, Switch.ON_),  # On by default
    # Show Progressbar
    Settings(
        # For user experience: On by default
        'ShowProgressBarWhenConnecting',
        Switch.RANGE,
        Switch.ON_,
    ),
    # Show Tab and spaces
    Settings('ShowTabAndSpacesInEditor', Switch.RANGE),
)

Memo = {settings.name: settings for settings in SUPPORTED_SETTINGS}
