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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

import functools

__all__ = ['SystemProxyAction']

BUILTIN_PROXY_MODE = ['Auto', 'NoChanges']

registerAppSettings('SystemProxyMode', validRange=BUILTIN_PROXY_MODE)

needTrans = functools.partial(needTransFn, source=__name__)


class SystemProxyChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        if self.textCompare('Automatically Configure System Proxy'):
            AppSettings.set('SystemProxyMode', 'Auto')
        elif self.textCompare('Do Not Change System Proxy'):
            AppSettings.set('SystemProxyMode', 'NoChanges')


needTrans(
    'System Proxy',
    'Automatically Configure System Proxy',
    'Do Not Change System Proxy',
)


class SystemProxyAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('System Proxy'),
            icon=bootstrapIcon('hdd-network.svg'),
            menu=AppQMenu(
                SystemProxyChildAction(
                    _('Automatically Configure System Proxy'),
                    checkable=True,
                    checked=AppSettings.get('SystemProxyMode') == 'Auto',
                ),
                SystemProxyChildAction(
                    _('Do Not Change System Proxy'),
                    checkable=True,
                    checked=AppSettings.get('SystemProxyMode') == 'NoChanges',
                ),
            ),
            **kwargs,
        )
