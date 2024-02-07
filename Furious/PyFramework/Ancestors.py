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

__all__ = [
    'Translatable',
    'SupportConnectedCallback',
    'SupportThemeChangedCallback',
    'SupportExitCleanup',
    'SupportImplicitReference',
    'FastItemDeletionSearch',
]

import logging

logger = logging.getLogger(__name__)


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
        for ob in Translatable.ObjectsPool:
            assert isinstance(ob, Translatable)

            if ob.translatable:
                ob.retranslate()


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
        for ob in SupportConnectedCallback.ObjectsPool:
            assert isinstance(ob, SupportConnectedCallback)

            ob.connectedCallback()

    @staticmethod
    def callDisconnectedCallback():
        for ob in SupportConnectedCallback.ObjectsPool:
            assert isinstance(ob, SupportConnectedCallback)

            ob.disconnectedCallback()


class SupportThemeChangedCallback:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportThemeChangedCallback.ObjectsPool.append(self)

    def themeChangedCallback(self, theme: str):
        raise NotImplementedError

    @staticmethod
    def callThemeChangedCallbackUnchecked(theme: str):
        for ob in SupportThemeChangedCallback.ObjectsPool:
            assert isinstance(ob, SupportThemeChangedCallback)

            ob.themeChangedCallback(theme)

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
        for ob in SupportExitCleanup.ObjectsPool:
            assert isinstance(ob, SupportExitCleanup)

            if ob.uniqueCleanup:
                obtype = str(type(ob))

                if not SupportExitCleanup.VisitedType.get(obtype, False):
                    ob.cleanup()

                    SupportExitCleanup.VisitedType[obtype] = True
                else:
                    pass
            else:
                ob.cleanup()


class SupportImplicitReference:
    ObjectsPool = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportImplicitReference.ObjectsPool.append(self)


class FastItemDeletionSearch:
    DeletedItem = list()
    DeletedId = dict()

    @staticmethod
    def moveToTrash(item):
        FastItemDeletionSearch.DeletedItem.append(item)
        FastItemDeletionSearch.DeletedId[id(item)] = True

    @staticmethod
    def isInTrash(item) -> bool:
        return id(item) in FastItemDeletionSearch.DeletedId
