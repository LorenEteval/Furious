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

"""Provide the editor for Hysteria 2 native TUN settings."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from .Plugin import *
from .TUN import *

import copy
import logging

__all__ = ['Hysteria2TunSettingsDialog']

logger = logging.getLogger(__name__)


def _nestedValue(config: dict, path: tuple[str, ...], default):
    """Return a nested settings value or *default*."""
    value = config

    for key in path:
        if not isinstance(value, dict):
            return default

        value = value.get(key, default)

    return value


def _setNestedValue(config: dict, path: tuple[str, ...], value):
    """Set one nested settings value."""
    target = config

    for key in path[:-1]:
        child = target.get(key)

        if not isinstance(child, dict):
            child = {}
            target[key] = child

        target = child

    target[path[-1]] = value


class GuiHysteria2TUNItemText(GuiEditorItemTextInput):
    """Edit one string-valued Hysteria 2 TUN setting."""

    def __init__(self, *args, **kwargs):
        """Initialize a Hysteria 2 TUN string editor."""
        self.path = tuple(kwargs.pop('path'))

        maximumWidth = kwargs.pop('maximumWidth', None)

        super().__init__(*args, **kwargs)

        if maximumWidth is not None:
            self._input.setMaximumWidth(maximumWidth)

    def inputToFactory(self, config: dict) -> bool:
        """Store the current text in a Hysteria 2 TUN settings mapping."""
        value = self.text().strip()

        if _nestedValue(config, self.path, '') == value:
            return False

        _setNestedValue(config, self.path, value)

        return True

    def factoryToInput(self, config: dict):
        """Load one Hysteria 2 TUN string setting into the editor."""
        value = _nestedValue(config, self.path, '')

        self.setText(value if isinstance(value, str) else '')


class GuiHysteria2TUNItemList(GuiHysteria2TUNItemText):
    """Edit one list-valued TUN setting as comma-separated text."""

    def inputToFactory(self, config: dict) -> bool:
        """Store comma-separated values in the settings mapping."""
        value = [item.strip() for item in self.text().split(',') if item.strip()]

        if _nestedValue(config, self.path, []) == value:
            return False

        _setNestedValue(config, self.path, value)

        return True

    def factoryToInput(self, config: dict):
        """Load one list setting into the editor."""
        value = _nestedValue(config, self.path, [])

        self.setText(','.join(value) if isinstance(value, list) else '')


class GuiHysteria2TUNItemMTU(GuiEditorItemTextSpinBox):
    """Edit the native TUN MTU."""

    def __init__(self, *args, **kwargs):
        """Initialize the MTU editor."""
        super().__init__(*args, **kwargs)

        self.setRange(1, 65535)

    def inputToFactory(self, config: dict) -> bool:
        """Store the MTU in the settings mapping."""
        value = self.value()

        if config.get('mtu', 1500) == value:
            return False

        config['mtu'] = value

        return True

    def factoryToInput(self, config: dict):
        """Load the MTU into the editor."""
        value = config.get('mtu', 1500)

        self.setValue(value if isinstance(value, int) else 1500)


class GuiHysteria2TUNSettingsGroupBoxInterface(GuiEditorWidgetQGroupBox):
    """Edit Hysteria 2 TUN interface settings."""

    def __init__(self, **kwargs):
        """Initialize the interface settings group."""
        super().__init__(_('Interface'), **kwargs)

    def containerSequence(self):
        """Return interface-setting editors in display order."""
        return [
            GuiHysteria2TUNItemText(
                title='name',
                path=('name',),
                maximumWidth=360,
                translatable=False,
            ),
            GuiHysteria2TUNItemMTU(title='mtu', translatable=False),
            GuiHysteria2TUNItemText(
                title='timeout',
                path=('timeout',),
                maximumWidth=360,
                translatable=False,
            ),
        ]


class GuiHysteria2TUNSettingsGroupBoxNetwork(GuiEditorWidgetQGroupBox):
    """Edit Hysteria 2 TUN addresses and routes."""

    def __init__(self, **kwargs):
        """Initialize the network settings group."""
        super().__init__(_('Network'), **kwargs)

    def containerSequence(self):
        """Return address and route editors in display order."""
        return [
            GuiHysteria2TUNItemText(
                title='address.ipv4',
                path=('address', 'ipv4'),
                translatable=False,
            ),
            GuiHysteria2TUNItemText(
                title='address.ipv6',
                path=('address', 'ipv6'),
                translatable=False,
            ),
            GuiHysteria2TUNItemList(
                title='route.ipv4',
                path=('route', 'ipv4'),
                translatable=False,
            ),
            GuiHysteria2TUNItemList(
                title='route.ipv6',
                path=('route', 'ipv6'),
                translatable=False,
            ),
            GuiHysteria2TUNItemList(
                title='route.ipv4Exclude',
                path=('route', 'ipv4Exclude'),
                translatable=False,
            ),
            GuiHysteria2TUNItemList(
                title='route.ipv6Exclude',
                path=('route', 'ipv6Exclude'),
                translatable=False,
            ),
        ]

    def setupPageLayout(self):
        """Arrange related IPv4 and IPv6 settings in paired rows."""
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

        for index, container in enumerate(self._containers):
            row, field = divmod(index, 2)
            label, editor = container.widgets()
            column = field * 2

            layout.addWidget(label, row, column)
            layout.addWidget(editor, row, column + 1)

        return layout


class Hysteria2TUNDocumentationURL(AppQLabel):
    """Link to the official Hysteria 2 TUN documentation."""

    URL = 'https://hysteria.network/docs/advanced/Full-Client-Config/#tun'

    def __init__(self, *args, **kwargs):
        """Initialize the Hysteria 2 TUN documentation link."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set the translated documentation hyperlink text."""
        self.setText(f'<a href="{self.URL}">' + _('TUN Documentation') + '</a>')

    @staticmethod
    def handleLinkActivated(link: str):
        """Open the Hysteria 2 TUN documentation in the default browser."""
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link {link!r} success')
        else:
            logger.error(f'open link {link!r} failed')

    def retranslate(self):
        """Refresh the translated documentation hyperlink text."""
        self.setWebsiteURL()


class Hysteria2TunSettingsDialog(GuiEditorWidgetQDialog):
    """Edit and persist Hysteria 2 native TUN settings."""

    def __init__(self, *args, **kwargs):
        """Initialize the Hysteria 2 TUN settings dialog."""
        self._isConnectionActive = kwargs.pop('isConnectionActive', lambda: False)
        kwargs.setdefault('style', 'portrait')
        kwargs.setdefault('tabTranslatable', True)

        super().__init__(*args, **kwargs)

        self.setTabText(_('Customize Hysteria2 TUN Settings'))
        self.setFixedSize(int(650 * GOLDEN_RATIO), 650)

        self._settings = getHysteria2TUNSettings()

        self.factoryToInput(self._settings)

        self.accepted.connect(self.handleAccepted)

        self.layout().takeRow(self.layout().rowCount() - 1)

        bottomLayout = QHBoxLayout()
        bottomLayout.addWidget(Hysteria2TUNDocumentationURL())
        bottomLayout.addStretch(1)
        bottomLayout.addWidget(self.dialogBtns)

        self.layout().addRow(bottomLayout)

    def handleAccepted(self):
        """Persist changed settings and offer to reconnect when connected."""
        oldSettings = copy.deepcopy(self._settings)

        self.inputToFactory(self._settings)

        if self._settings == oldSettings:
            return

        saveHysteria2TUNSettings(self._settings)

        if SystemRuntime.isTUNMode() and self._isConnectionActive():
            showMBoxNewChangesNextTime()

    def createGroupBoxSequence(self):
        """Create Hysteria 2 TUN setting groups in display order."""
        return [
            GuiHysteria2TUNSettingsGroupBoxInterface(),
            GuiHysteria2TUNSettingsGroupBoxNetwork(),
        ]
