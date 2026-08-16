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

"""Define UI-independent records used by the unified logging service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ['LogCategory', 'LogEntry']


@dataclass(frozen=True)
class LogCategory:
    """Describe one independently filterable source of log entries."""

    id: str
    displayName: str
    translatable: bool = False
    runtime: bool = False

    def __post_init__(self):
        """Validate the stable identifier and user-facing label."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError('log category ID cannot be empty')

        if not isinstance(self.displayName, str) or not self.displayName.strip():
            raise ValueError('log category display name cannot be empty')


@dataclass(frozen=True)
class LogEntry:
    """Capture one message together with its classification metadata."""

    message: str
    timestamp: datetime
    categoryId: str
    categoryLabel: str
    categoryTranslatable: bool = False
    source: str = ''
    severity: str = ''
    sequence: int = 0
