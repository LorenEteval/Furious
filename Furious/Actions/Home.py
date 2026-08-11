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

"""Provide the tray action that foregrounds the Home page."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

__all__ = ['ShowHomePageAction']


class ShowHomePageAction(AppQAction):
    """Foreground the main window and navigate to server management."""

    def __init__(self, **kwargs):
        """Initialize the Home-page navigation action."""
        super().__init__(
            _('Show Home Page...'),
            icon=bootstrapIcon('house-door.svg'),
            **kwargs,
        )

        self._setDescription()

    def _setDescription(self):
        """Apply translated explanatory text to hover/status surfaces."""
        description = _('Show the server management Home page')

        self.setToolTip(description)
        self.setStatusTip(description)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        mainWindow = APP().mainWindow

        if mainWindow.isMinimized():
            mainWindow.showNormal()
        else:
            mainWindow.show()

        mainWindow.showPage('home')
        mainWindow.raise_()
        mainWindow.activateWindow()

    def retranslate(self):
        """Refresh the action text and explanatory hover text."""
        super().retranslate()

        self._setDescription()
