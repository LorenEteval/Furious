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

"""Provide bundled enum."""

from __future__ import annotations

from enum import Enum

__all__ = [
    'ApplicationTheme',
    'AppBuiltinCommand',
    'AppBuiltinRouting',
    'AppBuiltinProxyMode',
]


class ApplicationTheme(Enum):
    """Enumerate the persisted application appearance preferences."""

    System = 'System'
    Light = 'Light'
    Dark = 'Dark'


class AppBuiltinCommand(Enum):
    """Enumerate app builtin command."""

    Empty = 'empty'
    RunAs = 'runas'
    Clear = 'clear'


class AppBuiltinRouting(Enum):
    """Enumerate app builtin routing."""

    BypassMainlandChina = 'Bypass Mainland China'
    Global = 'Global'
    Custom = 'Custom'


class AppBuiltinProxyMode(Enum):
    """Enumerate app builtin proxy mode."""

    Auto = 'Auto'
    NoChanges = 'NoChanges'
