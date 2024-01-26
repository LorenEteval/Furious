from __future__ import annotations

from abc import ABC
from typing import Any

__all__ = ['Encoder']


class Encoder(ABC):
    def encode(self, data: Any, **kwargs) -> Any:
        raise NotImplementedError

    def decode(self, data: Any, **kwargs) -> Any:
        raise NotImplementedError
