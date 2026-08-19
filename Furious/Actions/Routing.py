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

"""Present shared routing state through the tray action menu."""

from __future__ import annotations

from Furious.Frozenlib import AppRoutingController
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore

__all__ = ['RoutingAction']

# ALL BUILTIN ROUTING VALUE
_TRANSLATABLE_BUILTIN_ROUTING = [
    _('Bypass Mainland China'),
    _('Global'),
    _('Custom'),
]


class RoutingChildAction(AppQAction):
    """Forward one tray route choice to the shared controller."""

    def __init__(self, *args, routingValue: str, **kwargs):
        """Initialize the RoutingChildAction."""
        self.routingValue = routingValue

        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        AppRoutingController().selectRouting(self.routingValue)


class RoutingAction(AppQAction):
    """Render application routing options as a synchronized tray menu."""

    def __init__(self, **kwargs):
        """Initialize the RoutingAction."""
        self.controller = AppRoutingController()

        super().__init__(
            _('Routing'),
            icon=bootstrapIcon('shuffle.svg'),
            menu=AppQMenu(),
            **kwargs,
        )

        self.controller.stateChanged.connect(self._applyState)
        self.controller.interactionEnabledChanged.connect(self.setEnabled)

        self._applyState(*self.controller.state())

    def routingActions(self, options, routing: str):
        """Build tray actions from one shared controller snapshot."""
        actions = list()

        for option in options:
            if option.separatorBefore and actions:
                actions.append(AppQSeparator())

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

    @QtCore.Slot(object, str)
    def _applyState(self, options, routing: str):
        """Rebuild the tray menu from one controller state snapshot."""
        oldActionGroup = getattr(self, '_actionGroup', None)

        self._menu.clear()
        self._menu._actions.clear()

        if oldActionGroup is not None:
            oldActionGroup.deleteLater()

        self._actionGroup = AppQActionGroup(self)

        actions = self.routingActions(options, routing)

        for action in actions:
            if isinstance(action, AppQSeparator):
                self._menu._actions.append(action)
                self._menu.addSeparator()
            else:
                self._menu._actions.append(action)
                self._menu.addAction(action)
                self._actionGroup.addAction(action)

        self.setVisible(bool(actions))
        self.setEnabled(self.controller.interactionEnabled)

    def rebuildMenu(self):
        """Refresh plugin options immediately before the tray menu opens."""
        self.controller.refresh(force=True)
