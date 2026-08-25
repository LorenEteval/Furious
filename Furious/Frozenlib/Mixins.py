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


class _WeakObjectsPool:
    """Store objects in registration order without extending their lifetime."""

    def __init__(self):
        """Initialize an empty weak object registry."""
        self._references = {}

    def _removeReference(self, key, reference):
        """Remove a weak reference if it is still registered under its object ID."""
        if self._references.get(key) is reference:
            self._references.pop(key)

    def append(self, ob):
        """Register an object without retaining a strong reference to it."""
        key = id(ob)
        current = self._references.get(key)

        if current is not None:
            if current() is ob:
                raise ValueError('object is already registered')

            self._references.pop(key)

        reference = weakref.ref(
            ob,
            lambda ref, _key=key: self._removeReference(_key, ref),
        )
        self._references[key] = reference

        if isinstance(ob, QtCore.QObject):
            ob.destroyed.connect(
                lambda *_args, _key=key, _reference=reference: self._removeReference(
                    _key, _reference
                )
            )

    def remove(self, ob):
        """Remove an object's registration by identity."""
        key = id(ob)
        reference = self._references.get(key)

        if reference is None or reference() is not ob:
            raise ValueError('object is not registered')

        self._references.pop(key)

    def clear(self):
        """Remove every registration from the registry."""
        self._references.clear()

    def prune(self, predicate=None):
        """Remove dead objects and live objects rejected by a predicate."""
        for key, reference in list(self._references.items()):
            ob = reference()

            if ob is None or (predicate is not None and not predicate(ob)):
                self._removeReference(key, reference)

    def __iter__(self):
        """Iterate over a stable snapshot of currently live objects."""
        for key, reference in list(self._references.items()):
            ob = reference()

            if ob is None:
                self._removeReference(key, reference)
            else:
                yield ob

    def __len__(self):
        """Return the number of currently live registrations."""
        self.prune()

        return len(self._references)


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

        ObjectsPool = _WeakObjectsPool()

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
            Mixins.ConnectionAware.ObjectsPool.prune(Mixins.qObjectIsValid)

            for ob in list(Mixins.ConnectionAware.ObjectsPool):
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.connectedCallback()

        @staticmethod
        def callDisconnectedCallback():
            """Call disconnected callback."""
            Mixins.ConnectionAware.ObjectsPool.prune(Mixins.qObjectIsValid)

            for ob in list(Mixins.ConnectionAware.ObjectsPool):
                assert isinstance(ob, Mixins.ConnectionAware)

                ob.disconnectedCallback()

    class ThemeAware:
        """Represent theme aware."""

        ObjectsPool = _WeakObjectsPool()

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
            Mixins.ThemeAware.ObjectsPool.prune(Mixins.qObjectIsValid)

            for ob in list(Mixins.ThemeAware.ObjectsPool):
                assert isinstance(ob, Mixins.ThemeAware)

                ob.themeChangedCallback(theme)

        @staticmethod
        def callThemeChangedCallback(theme: str):
            """Notify registered objects after an accepted system theme change."""
            logger.info(f'system theme changed to \'{theme}\'')

            Mixins.ThemeAware.callThemeChangedCallbackUnchecked(theme)

    class CleanupOnExit:
        """Represent cleanup on exit."""

        ObjectsPool = _WeakObjectsPool()
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
            Mixins.CleanupOnExit.ObjectsPool.prune(Mixins.qObjectIsValid)

            try:
                for ob in list(Mixins.CleanupOnExit.ObjectsPool):
                    assert isinstance(ob, Mixins.CleanupOnExit)

                    if ob.uniqueCleanup:
                        obtype = str(type(ob))

                        if Mixins.CleanupOnExit.VisitedType.get(obtype, False):
                            continue

                        Mixins.CleanupOnExit.VisitedType[obtype] = True

                    try:
                        ob.cleanup()
                    except Exception:
                        # Any non-exit exceptions

                        # Cleanup is an isolation boundary. One failed owner
                        # must not prevent unrelated resources from being
                        # released during application shutdown.
                        logger.exception(f'cleanup failed for {type(ob).__name__}')
            finally:
                Mixins.CleanupOnExit.ObjectsPool.clear()
                Mixins.CleanupOnExit.VisitedType.clear()

    class QSetDisabledContext:
        """Manage the q set disabled context."""

        def __init__(self, qobject: QtCore.QObject):
            """Initialize the QSetDisabledContext."""
            self._qobject = qobject
            self._wasDisabled = None

        def __enter__(self):
            """Enter the q set disabled context context."""
            if (
                Mixins.qObjectIsValid(self._qobject)
                and hasattr(self._qobject, 'isEnabled')
                and hasattr(self._qobject, 'setDisabled')
            ):
                self._wasDisabled = not self._qobject.isEnabled()
                self._qobject.setDisabled(True)

            return self._qobject

        def __exit__(self, exceptionType, exceptionValue, tb):
            """Exit the q set disabled context context and restore state."""
            if (
                self._wasDisabled is not None
                and Mixins.qObjectIsValid(self._qobject)
                and hasattr(self._qobject, 'setDisabled')
            ):
                self._qobject.setDisabled(self._wasDisabled)

    class QBlockSignalContext:
        """Manage the q block signal context."""

        def __init__(self, qobject: QtCore.QObject):
            """Initialize the QBlockSignalContext."""
            self._qobject = qobject
            self._signalsWereBlocked = None

        def __enter__(self):
            """Enter the q block signal context context."""
            if Mixins.qObjectIsValid(self._qobject) and hasattr(
                self._qobject, 'blockSignals'
            ):
                self._signalsWereBlocked = self._qobject.blockSignals(True)

            return self._qobject

        def __exit__(self, exceptionType, exceptionValue, tb):
            """Exit the q block signal context context and restore state."""
            if (
                self._signalsWereBlocked is not None
                and Mixins.qObjectIsValid(self._qobject)
                and hasattr(self._qobject, 'blockSignals')
            ):
                self._qobject.blockSignals(self._signalsWereBlocked)

    class QTranslatable:
        """Represent q translatable."""

        ObjectsPool = _WeakObjectsPool()

        def __init__(self, *args, **kwargs):
            """Initialize the QTranslatable."""
            self.translatable = kwargs.pop('translatable', True)
            self.useQSetDisabled = kwargs.pop('useQSetDisabled', True)

            super().__init__(*args, **kwargs)

            Mixins.QTranslatable.ObjectsPool.append(self)

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
            Mixins.QTranslatable.ObjectsPool.prune(Mixins.qObjectIsValid)

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
