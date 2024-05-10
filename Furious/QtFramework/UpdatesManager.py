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

from Furious.QtFramework.QtNetwork import *
from Furious.QtFramework.QtWidgets import *
from Furious.QtFramework.DynamicTranslate import gettext as _, needTransFn
from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtNetwork import *

from typing import Union

import logging
import operator
import functools

__all__ = ['UpdatesManager']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans('New version available')


class QuestionUpdateMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.version = '0.0.0'
        self.setWindowTitle(_(APPLICATION_NAME))
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def customText(self):
        return _('New version available') + f': {self.version}'

    def retranslate(self):
        self.setText(self.customText())
        self.setWindowTitle(_(self.windowTitle()))
        self.setInformativeText(_(self.informativeText()))

        # Ignore button text

        self.moveToCenter()


needTrans(
    'Check for updates failed',
    'Go to download page?',
    f'{APPLICATION_NAME} is already the latest version',
)


class UpdatesManager(AppQNetworkAccessManager):
    API_URL = (
        f'https://api.github.com/repos/'
        f'{APPLICATION_REPO_OWNER_NAME}/{APPLICATION_REPO_NAME}/releases/latest'
    )

    def __init__(self, parent=None):
        super().__init__(parent)

    def handleFinishedByNetworkReply(self, networkReply):
        assert isinstance(networkReply, QNetworkReply)

        if networkReply.error() != QNetworkReply.NetworkError.NoError:
            logger.error(f'check for updates failed. {networkReply.errorString()}')

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_(APPLICATION_NAME))
            mbox.setText(_('Check for updates failed'))

            # Show the MessageBox asynchronously
            mbox.open()
        else:
            logger.info('check for updates success')

            # Unchecked?
            info = UJSONEncoder.decode(networkReply.readAll().data())

            if versionToValue(info['tag_name']) > versionToValue(APPLICATION_VERSION):

                def handleResultCode(code):
                    if code == PySide6LegacyEnumValueWrapper(
                        AppQMessageBox.StandardButton.Yes
                    ):
                        if QDesktopServices.openUrl(QtCore.QUrl(info['html_url'])):
                            logger.info('open download page success')
                        else:
                            logger.error('open download page failed')
                    else:
                        # Do nothing
                        pass

                mbox = QuestionUpdateMBox(icon=AppQMessageBox.Icon.Information)
                mbox.version = info['tag_name']
                mbox.setText(mbox.customText())
                mbox.setInformativeText(_('Go to download page?'))
                mbox.finished.connect(functools.partial(handleResultCode))

                # dummy ref
                setattr(self, '_questionUpdateMBox', mbox)

                # Show the MessageBox asynchronously
                mbox.open()
            else:
                mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
                mbox.setWindowTitle(_(APPLICATION_NAME))
                mbox.setText(_(f'{APPLICATION_NAME} is already the latest version'))

                # Show the MessageBox asynchronously
                mbox.open()

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        useProxy = super().configureHttpProxy(httpProxy)

        if useProxy:
            logger.info(f'check for updates uses proxy server {httpProxy}')
        else:
            logger.info(f'check for updates uses no proxy')

        return useProxy

    def checkForUpdates(self):
        networkReply = self.get(QNetworkRequest(QtCore.QUrl(self.API_URL)))
        networkReply.finished.connect(
            functools.partial(
                self.handleFinishedByNetworkReply,
                networkReply,
            )
        )
