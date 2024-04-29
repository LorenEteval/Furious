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

__all__ = ['GuiHysteria2']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)


class GuiHy2ItemBasicServer(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.get('server', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemBasicAuth(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.get('auth', ''))
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiHy2ItemObfsType(GuiEditorItemTextComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: Only 'salamander' is currently supported by hy2
        self.addItems(['', 'salamander'])

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        # TODO: Only 'salamander' is currently supported by hy2
        if isinstance(obfsType, str) and obfsType != 'salamander':
            self.setText('')
        else:
            self.setText('salamander')


class GuiHy2ItemObfsPassword(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        newObfsPassword = self.text()

        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        # TODO: Only 'salamander' is currently supported by hy2
        if not isinstance(obfsType, str) or obfsType != 'salamander':
            if config.get('obfs') is None:
                return False
            else:
                # Remove obfs field
                config.pop('obfs', None)

                return True

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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            obfsType = config['obfs']['type']
        except Exception:
            # Any non-exit exceptions

            obfsType = ''

        # TODO: Only 'salamander' is currently supported by hy2
        if not isinstance(obfsType, str) or obfsType != 'salamander':
            self.setText('')

            return

        try:
            obfsPassword = config['obfs'][obfsType]['password']
        except Exception:
            # Any non-exit exceptions

            obfsPassword = ''

        self.setText(obfsPassword)


class GuiHy2ItemTLSTextInput(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        key = kwargs.pop('key', '')

        super().__init__(*args, **kwargs)

        self.key = key

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            value = config['tls'][self.key]
        except Exception:
            # Any non-exit exceptions

            value = ''

        self.setText(value)


class GuiHy2ItemTLSInsecure(GuiEditorItemTextCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
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

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            checked = config['tls']['insecure']
        except Exception:
            # Any non-exit exceptions

            checked = False

        if not isinstance(checked, bool):
            checked = False

        self.setChecked(checked)


needTrans(
    'Basic Configuration',
    'Remark',
    'Server',
)


class GuiHy2GroupBoxBasic(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Basic Configuration'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemBasicRemark(title=_('Remark')),
            GuiHy2ItemBasicServer(title=_('Server')),
            GuiHy2ItemBasicAuth(title='auth', translatable=False),
        ]


needTrans('Proxy')


class GuiHy2GroupBoxProxy(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Proxy'), **kwargs)

    def containerSequence(self):
        return [
            GuiEditorItemProxyHttp(title='http', translatable=False),
            GuiEditorItemProxySocks(title='socks', translatable=False),
        ]


class GuiHy2GroupBoxObfs(GuiEditorWidgetQGroupBox):
    def __init__(self, **kwargs):
        super().__init__('obfs', **kwargs)

        self.translatable = False

    def containerSequence(self):
        return [
            GuiHy2ItemObfsType(title='obfs-type', translatable=False),
            GuiHy2ItemObfsPassword(title='obfs-password', translatable=False),
        ]


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


needTrans('Project Website')


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


needTrans('Other')


class GuiHy2GroupBoxOther(GuiEditorItemFactory, AppQGroupBox):
    def __init__(self, **kwargs):
        super().__init__(_('Other'), **kwargs)

        self._website = GuiHy2ProjectWebsiteURL()

        layout = QFormLayout()
        layout.addRow(self._website)

        self.setLayout(layout)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        return False

    def factoryToInput(self, config: ConfigurationFactory):
        pass


class GuiHysteria2(GuiEditorWidgetQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setTabText(Protocol.Hysteria2)

    def groupBoxSequence(self):
        return [
            GuiHy2GroupBoxBasic(),
            GuiHy2GroupBoxProxy(),
            GuiHy2GroupBoxObfs(),
            GuiHy2GroupBoxTLS(),
            # GuiHy2GroupBoxOther(),
        ]
