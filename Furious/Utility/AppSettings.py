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
            self.default = BinarySettings.OFF if default is None else default
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
