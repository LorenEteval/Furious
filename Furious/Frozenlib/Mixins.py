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

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

import logging

logger = logging.getLogger(__name__)

__all__ = ['Mixins']


class Mixins:
    class ConnectionAware:
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            Mixins.ConnectionAware.ObjectsPool.append(self)

        def disconnectedCallback(self):
            raise NotImplementedError

        def connectedCallback(self):
            raise NotImplementedError

        @staticmethod
        def callConnectedCallback():
            for ob in Mixins.ConnectionAware.ObjectsPool:
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.connectedCallback()

        @staticmethod
        def callDisconnectedCallback():
            for ob in Mixins.ConnectionAware.ObjectsPool:
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.disconnectedCallback()

    class ThemeAware:
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            Mixins.ThemeAware.ObjectsPool.append(self)

        def themeChangedCallback(self, theme: str):
            raise NotImplementedError

        @staticmethod
        def callThemeChangedCallbackUnchecked(theme: str):
            for ob in Mixins.ThemeAware.ObjectsPool:
                assert isinstance(ob, Mixins.ThemeAware)

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

            Mixins.ThemeAware.callThemeChangedCallbackUnchecked(theme)

    class CleanupOnExit:
        ObjectsPool = list()
        VisitedType = dict()

        def __init__(self, *args, **kwargs):
            self.uniqueCleanup = kwargs.pop('uniqueCleanup', True)

            super().__init__(*args, **kwargs)

            Mixins.CleanupOnExit.ObjectsPool.append(self)

        def cleanup(self):
            raise NotImplementedError

        @staticmethod
        def cleanupAll():
            for ob in Mixins.CleanupOnExit.ObjectsPool:
                assert isinstance(ob, Mixins.CleanupOnExit)

                if ob.uniqueCleanup:
                    obtype = str(type(ob))

                    if not Mixins.CleanupOnExit.VisitedType.get(obtype, False):
                        ob.cleanup()

                        Mixins.CleanupOnExit.VisitedType[obtype] = True
                    else:
                        pass
                else:
                    ob.cleanup()

            Mixins.CleanupOnExit.ObjectsPool.clear()
            Mixins.CleanupOnExit.VisitedType.clear()

    class QSetDisabledContext:
        def __init__(self, qobject: QtCore.QObject):
            self.qobject = qobject

        def __enter__(self):
            if hasattr(self.qobject, 'setDisabled'):
                self.qobject.setDisabled(True)

        def __exit__(self, exceptionType, exceptionValue, tb):
            if hasattr(self.qobject, 'setDisabled'):
                self.qobject.setDisabled(False)

    class QBlockSignalContext:
        def __init__(self, qobject: QtCore.QObject):
            self.qobject = qobject

        def __enter__(self):
            if hasattr(self.qobject, 'blockSignals'):
                self.qobject.blockSignals(True)

        def __exit__(self, exceptionType, exceptionValue, tb):
            if hasattr(self.qobject, 'blockSignals'):
                self.qobject.blockSignals(False)

    class QTranslatable:
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            self.translatable = kwargs.pop('translatable', True)
            self.useQSetDisabled = kwargs.pop('useQSetDisabled', True)

            super().__init__(*args, **kwargs)

            Mixins.QTranslatable.ObjectsPool.append(self)

        def retranslate(self):
            raise NotImplementedError

        @staticmethod
        def retranslateAll():
            for ob in Mixins.QTranslatable.ObjectsPool:
                assert isinstance(ob, Mixins.QTranslatable)

                if ob.translatable:
                    if ob.useQSetDisabled:
                        assert isinstance(ob, QtCore.QObject)

                        with Mixins.QSetDisabledContext(ob):
                            ob.retranslate()
                    else:
                        ob.retranslate()
