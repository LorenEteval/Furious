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

from Furious.Utility.Constants import *

import logging
import threading

from typing import Callable

__all__ = ['Win32Session']

logger = logging.getLogger(__name__)


class _Win32Session:
    def __init__(self):
        self._daemonThread = None

    @staticmethod
    def set(callback: Callable[[], None]) -> bool:
        if PLATFORM == 'Windows':
            import win32session

            win32session.set(callback)

            return True
        else:
            return False

    def off(self) -> bool:
        if PLATFORM == 'Windows':
            import win32session

            if win32session.off():
                self._daemonThread.join()
                # Reset it
                self._daemonThread = None

                return True
            else:
                return False
        else:
            return False

    def run(self) -> bool:
        if PLATFORM == 'Windows':
            import win32session

            if self._daemonThread is None:
                self._daemonThread = threading.Thread(
                    target=lambda: win32session.run(), daemon=True
                )
                self._daemonThread.start()

            return True
        else:
            return False


Win32Session = _Win32Session()
