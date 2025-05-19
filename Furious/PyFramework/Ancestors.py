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

from PySide6.QtWidgets import QApplication

from typing import Any

import logging

logger = logging.getLogger(__name__)

__all__ = [
    'Translatable',
    'SupportConnectedCallback',
    'SupportThemeChangedCallback',
    'SupportExitCleanup',
    'GarbageCollector',
]


class Translatable:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        self.translatable = kwargs.pop('translatable', True)

        super().__init__(*args, **kwargs)

        Translatable.ObjectsPool.append(self)

    def retranslate(self):
        raise NotImplementedError

    @staticmethod
    def retranslateAll():
        for object_ in Translatable.ObjectsPool:
            assert isinstance(object_, Translatable)

            if object_.translatable:
                object_.retranslate()


class SupportConnectedCallback:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportConnectedCallback.ObjectsPool.append(self)

    def disconnectedCallback(self):
        raise NotImplementedError

    def connectedCallback(self):
        raise NotImplementedError

    @staticmethod
    def callConnectedCallback():
        for object_ in SupportConnectedCallback.ObjectsPool:
            assert isinstance(object_, SupportConnectedCallback)

            object_.connectedCallback()

    @staticmethod
    def callDisconnectedCallback():
        for object_ in SupportConnectedCallback.ObjectsPool:
            assert isinstance(object_, SupportConnectedCallback)

            object_.disconnectedCallback()


class SupportThemeChangedCallback:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportThemeChangedCallback.ObjectsPool.append(self)

    def themeChangedCallback(self, theme: str):
        raise NotImplementedError

    @staticmethod
    def callThemeChangedCallbackUnchecked(theme: str):
        for object_ in SupportThemeChangedCallback.ObjectsPool:
            assert isinstance(object_, SupportThemeChangedCallback)

            object_.themeChangedCallback(theme)

    @staticmethod
    def callThemeChangedCallback(theme: str):
        try:
            app = QApplication.instance()

            if app is not None and app.isDarkModeEnabled():
                # Ignore application dark detect system
                logger.info(f'ignore system theme \'{theme}\' changes in dark mode')

                return
        except Exception:
            # Any non-exit exceptions

            pass

        logger.info(f'system theme changed to \'{theme}\'')

        SupportThemeChangedCallback.callThemeChangedCallbackUnchecked(theme)


class SupportExitCleanup:
    ObjectsPool = list()
    VisitedType = dict()

    def __init__(self, *args, **kwargs):
        self.uniqueCleanup = kwargs.pop('uniqueCleanup', True)

        super().__init__(*args, **kwargs)

        SupportExitCleanup.ObjectsPool.append(self)

    def cleanup(self):
        raise NotImplementedError

    @staticmethod
    def cleanupAll():
        for object_ in SupportExitCleanup.ObjectsPool:
            assert isinstance(object_, SupportExitCleanup)

            if object_.uniqueCleanup:
                obtype = str(type(object_))

                if not SupportExitCleanup.VisitedType.get(obtype, False):
                    object_.cleanup()

                    SupportExitCleanup.VisitedType[obtype] = True
                else:
                    pass
            else:
                object_.cleanup()


class GarbageCollector:
    ObjectsPool = list()
    # ObjectsId is used to speed up searching
    ObjectsId = dict()

    @staticmethod
    def track(object_: Any):
        GarbageCollector.ObjectsPool.append(object_)
        GarbageCollector.ObjectsId[id(object_)] = True

    @staticmethod
    def isTracked(object_: Any) -> bool:
        return id(object_) in GarbageCollector.ObjectsId

    @staticmethod
    def clear():
        GarbageCollector.ObjectsPool.clear()
        GarbageCollector.ObjectsId.clear()
