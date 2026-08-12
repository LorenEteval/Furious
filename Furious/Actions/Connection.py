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

"""Present the shared connection controller as a tray action."""

from __future__ import annotations

from Furious.Controllers.ConnectionController import (
    ConnectionController,
    ConnectionError,
    ConnectionState,
)
from Furious.Frozenlib import APP, AppSettings
from Furious.Qt import AppQAction, AppQMessageBox, bootstrapIcon
from Furious.Qt import gettext as _
from Furious.Widget.ConnectionProgressWidget import ConnectionProgressWidget

from PySide6 import QtCore

__all__ = ['ConnectAction']

_TRANSLATABLE_CONNECTION_STATES = (
    _('Connect'),
    _('Connecting'),
    _('Disconnect'),
    _('Disconnecting'),
)


class ConnectAction(AppQAction):
    """Adapt connection state and operations to a tray QAction."""

    def __init__(self, controller: ConnectionController, **kwargs):
        """Bind tray presentation to the shared connection controller."""
        self.controller = controller

        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
            **kwargs,
        )

        self.progressWidget = ConnectionProgressWidget()

        self.controller.stateChanged.connect(self.syncPresentation)
        self.controller.progressStarted.connect(self.showProgress)
        self.controller.progressFinished.connect(self.hideProgress)
        self.controller.notificationRequested.connect(self.showNotification)
        self.controller.errorOccurred.connect(self.showError)

        self.syncPresentation()

    @QtCore.Slot()
    def syncPresentation(self, *_args):
        """Render the controller's state through text, icon, and action state."""
        state = self.controller.state

        self.setText(_(state.value))
        self.setChecked(
            state
            in (
                ConnectionState.Connecting,
                ConnectionState.Connected,
            )
        )
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
        self.setEnabled(self.controller.interactionEnabled)

    @QtCore.Slot()
    def showProgress(self):
        """Show connection progress when the user preference allows it."""
        if AppSettings.isStateON_('ShowProgressBarWhenConnecting'):
            self.progressWidget.setValue(0)
            self.progressWidget.start(50)
            self.progressWidget.show()

    @QtCore.Slot(bool)
    def hideProgress(self, done: bool):
        """Stop and close the connection progress presentation."""
        if done:
            self.progressWidget.setValue(100)

        self.progressWidget.close()
        self.progressWidget.stop()

    @staticmethod
    @QtCore.Slot(str)
    def showNotification(message: str):
        """Present a controller notification through the system tray."""
        try:
            APP().systemTray.showMessage(message)
        except (AttributeError, RuntimeError):
            pass

    @staticmethod
    @QtCore.Slot(object)
    def showError(error: ConnectionError):
        """Present a structured controller error asynchronously."""
        if not isinstance(error, ConnectionError):
            return

        mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
        mbox.setWindowTitle(error.title)
        mbox.setText(error.message)

        if error.details:
            mbox.setInformativeText(error.details)

        mbox.open()

    def triggeredCallback(self, checked):
        """Delegate the requested operation to the shared controller."""
        self.controller.toggle()
        # QAction toggles before its callback. Restore controller-owned state
        # when validation rejected the operation without a state transition.
        self.syncPresentation()

    def retranslate(self):
        """Refresh the state-derived action text and icon."""
        self.syncPresentation()
