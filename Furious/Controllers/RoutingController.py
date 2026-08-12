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

"""Own application routing selection independently from its UI controls."""

from __future__ import annotations

from Furious.Frozenlib import (
    APP,
    AppBuiltinRouting,
    AppSettings,
    registerAppSettings,
)
from Furious.Plugins import getPluginRegistry
from Furious.Repository import Storage

from PySide6 import QtCore

__all__ = ['RoutingController']

registerAppSettings('Routing', default=AppBuiltinRouting.BypassMainlandChina.value)


class RoutingController(QtCore.QObject):
    """Expose one routing state shared by every application surface."""

    stateChanged = QtCore.Signal(object, str)
    optionsChanged = QtCore.Signal(object)
    routingChanged = QtCore.Signal(str)
    interactionEnabledChanged = QtCore.Signal(bool)

    def __init__(self, parent=None):
        """Initialize persisted routing state and plugin-provided options."""
        super().__init__(parent)

        if AppSettings.get('Routing') == 'Bypass':
            # Update the value used by older Furious releases.
            AppSettings.set('Routing', AppBuiltinRouting.BypassMainlandChina.value)

        self._options = tuple()
        self._routing = str(AppSettings.get('Routing'))
        self._interactionEnabled = True

        self.refresh()

    @staticmethod
    def activeConfiguration():
        """Return the active server configuration, if one is available."""
        try:
            index = Storage.UserActivatedItemIndex()
            servers = Storage.UserServers()

            if 0 <= index < len(servers):
                return servers[index]
        except Exception:
            # The controller can exist before persistent storage is ready.
            pass

        return None

    @property
    def options(self):
        """Return routing options supported by the active configuration."""
        return self._options

    @property
    def routing(self) -> str:
        """Return the normalized route shown by routing controls."""
        return self._routing

    @property
    def interactionEnabled(self) -> bool:
        """Return whether users may change routing at this lifecycle state."""
        return self._interactionEnabled

    def state(self):
        """Return the current immutable option and selection snapshot."""
        return self.options, self.routing

    def refresh(self, *, force=False):
        """Refresh routing capabilities from the active proxy-core plugin."""
        config = self.activeConfiguration()
        registry = getPluginRegistry()
        options = registry.routingOptions(config) if config is not None else tuple()
        routing = (
            registry.normalizeRouting(config, AppSettings.get('Routing'))
            if config is not None
            else str(AppSettings.get('Routing'))
        )

        optionsChanged = options != self._options
        routingChanged = routing != self._routing

        self._options = options
        self._routing = routing

        if optionsChanged:
            self.optionsChanged.emit(options)

        if routingChanged:
            self.routingChanged.emit(routing)

        if force or optionsChanged or routingChanged:
            self.stateChanged.emit(options, routing)

        return self.state()

    @QtCore.Slot(str)
    def selectRouting(self, routing: str) -> bool:
        """Persist a supported route and reconnect the active proxy if needed."""
        options, _current = self.refresh()

        if routing not in tuple(option.id for option in options):
            return False

        if AppSettings.get('Routing') == routing:
            return False

        AppSettings.set('Routing', routing)

        self.refresh(force=True)

        app = APP()

        if app is not None and app.connectionController.isConnected():
            app.connectionController.startReconnection()

        return True

    @QtCore.Slot(bool)
    def setInteractionEnabled(self, enabled: bool):
        """Publish whether routing controls may accept user interaction."""
        enabled = bool(enabled)

        if enabled == self._interactionEnabled:
            return

        self._interactionEnabled = enabled
        self.interactionEnabledChanged.emit(enabled)
