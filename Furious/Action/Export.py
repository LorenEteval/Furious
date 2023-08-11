from Furious.Core.Configuration import Configuration
from Furious.Gui.Action import Action
from Furious.Widget.Widget import Menu, MessageBox
from Furious.Widget.ExportQRCode import ExportQRCode
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import StateContext, bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6.QtWidgets import QApplication

import ujson


class ExportLinkResultBox(MessageBox):
    def __init__(self, successStr, failureStr, isQRCodeExport, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.successStr = successStr
        self.failureStr = failureStr
        self.isQRCodeExport = isQRCodeExport

        self.setWindowTitle(_('Export'))

        if len(self.failureStr):
            self.setIcon(MessageBox.Icon.Critical)
        else:
            self.setIcon(MessageBox.Icon.Information)

    def getText(self):
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
    serverList = APP().MainWidget.ServerList
    serverLink = []
    successStr = []
    failureStr = []

    for index in selectedIndex:
        try:
            serverLink.append(
                Configuration.export(
                    serverList[index]['remark'],
                    ujson.loads(serverList[index]['config']),
                )
            )

            successStr.append(f'{index + 1} - {serverList[index]["remark"]}')
        except Exception as ex:
            # Any non-exit Exceptions

            failureStr.append(f'{index + 1} - {serverList[index]["remark"]}: {ex}')

    return serverLink, successStr, failureStr


class ExportLinkAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Export Share Link To Clipboard'), **kwargs)

        self.exportLinkResult = ExportLinkResultBox('', '', isQRCodeExport=False)

    def triggeredCallback(self, checked):
        selectedIndex = APP().MainWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        serverLink, successStr, failureStr = exportLink(selectedIndex)

        QApplication.clipboard().setText('\n'.join(serverLink))

        self.exportLinkResult.successStr = successStr
        self.exportLinkResult.failureStr = failureStr
        self.exportLinkResult.setText(self.exportLinkResult.getText())

        # Show the MessageBox and wait for user to close it
        self.exportLinkResult.exec()


class ExportQRCodeAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Export As QR Code'), **kwargs)

        self.exportQRCode = ExportQRCode()
        self.exportLinkResult = ExportLinkResultBox('', '', isQRCodeExport=True)

    def triggeredCallback(self, checked):
        selectedIndex = APP().MainWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        serverLink, successStr, failureStr = exportLink(selectedIndex)

        if len(successStr) > 0:
            self.exportQRCode.editorTab.clear()
            self.exportQRCode.initTabWithData(list(zip(successStr, serverLink)))
            self.exportQRCode.show()

        self.exportLinkResult.successStr = successStr
        self.exportLinkResult.failureStr = failureStr
        self.exportLinkResult.setText(self.exportLinkResult.getText())

        # Show the MessageBox and wait for user to close it
        self.exportLinkResult.exec()


class ExportJSONAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Export JSON Configuration To Clipboard'), **kwargs)

        self.exportJSONResult = ExportJSONResultBox()

    def triggeredCallback(self, checked):
        selectedIndex = APP().MainWidget.selectedIndex

        if len(selectedIndex) == 0:
            # Nothing selected. Do nothing
            return

        try:
            QApplication.clipboard().setText(
                '\n'.join(
                    APP().MainWidget.ServerList[index]['config']
                    for index in selectedIndex
                )
            )
        except Exception:
            # Any non-exit exceptions

            pass
        else:
            # Show the MessageBox and wait for user to close it
            self.exportJSONResult.exec()
