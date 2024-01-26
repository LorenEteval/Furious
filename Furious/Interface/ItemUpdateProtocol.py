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

            # Should not reach here.
