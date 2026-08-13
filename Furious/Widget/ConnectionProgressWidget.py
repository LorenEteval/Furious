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

"""Provide widgets for connect progress bar."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

__all__ = ['ConnectionProgressWidget']


class ConnectionProgressBar(Mixins.ConnectionAware, QProgressBar):
    """Represent auto update progress bar."""

    def __init__(self, **kwargs):
        """Initialize the connection progress bar."""
        super().__init__(**kwargs)

        self.setRange(0, 100)

        # The timer belongs to the progress bar.  Parenting it and connecting
        # to a normal method avoids a parentless timer/closure cycle surviving
        # after the widget's Qt lifetime ends.
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._advance)

        self._setConnectionState('disconnected')

    @QtCore.Slot()
    def _advance(self):
        """Advance the connection progress animation."""
        if self.value() < 90:
            self.setValue(self.value() + 1)

        if self.value() > 99:
            self.timer.stop()

    def _setConnectionState(self, state: str):
        """Expose semantic state to the application-owned progress style."""
        if self.property('connectionState') == state:
            return

        self.setProperty('connectionState', state)

        # Qt does not automatically repolish a widget after a dynamic property
        # used by a style-sheet selector changes.
        style = self.style()
        style.unpolish(self)
        style.polish(self)

        self.update()

    def start(self, msec: int):
        """Start the auto update progress bar."""
        self._setConnectionState('connecting')
        self.timer.start(msec)

    def stop(self):
        """Stop the auto update progress bar."""
        self.timer.stop()

    @staticmethod
    def getStyleSheet(theme=None):
        """Return centralized progress styling for compatibility callers."""
        if theme is None:
            try:
                theme = APP().theme()
            except Exception:
                # Any non-exit exceptions

                theme = AppStyleSheet.Light

        return AppStyleSheet.progressBarStyleSheet(theme)

    def disconnectedCallback(self):
        """Update the auto update progress bar for a disconnected state."""
        self._setConnectionState('disconnected')

    def connectedCallback(self):
        """Update the auto update progress bar for a connected state."""
        self._setConnectionState('connected')


class ConnectionProgressWidget(Mixins.QTranslatable, Mixins.ConnectionAware, QWidget):
    """Provide the connect progress bar widget."""

    def __init__(self, parent=None):
        """Initialize the connection progress widget."""
        super().__init__(parent)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setWindowIcon(AppHue.currentWindowIcon())
        self.setFixedSize(280, 61)

        # Create a progress bar widget
        self._widget = ConnectionProgressBar(parent=self)
        self._widget.setRange(0, 100)

        self._layout = QVBoxLayout()
        self._layout.addWidget(self._widget)

        self.setLayout(self._layout)

    def setValue(self, value: int):
        """Set value."""
        self._widget.setValue(value)

    def start(self, msec: int):
        """Start the connect progress bar."""
        self._widget.start(msec)

    def stop(self):
        """Stop the connect progress bar."""
        self._widget.stop()

    def disconnectedCallback(self):
        """Update the connect progress bar for a disconnected state."""
        self.setWindowIcon(AppHue.disconnectedWindowIcon())

    def connectedCallback(self):
        """Update the connect progress bar for a connected state."""
        self.setWindowIcon(AppHue.connectedWindowIcon())

    def retranslate(self):
        """Refresh translated text for the connect progress bar."""
        self.setWindowTitle(_(self.windowTitle()))
