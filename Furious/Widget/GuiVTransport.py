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
from Furious.Widget.GuiVTLS import *

from PySide6.QtWidgets import *

from typing import Callable

__all__ = ['GuiVTransportQGroupBox']

needTrans = functools.partial(needTransFn, source=__name__)

STREAM_NETWORK = [
    'tcp',
    'kcp',
    'ws',
    'h2',
    'quic',
    'grpc',
    'httpupgrade',
    'splithttp',
]


class GuiVTransportItemNetwork(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(STREAM_NETWORK)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        try:
            oldNetwork = streamSettings['network']
        except Exception:
            # Any non-exit exceptions

            oldNetwork = ''

        newNetwork = self.text()

        def setNewNetwork():
            streamSettings['network'] = newNetwork

            for network in STREAM_NETWORK:
                if network == newNetwork:
                    continue

                if network == 'h2':
                    networkKey = 'httpSettings'
                else:
                    networkKey = f'{network}Settings'

                # Remove irrelevant settings
                streamSettings.pop(networkKey, None)

        if isinstance(oldNetwork, str):
            if newNetwork != oldNetwork:
                setNewNetwork()

                return True
            else:
                return False
        else:
            setNewNetwork()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            streamSettings = getXrayProxyOutboundStream(config)

            self.setText(streamSettings.get('network', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeXXX(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        networkKey = kwargs.pop('networkKey', '')

        super().__init__(*args, **kwargs)

        self.networkKey = networkKey

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get(self.networkKey), dict):
            streamSettings[self.networkKey] = {}

        xxxObject = streamSettings[self.networkKey]

        try:
            oldType = xxxObject['header']['type']
        except Exception:
            # Any non-exit exceptions

            oldType = ''

        newType = self.text()

        def setNewType():
            if not isinstance(xxxObject.get('header'), dict):
                xxxObject['header'] = {}

            if newType == '':
                xxxObject['header'].pop('type', None)
            else:
                xxxObject['header']['type'] = newType

        if isinstance(oldType, str):
            if newType != oldType:
                setNewType()

                return True
            else:
                return False
        else:
            setNewType()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            xxxObject = getXrayProxyOutboundStream(config)[self.networkKey]

            self.setText(xxxObject['header']['type'])
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeTcp(GuiVTransportItemTypeXXX):
    def __init__(self, *args, **kwargs):
        networkKey = kwargs.pop('networkKey', 'tcpSettings')

        super().__init__(*args, **kwargs, networkKey=networkKey)

        self.addItems(
            [
                '',
                'none',
                'http',
            ]
        )


class GuiVTransportItemHostTcp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('tcpSettings'), dict):
            streamSettings['tcpSettings'] = {}

        tcpObject = streamSettings['tcpSettings']

        try:
            oldHost = ','.join(tcpObject['header']['request']['headers']['Host'])
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            if not isinstance(tcpObject.get('header'), dict):
                tcpObject['header'] = {}

            if not isinstance(tcpObject['header'].get('request'), dict):
                tcpObject['header']['request'] = {}

            if not isinstance(tcpObject['header']['request'].get('headers'), dict):
                tcpObject['header']['request']['headers'] = {}

            if newHost == '':
                tcpObject['header']['request']['headers'].pop('Host', None)
            else:
                tcpObject['header']['request']['headers']['Host'] = newHost.split(',')

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            tcpObject = getXrayProxyOutboundStream(config)['tcpSettings']

            self.setText(','.join(tcpObject['header']['request']['headers']['Host']))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathTcp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('tcpSettings'), dict):
            streamSettings['tcpSettings'] = {}

        tcpObject = streamSettings['tcpSettings']

        try:
            oldPath = ','.join(tcpObject['header']['request']['path'])
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            if not isinstance(tcpObject.get('header'), dict):
                tcpObject['header'] = {}

            if not isinstance(tcpObject['header'].get('request'), dict):
                tcpObject['header']['request'] = {}

            if newPath == '':
                tcpObject['header']['request'].pop('path', None)
            else:
                tcpObject['header']['request']['path'] = newPath.split(',')

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            tcpObject = getXrayProxyOutboundStream(config)['tcpSettings']

            self.setText(','.join(tcpObject['header']['request']['path']))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeKcp(GuiVTransportItemTypeXXX):
    def __init__(self, *args, **kwargs):
        networkKey = kwargs.pop('networkKey', 'kcpSettings')

        super().__init__(*args, **kwargs, networkKey=networkKey)

        self.addItems(
            [
                '',
                'none',
                'srtp',
                'utp',
                'wechat-video',
                'dtls',
                'wireguard',
                'dns',
            ]
        )


class GuiVTransportItemSeedKcp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('kcpSettings'), dict):
            streamSettings['kcpSettings'] = {}

        kcpObject = streamSettings['kcpSettings']

        try:
            oldSeed = kcpObject.get('seed', '')
        except Exception:
            # Any non-exit exceptions

            oldSeed = ''

        newSeed = self.text()

        def setNewSeed():
            if newSeed == '':
                kcpObject.pop('seed', None)
            else:
                kcpObject['seed'] = newSeed

        if isinstance(oldSeed, str):
            if newSeed != oldSeed:
                setNewSeed()

                return True
            else:
                return False
        else:
            setNewSeed()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            kcpObject = getXrayProxyOutboundStream(config)['kcpSettings']

            self.setText(kcpObject.get('seed', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostWs(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('wsSettings'), dict):
            streamSettings['wsSettings'] = {}

        wsObject = streamSettings['wsSettings']

        try:
            oldHost = wsObject['headers']['Host']
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            if not isinstance(wsObject.get('headers'), dict):
                wsObject['headers'] = {}

            if newHost == '':
                wsObject['headers'].pop('Host', None)
            else:
                wsObject['headers']['Host'] = newHost

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            wsObject = getXrayProxyOutboundStream(config)['wsSettings']

            self.setText(wsObject['headers']['Host'])
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathWs(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('wsSettings'), dict):
            streamSettings['wsSettings'] = {}

        wsObject = streamSettings['wsSettings']

        try:
            oldPath = wsObject.get('path', '')
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            if newPath == '':
                wsObject.pop('path', None)
            else:
                wsObject['path'] = newPath

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            wsObject = getXrayProxyOutboundStream(config)['wsSettings']

            self.setText(wsObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostHttpUpgrade(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('httpupgradeSettings'), dict):
            streamSettings['httpupgradeSettings'] = {}

        httpUpgradeObject = streamSettings['httpupgradeSettings']

        try:
            oldHost = httpUpgradeObject.get('host', '')
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            if newHost == '':
                httpUpgradeObject.pop('host', None)
            else:
                httpUpgradeObject['host'] = newHost

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            httpUpgradeObject = getXrayProxyOutboundStream(config)[
                'httpupgradeSettings'
            ]

            self.setText(httpUpgradeObject.get('host', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathHttpUpgrade(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('httpupgradeSettings'), dict):
            streamSettings['httpupgradeSettings'] = {}

        httpUpgradeObject = streamSettings['httpupgradeSettings']

        try:
            oldPath = httpUpgradeObject.get('path', '')
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            if newPath == '':
                httpUpgradeObject.pop('path', None)
            else:
                httpUpgradeObject['path'] = newPath

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            httpUpgradeObject = getXrayProxyOutboundStream(config)[
                'httpupgradeSettings'
            ]

            self.setText(httpUpgradeObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostSplitHttp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('splithttpSettings'), dict):
            streamSettings['splithttpSettings'] = {}

        splitHttpObject = streamSettings['splithttpSettings']

        try:
            oldHost = splitHttpObject.get('host', '')
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            if newHost == '':
                splitHttpObject.pop('host', None)
            else:
                splitHttpObject['host'] = newHost

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            splitHttpObject = getXrayProxyOutboundStream(config)['splithttpSettings']

            self.setText(splitHttpObject.get('host', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathSplitHttp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('splithttpSettings'), dict):
            streamSettings['splithttpSettings'] = {}

        splitHttpObject = streamSettings['splithttpSettings']

        try:
            oldPath = splitHttpObject.get('path', '')
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            if newPath == '':
                splitHttpObject.pop('path', None)
            else:
                splitHttpObject['path'] = newPath

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            splitHttpObject = getXrayProxyOutboundStream(config)['splithttpSettings']

            self.setText(splitHttpObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostH2(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('httpSettings'), dict):
            streamSettings['httpSettings'] = {}

        httpObject = streamSettings['httpSettings']

        try:
            oldHost = ','.join(httpObject.get('host', []))
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            if newHost == '':
                httpObject.pop('host', None)
            else:
                httpObject['host'] = newHost.split(',')

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            httpObject = getXrayProxyOutboundStream(config)['httpSettings']

            self.setText(','.join(httpObject.get('host', [])))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathH2(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('httpSettings'), dict):
            streamSettings['httpSettings'] = {}

        httpObject = streamSettings['httpSettings']

        try:
            oldPath = httpObject.get('path', '')
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            if newPath == '':
                httpObject.pop('path', None)
            else:
                httpObject['path'] = newPath

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            httpObject = getXrayProxyOutboundStream(config)['httpSettings']

            self.setText(httpObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeQuic(GuiVTransportItemTypeXXX):
    def __init__(self, *args, **kwargs):
        networkKey = kwargs.pop('networkKey', 'quicSettings')

        super().__init__(*args, **kwargs, networkKey=networkKey)

        self.addItems(
            [
                '',
                'none',
                'srtp',
                'utp',
                'wechat-video',
                'dtls',
                'wireguard',
            ]
        )


class GuiVTransportItemSecurityQuic(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'none',
                'aes-128-gcm',
                'chacha20-poly1305',
            ]
        )

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('quicSettings'), dict):
            streamSettings['quicSettings'] = {}

        quicObject = streamSettings['quicSettings']

        try:
            oldSecurity = quicObject.get('security', '')
        except Exception:
            # Any non-exit exceptions

            oldSecurity = ''

        newSecurity = self.text()

        def setNewSecurity():
            quicObject['security'] = newSecurity

        if isinstance(oldSecurity, str):
            if newSecurity != oldSecurity:
                setNewSecurity()

                return True
            else:
                return False
        else:
            setNewSecurity()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            quicObject = getXrayProxyOutboundStream(config)['quicSettings']

            self.setText(quicObject.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemKeyQuic(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('quicSettings'), dict):
            streamSettings['quicSettings'] = {}

        quicObject = streamSettings['quicSettings']

        try:
            oldKey = quicObject.get('key', '')
        except Exception:
            # Any non-exit exceptions

            oldKey = ''

        newKey = self.text()

        def setNewKey():
            if newKey == '':
                quicObject.pop('key', None)
            else:
                quicObject['key'] = newKey

        if isinstance(oldKey, str):
            if newKey != oldKey:
                setNewKey()

                return True
            else:
                return False
        else:
            setNewKey()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            quicObject = getXrayProxyOutboundStream(config)['quicSettings']

            self.setText(quicObject.get('key', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemModeGRPC(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'gun',
                'multi',
            ]
        )

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('grpcSettings'), dict):
            streamSettings['grpcSettings'] = {}

        grpcObject = streamSettings['grpcSettings']

        try:
            oldMode = grpcObject.get('multiMode', False)
        except Exception:
            # Any non-exit exceptions

            oldMode = False

        if oldMode is True:
            oldMode = 'multi'
        else:
            oldMode = 'gun'

        newMode = self.text()

        def setNewMode():
            if newMode == 'multi':
                grpcObject['multiMode'] = True
            else:
                grpcObject['multiMode'] = False

        if isinstance(oldMode, str):
            if newMode != oldMode:
                setNewMode()

                return True
            else:
                return False
        else:
            setNewMode()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            grpcObject = getXrayProxyOutboundStream(config)['grpcSettings']

            multi = grpcObject.get('multiMode', False)

            if multi is True:
                self.setText('multi')
            elif multi is False:
                self.setText('gun')
            else:
                self.setText('')
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemAuthorityGRPC(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('grpcSettings'), dict):
            streamSettings['grpcSettings'] = {}

        grpcObject = streamSettings['grpcSettings']

        try:
            oldAuthority = grpcObject.get('authority', '')
        except Exception:
            # Any non-exit exceptions

            oldAuthority = ''

        newAuthority = self.text()

        def setNewAuthority():
            if newAuthority == '':
                grpcObject.pop('authority', None)
            else:
                grpcObject['authority'] = newAuthority

        if isinstance(oldAuthority, str):
            if newAuthority != oldAuthority:
                setNewAuthority()

                return True
            else:
                return False
        else:
            setNewAuthority()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            grpcObject = getXrayProxyOutboundStream(config)['grpcSettings']

            self.setText(grpcObject.get('authority', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemServiceNameGRPC(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('grpcSettings'), dict):
            streamSettings['grpcSettings'] = {}

        grpcObject = streamSettings['grpcSettings']

        try:
            oldServiceName = grpcObject.get('serviceName', '')
        except Exception:
            # Any non-exit exceptions

            oldServiceName = ''

        newServiceName = self.text()

        def setNewServiceName():
            if newServiceName == '':
                grpcObject.pop('serviceName', None)
            else:
                grpcObject['serviceName'] = newServiceName

        if isinstance(oldServiceName, str):
            if newServiceName != oldServiceName:
                setNewServiceName()

                return True
            else:
                return False
        else:
            setNewServiceName()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            grpcObject = getXrayProxyOutboundStream(config)['grpcSettings']

            self.setText(grpcObject.get('serviceName', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportPageXXX(GuiEditorWidgetQWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setNetworkText(self, text: str):
        network = self._containers[0]

        if isinstance(network, GuiEditorItemTextComboBox):
            network.setText(text)

    def connectActivated(self, func: Callable):
        network = self._containers[0]

        if isinstance(network, GuiEditorItemTextComboBox):
            network.connectActivated(func)


class GuiVTransportPageTcp(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemTypeTcp(title='Type', translatable=False),
            GuiVTransportItemHostTcp(title='Host', translatable=False),
            GuiVTransportItemPathTcp(title='Path', translatable=False),
        ]


class GuiVTransportPageKcp(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemTypeKcp(title='Type', translatable=False),
            GuiVTransportItemSeedKcp(title='KCP seed', translatable=False),
        ]


class GuiVTransportPageWs(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemHostWs(title='Host', translatable=False),
            GuiVTransportItemPathWs(title='Path', translatable=False),
        ]


class GuiVTransportPageHttpUpgrade(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemHostHttpUpgrade(title='Host', translatable=False),
            GuiVTransportItemPathHttpUpgrade(title='Path', translatable=False),
        ]


class GuiVTransportPageSplitHttp(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemHostSplitHttp(title='Host', translatable=False),
            GuiVTransportItemPathSplitHttp(title='Path', translatable=False),
        ]


class GuiVTransportPageH2(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemHostH2(title='Host', translatable=False),
            GuiVTransportItemPathH2(title='Path', translatable=False),
        ]


class GuiVTransportPageQuic(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemTypeQuic(title='Type', translatable=False),
            GuiVTransportItemSecurityQuic(title='QUIC Security', translatable=False),
            GuiVTransportItemKeyQuic(title='QUIC Key', translatable=False),
        ]


class GuiVTransportPageGRPC(GuiVTransportPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemModeGRPC(title='gRPC mode', translatable=False),
            GuiVTransportItemAuthorityGRPC(title='gRPC authority', translatable=False),
            GuiVTransportItemServiceNameGRPC(
                title='gRPC serviceName', translatable=False
            ),
        ]


class GuiVTransportPageStackedWidget(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Corresponds to stream network
        self._pages = [
            GuiVTransportPageTcp(),
            GuiVTransportPageKcp(),
            GuiVTransportPageWs(),
            GuiVTransportPageH2(),
            GuiVTransportPageQuic(),
            GuiVTransportPageGRPC(),
            GuiVTransportPageHttpUpgrade(),
            GuiVTransportPageSplitHttp(),
        ]

        for page in self._pages:
            self.addWidget(page)

    def page(self, index: int) -> GuiVTransportPageXXX:
        return self._pages[index]

    def connectActivated(self, func: Callable):
        for page in self._pages:
            page.connectActivated(func)


needTrans(
    'Transport',
)


class GuiVTransportQGroupBox(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Transport'), **kwargs)

        self._config = ConfigurationFactory()

        self._widget = GuiVTransportPageStackedWidget()
        self._widget.connectActivated(self.handleActivated)

        layout = QFormLayout()
        layout.addRow(self._widget)

        self.setLayout(layout)

    def currentIndex(self) -> int:
        return self._widget.currentIndex()

    def setCurrentIndex(self, index: int):
        self._widget.setCurrentIndex(index)

    def page(self, index: int) -> GuiVTransportPageXXX:
        return self._widget.page(index)

    def handleActivated(self, index: int):
        page = self.page(index)
        page.factoryToInput(self._config)
        page.setNetworkText(STREAM_NETWORK[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        return self.page(self.currentIndex()).inputToFactory(config)

    def factoryToInput(self, config: ConfigurationFactory):
        # Shallow copy
        self._config = config

        streamSettings = getXrayProxyOutboundStream(config)
        network = streamSettings.get('network', '')

        if not isinstance(network, str):
            return

        def alterNetwork(sourceNetwork, targetNetwork):
            nonlocal network

            if network == sourceNetwork:
                network = targetNetwork

            streamSettings['network'] = network

        # Adjust alternative values
        # https://xtls.github.io/config/transport.html#streamsettingsobject
        alterNetwork('http', 'h2')
        alterNetwork('gun', 'grpc')
        alterNetwork('mkcp', 'kcp')

        try:
            index = STREAM_NETWORK.index(network)
        except Exception:
            # Any non-exit exceptions

            pass
        else:
            self.page(index).factoryToInput(config)
            self.setCurrentIndex(index)
