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

__all__ = ['RoutingAction']

BUILTIN_ROUTING = ['Bypass Mainland China', 'Global', 'Custom']

registerAppSettings('Routing', validRange=BUILTIN_ROUTING)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(*BUILTIN_ROUTING)


class RoutingChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        textEnglish = self.textEnglish

        if AppSettings.get('Routing') != textEnglish:
            AppSettings.set('Routing', textEnglish)

            if APP().isSystemTrayConnected():
                APP().systemTray.ConnectAction.doDisconnect()
                APP().systemTray.ConnectAction.trigger()


needTrans('Routing')


class RoutingAction(AppQAction):
    def __init__(self, **kwargs):
        if AppSettings.get('Routing') == 'Bypass':
            # Update value for backward compatibility
            AppSettings.set('Routing', 'Bypass Mainland China')

        super().__init__(
            _('Routing'),
            icon=bootstrapIcon('shuffle.svg'),
            menu=AppQMenu(
                *list(
                    RoutingChildAction(
                        _(routing),
                        checkable=True,
                        checked=AppSettings.get('Routing') == routing,
                    )
                    for routing in BUILTIN_ROUTING
                ),
            ),
            **kwargs,
        )
