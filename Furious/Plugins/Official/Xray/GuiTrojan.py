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

"""Provide widgets for GUI trojan."""

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

__all__ = ['GuiTrojan']

getProxyOutboundServer = functools.partial(
    ConfigXray.getProxyOutboundServer,
    protocol=Protocol.Trojan,
    default=configXrayEmptyProxyOutboundObject(Protocol.Trojan),
)


class GuiTrojanItemTextInput(GuiEditorItemTextInput):
    """Represent GUI trojan item text input."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTrojanItemTextInput."""
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


class GuiTrojanItemBasicPort(GuiEditorItemTextSpinBox):
    """Represent GUI trojan item basic port."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTrojanItemBasicPort."""
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


class GuiTrojanGroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI trojan group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiTrojanGroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiTrojanItemTextInput(title=_('Address'), key='address'),
            GuiTrojanItemBasicPort(title=_('Port')),
            GuiTrojanItemTextInput(title=_('Password'), key='password'),
        ]


class GuiTrojanGroupBoxProxy(GuiEditorWidgetQGroupBox):
    """Represent GUI trojan group box proxy."""

    def __init__(self, **kwargs):
        """Initialize the GuiTrojanGroupBoxProxy."""
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiTrojan(GuiEditorWidgetQDialog):
    """Represent GUI trojan."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTrojan."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Trojan.value)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        """Return the configuration group boxes in display order."""
        return [
            GuiTrojanGroupBoxBasic(),
            GuiTrojanGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
