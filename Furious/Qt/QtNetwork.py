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

"""Provide Qt support for qt network."""

from __future__ import annotations

from Furious.Frozenlib import *

from PySide6.QtNetwork import *

from typing import Union

import weakref
import functools

__all__ = ['AppQNetworkAccessManager']


class AppQNetworkAccessManager(QNetworkAccessManager):
    """Coordinate app q network access operations."""

    def __init__(self, parent=None):
        """Initialize the AppQNetworkAccessManager."""
        super().__init__(parent)

    @staticmethod
    def _releaseReplyContext(contexts, replyReference, *_args):
        """Drop plain request state even when native deletion skips finished."""
        reply = replyReference()

        if reply is not None:
            contexts.pop(reply, None)

    def _trackReplyContext(self, reply, contexts, context):
        """Retain request state until completion or exact reply destruction."""
        contexts[reply] = context

        # Native manager teardown also destroys its replies. Capture storage and
        # a weak key, never a bound QObject method or the destroyed signal's
        # temporary wrapper. Completion may already have removed this entry.
        reply.destroyed.connect(
            functools.partial(
                AppQNetworkAccessManager._releaseReplyContext,
                contexts,
                weakref.ref(reply),
            )
        )

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        """Configure HTTP proxy."""
        if httpProxy is None:
            useProxy = False
        else:
            try:
                proxyHost, proxyPort = parseHostPort(httpProxy)

                self.setProxy(
                    QNetworkProxy(
                        QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort)
                    )
                )
            except Exception:
                # Any non-exit exceptions

                useProxy = False
            else:
                useProxy = True

        if not useProxy:
            self.setProxy(QNetworkProxy.ProxyType.NoProxy)

        return useProxy
