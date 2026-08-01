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

"""Provide Qt support for web get manager."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.QtNetwork import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

from typing import Union

import logging
import functools

__all__ = ['WebGETManager']

logger = logging.getLogger(__name__)


class WebGETManager(AppQNetworkAccessManager):
    """Coordinate web get operations."""

    def __init__(self, parent=None, actionMessage='web GET', **kwargs):
        """Initialize the WebGETManager."""
        super().__init__(parent)

        self.actionMessage = actionMessage

        self.mustCallOnce = kwargs.pop('mustCallOnce', True)
        self.mustCalled = False

    def successCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle a successful network operation."""
        pass

    def hasDataCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle newly available network response data."""
        pass

    def failureCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle a failed network operation."""
        pass

    def mustCall(self, **kwargs):
        """Perform the required completion hook."""
        pass

    def must(self, **kwargs):
        """Run the required completion hook according to its call policy."""

        def call():
            """Invoke the registered completion callback."""
            try:
                self.mustCall(**kwargs)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'error calling must(): {ex}')
            finally:
                self.mustCalled = True

        if not self.mustCallOnce:
            call()
        elif not self.mustCalled:
            call()

    def handleReadyReadByNetworkReply(self, networkReply: QNetworkReply, **kwargs):
        """Handle ready read by network reply."""
        self.hasDataCallback(networkReply, **kwargs)

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
            self.must(**kwargs)

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        """Configure HTTP proxy."""
        useProxy = super().configureHttpProxy(httpProxy)

        if useProxy:
            logger.info(f'{self.actionMessage} uses proxy server {httpProxy}')
        else:
            logger.info(f'{self.actionMessage} uses no proxy')

        return useProxy

    def webGET(self, request: Union[QNetworkRequest, str], **kwargs) -> QNetworkReply:
        """Return the web get value used by the web get manager."""
        if isinstance(request, QNetworkRequest):
            networkReply = self.get(request)
        else:
            networkReply = self.get(QNetworkRequest(QtCore.QUrl(request)))

        networkReply.readyRead.connect(
            functools.partial(
                self.handleReadyReadByNetworkReply,
                networkReply,
                **kwargs,
            )
        )
        networkReply.finished.connect(
            functools.partial(
                self.handleFinishedByNetworkReply,
                networkReply,
                **kwargs,
            )
        )

        return networkReply
