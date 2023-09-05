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
    # User VPN Mode
    Settings('VPNMode', Switch.RANGE),
    # User Custom Routing object
    Settings('CustomRouting'),
    # User Configuration
    Settings('Configuration'),
    # User Activated Server Index
    Settings('ActivatedItemIndex'),
    # User Tor Relay Settings,
    Settings('TorRelaySettings'),
    # Server Widget Window Size
    Settings('ServerWidgetWindowSize'),
    # Routes Widget Window Size
    Settings('RoutesWidgetWindowSize'),
    # Server Widget Section Size
    Settings('ServerWidgetSectionSizeTable'),
    # Routes Widget Section Size
    Settings('RoutesWidgetSectionSizeTable'),
    # Server Widget Font Point Size
    Settings('ServerWidgetPointSize'),
    # Log Viewer Widget Font Point Size
    Settings('LogViewerWidgetPointSize'),
    # Tor Viewer Widget Font Point Size
    Settings('TorViewerWidgetPointSize'),
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
