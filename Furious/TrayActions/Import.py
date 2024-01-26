from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *

from PySide6.QtWidgets import QApplication, QFileDialog

import os
import logging

__all__ = [
    'ImportFromFileAction',
    'ImportURIFromClipboardAction',
    'ImportJSONFromClipboardAction',
    'ImportAction',
]

logger = logging.getLogger(__name__)


def showImportErrorMBox(clipboard: str):
    mbox = ImportErrorMBox(icon=AppQMessageBox.Icon.Critical)

    if len(clipboard) > 1000:
        # Limited
        mbox.setText(_('Invalid data'))
        mbox.setInformativeText('')
    else:
        mbox.setText(_('Invalid data. The content of the clipboard is:'))
        mbox.setInformativeText(clipboard)

    mbox.exec()


def importItemFromClipboard(clipboard: str):
    factory = constructFromAny(clipboard)

    if not factory.isValid():
        showImportErrorMBox(clipboard)
    else:
        APP().mainWindow.appendNewItemByFactory(factory)

        mbox = ImportSuccessMBox(icon=AppQMessageBox.Icon.Information)
        mbox.remark = factory.getExtras('remark')
        mbox.setText(mbox.customText())
        mbox.exec()


class ImportErrorMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Import'))

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(_(self.text()))

        # Ignore informative text, buttons

        self.moveToCenter()


class ImportMultiSuccessMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.imported = []
        self.rowCount = 0

        self.setWindowTitle(_('Import'))
        self.setIcon(AppQMessageBox.Icon.Information)

    def customText(self):
        text = (
            _('Import share link success: ')
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
            return _('Import share link success: ') + f'\n\n...'


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
                mbox.setText(_('Invalid configuration file.'))
                mbox.setInformativeText(str(ex))

                # Show the MessageBox and wait for user to close it
                mbox.exec()
            else:
                factory = constructFromAny(plainText, remark=os.path.basename(filename))

                if factory.isValid():
                    APP().mainWindow.appendNewItemByFactory(factory)

                    mbox = ImportSuccessMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.remark = factory.getExtras('remark')
                    mbox.setText(mbox.customText())
                    mbox.exec()
                else:
                    mbox = ImportErrorMBox(icon=AppQMessageBox.Icon.Critical)
                    mbox.setText(_('Invalid data'))
                    mbox.setInformativeText('')
                    mbox.show()


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
                    mbox.exec()
                else:
                    mbox = ImportMultiSuccessMBox(icon=AppQMessageBox.Icon.Information)
                    mbox.imported = imported
                    mbox.rowCount = rowCount
                    mbox.setText(mbox.customText())
                    mbox.exec()


class ImportJSONFromClipboardAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(_('Import JSON Configuration From Clipboard'), **kwargs)

    def triggeredCallback(self, checked):
        clipboard = QApplication.clipboard().text().strip()

        importItemFromClipboard(clipboard)


class ImportAction(AppQAction):
    def __init__(self):
        super().__init__(
            _('Import'),
            icon=bootstrapIcon('lightning-charge.svg'),
            menu=AppQMenu(
                ImportURIFromClipboardAction(),
                ImportJSONFromClipboardAction(),
            ),
            useActionGroup=False,
            checkable=True,
        )
