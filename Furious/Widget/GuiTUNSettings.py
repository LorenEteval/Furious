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

from PySide6.QtGui import *

import logging
import functools

__all__ = ['GuiTUNSettings']

logger = logging.getLogger(__name__)


class GuiTUNSettingsItemXXX(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        self.key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: dict) -> bool:
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
        self.setText(config.get(self.key, ''))


class GuiTUNSettingsItemSpinBoxBufferSizeXXX(GuiEditorItemTextSpinBox):
    def __init__(self, *args, **kwargs):
        self.key = kwargs.pop('key', '')
        self.default = kwargs.pop('default', 1)
        self.start = kwargs.pop('start', 1)
        self.end = kwargs.pop('end', 4)

        super().__init__(*args, **kwargs)

        # Range
        self.setRange(self.start, self.end)

    def inputToFactory(self, config: dict) -> bool:
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
        oldValue = config.get(self.key, self.default)

        if not isinstance(oldValue, int):
            config[self.key] = oldValue = self.default

        self.setValue(oldValue)


class GuiTUNSettingsItemCheckBoxXXX(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        self.key = kwargs.pop('key', '')
        self.default = kwargs.pop('default', 'False')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: dict) -> bool:
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
        self.setChecked(config.get(self.key, self.default) == 'True')


class AppQLabelHelpPage(AppQLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        self.setText(
            f'<html><head/><body><p>'
            f'<a href=\"{APPLICATION_ABOUT_PAGE}/wiki/TUN-Mode\">'
            f'<span style=\" text-decoration: underline; color:#007ad6;\">'
            + _('Go to help page')
            + f'</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        self.setWebsiteURL()


class GuiTUNSettingsItemHelpPage(GuiEditorItemWidgetContainer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._page = AppQLabelHelpPage()

    def widgets(self):
        return [self._page]


class GuiTUNSettingsGroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
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
                title=_('TUN Adapter Interface DNS'),
                key='tunAdapterInterfaceDNS',
            ),
            GuiTUNSettingsItemXXX(
                title=_('Bypass TUN Adapter Interface IP (separated by commas)'),
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
    def __init__(self, **kwargs):
        super().__init__(_('Memory Optimization'), **kwargs)

    def containerSequence(self):
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
    def __init__(self, *args, **kwargs):
        tabTranslatable = kwargs.pop('tabTranslatable', True)
        style = kwargs.pop('style', 'portrait')

        super().__init__(*args, tabTranslatable=tabTranslatable, style=style, **kwargs)

        self.setTabText(_('Customize TUN Settings'))

        if PLATFORM == 'Darwin' or PLATFORM == 'Linux':
            self.setFixedSize(int(550 * GOLDEN_RATIO), int(550))
        else:
            self.setFixedSize(int(480 * GOLDEN_RATIO), int(480))

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
        modified = self.inputToFactory(config)

        if modified and SystemRuntime.isTUNMode():
            showMBoxNewChangesNextTime()

        self.accepted.disconnect()
        self.rejected.disconnect()

    def handleRejected(self):
        self.accepted.disconnect()
        self.rejected.disconnect()

    def inputToFactory(self, config: dict) -> bool:
        modified = False

        for groupBox in self.groupBoxSequence():
            modified |= groupBox.inputToFactory(config)

        return modified

    def factoryToInput(self, config: dict):
        for groupBox in self.groupBoxSequence():
            groupBox.factoryToInput(config)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        return [
            GuiTUNSettingsGroupBoxBasic(),
            GuiTUNSettingsGroupBoxMemory(),
        ]
