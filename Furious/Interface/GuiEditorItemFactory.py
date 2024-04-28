# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from __future__ import annotations

from Furious.Interface.ConfigurationFactory import ConfigurationFactory

from typing import Any

__all__ = ['GuiEditorItemFactory', 'GuiEditorItemWidgetContainer']


class GuiEditorItemFactory:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> Any:
        raise NotImplementedError

    def factoryToInput(self, config: ConfigurationFactory) -> Any:
        raise NotImplementedError


class GuiEditorItemWidgetContainer(GuiEditorItemFactory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def widgets(self) -> Any:
        raise NotImplementedError
