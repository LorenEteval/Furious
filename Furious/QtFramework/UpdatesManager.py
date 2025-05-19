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
from Furious.QtFramework.DynamicTranslate import gettext as _
from Furious.QtFramework.WebGETManager import *
from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtNetwork import *

from typing import Union, Callable

import logging
import functools

__all__ = ['UpdatesManager']

logger = logging.getLogger(__name__)


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


class UpdatesManager(WebGETManager):
    API_URL = (
        f'https://api.github.com/repos/'
        f'{APPLICATION_REPO_OWNER_NAME}/{APPLICATION_REPO_NAME}/releases/latest'
    )

    def __init__(self, parent=None, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'check for updates')

        super().__init__(parent, actionMessage=actionMessage)

    def successCallback(self, networkReply, **kwargs):
        showMessageBox = kwargs.pop('showMessageBox', True)
        hasNewVersionCallback = kwargs.pop('hasNewVersionCallback', None)

        data = networkReply.readAll().data()

        try:
            info = UJSONEncoder.decode(data)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'bad network reply while checking for updates. {ex}')

            if showMessageBox:
                self.showErrorMessageBox()
        else:
            newVersion = info['tag_name']

            if versionToValue(newVersion) > versionToValue(APPLICATION_VERSION):

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

                if callable(hasNewVersionCallback):
                    hasNewVersionCallback(newVersion)

                if showMessageBox:
                    mbox = QuestionUpdateMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.version = newVersion
                    mbox.setText(mbox.customText())
                    mbox.setInformativeText(_('Go to download page?'))
                    mbox.finished.connect(functools.partial(handleResultCode))

                    # Show the MessageBox asynchronously
                    mbox.open()
            else:
                if showMessageBox:
                    mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
                    mbox.setWindowTitle(_(APPLICATION_NAME))
                    mbox.setText(_(f'{APPLICATION_NAME} is already the latest version'))

                    # Show the MessageBox asynchronously
                    mbox.open()

    @staticmethod
    def showErrorMessageBox():
        mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
        mbox.setWindowTitle(_(APPLICATION_NAME))
        mbox.setText(_('Check for updates failed'))

        # Show the MessageBox asynchronously
        mbox.open()

    def failureCallback(self, networkReply, **kwargs):
        showMessageBox = kwargs.pop('showMessageBox', True)

        if showMessageBox:
            self.showErrorMessageBox()

    def checkForUpdates(
        self,
        showMessageBox=True,
        hasNewVersionCallback: Callable[[str], None] = None,
    ):
        self.webGET(
            self.API_URL,
            showMessageBox=showMessageBox,
            hasNewVersionCallback=hasNewVersionCallback,
        )
