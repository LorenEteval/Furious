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
from Furious.Library import *
from Furious.Utility import *
from Furious.Widget.XrayAssetViewerQListWidget import *

from PySide6.QtGui import *
from PySide6.QtWidgets import *

import logging
import functools

__all__ = ['XrayAssetViewerWindow']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Xray-core Asset File',
    'Refresh',
    'Open Asset Directory',
    'Import From File...',
    'Exit',
    'File',
    'Import File',
    'All files (*)',
)


class XrayAssetViewerWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Xray-core Asset File'))

        self.xrayAssetViewerWidget = XrayAssetViewerQListWidget(parent=self)
        self.setCentralWidget(self.xrayAssetViewerWidget)

        if versionToValue(PYSIDE6_VERSION) <= versionToValue('6.1.3'):
            openAssetDirectoryActions = [None]
        else:
            # openUrl will crash on PySide6 6.1.3, probably a Qt bug
            openAssetDirectoryActions = [
                AppQAction(
                    _('Open Asset Directory'),
                    callback=lambda: self.openAssetDirectory(),
                    shortcut=QtCore.QKeyCombination(
                        QtCore.Qt.KeyboardModifier.ControlModifier,
                        QtCore.Qt.Key.Key_O,
                    ),
                ),
            ]

        self.fileMenu = AppQMenu(
            AppQAction(
                _('Refresh'),
                callback=lambda: self.flushItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_R,
                ),
            ),
            AppQSeperator(),
            *openAssetDirectoryActions,
            AppQAction(
                _('Import From File...'),
                callback=lambda: self.appendNewItem(),
            ),
            AppQSeperator(),
            AppQAction(
                _('Exit'),
                callback=lambda: self.hide(),
            ),
            title=_('File'),
            parent=self.menuBar(),
        )

        self.menuBar().addMenu(self.fileMenu)

    def setWidthAndHeight(self):
        self.setGeometry(100, 100, 360, 360 * GOLDEN_RATIO)

    def flushItem(self):
        self.xrayAssetViewerWidget.flushItem()

    @staticmethod
    def openAssetDirectory():
        if QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(XRAY_ASSET_DIR)):
            logger.info(f'open Xray-core asset dir success')
        else:
            logger.error(f'open Xray-core asset dir failed')

    def appendNewItem(self):
        filename, selectedFilter = QFileDialog.getOpenFileName(
            None, _('Import File'), filter=_('All files (*)')
        )

        if filename:
            self.xrayAssetViewerWidget.appendNewItem(filename)
