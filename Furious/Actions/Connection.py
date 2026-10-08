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
    ConnectionError,
    ConnectionState,
)
from Furious.Frozenlib import (
    APP,
    AppConnectionController,
    AppSettings,
    AppSystemTray,
    Mixins,
)
from Furious.Qt import AppQAction, AppQMessageBox, bootstrapIcon, connectWeakly
from Furious.Qt import gettext as _
from Furious.Widget.ConnectionProgressWidget import ConnectionProgressWidget

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from shiboken6 import isValid

__all__ = ['ConnectAction', 'ConnectionErrorMessageBox']

_TRANSLATABLE_CONNECTION_STATES = (
    _('Connect'),
    _('Connecting'),
    _('Disconnect'),
    _('Disconnecting'),
)


class ConnectionErrorMessageBox(AppQMessageBox):
    """Present one captured connection failure with copy and log-navigation actions."""

    def __init__(self, error: ConnectionError):
        super().__init__(
            icon=self.Icon.Critical,
            heading=error.title,
            text=error.message,
            buttons=self.StandardButton.Close,
        )

        self.setInformativeText(error.details)

        self.textLabel.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self.informativeLabel.setTextFormat(QtCore.Qt.TextFormat.PlainText)

        self._errorText = '\n\n'.join(
            text for text in (error.title, error.message, error.details) if text
        )

        self.copyErrorButton = self.addButton(
            _('Copy Error'), self.ButtonRole.ActionRole, closeOnClick=False
        )
        self.openLogsButton = self.addButton(_('Open Logs'), self.ButtonRole.ActionRole)

        connectWeakly(self.copyErrorButton.clicked, self, '_copyError')
        connectWeakly(self.openLogsButton.clicked, self, '_openLogs')

        window = getattr(APP(), 'mainWindow', None)

        self.openLogsButton.setEnabled(window is not None and isValid(window))

        self.setDefaultButton(self.StandardButton.Close)
        self.setEscapeButton(self.StandardButton.Close)

    @QtCore.Slot(bool)
    def _copyError(self, _checked=False):
        """Copy the original failure while keeping its dialog open."""
        QApplication.clipboard().setText(self._errorText)

    @QtCore.Slot(bool)
    def _openLogs(self, _checked=False):
        """Resolve the application window after the error dialog has completed."""
        window = getattr(APP(), 'mainWindow', None)

        if window is None or not isValid(window):
            return

        if window.isMinimized():
            window.showNormal()
        else:
            window.show()

        if not isValid(window):
            return

        window.showLogPage()

        if not isValid(window):
            return

        window.raise_()

        if isValid(window):
            window.activateWindow()


class ConnectAction(AppQAction):
    """Adapt connection state and operations to a tray QAction."""

    def __init__(self, **kwargs):
        """Bind tray presentation to the shared connection controller."""
        self.controller = AppConnectionController()

        super().__init__(
            _('Connect'),
            icon=bootstrapIcon('unlock-fill.svg'),
            checkable=True,
            **kwargs,
        )

        self.progressWidget = ConnectionProgressWidget()

        # The reusable top-level widget cannot have a QAction as QWidget parent.
        self.destroyed.connect(self.progressWidget.deleteLater)

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

        if not isValid(self) or self.controller.state is not state:
            return

        self.setChecked(
            state
            in (
                ConnectionState.Connecting,
                ConnectionState.Connected,
            )
        )

        if not isValid(self) or self.controller.state is not state:
            return

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

        if not isValid(self) or self.controller.state is not state:
            return

        self.setEnabled(self.controller.interactionEnabled)

    @QtCore.Slot()
    def showProgress(self):
        """Show connection progress when the user preference allows it."""
        if not Mixins.qObjectIsValid(self.progressWidget):
            return

        if AppSettings.isStateON_('ShowProgressBarWhenConnecting'):
            self.progressWidget.setValue(0)

            if not Mixins.qObjectIsValid(self, self.progressWidget):
                return

            self.progressWidget.start(50)
            self.progressWidget.show()

    @QtCore.Slot(bool)
    def hideProgress(self, done: bool):
        """Stop and close the connection progress presentation."""
        if not Mixins.qObjectIsValid(self.progressWidget):
            return

        if done:
            self.progressWidget.setValue(100)

            if not Mixins.qObjectIsValid(self, self.progressWidget):
                return

        self.progressWidget.close()

        if Mixins.qObjectIsValid(self, self.progressWidget):
            self.progressWidget.stop()

    @staticmethod
    @QtCore.Slot(str)
    def showNotification(message: str):
        """Present a controller notification through the system tray."""
        try:
            AppSystemTray().showMessage(message)
        except (AttributeError, RuntimeError):
            pass

    @staticmethod
    @QtCore.Slot(object)
    def showError(error: ConnectionError):
        """Present a structured controller error asynchronously."""
        if not isinstance(error, ConnectionError):
            return

        ConnectionErrorMessageBox(error).open()

    def triggeredCallback(self, checked):
        """Delegate the requested operation to the shared controller."""
        self.controller.toggle()

        # QAction toggles before its callback. Restore controller-owned state
        # when validation rejected the operation without a state transition.
        if isValid(self):
            self.syncPresentation()

    def retranslate(self):
        """Refresh the state-derived action text and icon."""
        self.syncPresentation()
