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
from Furious.Plugins.API import ProtocolDescriptor, ProtocolHandler

import copy

__all__ = ['HYSTERIA2_PROTOCOL_HANDLERS']


class Hysteria2ProtocolHandler(ProtocolHandler):
    """Own Hysteria 2 URI, mapping, blank-profile, and editor behavior."""

    descriptor = ProtocolDescriptor(
        'hysteria2',
        'Hysteria2',
        'Add Hysteria2 Server...',
        60,
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
        factory = ConfigHysteria2(uri, **kwargs)

        return factory if factory.isValid() else None

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
            return ConfigHysteria2(configuration, **kwargs)

        return None

    def blank(self, **kwargs):
        """Create a blank Hysteria 2 client profile."""
        return ConfigHysteria2(copy.deepcopy(BLANK_CONFIG_HYSTERIA2), **kwargs)

    def export(self, configuration, remark: str = '') -> str:
        """Export a Hysteria 2 profile."""
        return configuration.toURI(remark) if self.supports(configuration) else ''

    def createEditor(self, parent=None, **kwargs):
        """Create the Hysteria 2 editor on demand."""
        from .Editor import Hysteria2Editor

        return Hysteria2Editor(parent=parent, **kwargs)


HYSTERIA2_PROTOCOL_HANDLERS = (Hysteria2ProtocolHandler(),)
