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

"""Provide connection controls backed by the shared connection action."""

from __future__ import annotations

from Furious.Actions.Connection import ConnectionState

from PySide6 import QtCore
from PySide6.QtWidgets import QPushButton, QSizePolicy

from typing import Callable

__all__ = ['ConnectionButton']


class ConnectionButton(QPushButton):
    """Present a shared connection action with a local selection policy."""

    def __init__(
        self,
        connectionAction,
        activateSelected: Callable[[], bool],
        parent=None,
    ):
        """Bind to one connection action without duplicating its state machine."""
        super().__init__(parent)

        self.connectionAction = connectionAction
        self.activateSelected = activateSelected
        self._selectionCount = 0

        self.setObjectName('ConnectionButton')
        self.setMinimumWidth(124)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setIconSize(QtCore.QSize(18, 18))

        self.clicked.connect(self._handleClicked)
        self.connectionAction.changed.connect(self.syncPresentation)
        self.connectionAction.stateChanged.connect(self.syncPresentation)

        self.syncPresentation()

    def setSelectionCount(self, count: int):
        """Update the disconnected-state selection policy."""
        self._selectionCount = max(0, count)
        self.syncPresentation()

    @QtCore.Slot()
    def syncPresentation(self, *_args):
        """Mirror text/icon/state while applying only Home's selection rule."""
        action = self.connectionAction
        state = action.state

        self.setText(action.text())
        self.setIcon(action.icon())

        if state is ConnectionState.Disconnected:
            # Zero-selection remains intentionally clickable but is a no-op.
            enabled = self._selectionCount <= 1 and action.isEnabled()
        elif state is ConnectionState.Connected:
            # Disconnect always targets the active connection, not selection.
            enabled = action.isEnabled()
        else:
            enabled = False

        self.setEnabled(enabled)

    @QtCore.Slot()
    def _handleClicked(self):
        """Delegate connect/disconnect to the shared action."""
        state = self.connectionAction.state

        if state is ConnectionState.Disconnected:
            if self._selectionCount != 1 or not self.activateSelected():
                return

            if self.connectionAction.state is ConnectionState.Disconnected:
                self.connectionAction.trigger()
        elif state is ConnectionState.Connected:
            self.connectionAction.trigger()
