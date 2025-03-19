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

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Widget.GuiVTransport import *
from Furious.Widget.GuiVTLS import *

__all__ = ['GuiShadowsocks']


def getProxyOutboundObject(config: ConfigurationFactory) -> dict:
    if not isinstance(config.get('outbounds'), list):
        config['outbounds'] = []

    for outbound in config['outbounds']:
        if isinstance(outbound, dict):
            tag = outbound.get('tag')

            if isinstance(tag, str) and tag == 'proxy':
                return outbound

    outboundObject = {
        'tag': 'proxy',
        'protocol': 'shadowsocks',
        'settings': {
            'servers': [
                {
                    'address': '',
                    'port': 0,
                    'method': '',
                    'password': '',
                    'email': PROXY_OUTBOUND_USER_EMAIL,
                    'ota': False,
                }
            ]
        },
        'streamSettings': {
            'network': 'tcp',
        },
        'mux': {
            'enabled': False,
            'concurrency': -1,
        },
    }

    # Proxy outbound not found. Add it
    config['outbounds'].append(outboundObject)

    return outboundObject


def getProxyOutboundServer(config: ConfigurationFactory) -> dict:
    proxyOutbound = getProxyOutboundObject(config)

    try:
        server = proxyOutbound['settings']['servers'][0]
    except Exception:
        # Any non-exit exceptions

        server = {}

    if not isinstance(server, dict):
        server = {}

    return server


class GuiSSItemTextInput(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundServer = getProxyOutboundServer(config)

        oldValue = proxyOutboundServer.get(self.key, '')
        newValue = self.text()

        if isinstance(oldValue, str):
            if newValue != oldValue:
                if newValue == '':
                    # Remove field
                    proxyOutboundServer.pop(self.key, None)
                else:
                    proxyOutboundServer[self.key] = newValue

                return True
            else:
                return False
        else:
            proxyOutboundServer[self.key] = newValue

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get(self.key, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiSSItemBasicPort(GuiEditorItemTextSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 65535)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundServer = getProxyOutboundServer(config)

        oldPort = proxyOutboundServer.get('port')
        newPort = self.value()

        if isinstance(oldPort, int):
            if newPort != oldPort:
                proxyOutboundServer['port'] = newPort

                return True
            else:
                return False
        else:
            proxyOutboundServer['port'] = newPort

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setValue(proxyOutboundServer.get('port', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiSSItemBasicMethod(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'aes-128-gcm',
                'aes-256-gcm',
                'chacha20-poly1305',
                'chacha20-ietf-poly1305',
                'xchacha20-poly1305',
                'xchacha20-ietf-poly1305',
                'none',
                'plain',
                '2022-blake3-aes-128-gcm',
                '2022-blake3-aes-256-gcm',
                '2022-blake3-chacha20-poly1305',
            ]
        )

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundServer = getProxyOutboundServer(config)

        oldMethod = proxyOutboundServer.get('method', '')
        newMethod = self.text()

        if isinstance(oldMethod, str):
            if newMethod != oldMethod:
                proxyOutboundServer['method'] = newMethod

                return True
            else:
                return False
        else:
            proxyOutboundServer['method'] = newMethod

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get('method', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiSSGroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiSSItemTextInput(title=_('Address'), key='address'),
            GuiSSItemBasicPort(title=_('Port')),
            GuiSSItemBasicMethod(title=_('Encryption')),
            GuiSSItemTextInput(title=_('Password'), key='password'),
        ]


class GuiSSGroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiShadowsocks(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Shadowsocks)

    def groupBoxSequence(self):
        return [
            GuiSSGroupBoxBasic(),
            GuiSSGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
