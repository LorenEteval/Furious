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

from PySide6.QtWidgets import *

from typing import Callable

__all__ = ['GuiVTLSQGroupBox']

needTrans = functools.partial(needTransFn, source=__name__)

STREAM_SECURITY = [
    '',
    'none',
    'tls',
    'reality',
]


class GuiVTLSItemSecurity(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(STREAM_SECURITY)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        try:
            oldSecurity = streamSettings['security']
        except Exception:
            # Any non-exit exceptions

            oldSecurity = ''

        newSecurity = self.text()

        def setNewSecurity():
            if newSecurity == '':
                streamSettings.pop('security', None)
            else:
                streamSettings['security'] = newSecurity

            for security in ['tls', 'reality']:
                if security == newSecurity:
                    continue

                securityKey = f'{security}Settings'

                # Remove irrelevant settings
                streamSettings.pop(securityKey, None)

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
            streamSettings = getXrayProxyOutboundStream(config)

            self.setText(streamSettings.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemXXXServerName(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        # Mandatory
        securityKey = kwargs.pop('securityKey')

        super().__init__(*args, **kwargs)

        self.securityKey = securityKey

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get(self.securityKey), dict):
            streamSettings[self.securityKey] = {}

        xxxObject = streamSettings[self.securityKey]

        try:
            oldServerName = xxxObject.get('serverName', '')
        except Exception:
            # Any non-exit exceptions

            oldServerName = ''

        newServerName = self.text()

        def setNewServerName():
            if newServerName == '':
                xxxObject.pop('serverName', None)
            else:
                xxxObject['serverName'] = newServerName

        if isinstance(oldServerName, str):
            if newServerName != oldServerName:
                setNewServerName()

                return True
            else:
                return False
        else:
            setNewServerName()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            xxxObject = getXrayProxyOutboundStream(config)[self.securityKey]

            self.setText(xxxObject.get('serverName', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSServerName(GuiVTLSItemXXXServerName):
    def __init__(self, *args, **kwargs):
        securityKey = kwargs.pop('securityKey', 'tlsSettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemRealityServerName(GuiVTLSItemXXXServerName):
    def __init__(self, *args, **kwargs):
        securityKey = kwargs.pop('securityKey', 'realitySettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemXXXFingerprint(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        # Mandatory
        securityKey = kwargs.pop('securityKey')

        super().__init__(*args, **kwargs)

        self.securityKey = securityKey

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get(self.securityKey), dict):
            streamSettings[self.securityKey] = {}

        xxxObject = streamSettings[self.securityKey]

        try:
            oldFingerprint = xxxObject.get('fingerprint', '')
        except Exception:
            # Any non-exit exceptions

            oldFingerprint = ''

        newFingerprint = self.text()

        def setNewFingerprint():
            if newFingerprint == '':
                xxxObject.pop('fingerprint', None)
            else:
                xxxObject['fingerprint'] = newFingerprint

        if isinstance(oldFingerprint, str):
            if newFingerprint != oldFingerprint:
                setNewFingerprint()

                return True
            else:
                return False
        else:
            setNewFingerprint()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            xxxObject = getXrayProxyOutboundStream(config)[self.securityKey]

            self.setText(xxxObject.get('fingerprint', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSFingerprint(GuiVTLSItemXXXFingerprint):
    def __init__(self, *args, **kwargs):
        securityKey = kwargs.pop('securityKey', 'tlsSettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemRealityFingerprint(GuiVTLSItemXXXFingerprint):
    def __init__(self, *args, **kwargs):
        securityKey = kwargs.pop('securityKey', 'realitySettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemTLSAlpn(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('tlsSettings'), dict):
            streamSettings['tlsSettings'] = {}

        tlsObject = streamSettings['tlsSettings']

        try:
            oldAlpn = ','.join(tlsObject.get('alpn', []))
        except Exception:
            # Any non-exit exceptions

            oldAlpn = ''

        newAlpn = self.text()

        def setNewAlpn():
            if newAlpn == '':
                tlsObject.pop('alpn', None)
            else:
                tlsObject['alpn'] = newAlpn.split(',')

        if isinstance(oldAlpn, str):
            if newAlpn != oldAlpn:
                setNewAlpn()

                return True
            else:
                return False
        else:
            setNewAlpn()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            tlsObject = getXrayProxyOutboundStream(config)['tlsSettings']

            self.setText(','.join(tlsObject.get('alpn', [])))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSAllowInsecure(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('tlsSettings'), dict):
            streamSettings['tlsSettings'] = {}

        tlsObject = streamSettings['tlsSettings']

        try:
            oldInsecure = tlsObject.get('allowInsecure', False)
        except Exception:
            # Any non-exit exceptions

            oldInsecure = False

        newInsecure = self.isChecked()

        if newInsecure:
            if oldInsecure is not True:
                tlsObject['allowInsecure'] = True

                return True
            else:
                return False
        else:
            if oldInsecure is not False:
                tlsObject['allowInsecure'] = False

                return True
            else:
                return False

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            tlsObject = getXrayProxyOutboundStream(config)['tlsSettings']

            self.setChecked(tlsObject.get('allowInsecure', False))
        except Exception:
            # Any non-exit exceptions

            self.setChecked(False)


class GuiVTLSItemRealityXXX(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        # Mandatory
        realityKey = kwargs.pop('realityKey')

        super().__init__(*args, **kwargs)

        self.realityKey = realityKey

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        streamSettings = getXrayProxyOutboundStream(config)

        if not isinstance(streamSettings.get('realitySettings'), dict):
            streamSettings['realitySettings'] = {}

        realityObject = streamSettings['realitySettings']

        try:
            oldPublicKey = realityObject.get(self.realityKey, '')
        except Exception:
            # Any non-exit exceptions

            oldPublicKey = ''

        newPublicKey = self.text()

        def setNewPublicKey():
            if newPublicKey == '':
                realityObject.pop(self.realityKey, None)
            else:
                realityObject[self.realityKey] = newPublicKey

        if isinstance(oldPublicKey, str):
            if newPublicKey != oldPublicKey:
                setNewPublicKey()

                return True
            else:
                return False
        else:
            setNewPublicKey()

            return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            realityObject = getXrayProxyOutboundStream(config)['realitySettings']

            self.setText(realityObject.get(self.realityKey, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemRealityPublicKey(GuiVTLSItemRealityXXX):
    def __init__(self, *args, **kwargs):
        realityKey = kwargs.pop('realityKey', 'publicKey')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSItemRealityShortId(GuiVTLSItemRealityXXX):
    def __init__(self, *args, **kwargs):
        realityKey = kwargs.pop('realityKey', 'shortId')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSItemRealitySpiderX(GuiVTLSItemRealityXXX):
    def __init__(self, *args, **kwargs):
        realityKey = kwargs.pop('realityKey', 'spiderX')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSPageXXX(GuiEditorWidgetQWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setSecurityText(self, text: str):
        security = self._containers[0]

        if isinstance(security, GuiEditorItemTextComboBox):
            security.setText(text)

    def connectActivated(self, func: Callable):
        security = self._containers[0]

        if isinstance(security, GuiEditorItemTextComboBox):
            security.connectActivated(func)


class GuiVTLSPageEmpty(GuiVTLSPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
        ]


class GuiVTLSPageNone(GuiVTLSPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
        ]


class GuiVTLSPageTLS(GuiVTLSPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
            GuiVTLSItemTLSServerName(title='SNI', translatable=False),
            GuiVTLSItemTLSFingerprint(title='Fingerprint', translatable=False),
            GuiVTLSItemTLSAlpn(title='Alpn', translatable=False),
            GuiVTLSItemTLSAllowInsecure(title='AllowInsecure', translatable=False),
        ]


class GuiVTLSPageReality(GuiVTLSPageXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
            GuiVTLSItemRealityServerName(title='SNI', translatable=False),
            GuiVTLSItemRealityFingerprint(title='Fingerprint', translatable=False),
            GuiVTLSItemRealityPublicKey(title='PublicKey', translatable=False),
            GuiVTLSItemRealityShortId(title='ShortId', translatable=False),
            GuiVTLSItemRealitySpiderX(title='SpiderX', translatable=False),
        ]


class GuiVTLSPageStackedWidget(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Corresponds to stream security
        self._pages = [
            GuiVTLSPageEmpty(),
            GuiVTLSPageNone(),
            GuiVTLSPageTLS(),
            GuiVTLSPageReality(),
        ]

        for page in self._pages:
            self.addWidget(page)

    def page(self, index: int) -> GuiVTLSPageXXX:
        return self._pages[index]

    def connectActivated(self, func: Callable):
        for page in self._pages:
            page.connectActivated(func)


class GuiVTLSQGroupBox(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        translatable = kwargs.pop('translatable', False)

        super().__init__('TLS', **kwargs, translatable=translatable)

        self._config = ConfigurationFactory()

        self._widget = GuiVTLSPageStackedWidget()
        self._widget.connectActivated(self.handleActivated)

        layout = QFormLayout()
        layout.addRow(self._widget)

        self.setLayout(layout)

    def currentIndex(self) -> int:
        return self._widget.currentIndex()

    def setCurrentIndex(self, index: int):
        self._widget.setCurrentIndex(index)

    def page(self, index: int) -> GuiVTLSPageXXX:
        return self._widget.page(index)

    def handleActivated(self, index: int):
        page = self.page(index)
        page.factoryToInput(self._config)
        page.setSecurityText(STREAM_SECURITY[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        return self.page(self.currentIndex()).inputToFactory(config)

    def factoryToInput(self, config: ConfigurationFactory):
        # Shallow copy
        self._config = config

        streamSettings = getXrayProxyOutboundStream(config)
        security = streamSettings.get('security', '')

        if not isinstance(security, str):
            return

        try:
            index = STREAM_SECURITY.index(security)
        except Exception:
            # Any non-exit exceptions

            pass
        else:
            self.page(index).factoryToInput(config)
            self.setCurrentIndex(index)
