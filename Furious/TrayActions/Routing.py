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
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

__all__ = ['RoutingAction']

registerAppSettings('Routing', default=AppBuiltinRouting.BypassMainlandChina.value)

# ALL BUILTIN ROUTING VALUE
_TRANSLATABLE_BUILTIN_ROUTING = [
    _('Bypass Mainland China'),
    _('Global'),
    _('Custom'),
]


class RoutingChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        self.routingValue = kwargs.pop('routingValue', None)

        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        textEnglish = self.routingValue or self.textEnglish

        if AppSettings.get('Routing') != textEnglish:
            AppSettings.set('Routing', textEnglish)

            if APP().isSystemTrayConnected():
                APP().systemTray.ConnectAction.doReconnect()


class RoutingAction(AppQAction):
    def __init__(self, **kwargs):
        if AppSettings.get('Routing') == 'Bypass':
            # Update value for backward compatibility
            AppSettings.set('Routing', AppBuiltinRouting.BypassMainlandChina.value)

        super().__init__(
            _('Routing'),
            icon=bootstrapIcon('shuffle.svg'),
            menu=AppQMenu(),
            **kwargs,
        )
        self.rebuildMenu()
        self._menu.aboutToShow.connect(self.rebuildMenu)

    def routingActions(self):
        actions = list(
            RoutingChildAction(
                _(routing.value),
                checkable=True,
                checked=AppSettings.get('Routing') == routing.value,
            )
            for routing in AppBuiltinRouting
        )

        customActions = list()

        for unique, routing in Storage.UserRoutings().items():
            if not routing.get('enabled', True):
                continue

            action = RoutingChildAction(
                routing.get('remark', ''),
                routingValue=f'Custom:{unique}',
                checkable=True,
                checked=AppSettings.get('Routing') == f'Custom:{unique}',
            )
            customActions.append(action)

        if customActions:
            actions.extend([AppQSeperator(), *customActions])

        return actions

    def rebuildMenu(self):
        self._menu.clear()
        self._actionGroup = AppQActionGroup(self)

        for action in self.routingActions():
            if isinstance(action, AppQSeperator):
                self._menu.addSeparator()
            else:
                self._menu.addAction(action)
                self._actionGroup.addAction(action)

    def getGlobalAction(self):
        # 2nd action
        return self._menu.actions()[1]
