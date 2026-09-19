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

"""Route runtime exits on the Qt thread and model ownership transfer."""

from __future__ import annotations

from Furious.Interface import CoreRuntime, RuntimeExit
from Furious.Qt.Signals import connectWeakly

from PySide6 import QtCore

from enum import Enum

import logging
import weakref

__all__ = ['RuntimeEventRouter', 'RuntimeLease', 'RuntimeLeaseState']

logger = logging.getLogger(__name__)


class RuntimeLeaseState(str, Enum):
    """Describe the one owner responsible for a runtime resource."""

    AttemptOwned = 'attempt-owned'
    Committed = 'committed'
    Releasing = 'releasing'
    Released = 'released'


def _weakCallable(callback):
    """Return a weak callable reference where Python supports one."""
    if callback is None:
        return None

    try:
        return weakref.WeakMethod(callback)
    except TypeError:
        # Free functions have no separate lifecycle owner and must remain
        # reachable for the committed runtime's lifetime.
        return lambda: callback


class RuntimeEventRouter(QtCore.QObject):
    """Keep one runtime callback while routing exits by lease ownership state."""

    _published = QtCore.Signal(object, object)

    def __init__(self):
        """Create a detached router before a plugin constructs its runtime."""
        super().__init__()

        self._runtime = None
        self._state = RuntimeLeaseState.AttemptOwned
        self._attemptOwner = None
        self._attemptMethod = ''
        self._committedCallback = None
        self._terminalDelivered = False

        self._publishedConnection = connectWeakly(
            self._published,
            self,
            '_deliver',
            sender=self,
            connectionType=QtCore.Qt.ConnectionType.QueuedConnection,
        )

    @property
    def state(self):
        """Return the current logical owner state."""
        return self._state

    def attach(self, runtime, attemptOwner, methodName='runtimeExited'):
        """Attach the runtime and weak startup recipient before execution."""
        if self._runtime is not None:
            raise RuntimeError('runtime event router is already attached')

        self._runtime = runtime
        self._attemptOwner = weakref.ref(attemptOwner)
        self._attemptMethod = str(methodName)

    def publish(self, runtime, event):
        """Accept an exit from any thread and queue it to this Qt thread."""
        if not isinstance(event, RuntimeExit):
            raise TypeError('runtime event router requires a RuntimeExit value')

        self._published.emit(runtime, event)

    def commit(self, callback):
        """Transfer logical delivery without changing the runtime callback."""
        if self._state is not RuntimeLeaseState.AttemptOwned:
            raise RuntimeError('only an attempt-owned runtime can commit')

        self._attemptOwner = None
        self._attemptMethod = ''
        self._committedCallback = _weakCallable(callback)
        self._state = RuntimeLeaseState.Committed

    def beginRelease(self):
        """Suppress requested-stop and late queued events during cleanup."""
        if self._state is RuntimeLeaseState.Released:
            return False

        self._state = RuntimeLeaseState.Releasing
        self._attemptOwner = None
        self._committedCallback = None

        return True

    def finishRelease(self):
        """Mark the route permanently terminal."""
        self._state = RuntimeLeaseState.Released
        self._runtime = None

        if self._publishedConnection is not None:
            try:
                QtCore.QObject.disconnect(self._publishedConnection)
            except (RuntimeError, TypeError):
                pass

            self._publishedConnection = None

    @QtCore.Slot(object, object)
    def _deliver(self, runtime, event):
        """Deliver one typed terminal event on the router's Qt thread."""
        if (
            self._terminalDelivered
            or runtime is not self._runtime
            or self._state in (RuntimeLeaseState.Releasing, RuntimeLeaseState.Released)
        ):
            return

        self._terminalDelivered = True

        if self._state is RuntimeLeaseState.AttemptOwned:
            owner = self._attemptOwner() if self._attemptOwner is not None else None
            callback = getattr(owner, self._attemptMethod, None)
        else:
            callback = (
                self._committedCallback()
                if self._committedCallback is not None
                else None
            )

        if callable(callback):
            callback(runtime, event)


class RuntimeLease:
    """Own one runtime and its stable event router through transfer and release."""

    def __init__(self, runtime: CoreRuntime, router: RuntimeEventRouter):
        """Take exact ownership of one attached runtime."""
        if not isinstance(runtime, CoreRuntime):
            raise TypeError('runtime lease requires a CoreRuntime')

        self.runtime = runtime
        self.router = router
        self._releaseInProgress = False

    @property
    def state(self):
        """Return the route's ownership state."""
        return self.router.state

    def commit(self, callback):
        """Transfer event consumption to the committed connection owner."""
        self.router.commit(callback)

    def release(self):
        """Release execution, retaining failed cleanup for the owner to retry."""
        if self.state is RuntimeLeaseState.Released:
            return True

        if self._releaseInProgress:
            return False

        self.router.beginRelease()
        self._releaseInProgress = True

        stopped, disposed = True, True

        try:
            try:
                self.runtime.stop()
            except Exception as ex:
                # Any non-exit exceptions

                stopped = False

                logger.error(f'error stopping core runtime: {ex}')

            try:
                self.runtime.dispose()
            except Exception as ex:
                # Any non-exit exceptions

                disposed = False

                logger.error(f'error disposing core runtime: {ex}')

            if not stopped or not disposed:
                return False

            try:
                if self.runtime.isRunning():
                    logger.error('core runtime remains alive after disposal')

                    return False
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'could not verify core runtime shutdown: {ex}')

                return False

            self.router.finishRelease()
            self.router.deleteLater()

            return True
        finally:
            self._releaseInProgress = False
