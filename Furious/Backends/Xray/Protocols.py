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

"""Contribute isolated Xray protocol parsing capabilities."""

from __future__ import annotations

from Furious.Backends.Configuration import (
    BLANK_CONFIG_XRAY,
    ConfigXray,
    configXrayEmptyProxyOutboundObject,
)
from Furious.Backends.ShadowsocksURI import (
    SHADOWSOCKS_PLUGIN_METADATA_KEY,
    parseShadowsocksURI,
)
from Furious.Backends.SocksURI import (
    SOCKS_URI_SCHEMES,
    SocksURIData,
    SocksURIError,
    serializeSocksURI,
)
from Furious.Plugins.API import (
    ProtocolDescriptor,
    ProtocolHandler,
    ProtocolParseResult,
)

import copy

__all__ = ['XRAY_PROTOCOL_HANDLERS']


class XrayProtocolHandler(ProtocolHandler):
    """Adapt one Xray outbound protocol to the host protocol contract."""

    def __init__(
        self,
        descriptor,
        schemes,
        parserName,
    ):
        """Store immutable dispatch metadata for one Xray protocol."""
        self.descriptor = descriptor
        self.schemes = tuple(schemes)
        self._parserName = parserName

    @property
    def protocolId(self) -> str:
        """Return the normalized Xray outbound protocol identifier."""
        return self.descriptor.id.casefold()

    def supports(self, configuration) -> bool:
        """Return whether *configuration* uses this Xray outbound protocol."""
        return (
            isinstance(configuration, ConfigXray)
            and configuration.proxyProtocol.casefold() == self.protocolId
        )

    def parse(self, uri: str, **kwargs):
        """Parse this handler's URI directly into an Xray configuration."""
        parser = getattr(ConfigXray, self._parserName)
        remark, proxyOutbound = parser(uri)
        metadata = {'displayName': remark}

        if self.protocolId == 'shadowsocks':
            plugin = parseShadowsocksURI(uri).plugin

            if plugin:
                metadata[SHADOWSOCKS_PLUGIN_METADATA_KEY] = plugin

        if (
            not proxyOutbound
            or proxyOutbound.get('protocol', '').casefold() != self.protocolId
        ):
            return None

        config = copy.deepcopy(BLANK_CONFIG_XRAY)
        config['outbounds'][0] = proxyOutbound

        return ProtocolParseResult(
            ConfigXray(config),
            metadata,
        )

    def fromMapping(self, configuration, **kwargs):
        """Recognize a full Xray mapping by its tagged proxy outbound."""
        outbounds = configuration.get('outbounds')

        if not isinstance(outbounds, list):
            return None

        for outbound in outbounds:
            if (
                isinstance(outbound, dict)
                and outbound.get('tag') == 'proxy'
                and str(outbound.get('protocol', '')).casefold() == self.protocolId
            ):
                return ConfigXray(configuration)

        return None

    def blank(self, **kwargs):
        """Create a blank full Xray configuration for this protocol."""
        config = copy.deepcopy(BLANK_CONFIG_XRAY)
        config['outbounds'][0] = configXrayEmptyProxyOutboundObject(self.descriptor.id)

        return ConfigXray(config)

    def export(self, configuration, remark: str = '') -> str:
        """Export an owned Xray configuration to its share-link format."""
        return configuration.toURI(remark) if self.supports(configuration) else ''

    def exportProfile(self, profile, remark: str = '') -> str:
        """Export Xray profile metadata required by protocol share formats."""
        configuration = getattr(profile, 'connection', profile)

        return (
            configuration.toURI(
                remark,
                profileMetadata=getattr(profile, 'metadata', None),
            )
            if self.supports(configuration)
            else ''
        )


class SocksProtocolHandler(XrayProtocolHandler):
    """Validate SOCKS fields through the same codec used for sharing."""

    def validate(self, configuration):
        """Return semantic SOCKS endpoint validation errors."""
        if not self.supports(configuration):
            return ('Unsupported protocol',)

        server = configuration.proxyServerObject

        try:
            serializeSocksURI(
                SocksURIData(
                    server.get('address', ''),
                    server.get('port', 0),
                    server.get('user', ''),
                    server.get('pass', ''),
                )
            )
        except (SocksURIError, TypeError, ValueError) as ex:
            return (str(ex),)

        return tuple()


def _placeholder(x):
    return x


_ = _placeholder

_TRANSLATABLE = (
    _('Add VMess Server...'),
    _('Add VLESS Server...'),
    _('Add Shadowsocks Server...'),
    _('Add Trojan Server...'),
    _('Add SOCKS Server...'),
)

XRAY_PROTOCOL_HANDLERS = (
    XrayProtocolHandler(
        ProtocolDescriptor(
            'VMess',
            'VMess',
            'Add VMess Server...',
            10,
            configurationSchema={
                'type': 'object',
                'required': ('outbounds',),
                'proxyProtocol': 'vmess',
            },
            translatable=True,
        ),
        ('vmess',),
        'URI2ProxyOutboundObjectVMess',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor(
            'VLESS',
            'VLESS',
            'Add VLESS Server...',
            20,
            configurationSchema={
                'type': 'object',
                'required': ('outbounds',),
                'proxyProtocol': 'vless',
            },
            translatable=True,
        ),
        ('vless',),
        'URI2ProxyOutboundObjectVLESS',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor(
            'Shadowsocks',
            'Shadowsocks',
            'Add Shadowsocks Server...',
            30,
            configurationSchema={
                'type': 'object',
                'required': ('outbounds',),
                'proxyProtocol': 'shadowsocks',
            },
            translatable=True,
        ),
        ('ss',),
        'URI2ProxyOutboundObjectSS',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor(
            'Trojan',
            'Trojan',
            'Add Trojan Server...',
            40,
            configurationSchema={
                'type': 'object',
                'required': ('outbounds',),
                'proxyProtocol': 'trojan',
            },
            translatable=True,
        ),
        ('trojan',),
        'URI2ProxyOutboundObjectTrojan',
    ),
    SocksProtocolHandler(
        ProtocolDescriptor(
            'SOCKS',
            'SOCKS',
            'Add SOCKS Server...',
            70,
            True,
            {
                'type': 'object',
                'required': ('outbounds',),
                'proxyProtocol': 'socks',
            },
            True,
        ),
        SOCKS_URI_SCHEMES,
        'URI2ProxyOutboundObjectSocks',
    ),
)
