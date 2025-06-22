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

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from PySide6.QtGui import *

import logging

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


class GuiTUNSettingsItemDisablePrimaryAdapterInterfaceDNS(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        self.key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: dict) -> bool:
        oldItem = config.get(self.key, 'True')
        newItem = self.isChecked()

        if oldItem not in ['False', 'True']:
            # Invalid value. Set to default
            oldItem = 'True'

        if str(newItem) != oldItem:
            config[self.key] = str(newItem)

            # Modified
            return True
        else:
            # Not modified
            return False

    def factoryToInput(self, config: dict):
        self.setChecked(config.get(self.key, 'True') != 'False')


class AppQLabelHelpPage(AppQLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        self.setText(
            '<html><head/><body><p>'
            '<a href=\"https://github.com/LorenEteval/Furious/wiki/TUN-Mode\">'
            '<span style=\" text-decoration: underline; color:#007ad6;\">'
            + _('Go to help page')
            + '</span></a></p></body></html>'
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


class GuiTUNSettingsGroupBox(GuiEditorWidgetQGroupBox):
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
                title=_('Bypass TUN adapter interface IP (separated by commas)'),
                key='bypassTUNAdapterInterfaceIP',
            ),
            GuiTUNSettingsItemDisablePrimaryAdapterInterfaceDNS(
                title=_(
                    'Disable Primary Adapter Interface DNS (Mitigating DNS leaks on Windows)'
                ),
                key='disablePrimaryAdapterInterfaceDNS',
            ),
            GuiTUNSettingsItemHelpPage(),
        ]


class GuiTUNSettings(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        tabTranslatable = kwargs.pop('tabTranslatable', True)

        super().__init__(*args, tabTranslatable=tabTranslatable, **kwargs)

        self.setTabText(_('Customize TUN Settings'))
        self.setFixedSize(int(460 * GOLDEN_RATIO), int(460))

        # Shallow copy
        config = AS_UserTUNSettings()

        try:
            self.factoryToInput(config)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        self.accepted.connect(functools.partial(self.handleAccepted, config))
        self.rejected.connect(functools.partial(self.handleRejected))

    def handleAccepted(self, config: dict):
        modified = self.inputToFactory(config)

        if modified and isTUNMode():
            showNewChangesNextTimeMBox()

        self.accepted.disconnect()
        self.rejected.disconnect()

    def handleRejected(self):
        self.accepted.disconnect()
        self.rejected.disconnect()

    def inputToFactory(self, config: dict) -> bool:
        modified = False

        for groupBox in self.groupBoxes:
            modified |= groupBox.inputToFactory(config)

        return modified

    def factoryToInput(self, config: dict):
        for groupBox in self.groupBoxes:
            groupBox.factoryToInput(config)

    def groupBoxSequence(self):
        return [
            GuiTUNSettingsGroupBox(),
        ]
