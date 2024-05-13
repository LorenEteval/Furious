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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

import functools

__all__ = ['LogViewerWindow']

needTrans = functools.partial(needTransFn, source=__name__)

needTrans('Unable to save log')


class SaveErrorMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.saveError = ''

    def customText(self):
        if self.saveError:
            return _('Unable to save log') + f'\n\n{self.saveError}'
        else:
            return _('Unable to save log')

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


needTrans(
    'Save File',
    'Text files (*.txt);;All files (*)',
    'Error saving log',
)


def saveAsFile(content: str):
    filename, selectedFilter = QFileDialog.getSaveFileName(
        None, _('Save File'), filter=_('Text files (*.txt);;All files (*)')
    )

    if filename:
        try:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(content)
        except Exception as ex:
            # Any non-exit exceptions

            mbox = SaveErrorMBox(icon=AppQMessageBox.Icon.Critical)
            mbox.saveError = str(ex)
            mbox.setWindowTitle(_('Error saving log'))
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()


needTrans(
    'Log Viewer',
    'Save As...',
    'Exit',
    'File',
    'Copy',
    'Select All',
    'Edit',
    'Zoom In',
    'Zoom Out',
    'View',
)


class LogViewerWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        tabTitle = kwargs.pop('tabTitle', '')
        fontFamily = kwargs.pop('fontFamily', '')
        pointSizeSettingsName = kwargs.pop('pointSizeSettingsName', '')

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Log Viewer'))

        self.textBrowser = DraculaTextBrowser(
            fontFamily=fontFamily,
            pointSizeSettingsName=pointSizeSettingsName,
        )
        self.textBrowser.setLineWrapMode(DraculaTextBrowser.LineWrapMode.NoWrap)

        self.tabWidget = AppQTabWidget()
        self.tabWidget.addTab(self.textBrowser, tabTitle)

        self.setCentralWidget(self.tabWidget)

        self._fileMenu = AppQMenu(
            AppQAction(
                _('Save As...'),
                callback=lambda: saveAsFile(self.textBrowser.toPlainText()),
            ),
            AppQSeperator(),
            AppQAction(
                _('Exit'),
                callback=lambda: self.hide(),
            ),
            title=_('File'),
            parent=self,
        )

        self._editMenu = AppQMenu(
            AppQAction(
                _('Copy'),
                icon=bootstrapIcon('files.svg'),
                callback=lambda: self.textBrowser.copy(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.textBrowser.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            title=_('Edit'),
            parent=self,
        )

        self._viewMenu = AppQMenu(
            AppQAction(
                _('Zoom In'),
                callback=lambda: self.textBrowser.zoomIn(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Plus,
                ),
            ),
            AppQAction(
                _('Zoom Out'),
                callback=lambda: self.textBrowser.zoomOut(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Minus,
                ),
            ),
            title=_('View'),
            parent=self,
        )

        self.menuBar().addMenu(self._fileMenu)
        self.menuBar().addMenu(self._editMenu)
        self.menuBar().addMenu(self._viewMenu)

    def plainText(self) -> str:
        return self.textBrowser.toPlainText()

    def appendLine(self, line: str):
        self.textBrowser.appendLine(line)

    def clear(self):
        self.textBrowser.clear()
