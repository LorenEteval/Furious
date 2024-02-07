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

from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtWidgets import *

import os
import shutil
import logging
import functools
import darkdetect

__all__ = ['XrayAssetViewerQListWidget']

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)


class AssetExistsMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


needTrans(
    'Delete',
    'Import',
    'Asset file already exists. Overwrite?',
    'Error import asset file',
    'Import asset file success',
)


class XrayAssetViewerQListWidget(SupportThemeChangedCallback, AppQListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setSelectionBehavior(AppQListWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(AppQListWidget.SelectionMode.ExtendedSelection)
        self.setIconSize(QtCore.QSize(64, 64))

        if PLATFORM == 'Linux' and getUbuntuRelease() == '20.04':
            self.initialTheme = darkdetect.theme()
        else:
            self.initialTheme = None

        self.flushItem()

        logger.info(f'Xray-core asset dir is \'{XRAY_ASSET_DIR}\'')

        contextMenuActions = [
            AppQAction(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
            ),
        ]

        self.contextMenu = AppQMenu(*contextMenuActions)

        # Add actions to self in order to activate shortcuts
        self.addActions(self.contextMenu.actions())

        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def flushItemByTheme(self, theme: str):
        self.clear()

        for filename in os.listdir(XRAY_ASSET_DIR):
            if os.path.isfile(XRAY_ASSET_DIR / filename):
                item = QListWidgetItem(filename)

                if AppSettings.isStateON_('DarkMode'):
                    # Custom dark mode
                    item.setIcon(bootstrapIconWhite('file-earmark.svg'))
                else:
                    if theme == 'Dark':
                        if PLATFORM == 'Windows':
                            # Windows. Always use black icon
                            item.setIcon(bootstrapIcon('file-earmark.svg'))
                        else:
                            item.setIcon(bootstrapIconWhite('file-earmark.svg'))
                    else:
                        item.setIcon(bootstrapIcon('file-earmark.svg'))

                self.addItem(item)

    def flushItem(self):
        if PLATFORM == 'Linux' and getUbuntuRelease() == '20.04':
            assert self.initialTheme is not None

            # Ubuntu 20.04. Flush by initial theme(Ubuntu 20.04 theme changes bug)
            self.flushItemByTheme(self.initialTheme)
        else:
            self.flushItemByTheme(darkdetect.theme())

    def appendNewItem(self, filename: str):
        basename = os.path.basename(filename)

        if os.path.isfile(XRAY_ASSET_DIR / basename):
            mbox = AssetExistsMBox(icon=AppQMessageBox.Icon.Question)
            mbox.setWindowTitle(_('Import'))
            mbox.setText(_('Asset file already exists. Overwrite?'))
            mbox.setInformativeText(basename)

            if mbox.exec() == PySide6LegacyEnumValueWrapper(
                AppQMessageBox.StandardButton.No
            ):
                # Do not overwrite
                return

        try:
            shutil.copy(filename, XRAY_ASSET_DIR)
        except shutil.SameFileError:
            # Same file imported. Do nothing
            pass
        except Exception as ex:
            # Any non-exit exception

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
            mbox.setWindowTitle(_('Import'))
            mbox.setText(_('Error import asset file'))
            mbox.setInformativeText(str(ex))

            # Show the MessageBox and wait for user to close it
            mbox.exec()
        else:
            self.flushItem()

            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
            mbox.setWindowTitle(_('Import'))
            mbox.setText(_('Import asset file success'))

            # Show the MessageBox and wait for user to close it
            mbox.exec()

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected
            return

        mbox = QuestionDeleteMBox(icon=AppQMessageBox.Icon.Question)
        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = f'{self.item(indexes[0]).text()}'
        mbox.setText(mbox.customText())

        if mbox.exec() == PySide6LegacyEnumValueWrapper(
            AppQMessageBox.StandardButton.No
        ):
            # Do not delete
            return

        for index in indexes:
            os.remove(XRAY_ASSET_DIR / self.item(index).text())

        self.flushItem()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)

    def themeChangedCallback(self, theme):
        if PLATFORM == 'Linux' and getUbuntuRelease() == '20.04':
            # Ubuntu 20.04 system dark theme does not
            # change menu color. Do nothing
            pass
        else:
            self.flushItemByTheme(theme)
