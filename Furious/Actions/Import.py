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

"""Implement tray actions for import."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Models import *
from Furious.Plugins import profileFromAny
from Furious.Repository import *
from Furious.Qt import *
from Furious.Qt.Signals import connectWeakly, singleShotWeakly
from Furious.Qt import gettext as _
from Furious.Widget.WaitingSpinner import *

from PySide6 import QtCore
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QVBoxLayout

from PIL import Image

from typing import Callable, Tuple, Union

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
    """Show m box import error."""
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
    """Import URI from clipboard."""
    factory = profileFromAny(clipboard)

    if not factory.isValid():
        showMBoxImportError(clipboard)
    else:
        AppMainWindow().appendNewItemByFactory(factory)

        mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
        mbox.remark = factory.itemRemark
        mbox.setText(mbox.customText())

        # Show the MessageBox asynchronously
        mbox.open()


def importURIs(*uris, failureCallback: Union[Callable[[], None], None] = None):
    """Import ur is."""
    if len(uris) > 1:
        dialog = ImportURIsProgressDialog(
            uris,
            failureCallback=failureCallback,
            parent=AppMainWindow(),
        )
        dialog.open()

        return

    imported = list()
    rowIndex = len(Storage.UserServers())

    for uri in uris:
        factory = profileFromAny(uri.strip())

        if factory.isValid():
            AppMainWindow().appendNewItemByFactory(factory)

            imported.append(factory.itemRemark)

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


class ImportURIsProgressDialog(AppQTransientDialog):
    """Present progress and cancellation controls for import ur is."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(420, 150)

    def __init__(
        self,
        uris: Tuple[str, ...],
        failureCallback: Union[Callable[[], None], None] = None,
        parent=None,
    ):
        """Initialize the ImportURIsProgressDialog."""
        super().__init__(parent)

        self.uris = uris
        self.failureCallback = failureCallback
        self.imported = list()
        self.rowIndex = len(Storage.UserServers())
        self.currentIndex = 0
        self.currentRemark = ''
        self.canceled = False
        self.finishedImport = False

        self.setWindowTitle(_('Import'))
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)

        self.spinner = WaitingSpinner(
            self,
            center_on_parent=False,
            lines=12,
            line_length=7,
            line_width=3,
            radius=7,
            color=QColor(96, 160, 255),
        )
        self.statusLabel = AppQLabel()
        self.detailLabel = AppQLabel()
        self.detailLabel.setWordWrap(True)
        self.cancelButton = AppQPushButton(_('Cancel'))

        connectWeakly(
            self.cancelButton.clicked,
            self,
            'cancel',
            sender=self.cancelButton,
        )

        statusLayout = QHBoxLayout()
        statusLayout.addWidget(self.spinner)
        statusLayout.addWidget(self.statusLabel, 1)

        layout = QVBoxLayout()
        layout.addLayout(statusLayout)
        layout.addWidget(self.detailLabel)
        layout.addWidget(self.cancelButton)

        self.setLayout(layout)

        self.updateStatus()

    def open(self):
        """Open the import ur is progress dialog asynchronously."""
        result = super().open()

        self.spinner.start()

        singleShotWeakly(0, self, 'importNext')

        return result

    def reject(self):
        """Reject the current import ur is progress dialog values."""
        self.cancel()

    def cancel(self, *_args):
        """Cancel the import ur is progress dialog operation."""
        self.canceled = True
        self.cancelButton.setEnabled(False)
        self.updateStatus()

    def updateStatus(self):
        """Update status."""
        total = len(self.uris)
        processed = min(self.currentIndex, total)

        if self.canceled:
            self.statusLabel.setText(_('Canceling import') + f'... {processed}/{total}')
        else:
            self.statusLabel.setText(_('Importing') + f'... {processed}/{total}')

        if self.currentRemark:
            self.detailLabel.setText(_('Current') + f': {self.currentRemark}')
        else:
            self.detailLabel.setText('')

    @staticmethod
    def limitedRemark(remark: str) -> str:
        """Return the limited remark value used by the import ur is progress dialog."""
        remark = str(remark).strip()

        if len(remark) <= 120:
            return remark

        return remark[:117] + '...'

    def importNext(self):
        """Import next."""
        if self.canceled or self.currentIndex >= len(self.uris):
            self.finishImport()

            return

        uri = self.uris[self.currentIndex]
        self.currentIndex += 1

        factory = profileFromAny(uri.strip())

        if factory.isValid():
            remark = factory.itemRemark

            self.currentRemark = self.limitedRemark(remark)

            AppMainWindow().appendNewItemByFactory(factory)

            self.imported.append(remark)
        else:
            self.currentRemark = _('Invalid data')

        self.updateStatus()

        singleShotWeakly(0, self, 'importNext')

    def finishImport(self):
        """Handle finish import for the import ur is progress dialog."""
        if self.finishedImport:
            return

        self.finishedImport = True
        self.spinner.stop()
        self.accept()

        if self.canceled:
            return

        if len(self.imported) == 0:
            if callable(self.failureCallback):
                self.failureCallback()
        elif len(self.imported) == 1:
            mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
            mbox.remark = self.imported[0]
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()
        else:
            mbox = MBoxImportMultiSuccess(icon=AppQMessageBox.Icon.Information)
            mbox.imported = self.imported
            mbox.rowIndex = self.rowIndex
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()

    def retranslate(self):
        """Refresh translated text for the import ur is progress dialog."""
        self.setWindowTitle(_(self.windowTitle()))
        self.cancelButton.setText(_(self.cancelButton.text()))
        self.updateStatus()


class MBoxImportError(AppQMessageBox):
    """Represent m box import error."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxImportError."""
        super().__init__(*args, **kwargs)

    def retranslate(self):
        """Refresh translated text for the m box import error."""
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxImportMultiSuccess(AppQMessageBox):
    """Represent m box import multi success."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxImportMultiSuccess."""
        super().__init__(*args, **kwargs)

        self.imported = list()
        self.rowIndex = 0

        self.setIcon(AppQMessageBox.Icon.Information)

    def customText(self):
        """Return the user-facing message text for the m box import multi success."""
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
        """Refresh translated text for the m box import multi success."""
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class MBoxImportSuccess(AppQMessageBox):
    """Represent m box import success."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxImportSuccess."""
        super().__init__(*args, **kwargs)

        self.remark = ''

    def customText(self):
        """Return the user-facing message text for the m box import success."""
        if self.remark:
            return _('Import success') + f': {self.remark}'
        else:
            return _('Import success')

    def retranslate(self):
        """Refresh translated text for the m box import success."""
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


class ImportFromFileAction(AppQAction):
    """Handle the import from file action."""

    def __init__(self, **kwargs):
        """Initialize the ImportFromFileAction."""
        super().__init__(
            _('Import From File...'),
            icon=bootstrapIcon('folder2.svg'),
            **kwargs,
        )

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
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
                mbox.setText(_('Invalid configuration file'))
                mbox.setInformativeText(str(ex))

                # Show the MessageBox asynchronously
                mbox.open()
            else:
                factory = profileFromAny(plainText, remark=os.path.basename(filename))

                if factory.isValid():
                    AppMainWindow().appendNewItemByFactory(factory)

                    mbox = MBoxImportSuccess(icon=AppQMessageBox.Icon.Information)
                    mbox.remark = factory.itemRemark
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
    """Handle the import URI from clipboard action."""

    def __init__(self, **kwargs):
        """Initialize the ImportURIFromClipboardAction."""
        super().__init__(_('Import Share Link From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
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
    """Handle the import JSON from clipboard action."""

    def __init__(self, **kwargs):
        """Initialize the ImportJSONFromClipboardAction."""
        super().__init__(_('Import JSON Configuration From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        clipboard = QApplication.clipboard().text().strip()

        importURIFromClipboard(clipboard)


class ImportQRCodeOnTheScreenAction(Mixins.CleanupOnExit, AppQAction):
    """Handle the import QR code on the screen action."""

    def __init__(self, **kwargs):
        """Initialize the ImportQRCodeOnTheScreenAction."""
        super().__init__(
            _('Scan QR Code On The Screen'),
            icon=bootstrapIcon('qr-code-scan.svg'),
            # Tray and page actions each own a distinct native screen-capture
            # handle, so every instance must close its own handle at shutdown.
            uniqueCleanup=False,
            **kwargs,
        )

        try:
            self.sct = mss.mss()
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'\'{classname(self)}\' is not supported on this platform')

            self.sct = None

    def _importFromQRCode(self):
        """Handle import from QR code for the import QR code on the screen action."""
        if self.sct is None:
            # Nothing to do
            return

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

                logger.debug(f'found QR code on monitor \'{index}\'')

                uris.append(data)

        importURIs(*uris)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        try:
            self._importFromQRCode()
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while importing QR code on the screen: {ex}')

    def cleanup(self):
        """Release resources owned by the import QR code on the screen action."""
        try:
            if self.sct is not None:
                self.sct.close()
        except Exception:
            # Any non-exit exceptions

            pass


class ImportAction(AppQAction):
    """Handle the import action."""

    def __init__(self, **kwargs):
        """Initialize the ImportAction."""
        super().__init__(
            _('Import'),
            icon=bootstrapIcon('lightning-charge.svg'),
            menu=AppQMenu(
                ImportURIFromClipboardAction(),
                ImportJSONFromClipboardAction(),
                AppQSeparator(),
                ImportQRCodeOnTheScreenAction(),
            ),
            useActionGroup=False,
            **kwargs,
        )
