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

"""Provide widgets for GUI TUN settings."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging
import functools

__all__ = ['GuiTUNSettings']

logger = logging.getLogger(__name__)


class GuiTUNSettingsItemXXX(GuiEditorItemTextInput):
    """Represent GUI TUN settings item xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTUNSettingsItemXXX."""
        self.key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        oldItem = config.get(self.key, '')
        newItem = self.text()

        if newItem != oldItem:
            config[self.key] = newItem

            # Modified
            return True
        else:
            # Not modified
            return False

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        self.setText(config.get(self.key, ''))


class GuiTUNSettingsItemSpinBoxBufferSizeXXX(GuiEditorItemTextSpinBox):
    """Represent GUI TUN settings item spin box buffer size xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTUNSettingsItemSpinBoxBufferSizeXXX."""
        self.key = kwargs.pop('key', '')
        self.default = kwargs.pop('default', 1)
        self.start = kwargs.pop('start', 1)
        self.end = kwargs.pop('end', 4)

        super().__init__(*args, **kwargs)

        # Range
        self.setRange(self.start, self.end)

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        oldValue = config.get(self.key, self.default)
        newValue = self.value()

        if not isinstance(oldValue, int):
            oldValue = -1e8

        if newValue != oldValue:
            config[self.key] = newValue

            # Modified
            return True
        else:
            # Not modified
            return False

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        oldValue = config.get(self.key, self.default)

        if not isinstance(oldValue, int):
            config[self.key] = oldValue = self.default

        self.setValue(oldValue)


class GuiTUNSettingsItemCheckBoxXXX(GuiEditorItemTextCheckBox):
    """Represent GUI TUN settings item check box xxx."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTUNSettingsItemCheckBoxXXX."""
        self.key = kwargs.pop('key', '')
        self.default = kwargs.pop('default', 'False')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        oldItem = config.get(self.key, self.default)
        newItem = self.isChecked()

        if oldItem not in ['False', 'True']:
            # Invalid value. Set to default
            oldItem = self.default

        if str(newItem) != oldItem:
            config[self.key] = str(newItem)

            # Modified
            return True
        else:
            # Not modified
            return False

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        self.setChecked(config.get(self.key, self.default) == 'True')


class AppQLabelHelpPage(AppQLabel):
    """Represent app q label help page."""

    def __init__(self, *args, **kwargs):
        """Initialize the AppQLabelHelpPage."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set website URL."""
        self.setText(
            f'<html><head/><body><p>'
            f'<a href=\"{APPLICATION_ABOUT_PAGE}/wiki/TUN-Mode\">'
            f'<span style=\" text-decoration: underline; color:#007ad6;\">'
            + _('Go to help page')
            + f'</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        """Handle link activated."""
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        """Refresh translated text for the app q label help page."""
        self.setWebsiteURL()


class GuiTUNSettingsItemHelpPage(GuiEditorItemWidgetContainer):
    """Provide the TUN settings item help configuration editor page."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTUNSettingsItemHelpPage."""
        super().__init__(*args, **kwargs)

        self._page = AppQLabelHelpPage()

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return [self._page]


class GuiTUNSettingsGroupBoxBasic(GuiEditorWidgetQGroupBox):
    """Represent GUI TUN settings group box basic."""

    def __init__(self, **kwargs):
        """Initialize the GuiTUNSettingsGroupBoxBasic."""
        super().__init__(_('Basic Configuration'), **kwargs)

    def setupPageLayout(self):
        """Set up page layout."""
        layout = QFormLayout()
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        pairsLayout = QGridLayout()
        pairsLayout.setColumnStretch(1, 1)
        pairsLayout.setColumnStretch(3, 1)

        def addPair(index: int, row: int, column: int):
            """Add pair."""
            label, inputWidget = self._containers[index].widgets()

            pairsLayout.addWidget(label, row, column)
            pairsLayout.addWidget(inputWidget, row, column + 1)

        addPair(0, 0, 0)
        addPair(1, 0, 2)
        addPair(2, 1, 0)
        addPair(3, 1, 2)

        layout.addRow(pairsLayout)
        layout.addRow(*self._containers[4].widgets())
        layout.addRow(*self._containers[5].widgets())
        layout.addRow(*self._containers[6].widgets())

        return layout

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiTUNSettingsItemXXX(
                title=_('Primary Adapter Interface Name'),
                key='primaryAdapterInterfaceName',
            ),
            GuiTUNSettingsItemXXX(
                title=_('Primary Adapter Interface IP'),
                key='primaryAdapterInterfaceIP',
            ),
            GuiTUNSettingsItemXXX(
                title=_('Default Primary Gateway IP'),
                key='defaultPrimaryGatewayIP',
            ),
            GuiTUNSettingsItemXXX(
                title=_('Tun2socks Adapter Interface DNS'),
                key='tunAdapterInterfaceDNS',
            ),
            GuiTUNSettingsItemXXX(
                title=_('Bypass Tun2socks Adapter Interface IP (separated by commas)'),
                key='bypassTUNAdapterInterfaceIP',
            ),
            GuiTUNSettingsItemCheckBoxXXX(
                title=_(
                    'Disable Primary Adapter Interface DNS (Mitigating DNS leaks on Windows)'
                ),
                key='disablePrimaryAdapterInterfaceDNS',
                default='True',
            ),
            GuiTUNSettingsItemHelpPage(),
        ]


class GuiTUNSettingsGroupBoxMemory(GuiEditorWidgetQGroupBox):
    """Represent GUI TUN settings group box memory."""

    def __init__(self, **kwargs):
        """Initialize the GuiTUNSettingsGroupBoxMemory."""
        super().__init__(_('Memory Optimization'), **kwargs)

    def containerSequence(self):
        """Return the editor item containers in display order."""
        return [
            GuiTUNSettingsItemSpinBoxBufferSizeXXX(
                title=_('TCP Send Buffer Size (MiB)'),
                key='tcpSendBufferSize',
                default=1,
                start=1,
                end=4,
            ),
            GuiTUNSettingsItemSpinBoxBufferSizeXXX(
                title=_('TCP Receive Buffer Size (MiB)'),
                key='tcpReceiveBufferSize',
                default=1,
                start=1,
                end=4,
            ),
            GuiTUNSettingsItemCheckBoxXXX(
                title=_('TCP Receive Buffer Auto-tuning'),
                key='tcpAutoTuning',
                default='False',
            ),
        ]


class GuiTUNSettings(GuiEditorWidgetQDialog):
    """Store and validate GUI TUN settings."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiTUNSettings."""
        tabTranslatable = kwargs.pop('tabTranslatable', True)
        style = kwargs.pop('style', 'portrait')

        super().__init__(*args, tabTranslatable=tabTranslatable, style=style, **kwargs)

        self.setTabText(_('Customize Tun2socks Settings'))

        if PLATFORM == 'Darwin' or PLATFORM == 'Linux':
            self.setFixedSize(int(690 * GOLDEN_RATIO), int(690))
        else:
            self.setFixedSize(int(620 * GOLDEN_RATIO), int(620))

        # Shallow copy
        config = Storage.UserTUNSettings()

        try:
            self.factoryToInput(config)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        self.accepted.connect(functools.partial(self.handleAccepted, config))
        self.rejected.connect(functools.partial(self.handleRejected))

    def handleAccepted(self, config: dict):
        """Handle accepted."""
        modified = self.inputToFactory(config)

        if modified and SystemRuntime.isTUNMode():
            showMBoxNewChangesNextTime()

        self.accepted.disconnect()
        self.rejected.disconnect()

    def handleRejected(self):
        """Handle rejected."""
        self.accepted.disconnect()
        self.rejected.disconnect()

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        modified = False

        for groupBox in self.groupBoxSequence():
            modified |= groupBox.inputToFactory(config)

        return modified

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        for groupBox in self.groupBoxSequence():
            groupBox.factoryToInput(config)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        """Return the configuration group boxes in display order."""
        return [
            GuiTUNSettingsGroupBoxBasic(),
            GuiTUNSettingsGroupBoxMemory(),
        ]
