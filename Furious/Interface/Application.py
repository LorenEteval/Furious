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

"""Define the contract for the top-level application runner."""

from __future__ import annotations

from enum import Enum

__all__ = ['ApplicationRunner']


class ApplicationRunner:
    """Define the lifecycle contract for the top-level application runner."""

    class ExitCode(Enum):
        """Enumerate process exit codes."""

        ExitSuccess = 0
        UnknownException = 61
        AssertionError = 63

    def __init__(self, *args, **kwargs):
        """Initialize the application runner."""
        super().__init__(*args, **kwargs)

    def run(self):
        """Run the application factory task."""
        raise NotImplementedError
