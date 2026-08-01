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

"""Provide widgets for GUI SOCKS."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Plugins.Official.Configuration import (
    ConfigXray,
    configXrayEmptyProxyOutboundObject,
)
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Plugins.Official.Xray.GuiVTransport import *
from Furious.Plugins.Official.Xray.GuiVTLS import *

import functools

__all__ = ['GuiSocks']

getProxyOutboundServer = functools.partial(
    ConfigXray.getProxyOutboundServer,
    protocol=Protocol.Socks,
    default=configXrayEmptyProxyOutboundObject(Protocol.Socks),
)


class GuiSocksItemTextInput(GuiEditorItemTextInput):
    """Represent GUI SOCKS item text input."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSocksItemTextInput."""
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
                    proxyOutboundServer.pop(self.key, None)
                else:
                    proxyOutboundServer[self.key] = newValue

                return True

            return False

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


class GuiSocksItemBasicPort(GuiEditorItemTextSpinBox):
    """Represent GUI SOCKS item basic port."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSocksItemBasicPort."""
        super().__init__(*args, **kwargs)

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

            return False

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


class GuiSocksGroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI SOCKS group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiSocksGroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiSocksItemTextInput(title=_('Address'), key='address'),
            GuiSocksItemBasicPort(title=_('Port')),
            GuiSocksItemTextInput(title=_('Username'), key='user'),
            GuiSocksItemTextInput(title=_('Password'), key='pass'),
        ]


class GuiSocksGroupBoxProxy(GuiEditorWidgetQGroupBox):
    """Represent GUI SOCKS group box proxy."""

    def __init__(self, **kwargs):
        """Initialize the GuiSocksGroupBoxProxy."""
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiSocks(GuiEditorWidgetQDialog):
    """Represent GUI SOCKS."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiSocks."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Socks.value)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        """Return the configuration group boxes in display order."""
        return [
            GuiSocksGroupBoxBasic(),
            GuiSocksGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
