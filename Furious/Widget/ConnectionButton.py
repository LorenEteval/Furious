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

"""Provide a Home connection control backed by ConnectionController."""

from __future__ import annotations

from Furious.Controllers import ConnectionState
from Furious.Frozenlib import AppConnectionController, Mixins
from Furious.Qt import bootstrapIcon, AppQPushButton
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import QSizePolicy

from typing import Callable

__all__ = ['ConnectionButton']


class ConnectionButton(AppQPushButton):
    """Present connection state while retaining Home's selection policy."""

    def __init__(
        self,
        activateSelected: Callable[[], bool],
        parent=None,
    ):
        """Bind Home presentation and selection policy to the controller."""
        self.controller = AppConnectionController()
        self.activateSelected = activateSelected
        self._selectionCount = 0

        super().__init__(parent, useQSetDisabled=False)

        self.setObjectName('ConnectionButton')
        self.setMinimumWidth(124)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setIconSize(QtCore.QSize(18, 18))

        self.clicked.connect(self._handleClicked)
        self.controller.stateChanged.connect(self.syncPresentation)

        self.syncPresentation()

    def setSelectionCount(self, count: int):
        """Update the disconnected-state selection policy."""
        self._selectionCount = max(0, count)
        self.syncPresentation()

    @QtCore.Slot()
    def syncPresentation(self, *_args):
        """Render controller state while applying only Home's selection rule."""
        state = self.controller.state

        self.setText(_(state.value))
        self.setIcon(
            bootstrapIcon(
                'lock-fill.svg'
                if state
                in (
                    ConnectionState.Connecting,
                    ConnectionState.Connected,
                )
                else 'unlock-fill.svg'
            )
        )

        if state is ConnectionState.Disconnected:
            # Zero-selection remains intentionally clickable but is a no-op.
            enabled = self._selectionCount <= 1
        elif state is ConnectionState.Connected:
            # Disconnect always targets the active connection, not selection.
            enabled = True
        else:
            enabled = False

        self.setEnabled(enabled)

    @QtCore.Slot()
    def _handleClicked(self):
        """Apply Home selection policy, then delegate the lifecycle operation."""
        state = self.controller.state

        if state is ConnectionState.Disconnected:
            if self._selectionCount != 1 or not self.activateSelected():
                return

            self.controller.toggle()
        elif state is ConnectionState.Connected:
            self.controller.toggle()

    def retranslate(self):
        """Refresh state-derived Home connection text and icon."""
        self.syncPresentation()
