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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Widget.GuiVTransport import *
from Furious.Widget.GuiVTLS import *

from PySide6.QtWidgets import *

import uuid
import functools

__all__ = ['GuiVLESS']

getProxyOutboundServer = functools.partial(
    ConfigXray.getProxyOutboundServer,
    protocol=Protocol.VLESS,
    default=configXrayEmptyProxyOutboundObject(Protocol.VLESS),
)

getProxyOutboundUser = functools.partial(
    ConfigXray.getProxyOutboundUser,
    protocol=Protocol.VLESS,
    default=configXrayEmptyProxyOutboundObject(Protocol.VLESS),
)


class GuiVLESSItemBasicAddress(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def inputToFactory(self, config: ConfigFactory) -> bool:
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
        try:
            proxyOutboundServer = getProxyOutboundServer(config)

            self.setValue(proxyOutboundServer.get('port', 0))
        except Exception:
            # Any non-exit exceptions

            self.setValue(0)


class GuiVLESSItemBasicId(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.generateButton = AppQPushButton(_('Generate'))
        self.generateButton.clicked.connect(self.generateUUID)

        self._widget = QWidget()

        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._input)
        layout.addWidget(self.generateButton)

    def generateUUID(self):
        self.setText(str(uuid.uuid4()))

    def widgets(self):
        return self._title, self._widget

    def inputToFactory(self, config: ConfigFactory) -> bool:
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
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('id', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVLESSItemBasicEncryption(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def factoryToInput(self, config: ConfigFactory):
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

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def factoryToInput(self, config: ConfigFactory):
        try:
            proxyOutboundUser = getProxyOutboundUser(config)

            self.setText(proxyOutboundUser.get('flow', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVLESSGroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def setupPageLayout(self):
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        def keepSpinBoxCompact(widget: QWidget):
            if isinstance(widget, QSpinBox):
                widget.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    widget.sizePolicy().verticalPolicy(),
                )

        def addPair(index: int, row: int, column: int):
            label, inputWidget = self._containers[index].widgets()

            keepSpinBoxCompact(inputWidget)

            layout.addWidget(label, row, column)
            layout.addWidget(inputWidget, row, column + 1)

        def addFullRow(index: int, row: int):
            label, inputWidget = self._containers[index].widgets()

            keepSpinBoxCompact(inputWidget)

            layout.addWidget(label, row, 0)
            layout.addWidget(inputWidget, row, 1, 1, 3)

        addFullRow(0, 0)
        addFullRow(1, 1)
        addFullRow(2, 2)
        addFullRow(3, 3)
        addPair(4, 4, 0)
        addPair(5, 4, 2)

        layout.setRowStretch(5, 1)

        return layout

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiVLESSItemBasicAddress(title=_('Address')),
            GuiVLESSItemBasicPort(title=_('Port')),
            GuiVLESSItemBasicId(title='Id', translatable=False),
            GuiVLESSItemBasicEncryption(title=_('Encryption')),
            GuiVLESSItemBasicFlow(title=_('Flow')),
        ]


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

        self.setTabText(Protocol.VLESS.value)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        return [
            GuiVLESSGroupBoxBasic(),
            GuiVLESSGroupBoxProxy(),
            GuiVTransportQGroupBox(),
            GuiVTLSQGroupBox(),
        ]
