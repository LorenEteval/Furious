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

"""Define display fields for server-table rows."""

from __future__ import annotations

__all__ = ['UserServersTableItem']


class UserServersTableItem:
    """Define the display fields required by a server-table row."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserServersTableItem."""
        super().__init__(*args, **kwargs)

    @property
    def itemRemark(self) -> str:
        """Return the item remark value."""
        return ''

    @property
    def itemProtocol(self) -> str:
        """Return the item protocol value."""
        return ''

    @property
    def itemAddress(self) -> str:
        """Return the item address value."""
        return ''

    @property
    def itemPort(self) -> str:
        """Return the item port value."""
        return ''

    @property
    def itemTransport(self) -> str:
        """Return the item transport value."""
        return ''

    @property
    def itemTLS(self) -> str:
        """Return the item TLS value."""
        return ''

    @property
    def itemSubscription(self) -> str:
        """Return the item subscription value."""
        return ''

    @property
    def itemLatency(self) -> str:
        """Return the item latency value."""
        return ''

    @property
    def itemSpeed(self) -> str:
        """Return the item speed value."""
        return ''
