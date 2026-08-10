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

"""Contribute the Hysteria 1 profile and editor capability."""

from __future__ import annotations

from Furious.Backends.Configuration import (
    BLANK_CONFIG_HYSTERIA1,
    ConfigHysteria1,
)
from Furious.Plugins.API import (
    ProtocolDescriptor,
    ProtocolHandler,
    ProtocolParseResult,
)

from urllib.parse import unquote, urlsplit

import copy

__all__ = ['HYSTERIA1_PROTOCOL_HANDLERS']


def _placeholder(x):
    return x


_ = _placeholder

_TRANSLATABLE = (_('Add Hysteria1 Server...'),)


class Hysteria1ProtocolHandler(ProtocolHandler):
    """Own Hysteria 1 URI, mapping, validation, and export behavior."""

    descriptor = ProtocolDescriptor(
        'hysteria1',
        'Hysteria1',
        'Add Hysteria1 Server...',
        50,
        True,
        {'type': 'object', 'required': ('server',)},
        True,
    )
    schemes = ('hysteria',)

    def supports(self, configuration) -> bool:
        """Return whether *configuration* is a Hysteria 1 profile."""
        return isinstance(configuration, ConfigHysteria1)

    def parse(self, uri: str, **kwargs):
        """Parse a Hysteria 1 share URI."""
        factory = ConfigHysteria1(uri)

        return (
            ProtocolParseResult(
                factory,
                {'displayName': unquote(urlsplit(uri).fragment)},
            )
            if factory.isValid()
            else None
        )

    def fromMapping(self, configuration, **kwargs):
        """Recognize a Hysteria 1 client configuration mapping."""
        if configuration.get('server') is None:
            return None

        fields = (
            'protocol',
            'up_mbps',
            'down_mbps',
            'auth_str',
            'alpn',
            'server_name',
            'insecure',
            'recv_window_conn',
            'recv_window',
            'fast_open',
            'lazy_start',
        )

        if any(configuration.get(field) is not None for field in fields) or isinstance(
            configuration.get('obfs'), str
        ):
            return ConfigHysteria1(configuration)

        return None

    def blank(self, **kwargs):
        """Create a blank Hysteria 1 client profile."""
        return ConfigHysteria1(copy.deepcopy(BLANK_CONFIG_HYSTERIA1))

    def export(self, configuration, remark: str = '') -> str:
        """Export a Hysteria 1 profile."""
        return configuration.toURI(remark) if self.supports(configuration) else ''


HYSTERIA1_PROTOCOL_HANDLERS = (Hysteria1ProtocolHandler(),)
