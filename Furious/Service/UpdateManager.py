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

"""Provide Qt support for updates manager."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Models import *
from Furious.Qt.QtWidgets import *
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Qt.HttpGetManager import *

from PySide6 import QtCore
from PySide6.QtGui import *

from typing import Callable

import logging

__all__ = ['UpdateManager']

logger = logging.getLogger(__name__)


class MBoxQuestionUpdate(AppQMessageBox):
    """Represent m box question update."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxQuestionUpdate."""
        super().__init__(*args, **kwargs)

        self.version = '0.0.0'
        self.setWindowTitle(_(APPLICATION_NAME))
        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def customText(self):
        """Return the user-facing message text for the m box question update."""
        return _('New version available') + f': {self.version}'

    def retranslate(self):
        """Refresh translated text for the m box question update."""
        self.setText(self.customText())
        self.setWindowTitle(_(self.windowTitle()))
        self.setInformativeText(_(self.informativeText()))

        # Ignore button text

        self.moveToCenter()


class UpdateManager(HttpGetManager):
    """Coordinate updates operations."""

    API_URL = (
        f'https://api.github.com/repos/'
        f'{APPLICATION_REPO_OWNER_NAME}/{APPLICATION_REPO_NAME}/releases/latest'
    )

    def __init__(self, parent=None, **kwargs):
        """Initialize the update manager."""
        actionMessage = kwargs.pop('actionMessage', 'check for updates')

        super().__init__(parent, actionMessage=actionMessage)

    @staticmethod
    def showErrorMessageBox(parent=None):
        """Show error message box."""
        mbox = AppQMessageBox(parent=parent, icon=AppQMessageBox.Icon.Critical)
        mbox.setWindowTitle(_(APPLICATION_NAME))
        mbox.setText(_('Check for updates failed'))

        # Show the MessageBox asynchronously
        mbox.open()

    @staticmethod
    def _releaseInformation(data):
        """Return validated release fields from one GitHub API response."""
        info = UJSONEncoder.decode(data)

        if not isinstance(info, dict):
            raise ValueError('release response is not an object')

        tagName, htmlURL = (
            info.get('tag_name'),
            info.get('html_url'),
        )

        if not isinstance(tagName, str) or not tagName.strip():
            raise ValueError('release response has no valid tag_name')

        if not isinstance(htmlURL, str) or not htmlURL.strip():
            raise ValueError('release response has no valid html_url')

        parsedURL = QtCore.QUrl(htmlURL)

        if (
            not parsedURL.isValid()
            or parsedURL.scheme().casefold() != 'https'
            or parsedURL.host().casefold() != 'github.com'
        ):
            raise ValueError('release response has an untrusted html_url')

        # Validate before the value reaches the version comparison helper.
        if not isinstance(versionToValue(tagName), int):
            raise ValueError('release response has an invalid tag_name')

        return tagName, parsedURL

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        parent, showMessageBox, hasNewVersionCallback = (
            kwargs.pop('parent', None),
            kwargs.pop('showMessageBox', True),
            kwargs.pop('hasNewVersionCallback', None),
        )

        data = networkReply.readAll().data()

        try:
            tagName, htmlURL = self._releaseInformation(data)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'bad network reply while checking for updates. {ex}')

            if showMessageBox:
                self.showErrorMessageBox(parent)
        else:
            if versionToValue(tagName) > versionToValue(APPLICATION_VERSION):

                def handleResultCode(code):
                    """Handle result code."""
                    if code == PySide6Legacy.enumValueWrapper(
                        AppQMessageBox.StandardButton.Yes
                    ):
                        if QDesktopServices.openUrl(htmlURL):
                            logger.info('open download page success')
                        else:
                            logger.error('open download page failed')
                    else:
                        # Do nothing
                        pass

                if callable(hasNewVersionCallback):
                    hasNewVersionCallback(tagName)

                if showMessageBox:
                    mbox = MBoxQuestionUpdate(
                        parent=parent,
                        icon=AppQMessageBox.Icon.Information,
                    )
                    mbox.version = tagName
                    mbox.setText(mbox.customText())
                    mbox.setInformativeText(_('Go to download page?'))
                    mbox.finished.connect(handleResultCode)

                    # Show the MessageBox asynchronously
                    mbox.open()
            else:
                if showMessageBox:
                    mbox = AppQMessageBox(
                        parent=parent,
                        icon=AppQMessageBox.Icon.Information,
                    )
                    mbox.setWindowTitle(_(APPLICATION_NAME))
                    mbox.setText(_(f'{APPLICATION_NAME} is already the latest version'))

                    # Show the MessageBox asynchronously
                    mbox.open()

    def failureCallback(self, networkReply, **kwargs):
        """Handle a failed network operation."""
        parent, showMessageBox = (
            kwargs.pop('parent', None),
            kwargs.pop('showMessageBox', True),
        )

        if showMessageBox:
            self.showErrorMessageBox(parent)

    def checkForUpdates(
        self,
        showMessageBox=True,
        hasNewVersionCallback: Callable[[str], None] = None,
        **kwargs,
    ):
        """Check for updates."""
        self.webGET(
            self.API_URL,
            showMessageBox=showMessageBox,
            hasNewVersionCallback=hasNewVersionCallback,
            **kwargs,
        )
