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

"""Register, validate, read, and write persistent application settings."""

from __future__ import annotations

from PySide6 import QtCore

import logging

__all__ = [
    'AppBinarySettings',
    'AppSettings',
    'registerAppSettings',
]

logger = logging.getLogger(__name__)


class AppBinarySettings:
    """Store and validate app binary settings."""
    OFF = '0'
    ON_ = '1'

    RANGE = [OFF, ON_]


class AppSettings:
    """Store and validate app settings."""
    SettingsPool: dict[str, AppSettings] = dict()

    def __init__(
        self,
        name: str,
        isBinary=False,
        validRange: list = None,
        default=None,
    ):
        """Initialize the AppSettings."""
        self.name = name
        self.isBinary = isBinary

        if isBinary:
            self.validRange = AppBinarySettings.RANGE
            self.default = AppBinarySettings.OFF if default is None else default
        else:
            self.validRange = validRange

            if validRange is None:
                self.default = default
            else:
                self.default = validRange[0] if default is None else default

        if name in AppSettings.SettingsPool:
            raise ValueError(f'\'{name}\' already exists in AppSettings')

    def validate(self, value) -> bool:
        """Validate the app settings."""
        if self.validRange is None:
            return True
        else:
            return value in self.validRange

    @staticmethod
    def get(key: str):
        """Return data managed by the app settings."""
        settings = AppSettings.SettingsPool.get(key)

        if settings is None:
            raise AttributeError(f'AppSettings \'{key}\' not found')

        assert isinstance(settings, AppSettings)

        value = QtCore.QSettings().value(settings.name)

        if settings.validate(value):
            if value is None:
                if settings.default is not None:
                    logger.info(
                        f'detected settings \'{settings.name}\' was not set, '
                        f'but has a default value. Set to default \'{settings.default}\''
                    )

                    AppSettings.set(key, settings.default)

                    return settings.default
                else:
                    return value
            else:
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
        """Return whether state on."""
        value = AppSettings.get(key)

        if value == AppBinarySettings.ON_:
            return True
        else:
            return False

    @staticmethod
    def isStateOFF(key: str) -> bool:
        """Return whether state off."""
        value = AppSettings.get(key)

        if value == AppBinarySettings.OFF:
            return True
        else:
            return False

    @staticmethod
    def set(key: str, value):
        """Set data managed by the app settings."""
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
        """Handle turn on for the app settings."""
        AppSettings.set(key, AppBinarySettings.ON_)

    @staticmethod
    def turnOFF(key: str):
        """Handle turn off for the app settings."""
        AppSettings.set(key, AppBinarySettings.OFF)


def registerAppSettings(name: str, *args, **kwargs):
    """Handle register app settings for the application."""
    AppSettings.SettingsPool[name] = AppSettings(name, *args, **kwargs)
