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

"""Provide bundled globals."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

import functools

__all__ = [
    'APP',
    'AppConnectionController',
    'AppEndpointInfoService',
    'AppFontName',
    'AppLogManager',
    'AppLogPage',
    'AppMainWindow',
    'AppRoutingController',
    'AppSettingsController',
    'AppSystemTray',
    'AppThreadPool',
    'AppTrafficStatsManager',
]

APP = functools.partial(QApplication.instance)


def getAppAttributes(name: str):
    """Return app attributes."""
    return getattr(APP(), name)


def getAppNestedAttributes(*names: str):
    """Return an application-owned object through a stable attribute path."""
    value = APP()

    for name in names:
        value = getattr(value, name)

    return value


(
    AppConnectionController,
    AppEndpointInfoService,
    AppFontName,
    AppLogManager,
    AppLogPage,
    AppMainWindow,
    AppRoutingController,
    AppSettingsController,
    AppSystemTray,
    AppThreadPool,
    AppTrafficStatsManager,
) = (
    functools.partial(getAppAttributes, 'connectionController'),
    functools.partial(
        getAppNestedAttributes,
        'mainWindow',
        'metricsPage',
        'endpointInfoService',
    ),
    functools.partial(getAppAttributes, 'customFontName'),
    functools.partial(getAppAttributes, 'logManager'),
    functools.partial(getAppAttributes, 'logPage'),
    functools.partial(getAppAttributes, 'mainWindow'),
    functools.partial(getAppAttributes, 'routingController'),
    functools.partial(getAppAttributes, 'settingsController'),
    functools.partial(getAppAttributes, 'systemTray'),
    functools.partial(getAppAttributes, 'threadPool'),
    functools.partial(getAppNestedAttributes, 'mainWindow', 'trafficStatsManager'),
)
