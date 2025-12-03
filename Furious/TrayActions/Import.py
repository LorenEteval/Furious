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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6.QtWidgets import QApplication, QFileDialog

from PIL import Image

from typing import Callable, Union

import os
import mss
import zxingcpp
import logging
import functools

__all__ = [
    'ImportFromFileAction',
    'ImportURIFromClipboardAction',
    'ImportJSONFromClipboardAction',
    'ImportQRCodeOnTheScreenAction',
    'ImportAction',
]

logger = logging.getLogger(__name__)


def showMBoxImportError(clipboard: str):
    mbox = MBoxImportError(icon=AppQMessageBox.Icon.Critical)

    if len(clipboard) > 1000:
        # Limited
        mbox.setText(_('Invalid data'))
        mbox.setInformativeText('')
    else:
        mbox.setText(_('Invalid data. The content of the clipboard is:'))
        mbox.setInformativeText(clipboard)

    # Show the MessageBox asynchronously
    mbox.open()


def importURIFromClipboard(clipboard: str):
    factory = configFactoryFromAny(clipboard)

    if not factory.isValid():
        showMBoxImportError(clipboard)
    else:
        APP().mainWindow.appendNewItemByFactory(factory)

        mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
        mbox.remark = factory.getExtras('remark')
        mbox.setText(mbox.customText())

        # Show the MessageBox asynchronously
        mbox.open()


def importURIs(*uris, failureCallback: Union[Callable[[], None], None] = None):
    imported = list()
    rowIndex = len(Storage.UserServers())

    for uri in uris:
        factory = configFactoryFromAny(uri)

        if factory.isValid():
            APP().mainWindow.appendNewItemByFactory(factory)

            imported.append(factory.getExtras('remark'))

    if len(imported) == 0:
        if callable(failureCallback):
            failureCallback()
    else:
        if len(imported) == 1:
            # Fall back to single
            mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
            mbox.remark = imported[0]
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()
        else:
            mbox = MBoxImportMultiSuccess(icon=AppQMessageBox.Icon.Information)
            mbox.imported = imported
            mbox.rowIndex = rowIndex
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()


class MBoxImportError(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Import'))

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxImportMultiSuccess(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.imported = list()
        self.rowIndex = 0

        self.setWindowTitle(_('Import'))
        self.setIcon(AppQMessageBox.Icon.Information)

    def customText(self):
        text = (
            _('Import share link success')
            + '\n\n'
            + '\n'.join(
                list(
                    f'{index + 1} - {remark}. '
                    + _('Imported to row')
                    + f' {self.rowIndex + index + 1}'
                    for index, remark in enumerate(self.imported)
                )
            )
        )

        if len(text) <= 1000:
            return text
        else:
            # Limited
            return _('Import share link success') + f'\n\n...'

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxImportSuccess(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.remark = ''
        self.setWindowTitle(_('Import'))

    def customText(self):
        if self.remark:
            return _('Import success') + f': {self.remark}'
        else:
            return _('Import success')

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class ImportFromFileAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Import From File...'),
            icon=bootstrapIcon('folder2-open.svg'),
            **kwargs,
        )

    def triggeredCallback(self, checked):
        filename, selectedFilter = QFileDialog.getOpenFileName(
            None,
            _('Import File'),
            filter=_('Text files (*.json);;All files (*)'),
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    plainText = file.read()
            except Exception as ex:
                # Any non-exit exceptions

                mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)
                mbox.setWindowTitle(_('Error opening file'))
                mbox.setText(_('Invalid configuration file'))
                mbox.setInformativeText(str(ex))

                # Show the MessageBox asynchronously
                mbox.open()
            else:
                factory = configFactoryFromAny(
                    plainText, remark=os.path.basename(filename)
                )

                if factory.isValid():
                    APP().mainWindow.appendNewItemByFactory(factory)

                    mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
                    mbox.remark = factory.getExtras('remark')
                    mbox.setText(mbox.customText())

                    # Show the MessageBox asynchronously
                    mbox.open()
                else:
                    mbox = MBoxImportError(icon=AppQMessageBox.Icon.Critical)
                    mbox.setText(_('Invalid data'))
                    mbox.setInformativeText('')

                    # Show the MessageBox asynchronously
                    mbox.open()


class ImportURIFromClipboardAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(_('Import Share Link From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        clipboard = QApplication.clipboard().text().strip()

        try:
            uris = clipboard.split('\n')
        except Exception:
            # Any non-exit exceptions

            importURIFromClipboard(clipboard)
        else:
            importURIs(
                *uris,
                failureCallback=functools.partial(showMBoxImportError, clipboard),
            )


class ImportJSONFromClipboardAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(_('Import JSON Configuration From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        clipboard = QApplication.clipboard().text().strip()

        importURIFromClipboard(clipboard)


class ImportQRCodeOnTheScreenAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Scan QR Code On The Screen'),
            icon=bootstrapIcon('qr-code-scan.svg'),
            **kwargs,
        )

        self.sct = mss.mss()

    def triggeredCallback(self, checked):
        uris = list()

        for index, monitor in enumerate(self.sct.monitors[1:], start=1):
            frame = self.sct.grab(monitor)
            # Convert raw BGRA bytes to PIL Image
            image = Image.frombytes(
                'RGB', (frame.width, frame.height), frame.bgra, 'raw', 'BGRX'
            )

            barcodes = zxingcpp.read_barcodes(image)

            for barcode in barcodes:
                data = barcode.text

                logger.debug(f'found QR code on monitor \'{index}\': {data}')

                uris.append(data)

        importURIs(*uris)


class ImportAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Import'),
            icon=bootstrapIcon('lightning-charge.svg'),
            menu=AppQMenu(
                ImportURIFromClipboardAction(),
                ImportJSONFromClipboardAction(),
                AppQSeperator(),
                ImportQRCodeOnTheScreenAction(),
            ),
            useActionGroup=False,
            checkable=True,
            **kwargs,
        )
