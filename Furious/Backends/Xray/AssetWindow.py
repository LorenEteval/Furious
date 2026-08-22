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

"""Provide the application window for Xray asset viewer window."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Backends.Xray.AssetListView import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging

__all__ = ['XrayAssetWindow']

logger = logging.getLogger(__name__)


class XrayAssetWindow(AppQMainWindow):
    """Present the Xray asset viewer window."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(380, int(380 * GOLDEN_RATIO))

    def __init__(self, *args, **kwargs):
        """Initialize the Xray asset window."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Xray-core Asset File'))

        centralWidget = QWidget(parent=self)

        self.xrayAssetListView = XrayAssetListView(parent=centralWidget)

        if versionToValue(PYSIDE6_VERSION) <= versionToValue('6.1.3'):
            openAssetDirectoryActions = []
        else:
            # openUrl will crash on PySide6 6.1.3, probably a Qt bug
            openAssetDirectoryActions = [
                AppQAction(
                    _('Open Asset Directory'),
                    icon=bootstrapIcon('folder2-open.svg'),
                    callback=lambda: self.openAssetDirectory(),
                ),
                AppQSeparator(),
            ]

        self.fileMenu = AppQMenu(
            AppQAction(
                _('Refresh'),
                callback=lambda: self.flushItem(),
            ),
            AppQSeparator(),
            *openAssetDirectoryActions,
            AppQAction(
                _('Import From File...'),
                callback=lambda: self.appendNewItem(),
            ),
            title=_('File'),
            parent=self,
        )

        self.fileButton = AppQMenuPushButton(
            _('File'),
            icon=bootstrapIcon('file-earmark.svg'),
            popupMenu=self.fileMenu,
        )

        self.deleteButton = AppQPushButton(
            _('Delete'),
            icon=bootstrapIcon('trash.svg'),
        )
        self.deleteButton.clicked.connect(self.deleteSelectedItem)

        self.closeWindowButton = AppQPushButton(
            _('Close Window'),
            icon=bootstrapIcon('window-x.svg'),
        )
        self.closeWindowButton.clicked.connect(self.close)

        actionLayout = QHBoxLayout()
        actionLayout.setContentsMargins(0, 0, 0, 0)
        actionLayout.setSpacing(8)
        actionLayout.addWidget(self.fileButton)
        actionLayout.addWidget(self.deleteButton)
        actionLayout.addStretch(1)
        actionLayout.addWidget(self.closeWindowButton)

        contentLayout = QVBoxLayout(centralWidget)
        contentLayout.setContentsMargins(10, 10, 10, 8)
        contentLayout.setSpacing(10)
        contentLayout.addLayout(actionLayout)
        contentLayout.addWidget(self.xrayAssetListView, 1)

        self.setCentralWidget(centralWidget)
        self.menuBar().hide()

    def flushItem(self):
        """Refresh item."""
        self.xrayAssetListView.flushItem()

    def deleteSelectedItem(self):
        self.xrayAssetListView.deleteSelectedItem()

    @staticmethod
    def openAssetDirectory():
        """Open asset directory."""
        if QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(XRAY_ASSET_DIR)):
            logger.info(f'open Xray-core asset dir success')
        else:
            logger.error(f'open Xray-core asset dir failed')

    def appendNewItem(self):
        """Append new item."""
        filename, selectedFilter = QFileDialog.getOpenFileName(
            None, _('Import File'), filter=_('All files (*)')
        )

        if filename:
            self.xrayAssetListView.appendNewItem(filename)
