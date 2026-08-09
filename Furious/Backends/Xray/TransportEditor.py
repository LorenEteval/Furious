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

"""Provide widgets for GUI v transport."""

from __future__ import annotations

from Furious.Interface import *
from Furious.Models import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Backends.Configuration import *

from PySide6.QtWidgets import *

from typing import Callable

__all__ = ['GuiVTransportQGroupBox']

STREAM_NETWORK = [
    'tcp',
    'raw',
    'kcp',
    'ws',
    'h2',
    'quic',
    'grpc',
    'httpupgrade',
    'splithttp',
    'xhttp',
    'hysteria',
]


class GuiVTransportItemNetwork(GuiEditorItemTextComboBox):
    """Represent GUI v transport item network."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemNetwork."""
        super().__init__(*args, **kwargs)

        self.addItems(STREAM_NETWORK)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        try:
            oldNetwork = streamSettings['network']
        except Exception:
            # Any non-exit exceptions

            oldNetwork = ''

        newNetwork = self.text()

        def setNewNetwork():
            """Set new network."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            streamSettings = ConfigXray.getProxyOutboundStream(config)

            self.setText(streamSettings.get('network', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemFinalMask(GuiEditorItemTextInput):
    """Represent GUI v transport item final mask."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemFinalMask."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        oldFinalMaskObject = streamSettings.get('finalmask')
        newFinalMaskText = self.text().strip()

        if newFinalMaskText == '':
            if 'finalmask' in streamSettings:
                streamSettings.pop('finalmask', None)

                return True

            return False

        try:
            newFinalMaskObject = UJSONEncoder.decode(newFinalMaskText)
        except Exception:
            # Any non-exit exceptions

            newFinalMaskObject = {}

        if not isinstance(oldFinalMaskObject, dict):
            streamSettings['finalmask'] = newFinalMaskObject

            return True

        if newFinalMaskObject != oldFinalMaskObject:
            streamSettings['finalmask'] = newFinalMaskObject

            return True

        return False

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            finalMaskObject = ConfigXray.getProxyOutboundStream(config)['finalmask']

            self.setText(UJSONEncoder.encode(finalMaskObject))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeXXX(GuiEditorItemTextComboBox):
    """Represent GUI v transport item type xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemTypeXXX."""
        networkKey = kwargs.pop('networkKey', '')

        super().__init__(*args, **kwargs)

        self.networkKey = networkKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new type."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xxxObject = ConfigXray.getProxyOutboundStream(config)[self.networkKey]

            self.setText(xxxObject['header']['type'])
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeTcpOrRaw(GuiVTransportItemTypeXXX):
    """Represent GUI v transport item type TCP or raw."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemTypeTcpOrRaw."""
        networkKey = kwargs.pop('networkKey', 'tcpSettings')

        super().__init__(*args, **kwargs, networkKey=networkKey)

        self.addItems(
            [
                '',
                'none',
                'http',
            ]
        )


class GuiVTransportItemHostTcpOrRaw(GuiEditorItemTextInput):
    """Represent GUI v transport item host TCP or raw."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostTcpOrRaw."""
        networkKey = kwargs.pop('networkKey', 'tcpSettings')

        super().__init__(*args, **kwargs)

        self.networkKey = networkKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get(self.networkKey), dict):
            streamSettings[self.networkKey] = {}

        tcpObject = streamSettings[self.networkKey]

        try:
            oldHost = ','.join(tcpObject['header']['request']['headers']['Host'])
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            """Set new host."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            tcpObject = ConfigXray.getProxyOutboundStream(config)[self.networkKey]

            self.setText(','.join(tcpObject['header']['request']['headers']['Host']))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathTcpOrRaw(GuiEditorItemTextInput):
    """Represent GUI v transport item path TCP or raw."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathTcpOrRaw."""
        networkKey = kwargs.pop('networkKey', 'tcpSettings')

        super().__init__(*args, **kwargs)

        self.networkKey = networkKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get(self.networkKey), dict):
            streamSettings[self.networkKey] = {}

        tcpObject = streamSettings[self.networkKey]

        try:
            oldPath = ','.join(tcpObject['header']['request']['path'])
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            """Set new path."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            tcpObject = ConfigXray.getProxyOutboundStream(config)[self.networkKey]

            self.setText(','.join(tcpObject['header']['request']['path']))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeKcp(GuiVTransportItemTypeXXX):
    """Represent GUI v transport item type kcp."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemTypeKcp."""
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
    """Represent GUI v transport item seed kcp."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemSeedKcp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new seed."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            kcpObject = ConfigXray.getProxyOutboundStream(config)['kcpSettings']

            self.setText(kcpObject.get('seed', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostWs(GuiEditorItemTextInput):
    """Represent GUI v transport item host ws."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostWs."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new host."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            wsObject = ConfigXray.getProxyOutboundStream(config)['wsSettings']

            self.setText(wsObject['headers']['Host'])
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathWs(GuiEditorItemTextInput):
    """Represent GUI v transport item path ws."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathWs."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new path."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            wsObject = ConfigXray.getProxyOutboundStream(config)['wsSettings']

            self.setText(wsObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostHttpUpgrade(GuiEditorItemTextInput):
    """Represent GUI v transport item host HTTP upgrade."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostHttpUpgrade."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new host."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            httpUpgradeObject = ConfigXray.getProxyOutboundStream(config)[
                'httpupgradeSettings'
            ]

            self.setText(httpUpgradeObject.get('host', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathHttpUpgrade(GuiEditorItemTextInput):
    """Represent GUI v transport item path HTTP upgrade."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathHttpUpgrade."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new path."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            httpUpgradeObject = ConfigXray.getProxyOutboundStream(config)[
                'httpupgradeSettings'
            ]

            self.setText(httpUpgradeObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostSplitHttp(GuiEditorItemTextInput):
    """Represent GUI v transport item host split HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostSplitHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new host."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            splitHttpObject = ConfigXray.getProxyOutboundStream(config)[
                'splithttpSettings'
            ]

            self.setText(splitHttpObject.get('host', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathSplitHttp(GuiEditorItemTextInput):
    """Represent GUI v transport item path split HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathSplitHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new path."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            splitHttpObject = ConfigXray.getProxyOutboundStream(config)[
                'splithttpSettings'
            ]

            self.setText(splitHttpObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostXHttp(GuiEditorItemTextInput):
    """Represent GUI v transport item host x HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostXHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('xhttpSettings'), dict):
            streamSettings['xhttpSettings'] = {}

        xhttpObject = streamSettings['xhttpSettings']

        try:
            oldHost = xhttpObject.get('host', '')
        except Exception:
            # Any non-exit exceptions

            oldHost = ''

        newHost = self.text()

        def setNewHost():
            """Set new host."""
            if newHost == '':
                xhttpObject.pop('host', None)
            else:
                xhttpObject['host'] = newHost

        if isinstance(oldHost, str):
            if newHost != oldHost:
                setNewHost()

                return True
            else:
                return False
        else:
            setNewHost()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xhttpObject = ConfigXray.getProxyOutboundStream(config)['xhttpSettings']

            self.setText(xhttpObject.get('host', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathXHttp(GuiEditorItemTextInput):
    """Represent GUI v transport item path x HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathXHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('xhttpSettings'), dict):
            streamSettings['xhttpSettings'] = {}

        xhttpObject = streamSettings['xhttpSettings']

        try:
            oldPath = xhttpObject.get('path', '')
        except Exception:
            # Any non-exit exceptions

            oldPath = ''

        newPath = self.text()

        def setNewPath():
            """Set new path."""
            if newPath == '':
                xhttpObject.pop('path', None)
            else:
                xhttpObject['path'] = newPath

        if isinstance(oldPath, str):
            if newPath != oldPath:
                setNewPath()

                return True
            else:
                return False
        else:
            setNewPath()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xhttpObject = ConfigXray.getProxyOutboundStream(config)['xhttpSettings']

            self.setText(xhttpObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemModeXHttp(GuiEditorItemTextComboBox):
    """Represent GUI v transport item mode x HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemModeXHttp."""
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'auto',
                'packet-up',
                'stream-up',
            ]
        )

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('xhttpSettings'), dict):
            streamSettings['xhttpSettings'] = {}

        xhttpObject = streamSettings['xhttpSettings']

        try:
            oldMode = xhttpObject.get('mode', '')
        except Exception:
            # Any non-exit exceptions

            oldMode = ''

        newMode = self.text()

        def setNewMode():
            """Set new mode."""
            if newMode == '':
                xhttpObject.pop('mode', None)
            else:
                xhttpObject['mode'] = newMode

        if isinstance(oldMode, str):
            if newMode != oldMode:
                setNewMode()

                return True
            else:
                return False
        else:
            setNewMode()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xhttpObject = ConfigXray.getProxyOutboundStream(config)['xhttpSettings']

            self.setText(xhttpObject.get('mode', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemExtraXHttp(GuiEditorItemTextInput):
    """Represent GUI v transport item extra x HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemExtraXHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('xhttpSettings'), dict):
            streamSettings['xhttpSettings'] = {}

        xhttpObject = streamSettings['xhttpSettings']

        try:
            if xhttpObject.get('extra', ''):
                oldExtra = UJSONEncoder.encode(xhttpObject.get('extra', ''))
            else:
                oldExtra = ''
        except Exception:
            # Any non-exit exceptions

            oldExtra = ''

        newExtra = self.text()

        def setNewExtra():
            """Set new extra."""
            if newExtra == '':
                xhttpObject.pop('extra', None)
            else:
                try:
                    xhttpObject['extra'] = UJSONEncoder.decode(newExtra)
                except Exception:
                    # Any non-exit exceptions

                    xhttpObject.pop('extra', None)

        if isinstance(oldExtra, str):
            if newExtra != oldExtra:
                setNewExtra()

                return True
            else:
                return False
        else:
            setNewExtra()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xhttpObject = ConfigXray.getProxyOutboundStream(config)['xhttpSettings']

            if xhttpObject.get('extra', ''):
                self.setText(UJSONEncoder.encode(xhttpObject.get('extra', '')))
            else:
                self.setText('')
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemHostH2(GuiEditorItemTextInput):
    """Represent GUI v transport item host h2."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemHostH2."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new host."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            httpObject = ConfigXray.getProxyOutboundStream(config)['httpSettings']

            self.setText(','.join(httpObject.get('host', [])))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPathH2(GuiEditorItemTextInput):
    """Represent GUI v transport item path h2."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPathH2."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new path."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            httpObject = ConfigXray.getProxyOutboundStream(config)['httpSettings']

            self.setText(httpObject.get('path', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemTypeQuic(GuiVTransportItemTypeXXX):
    """Represent GUI v transport item type quic."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemTypeQuic."""
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
    """Represent GUI v transport item security quic."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemSecurityQuic."""
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'none',
                'aes-128-gcm',
                'chacha20-poly1305',
            ]
        )

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new security."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            quicObject = ConfigXray.getProxyOutboundStream(config)['quicSettings']

            self.setText(quicObject.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemKeyQuic(GuiEditorItemTextInput):
    """Represent GUI v transport item key quic."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemKeyQuic."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new key."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            quicObject = ConfigXray.getProxyOutboundStream(config)['quicSettings']

            self.setText(quicObject.get('key', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemModeGRPC(GuiEditorItemTextComboBox):
    """Represent GUI v transport item mode grpc."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemModeGRPC."""
        super().__init__(*args, **kwargs)

        self.addItems(
            [
                '',
                'gun',
                'multi',
            ]
        )

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new mode."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            grpcObject = ConfigXray.getProxyOutboundStream(config)['grpcSettings']

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
    """Represent GUI v transport item authority grpc."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemAuthorityGRPC."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new authority."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            grpcObject = ConfigXray.getProxyOutboundStream(config)['grpcSettings']

            self.setText(grpcObject.get('authority', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemServiceNameGRPC(GuiEditorItemTextInput):
    """Represent GUI v transport item service name grpc."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemServiceNameGRPC."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new service name."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            grpcObject = ConfigXray.getProxyOutboundStream(config)['grpcSettings']

            self.setText(grpcObject.get('serviceName', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemVersionHysteria(GuiEditorItemTextSpinBox):
    """Represent GUI v transport item version hysteria."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemVersionHysteria."""
        super().__init__(*args, **kwargs)

        # Range. 0 means invalid
        self.setRange(0, 2)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('hysteriaSettings'), dict):
            streamSettings['hysteriaSettings'] = {}

        hysteriaObject = streamSettings['hysteriaSettings']

        oldVersion = hysteriaObject.get('version', 0)
        newVersion = self.value()

        if isinstance(oldVersion, int):
            if newVersion != oldVersion:
                hysteriaObject['version'] = newVersion

                return True
            else:
                return False
        else:
            hysteriaObject['version'] = newVersion

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            hysteriaObject = ConfigXray.getProxyOutboundStream(config)[
                'hysteriaSettings'
            ]

            self.setValue(hysteriaObject.get('version', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiVTransportItemAuthHysteria(GuiEditorItemTextInput):
    """Represent GUI v transport item auth hysteria."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemAuthHysteria."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('hysteriaSettings'), dict):
            streamSettings['hysteriaSettings'] = {}

        hysteriaObject = streamSettings['hysteriaSettings']

        try:
            oldAuth = hysteriaObject.get('auth', '')
        except Exception:
            # Any non-exit exceptions

            oldAuth = ''

        newAuth = self.text()

        def setNewAuth():
            """Set new auth."""
            if newAuth == '':
                hysteriaObject.pop('auth', None)
            else:
                hysteriaObject['auth'] = newAuth

        if isinstance(oldAuth, str):
            if newAuth != oldAuth:
                setNewAuth()

                return True
            else:
                return False
        else:
            setNewAuth()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            hysteriaObject = ConfigXray.getProxyOutboundStream(config)[
                'hysteriaSettings'
            ]

            self.setText(hysteriaObject.get('auth', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportItemPasswordHysteria(GuiEditorItemTextInput):
    """Represent GUI v transport item password hysteria."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportItemPasswordHysteria."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('finalmask'), dict):
            streamSettings['finalmask'] = {}

        finalmaskObject = streamSettings['finalmask']

        if not isinstance(finalmaskObject.get('salamander'), dict):
            finalmaskObject['salamander'] = {}

        salamander = finalmaskObject['salamander']

        try:
            oldPassword = salamander.get('password', '')
        except Exception:
            # Any non-exit exceptions

            oldPassword = ''

        newPassword = self.text()

        def setNewPassword():
            """Set new password."""
            if newPassword == '':
                finalmaskObject.pop('salamander', None)
            else:
                salamander['password'] = newPassword

        if isinstance(oldPassword, str):
            if newPassword != oldPassword:
                setNewPassword()

                return True
            else:
                return False
        else:
            setNewPassword()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            salamander = ConfigXray.getProxyOutboundStream(config)['finalmask'][
                'salamander'
            ]

            self.setText(salamander.get('password', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTransportPageXXX(GuiEditorWidgetQWidget):
    """Represent GUI v transport page xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageXXX."""
        super().__init__(*args, **kwargs)

    def setNetworkText(self, text: str):
        """Set network text."""
        network = self._containers[0]

        if isinstance(network, GuiEditorItemTextComboBox):
            network.setText(text)

    def connectActivated(self, func: Callable):
        """Connect activated."""
        network = self._containers[0]

        if isinstance(network, GuiEditorItemTextComboBox):
            network.connectActivated(func)


class GuiVTransportPageTcp(GuiVTransportPageXXX):
    """Represent GUI v transport page TCP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageTcp."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemTypeTcpOrRaw(
                title='Type', networkKey='tcpSettings', translatable=False
            ),
            GuiVTransportItemHostTcpOrRaw(
                title='Host', networkKey='tcpSettings', translatable=False
            ),
            GuiVTransportItemPathTcpOrRaw(
                title='Path', networkKey='tcpSettings', translatable=False
            ),
        ]


class GuiVTransportPageRaw(GuiVTransportPageXXX):
    """Represent GUI v transport page raw."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageRaw."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemTypeTcpOrRaw(
                title='Type', networkKey='rawSettings', translatable=False
            ),
            GuiVTransportItemHostTcpOrRaw(
                title='Host', networkKey='rawSettings', translatable=False
            ),
            GuiVTransportItemPathTcpOrRaw(
                title='Path', networkKey='rawSettings', translatable=False
            ),
        ]


class GuiVTransportPageKcp(GuiVTransportPageXXX):
    """Represent GUI v transport page kcp."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageKcp."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemTypeKcp(title='Type', translatable=False),
            GuiVTransportItemSeedKcp(title='KCP seed', translatable=False),
        ]


class GuiVTransportPageWs(GuiVTransportPageXXX):
    """Represent GUI v transport page ws."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageWs."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemHostWs(title='Host', translatable=False),
            GuiVTransportItemPathWs(title='Path', translatable=False),
        ]


class GuiVTransportPageHttpUpgrade(GuiVTransportPageXXX):
    """Represent GUI v transport page HTTP upgrade."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageHttpUpgrade."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemHostHttpUpgrade(title='Host', translatable=False),
            GuiVTransportItemPathHttpUpgrade(title='Path', translatable=False),
        ]


class GuiVTransportPageSplitHttp(GuiVTransportPageXXX):
    """Represent GUI v transport page split HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageSplitHttp."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemHostSplitHttp(title='Host', translatable=False),
            GuiVTransportItemPathSplitHttp(title='Path', translatable=False),
        ]


class GuiVTransportPageXHttp(GuiVTransportPageXXX):
    """Represent GUI v transport page x HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageXHttp."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemHostXHttp(title='Host', translatable=False),
            GuiVTransportItemPathXHttp(title='Path', translatable=False),
            GuiVTransportItemModeXHttp(title='Mode', translatable=False),
            GuiVTransportItemExtraXHttp(title='Extra', translatable=False),
        ]


class GuiVTransportPageH2(GuiVTransportPageXXX):
    """Represent GUI v transport page h2."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageH2."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemHostH2(title='Host', translatable=False),
            GuiVTransportItemPathH2(title='Path', translatable=False),
        ]


class GuiVTransportPageQuic(GuiVTransportPageXXX):
    """Represent GUI v transport page quic."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageQuic."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemTypeQuic(title='Type', translatable=False),
            GuiVTransportItemSecurityQuic(title='QUIC Security', translatable=False),
            GuiVTransportItemKeyQuic(title='QUIC Key', translatable=False),
        ]


class GuiVTransportPageGRPC(GuiVTransportPageXXX):
    """Represent GUI v transport page grpc."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageGRPC."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemModeGRPC(title='gRPC mode', translatable=False),
            GuiVTransportItemAuthorityGRPC(title='gRPC authority', translatable=False),
            GuiVTransportItemServiceNameGRPC(
                title='gRPC serviceName', translatable=False
            ),
        ]


class GuiVTransportPageHysteria(GuiVTransportPageXXX):
    """Represent GUI v transport page hysteria."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageHysteria."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTransportItemNetwork(title='Network', translatable=False),
            GuiVTransportItemFinalMask(title='Finalmask', translatable=False),
            GuiVTransportItemVersionHysteria(title='Version', translatable=False),
            GuiVTransportItemAuthHysteria(title='Auth', translatable=False),
            # GuiVTransportItemPasswordHysteria(title='Password', translatable=False),
        ]


class GuiVTransportPageStackedWidget(QStackedWidget):
    """Provide the GUI v transport page stacked widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTransportPageStackedWidget."""
        super().__init__(*args, **kwargs)

        # Corresponds to stream network
        self._pages = [
            GuiVTransportPageTcp(),
            GuiVTransportPageRaw(),
            GuiVTransportPageKcp(),
            GuiVTransportPageWs(),
            GuiVTransportPageH2(),
            GuiVTransportPageQuic(),
            GuiVTransportPageGRPC(),
            GuiVTransportPageHttpUpgrade(),
            GuiVTransportPageSplitHttp(),
            GuiVTransportPageXHttp(),
            GuiVTransportPageHysteria(),
        ]

        assert len(STREAM_NETWORK) == len(self._pages)

        for page in self._pages:
            self.addWidget(page)

    def page(self, index: int) -> GuiVTransportPageXXX:
        """Return the page value."""
        return self._pages[index]

    def connectActivated(self, func: Callable):
        """Connect activated."""
        for page in self._pages:
            page.connectActivated(func)


class GuiVTransportQGroupBox(EditorBinding, AppQGroupBox):
    """Group the GUI v transport q editor controls."""

    def __init__(self, **kwargs):
        """Initialize the GuiVTransportQGroupBox."""
        super().__init__(_('Transport'), **kwargs)

        self._config = ConfigFactory()

        self._widget = GuiVTransportPageStackedWidget()
        self._widget.connectActivated(self.handleActivated)

        layout = QFormLayout()
        layout.addRow(self._widget)

        self.setLayout(layout)

    def currentIndex(self) -> int:
        """Return the current index value."""
        return self._widget.currentIndex()

    def setCurrentIndex(self, index: int):
        """Set current index."""
        self._widget.setCurrentIndex(index)

    def page(self, index: int) -> GuiVTransportPageXXX:
        """Return the page value."""
        return self._widget.page(index)

    def handleActivated(self, index: int):
        """Handle activated."""
        page = self.page(index)
        page.factoryToInput(self._config)
        page.setNetworkText(STREAM_NETWORK[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        return self.page(self.currentIndex()).inputToFactory(config)

    def factoryToInput(self, config: ConfigFactory):
        # Shallow copy
        """Load the configuration value into the editor."""
        self._config = config

        streamSettings = ConfigXray.getProxyOutboundStream(config)
        network = streamSettings.get('network', '')

        if not isinstance(network, str):
            return

        def alterNetwork(sourceNetwork, targetNetwork):
            """Handle alter network for the GUI v transport q group box."""
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
