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
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging
import functools

__all__ = ['GuiHysteria2']

logger = logging.getLogger(__name__)

HY2_OBFS_TYPES = ['', 'salamander', 'gecko']


class GuiHy2ItemBasicServer(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def factoryToInput(self, config: ConfigFactory):
        try:
            self.setText(config.get('server', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemBasicAuth(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def factoryToInput(self, config: ConfigFactory):
        try:
            self.setText(config.get('auth', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemBasicCongestionComboBox(GuiEditorItemTextComboBox):
    CONGESTION_KEYS = ['type', 'bbrProfile']

    def __init__(self, *args, **kwargs):
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

    def inputToFactory(self, config: ConfigFactory) -> bool:
        newValue = self.text()

        if newValue == '':
            congestion = config.get('congestion')

            if isinstance(congestion, dict):
                if len(congestion) > 0:
                    if congestion.get(self.key) is not None:
                        oldValue = congestion[self.key]

                        congestion.pop(self.key, None)

                        if not isinstance(oldValue, str) or oldValue != '':
                            modified = True
                        else:
                            modified = False
                    else:
                        modified = False

                    # TODO: Future extension
                    anyValid = any(
                        congestion.get(key, '') for key in self.CONGESTION_KEYS
                    )

                    if not anyValid:
                        config.pop('congestion', None)

                        return True
                    else:
                        return modified
                else:
                    config.pop('congestion', None)

                    # Modified silently
                    return False
            else:
                config.pop('congestion', None)

                # Modified silently
                return False
        else:
            if not isinstance(config.get('congestion'), dict):
                config['congestion'] = {}

            oldValue = config['congestion'].get(self.key, '')

            if not isinstance(oldValue, str) or newValue != oldValue:
                config['congestion'][self.key] = newValue

                return True
            else:
                return False

    def factoryToInput(self, config: ConfigFactory):
        try:
            value = config['congestion'][self.key]
        except Exception:
            # Any non-exit exceptions

            value = ''

        self.setText(value)


class GuiHy2ItemObfsType(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addItems(HY2_OBFS_TYPES)

    def inputToFactory(self, config: ConfigFactory) -> bool:
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

    def factoryToInput(self, config: ConfigFactory):
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if isinstance(obfsType, str) and obfsType in HY2_OBFS_TYPES:
            self.setText(obfsType)
        else:
            self.setText('')


class GuiHy2ItemObfsPassword(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        self.obfsType = kwargs.pop('obfsType', 'salamander')

        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        newObfsPassword = self.text()

        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            return False

        modified = False

        if not isinstance(config.get('obfs'), dict):
            config['obfs'] = {}

            modified = True

        if not isinstance(config['obfs'].get(obfsType), dict):
            config['obfs'][obfsType] = {}

            modified = True

        try:
            oldObfsPassword = config['obfs'][obfsType]['password']
        except Exception:
            # Any non-exit exceptions

            oldObfsPassword = ''

        if not isinstance(oldObfsPassword, str) or newObfsPassword != oldObfsPassword:
            config['obfs'][obfsType]['password'] = newObfsPassword

            return True
        else:
            return modified

    def factoryToInput(self, config: ConfigFactory):
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
    def __init__(self, *args, **kwargs):
        self.obfsType, self.key, self.default = (
            kwargs.pop('obfsType', 'gecko'),
            kwargs.pop('key', ''),
            kwargs.pop('default', 0),
        )

        super().__init__(*args, **kwargs)

        self.setRange(1, 2048)
        self.setValue(self.default)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType != self.obfsType:
            return False

        if not isinstance(config.get('obfs'), dict):
            config['obfs'] = {}

        if not isinstance(config['obfs'].get(obfsType), dict):
            config['obfs'][obfsType] = {}

        oldValue = config['obfs'][obfsType].get(self.key)
        newValue = self.value()

        if not isinstance(oldValue, int) or newValue != oldValue:
            config['obfs'][obfsType][self.key] = newValue

            return True

        return False

    def factoryToInput(self, config: ConfigFactory):
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setObfsTypeText(self, text: str):
        obfsType = self._containers[0]

        if isinstance(obfsType, GuiEditorItemTextComboBox):
            obfsType.setText(text)

    def connectActivated(self, func):
        obfsType = self._containers[0]

        if isinstance(obfsType, GuiEditorItemTextComboBox):
            obfsType.connectActivated(func)


class GuiHy2PageObfsEmpty(GuiHy2PageObfsXXX):
    def containerSequence(self):
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
        ]


class GuiHy2PageObfsSalamander(GuiHy2PageObfsXXX):
    def containerSequence(self):
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
            GuiHy2ItemObfsPassword(
                title='obfs-password',
                obfsType='salamander',
                translatable=False,
            ),
        ]


class GuiHy2PageObfsGecko(GuiHy2PageObfsXXX):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.minPacketSizeItem = self._containers[2]
        self.maxPacketSizeItem = self._containers[3]
        self.minPacketSizeItem._input.valueChanged.connect(
            self.handleMinPacketSizeChanged
        )

        self.handleMinPacketSizeChanged(self.minPacketSizeItem.value())

    def containerSequence(self):
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
            GuiHy2ItemObfsPassword(
                title='obfs-password',
                obfsType='gecko',
                translatable=False,
            ),
            GuiHy2ItemObfsPacketSize(
                title='minPacketSize',
                key='minPacketSize',
                default=512,
                translatable=False,
            ),
            GuiHy2ItemObfsPacketSize(
                title='maxPacketSize',
                key='maxPacketSize',
                default=1200,
                translatable=False,
            ),
        ]

    def handleMinPacketSizeChanged(self, value: int):
        self.maxPacketSizeItem._input.setMinimum(value)

        if self.maxPacketSizeItem.value() < value:
            self.maxPacketSizeItem.setValue(value)


class GuiHy2ObfsPageStackedWidget(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._pages = [
            GuiHy2PageObfsEmpty(),
            GuiHy2PageObfsSalamander(),
            GuiHy2PageObfsGecko(),
        ]

        for page in self._pages:
            self.addWidget(page)

    def page(self, index: int) -> GuiHy2PageObfsXXX:
        return self._pages[index]

    def connectActivated(self, func):
        for page in self._pages:
            page.connectActivated(func)


class GuiHy2ItemTLSTextInput(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigFactory) -> bool:
        newValue = self.text()

        if newValue == '':
            tls = config.get('tls')

            if isinstance(tls, dict):
                if len(tls) > 0:
                    if tls.get(self.key) is not None:
                        oldValue = tls[self.key]

                        tls.pop(self.key, None)

                        if not isinstance(oldValue, str) or oldValue != '':
                            modified = True
                        else:
                            # Modified silently
                            modified = False
                    else:
                        modified = False

                    # TODO: Future extension
                    anyValid = any(
                        tls.get(key, '')
                        for key in ['sni', 'insecure', 'pinSHA256', 'ca']
                    )

                    if not anyValid:
                        config.pop('tls', None)

                        return True
                    else:
                        return modified
                else:
                    config.pop('tls', None)

                    # Modified silently
                    return False
            else:
                config.pop('tls', None)

                # Modified silently
                return False
        else:
            if not isinstance(config.get('tls'), dict):
                config['tls'] = {}

            oldValue = config['tls'].get(self.key, '')

            if not isinstance(oldValue, str) or newValue != oldValue:
                config['tls'][self.key] = newValue

                return True
            else:
                return False

    def factoryToInput(self, config: ConfigFactory):
        try:
            value = config['tls'][self.key]
        except Exception:
            # Any non-exit exceptions

            value = ''

        self.setText(value)


class GuiHy2ItemTLSInsecure(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        try:
            oldChecked = config['tls']['insecure']
        except Exception:
            # Any non-exit exceptions

            oldChecked = False

        newChecked = self.isChecked()

        if newChecked:
            if not isinstance(config.get('tls'), dict):
                config['tls'] = {}

            if oldChecked is not True:
                config['tls']['insecure'] = True

                return True
            else:
                return False
        else:
            if not isinstance(config.get('tls'), dict):
                config['tls'] = {}

            if oldChecked is not False:
                config['tls']['insecure'] = False

                return True
            else:
                return False

    def factoryToInput(self, config: ConfigFactory):
        try:
            checked = config['tls']['insecure']
        except Exception:
            # Any non-exit exceptions

            checked = False

        if not isinstance(checked, bool):
            checked = False

        self.setChecked(checked)


class GuiHy2GroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiHy2ItemBasicServer(title=_('Server')),
            GuiHy2ItemBasicAuth(title='auth', translatable=False),
            GuiHy2ItemBasicCongestionComboBox(
                title='congestion-type', key='type', translatable=False
            ),
            GuiHy2ItemBasicCongestionComboBox(
                title='congestion-profile', key='bbrProfile', translatable=False
            ),
        ]


class GuiHy2GroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiHy2GroupBoxObfs(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        translatable = kwargs.pop('translatable', False)

        super().__init__('obfs', **kwargs, translatable=translatable)

        self._config = ConfigFactory()

        self._widget = GuiHy2ObfsPageStackedWidget()
        self._widget.connectActivated(self.handleActivated)

        layout = QFormLayout()
        layout.addRow(self._widget)

        self.setLayout(layout)

    def currentIndex(self) -> int:
        return self._widget.currentIndex()

    def setCurrentIndex(self, index: int):
        self._widget.setCurrentIndex(index)

    def page(self, index: int) -> GuiHy2PageObfsXXX:
        return self._widget.page(index)

    def handleActivated(self, index: int):
        page = self.page(index)
        page.factoryToInput(self._config)
        page.setObfsTypeText(HY2_OBFS_TYPES[index])

        self.setCurrentIndex(index)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        oldObfs = config.get('obfs')
        oldObfsType = ''

        if isinstance(oldObfs, dict):
            oldObfsType = oldObfs.get('type', '')

        newObfsType = HY2_OBFS_TYPES[self.currentIndex()]

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

        for obfsType in HY2_OBFS_TYPES:
            if obfsType and obfsType != newObfsType:
                config['obfs'].pop(obfsType, None)

        modified |= self.page(self.currentIndex()).inputToFactory(config)

        return modified

    def factoryToInput(self, config: ConfigFactory):
        self._config = config

        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        if not isinstance(obfsType, str) or obfsType not in HY2_OBFS_TYPES:
            obfsType = ''

        index = HY2_OBFS_TYPES.index(obfsType)

        self.page(index).factoryToInput(config)
        self.page(index).setObfsTypeText(obfsType)
        self.setCurrentIndex(index)


class GuiHy2GroupBoxTLS(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__('TLS', **kwargs)

        self.translatable = False

    def containerSequence(self):
        return [
            GuiHy2ItemTLSTextInput(title='sni', key='sni', translatable=False),
            GuiHy2ItemTLSTextInput(
                title='pinSHA256', key='pinSHA256', translatable=False
            ),
            GuiHy2ItemTLSTextInput(title='ca', key='ca', translatable=False),
            GuiHy2ItemTLSInsecure(title='insecure', translatable=False),
        ]


class GuiHy2ProjectWebsiteURL(AppQLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        self.setText(
            '<html><head/><body><p>'
            '<a href=\"https://v2.hysteria.network/\">'
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


class GuiHy2GroupBoxOther(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Other'), **kwargs)

        self._website = GuiHy2ProjectWebsiteURL()

        layout = QFormLayout()
        layout.addRow(self._website)

        self.setLayout(layout)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        return False

    def factoryToInput(self, config: ConfigFactory):
        pass


class GuiHysteria2(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Hysteria2.value)

    @functools.lru_cache(None)
    def groupBoxSequence(self):
        return [
            GuiHy2GroupBoxBasic(),
            GuiHy2GroupBoxProxy(),
            GuiHy2GroupBoxObfs(),
            GuiHy2GroupBoxTLS(),
            # GuiHy2GroupBoxOther(),
        ]
