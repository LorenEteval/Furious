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

"""Provide the compatibility action used by the Settings-page TUN control."""

from __future__ import annotations

from Furious.Controllers import SettingsController
from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

__all__ = ['TUNModeAction']


class TUNModeAction(AppQAction):
    """Handle the TUN mode action."""

    def __init__(self, **kwargs):
        """Initialize the TUNModeAction."""
        if PLATFORM == 'Linux':
            super().__init__(_('TUN Mode'), **kwargs)
        else:
            if SystemRuntime.isAdmin():
                super().__init__(_('TUN Mode'), **kwargs)
            else:
                if ADMINISTRATOR_NAME == 'Administrator':
                    text = _('TUN Mode Disabled (Administrator)')
                else:
                    text = _('TUN Mode Disabled (Superuser)')

                super().__init__(text, **kwargs)

                self.setDisabled(True)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        SettingsController.setTUNMode(checked)
