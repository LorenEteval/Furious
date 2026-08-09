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

"""Provide the editor for Xray-core native TUN settings."""

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
import functools

__all__ = ['XrayTunSettingsDialog']

logger = logging.getLogger(__name__)


class GuiXrayTUNItemText(GuiEditorItemTextInput):
    """Edit one string-valued Xray TUN setting."""

    def __init__(self, *args, **kwargs):
        """Initialize an Xray TUN string editor."""
        self.key = kwargs.pop('key')

        maximumWidth = kwargs.pop('maximumWidth', None)

        super().__init__(*args, **kwargs)

        if maximumWidth is not None:
            self._input.setMaximumWidth(maximumWidth)

    def inputToFactory(self, config: dict) -> bool:
        """Store the current text in an Xray TUN settings mapping."""
        value = self.text().strip()

        if config.get(self.key, '') == value:
            return False

        config[self.key] = value

        return True

    def factoryToInput(self, config: dict):
        """Load one Xray TUN string setting into the editor."""
        self.setText(config.get(self.key, ''))


class GuiXrayTUNItemList(GuiXrayTUNItemText):
    """Edit one list-valued Xray TUN setting as comma-separated text."""

    def inputToFactory(self, config: dict) -> bool:
        """Store comma-separated values in the settings mapping."""
        value = [item.strip() for item in self.text().split(',') if item.strip()]

        if config.get(self.key, []) == value:
            return False

        config[self.key] = value

        return True

    def factoryToInput(self, config: dict):
        """Load one Xray TUN list setting into the editor."""
        value = config.get(self.key, [])

        self.setText(','.join(value) if isinstance(value, list) else '')


class GuiXrayTUNItemNumber(GuiEditorItemTextSpinBox):
    """Edit one integer-valued Xray TUN setting."""

    def __init__(self, *args, **kwargs):
        """Initialize an Xray TUN numeric editor."""
        self.key = kwargs.pop('key')
        self.default = kwargs.pop('default')

        minimum = kwargs.pop('minimum')
        maximum = kwargs.pop('maximum')

        super().__init__(*args, **kwargs)

        self.setRange(minimum, maximum)

    def inputToFactory(self, config: dict) -> bool:
        """Store the current number in an Xray TUN settings mapping."""
        value = self.value()

        if config.get(self.key, self.default) == value:
            return False

        config[self.key] = value

        return True

    def factoryToInput(self, config: dict):
        """Load one Xray TUN numeric setting into the editor."""
        value = config.get(self.key, self.default)

        self.setValue(value if isinstance(value, int) else self.default)


class GuiXrayTUNSettingsGroupBoxInterface(GuiEditorWidgetQGroupBox):
    """Edit Xray TUN interface identity and packet settings."""

    def __init__(self, **kwargs):
        """Initialize the interface settings group."""
        super().__init__(_('Interface'), **kwargs)

    def containerSequence(self):
        """Return interface-setting editors in display order."""
        return [
            GuiXrayTUNItemText(
                title='Name',
                translatable=False,
                key='name',
                maximumWidth=360,
            ),
            GuiXrayTUNItemText(
                title='Description',
                translatable=False,
                key='desc',
                maximumWidth=360,
            ),
            GuiXrayTUNItemNumber(
                title='MTU',
                key='mtu',
                default=1500,
                minimum=1,
                maximum=65535,
            ),
            GuiXrayTUNItemNumber(
                title='UserLevel',
                key='userLevel',
                default=0,
                minimum=0,
                maximum=65535,
            ),
        ]


class XrayTUNDocumentationURL(AppQLabel):
    """Link to the official Xray-core TUN documentation."""

    URL = 'https://xtls.github.io/config/inbounds/tun.html'

    def __init__(self, *args, **kwargs):
        """Initialize the Xray TUN documentation link."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set the translated documentation hyperlink text."""
        self.setText(
            '<html><head/><body><p>'
            f'<a href="{self.URL}">'
            '<span style=" text-decoration: underline; color:#007ad6;">'
            + _('TUN Documentation')
            + '</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        """Open the Xray TUN documentation in the default browser."""
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        """Refresh the translated documentation hyperlink text."""
        self.setWebsiteURL()


class GuiXrayTUNSettingsGroupBoxNetwork(GuiEditorWidgetQGroupBox):
    """Edit Xray TUN addresses, DNS, and automatic routing settings."""

    def __init__(self, **kwargs):
        """Initialize the network settings group."""
        super().__init__(_('Network'), **kwargs)

    def containerSequence(self):
        """Return network-setting editors in display order."""
        return [
            GuiXrayTUNItemList(
                title=_('Gateway (separated by commas)'),
                key='gateway',
            ),
            GuiXrayTUNItemList(
                title=_('DNS (separated by commas)'),
                key='dns',
            ),
            GuiXrayTUNItemList(
                title=_('AutoSystemRoutingTable (separated by commas)'),
                key='autoSystemRoutingTable',
            ),
            GuiXrayTUNItemText(
                title='AutoOutboundsInterface',
                translatable=False,
                key='autoOutboundsInterface',
            ),
        ]


class XrayTunSettingsDialog(GuiEditorWidgetQDialog):
    """Edit and persist Xray-core native TUN settings."""

    def __init__(self, *args, **kwargs):
        """Initialize the Xray-core TUN settings dialog."""
        self._isConnectionActive = kwargs.pop('isConnectionActive', lambda: False)
        kwargs.setdefault('style', 'portrait')
        kwargs.setdefault('tabTranslatable', True)

        super().__init__(*args, **kwargs)

        self.setTabText(_('Customize Xray-core TUN Settings'))
        self.setFixedSize(int(650 * GOLDEN_RATIO), 650)

        self._settings = getXrayTUNSettings()

        self.factoryToInput(self._settings)

        self.accepted.connect(self.handleAccepted)

        self.layout().takeRow(self.layout().rowCount() - 1)

        bottomLayout = QHBoxLayout()
        bottomLayout.addWidget(XrayTUNDocumentationURL())
        bottomLayout.addStretch(1)
        bottomLayout.addWidget(self.dialogBtns)

        self.layout().addRow(bottomLayout)

    def handleAccepted(self):
        """Persist changed settings and offer to reconnect when connected."""
        oldSettings = copy.deepcopy(self._settings)

        self.inputToFactory(self._settings)

        if self._settings == oldSettings:
            return

        saveXrayTUNSettings(self._settings)

        if SystemRuntime.isTUNMode() and self._isConnectionActive():
            showMBoxNewChangesNextTime()

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        """Return Xray TUN setting groups in display order."""
        return [
            GuiXrayTUNSettingsGroupBoxInterface(),
            GuiXrayTUNSettingsGroupBoxNetwork(),
        ]
