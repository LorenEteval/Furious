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

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *

from PySide6.QtWidgets import QApplication, QFileDialog

import os
import logging
import functools

__all__ = [
    'ImportFromFileAction',
    'ImportURIFromClipboardAction',
    'ImportJSONFromClipboardAction',
    'ImportAction',
]

logger = logging.getLogger(__name__)

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Invalid data',
    'Invalid data. The content of the clipboard is:',
)


def showImportErrorMBox(clipboard: str):
    mbox = ImportErrorMBox(icon=AppQMessageBox.Icon.Critical)

    if len(clipboard) > 1000:
        # Limited
        mbox.setText(_('Invalid data'))
        mbox.setInformativeText('')
    else:
        mbox.setText(_('Invalid data. The content of the clipboard is:'))
        mbox.setInformativeText(clipboard)

    # Show the MessageBox asynchronously
    mbox.open()


def importItemFromClipboard(clipboard: str):
    factory = constructFromAny(clipboard)

    if not factory.isValid():
        showImportErrorMBox(clipboard)
    else:
        APP().mainWindow.appendNewItemByFactory(factory)

        mbox = ImportSuccessMBox(icon=AppQMessageBox.Icon.Information)
        mbox.remark = factory.getExtras('remark')
        mbox.setText(mbox.customText())

        # Show the MessageBox asynchronously
        mbox.open()


needTrans('Import')


class ImportErrorMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Import'))

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


needTrans(
    'Import',
    'Import share link success',
    'Imported to row',
)


class ImportMultiSuccessMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.imported = []
        self.rowCount = 0

        self.setWindowTitle(_('Import'))
        self.setIcon(AppQMessageBox.Icon.Information)

    def customText(self):
        text = (
            _('Import share link success')
            + f'\n\n'
            + '\n'.join(
                list(
                    f'{index + 1} - {remark}. '
                    + _('Imported to row')
                    + f' {self.rowCount + index + 1}'
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


needTrans(
    'Import',
    'Import success',
)


class ImportSuccessMBox(AppQMessageBox):
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


needTrans(
    'Import From File...',
    'Import File',
    'Text files (*.json);;All files (*)',
    'Error opening file',
    'Invalid configuration file',
    'Invalid data',
)


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
                factory = constructFromAny(plainText, remark=os.path.basename(filename))

                if factory.isValid():
                    APP().mainWindow.appendNewItemByFactory(factory)

                    mbox = ImportSuccessMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.remark = factory.getExtras('remark')
                    mbox.setText(mbox.customText())

                    # Show the MessageBox asynchronously
                    mbox.open()
                else:
                    mbox = ImportErrorMBox(icon=AppQMessageBox.Icon.Critical)
                    mbox.setText(_('Invalid data'))
                    mbox.setInformativeText('')

                    # Show the MessageBox asynchronously
                    mbox.open()


needTrans('Import Share Link From Clipboard')


class ImportURIFromClipboardAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(_('Import Share Link From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        clipboard = QApplication.clipboard().text().strip()

        try:
            split = clipboard.split('\n')
        except Exception:
            # Any non-exit exceptions

            importItemFromClipboard(clipboard)
        else:
            imported = list()
            rowCount = len(AS_UserServers())

            for uri in split:
                factory = constructFromAny(uri)

                if factory.isValid():
                    APP().mainWindow.appendNewItemByFactory(factory)

                    imported.append(factory.getExtras('remark'))

            if len(imported) == 0:
                showImportErrorMBox(clipboard)
            else:
                if len(imported) == 1:
                    # Fall back to single
                    mbox = ImportSuccessMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.remark = imported[0]
                    mbox.setText(mbox.customText())

                    # Show the MessageBox asynchronously
                    mbox.open()
                else:
                    mbox = ImportMultiSuccessMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.imported = imported
                    mbox.rowCount = rowCount
                    mbox.setText(mbox.customText())

                    # Show the MessageBox asynchronously
                    mbox.open()


needTrans('Import JSON Configuration From Clipboard')


class ImportJSONFromClipboardAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(_('Import JSON Configuration From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        clipboard = QApplication.clipboard().text().strip()

        importItemFromClipboard(clipboard)


needTrans('Import')


class ImportAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Import'),
            icon=bootstrapIcon('lightning-charge.svg'),
            menu=AppQMenu(
                ImportURIFromClipboardAction(),
                ImportJSONFromClipboardAction(),
            ),
            useActionGroup=False,
            checkable=True,
            **kwargs,
        )
