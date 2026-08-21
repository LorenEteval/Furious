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

"""Provide the model-based Xray asset list view."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import os
import shutil
import logging
import datetime
import functools

__all__ = ['XrayAssetListView']

logger = logging.getLogger(__name__)


class MBoxAssetExists(AppQMessageBox):
    """Represent m box asset exists."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxAssetExists."""
        super().__init__(*args, **kwargs)

        self.setStandardButtons(
            AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
        )

    def retranslate(self):
        """Refresh translated text for the m box asset exists."""
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


class XrayAssetListView(Mixins.ThemeAware, AppQListView):
    """Provide the model-based Xray asset viewer list."""

    def __init__(self, *args, **kwargs):
        """Initialize the Xray asset list view."""
        super().__init__(*args, **kwargs)

        self.assetModel = QStandardItemModel(parent=self)
        self.setModel(self.assetModel)

        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(AppQListView.SelectionBehavior.SelectRows)
        self.setSelectionMode(AppQListView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(AppQListView.EditTrigger.NoEditTriggers)
        self.setIconSize(QtCore.QSize(64, 64))

        if PLATFORM == 'Linux' and SystemRuntime.ubuntuRelease() == '20.04':
            self.initialTheme = APP().theme()
        else:
            self.initialTheme = None

        self.flushItem()

        logger.info(f'Xray-core asset dir is \'{XRAY_ASSET_DIR}\'')

        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)

    def showEvent(self, event):
        """Recalculate item geometry after the view receives its display style."""
        super().showEvent(event)

        self.scheduleDelayedItemsLayout()

    def flushItemByTheme(self, theme: str):
        """Refresh item by theme."""
        self.assetModel.clear()

        maxlen = max(
            len(filename)
            for filename in os.listdir(XRAY_ASSET_DIR)
            if os.path.isfile(XRAY_ASSET_DIR / filename)
        )

        for filename in os.listdir(XRAY_ASSET_DIR):
            if os.path.isfile(XRAY_ASSET_DIR / filename):
                try:
                    # Exception may be raised
                    epoch = os.path.getmtime(XRAY_ASSET_DIR / filename)
                except Exception:
                    # Any non-exit exceptions

                    mdate = ''
                else:
                    mdate = datetime.datetime.fromtimestamp(epoch).strftime(
                        '%Y-%m-%d %H:%M:%S'
                    )

                item = QStandardItem(f'{filename:{maxlen + 5}}{mdate}')
                item.setData(filename, QtCore.Qt.ItemDataRole.UserRole)
                item.setFont(QFont(AppFontName()))

                if APP().usesForcedDarkTheme():
                    # Explicit dark theme
                    item.setIcon(bootstrapIconWhite('file-earmark.svg'))
                else:
                    if theme == 'Dark':
                        if PLATFORM == 'Windows':
                            # Windows
                            if versionToValue(PYSIDE6_VERSION) < versionToValue(
                                '6.7.0'
                            ):
                                # PySide6 < 6.7.0 has no system theme handling on Windows.
                                # Always use black icon
                                item.setIcon(bootstrapIcon('file-earmark.svg'))
                            else:
                                # PySide6 has system theme handling.
                                item.setIcon(bootstrapIconWhite('file-earmark.svg'))
                        else:
                            item.setIcon(bootstrapIconWhite('file-earmark.svg'))
                    else:
                        item.setIcon(bootstrapIcon('file-earmark.svg'))

                self.assetModel.appendRow(item)

    def filenameAt(self, row: int) -> str:
        """Return the filesystem name represented by one model row."""
        item = self.assetModel.item(row)

        if item is None:
            return ''

        return str(item.data(QtCore.Qt.ItemDataRole.UserRole) or '')

    def flushItem(self):
        """Refresh item."""
        if PLATFORM == 'Linux' and SystemRuntime.ubuntuRelease() == '20.04':
            assert self.initialTheme is not None

            # Ubuntu 20.04. Flush by initial theme(Ubuntu 20.04 theme changes bug)
            self.flushItemByTheme(self.initialTheme)
        else:
            self.flushItemByTheme(APP().theme())

    def appendNewItem(self, filename: str):
        """Append new item."""

        def append(_filename):
            """Append an item to the Xray asset list view."""
            try:
                shutil.copy(_filename, XRAY_ASSET_DIR)
            except shutil.SameFileError:
                # Same file imported. Do nothing
                pass
            except Exception as ex:
                # Any non-exit exception

                _mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
                _mbox.setText(_('Error import asset file'))
                _mbox.setInformativeText(str(ex))

                # Show the MessageBox asynchronously
                _mbox.open()
            else:
                self.flushItem()

                _mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
                _mbox.setText(_('Import asset file success'))

                # Show the MessageBox asynchronously
                _mbox.open()

        basename = os.path.basename(filename)

        if os.path.isfile(XRAY_ASSET_DIR / basename):

            def handleResultCode(_filename, code):
                """Handle result code."""
                if code == PySide6Legacy.enumValueWrapper(
                    AppQMessageBox.StandardButton.Yes
                ):
                    append(_filename)
                else:
                    # Do not overwrite
                    pass

            mbox = MBoxAssetExists(icon=AppQMessageBox.Icon.Question)
            mbox.setText(_('Asset file already exists. Overwrite?'))
            mbox.setInformativeText(basename)
            mbox.finished.connect(functools.partial(handleResultCode, filename))

            # Show the MessageBox asynchronously
            mbox.open()
        else:
            append(filename)

    def deleteSelectedItem(self):
        """Delete selected item."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected
            return

        filenames = [self.filenameAt(index) for index in indexes]
        filenames = [filename for filename in filenames if filename]

        if not filenames:
            return

        def handleResultCode(_filenames, code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                for filename in _filenames:
                    os.remove(XRAY_ASSET_DIR / filename)

                self.flushItem()
            else:
                # Do not delete
                pass

        if PLATFORM == 'Windows':
            # Windows
            mbox = MBoxQuestionDelete(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = MBoxQuestionDelete(
                icon=AppQMessageBox.Icon.Question, parent=self.parent()
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(filenames) > 1)
        mbox.possibleRemark = filenames[0]
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, filenames))

        # Show the MessageBox asynchronously
        mbox.open()

    def keyPressEvent(self, event):
        """Handle a key press for the Xray asset viewer list."""
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)

    def themeChangedCallback(self, theme):
        """Update the Xray asset viewer list for a theme change."""
        if PLATFORM == 'Linux' and SystemRuntime.ubuntuRelease() == '20.04':
            # Ubuntu 20.04 system dark theme does not
            # change menu color. Do nothing
            pass
        else:
            self.flushItemByTheme(theme)
