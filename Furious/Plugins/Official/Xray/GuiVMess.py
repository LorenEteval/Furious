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

"""Provide widgets for GUI v mess."""

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

from PySide6.QtWidgets import *

import uuid
import functools

__all__ = ['GuiVMess']

getProxyOutboundServer = functools.partial(
    ConfigXray.getProxyOutboundServer,
    protocol=Protocol.VMess,
    default=configXrayEmptyProxyOutboundObject(Protocol.VMess),
)

getProxyOutboundUser = functools.partial(
    ConfigXray.getProxyOutboundUser,
    protocol=Protocol.VMess,
    default=configXrayEmptyProxyOutboundObject(Protocol.VMess),
)


class GuiVMessItemBasicAddress(GuiEditorItemTextInput):
    """Represent GUI v mess item basic address."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMessItemBasicAddress."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setText(proxyOutboundServer.get('address', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVMessItemBasicPort(GuiEditorItemTextSpinBox):
    """Represent GUI v mess item basic port."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMessItemBasicPort."""
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


class GuiVMessItemBasicId(GuiEditorItemTextInput):
    """Represent GUI v mess item basic id."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMessItemBasicId."""
        super().__init__(*args, **kwargs)

        self.generateButton = AppQPushButton(_('Generate'))
        self.generateButton.clicked.connect(self.generateUUID)

        self._widget = QWidget()

        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input)
        layout.addWidget(self.generateButton)

    def generateUUID(self):
        """Handle generate uuid for the GUI v mess item basic id."""
        self.setText(str(uuid.uuid4()))

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return self._title, self._widget

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('id', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVMessItemBasicAlterId(GuiEditorItemTextSpinBox):
    """Represent GUI v mess item basic alter id."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMessItemBasicAlterId."""
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 65535)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setValue(proxyOutboundUser.get('alterId', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiVMessItemBasicSecurity(GuiEditorItemTextComboBox):
    """Represent GUI v mess item basic security."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMessItemBasicSecurity."""
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

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVMessGroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI v mess group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiVMessGroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def setupPageLayout(self):
        """Set up page layout."""
        layout = QGridLayout()
        layout.setColumnStretch(4, 1)

        def keepSpinBoxCompact(widget: QWidget):
            """Handle keep spin box compact for the GUI v mess group box basic."""
            if isinstance(widget, QSpinBox):
                widget.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    widget.sizePolicy().verticalPolicy(),
                )

        def keepComboBoxCompact(widget: QWidget):
            """Handle keep combo box compact for the GUI v mess group box basic."""
            if isinstance(widget, QComboBox):
                widget.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    widget.sizePolicy().verticalPolicy(),
                )

        def addPair(index: int, row: int, column: int):
            """Add pair."""
            label, inputWidget = self._containers[index].widgets()

            keepSpinBoxCompact(inputWidget)

            layout.addWidget(label, row, column)
            layout.addWidget(inputWidget, row, column + 1)

        def addFullRow(index: int, row: int):
            """Add full row."""
            label, inputWidget = self._containers[index].widgets()

            keepSpinBoxCompact(inputWidget)

            layout.addWidget(label, row, 0)
            layout.addWidget(inputWidget, row, 1, 1, 4)

        addFullRow(0, 0)
        addFullRow(1, 1)
        addPair(2, 2, 0)
        addPair(4, 2, 2)
        addFullRow(3, 3)
        keepComboBoxCompact(self._containers[5].widgets()[1])
        addFullRow(5, 4)

        layout.setRowStretch(5, 1)

        return layout

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiVMessItemBasicAddress(title=_('Address')),
            GuiVMessItemBasicPort(title=_('Port')),
            GuiVMessItemBasicId(title='Id', translatable=False),
            GuiVMessItemBasicAlterId(title='AlterId', translatable=False),
            GuiVMessItemBasicSecurity(title='Security', translatable=False),
        ]


class GuiVMessGroupBoxProxy(GuiEditorWidgetQGroupBox):
    """Represent GUI v mess group box proxy."""

    def __init__(self, **kwargs):
        """Initialize the GuiVMessGroupBoxProxy."""
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiVMess(GuiEditorWidgetQDialog):
    """Represent GUI v mess."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVMess."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.VMess.value)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        """Return the configuration group boxes in display order."""
        return [
            GuiVMessGroupBoxBasic(),
            GuiVMessGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
