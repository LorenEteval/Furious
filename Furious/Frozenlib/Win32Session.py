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

"""Provide bundled win32 session."""

from __future__ import annotations

from Furious.Frozenlib.Constants import *

import logging
import threading

from typing import Callable

__all__ = ['Win32Session']

logger = logging.getLogger(__name__)


class _Win32Session:
    """Represent win32 session."""

    ShutdownTimeout = 5.0

    def __init__(self):
        """Initialize the _Win32Session."""
        self._daemonThread = None
        self._daemonLock = threading.RLock()

    def _runListener(self, listenerCallback):
        """Run native session monitoring and release this exact thread on exit."""
        thread = threading.current_thread()

        try:
            listenerCallback()
        except Exception:
            # Any non-exit exceptions

            logger.exception('Windows session listener terminated with an error')
        finally:
            with self._daemonLock:
                if self._daemonThread is thread:
                    self._daemonThread = None

    @staticmethod
    def set(callback: Callable[[], None]) -> bool:
        """Set data managed by the win32 session."""
        if PLATFORM == 'Windows':
            import win32session

            win32session.set(callback)

            return True
        else:
            return False

    def off(self) -> bool:
        """Disable the win32 session."""
        if PLATFORM == 'Windows':
            import win32session

            if win32session.off():
                with self._daemonLock:
                    thread = self._daemonThread

                if isinstance(thread, threading.Thread):
                    if thread is threading.current_thread():
                        logger.error(
                            'Windows session listener cannot join its own thread'
                        )

                        return False

                    thread.join(self.ShutdownTimeout)

                    if thread.is_alive():
                        logger.error(
                            'Windows session listener did not stop before timeout'
                        )

                        return False

                with self._daemonLock:
                    if self._daemonThread is thread:
                        self._daemonThread = None

                return True
            else:
                return False
        else:
            return False

    def run(self) -> bool:
        """Run the win32 session task."""
        if PLATFORM == 'Windows':
            import win32session

            with self._daemonLock:
                if (
                    isinstance(self._daemonThread, threading.Thread)
                    and self._daemonThread.is_alive()
                ):
                    return True

                self._daemonThread = None

                thread = threading.Thread(
                    target=self._runListener,
                    args=(win32session.run,),
                    daemon=True,
                )

                self._daemonThread = thread

                try:
                    thread.start()
                except Exception:
                    if self._daemonThread is thread:
                        self._daemonThread = None

                    logger.exception('failed to start Windows session listener')

                    return False

            return True
        else:
            return False


Win32Session = _Win32Session()
