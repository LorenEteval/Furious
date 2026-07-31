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

"""Define configuration-editor binding interfaces."""

from __future__ import annotations

from typing import Any

__all__ = ['GuiEditorItemFactory', 'GuiEditorItemWidgetContainer']


class GuiEditorItemFactory:
    """Define the interface and shared behavior for GUI editor item objects."""
    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemFactory."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, *args, **kwargs) -> Any:
        """Apply the current editor value to the configuration."""
        raise NotImplementedError

    def factoryToInput(self, *args, **kwargs) -> Any:
        """Load the configuration value into the editor."""
        raise NotImplementedError


class GuiEditorItemWidgetContainer(GuiEditorItemFactory):
    """Bind one or more editor widgets to configuration data."""
    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemWidgetContainer."""
        super().__init__(*args, **kwargs)

    def widgets(self) -> Any:
        """Return the widgets owned by this editor item."""
        raise NotImplementedError
