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

"""Provide widgets for GUI shadowsocks."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Backends.Configuration import *
from Furious.Backends.Xray.TlsEditor import *
from Furious.Backends.Xray.TransportEditor import *

import functools

__all__ = ['ShadowsocksEditor']

getProxyOutboundServer = functools.partial(
    ConfigXray.getProxyOutboundServer,
    protocol=Protocol.Shadowsocks,
    default=configXrayEmptyProxyOutboundObject(Protocol.Shadowsocks),
)


class GuiSSItemTextInput(GuiEditorItemTextInput):
    """Represent GUI ss item text input."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSSItemTextInput."""
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get(self.key, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiSSItemBasicPort(GuiEditorItemTextSpinBox):
    """Represent GUI ss item basic port."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSSItemBasicPort."""
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 65535)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setValue(proxyOutboundServer.get('port', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiSSItemBasicMethod(GuiEditorItemTextComboBox):
    """Represent GUI ss item basic method."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSSItemBasicMethod."""
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

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get('method', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiSSGroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI ss group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiSSGroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiSSItemTextInput(title=_('Address'), key='address'),
            GuiSSItemBasicPort(title=_('Port')),
            GuiSSItemBasicMethod(title=_('Encryption')),
            GuiSSItemTextInput(title=_('Password'), key='password'),
        ]


class GuiSSGroupBoxProxy(GuiEditorWidgetQGroupBox):
    """Represent GUI ss group box proxy."""

    def __init__(self, **kwargs):
        """Initialize the GuiSSGroupBoxProxy."""
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class ShadowsocksEditor(GuiEditorWidgetQDialog):
    """Represent GUI shadowsocks."""

    def __init__(self, *args, **kwargs):
        """Initialize the Shadowsocks configuration editor."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Shadowsocks.value)

    def createGroupBoxSequence(self):
        """Create the configuration group boxes in display order."""
        return [
            GuiSSGroupBoxBasic(),
            GuiSSGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
