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

"""Provide widgets for GUI hysteria1."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import ConfigFactory, Protocol
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging

__all__ = ['Hysteria1Editor']

logger = logging.getLogger(__name__)


class GuiHy1ItemTextInput(GuiEditorItemTextInput):
    """Represent GUI hy1 item text input."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ItemTextInput."""
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldValue = config.get(self.key, '')
        newValue = self.text()

        if isinstance(oldValue, str):
            if newValue != oldValue:
                if newValue == '':
                    # Remove field
                    config.pop(self.key, None)
                else:
                    config[self.key] = newValue

                return True
            else:
                return False
        else:
            config[self.key] = newValue

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.get(self.key, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy1ItemBasicProtocol(GuiEditorItemTextComboBox):
    """Represent GUI hy1 item basic protocol."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ItemBasicProtocol."""
        super().__init__(*args, **kwargs)

        self.addItems(['', 'udp', 'wechat-video', 'faketcp'])

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldProtocol = config.get('protocol', '')
        newProtocol = self.text()

        if isinstance(oldProtocol, str):
            if newProtocol != oldProtocol:
                config['protocol'] = newProtocol

                return True
            else:
                return False
        else:
            config['protocol'] = newProtocol

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.get('protocol', 'udp'))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy1ItemSpeedUpMbps(GuiEditorItemTextSpinBox):
    """Represent GUI hy1 item speed up mbps."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ItemSpeedUpMbps."""
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 1048576)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldUpMbps = config.get('up_mbps')
        newUpMbps = self.value()

        if isinstance(oldUpMbps, int):
            if newUpMbps != oldUpMbps:
                config['up_mbps'] = newUpMbps

                return True
            else:
                return False
        else:
            config['up_mbps'] = newUpMbps

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setValue(config.get('up_mbps'))
        except Exception:
            # Any non-exit exceptions

            self.setValue(24)


class GuiHy1ItemSpeedDownMbps(GuiEditorItemTextSpinBox):
    """Represent GUI hy1 item speed down mbps."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ItemSpeedDownMbps."""
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 1048576)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldDownMbps = config.get('down_mbps')
        newDownMbps = self.value()

        if isinstance(oldDownMbps, int):
            if newDownMbps != oldDownMbps:
                config['down_mbps'] = newDownMbps

                return True
            else:
                return False
        else:
            config['down_mbps'] = newDownMbps

            return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setValue(config.get('down_mbps'))
        except Exception:
            # Any non-exit exceptions

            self.setValue(96)


class GuiHy1ItemTLSInsecure(GuiEditorItemTextCheckBox):
    """Represent GUI hy1 item TLS insecure."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ItemTLSInsecure."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        try:
            oldChecked = config.get('insecure')
        except Exception:
            # Any non-exit exceptions

            oldChecked = False

        newChecked = self.isChecked()

        if newChecked:
            if oldChecked is not True:
                config['insecure'] = True

                return True
            else:
                return False
        else:
            if oldChecked is True:
                config['insecure'] = False

                return True
            if oldChecked is False:
                return False

            # Invalid value for insecure. Remove it
            config.pop('insecure', None)

            # Modified silently
            return False

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            checked = config['insecure']
        except Exception:
            # Any non-exit exceptions

            checked = False

        if not isinstance(checked, bool):
            checked = False

        self.setChecked(checked)


class GuiHy1ProjectWebsiteURL(AppQLabel):
    """Represent GUI hy1 project website URL."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiHy1ProjectWebsiteURL."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set website URL."""
        self.setText(
            '<html><head/><body><p>'
            '<a href=\"https://v1.hysteria.network/\">'
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
        """Refresh translated text for the GUI hy1 project website URL."""
        self.setWebsiteURL()


class GuiHy1GroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI hy1 group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy1GroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiHy1ItemTextInput(title=_('Server'), key='server'),
            GuiHy1ItemBasicProtocol(title=_('Protocol')),
            GuiHy1ItemTextInput(title='auth_str', translatable=False, key='auth_str'),
            GuiHy1ItemTextInput(title='obfs', translatable=False, key='obfs'),
        ]


class GuiHy1GroupBoxProxy(GuiEditorWidgetQGroupBox):
    """Represent GUI hy1 group box proxy."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy1GroupBoxProxy."""
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiHy1GroupBoxSpeed(GuiEditorWidgetQGroupBox):
    """Represent GUI hy1 group box speed."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy1GroupBoxSpeed."""
        super().__init__(_('Speed'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiHy1ItemSpeedUpMbps(title='up_mbps', translatable=False),
            GuiHy1ItemSpeedDownMbps(title='down_mbps', translatable=False),
        ]


class GuiHy1GroupBoxTLS(GuiEditorWidgetQGroupBox):
    """Represent GUI hy1 group box TLS."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy1GroupBoxTLS."""
        super().__init__('TLS', **kwargs)

        self.translatable = False

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiHy1ItemTextInput(title='sni', translatable=False, key='server_name'),
            GuiHy1ItemTextInput(title='alpn', translatable=False, key='alpn'),
            GuiHy1ItemTextInput(title='ca', translatable=False, key='ca'),
            GuiHy1ItemTLSInsecure(title='insecure', translatable=False),
        ]


class GuiHy1GroupBoxOther(EditorBinding, AppQGroupBox):
    """Represent GUI hy1 group box other."""

    def __init__(self, **kwargs):
        """Initialize the GuiHy1GroupBoxOther."""
        super().__init__(_('Other'), **kwargs)

        self._website = GuiHy1ProjectWebsiteURL()

        layout = QFormLayout()
        layout.addRow(self._website)

        self.setLayout(layout)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        return False

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        pass


class Hysteria1Editor(GuiEditorWidgetQDialog):
    """Represent GUI hysteria1."""

    def __init__(self, *args, **kwargs):
        """Initialize the Hysteria 1 configuration editor."""
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Hysteria1.value)

    def createGroupBoxSequence(self):
        """Create the configuration group boxes in display order."""
        return [
            GuiHy1GroupBoxBasic(),
            GuiHy1GroupBoxProxy(),
            GuiHy1GroupBoxSpeed(),
            GuiHy1GroupBoxTLS(),
            # GuiHy1GroupBoxOther(),
        ]
