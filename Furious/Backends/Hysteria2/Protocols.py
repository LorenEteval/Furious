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

"""Contribute the Hysteria 2 profile and editor capability."""

from __future__ import annotations

from Furious.Backends.Configuration import (
    BLANK_CONFIG_HYSTERIA2,
    ConfigHysteria2,
)
from Furious.Plugins.API import (
    ProtocolDescriptor,
    ProtocolHandler,
    ProtocolParseResult,
)

from urllib.parse import unquote, urlsplit

import copy

__all__ = ['HYSTERIA2_PROTOCOL_HANDLERS']


def _placeholder(x):
    return x


_ = _placeholder

_TRANSLATABLE = (
    _('Add Hysteria2 Server...'),
    _('Add Hysteria2 Server'),
)


class Hysteria2ProtocolHandler(ProtocolHandler):
    """Own Hysteria 2 URI, mapping, validation, and export behavior."""

    descriptor = ProtocolDescriptor(
        id='hysteria2',
        displayName='Hysteria2',
        addActionText='Add Hysteria2 Server...',
        editorWindowTitle='Add Hysteria2 Server',
        menuOrder=60,
        configurationSchema={'type': 'object', 'required': ('server', 'auth')},
        translatable=True,
    )
    schemes = (
        'hy2',
        'hysteria2',
        'hysteria2+realm',
        'hysteria2+realm+http',
    )

    def supports(self, configuration) -> bool:
        """Return whether *configuration* is a Hysteria 2 profile."""
        return isinstance(configuration, ConfigHysteria2)

    def parse(self, uri: str, **kwargs):
        """Parse a Hysteria 2 share URI, including Realm mode."""
        factory = ConfigHysteria2(uri)

        return (
            ProtocolParseResult(
                factory,
                {'displayName': unquote(urlsplit(uri).fragment)},
            )
            if factory.isValid()
            else None
        )

    def fromMapping(self, configuration, **kwargs):
        """Recognize a Hysteria 2 client configuration mapping."""
        if configuration.get('server') is None:
            return None

        fields = (
            'auth',
            'tls',
            'transport',
            'quic',
            'bandwidth',
            'tcpForwarding',
            'udpForwarding',
            'tcpTProxy',
            'udpTProxy',
            'tun',
            'fastOpen',
            'lazy',
        )

        if any(configuration.get(field) is not None for field in fields) or isinstance(
            configuration.get('obfs'), dict
        ):
            return ConfigHysteria2(configuration)

        return None

    def blank(self, **kwargs):
        """Create a blank Hysteria 2 client profile."""
        return ConfigHysteria2(copy.deepcopy(BLANK_CONFIG_HYSTERIA2))

    def export(self, configuration, remark: str = '') -> str:
        """Export a Hysteria 2 profile."""
        return configuration.toURI(remark) if self.supports(configuration) else ''


HYSTERIA2_PROTOCOL_HANDLERS = (Hysteria2ProtocolHandler(),)
