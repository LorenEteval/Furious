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

"""Provide widgets for GUI vtls."""

from __future__ import annotations

from Furious.Interface import *
from Furious.Domain import *
from Furious.Qt import *
from Furious.Backends.Configuration import *

from PySide6 import QtCore
from PySide6.QtWidgets import *

from typing import Callable

__all__ = ['GuiVTLSQGroupBox']

STREAM_SECURITY = [
    '',
    'none',
    'tls',
    'reality',
]


class GuiVTLSItemSecurity(GuiEditorItemTextComboBox):
    """Represent GUI vtls item security."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemSecurity."""
        super().__init__(*args, **kwargs)

        self.addItems(STREAM_SECURITY)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        try:
            oldSecurity = streamSettings['security']
        except Exception:
            # Any non-exit exceptions

            oldSecurity = ''

        newSecurity = self.text()

        def setNewSecurity():
            """Set new security."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            streamSettings = ConfigXray.getProxyOutboundStream(config)

            self.setText(streamSettings.get('security', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemXXXServerName(GuiEditorItemTextInput):
    """Represent GUI vtls item xxx server name."""

    def __init__(self, *args, **kwargs):
        # Mandatory
        """Initialize the GuiVTLSItemXXXServerName."""
        securityKey = kwargs.pop('securityKey')

        super().__init__(*args, **kwargs)

        self.securityKey = securityKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new server name."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xxxObject = ConfigXray.getProxyOutboundStream(config)[self.securityKey]

            self.setText(xxxObject.get('serverName', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSServerName(GuiVTLSItemXXXServerName):
    """Represent GUI vtls item TLS server name."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemTLSServerName."""
        securityKey = kwargs.pop('securityKey', 'tlsSettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemRealityServerName(GuiVTLSItemXXXServerName):
    """Represent GUI vtls item reality server name."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealityServerName."""
        securityKey = kwargs.pop('securityKey', 'realitySettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemXXXFingerprint(GuiEditorItemTextInput):
    """Represent GUI vtls item xxx fingerprint."""

    def __init__(self, *args, **kwargs):
        # Mandatory
        """Initialize the GuiVTLSItemXXXFingerprint."""
        securityKey = kwargs.pop('securityKey')

        super().__init__(*args, **kwargs)

        self.securityKey = securityKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new fingerprint."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            xxxObject = ConfigXray.getProxyOutboundStream(config)[self.securityKey]

            self.setText(xxxObject.get('fingerprint', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSFingerprint(GuiVTLSItemXXXFingerprint):
    """Represent GUI vtls item TLS fingerprint."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemTLSFingerprint."""
        securityKey = kwargs.pop('securityKey', 'tlsSettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemRealityFingerprint(GuiVTLSItemXXXFingerprint):
    """Represent GUI vtls item reality fingerprint."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealityFingerprint."""
        securityKey = kwargs.pop('securityKey', 'realitySettings')

        super().__init__(*args, **kwargs, securityKey=securityKey)


class GuiVTLSItemTLSAlpn(GuiEditorItemTextInput):
    """Represent GUI vtls item TLS alpn."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemTLSAlpn."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new alpn."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            tlsObject = ConfigXray.getProxyOutboundStream(config)['tlsSettings']

            self.setText(','.join(tlsObject.get('alpn', [])))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSXXXTextInput(GuiEditorItemTextInput):
    """Represent GUI vtls item tlsxxx text input."""

    def __init__(self, *args, **kwargs):
        # Mandatory
        """Initialize the GuiVTLSItemTLSXXXTextInput."""
        key = kwargs.pop('key')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

        if not isinstance(streamSettings.get('tlsSettings'), dict):
            streamSettings['tlsSettings'] = {}

        tlsObject = streamSettings['tlsSettings']

        oldValue = tlsObject.get(self.key, '')
        newValue = self.text()

        def setNewTLSXXXValue():
            """Set new tlsxxx value."""
            if newValue == '':
                tlsObject.pop(self.key, None)
            else:
                tlsObject[self.key] = newValue

        if isinstance(oldValue, str):
            if newValue != oldValue:
                setNewTLSXXXValue()

                return True
            else:
                return False
        else:
            setNewTLSXXXValue()

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            tlsObject = ConfigXray.getProxyOutboundStream(config)['tlsSettings']

            self.setText(tlsObject.get(self.key, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemTLSAllowInsecure(GuiEditorItemTextCheckBox):
    """Represent GUI vtls item TLS allow insecure."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemTLSAllowInsecure."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            tlsObject = ConfigXray.getProxyOutboundStream(config)['tlsSettings']

            self.setChecked(tlsObject.get('allowInsecure', False))
        except Exception:
            # Any non-exit exceptions

            self.setChecked(False)


class GuiVTLSItemRealityXXX(GuiEditorItemTextInput):
    """Represent GUI vtls item reality xxx."""

    def __init__(self, *args, **kwargs):
        # Mandatory
        """Initialize the GuiVTLSItemRealityXXX."""
        realityKey = kwargs.pop('realityKey')

        super().__init__(*args, **kwargs)

        self.realityKey = realityKey

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        streamSettings = ConfigXray.getProxyOutboundStream(config)

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
            """Set new public key."""
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

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            realityObject = ConfigXray.getProxyOutboundStream(config)['realitySettings']

            self.setText(realityObject.get(self.realityKey, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiVTLSItemRealityPublicKey(GuiVTLSItemRealityXXX):
    """Represent GUI vtls item reality public key."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealityPublicKey."""
        realityKey = kwargs.pop('realityKey', 'publicKey')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSItemRealityShortId(GuiVTLSItemRealityXXX):
    """Represent GUI vtls item reality short id."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealityShortId."""
        realityKey = kwargs.pop('realityKey', 'shortId')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSItemRealityMldsa65Verify(GuiVTLSItemRealityXXX):
    """Represent GUI vtls item reality mldsa65 verify."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealityMldsa65Verify."""
        realityKey = kwargs.pop('realityKey', 'mldsa65Verify')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSItemRealitySpiderX(GuiVTLSItemRealityXXX):
    """Represent GUI vtls item reality spider x."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSItemRealitySpiderX."""
        realityKey = kwargs.pop('realityKey', 'spiderX')

        super().__init__(*args, **kwargs, realityKey=realityKey)


class GuiVTLSPageXXX(GuiEditorWidgetQWidget):
    """Represent GUI vtls page xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageXXX."""
        super().__init__(*args, **kwargs)

    def setSecurityText(self, text: str):
        """Set security text."""
        security = self._containers[0]

        if isinstance(security, GuiEditorItemTextComboBox):
            security.setText(text)

    def connectActivated(self, func: Callable):
        """Connect activated."""
        security = self._containers[0]

        if isinstance(security, GuiEditorItemTextComboBox):
            security.connectActivated(func)


class GuiVTLSPageEmpty(GuiVTLSPageXXX):
    """Represent GUI vtls page empty."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageEmpty."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
        ]


class GuiVTLSPageNone(GuiVTLSPageXXX):
    """Represent GUI vtls page none."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageNone."""
        super().__init__(*args, **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
        ]


class GuiVTLSPageTLS(GuiVTLSPageXXX):
    """Represent GUI vtls page TLS."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageTLS."""
        super().__init__(*args, **kwargs)

    def setupLayout(self):
        """Set up layout."""
        layout = QFormLayout()
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        basicLayout = QGridLayout()
        basicLayout.setColumnStretch(1, 1)
        basicLayout.setColumnStretch(3, 1)

        def addPair(index: int, row: int, column: int):
            """Add pair."""
            label, inputWidget = self._containers[index].widgets()

            basicLayout.addWidget(label, row, column)
            basicLayout.addWidget(inputWidget, row, column + 1)

        def addBasicFullRow(index: int, row: int):
            """Add basic full row."""
            label, inputWidget = self._containers[index].widgets()

            basicLayout.addWidget(label, row, 0)
            basicLayout.addWidget(inputWidget, row, 1, 1, 3)

        def addFullRow(index: int):
            """Add full row."""
            widgets = self._containers[index].widgets()

            if len(widgets) == 1:
                layout.addRow(widgets[0])
            else:
                label, inputWidget = widgets

                layout.addRow(label, inputWidget)

        addPair(0, 0, 0)
        addPair(2, 0, 2)
        addPair(1, 1, 0)
        addPair(3, 1, 2)
        addBasicFullRow(4, 2)

        layout.addRow(basicLayout)

        addFullRow(5)
        addFullRow(6)
        addFullRow(7)

        self.setLayout(layout)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
            GuiVTLSItemTLSServerName(title='SNI', translatable=False),
            GuiVTLSItemTLSFingerprint(title='Fingerprint', translatable=False),
            GuiVTLSItemTLSAlpn(title='Alpn', translatable=False),
            GuiVTLSItemTLSXXXTextInput(
                title='EchConfigList',
                key='echConfigList',
                translatable=False,
            ),
            GuiVTLSItemTLSXXXTextInput(
                title='VerifyPeerCertByName',
                key='verifyPeerCertByName',
                translatable=False,
            ),
            GuiVTLSItemTLSXXXTextInput(
                title='PinnedPeerCertSha256',
                key='pinnedPeerCertSha256',
                translatable=False,
            ),
            GuiVTLSItemTLSAllowInsecure(title='AllowInsecure', translatable=False),
        ]


class GuiVTLSPageReality(GuiVTLSPageXXX):
    """Represent GUI vtls page reality."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageReality."""
        super().__init__(*args, **kwargs)

    def setupLayout(self):
        """Set up layout."""
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        layout.setHorizontalSpacing(12)

        def addPair(index: int, row: int, column: int):
            """Add pair."""
            label, inputWidget = self._containers[index].widgets()

            layout.addWidget(label, row, column)
            layout.addWidget(inputWidget, row, column + 1)

        def addFullRow(index: int, row: int):
            """Add full row."""
            label, inputWidget = self._containers[index].widgets()

            layout.addWidget(label, row, 0)
            layout.addWidget(inputWidget, row, 1, 1, 3)

        addPair(0, 0, 0)
        addPair(2, 0, 2)
        addPair(1, 1, 0)
        addPair(4, 1, 2)
        addFullRow(3, 2)
        addFullRow(5, 3)
        addFullRow(6, 4)

        self.setLayout(layout)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiVTLSItemSecurity(title='TLS', translatable=False),
            GuiVTLSItemRealityServerName(title='SNI', translatable=False),
            GuiVTLSItemRealityFingerprint(title='Fingerprint', translatable=False),
            GuiVTLSItemRealityPublicKey(title='PublicKey', translatable=False),
            GuiVTLSItemRealityShortId(title='ShortId', translatable=False),
            GuiVTLSItemRealityMldsa65Verify(title='Mldsa65Verify', translatable=False),
            GuiVTLSItemRealitySpiderX(title='SpiderX', translatable=False),
        ]


class GuiVTLSPageStackedWidget(QStackedWidget):
    """Provide the GUI vtls page stacked widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiVTLSPageStackedWidget."""
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
        """Return the page value."""
        return self._pages[index]

    def connectActivated(self, func: Callable):
        """Connect activated."""
        for page in self._pages:
            page.connectActivated(func)


class GuiVTLSQGroupBox(EditorBinding, AppQGroupBox):
    """Group the GUI vtlsq editor controls."""

    def __init__(self, **kwargs):
        """Initialize the GuiVTLSQGroupBox."""
        translatable = kwargs.pop('translatable', False)

        super().__init__('TLS', **kwargs, translatable=translatable)

        self._config = ConfigFactory()

        self._widget = GuiVTLSPageStackedWidget()
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

    def page(self, index: int) -> GuiVTLSPageXXX:
        """Return the page value."""
        return self._widget.page(index)

    def handleActivated(self, index: int):
        """Handle activated."""
        page = self.page(index)
        page.factoryToInput(self._config)
        page.setSecurityText(STREAM_SECURITY[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        return self.page(self.currentIndex()).inputToFactory(config)

    def factoryToInput(self, config: ConfigFactory):
        # Shallow copy
        """Load the configuration value into the editor."""
        self._config = config

        streamSettings = ConfigXray.getProxyOutboundStream(config)
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
