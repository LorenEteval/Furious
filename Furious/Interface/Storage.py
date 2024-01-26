from __future__ import annotations

from abc import ABC
from typing import Any

__all__ = ['StorageFactory']


class StorageFactory(ABC):
    def sync(self):
        raise NotImplementedError

    def data(self) -> Any:
        raise NotImplementedError
