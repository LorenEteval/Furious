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

"""Provide bundled mixins."""

from __future__ import annotations

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from shiboken6 import isValid as isValidQObject

import logging
import weakref

logger = logging.getLogger(__name__)

__all__ = ['Mixins']


class Mixins:
    """Group reusable lifecycle, translation, theme, and Qt context mixins."""
    @staticmethod
    def qObjectIsValid(qobject) -> bool:
        """Return the q object is valid value used by the mixins."""
        if not isinstance(qobject, QtCore.QObject):
            return True

        try:
            return isValidQObject(qobject)
        except RuntimeError:
            return False

    class ConnectionAware:
        """Represent connection aware."""
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            """Initialize the ConnectionAware."""
            super().__init__(*args, **kwargs)

            Mixins.ConnectionAware.ObjectsPool.append(self)

        def disconnectedCallback(self):
            """Update the connection aware for a disconnected state."""
            raise NotImplementedError

        def connectedCallback(self):
            """Update the connection aware for a connected state."""
            raise NotImplementedError

        @staticmethod
        def callConnectedCallback():
            """Call connected callback."""
            for ob in Mixins.ConnectionAware.ObjectsPool:
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.connectedCallback()

        @staticmethod
        def callDisconnectedCallback():
            """Call disconnected callback."""
            for ob in Mixins.ConnectionAware.ObjectsPool:
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.disconnectedCallback()

    class ThemeAware:
        """Represent theme aware."""
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            """Initialize the ThemeAware."""
            super().__init__(*args, **kwargs)

            Mixins.ThemeAware.ObjectsPool.append(self)

        def themeChangedCallback(self, theme: str):
            """Update the theme aware for a theme change."""
            raise NotImplementedError

        @staticmethod
        def callThemeChangedCallbackUnchecked(theme: str):
            """Call theme changed callback unchecked."""
            for ob in Mixins.ThemeAware.ObjectsPool:
                assert isinstance(ob, Mixins.ThemeAware)

                ob.themeChangedCallback(theme)

        @staticmethod
        def callThemeChangedCallback(theme: str):
            """Call theme changed callback."""
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
        """Represent cleanup on exit."""
        ObjectsPool = list()
        VisitedType = dict()

        def __init__(self, *args, **kwargs):
            """Initialize the CleanupOnExit."""
            self.uniqueCleanup = kwargs.pop('uniqueCleanup', True)

            super().__init__(*args, **kwargs)

            Mixins.CleanupOnExit.ObjectsPool.append(self)

        def cleanup(self):
            """Release resources owned by the cleanup on exit."""
            raise NotImplementedError

        @staticmethod
        def cleanupAll():
            """Handle cleanup all for the cleanup on exit."""
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
        """Manage the q set disabled context."""
        def __init__(self, qobject: QtCore.QObject):
            """Initialize the QSetDisabledContext."""
            self.qobject = qobject

        def __enter__(self):
            """Enter the q set disabled context context."""
            if Mixins.qObjectIsValid(self.qobject) and hasattr(
                self.qobject, 'setDisabled'
            ):
                self.qobject.setDisabled(True)

        def __exit__(self, exceptionType, exceptionValue, tb):
            """Exit the q set disabled context context and restore state."""
            if Mixins.qObjectIsValid(self.qobject) and hasattr(
                self.qobject, 'setDisabled'
            ):
                self.qobject.setDisabled(False)

    class QBlockSignalContext:
        """Manage the q block signal context."""
        def __init__(self, qobject: QtCore.QObject):
            """Initialize the QBlockSignalContext."""
            self.qobject = qobject

        def __enter__(self):
            """Enter the q block signal context context."""
            if Mixins.qObjectIsValid(self.qobject) and hasattr(
                self.qobject, 'blockSignals'
            ):
                self.qobject.blockSignals(True)

        def __exit__(self, exceptionType, exceptionValue, tb):
            """Exit the q block signal context context and restore state."""
            if Mixins.qObjectIsValid(self.qobject) and hasattr(
                self.qobject, 'blockSignals'
            ):
                self.qobject.blockSignals(False)

    class QTranslatable:
        """Represent q translatable."""
        ObjectsPool = list()

        def __init__(self, *args, **kwargs):
            """Initialize the QTranslatable."""
            self.translatable = kwargs.pop('translatable', True)
            self.useQSetDisabled = kwargs.pop('useQSetDisabled', True)

            super().__init__(*args, **kwargs)

            Mixins.QTranslatable.ObjectsPool.append(self)

            if isinstance(self, QtCore.QObject):
                selfref = weakref.ref(self)
                self.destroyed.connect(
                    lambda *_args, _selfref=selfref: Mixins.QTranslatable.unregister(
                        _selfref()
                    )
                )

        def retranslate(self):
            """Refresh translated text for the q translatable."""
            raise NotImplementedError

        @staticmethod
        def unregister(ob):
            """Handle unregister for the q translatable."""
            try:
                Mixins.QTranslatable.ObjectsPool.remove(ob)
            except ValueError:
                pass

        @staticmethod
        def pruneObjectsPool():
            """Handle prune objects pool for the q translatable."""
            Mixins.QTranslatable.ObjectsPool = list(
                filter(Mixins.qObjectIsValid, Mixins.QTranslatable.ObjectsPool)
            )

        @staticmethod
        def retranslateAll():
            """Handle retranslate all for the q translatable."""
            Mixins.QTranslatable.pruneObjectsPool()

            for ob in list(Mixins.QTranslatable.ObjectsPool):
                assert isinstance(ob, Mixins.QTranslatable)

                if ob.translatable:
                    if ob.useQSetDisabled:
                        assert isinstance(ob, QtCore.QObject)

                        with Mixins.QSetDisabledContext(ob):
                            ob.retranslate()
                    else:
                        ob.retranslate()
