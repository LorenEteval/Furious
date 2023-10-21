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

from Furious.Core.Core import Core, XrayCore, Hysteria1, Hysteria2
from Furious.Core.TorRelay import TorRelay
from Furious.Core.Configuration import Configuration
from Furious.Core.Intellisense import Intellisense
from Furious.Action.Import import ImportLinkAction, ImportJSONAction
from Furious.Action.Export import ExportLinkAction, ExportJSONAction, ExportQRCodeAction
from Furious.Gui.Action import Action, Seperator
from Furious.Widget.Widget import (
    HeaderView,
    MainWindow,
    Menu,
    MessageBox,
    PushButton,
    StyledItemDelegate,
    TableWidget,
    TabWidget,
    ZoomablePlainTextEdit,
)
from Furious.Widget.IndentSpinBox import IndentSpinBox
from Furious.Utility.Constants import (
    APP,
    APPLICATION_NAME,
    APPLICATION_VERSION,
    APPLICATION_ABOUT_PAGE,
    APPLICATION_REPO_OWNER_NAME,
    APPLICATION_REPO_NAME,
    PLATFORM,
    Color,
)
from Furious.Utility.Utility import (
    Base64Encoder,
    StateContext,
    ServerStorage,
    Switch,
    SupportConnectedCallback,
    bootstrapIcon,
    enumValueWrapper,
    parseHostPort,
    eventLoopWait,
    swapListItem,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _
from Furious.Utility.Theme import DraculaTheme

from PySide6 import QtCore
from PySide6.QtGui import QDesktopServices, QFont, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
    QNetworkProxy,
)

import os
import copy
import queue
import ujson
import ping3
import logging
import operator
import functools
import multiprocessing

logger = logging.getLogger(__name__)


def needSaveChanges(func):
    def decorator(*args, **kwargs):
        if APP().ServerWidget is not None and APP().ServerWidget.modified:
            # Need save changes
            APP().ServerWidget.saveChangeFirst.exec()

            return

        # Call the actual function
        func(*args, **kwargs)

    return decorator


class NewBlankServerAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('New...'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_N,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().importServer(_('Untitled'), '', syncStorage=True)


class ImportFileAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Import From File...'),
            icon=bootstrapIcon('folder2-open.svg'),
            **kwargs,
        )

        self.openErrorBox = MessageBox(
            icon=MessageBox.Icon.Critical, parent=self.parent()
        )

    def triggeredCallback(self, checked):
        filename, selectedFilter = QFileDialog.getOpenFileName(
            self.parent(),
            _('Import File'),
            filter=_('Text files (*.json);;All files (*)'),
        )

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    plainText = file.read()
            except Exception as ex:
                # Any non-exit exceptions

                self.openErrorBox.setWindowTitle(_('Error opening file'))
                self.openErrorBox.setText(_('Invalid configuration file.'))
                self.openErrorBox.setInformativeText(str(ex))

                # Show the MessageBox and wait for user to close it
                self.openErrorBox.exec()
            else:
                self.parent().importServer(
                    os.path.basename(filename), plainText, syncStorage=True
                )


class ImportLinkActionWithHotKey(ImportLinkAction):
    def __init__(self, **kwargs):
        # Cloned. With hot key
        super().__init__(**kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_V,
            )
        )


class ImportJSONActionWithHotKey(ImportJSONAction):
    def __init__(self, **kwargs):
        # Cloned. With hot key
        super().__init__(**kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_J,
            )
        )


class ExportLinkActionWithHotKey(ExportLinkAction):
    def __init__(self, **kwargs):
        # Cloned. With hot key
        super().__init__(**kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_C,
            )
        )


class ExportQRCodeActionWithHotKey(ExportQRCodeAction):
    def __init__(self, **kwargs):
        # Cloned. With hot key
        super().__init__(**kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_Q,
            )
        )


class ExportJSONActionWithHotKey(ExportJSONAction):
    def __init__(self, **kwargs):
        # Cloned. With hot key
        super().__init__(**kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_J,
            )
        )


class SelectAllServerAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Select All'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_A,
            )
        )


class TestPingLatencyAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Test Ping Latency'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_P,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().testSelectedItemDelay()


class TestDownloadSpeedAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Test Download Speed'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_T,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().testSelectedItemSpeed()


class ClearTestResultsAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Clear Test Results'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_R,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().clearSelectedItemTestResults()


class ScrollToActivatedServerAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Scroll To Activated Server'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_G,
            )
        )

    @needSaveChanges
    def triggeredCallback(self, checked):
        activatedItem = self.parent().activatedItem

        self.parent().setCurrentItem(activatedItem)
        self.parent().scrollToItem(activatedItem)


class JSONErrorBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.decodeError = ''

    def getText(self):
        return (
            _('Please check your configuration is in valid JSON format:')
            + f'\n\n{self.decodeError}'
        )

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(self.getText())

            # Ignore informative text, buttons

            self.moveToCenter()


class SaveConfInfo(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.addButton(_('Reconnect'), MessageBox.ButtonRole.AcceptRole)
        self.addButton(_('OK'), MessageBox.ButtonRole.RejectRole)


def questionReconnect(saveConfInfo):
    saveConfInfo.setWindowTitle(_('Hint'))
    saveConfInfo.setText(
        _(
            f'{APPLICATION_NAME} is currently connected.\n\n'
            f'The new configuration will take effect the next time you connect.'
        )
    )

    # Show the MessageBox and wait for user to close it
    choice = saveConfInfo.exec()

    if choice == enumValueWrapper(MessageBox.ButtonRole.AcceptRole):
        # Reconnect
        APP().tray.ConnectAction.reconnectAction()
    else:
        # OK. Do nothing
        pass


class SaveAsServerAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Save'), icon=bootstrapIcon('save.svg'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_S
            )
        )

        self.saveErrorBox = JSONErrorBox(icon=MessageBox.Icon.Critical)
        self.saveConfInfo = SaveConfInfo(icon=MessageBox.Icon.Information)

    def save(self, successCallback=None):
        def saveSuccess(server):
            myServerList = self.parent().ServerList
            myFocusIndex = self.parent().currentFocus

            # Assert to be valid
            assert 0 <= myFocusIndex < len(myServerList)

            # Unchecked?
            myServerList[myFocusIndex]['config'] = server
            # Flush row
            self.parent().serverWidget.flushRow(
                myFocusIndex, myServerList[myFocusIndex]
            )

            # Sync it
            ServerStorage.sync()

            self.parent().markAsSaved()

            if callable(successCallback):
                successCallback()

            if myFocusIndex == self.parent().activatedItemIndex:
                # Activated configuration modified

                if server and APP().isConnected():
                    questionReconnect(self.saveConfInfo)

            return True

        if not self.parent().modified:
            return True

        text = self.parent().plainTextEdit.toPlainText()

        if text == '':
            # Text is empty. Allowed.
            return saveSuccess('')

        try:
            myJSON = Configuration.toJSON(text)
        except ujson.JSONDecodeError as decodeError:
            self.saveErrorBox.decodeError = str(decodeError)
            self.saveErrorBox.setWindowTitle(_('Error saving configuration'))
            self.saveErrorBox.setText(self.saveErrorBox.getText())

            # Show the MessageBox and wait for user to close it
            self.saveErrorBox.exec()

            return False
        except Exception:
            # Any non-exit exceptions

            self.saveErrorBox.setWindowTitle(_('Error saving configuration'))
            self.saveErrorBox.setText(_('Invalid server configuration.'))

            # Show the MessageBox and wait for user to close it
            self.saveErrorBox.exec()

            return False
        else:
            return saveSuccess(text)

    def triggeredCallback(self, checked):
        self.save()


class SaveErrorBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.saveError = ''

    def getText(self):
        if self.saveError:
            return _('Invalid server configuration.') + f'\n\n{self.saveError}'
        else:
            return _('Invalid server configuration.')

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(self.getText())

            # Ignore informative text, buttons

            self.moveToCenter()


class SaveAsFileAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Save As...'), **kwargs)

        self.saveErrorBox = SaveErrorBox(
            icon=MessageBox.Icon.Critical, parent=self.parent()
        )

    def triggeredCallback(self, checked):
        filename, selectedFilter = QFileDialog.getSaveFileName(
            self.parent(),
            _('Save File'),
            filter=_('Text files (*.json);;All files (*)'),
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.write(self.parent().plainTextEdit.toPlainText())
            except Exception as ex:
                # Any non-exit exceptions

                self.saveErrorBox.saveError = str(ex)
                self.saveErrorBox.setWindowTitle(_('Error saving file'))
                self.saveErrorBox.setText(self.saveErrorBox.getText())

                # Show the MessageBox and wait for user to close it
                self.saveErrorBox.exec()


class ExitAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Exit'), **kwargs)

    def triggeredCallback(self, checked):
        self.parent().syncSettings()
        self.parent().questionSave()


class UndoAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Undo'),
            icon=bootstrapIcon('arrow-return-left.svg'),
            **kwargs,
        )

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Z
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.undo()


class RedoAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Redo'),
            icon=bootstrapIcon('arrow-return-right.svg'),
            **kwargs,
        )

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier
                | QtCore.Qt.KeyboardModifier.ShiftModifier,
                QtCore.Qt.Key.Key_Z,
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.redo()


class CutAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Cut'), icon=bootstrapIcon('scissors.svg'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_X,
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.cut()


class CopyAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Copy'), icon=bootstrapIcon('files.svg'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_C,
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.copy()


class PasteAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Paste'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_V,
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.paste()


class SelectAllTextAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Select All'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_A,
            )
        )

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        self.parent().plainTextEdit.selectAll()


class IndentAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Indent...'), **kwargs)

        self.indentSpinBox = IndentSpinBox()
        self.indentFailure = JSONErrorBox(icon=MessageBox.Icon.Critical)

    def triggeredCallback(self, checked):
        if self.parent().editorTab.isHidden():
            return

        choice = self.indentSpinBox.exec()

        if choice == enumValueWrapper(QDialog.DialogCode.Accepted):
            myText = self.parent().plainTextEdit.toPlainText()

            if myText == '':
                # Empty. Do nothing
                return

            currentFocus = self.parent().currentFocus

            if currentFocus >= 0:
                self.parent().saveScrollBarValue(currentFocus)

            try:
                myJSON = Configuration.toJSON(myText)
                myText = ujson.dumps(
                    myJSON,
                    indent=self.indentSpinBox.value(),
                    ensure_ascii=False,
                    escape_forward_slashes=False,
                )
            except ujson.JSONDecodeError as decodeError:
                self.indentFailure.decodeError = str(decodeError)
                self.indentFailure.setWindowTitle(_('Error setting indent'))
                self.indentFailure.setText(self.indentFailure.getText())

                # Show the MessageBox and wait for user to close it
                self.indentFailure.exec()
            except Exception:
                # Any non-exit exceptions

                self.indentFailure.setWindowTitle(_('Error setting indent'))
                self.indentFailure.setText(_('Invalid server configuration.'))

                # Show the MessageBox and wait for user to close it
                self.indentFailure.exec()
            else:
                self.parent().plainTextEdit.setPlainText(myText)

                if currentFocus >= 0:
                    self.parent().restoreScrollBarValue(currentFocus)
        else:
            # Do nothing
            pass


class ZoomInAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom In'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Plus
            )
        )

    def triggeredCallback(self, checked):
        self.parent().plainTextEdit.zoomIn()


class ZoomOutAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom Out'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Minus
            )
        )

    def triggeredCallback(self, checked):
        self.parent().plainTextEdit.zoomOut()


class ShowHideEditorAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Show/Hide Editor'),
            icon=bootstrapIcon('layout-text-sidebar-reverse.svg'),
            **kwargs,
        )

        # Reference
        self.serverTab = self.parent().serverTab
        self.editorTab = self.parent().editorTab

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_E
            )
        )

    def triggeredCallback(self, checked):
        oldSize = self.serverTab.width()

        if APP().HideEditor == Switch.OFF:
            self.editorTab.hide()

            APP().HideEditor = Switch.ON_
        else:
            self.editorTab.show()

            APP().HideEditor = Switch.OFF

        APP().processEvents()

        newSize = self.serverTab.width()

        APP().ServerWidget.resizeHorizontalHeaderSection(oldSize, newSize)


def useProxyServerIfPossible(manager, loggerAction):
    proxyServer = APP().tray.ConnectAction.httpsProxyServer

    if proxyServer:
        logger.info(f'{loggerAction} uses proxy server {proxyServer}')

        # Checked. Should not throw exceptions
        proxyHost, proxyPort = parseHostPort(proxyServer)

        # Checked. int(proxyPort) should not throw exceptions
        manager.setProxy(
            QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort))
        )
    else:
        logger.info(f'{loggerAction} uses no proxy')

        manager.setProxy(QNetworkProxy.ProxyType.NoProxy)

    return proxyServer


class UpdateSubsAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.networkAccessManager = QNetworkAccessManager(parent=self)

        self.networkReplyTable = {}

    def handleFinishedByNetworkReply(self, networkReply):
        unique, remark, webURL = (
            self.networkReplyTable[networkReply]['unique'],
            self.networkReplyTable[networkReply]['remark'],
            self.networkReplyTable[networkReply]['webURL'],
        )

        if networkReply.error() != QNetworkReply.NetworkError.NoError:
            logger.error(f'update subs {webURL} failed. {networkReply.errorString()}')
        else:
            logger.info(f'update subs {webURL} success')

            try:
                shareLinks = list(
                    filter(
                        lambda x: x != '',
                        Base64Encoder.decode(networkReply.readAll().data())
                        .decode()
                        .split('\n'),
                    )
                )
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'parse share link failed: {ex}')
            else:
                # Delete old subscription by unique(subsId)
                deletedNum = APP().ServerWidget.deleteItemByUnique(
                    unique, syncStorage=False
                )

                # Append subscription
                for shareLink in shareLinks:
                    ImportLinkAction.parseShareLink(shareLink, {'subsId': unique})

                if deletedNum or shareLinks:
                    # Deleted or imported. Sync it
                    ServerStorage.sync()

        # Done. Remove entry. Key should be found, but protect it anyway
        self.networkReplyTable.pop(networkReply, None)

    @QtCore.Slot()
    def handleFinished(self):
        networkReply = self.sender()

        self.handleFinishedByNetworkReply(networkReply)

    def configureProxy(self):
        raise NotImplementedError

    @needSaveChanges
    def triggeredCallback(self, checked):
        # Reference
        subscriptionDict = APP().SubscriptionWidget.SubscriptionDict

        if not subscriptionDict:
            # Empty. Nothing to do
            return

        self.configureProxy()

        for key, value in subscriptionDict.items():
            networkReply = self.networkAccessManager.get(
                QNetworkRequest(QtCore.QUrl(value['webURL']))
            )

            self.networkReplyTable[networkReply] = {
                'unique': key,
                'remark': value['remark'],
                'webURL': value['webURL'],
            }

            networkReply.finished.connect(
                functools.partial(self.handleFinishedByNetworkReply, networkReply)
            )

            # networkReply.finished.connect(self.handleFinished)


class UpdateSubsUseCurrentProxyAction(UpdateSubsAction):
    def __init__(self, **kwargs):
        super().__init__(_('Update Subscription (Use Current Proxy)'), **kwargs)

    def configureProxy(self):
        useProxyServerIfPossible(self.networkAccessManager, 'update subscription')


class UpdateSubsForceProxyAction(UpdateSubsAction):
    FORCE_PROXY_HOST = '127.0.0.1'
    FORCE_PROXY_PORT = 10809

    FORCE_PROXY = f'{FORCE_PROXY_HOST}:{FORCE_PROXY_PORT}'

    def __init__(self, **kwargs):
        super().__init__(_('Update Subscription (Force Proxy)'), **kwargs)

    def configureProxy(self):
        logger.info(
            f'update subscription uses proxy server {UpdateSubsForceProxyAction.FORCE_PROXY}'
        )

        self.networkAccessManager.setProxy(
            QNetworkProxy(
                QNetworkProxy.ProxyType.HttpProxy,
                UpdateSubsForceProxyAction.FORCE_PROXY_HOST,
                UpdateSubsForceProxyAction.FORCE_PROXY_PORT,
            )
        )


class UpdateSubsNoProxyAction(UpdateSubsAction):
    def __init__(self, **kwargs):
        super().__init__(_('Update Subscription (No Proxy)'), **kwargs)

    def configureProxy(self):
        self.networkAccessManager.setProxy(QNetworkProxy.ProxyType.NoProxy)


class EditSubscriptionAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            _('Edit Subscription...'),
            icon=bootstrapIcon('star.svg'),
            **kwargs,
        )

    def triggeredCallback(self, checked):
        APP().SubscriptionWidget.show()


class ShowLogAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Show Log...'), **kwargs)

    def triggeredCallback(self, checked):
        APP().logViewerWidget.showMaximized()


class WhetherUpdateInfoBox(MessageBox):
    def __init__(self, version='0.0.0', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.version = version

    def retranslate(self):
        with StateContext(self):
            self.setText(_('New version available: ') + self.version)
            self.setWindowTitle(_(self.windowTitle()))
            self.setInformativeText(_(self.informativeText()))

            # Ignore button text

            self.moveToCenter()


def versionToNumber(version):
    major_weight = 10000
    minor_weight = 100
    patch_weight = 1

    return functools.reduce(
        operator.add,
        list(
            int(ver) * weight
            for ver, weight in zip(
                version.split('.'), [major_weight, minor_weight, patch_weight]
            )
        ),
    )


class CheckForUpdatesAction(Action):
    API_URL = (
        f'https://api.github.com/repos/'
        f'{APPLICATION_REPO_OWNER_NAME}/{APPLICATION_REPO_NAME}/releases/latest'
    )

    def __init__(self, **kwargs):
        super().__init__(
            _('Check For Updates'),
            icon=bootstrapIcon('download.svg'),
            **kwargs,
        )

        self.networkAccessManager = QNetworkAccessManager(parent=self)

        self.checkForUpdatesError = MessageBox(
            icon=MessageBox.Icon.Critical, parent=self.parent()
        )
        self.whetherUpdateInfoBox = WhetherUpdateInfoBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.latestVersionInfoBox = MessageBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )

    def handleFinishedByNetworkReply(self, networkReply):
        if networkReply.error() != QNetworkReply.NetworkError.NoError:
            logger.error(f'check for updates failed. {networkReply.errorString()}')

            self.checkForUpdatesError.setWindowTitle(_(APPLICATION_NAME))
            self.checkForUpdatesError.setText(_('Check for updates failed.'))

            # Show the MessageBox and wait for user to close it
            self.checkForUpdatesError.exec()
        else:
            logger.info('check for updates success')

            # Unchecked?
            info = ujson.loads(networkReply.readAll().data())

            if versionToNumber(info['tag_name']) > versionToNumber(APPLICATION_VERSION):
                self.whetherUpdateInfoBox.version = info['tag_name']
                self.whetherUpdateInfoBox.setWindowTitle(_(APPLICATION_NAME))
                self.whetherUpdateInfoBox.setStandardButtons(
                    MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
                )
                self.whetherUpdateInfoBox.setText(
                    _('New version available: ') + info['tag_name']
                )
                self.whetherUpdateInfoBox.setInformativeText(_('Go to download page?'))

                # Show the MessageBox and wait for user to close it
                if self.whetherUpdateInfoBox.exec() == enumValueWrapper(
                    MessageBox.StandardButton.Yes
                ):
                    if QDesktopServices.openUrl(QtCore.QUrl(info['html_url'])):
                        logger.info('open download page success')
                    else:
                        logger.error('open download page failed')
                else:
                    # Do nothing
                    pass
            else:
                self.latestVersionInfoBox.setWindowTitle(_(APPLICATION_NAME))
                self.latestVersionInfoBox.setText(
                    _(f'{APPLICATION_NAME} is already the latest version.')
                )
                self.latestVersionInfoBox.setInformativeText(
                    _(f'Thank you for using {APPLICATION_NAME}.')
                )

                # Show the MessageBox and wait for user to close it
                self.latestVersionInfoBox.exec()

    @QtCore.Slot()
    def handleFinished(self):
        networkReply = self.sender()

        self.handleFinishedByNetworkReply(networkReply)

    def triggeredCallback(self, checked):
        useProxyServerIfPossible(self.networkAccessManager, 'check for updates')

        networkReply = self.networkAccessManager.get(
            QNetworkRequest(QtCore.QUrl(CheckForUpdatesAction.API_URL))
        )

        networkReply.finished.connect(
            functools.partial(self.handleFinishedByNetworkReply, networkReply)
        )

        # networkReply.finished.connect(self.handleFinished)


class AboutAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('About'), **kwargs)

    def triggeredCallback(self, checked):
        if QDesktopServices.openUrl(QtCore.QUrl(APPLICATION_ABOUT_PAGE)):
            logger.info('open about page success')
        else:
            logger.error('open about page failed')


class QuestionSaveBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Save Changes'))
        self.setText(
            _('The content has been modified. Do you want to save the changes?')
        )

        self.button0 = self.addButton(
            _('Save'),
            MessageBox.ButtonRole.AcceptRole,
        )
        self.button1 = self.addButton(
            _('Cancel'),
            MessageBox.ButtonRole.RejectRole,
        )
        self.button2 = self.addButton(
            _('Discard'),
            MessageBox.ButtonRole.DestructiveRole,
        )

        self.setDefaultButton(self.button0)


class QuestionDeleteBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.isMulti = False
        self.possibleRemark = ''

        self.setWindowTitle(_('Delete'))

        self.setStandardButtons(
            MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
        )

    def getText(self):
        if self.isMulti:
            return _('Delete these configuration?')
        else:
            return _('Delete this configuration?') + f'\n\n{self.possibleRemark}'

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(self.getText())

            # Ignore informative text, buttons

            self.moveToCenter()


class ProgressWaitBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Connecting'))
        self.setText(_('Connecting. Please wait.'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(_(self.text()))

            # Ignore informative text, buttons

            self.moveToCenter()


class SaveChangeFirst(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Hint'))
        self.setText(_('Please save any changes to continue.'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(_(self.text()))

            # Ignore informative text, buttons

            self.moveToCenter()


class ServerWidgetHorizontalHeader(HeaderView):
    class SortOrder:
        Ascending_ = False
        Descending = True

    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

        self.sectionClicked.connect(self.handleSectionClicked)
        self.sectionResized.connect(self.handleSectionResized)

        self.sortOrderTable = list(
            ServerWidgetHorizontalHeader.SortOrder.Ascending_
            for i in range(self.parent().columnCount())
        )

    @needSaveChanges
    @QtCore.Slot(int)
    def handleSectionClicked(self, clickedIndex):
        activatedIndex = self.parent().activatedItemIndex

        if activatedIndex < 0:
            activatedServerId = None
        else:
            # Object is activated
            activatedServerId = id(self.parent().ServerList[activatedIndex])

            # De-activated temporarily for sorting
            self.parent().activateItemByIndex(activatedIndex, activate=False)

        # Assertions
        assert len(self.parent().ServerList) == len(self.parent().ScrollList)

        # Save focus scroll bar value
        currentFocus = self.parent().currentFocus

        if currentFocus >= 0:
            self.parent().saveScrollBarValue(currentFocus)
        else:
            # No item selected. Save nothing
            pass

        # Prepare for scroll bar value restoration
        scrollBarValueTable = {}

        for index, server in enumerate(self.parent().ServerList):
            # Object id -> v, h
            scrollBarValueTable[id(server)] = self.parent().ScrollList[index]

        # Sort it
        self.parent().ServerList.sort(
            key=lambda x: ServerWidget.HEADER_LABEL_GET_FUNC[clickedIndex](x),
            reverse=self.sortOrderTable[clickedIndex],
        )

        # Sync it
        ServerStorage.sync()

        # Flush it
        self.parent().flushAll()

        # Toggle. Sorting done
        self.sortOrderTable[clickedIndex] = not self.sortOrderTable[clickedIndex]

        # Restore corresponding scroll bar value. Later clicking will use them
        for index, server in enumerate(self.parent().ServerList):
            # Get v, h by Object id
            self.parent().ScrollList[index] = scrollBarValueTable[id(server)]

        if activatedServerId is not None:
            foundActivatedItem = False

            for index, server in enumerate(self.parent().ServerList):
                if activatedServerId == id(server):
                    foundActivatedItem = True

                    # Restore scroll bar value. Later clicking will use it
                    if currentFocus >= 0:
                        self.parent().restoreScrollBarValue(currentFocus)

                    # Focus on focus
                    self.parent().setCurrentItemByIndex(index)
                    self.parent().activateItemByIndex(index, activate=True)

                    break

            # Object id should be found
            assert foundActivatedItem
        else:
            # Restore scroll bar value. Later clicking will use it
            if currentFocus >= 0:
                self.parent().restoreScrollBarValue(currentFocus)

            # Focus on focus
            self.parent().setCurrentItemByIndex(currentFocus)

    @QtCore.Slot(int, int, int)
    def handleSectionResized(self, index, oldSize, newSize):
        # Keys are string when loaded from json
        self.parent().sectionSizeTable[str(index)] = newSize


class ServerWidgetVerticalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


def toJSONMayBeNull(text):
    try:
        return Configuration.toJSON(text)
    except Exception:
        # Any non-exit exceptions

        return {}


def getSubsRemarkFromUnique(server):
    try:
        # SubscriptionWidget must be initialized before ServerWidget
        return APP().SubscriptionWidget.SubscriptionDict[server['subsId']]['remark']
    except Exception:
        # Any non-exit exceptions

        return ''


class Worker:
    def __init__(self, serverIdx, serverObj):
        self.serverIdx = serverIdx
        self.serverObj = serverObj

        # Reference
        self.serverRef = APP().ServerWidget.ServerList
        self.deletedId = APP().ServerWidget.deletedServerId

    def serverDeleted(self):
        if (
            # Fast search for deletion
            id(self.serverObj) in self.deletedId
            or self.serverIdx < 0
            or self.serverIdx >= len(self.serverRef)
        ):
            # Deleted
            return True
        else:
            return False

    def updateCallback(self, index, reference):
        raise NotImplementedError

    def updateResult(self):
        if self.serverDeleted():
            # Deleted. Do nothing
            return

        if id(self.serverRef[self.serverIdx]) == id(self.serverObj):
            # Quick update
            self.updateCallback(self.serverIdx, self.serverObj)
        else:
            # Linear find and update
            for index, server in enumerate(self.serverRef):
                if id(server) == id(self.serverObj):
                    # Found. Refresh index
                    self.serverIdx = index
                    self.updateCallback(self.serverIdx, self.serverObj)

                    # Updated
                    return

            # Should not reach here.
            self.serverIdx = -1


class PingDelayWorker(Worker, QtCore.QObject, QtCore.QRunnable):
    updateTable = QtCore.Signal(int, dict)

    def __init__(self, serverIdx, serverObj):
        super().__init__(serverIdx, serverObj)

        # Explictly called __init__
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

    def updateCallback(self, index, reference):
        self.updateTable.emit(index, reference)

    def run(self):
        if self.serverDeleted():
            # Deleted. Do nothing
            return

        try:
            result = ping3.ping(
                Intellisense.getCoreAddr(
                    Configuration.toJSON(self.serverObj['config'])
                ),
                timeout=1,
                unit='ms',
            )
        except Exception:
            # Any non-exit exceptions

            self.serverObj['delayResult'] = 'Timeout'
            self.updateResult()

            return

        if result is False or result is None:
            self.serverObj['delayResult'] = 'Timeout'
        else:
            self.serverObj['delayResult'] = f'{round(result)}ms'

        self.updateResult()


class DownSpeedWorker(Worker):
    def __init__(self, serverIdx, serverObj):
        super().__init__(serverIdx, serverObj)

        self.core = None

        self.speedValue = False
        self.totalBytes = 0

        self.testFinished = False
        self.elapsedTimer = QtCore.QElapsedTimer()

        self.networkReply = None
        self.networkAccessManager = QNetworkAccessManager()

    def updateCallback(self, index, reference):
        APP().ServerWidget.flushServerSpeedResult(index, reference)

    def abort(self):
        if self.networkReply is not None:
            self.networkReply.abort()
        else:
            self.testFinished = True

        if self.core is not None:
            self.core.stop()

    def cancelTest(self):
        self.serverObj['speedResult'] = 'Canceled'
        self.updateResult()
        self.testFinished = True

    def isFinished(self):
        return self.testFinished

    def run(self):
        if self.serverDeleted():
            self.testFinished = True

            # Deleted. Do nothing
            return

        config = self.serverObj.get('config', '')

        if not config:
            self.cancelTest()

            return

        self.serverObj['speedResult'] = 'Starting'
        self.updateResult()

        try:
            coreJSON = Configuration.toJSON(config)
            coreType = Intellisense.getCoreType(coreJSON)
        except Exception:
            # Any non-exit exceptions

            self.cancelTest()

            return

        def coreExitCallback(exitcode):
            if exitcode == Core.ExitCode.ConfigurationError:
                self.serverObj['speedResult'] = 'Invalid'
            elif exitcode == Core.ExitCode.ServerStartFailure:
                self.serverObj['speedResult'] = 'Start failed'
            else:
                self.serverObj['speedResult'] = 'Canceled'

            self.updateResult()

        if coreType == XrayCore.name():
            # Force redirect
            coreJSON['inbounds'] = [
                {
                    'tag': 'http',
                    'port': 20809,
                    'listen': '127.0.0.1',
                    'protocol': 'http',
                    'sniffing': {
                        'enabled': True,
                        'destOverride': [
                            'http',
                            'tls',
                        ],
                    },
                    'settings': {
                        'auth': 'noauth',
                        'udp': True,
                        'allowTransparent': False,
                    },
                },
            ]
            # No routing
            coreJSON['routing'] = {}

            self.core = XrayCore(waitCore=False)
            self.core.registerExitCallback(coreExitCallback)
            self.core.start(
                ujson.dumps(
                    coreJSON,
                    ensure_ascii=False,
                    escape_forward_slashes=False,
                )
            )
        elif coreType == Hysteria1.name() or coreType == Hysteria2.name():
            # Force redirect
            coreJSON['http'] = {
                'listen': '127.0.0.1:20809',
                'timeout': 300,
                'disable_udp': False,
            }

            # No socks inbounds
            coreJSON.pop('socks5', '')

            if coreType == Hysteria1.name():
                # User acl and mmdb already ignored

                self.core = Hysteria1(waitCore=False)
                self.core.registerExitCallback(coreExitCallback)
                self.core.start(
                    ujson.dumps(
                        coreJSON,
                        ensure_ascii=False,
                        escape_forward_slashes=False,
                    ),
                    '',
                    '',
                )
            else:
                self.core = Hysteria2(waitCore=False)
                self.core.registerExitCallback(coreExitCallback)
                self.core.start(
                    ujson.dumps(
                        coreJSON,
                        ensure_ascii=False,
                        escape_forward_slashes=False,
                    )
                )
        else:
            self.cancelTest()

            return

        if self.core.checkAlive():
            self.networkAccessManager.setProxy(
                QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, '127.0.0.1', 20809)
            )

            self.networkReply = self.networkAccessManager.get(
                QNetworkRequest(QtCore.QUrl('http://cachefly.cachefly.net/100mb.test'))
            )
            self.networkReply.readyRead.connect(self.handleReadyRead)
            self.networkReply.finished.connect(self.handleFinished)

            self.elapsedTimer.start()
        else:
            self.testFinished = True

    @QtCore.Slot()
    def handleReadyRead(self):
        if self.core.isAlive():
            self.totalBytes += self.networkReply.readAll().length()

            # Convert to seconds
            elapsedSecond = self.elapsedTimer.elapsed() / 1000
            downloadSpeed = self.totalBytes / elapsedSecond / 1024 / 1024

            # Has speed value
            self.speedValue = True
            self.serverObj['speedResult'] = f'{downloadSpeed:.2f} M/s'
            self.updateResult()

    @QtCore.Slot()
    def handleFinished(self):
        if self.networkReply.error() != QNetworkReply.NetworkError.NoError:
            if not self.speedValue:
                if self.core.isAlive():
                    if (
                        self.networkReply.error()
                        == QNetworkReply.NetworkError.OperationCanceledError
                    ):
                        # Canceled by application
                        self.serverObj['speedResult'] = 'Canceled'
                    else:
                        try:
                            error = self.networkReply.error().name
                        except Exception:
                            # Any non-exit exceptions

                            error = 'Unknown Error'

                        if isinstance(error, bytes):
                            # Some old version PySide6 returns it as bytes.
                            # Protect it.
                            errorString = error.decode()
                        elif isinstance(error, str):
                            errorString = error
                        else:
                            errorString = 'Unknown Error'

                        if errorString.endswith('Error'):
                            self.serverObj['speedResult'] = errorString[:-5]
                        else:
                            self.serverObj['speedResult'] = errorString
                else:
                    # Core ExitCallback has been called
                    self.testFinished = True

                    return
        else:
            if self.core.isAlive():
                self.totalBytes += self.networkReply.readAll().length()

                # Convert to seconds
                elapsedSecond = self.elapsedTimer.elapsed() / 1000
                downloadSpeed = self.totalBytes / elapsedSecond / 1024 / 1024

                self.serverObj['speedResult'] = f'{downloadSpeed:.2f} M/s'
            else:
                self.serverObj['speedResult'] = 'Start failed'

        self.core.stop()
        self.updateResult()
        self.testFinished = True


class ServerWidget(Translatable, SupportConnectedCallback, TableWidget):
    # Might be extended in the future
    HEADER_LABEL = [
        'Remark',
        'Protocol',
        'Address',
        'Port',
        'Transport',
        'TLS',
        'Subscription',
        'Latency',
        'Speed',
    ]

    DELAY_INDEX = HEADER_LABEL.index('Latency')
    SPEED_INDEX = HEADER_LABEL.index('Speed')

    # Corresponds to header label
    HEADER_LABEL_GET_FUNC = [
        lambda server: server['remark'],
        lambda server: Intellisense.getCoreProtocol(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreAddr(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCorePort(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreTransport(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreTLS(toJSONMayBeNull(server['config'])),
        lambda server: getSubsRemarkFromUnique(server),
        lambda server: server.get('delayResult', ''),
        lambda server: server.get('speedResult', ''),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # MessageBox
        self.questionSaveBox = QuestionSaveBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )
        self.questionDelete_ = QuestionDeleteBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )
        self.saveConfInfoBox = SaveConfInfo(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.progressWaitBox = ProgressWaitBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.saveChangeFirst = SaveChangeFirst(
            icon=MessageBox.Icon.Information, parent=None
        )

        # Shallow copy. Checked
        self.ServerList = self.parent().ServerList

        # Quick delete search
        self.deletedServerOb = []
        self.deletedServerId = {}

        # Handy reference
        self.plainTextEdit = self.parent().plainTextEdit

        # Handy reference
        self.editorTab = self.parent().editorTab

        # Ping Thread Pool
        self.pingThreadPool = QtCore.QThreadPool()
        self.downSpeedQueue = queue.Queue()

        self.downSpeedTimer = QtCore.QTimer()
        self.downSpeedTimer.timeout.connect(self.downSpeedTimeoutCallback)
        self.downSpeedTimer.start(1)

        # Delegate
        self.delegate = StyledItemDelegate(parent=self)
        self.setItemDelegate(self.delegate)

        # Scroll bar value list. v, h
        self.ScrollList = list([0, 0] for i in range(len(self.ServerList)))

        # Must set before flush all
        self.setColumnCount(len(ServerWidget.HEADER_LABEL))

        # Flush all data to table
        self.flushAll()

        # Install custom header
        self.setHorizontalHeader(ServerWidgetHorizontalHeader(self))

        # Horizontal header resize mode
        for index in range(self.columnCount()):
            if index < self.columnCount() - 1:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Interactive
                )
            else:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Stretch
                )

        try:
            # Restore horizontal section size
            self.sectionSizeTable = ujson.loads(APP().ServerWidgetSectionSizeTable)

            # Fill missing value
            for column in range(self.columnCount()):
                if self.sectionSizeTable.get(str(column)) is None:
                    self.sectionSizeTable[
                        str(column)
                    ] = self.horizontalHeader().defaultSectionSize()

            # Block resize callback
            self.horizontalHeader().blockSignals(True)

            for key, value in self.sectionSizeTable.items():
                self.horizontalHeader().resizeSection(int(key), value)

            # Unblock resize callback
            self.horizontalHeader().blockSignals(False)
        except Exception:
            # Any non-exit exceptions

            # Leave keys as strings since they will be
            # loaded as string from json
            self.sectionSizeTable = {
                str(column): self.horizontalHeader().defaultSectionSize()
                for column in range(self.columnCount())
            }

        self.setHorizontalHeaderLabels(
            list(_(label) for label in ServerWidget.HEADER_LABEL)
        )

        for column in range(self.horizontalHeader().count()):
            self.horizontalHeaderItem(column).setFont(QFont(APP().customFontName))

        # Install custom header
        self.setVerticalHeader(ServerWidgetVerticalHeader(self))

        # Selection
        self.setSelectionColor(Color.LIGHT_BLUE)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        contextMenuActions = [
            Action(
                _('Move Up'),
                callback=lambda: self.moveUpSelectedItem(),
                parent=self,
            ),
            Action(
                _('Move Down'),
                callback=lambda: self.moveDownSelectedItem(),
                parent=self,
            ),
            Action(
                _('Duplicate'),
                callback=lambda: self.duplicateSelectedItem(),
                parent=self,
            ),
            Action(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
                parent=self,
            ),
            Seperator(),
            SelectAllServerAction(
                callback=lambda: self.selectAll(),
                parent=self,
            ),
            Seperator(),
            ScrollToActivatedServerAction(parent=self),
            Seperator(),
            TestPingLatencyAction(parent=self),
            TestDownloadSpeedAction(parent=self),
            ClearTestResultsAction(parent=self),
            Seperator(),
            ImportFileAction(parent=self),
            ImportLinkActionWithHotKey(parent=self),
            ImportJSONActionWithHotKey(parent=self),
            Seperator(),
            ExportLinkActionWithHotKey(parent=self),
            ExportQRCodeActionWithHotKey(parent=self),
            ExportJSONActionWithHotKey(parent=self),
        ]

        self.contextMenu = Menu(*contextMenuActions)

        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

        # Signals
        self.currentItemChanged.connect(self.handleCurrentItemChanged)
        self.itemChanged.connect(self.handleItemChanged)
        self.itemSelectionChanged.connect(self.handleItemSelectionChanged)
        self.itemActivated.connect(self.handleItemActivated)

        self.doNotSwitchCallback = None

        if self.activatedItem is not None:
            self.setCurrentItem(self.activatedItem)
            # Activate it from settings
            self.activateItemByIndex(self.activatedItemIndex, activate=True)

    @property
    def activatedItemIndex(self):
        try:
            return int(APP().ActivatedItemIndex)
        except Exception:
            # Any non-exit exceptions

            return -1

    @property
    def activatedItem(self):
        return self.item(self.activatedItemIndex, 0)

    @property
    def currentFocus(self):
        try:
            # Get current index from tab
            return int(self.editorTab.tabText(0).split(' - ')[0]) - 1
        except Exception:
            # Any non-exit exceptions

            return -1

    def resizeHorizontalHeaderSection(self, oldSize, newSize):
        factor = newSize / oldSize

        for index in range(self.columnCount()):
            self.horizontalHeader().resizeSection(
                index, round(self.horizontalHeader().sectionSize(index) * factor)
            )

    def flushRow(self, row, server):
        for column in range(self.columnCount()):
            oldItem = self.item(row, column)
            newItem = QTableWidgetItem(
                ServerWidget.HEADER_LABEL_GET_FUNC[column](server)
            )

            if oldItem is None:
                # Item does not exists
                newItem.setFont(QFont(APP().customFontName))

                if (
                    ServerWidget.HEADER_LABEL[column] == 'Latency'
                    or ServerWidget.HEADER_LABEL[column] == 'Speed'
                ):
                    # Test results. Align right and vcenter
                    newItem.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignRight
                        | QtCore.Qt.AlignmentFlag.AlignVCenter
                    )
            else:
                # Use existing
                newItem.setFont(oldItem.font())
                newItem.setForeground(oldItem.foreground())

                if oldItem.textAlignment() != 0:
                    newItem.setTextAlignment(oldItem.textAlignment())

            if ServerWidget.HEADER_LABEL[column] == 'Remark':
                # Remark is editable
                newItem.setFlags(
                    QtCore.Qt.ItemFlag.ItemIsEnabled
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                    | QtCore.Qt.ItemFlag.ItemIsEditable
                )
            else:
                newItem.setFlags(
                    QtCore.Qt.ItemFlag.ItemIsEnabled
                    | QtCore.Qt.ItemFlag.ItemIsSelectable
                )

            self.setItem(row, column, newItem)

    def flushAll(self):
        if self.rowCount() == 0:
            # Should insert row
            for row, server in enumerate(self.ServerList):
                self.insertRow(row)
                self.flushRow(row, server)
        else:
            for row, server in enumerate(self.ServerList):
                self.flushRow(row, server)

    def saveScrollBarValue(self, index):
        assert len(self.ScrollList) == len(self.ServerList)

        if 0 <= index < len(self.ScrollList):
            self.ScrollList[index] = [
                self.plainTextEdit.verticalScrollBar().value(),
                self.plainTextEdit.horizontalScrollBar().value(),
            ]

    def restoreScrollBarValue(self, index):
        assert len(self.ScrollList) == len(self.ServerList)

        if 0 <= index < len(self.ScrollList):
            self.plainTextEdit.verticalScrollBar().setValue(self.ScrollList[index][0])
            self.plainTextEdit.horizontalScrollBar().setValue(self.ScrollList[index][1])

    def appendScrollBarEntry(self):
        self.ScrollList.append([0, 0])

    def setPlainText(self, text, block=False, disabled=False):
        if block:
            self.plainTextEdit.blockSignals(True)
            self.plainTextEdit.setPlainText(text)
            self.plainTextEdit.blockSignals(False)
        else:
            self.plainTextEdit.setPlainText(text)

        self.plainTextEdit.setDisabled(disabled)

    def syncRemarkByIndex(self, index):
        assert self.rowCount() == len(self.ServerList)

        if self.item(index, 0) is None:
            return

        if self.ServerList[index]['remark'] != self.item(index, 0).text():
            self.ServerList[index]['remark'] = self.item(index, 0).text()

            # Only one tab currently. Refresh tab title
            self.editorTab.setTabText(
                0, f'{index + 1} - {self.ServerList[index]["remark"]}'
            )

            remarkModified = True
        else:
            remarkModified = False

        # Avoid unnecessary encode/write, etc.
        if remarkModified:
            ServerStorage.sync()

    def activateItemByIndex(self, index, activate=True):
        super().activateItemByIndex(index, activate)

        if activate:
            APP().ActivatedItemIndex = str(index)

    def setCurrentItemByIndex(self, index):
        self.setCurrentItem(self.item(index, 0))

    def swapItem(self, index0, index1):
        swapListItem(self.ServerList, index0, index1)
        swapListItem(self.ScrollList, index0, index1)

        # Server storage sync is done by caller!!!

        self.flushRow(index0, self.ServerList[index0])
        self.flushRow(index1, self.ServerList[index1])

        if index0 == self.activatedItemIndex:
            # De-activate
            self.activateItemByIndex(index0, activate=False)
            # Activate
            self.activateItemByIndex(index1, activate=True)
        elif index1 == self.activatedItemIndex:
            # De-activate
            self.activateItemByIndex(index1, activate=False)
            # Activate
            self.activateItemByIndex(index0, activate=True)

    def selectMultipleRow(self, indexes, clearCurrentSelection):
        if clearCurrentSelection:
            self.selectionModel().clearSelection()

        selection = self.selectionModel().selection()

        for index in indexes:
            selection.select(
                self.model().index(index, 0),
                self.model().index(index, self.columnCount() - 1),
            )

        self.selectionModel().select(
            selection, QtCore.QItemSelectionModel.SelectionFlag.Select
        )

    def moveUpItemByIndex(self, index):
        if index <= 0 or index >= len(self.ServerList):
            # The top item, or does not exist. Do nothing
            return

        self.swapItem(index, index - 1)

    @needSaveChanges
    def moveUpSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        currentFocus = self.currentFocus

        if currentFocus >= 0:
            self.saveScrollBarValue(currentFocus)

        for index in indexes:
            self.moveUpItemByIndex(index)

        # Sync it
        ServerStorage.sync()

        # Don't use setCurrentItemXXX since it will
        # trigger handleCurrentItemChanged. Just switch context
        # and change index
        self.switchContext(indexes[-1] - 1)

        self.blockSignals(True)
        self.setCurrentIndex(self.indexFromItem(self.item(indexes[-1] - 1, 0)))
        self.blockSignals(False)

        self.selectMultipleRow(
            list(index - 1 for index in indexes), clearCurrentSelection=True
        )

    def moveDownItemByIndex(self, index):
        if index < 0 or index >= len(self.ServerList) - 1:
            # The bottom item, or does not exist. Do nothing
            return

        self.swapItem(index, index + 1)

    @needSaveChanges
    def moveDownSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        currentFocus = self.currentFocus

        if currentFocus >= 0:
            self.saveScrollBarValue(currentFocus)

        for index in indexes[::-1]:
            self.moveDownItemByIndex(index)

        # Sync it
        ServerStorage.sync()

        # Don't use setCurrentItemXXX since it will
        # trigger handleCurrentItemChanged. Just switch context
        # and change index
        self.switchContext(indexes[0] + 1)

        self.blockSignals(True)
        self.setCurrentIndex(self.indexFromItem(self.item(indexes[0] + 1, 0)))
        self.blockSignals(False)

        self.selectMultipleRow(
            list(index + 1 for index in indexes), clearCurrentSelection=True
        )

    @needSaveChanges
    def duplicateSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            if 0 <= index < len(self.ServerList):
                # Do not clone subsId
                APP().ServerWidget.importServer(
                    self.ServerList[index]['remark'],
                    self.ServerList[index]['config'],
                )

        # Sync it
        ServerStorage.sync()

    def deleteItemByIndex(self, indexes, syncStorage=False):
        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return 0

        if self.activatedItemIndex in indexes:
            takedActivated = True
        else:
            takedActivated = False

        for i in range(len(indexes)):
            takedRow = indexes[i] - i

            self.blockSignals(True)
            self.removeRow(takedRow)
            self.blockSignals(False)

            # Added for deletion search
            self.deletedServerOb.append(self.ServerList[takedRow])
            self.deletedServerId[id(self.ServerList[takedRow])] = True

            self.ServerList.pop(takedRow)
            self.ScrollList.pop(takedRow)

            if not takedActivated and takedRow < self.activatedItemIndex:
                APP().ActivatedItemIndex = str(self.activatedItemIndex - 1)

        if syncStorage:
            # Sync it
            ServerStorage.sync()

        if takedActivated:
            # Set invalid first
            APP().ActivatedItemIndex = str(-1)

            if APP().isConnected():
                # Trigger disconnect
                APP().tray.ConnectAction.trigger()

        # Don't use setCurrentItemXXX since the
        # selection may not be changed. Just switch context
        # and change index

        # Don't use currentFocus since it may have been deleted. Get
        # current row from self
        self.switchContext(self.currentRow())

        self.blockSignals(True)
        self.setCurrentIndex(self.indexFromItem(self.item(self.currentRow(), 0)))
        self.blockSignals(False)

        return len(indexes)

    @needSaveChanges
    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        self.questionDelete_.isMulti = bool(len(indexes) > 1)
        self.questionDelete_.possibleRemark = (
            f'{indexes[0] + 1} - {self.ServerList[indexes[0]]["remark"]}'
        )
        self.questionDelete_.setText(self.questionDelete_.getText())

        if self.questionDelete_.exec() == enumValueWrapper(
            MessageBox.StandardButton.No
        ):
            # Do not delete
            return

        self.deleteItemByIndex(indexes, syncStorage=True)

    def flushServerResultByColumn(self, row, column, server):
        oldItem = self.item(row, column)
        newItem = QTableWidgetItem(ServerWidget.HEADER_LABEL_GET_FUNC[column](server))

        if oldItem is None:
            # Item does not exists
            newItem.setFont(QFont(APP().customFontName))
            # Test results. Align right and vcenter
            newItem.setTextAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
        else:
            # Use existing
            newItem.setFont(oldItem.font())
            newItem.setForeground(oldItem.foreground())

            if oldItem.textAlignment() != 0:
                newItem.setTextAlignment(oldItem.textAlignment())

        newItem.setFlags(
            QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        )

        self.setItem(row, column, newItem)

    def flushServerDelayResult(self, row, server):
        self.flushServerResultByColumn(row, ServerWidget.DELAY_INDEX, server)

    def flushServerSpeedResult(self, row, server):
        self.flushServerResultByColumn(row, ServerWidget.SPEED_INDEX, server)

    def testPingDelayByReference(self, indexes, references):
        for index, reference in zip(indexes, references):
            worker = PingDelayWorker(index, reference)
            worker.setAutoDelete(True)
            worker.updateTable.connect(self.flushServerDelayResult)

            self.pingThreadPool.start(worker)

    @QtCore.Slot()
    def downSpeedTimeoutCallback(self):
        try:
            index, server = self.downSpeedQueue.get_nowait()
        except queue.Empty:
            # Queue is empty

            return

        def testDownloadSpeed(counter=0, timeout=5000, step=100):
            worker = DownSpeedWorker(index, server)
            worker.run()

            while not APP().exiting and not worker.isFinished() and counter < timeout:
                eventLoopWait(step)

                counter += step

            if not worker.isFinished():
                worker.abort()

                while not worker.isFinished():
                    eventLoopWait(step)

            if APP().exiting:
                # Stop timer
                self.downSpeedTimer.stop()

        testDownloadSpeed()

    def testDownSpeedByReference(self, indexes, references):
        for index, reference in zip(indexes, references):
            # Served by FIFO
            try:
                self.downSpeedQueue.put_nowait((index, reference))
            except Exception:
                # Any non-exit exceptions

                pass

    def testItemDelayByIndex(self, indexes):
        references = list(self.ServerList[index] for index in indexes)

        self.testPingDelayByReference(indexes, references)

    def testItemSpeedByIndex(self, indexes):
        references = list(self.ServerList[index] for index in indexes)

        self.testDownSpeedByReference(indexes, references)

    def testSelectedItemDelay(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        APP().testPerformed = True

        self.testItemDelayByIndex(indexes)

    def testSelectedItemSpeed(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        APP().testPerformed = True

        self.testItemSpeedByIndex(indexes)

    def clearSelectedItemTestResultsByIndex(self, indexes):
        for index in indexes:
            server = self.ServerList[index]

            server['delayResult'] = ''
            server['speedResult'] = ''

            self.flushServerDelayResult(index, server)
            self.flushServerSpeedResult(index, server)

    def clearSelectedItemTestResults(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        self.clearSelectedItemTestResultsByIndex(indexes)

        # Sync it
        ServerStorage.sync()

    def setEmptyItem(self):
        # Click empty.
        self.setPlainText('', block=True, disabled=True)
        # Only one tab currently. Clear tab title
        self.editorTab.setTabText(0, '')
        self.blockSignals(True)
        self.setCurrentIndex(self.indexFromItem(None))
        self.blockSignals(False)

    def switchContext(self, index):
        self.doNotSwitchCallback = None

        if index < 0 or index >= len(self.ServerList):
            # Click empty.
            self.setEmptyItem()
        else:
            self.setPlainText(self.ServerList[index]['config'], block=True)
            # Only one tab currently. Refresh tab title
            self.editorTab.setTabText(
                0, f'{index + 1} - {self.ServerList[index]["remark"]}'
            )
            # Restore scroll bar
            self.restoreScrollBarValue(index)

    @QtCore.Slot(QTableWidgetItem, QTableWidgetItem)
    def handleCurrentItemChanged(self, currItem, prevItem):
        currRow = -1 if currItem is None else currItem.row()
        prevRow = -1 if prevItem is None else prevItem.row()

        def doNotSwitchCallback(tableWidgetItem):
            self.blockSignals(True)
            self.setCurrentIndex(self.indexFromItem(tableWidgetItem))
            self.blockSignals(False)

        def doNotSwitch():
            self.doNotSwitchCallback = functools.partial(doNotSwitchCallback, prevItem)

        self.saveScrollBarValue(prevRow)

        if APP().ServerWidget is not None and APP().ServerWidget.modified:
            choice = self.questionSaveBox.exec()

            if choice == enumValueWrapper(MessageBox.ButtonRole.AcceptRole):
                # Save
                if APP().ServerWidget.SaveAsServerAction.save(
                    successCallback=lambda: self.switchContext(currRow),
                ):
                    pass
                else:
                    # Do not switch
                    doNotSwitch()

            elif choice == enumValueWrapper(MessageBox.ButtonRole.DestructiveRole):
                # Discard
                self.switchContext(currRow)

                APP().ServerWidget.markAsSaved()  # Fake saved

            elif choice == enumValueWrapper(MessageBox.ButtonRole.RejectRole):
                # Cancel. Do not switch
                doNotSwitch()
        else:
            self.switchContext(currRow)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemChanged(self, item):
        self.syncRemarkByIndex(item.row())

    @QtCore.Slot()
    def handleItemSelectionChanged(self):
        if callable(self.doNotSwitchCallback):
            self.doNotSwitchCallback()

    @QtCore.Slot(QTableWidgetItem)
    def handleItemActivated(self, item):
        if self.activatedItemIndex == item.row():
            # Same item activated. Do nothing
            return

        if APP().ServerWidget is not None and APP().ServerWidget.modified:
            self.saveChangeFirst.exec()

            return

        if APP().tray.ConnectAction.isConnecting():
            if PLATFORM != 'Darwin':
                # Show the MessageBox asynchronously
                self.progressWaitBox.open()
            else:
                # Show the MessageBox and wait for user to close it
                self.progressWaitBox.exec()

            return

        if self.activatedItemIndex >= 0:
            # De-activate
            self.activateItemByIndex(self.activatedItemIndex, activate=False)

        newIndex = item.row()

        # Activate
        self.activateItemByIndex(newIndex, activate=True)

        if APP().isConnected():
            APP().tray.ConnectAction.reconnectAction()

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)

    def connectedCallback(self):
        self.setSelectionColor(Color.LIGHT_RED_)
        # Reactivate with possible color
        self.activateItemByIndex(self.activatedItemIndex)

    def disconnectedCallback(self):
        self.setSelectionColor(Color.LIGHT_BLUE)
        # Reactivate with possible color
        self.activateItemByIndex(self.activatedItemIndex)

    def retranslate(self):
        self.setHorizontalHeaderLabels(
            list(_(label) for label in ServerWidget.HEADER_LABEL)
        )


class EditConfigurationWidget(MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Server Configuration'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        # MessageBox
        self.questionSaveBox = QuestionSaveBox(
            icon=MessageBox.Icon.Question, parent=self
        )
        self.restoreErrorBox = MessageBox(parent=self)

        try:
            self.StorageObj = ServerStorage.toObject(APP().Configuration)
            # Check model. Shallow copy
            self.ServerList = self.StorageObj['model']
        except Exception:
            # Any non-exit exceptions

            self.StorageObj = ServerStorage.init()
            # Shallow copy
            self.ServerList = self.StorageObj['model']

            # Clear it
            ServerStorage.clear()

            Configuration.corruptedError(self.restoreErrorBox)

        # Modified flag
        self.modified = False
        self.modifiedMark = ' *'

        # Initialize PlainTextEdit
        @QtCore.Slot(bool)
        def handleModification(changed):
            if changed:
                self.plainTextEdit.document().setModified(False)
                self.markAsModified()

        self.plainTextEdit = ZoomablePlainTextEdit(parent=self)

        self.plainTextEdit.modificationChanged.connect(handleModification)
        self.plainTextEdit.setDisabled(True)

        self.showTabAndSpacesIfNecessary()

        self.lineColumnLabel = QLabel('1:1 0')
        self.statusBar().addPermanentWidget(self.lineColumnLabel)

        @QtCore.Slot()
        def handleCursorPositionChanged():
            cursor = self.plainTextEdit.textCursor()

            self.lineColumnLabel.setText(
                f'{cursor.blockNumber() + 1}:{cursor.columnNumber() + 1} {cursor.position()}'
            )

        self.plainTextEdit.cursorPositionChanged.connect(handleCursorPositionChanged)

        # Theme
        self.plainTextEdit.setStyleSheet(
            DraculaTheme.getStyleSheet(
                widgetName='QPlainTextEdit',
                fontFamily=APP().customFontName,
            )
        )

        self.theme = DraculaTheme(self.plainTextEdit.document())

        try:
            font = self.plainTextEdit.font()
            font.setPointSize(int(APP().ServerWidgetPointSize))

            self.plainTextEdit.setFont(font)
        except Exception:
            # Any non-exit exceptions

            pass

        self.serverEditorTabWidget = QWidget()
        self.serverEditorTabWidgetLayout = QVBoxLayout(self.serverEditorTabWidget)
        self.serverEditorTabWidgetLayout.addWidget(self.plainTextEdit)

        # Advance for self.serverWidget
        self.editorTab = QTabWidget(self)
        # Note: Set tab text later
        self.editorTab.addTab(self.serverEditorTabWidget, '')

        self.serverWidget = ServerWidget(parent=self)

        # Buttons
        self.moveUpButton = PushButton(_('Move Up'))
        self.moveUpButton.clicked.connect(
            lambda: self.serverWidget.moveUpSelectedItem()
        )
        self.moveDownButton = PushButton(_('Move Down'))
        self.moveDownButton.clicked.connect(
            lambda: self.serverWidget.moveDownSelectedItem()
        )
        self.duplicateButton = PushButton(_('Duplicate'))
        self.duplicateButton.clicked.connect(
            lambda: self.serverWidget.duplicateSelectedItem()
        )
        self.deleteButton = PushButton(_('Delete'))
        self.deleteButton.clicked.connect(
            lambda: self.serverWidget.deleteSelectedItem()
        )

        # Button Layout
        self.buttonWidget = QWidget()
        self.buttonWidgetLayout = QGridLayout(parent=self.buttonWidget)
        self.buttonWidgetLayout.addWidget(self.moveUpButton, 0, 0)
        self.buttonWidgetLayout.addWidget(self.moveDownButton, 0, 1)
        self.buttonWidgetLayout.addWidget(self.duplicateButton, 1, 0)
        self.buttonWidgetLayout.addWidget(self.deleteButton, 1, 1)

        self.serverTabWidget = QWidget()
        self.serverTabWidgetLayout = QVBoxLayout(self.serverTabWidget)
        self.serverTabWidgetLayout.addWidget(self.serverWidget)
        self.serverTabWidgetLayout.addWidget(self.buttonWidget)

        self.serverTab = TabWidget(self)
        self.serverTab.addTab(self.serverTabWidget, _('Server'))

        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.serverTab)
        self.splitter.addWidget(self.editorTab)
        self.splitter.setStretchFactor(0, 8)
        self.splitter.setStretchFactor(1, 5)

        if APP().HideEditor == Switch.ON_:
            APP().processEvents()

            self.editorTab.hide()

        self.fakeCentralWidget = QWidget()

        self.fakeCentralWidgetLayout = QHBoxLayout(self.fakeCentralWidget)
        self.fakeCentralWidgetLayout.addWidget(self.splitter)

        self.setCentralWidget(self.fakeCentralWidget)

        # Menu actions
        fileMenu = {
            'name': 'File',
            'actions': [
                NewBlankServerAction(parent=self),
                Seperator(),
                SelectAllServerAction(
                    callback=lambda: self.serverWidget.selectAll(),
                    parent=self,
                ),
                Seperator(),
                ScrollToActivatedServerAction(parent=self.serverWidget),
                Seperator(),
                TestPingLatencyAction(parent=self.serverWidget),
                TestDownloadSpeedAction(parent=self.serverWidget),
                ClearTestResultsAction(parent=self.serverWidget),
                Seperator(),
                ImportFileAction(parent=self),
                ImportLinkActionWithHotKey(parent=self),
                ImportJSONActionWithHotKey(parent=self),
                Seperator(),
                ExportLinkActionWithHotKey(parent=self),
                ExportQRCodeActionWithHotKey(parent=self),
                ExportJSONActionWithHotKey(parent=self),
                Seperator(),
                SaveAsServerAction(parent=self),
                SaveAsFileAction(parent=self),
                Seperator(),
                ExitAction(parent=self),
            ],
        }

        editMenu = {
            'name': 'Edit',
            'actions': [
                UndoAction(parent=self),
                RedoAction(parent=self),
                Seperator(),
                CutAction(parent=self),
                CopyAction(parent=self),
                PasteAction(parent=self),
                Seperator(),
                SelectAllTextAction(parent=self),
                Seperator(),
                IndentAction(parent=self),
            ],
        }

        viewMenu = {
            'name': 'View',
            'actions': [
                ZoomInAction(parent=self),
                ZoomOutAction(parent=self),
                Seperator(),
                ShowHideEditorAction(parent=self),
            ],
        }

        subsMenu = {
            'name': 'Subscription',
            'actions': [
                UpdateSubsUseCurrentProxyAction(parent=self),
                UpdateSubsForceProxyAction(parent=self),
                UpdateSubsNoProxyAction(parent=self),
                Seperator(),
                EditSubscriptionAction(parent=self),
            ],
        }

        helpMenu = {
            'name': 'Help',
            'actions': [
                ShowLogAction(parent=self),
                Seperator(),
                CheckForUpdatesAction(parent=self),
                AboutAction(parent=self),
            ],
        }

        # Menus
        for menuDict in (fileMenu, editMenu, viewMenu, subsMenu, helpMenu):
            menuName = menuDict['name']
            menuObjName = f'_{menuName}Menu'
            menu = Menu(*menuDict['actions'], title=_(menuName), parent=self.menuBar())

            for action in menuDict['actions']:
                if isinstance(action, Action):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

            # Set reference
            setattr(self, menuObjName, menu)

            self.menuBar().addMenu(menu)

    def setWidthAndHeight(self):
        try:
            self.setGeometry(
                100,
                100,
                *list(int(size) for size in APP().ServerWidgetWindowSize.split(',')),
            )
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 1800, 960)

    def deleteItemByIndex(self, indexes, syncStorage=False):
        return self.serverWidget.deleteItemByIndex(indexes, syncStorage)

    def deleteItemByUnique(self, unique, syncStorage=False):
        return self.deleteItemByIndex(
            list(
                index
                for index, server in enumerate(self.ServerList)
                if server.get('subsId', '') == unique
            ),
            syncStorage=syncStorage,
        )

    def importServer(self, remark, config, subsId='', syncStorage=False):
        server = {
            'remark': remark,
            'config': config,
            'subsId': subsId,
        }

        self.ServerList.append(server)

        if syncStorage:
            # Sync it
            ServerStorage.sync()

        row = self.serverWidget.rowCount()

        self.serverWidget.insertRow(row)
        self.serverWidget.appendScrollBarEntry()
        self.serverWidget.flushRow(row, server)

        if len(self.ServerList) == 1:
            # The first one. Click it
            self.serverWidget.setCurrentItemByIndex(0)

            # Try to be user-friendly in some extreme cases
            if not APP().isConnected():
                # Activate automatically
                self.serverWidget.activateItemByIndex(0)

    def showTabAndSpacesIfNecessary(self):
        textOption = QTextOption()

        if APP().ShowTabAndSpacesInEditor == Switch.ON_:
            textOption.setFlags(QTextOption.Flag.ShowTabsAndSpaces)

        self.plainTextEdit.document().setDefaultTextOption(textOption)
        # Reset. Set
        self.plainTextEdit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.plainTextEdit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    @property
    def activatedItemIndex(self):
        return self.serverWidget.activatedItemIndex

    @property
    def selectedIndex(self):
        return self.serverWidget.selectedIndex

    @property
    def rowCount(self):
        return self.serverWidget.rowCount()

    @property
    def currentFocus(self):
        return self.serverWidget.currentFocus

    @property
    def saveChangeFirst(self):
        return self.serverWidget.saveChangeFirst

    @property
    def deletedServerId(self):
        return self.serverWidget.deletedServerId

    @property
    def pingThreadPool(self):
        return self.serverWidget.pingThreadPool

    def flushServerSpeedResult(self, row, server):
        self.serverWidget.flushServerSpeedResult(row, server)

    def saveScrollBarValue(self, index):
        self.serverWidget.saveScrollBarValue(index)

    def restoreScrollBarValue(self, index):
        self.serverWidget.restoreScrollBarValue(index)

    def resizeHorizontalHeaderSection(self, oldSize, newSize):
        self.serverWidget.resizeHorizontalHeaderSection(oldSize, newSize)

    def questionSave(self):
        # Save current scroll bar value
        currentFocus = self.currentFocus

        if currentFocus >= 0:
            self.saveScrollBarValue(currentFocus)
        else:
            # No item selected. Save nothing
            pass

        if self.modified:
            choice = self.questionSaveBox.exec()

            if choice == enumValueWrapper(MessageBox.ButtonRole.AcceptRole):
                # Save
                # If save success, close the window.
                return self.SaveAsServerAction.save(successCallback=lambda: self.hide())

            if choice == enumValueWrapper(MessageBox.ButtonRole.DestructiveRole):
                # Discard
                self.hide()
                self.serverWidget.setEmptyItem()
                self.markAsSaved()  # Fake saved

                return True

            if choice == enumValueWrapper(MessageBox.ButtonRole.RejectRole):
                # Cancel. Do nothing
                return False
        else:
            self.hide()

            return True

    def markAsModified(self):
        self.modified = True

        self.setWindowTitle(_('Edit Server Configuration') + self.modifiedMark)

    def markAsSaved(self):
        self.modified = False

        self.setWindowTitle(_('Edit Server Configuration'))

    def closeEvent(self, event):
        event.ignore()

        self.syncSettings()
        self.questionSave()

    def syncSettings(self):
        APP().ServerWidgetWindowSize = (
            f'{self.geometry().width()},{self.geometry().height()}'
        )
        APP().ServerWidgetSectionSizeTable = ujson.dumps(
            self.serverWidget.sectionSizeTable,
            ensure_ascii=False,
            escape_forward_slashes=False,
        )
        APP().ServerWidgetPointSize = str(self.plainTextEdit.font().pointSize())

    def retranslate(self):
        with StateContext(self):
            if self.modified:
                # Keep modified mark
                self.setWindowTitle(_('Edit Server Configuration') + self.modifiedMark)
            else:
                self.setWindowTitle(_(self.windowTitle()))
