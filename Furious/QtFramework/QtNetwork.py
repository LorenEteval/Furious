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

from Furious.Utility import *

from PySide6.QtNetwork import *

from typing import Union

__all__ = ['AppQNetworkAccessManager']


class AppQNetworkAccessManager(QNetworkAccessManager):
    def __init__(self, parent=None):
        super().__init__(parent)

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
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
