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

"""Contribute isolated Xray protocol profile and editor capabilities."""

from __future__ import annotations

from Furious.Backends.Configuration import (
    BLANK_CONFIG_XRAY,
    ConfigXray,
    configXrayEmptyProxyOutboundObject,
)
from Furious.Plugins.API import ProtocolDescriptor, ProtocolHandler

from importlib import import_module

import copy

__all__ = ['XRAY_PROTOCOL_HANDLERS']


class XrayProtocolHandler(ProtocolHandler):
    """Adapt one Xray outbound protocol to the host protocol contract."""

    def __init__(
        self,
        descriptor,
        schemes,
        parserName,
        editorModule,
        editorType,
    ):
        """Store immutable dispatch metadata for one Xray protocol."""
        self.descriptor = descriptor
        self.schemes = tuple(schemes)
        self._parserName = parserName
        self._editorModule = editorModule
        self._editorType = editorType

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

        if (
            not proxyOutbound
            or proxyOutbound.get('protocol', '').casefold() != self.protocolId
        ):
            return None

        config = copy.deepcopy(BLANK_CONFIG_XRAY)
        config['outbounds'][0] = proxyOutbound
        factory = ConfigXray(config, **kwargs)
        factory.setExtras('remark', remark)

        return factory

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
                return ConfigXray(configuration, **kwargs)

        return None

    def blank(self, **kwargs):
        """Create a blank full Xray configuration for this protocol."""
        config = copy.deepcopy(BLANK_CONFIG_XRAY)
        config['outbounds'][0] = configXrayEmptyProxyOutboundObject(self.descriptor.id)

        return ConfigXray(config, **kwargs)

    def export(self, configuration, remark: str = '') -> str:
        """Export an owned Xray configuration to its share-link format."""
        return configuration.toURI(remark) if self.supports(configuration) else ''

    def createEditor(self, parent=None, **kwargs):
        """Load and create the protocol editor only when the GUI asks for it."""
        module = import_module(self._editorModule)
        editorType = getattr(module, self._editorType)

        return editorType(parent=parent, **kwargs)


XRAY_PROTOCOL_HANDLERS = (
    XrayProtocolHandler(
        ProtocolDescriptor('VMess', 'VMess', 'Add VMess Server...', 10),
        ('vmess',),
        'URI2ProxyOutboundObjectVMess',
        'Furious.Backends.Xray.VmessEditor',
        'VmessEditor',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor('VLESS', 'VLESS', 'Add VLESS Server...', 20),
        ('vless',),
        'URI2ProxyOutboundObjectVLESS',
        'Furious.Backends.Xray.VlessEditor',
        'VlessEditor',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor(
            'Shadowsocks',
            'Shadowsocks',
            'Add Shadowsocks Server...',
            30,
        ),
        ('ss',),
        'URI2ProxyOutboundObjectSS',
        'Furious.Backends.Xray.ShadowsocksEditor',
        'ShadowsocksEditor',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor('Trojan', 'Trojan', 'Add Trojan Server...', 40),
        ('trojan',),
        'URI2ProxyOutboundObjectTrojan',
        'Furious.Backends.Xray.TrojanEditor',
        'TrojanEditor',
    ),
    XrayProtocolHandler(
        ProtocolDescriptor('SOCKS', 'SOCKS', 'Add SOCKS Server...', 70, True),
        ('socks', 'socks5', 'socks5h'),
        'URI2ProxyOutboundObjectSocks',
        'Furious.Backends.Xray.SocksEditor',
        'SocksEditor',
    ),
)
