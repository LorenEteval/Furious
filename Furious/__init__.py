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

"""Initialize Furious without eagerly loading its Qt resource module."""

from __future__ import annotations

from importlib import import_module

__all__ = ['AppResources']


def __getattr__(name: str):
    """Load generated Qt resources only when requested by the application."""
    if name != 'AppResources':
        raise AttributeError(name)

    resources = import_module('.Frozenlib.AppResources', __name__)

    globals()[name] = resources

    return resources
