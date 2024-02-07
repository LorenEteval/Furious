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
