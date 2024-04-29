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

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging
import functools

__all__ = ['GuiHysteria1']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)


class GuiHy1ItemTextInput(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.get(self.key, ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy1ItemBasicProtocol(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(['', 'udp', 'wechat-video', 'faketcp'])

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.get('protocol', 'udp'))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy1ItemSpeedUpMbps(GuiEditorItemTextSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 1048576)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setValue(config.get('up_mbps'))
        except Exception:
            # Any non-exit exceptions

            self.setValue(24)


class GuiHy1ItemSpeedDownMbps(GuiEditorItemTextSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Range
        self.setRange(0, 1048576)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setValue(config.get('down_mbps'))
        except Exception:
            # Any non-exit exceptions

            self.setValue(96)


class GuiHy1ItemTLSInsecure(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            checked = config['insecure']
        except Exception:
            # Any non-exit exceptions

            checked = False

        if not isinstance(checked, bool):
            checked = False

        self.setChecked(checked)


needTrans('Project Website')


class GuiHy1ProjectWebsiteURL(AppQLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        self.setText(
            '<html><head/><body><p>'
            '<a href=\"https://v1.hysteria.network/\">'
            '<span style=\" text-decoration: underline; color:#007ad6;\">'
            + _('Project Website')
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


needTrans(
    'Basic Configuration',
    'Remark',
    'Server',
    'Protocol',
)


class GuiHy1GroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiHy1ItemTextInput(title=_('Server'), key='server'),
            GuiHy1ItemBasicProtocol(title=_('Protocol')),
            GuiHy1ItemTextInput(title='auth_str', translatable=False, key='auth_str'),
            GuiHy1ItemTextInput(title='obfs', translatable=False, key='obfs'),
        ]


needTrans('Proxy')


class GuiHy1GroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


needTrans('Speed')


class GuiHy1GroupBoxSpeed(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Speed'), **kwargs)

    def containerSequence(self):
        return [
            GuiHy1ItemSpeedUpMbps(title='up_mbps', translatable=False),
            GuiHy1ItemSpeedDownMbps(title='down_mbps', translatable=False),
        ]


class GuiHy1GroupBoxTLS(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__('TLS', **kwargs)

        self.translatable = False

    def containerSequence(self):
        return [
            GuiHy1ItemTextInput(title='sni', translatable=False, key='server_name'),
            GuiHy1ItemTextInput(title='alpn', translatable=False, key='alpn'),
            GuiHy1ItemTextInput(title='ca', translatable=False, key='ca'),
            GuiHy1ItemTLSInsecure(title='insecure', translatable=False),
        ]


needTrans('Other')


class GuiHy1GroupBoxOther(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Other'), **kwargs)

        self._website = GuiHy1ProjectWebsiteURL()

        layout = QFormLayout()
        layout.addRow(self._website)

        self.setLayout(layout)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        return False

    def factoryToInput(self, config: ConfigurationFactory):
        pass


class GuiHysteria1(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Hysteria1)

    def groupBoxSequence(self):
        return [
            GuiHy1GroupBoxBasic(),
            GuiHy1GroupBoxProxy(),
            GuiHy1GroupBoxSpeed(),
            GuiHy1GroupBoxTLS(),
            # GuiHy1GroupBoxOther(),
        ]
