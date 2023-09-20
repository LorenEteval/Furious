# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Core.Configuration import Configuration
from Furious.Gui.Action import Action
from Furious.Widget.Widget import Menu, MessageBox
from Furious.Widget.ExportQRCode import ExportQRCode
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import StateContext, bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6.QtWidgets import QApplication


class ExportLinkResultBox(MessageBox):
    def __init__(self, successStr, failureStr, isQRCodeExport, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.successStr = successStr
        self.failureStr = failureStr
        self.isQRCodeExport = isQRCodeExport

        self.setWindowTitle(_('Export'))

    def getText(self):
        text = self.getTextAll()

        if len(text) <= 1000:
            return text
        else:
            # Limited
            if len(self.successStr) == 0:
                return (
                    _('Export as QR code failed:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard failed:')
                ) + f'\n\n...'
            elif len(self.failureStr) == 0:
                return (
                    _('Export as QR code success:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard success:')
                ) + f'\n\n...'
            else:
                return (
                    _('Export as QR code partially success:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard partially success:')
                ) + f'\n\n...'

    def getTextAll(self):
        if len(self.successStr) == 0:
            return (
                (
                    _('Export as QR code failed:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard failed:')
                )
                + f'\n\n'
                + '\n'.join(
                    list(
                        f'{index + 1}: {failure}'
                        for index, failure in enumerate(self.failureStr)
                    )
                )
            )
        elif len(self.failureStr) == 0:
            return (
                (
                    _('Export as QR code success:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard success:')
                )
                + f'\n\n'
                + '\n'.join(
                    list(
                        f'{index + 1}: {success}'
                        for index, success in enumerate(self.successStr)
                    )
                )
            )
        else:
            return (
                (
                    _('Export as QR code partially success:')
                    if self.isQRCodeExport
                    else _('Export share link to clipboard partially success:')
                )
                + f'\n\n'
                + '\n'.join(
                    list(
                        f'{index + 1}: {success}'
                        for index, success in enumerate(self.successStr)
                    )
                )
                + f'\n\n'
                + _('Failed:')
                + f'\n\n'
                + '\n'.join(
                    list(
                        f'{index + 1}: {failure}'
                        for index, failure in enumerate(self.failureStr)
                    )
                )
            )

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(self.getText())

            # Ignore informative text, buttons

            self.moveToCenter()


class ExportJSONResultBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Export'))
        self.setIcon(MessageBox.Icon.Information)
        self.setText(_('Export JSON configuration to clipboard success.'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(_(self.text()))

            # Ignore informative text, buttons

            self.moveToCenter()


def exportLink(selectedIndex):
    serverList = APP().ServerWidget.ServerList
    serverLink = []
    successStr = []
    failureStr = []

    for index in selectedIndex:
        try:
            serverLink.append(
                Configuration.export(
                    serverList[index]['remark'],
                    Configuration.toJSON(serverList[index]['config']),
                )
            )

            successStr.append(f'{index + 1} - {serverList[index]["remark"]}')
        except Exception as ex:
            # Any non-exit Exceptions

            failureStr.append(f'{index + 1} - {serverList[index]["remark"]}: {ex}')

    return serverLink, successStr, failureStr


def showExportLinkResult(resultBox, successStr, failureStr):
    resultBox.successStr = successStr
    resultBox.failureStr = failureStr
    resultBox.setText(resultBox.getText())

    if len(successStr) == 0:
        resultBox.setIcon(MessageBox.Icon.Critical)
    else:
        resultBox.setIcon(MessageBox.Icon.Information)

    # Show the MessageBox and wait for user to close it
    resultBox.exec()


class ExportLinkAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Export Share Link To Clipboard'), **kwargs)

        self.exportLinkResult = ExportLinkResultBox('', '', isQRCodeExport=False)

    def triggeredCallback(self, checked):
        selectedIndex = APP().ServerWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        serverLink, successStr, failureStr = exportLink(selectedIndex)

        QApplication.clipboard().setText('\n'.join(serverLink))

        showExportLinkResult(self.exportLinkResult, successStr, failureStr)


class ExportQRCodeAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Export As QR Code'),
            icon=bootstrapIcon('qr-code.svg'),
            **kwargs,
        )

        self.exportQRCode = ExportQRCode()
        self.exportLinkResult = ExportLinkResultBox('', '', isQRCodeExport=True)

    def triggeredCallback(self, checked):
        selectedIndex = APP().ServerWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        serverLink, successStr, failureStr = exportLink(selectedIndex)

        if len(successStr) > 0:
            self.exportQRCode.editorTab.clear()
            self.exportQRCode.labelList.clear()
            self.exportQRCode.initTabWithData(list(zip(successStr, serverLink)))
            self.exportQRCode.show()

        showExportLinkResult(self.exportLinkResult, successStr, failureStr)


class ExportJSONAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Export JSON Configuration To Clipboard'), **kwargs)

        self.exportJSONResult = ExportJSONResultBox()

    def triggeredCallback(self, checked):
        selectedIndex = APP().ServerWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        try:
            QApplication.clipboard().setText(
                '\n'.join(
                    APP().ServerWidget.ServerList[index]['config']
                    for index in selectedIndex
                )
            )
        except Exception:
            # Any non-exit exceptions

            pass
        else:
            # Show the MessageBox and wait for user to close it
            self.exportJSONResult.exec()
