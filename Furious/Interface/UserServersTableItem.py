from __future__ import annotations

from abc import ABC

__all__ = ['UserServersTableItem']


class UserServersTableItem(ABC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def itemRemark(self) -> str:
        return ''

    @property
    def itemProtocol(self) -> str:
        return ''

    @property
    def itemAddress(self) -> str:
        return ''

    @property
    def itemPort(self) -> str:
        return ''

    @property
    def itemTransport(self) -> str:
        return ''

    @property
    def itemTLS(self) -> str:
        return ''

    @property
    def itemSubscription(self) -> str:
        return ''

    @property
    def itemLatency(self) -> str:
        return ''

    @property
    def itemSpeed(self) -> str:
        return ''
