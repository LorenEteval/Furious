from __future__ import annotations

from Furious.QtFramework.QtGui import bootstrapIcon, AppQIcon
from Furious.Utility import *

import functools

__all__ = ['ColorRGB', 'AppHue']


class ColorRGB:
    LIGHT_BLUE = '#43ACED'
    LIGHT_RED = '#FF7276'
    LIGHT_PURPLE = '#DA70D6'


class AppHue:
    @staticmethod
    def disconnectedColor() -> str:
        return ColorRGB.LIGHT_BLUE

    @staticmethod
    def disconnectedWindowIcon() -> AppQIcon:
        return bootstrapIcon('rocket-takeoff-window.svg')

    @staticmethod
    @functools.lru_cache(None)
    def connectedColor() -> str:
        if not isAdministrator():
            return ColorRGB.LIGHT_RED
        else:
            return ColorRGB.LIGHT_PURPLE

    @staticmethod
    @functools.lru_cache(None)
    def connectedWindowIcon() -> AppQIcon:
        if not isAdministrator():
            return bootstrapIcon('rocket-takeoff-connected-dark.svg')
        else:
            return bootstrapIcon('rocket-takeoff-admin-connected.svg')

    @staticmethod
    def currentColor() -> str:
        if APP().isTrayConnected():
            return AppHue.connectedColor()
        else:
            return AppHue.disconnectedColor()

    @staticmethod
    def currentWindowIcon() -> AppQIcon:
        if APP().isTrayConnected():
            return AppHue.connectedWindowIcon()
        else:
            return AppHue.disconnectedWindowIcon()
