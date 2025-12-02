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

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

__all__ = ['SystemProxyAction']

registerAppSettings(
    'SystemProxyMode', validRange=list(mode.value for mode in AppBuiltinProxyMode)
)


class SystemProxyChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Automatically Configure System Proxy'):
            AppSettings.set('SystemProxyMode', AppBuiltinProxyMode.Auto.value)
        elif self.textCompare('Do Not Change System Proxy'):
            AppSettings.set('SystemProxyMode', AppBuiltinProxyMode.NoChanges.value)


class SystemProxyAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('System Proxy'),
            icon=bootstrapIcon('hdd-network.svg'),
            menu=AppQMenu(
                SystemProxyChildAction(
                    _('Automatically Configure System Proxy'),
                    checkable=True,
                    checked=AppSettings.get('SystemProxyMode')
                    == AppBuiltinProxyMode.Auto.value,
                ),
                SystemProxyChildAction(
                    _('Do Not Change System Proxy'),
                    checkable=True,
                    checked=AppSettings.get('SystemProxyMode')
                    == AppBuiltinProxyMode.NoChanges.value,
                ),
            ),
            **kwargs,
        )
