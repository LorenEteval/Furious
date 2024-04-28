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

__all__ = ['GuiVMess']

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
        'protocol': 'vmess',
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


class GuiVMessItemBasicAddress(GuiEditorItemTextInput):
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


class GuiVMessItemBasicPort(GuiEditorItemTextSpinBox):
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


class GuiVMessItemBasicId(GuiEditorItemTextInput):
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


class GuiVMessItemBasicAlterId(GuiEditorItemTextSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 65535)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundUser = getProxyOutboundUser(config)

        oldAlterId = proxyOutboundUser.get('alterId')
        newAlterId = self.value()

        if isinstance(oldAlterId, int):
            if newAlterId != oldAlterId:
                proxyOutboundUser['alterId'] = newAlterId

                return True
            else:
                return False
        else:
            proxyOutboundUser['alterId'] = newAlterId

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setValue(proxyOutboundUser.get('alterId', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiVMessItemBasicSecurity(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'aes-128-gcm',
                'chacha20-poly1305',
                'auto',
                'none',
                'zero',
            ]
        )

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        proxyOutboundUser = getProxyOutboundUser(config)

        oldSecurity = proxyOutboundUser.get('security', '')
        newSecurity = self.text()

        if isinstance(oldSecurity, str):
            if newSecurity != oldSecurity:
                proxyOutboundUser['security'] = newSecurity

                return True
            else:
                return False
        else:
            proxyOutboundUser['security'] = newSecurity

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


needTrans(
    'Basic Configuration',
    'Address',
    'Port',
)


class GuiVMessGroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiVMessItemBasicAddress(title=_('Address')),
            GuiVMessItemBasicPort(title=_('Port')),
            GuiVMessItemBasicId(title='Id', translatable=False),
            GuiVMessItemBasicAlterId(title='AlterId', translatable=False),
            GuiVMessItemBasicSecurity(title='Security', translatable=False),
        ]


needTrans('Proxy')


class GuiVMessGroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiVMess(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.VMess)

    def groupBoxSequence(self):
        return [
            GuiVMessGroupBoxBasic(),
            GuiVMessGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
