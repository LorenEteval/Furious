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

"""Provide the application window for QR code window."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import io
import functools
import pyqrcode

__all__ = ['QRCodeWindow']

_OpenQRCodeWindows = {}


def _releaseOpenQRCodeWindow(key, *_args):
    """Release an exported QR-code window after Qt destroys it."""
    _OpenQRCodeWindows.pop(key, None)


class QRCodeWindow(AppQMainWindow):
    """Present the QR code window."""

    def __init__(self, *args, **kwargs):
        """Initialize the QRCodeWindow."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setFixedSize(640, 640)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._lifetimeKey = id(self)
        self.destroyed.connect(
            functools.partial(_releaseOpenQRCodeWindow, self._lifetimeKey)
        )

        self.tabWidget = QTabWidget(self)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.handleTabCloseRequested)

        self.setCentralWidget(self.tabWidget)

    def show(self):
        """Show and retain this unparented window until Qt destroys it."""
        _OpenQRCodeWindows[self._lifetimeKey] = self

        try:
            return super().show()
        except Exception:
            _releaseOpenQRCodeWindow(self._lifetimeKey)

            raise

    def tabCount(self) -> int:
        """Return the tab count value used by the QR code window."""
        return self.tabWidget.count()

    def initTabByIndex(self, indexes):
        """Handle init tab by index for the QR code window."""
        self.tabWidget.clear()

        for index in indexes:
            qrdata = io.BytesIO()

            config = Storage.UserServers()[index]

            try:
                uri = config.toURI()
            except Exception:
                # Any non-exit exceptions

                uri = ''

            if uri:
                qrcode = pyqrcode.create(uri)
                qrcode.png(qrdata, scale=5)

                pixmap = QPixmap()
                pixmap.loadFromData(qrdata.getvalue(), 'PNG')

                widget = QLabel(parent=self.tabWidget)
                widget.setPixmap(pixmap)

                self.tabWidget.addTab(
                    widget, f'{index + 1} - ' + config.getExtras('remark')
                )

    @QtCore.Slot(int)
    def handleTabCloseRequested(self, index):
        """Handle tab close requested."""
        self.tabWidget.removeTab(index)

        if self.tabWidget.count() == 0:
            self.close()
