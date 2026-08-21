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

"""Provide widgets for GUI hysteria2."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import CoreConfiguration, Protocol
from Furious.Backends.Configuration import ConfigHysteria2
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from collections.abc import Mapping, MutableMapping
from typing import Any, Sequence

import logging

__all__ = ['Hysteria2Editor']

logger = logging.getLogger(__name__)

HY2_OBFS_TYPES = ['', 'salamander', 'gecko']


def _nestedValue(config, path: Sequence[str], default=None):
    """Return a nested configuration value without modifying the document."""
    value = config

    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return default

        value = value[key]

    return value


def _setNestedValue(config, path: Sequence[str], value: Any) -> bool:
    """Set one nested leaf while preserving every unrelated document field."""
    current = config

    for key in path[:-1]:
        child = current.get(key)

        if not isinstance(child, MutableMapping):
            child = {}
            current[key] = child

        current = child

    key = path[-1]
    oldValue = current.get(key, object())

    if oldValue == value:
        return False

    current[key] = value

    return True


def _removeNestedValue(config, path: Sequence[str]) -> bool:
    """Remove one nested leaf and prune only dictionaries left completely empty."""
    current = config
    parents = []

    for key in path[:-1]:
        if not isinstance(current, MutableMapping):
            return False

        child = current.get(key)

        if not isinstance(child, MutableMapping):
            return False

        parents.append((current, key, child))
        current = child

    if not isinstance(current, MutableMapping) or path[-1] not in current:
        return False

    current.pop(path[-1])

    for parent, key, child in reversed(parents):
        if child:
            break

        parent.pop(key, None)

    return True


class GuiHy2NestedTextInput(GuiEditorItemTextInput):
    """Edit one optional string leaf in the client document."""

    def __init__(self, *args, **kwargs):
        """Initialize a nested text input."""
        self.path = tuple(kwargs.pop('path'))

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Write a non-empty value or remove the optional leaf."""
        text = self.text().strip()

        if not text:
            return _removeNestedValue(config, self.path)
        else:
            return _setNestedValue(config, self.path, text)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the current leaf without materializing missing groups."""
        value = _nestedValue(config, self.path, '')

        self.setText(str(value) if value is not None else '')


class GuiHy2NestedSwitch(GuiEditorItemTextSwitch):
    """Edit an optional boolean leaf using a compact Fluent switch."""

    def __init__(self, *args, **kwargs):
        """Initialize a nested boolean switch."""
        self.path = tuple(kwargs.pop('path'))

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Store the current boolean value when it differs from the document."""
        oldChecked = _nestedValue(config, self.path, False)
        newChecked = self.isChecked()

        if bool(oldChecked) == newChecked:
            return False

        return _setNestedValue(config, self.path, newChecked)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the effective boolean state."""
        value = _nestedValue(config, self.path, False)

        self.setChecked(bool(value))


class GuiHy2ItemIPMode(GuiEditorItemTextComboBox):
    """Edit the Hysteria 2 client IP mode."""

    def __init__(self, *args, **kwargs):
        """Initialize the IP mode combo box with upstream values."""
        self.path = ('realm', 'ipMode')

        super().__init__(*args, **kwargs)

        self.addItems(['dual', 'v4', 'v6'])

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Store the selected upstream IP mode."""
        oldValue = _nestedValue(config, self.path, 'dual')
        newValue = self.text()

        if oldValue == newValue:
            return False

        return _setNestedValue(config, self.path, newValue)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configured upstream IP mode."""
        value = _nestedValue(config, self.path, 'dual')

        self.setText(value if isinstance(value, str) else 'dual')


class GuiHy2InlineBindings(EditorWidgetBinding):
    """Lay out several editor bindings on one row without duplicating behavior."""

    def __init__(self, *bindings: EditorWidgetBinding, **kwargs):
        """Create one persistent row that owns the supplied labeled controls."""
        expandInputs = kwargs.pop('expandInputs', True)

        super().__init__(**kwargs)

        self.bindings = tuple(bindings)
        self._widget = QWidget()

        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for index, binding in enumerate(self.bindings):
            title, inputWidget = binding.widgets()

            if index:
                layout.addSpacing(6)

            layout.addWidget(title)
            layout.addWidget(inputWidget, 1 if expandInputs else 0)

        if not expandInputs:
            layout.addStretch()

    def widgets(self):
        """Return the composed full-width form row."""
        return (self._widget,)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply every binding in the row to the same configuration."""
        modified = False

        for binding in self.bindings:
            modified |= binding.inputToFactory(config)

        return modified

    def factoryToInput(self, config: CoreConfiguration):
        """Load every binding in the row from the same configuration."""
        for binding in self.bindings:
            binding.factoryToInput(config)


class GuiHy2FormBindings(EditorWidgetBinding):
    """Give a related set of bindings its own form-alignment scope."""

    def __init__(self, *bindings: EditorWidgetBinding, **kwargs):
        """Create one persistent form containing the supplied bindings."""
        super().__init__(**kwargs)

        self.bindings = tuple(bindings)

        self._widget = QWidget()
        self._widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QFormLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for binding in self.bindings:
            layout.addRow(*binding.widgets())

    def widgets(self):
        """Return the composed full-width form row."""
        return (self._widget,)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply every binding in the form to the same configuration."""
        modified = False

        for binding in self.bindings:
            modified |= binding.inputToFactory(config)

        return modified

    def factoryToInput(self, config: CoreConfiguration):
        """Load every binding in the form from the same configuration."""
        for binding in self.bindings:
            binding.factoryToInput(config)


class GuiHy2ColumnBindings(EditorWidgetBinding):
    """Arrange independent compact form fields in equal-width columns."""

    def __init__(self, *bindings: EditorWidgetBinding, **kwargs):
        """Create one persistent row of equal-width one-field forms."""
        super().__init__(**kwargs)

        self.bindings = tuple(bindings)
        self._widget = QWidget()

        layout = QHBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        columns = []

        for binding in self.bindings:
            column = QWidget(self._widget)

            columnLayout = QFormLayout(column)
            columnLayout.setContentsMargins(0, 0, 0, 0)
            columnLayout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            columnLayout.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )
            columnLayout.addRow(*binding.widgets())

            layout.addWidget(column, 1)
            columns.append(column)

        minimumColumnWidth = max(
            (column.minimumSizeHint().width() for column in columns), default=0
        )

        for column in columns:
            column.setMinimumWidth(minimumColumnWidth)

    def widgets(self):
        """Return the composed full-width column row."""
        return (self._widget,)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply every binding in the row to the same configuration."""
        modified = False

        for binding in self.bindings:
            modified |= binding.inputToFactory(config)

        return modified

    def factoryToInput(self, config: CoreConfiguration):
        """Load every binding in the row from the same configuration."""
        for binding in self.bindings:
            binding.factoryToInput(config)


class GuiHy2ItemBasicServer(GuiEditorItemTextInput):
    """Represent GUI hy2 item basic server."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemBasicServer."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        oldServer = config.get('server', '')
        newServer = self.text()

        if isinstance(oldServer, str):
            if newServer != oldServer:
                config['server'] = newServer

                return True
            else:
                return False
        else:
            config['server'] = newServer

            return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.get('server', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemBasicAuth(GuiEditorItemTextInput):
    """Represent GUI hy2 item basic auth."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemBasicAuth."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        oldAuth = config.get('auth')
        newAuth = self.text()

        if newAuth == '':
            if oldAuth is None:
                return False
            else:
                config.pop('auth', None)

                return True
        else:
            if isinstance(oldAuth, str):
                if newAuth != oldAuth:
                    config['auth'] = newAuth

                    return True
                else:
                    return False
            else:
                config['auth'] = newAuth

                return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.get('auth', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemBasicCongestionComboBox(GuiEditorItemTextComboBox):
    """Represent GUI hy2 item basic congestion combo box."""

    CONGESTION_KEYS = ['type', 'bbrProfile']

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemBasicCongestionComboBox."""
        key = kwargs.pop('key', '')

        assert key in self.CONGESTION_KEYS

        super().__init__(*args, **kwargs)

        self.key = key

        if key == 'type':
            # TODO: Future extension
            self.addItems(['', 'bbr', 'reno'])
        elif key == 'bbrProfile':
            # TODO: Future extension
            self.addItems(['', 'standard', 'conservative', 'aggressive'])
        else:
            # Should not reach here
            raise

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        newValue = self.text()

        if newValue == '':
            return _removeNestedValue(config, ('congestion', self.key))
        else:
            return _setNestedValue(config, ('congestion', self.key), newValue)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            value = config['congestion'][self.key]
        except Exception:
            # Any non-exit exceptions

            value = ''

        self.setText(value if isinstance(value, str) else '')


class GuiHy2ItemObfsType(GuiEditorItemTextComboBox):
    """Represent GUI hy2 item obfs type."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemObfsType."""
        super().__init__(*args, **kwargs)

        self.addItems(HY2_OBFS_TYPES)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        try:
            oldObfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            oldObfsType = ''

        newObfsType = self.text()

        if newObfsType == '':
            if config.get('obfs') is None:
                return False
            else:
                config.pop('obfs', None)

                return True
        else:
            if not isinstance(oldObfsType, str) or newObfsType != oldObfsType:
                if not isinstance(config.get('obfs'), dict):
                    config['obfs'] = {}

                try:
                    config['obfs']['type'] = newObfsType
                except Exception:
                    # Any non-exit exceptions

                    pass

                return True
            else:
                return False

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        self.setText(obfsType if isinstance(obfsType, str) else '')


class GuiHy2ItemObfsPassword(GuiEditorItemTextInput):
    """Represent GUI hy2 item obfs password."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemObfsPassword."""
        self.obfsType = kwargs.pop('obfsType', 'salamander')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        newObfsPassword = self.text()

        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            return False

        path = ('obfs', obfsType, 'password')

        if newObfsPassword == '':
            return _removeNestedValue(config, path)
        else:
            return _setNestedValue(config, path, newObfsPassword)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            self.setText('')

            return

        try:
            obfsPassword = config['obfs'][obfsType]['password']
        except Exception:
            # Any non-exit exceptions

            obfsPassword = ''

        self.setText(obfsPassword)


class GuiHy2ItemObfsPacketSize(GuiEditorItemTextSpinBox):
    """Represent GUI hy2 item obfs packet size."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ItemObfsPacketSize."""
        self.obfsType, self.key, self.default = (
            kwargs.pop('obfsType', 'gecko'),
            kwargs.pop('key', ''),
            kwargs.pop('default', 0),
        )

        super().__init__(*args, **kwargs)

        self.setRange(1, 2048)
        self.setValue(self.default)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            return False

        path = ('obfs', obfsType, self.key)

        oldValue = _nestedValue(config, path, self.default)
        newValue = self.value()

        if isinstance(oldValue, int) and newValue == oldValue:
            return False
        else:
            return _setNestedValue(config, path, newValue)

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            self.setValue(self.default)

            return

        try:
            value = config['obfs'][obfsType][self.key]
        except Exception:
            # Any non-exit exceptions

            value = self.default

        if not isinstance(value, int):
            value = self.default

        self.setValue(value)


class GuiHy2PageObfsXXX(GuiEditorWidgetQWidget):
    """Represent GUI hy2 page obfs xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2PageObfsXXX."""
        super().__init__(*args, **kwargs)

    def setObfsTypeText(self, text: str):
        """Set obfs type text."""
        obfsType = self._containers[0]

        if isinstance(obfsType, GuiEditorItemTextComboBox):
            obfsType.setText(text)

    def obfsTypeText(self) -> str:
        """Return the semantic obfuscation value displayed by this page."""
        obfsType = self._containers[0]

        if isinstance(obfsType, GuiEditorItemTextComboBox):
            return obfsType.text()

        return ''

    def connectActivated(self, func):
        """Connect activated."""
        obfsType = self._containers[0]

        if isinstance(obfsType, GuiEditorItemTextComboBox):
            obfsType.connectActivated(func)


class GuiHy2PageObfsEmpty(GuiHy2PageObfsXXX):
    """Represent GUI hy2 page obfs empty."""

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
        ]


class GuiHy2PageObfsSalamander(GuiHy2PageObfsXXX):
    """Represent GUI hy2 page obfs salamander."""

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
            GuiHy2ItemObfsPassword(
                title='obfs-password',
                obfsType='salamander',
                translatable=False,
            ),
        ]


class GuiHy2PageObfsGecko(GuiHy2PageObfsXXX):
    """Represent GUI hy2 page obfs gecko."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2PageObfsGecko."""
        super().__init__(*args, **kwargs)

        self.minPacketSizeItem._input.valueChanged.connect(
            self.handleMinPacketSizeChanged
        )

        self.handleMinPacketSizeChanged(self.minPacketSizeItem.value())

    def containerSequence(self):
        """Return the editor item containers in display order."""
        self.minPacketSizeItem = GuiHy2ItemObfsPacketSize(
            title='minPacketSize',
            key='minPacketSize',
            default=512,
            translatable=False,
        )
        self.maxPacketSizeItem = GuiHy2ItemObfsPacketSize(
            title='maxPacketSize',
            key='maxPacketSize',
            default=1200,
            translatable=False,
        )

        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
            GuiHy2ItemObfsPassword(
                title='obfs-password',
                obfsType='gecko',
                translatable=False,
            ),
            self.minPacketSizeItem,
            self.maxPacketSizeItem,
        ]

    def setupLayout(self):
        """Align packet sizes with the full-width obfuscation fields."""
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        layout.setHorizontalSpacing(18)

        def addFullRow(index: int, row: int):
            label, inputWidget = self._containers[index].widgets()

            layout.addWidget(label, row, 0)
            layout.addWidget(inputWidget, row, 1, 1, 3)

        def addPair(index: int, column: int):
            label, inputWidget = self._containers[index].widgets()

            layout.addWidget(label, 2, column)
            layout.addWidget(inputWidget, 2, column + 1)

        packetSizeLabelWidth = max(
            self.minPacketSizeItem._title.sizeHint().width(),
            self.maxPacketSizeItem._title.sizeHint().width(),
        )

        layout.setColumnMinimumWidth(0, packetSizeLabelWidth)
        layout.setColumnMinimumWidth(2, packetSizeLabelWidth)

        addFullRow(0, 0)
        addFullRow(1, 1)
        addPair(2, 0)
        addPair(3, 2)

        self.setLayout(layout)

    def handleMinPacketSizeChanged(self, value: int):
        """Handle min packet size changed."""
        self.maxPacketSizeItem._input.setMinimum(value)

        if self.maxPacketSizeItem.value() < value:
            self.maxPacketSizeItem.setValue(value)


class GuiHy2ObfsPageStackedWidget(QStackedWidget):
    """Provide the GUI hy2 obfs page stacked widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ObfsPageStackedWidget."""
        super().__init__(*args, **kwargs)

        self._pages = [
            GuiHy2PageObfsEmpty(),
            GuiHy2PageObfsSalamander(),
            GuiHy2PageObfsGecko(),
        ]

        for page in self._pages:
            self.addWidget(page)

    def page(self, index: int) -> GuiHy2PageObfsXXX:
        """Return the page value."""
        return self._pages[index]

    def connectActivated(self, func):
        """Connect activated."""
        for page in self._pages:
            page.connectActivated(func)


class GuiHy2GroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI hy2 group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy2GroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiHy2ItemBasicServer(title=_('Server')),
            GuiHy2ItemBasicAuth(title='auth', translatable=False),
            GuiHy2ColumnBindings(
                GuiHy2ItemBasicCongestionComboBox(
                    title='congestion-type',
                    key='type',
                    translatable=False,
                ),
                GuiHy2ItemBasicCongestionComboBox(
                    title='congestion-profile',
                    key='bbrProfile',
                    translatable=False,
                ),
            ),
        ]


class GuiHy2GroupBoxProxyBandwidth(GuiEditorWidgetQGroupBox):
    """Edit local proxy endpoints and common Brutal bandwidth settings."""

    def __init__(self, **kwargs):
        """Initialize the compact proxy and bandwidth group."""
        super().__init__(self._titleText(), **kwargs)

    @staticmethod
    def _titleText():
        """Escape Qt's mnemonic marker while preserving the translated title."""
        return _('Proxy & Bandwidth').replace('&', '&&')

    def retranslate(self):
        """Refresh the translated title with a visible ampersand."""
        self.setTitle(self._titleText())

    def containerSequence(self):
        """Return the editor item containers in display order."""
        (
            self.proxyFields,
            self.bandwidthFields,
            self.lossCompensationItem,
        ) = (
            GuiHy2FormBindings(
                GuiEditorItemProxyHttp(title='http', translatable=False),
                GuiEditorItemProxySocks(title='socks', translatable=False),
            ),
            GuiHy2FormBindings(
                GuiHy2NestedTextInput(
                    title='bandwidth.up',
                    path=('bandwidth', 'up'),
                    translatable=False,
                ),
                GuiHy2NestedTextInput(
                    title='bandwidth.down',
                    path=('bandwidth', 'down'),
                    translatable=False,
                ),
            ),
            GuiHy2NestedSwitch(
                title='bandwidth.disableLossCompensation',
                path=('bandwidth', 'disableLossCompensation'),
                translatable=False,
            ),
        )

        return [
            self.proxyFields,
            self.bandwidthFields,
            GuiHy2InlineBindings(
                self.lossCompensationItem,
                expandInputs=False,
            ),
        ]


class GuiHy2ItemObfs(EditorBinding):
    """Edit the common obfuscation settings inside another form group."""

    def __init__(self, **kwargs):
        """Initialize the compact obfuscation editor binding."""
        super().__init__(**kwargs)

        self._config = CoreConfiguration()

        self._widget = GuiHy2ObfsPageStackedWidget()
        self._widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self._widget.connectActivated(self.handleActivated)

    def widgets(self):
        """Return the stacked obfuscation editor as one full-width form row."""
        return (self._widget,)

    def currentIndex(self) -> int:
        """Return the current index value."""
        return self._widget.currentIndex()

    def setCurrentIndex(self, index: int):
        """Set current index."""
        self._widget.setCurrentIndex(index)

    def page(self, index: int) -> GuiHy2PageObfsXXX:
        """Return the page value."""
        return self._widget.page(index)

    def handleActivated(self, index: int):
        """Handle activated."""
        if not 0 <= index < len(HY2_OBFS_TYPES):
            return

        page = self.page(index)
        page.factoryToInput(self._config)
        page.setObfsTypeText(HY2_OBFS_TYPES[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        oldObfs = config.get('obfs')
        oldObfsType = ''

        if isinstance(oldObfs, dict):
            oldObfsType = oldObfs.get('type', '')

        newObfsType = self.page(self.currentIndex()).obfsTypeText()

        if newObfsType == oldObfsType and newObfsType not in HY2_OBFS_TYPES:
            return False

        if newObfsType == '':
            if isinstance(oldObfs, dict):
                config.pop('obfs', None)

                return True

            return False

        if newObfsType not in HY2_OBFS_TYPES:
            return False

        if not isinstance(config.get('obfs'), dict):
            config['obfs'] = {}

        modified = oldObfsType != newObfsType

        config['obfs']['type'] = newObfsType

        obsoleteTypes = set(HY2_OBFS_TYPES)

        if isinstance(oldObfsType, str):
            obsoleteTypes.add(oldObfsType)

        for obfsType in obsoleteTypes:
            if obfsType and obfsType != newObfsType:
                config['obfs'].pop(obfsType, None)

        modified |= self.page(self.currentIndex()).inputToFactory(config)

        return modified

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        self._config = config

        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str):
            obfsType = ''

        index = HY2_OBFS_TYPES.index(obfsType) if obfsType in HY2_OBFS_TYPES else 0

        self.page(index).factoryToInput(config)
        self.page(index).setObfsTypeText(obfsType)
        self.setCurrentIndex(index)


class GuiHy2GroupBoxTLS(GuiEditorWidgetQGroupBox):
    """Represent GUI hy2 group box TLS."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy2GroupBoxTLS."""
        super().__init__('TLS', **kwargs, translatable=False)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiHy2NestedTextInput(
                title='sni',
                path=('tls', 'sni'),
                translatable=False,
            ),
            GuiHy2NestedTextInput(
                title='pinSHA256',
                path=('tls', 'pinSHA256'),
                translatable=False,
            ),
            GuiHy2NestedTextInput(
                title='ca',
                path=('tls', 'ca'),
                translatable=False,
            ),
            GuiHy2NestedTextInput(
                title='ech',
                path=('tls', 'ech'),
                translatable=False,
            ),
            GuiHy2NestedSwitch(
                title='insecure',
                path=('tls', 'insecure'),
                translatable=False,
            ),
        ]


class GuiHy2GroupBoxAdvanced(GuiEditorWidgetQGroupBox):
    """Expose a small, practical subset of advanced client configuration."""

    def __init__(self, **kwargs):
        """Initialize the compact advanced group."""
        super().__init__(_('Advanced'), **kwargs)

    def containerSequence(self):
        """Return common advanced controls while leaving other fields JSON-only."""
        self.obfsItem, self.ipModeItem = (
            GuiHy2ItemObfs(),
            GuiHy2ItemIPMode(
                title='ipMode',
                translatable=False,
            ),
        )

        self.chromeParrotItem, self.mimicEnabledItem = (
            GuiHy2NestedSwitch(
                title='disableChromeParrot',
                path=('quic', 'disableChromeParrot'),
                translatable=False,
            ),
            GuiHy2NestedSwitch(
                title='mimic.enabled',
                path=('mimic', 'enabled'),
                translatable=False,
            ),
        )

        self.toggleRow = GuiHy2ColumnBindings(
            self.chromeParrotItem,
            self.mimicEnabledItem,
        )

        return [
            self.obfsItem,
            self.ipModeItem,
            self.toggleRow,
        ]

    def setupPageLayout(self):
        """Align labels while keeping each control group independently compact."""
        layout = super().setupPageLayout()
        layout.setFormAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop
        )

        for index in range(self.obfsItem._widget.count()):
            page = self.obfsItem.page(index)
            page.layout().setContentsMargins(0, 0, 0, 0)

        return layout


class GuiHy2ProjectWebsiteURL(AppQLabel):
    """Represent GUI hy2 project website URL."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy2ProjectWebsiteURL."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set website URL."""
        self.setText(
            '<html><head/><body><p>'
            '<a href=\"https://v2.hysteria.network/\">'
            '<span style=\" text-decoration: underline; color:#007ad6;\">'
            + _('Project Website')
            + '</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        """Handle link activated."""
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        """Refresh translated text for the GUI hy2 project website URL."""
        self.setWebsiteURL()


class GuiHy2GroupBoxOther(EditorBinding, AppQGroupBox):
    """Represent GUI hy2 group box other."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy2GroupBoxOther."""
        super().__init__(_('Other'), **kwargs)

        self._website = GuiHy2ProjectWebsiteURL()

        layout = QFormLayout()
        layout.addRow(self._website)

        self.setLayout(layout)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Apply the current editor value to the configuration."""
        return False

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configuration value into the editor."""
        pass


class Hysteria2Editor(GuiEditorWidgetQDialog):
    """Represent GUI hysteria2."""

    def __init__(self, *args, **kwargs):
        """Initialize the Hysteria 2 configuration editor."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Hysteria2.value)

    def createGroupBoxSequence(self):
        """Create the configuration group boxes in display order."""
        self.basicGroup, self.advancedGroup = (
            GuiHy2GroupBoxBasic(),
            GuiHy2GroupBoxAdvanced(),
        )

        return [
            self.basicGroup,
            GuiHy2GroupBoxProxyBandwidth(),
            self.advancedGroup,
            GuiHy2GroupBoxTLS(),
        ]

    def accept(self):
        """Reject the unsupported Mimic and port-hopping combination."""
        server, mimicEnabled = (
            self.basicGroup._containers[1].text(),
            self.advancedGroup.mimicEnabledItem.isChecked(),
        )

        if mimicEnabled and ConfigHysteria2({'server': server}).usesPortHopping():
            mbox = AppQMessageBox(
                icon=AppQMessageBox.Icon.Warning,
                heading=_('Invalid Configuration'),
                text=_('Mimic cannot be used with port hopping.'),
                parent=self,
            )
            mbox.open()

            return

        super().accept()
