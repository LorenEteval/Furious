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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.QtGui import *
from Furious.Utility import *

__all__ = ['AppHue']


class AppHue:
    class ColorRGB:
        LIGHT_BLUE = '#43ACED'
        LIGHT_RED = '#FF7276'
        LIGHT_PURPLE = '#DA70D6'

    @staticmethod
    def disconnectedColor() -> str:
        return AppHue.ColorRGB.LIGHT_BLUE

    @staticmethod
    def disconnectedWindowIcon() -> AppQIcon:
        return bootstrapIcon('rocket-takeoff-window.svg')

    @staticmethod
    def connectedColor() -> str:
        if not SystemRuntime.isAdmin():
            return AppHue.ColorRGB.LIGHT_RED
        else:
            return AppHue.ColorRGB.LIGHT_PURPLE

    @staticmethod
    def connectedWindowIcon() -> AppQIcon:
        if not SystemRuntime.isAdmin():
            return bootstrapIcon('rocket-takeoff-connected-dark.svg')
        else:
            return bootstrapIcon('rocket-takeoff-admin-connected.svg')

    @staticmethod
    def currentColor() -> str:
        if APP().isSystemTrayConnected():
            return AppHue.connectedColor()
        else:
            return AppHue.disconnectedColor()

    @staticmethod
    def currentWindowIcon() -> AppQIcon:
        if APP().isSystemTrayConnected():
            return AppHue.connectedWindowIcon()
        else:
            return AppHue.disconnectedWindowIcon()
