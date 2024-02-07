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

from typing import Any, Sequence

__all__ = ['ItemUpdateProtocol']


class ItemUpdateProtocol:
    def __init__(self, sequence: Sequence, currentIndex: int, currentItem: Any):
        self.sequence = sequence
        self.currentIndex = currentIndex
        self.currentItem = currentItem

    def currentItemDeleted(self, *args, **kwargs) -> bool:
        return self.currentIndex < 0 or self.currentIndex >= len(self.sequence)

    def updateImpl(self, *args, **kwargs):
        raise NotImplementedError

    def updateResult(self):
        if self.currentItemDeleted():
            # Deleted. Do nothing
            return

        if id(self.sequence[self.currentIndex]) == id(self.currentItem):
            self.updateImpl()
        else:
            # Linear find and update
            for index, item in enumerate(self.sequence):
                if id(item) == id(self.currentItem):
                    # Found. Update index
                    self.currentIndex = index
                    self.updateImpl()

                    # Updated
                    break

            # Not found. Do nothing
