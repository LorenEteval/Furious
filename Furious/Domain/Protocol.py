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

"""Define core-neutral proxy protocol identifiers."""

from __future__ import annotations

from enum import Enum

__all__ = ['Protocol']


class Protocol(Enum):
    """Enumerate protocol names used by built-in configuration models."""

    Unknown = 'Unknown'
    VMess = 'VMess'
    VLESS = 'VLESS'
    Shadowsocks = 'Shadowsocks'
    Socks = 'SOCKS'
    Trojan = 'Trojan'
    Hysteria1 = 'hysteria1'
    Hysteria2 = 'hysteria2'

    @staticmethod
    def toEnum(protocol: str):
        """Return the built-in identifier matching *protocol*."""
        if not isinstance(protocol, str):
            return Protocol.Unknown

        normalized = protocol.casefold()

        for value in Protocol:
            if value is not Protocol.Unknown and value.value.casefold() == normalized:
                return value

        return Protocol.Unknown
