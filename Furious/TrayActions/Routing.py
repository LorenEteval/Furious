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

"""Implement tray actions for routing."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Plugins import getPluginRegistry
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
    """Handle the routing child action."""

    def __init__(self, *args, **kwargs):
        """Initialize the RoutingChildAction."""
        self.routingValue = kwargs.pop('routingValue', None)

        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        textEnglish = self.routingValue or self.textEnglish

        if AppSettings.get('Routing') != textEnglish:
            AppSettings.set('Routing', textEnglish)

            if APP().isSystemTrayConnected():
                APP().systemTray.ConnectAction.doReconnect()


class RoutingAction(AppQAction):
    """Handle the routing action."""

    def __init__(self, **kwargs):
        """Initialize the RoutingAction."""
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

    def routingActions(self):
        """Return routing actions supported by the active core plugin."""
        config = self.activeConfig()
        if config is None:
            return list()

        pluginRegistry = getPluginRegistry()
        options = pluginRegistry.routingOptions(config)
        routing = pluginRegistry.normalizeRouting(config, AppSettings.get('Routing'))
        actions = list()

        for option in options:
            if option.separatorBefore and actions:
                actions.append(AppQSeperator())

            actions.append(
                RoutingChildAction(
                    (
                        _(option.displayName)
                        if option.translatable
                        else option.displayName
                    ),
                    routingValue=option.id,
                    checkable=True,
                    checked=routing == option.id,
                )
            )

        return actions

    @staticmethod
    def activeConfig():
        """Return the currently selected server configuration, if any."""
        try:
            index = Storage.UserActivatedItemIndex()
            servers = Storage.UserServers()

            if 0 <= index < len(servers):
                return servers[index]
        except Exception:
            # The tray may be built before persistent storage is available.
            pass

        return None

    def rebuildMenu(self):
        """Handle rebuild menu for the routing action."""
        self._menu.clear()
        self._menu._actions.clear()
        self._actionGroup = AppQActionGroup(self)
        actions = self.routingActions()

        for action in actions:
            if isinstance(action, AppQSeperator):
                self._menu._actions.append(action)
                self._menu.addSeparator()
            else:
                self._menu._actions.append(action)
                self._menu.addAction(action)
                self._actionGroup.addAction(action)

        self.setVisible(bool(actions))

    def getGlobalAction(self):
        """Return the active plugin's global routing action, if supported."""
        return next(
            (
                action
                for action in self._menu._actions
                if isinstance(action, RoutingChildAction)
                and action.routingValue == AppBuiltinRouting.Global.value
            ),
            None,
        )
