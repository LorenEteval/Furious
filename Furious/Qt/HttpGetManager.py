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

"""Provide reusable Qt support for HTTP GET workflows."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.QtNetwork import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

from typing import Union

import logging

__all__ = ['HttpGetManager']

logger = logging.getLogger(__name__)


class HttpGetManager(AppQNetworkAccessManager):
    """Coordinate HTTP GET operations and their completion lifecycle."""

    def __init__(self, parent=None, actionMessage='web GET', **kwargs):
        """Initialize the HttpGetManager."""
        super().__init__(parent)

        self.transferTimeout = max(int(kwargs.pop('transferTimeout', 60_000)), 1)
        self.actionMessage = actionMessage

        self.completionRunsOnce = kwargs.pop('completionRunsOnce', True)
        self.completionHasRun = False
        self._replyContexts = {}

    def successCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle a successful network operation."""
        pass

    def hasDataCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle newly available network response data."""
        pass

    def failureCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle a failed network operation."""
        pass

    def completionCallback(self, **kwargs):
        """Perform the required completion hook."""
        pass

    def runCompletionCallback(self, **kwargs):
        """Run the completion callback according to its call policy."""

        def call():
            """Invoke the registered completion callback."""
            try:
                self.completionCallback(**kwargs)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'error calling completion callback: {ex}')
            finally:
                self.completionHasRun = True

        if not self.completionRunsOnce:
            call()
        elif not self.completionHasRun:
            call()

    def handleReadyReadByNetworkReply(self, networkReply: QNetworkReply, **kwargs):
        """Handle ready read by network reply."""
        self.hasDataCallback(networkReply, **kwargs)

    @QtCore.Slot()
    def _handleReadyRead(self):
        """Dispatch ready-read data without a closure retaining the reply."""
        networkReply = self.sender()

        if isinstance(networkReply, QNetworkReply):
            self.handleReadyReadByNetworkReply(
                networkReply,
                **self._replyContexts.get(networkReply, {}),
            )

    @QtCore.Slot()
    def _handleFinished(self):
        """Dispatch and release one completed network reply."""
        networkReply = self.sender()

        if not isinstance(networkReply, QNetworkReply):
            return

        kwargs = self._replyContexts.pop(networkReply, {})

        self.handleFinishedByNetworkReply(networkReply, **kwargs)

    def handleFinishedByNetworkReply(self, networkReply: QNetworkReply, **kwargs):
        """Handle finished by network reply."""
        try:
            if not isinstance(networkReply, QNetworkReply):
                # Some PySide6 version does not have networkReply as
                # QNetworkReply instance, so assertion is not used here
                logger.error(
                    f'QNetworkReply error in PySide6 {PYSIDE6_VERSION} version'
                )

                return

            logActionMessage = kwargs.pop('logActionMessage', True)

            if networkReply.error() != QNetworkReply.NetworkError.NoError:
                if logActionMessage:
                    logger.error(
                        f'{self.actionMessage} failed. {networkReply.errorString()}'
                    )

                self.failureCallback(networkReply, **kwargs)
            else:
                if logActionMessage:
                    logger.info(f'{self.actionMessage} success')

                self.successCallback(networkReply, **kwargs)
        finally:
            try:
                self.runCompletionCallback(**kwargs)
            finally:
                # QNetworkAccessManager owns replies by default and does not
                # remove completed children automatically.  All response data
                # has been consumed by this point.  The shared slots above use
                # sender(), so no per-request closure retains this wrapper.
                networkReply.deleteLater()

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        """Configure HTTP proxy."""
        useProxy = super().configureHttpProxy(httpProxy)

        if useProxy:
            logger.info(f'{self.actionMessage} uses proxy server {httpProxy}')
        else:
            logger.info(f'{self.actionMessage} uses no proxy')

        return useProxy

    def webGET(self, request: Union[QNetworkRequest, str], **kwargs) -> QNetworkReply:
        """Start an HTTP GET request managed by this instance."""
        if isinstance(request, QNetworkRequest):
            request = QNetworkRequest(request)
        else:
            request = QNetworkRequest(QtCore.QUrl(request))

        if request.transferTimeout() <= 0:
            request.setTransferTimeout(self.transferTimeout)

        networkReply = self.get(request)

        self._replyContexts[networkReply] = dict(kwargs)

        networkReply.readyRead.connect(self._handleReadyRead)
        networkReply.finished.connect(self._handleFinished)

        return networkReply
