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

__all__ = ['GuiVLESS']

needTrans = functools.partial(needTransFn, source=__name__)


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
        'protocol': 'vless',
        'settings': {
            'vnext': [
                {
                    'address': '',
                    'port': 0,
                    'users': [
                        {
                            'email': PROXY_OUTBOUND_USER_EMAIL,
                        },
                    ],
                },
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
        server = proxyOutbound['settings']['vnext'][0]
    except Exception:
        # Any non-exit exceptions

        server = {}

    if not isinstance(server, dict):
        server = {}

    return server


def getProxyOutboundUser(config: ConfigurationFactory) -> dict:
    proxyOutboundServer = getProxyOutboundServer(config)

    try:
        user = proxyOutboundServer['users'][0]
    except Exception:
        # Any non-exit exceptions

        user = {}

    if not isinstance(user, dict):
        user = {}

    return user


class GuiVLESSItemBasicAddress(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundServer = getProxyOutboundServer(config)

        oldAddress = proxyOutboundServer.get('address', '')
        newAddress = self.text()

        if isinstance(oldAddress, str):
            if newAddress != oldAddress:
                if newAddress == '':
                    # Remove field
                    proxyOutboundServer.pop('address', None)
                else:
                    proxyOutboundServer['address'] = newAddress

                return True
            else:
                return False
        else:
            proxyOutboundServer['address'] = newAddress

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get('address', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVLESSItemBasicPort(GuiEditorItemTextSpinBox):
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


class GuiVLESSItemBasicId(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundUser = getProxyOutboundUser(config)

        oldId = proxyOutboundUser.get('id', '')
        newId = self.text()

        if isinstance(oldId, str):
            if newId != oldId:
                if newId == '':
                    # Remove field
                    proxyOutboundUser.pop('id', None)
                else:
                    proxyOutboundUser['id'] = newId

                return True
            else:
                return False
        else:
            proxyOutboundUser['id'] = newId

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('id', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVLESSItemBasicEncryption(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundUser = getProxyOutboundUser(config)

        oldEncryption = proxyOutboundUser.get('encryption', '')
        newEncryption = self.text()

        if isinstance(oldEncryption, str):
            if newEncryption != oldEncryption:
                if newEncryption == '':
                    # Remove field
                    proxyOutboundUser.pop('encryption', None)
                else:
                    proxyOutboundUser['encryption'] = newEncryption

                return True
            else:
                return False
        else:
            proxyOutboundUser['encryption'] = newEncryption

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('encryption', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVLESSItemBasicFlow(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'none',
                'xtls-rprx-vision',
                'xtls-rprx-vision-udp443',
            ]
        )

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundUser = getProxyOutboundUser(config)

        oldFlow = proxyOutboundUser.get('flow', '')
        newFlow = self.text()

        if isinstance(oldFlow, str):
            if newFlow != oldFlow:
                proxyOutboundUser['flow'] = newFlow

                return True
            else:
                return False
        else:
            proxyOutboundUser['flow'] = newFlow

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('flow', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


needTrans(
    'Basic Configuration',
    'Address',
    'Port',
    'Encryption',
    'Flow',
)


class GuiVLESSGroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiVLESSItemBasicAddress(title=_('Address')),
            GuiVLESSItemBasicPort(title=_('Port')),
            GuiVLESSItemBasicId(title='Id', translatable=False),
            GuiVLESSItemBasicEncryption(title=_('Encryption')),
            GuiVLESSItemBasicFlow(title=_('Flow')),
        ]


needTrans('Proxy')


class GuiVLESSGroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiVLESS(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.VLESS)

    def groupBoxSequence(self):
        return [
            GuiVLESSGroupBoxBasic(),
            GuiVLESSGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
