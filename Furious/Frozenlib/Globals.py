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

from PySide6.QtWidgets import QApplication

import functools

__all__ = [
    'APP',
    'AppFontName',
    'AppThreadPool',
    'AppLoggerWindow',
]

APP = functools.partial(QApplication.instance)


def getAppAttributes(name: str):
    return getattr(APP(), name)


(
    AppFontName,
    AppThreadPool,
) = (
    functools.partial(getAppAttributes, 'customFontName'),
    functools.partial(getAppAttributes, 'threadPool'),
)


class AppLoggerWindow:
    Self = functools.partial(getAppAttributes, 'logViewerWindowSelf')
    Core = functools.partial(getAppAttributes, 'logViewerWindowCore')
    TUN_ = functools.partial(getAppAttributes, 'logViewerWindowTun_')
