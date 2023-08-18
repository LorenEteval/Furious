from Furious.Action.Import import ImportLinkAction, ImportJSONAction
from Furious.Action.Export import ExportLinkAction, ExportJSONAction, ExportQRCodeAction
from Furious.Core.Intellisense import Intellisense
from Furious.Core.Configuration import Configuration
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
    GOLDEN_RATIO,
    Color,
)
from Furious.Utility.Utility import (
    Base64Encoder,
    StateContext,
    ServerStorage,
    Switch,
    SupportConnectedCallback,
    bootstrapIcon,
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
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QStyledItemDelegate,
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
import ujson
import logging
import functools

logger = logging.getLogger(__name__)


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


class ScrollToActivatedServerAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Scroll To Activated Server'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_G,
            )
        )

    def triggeredCallback(self, checked):
        if APP().MainWidget.modified:
            self.parent().saveChangeFirst.exec()

            return

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

    if choice == MessageBox.ButtonRole.AcceptRole.value:
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
            self.parent().normalServerWidget.flushRow(
                myFocusIndex, myServerList[myFocusIndex]
            )

            # Sync it
            ServerStorage.sync()

            self.parent().markAsSaved()

            if callable(successCallback):
                successCallback()

            if myFocusIndex == self.parent().activatedItemIndex:
                # Activated configuration modified

                if server and APP().tray.ConnectAction.isConnected():
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
        self.parent().plainTextEdit.selectAll()


class IndentAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Indent...'), **kwargs)

        self.indentSpinBox = IndentSpinBox()
        self.indentFailure = JSONErrorBox(icon=MessageBox.Icon.Critical)

    def triggeredCallback(self, checked):
        choice = self.indentSpinBox.exec()

        if choice == QDialog.DialogCode.Accepted.value:
            myText = self.parent().plainTextEdit.toPlainText()

            if myText == '':
                # Empty. Do nothing
                return

            try:
                myJSON = ujson.loads(myText)
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


class RoutingAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Edit Routing...'), **kwargs)

    def triggeredCallback(self, checked):
        APP().editRoutingWidget.show()


class ShowLogAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Show Log...'), **kwargs)

    def triggeredCallback(self, checked):
        APP().logViewerWidget.showMaximized()


class WhetherToUpdateInfoBox(MessageBox):
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
        lambda x, y: x + y,
        list(
            int(ver) * weight
            for ver, weight in zip(
                version.split('.'), [major_weight, minor_weight, patch_weight]
            )
        ),
    )


class CheckForUpdatesAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Check For Updates'), **kwargs)

        self.networkAccessManager = QNetworkAccessManager(parent=self)
        self.networkReply = None

        self.checkForUpdateErrorBox = MessageBox(
            icon=MessageBox.Icon.Critical, parent=self.parent()
        )
        self.whetherToUpdateInfoBox = WhetherToUpdateInfoBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.isLatestVersionInfoBox = MessageBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )

    def triggeredCallback(self, checked):
        proxyServer = APP().tray.ConnectAction.proxyServer

        if proxyServer:
            logger.info(f'check for updates uses proxy server {proxyServer}')

            # Checked. split should not throw exceptions
            proxyHost, proxyPort = proxyServer.split(':')

            # Checked. int(proxyPort) should not throw exceptions
            self.networkAccessManager.setProxy(
                QNetworkProxy(
                    QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort)
                )
            )
        else:
            self.networkAccessManager.setProxy(
                QNetworkProxy(QNetworkProxy.ProxyType.DefaultProxy)
            )

        apiUrl = (
            f'https://api.github.com/repos/'
            f'{APPLICATION_REPO_OWNER_NAME}/{APPLICATION_REPO_NAME}/releases/latest'
        )

        self.networkReply = self.networkAccessManager.get(
            QNetworkRequest(QtCore.QUrl(apiUrl))
        )

        @QtCore.Slot()
        def finishedCallback():
            if self.networkReply.error() != QNetworkReply.NetworkError.NoError:
                logger.error(
                    f'check for updates failed. {self.networkReply.errorString()}'
                )

                self.checkForUpdateErrorBox.setWindowTitle(_(APPLICATION_NAME))
                self.checkForUpdateErrorBox.setText(_('Check for updates failed.'))

                # Show the MessageBox and wait for user to close it
                self.checkForUpdateErrorBox.exec()
            else:
                logger.info('check for updates success')

                # b'...'
                data = (
                    str(self.networkReply.readAll())[2:-1]
                    .encode('utf-8')
                    .decode('unicode_escape')
                )

                info = ujson.loads(data)

                if versionToNumber(info['tag_name']) > versionToNumber(
                    APPLICATION_VERSION
                ):
                    self.whetherToUpdateInfoBox.version = info['tag_name']
                    self.whetherToUpdateInfoBox.setWindowTitle(_(APPLICATION_NAME))
                    self.whetherToUpdateInfoBox.setStandardButtons(
                        MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
                    )
                    self.whetherToUpdateInfoBox.setText(
                        _('New version available: ') + info['tag_name']
                    )
                    self.whetherToUpdateInfoBox.setInformativeText(
                        _('Go to download page?')
                    )

                    # Show the MessageBox and wait for user to close it
                    if (
                        self.whetherToUpdateInfoBox.exec()
                        == MessageBox.StandardButton.Yes.value
                    ):
                        if QDesktopServices.openUrl(QtCore.QUrl(info['html_url'])):
                            logger.info('open download page success')
                        else:
                            logger.error('open download page failed')
                    else:
                        # Do nothing
                        pass
                else:
                    self.isLatestVersionInfoBox.setWindowTitle(_(APPLICATION_NAME))
                    self.isLatestVersionInfoBox.setText(
                        _(f'{APPLICATION_NAME} is already the latest version.')
                    )
                    self.isLatestVersionInfoBox.setInformativeText(
                        _(f'Thank you for using {APPLICATION_NAME}.')
                    )

                    # Show the MessageBox and wait for user to close it
                    self.isLatestVersionInfoBox.exec()

        self.networkReply.finished.connect(finishedCallback)


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


class NormalServerHorizontalHeader(HeaderView):
    class SortOrder:
        Ascending_ = False
        Descending = True

    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

        self.sectionClicked.connect(self.handleSectionClicked)
        self.sectionResized.connect(self.handleSectionResized)

        self.sortOrderTable = list(
            NormalServerHorizontalHeader.SortOrder.Ascending_
            for i in range(self.parent().columnCount())
        )

    @QtCore.Slot(int)
    def handleSectionClicked(self, clickedIndex):
        if APP().MainWidget.modified:
            self.parent().saveChangeFirst.exec()

            return

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
            key=lambda x: NormalServerWidget.HEADER_LABEL_GET_FUNC[clickedIndex](x),
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


class NormalServerVerticalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


def toJSONMayBeNull(text):
    try:
        return ujson.loads(text)
    except Exception:
        # Any non-exit exceptions

        return {}


class NormalServerWidget(Translatable, SupportConnectedCallback, TableWidget):
    # Might be extended in the future
    HEADER_LABEL = [
        'Remark',
        'Protocol',
        'Address',
        'Port',
        'Transport',
        'TLS',
    ]

    # Corresponds to header label
    HEADER_LABEL_GET_FUNC = [
        lambda server: server['remark'],
        lambda server: Intellisense.getCoreProtocol(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreAddr(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCorePort(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreTransport(toJSONMayBeNull(server['config'])),
        lambda server: Intellisense.getCoreTLS(toJSONMayBeNull(server['config'])),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # MessageBox
        self.questionSaveBox = QuestionSaveBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )
        self.questionDel0Box = QuestionDeleteBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )
        self.saveConfInfoBox = SaveConfInfo(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.progressWaitBox = ProgressWaitBox(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )
        self.saveChangeFirst = SaveChangeFirst(
            icon=MessageBox.Icon.Information, parent=self.parent()
        )

        # Shallow copy. Checked
        self.ServerList = self.parent().ServerList

        # Handy reference
        self.plainTextEdit = self.parent().plainTextEdit

        # Handy reference
        self.editorTab = self.parent().editorTab

        # Delegate
        self.delegate = StyledItemDelegate(parent=self)
        self.setItemDelegate(self.delegate)

        # Scroll bar value list. v, h
        self.ScrollList = list([0, 0] for i in range(len(self.ServerList)))

        # Must set before flush all
        self.setColumnCount(len(NormalServerWidget.HEADER_LABEL))

        # Flush all data to table
        self.flushAll()

        # Install custom header
        self.setHorizontalHeader(NormalServerHorizontalHeader(self))

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
                str(row): self.horizontalHeader().defaultSectionSize()
                for row in range(self.columnCount())
            }

        self.setHorizontalHeaderLabels(
            list(_(label) for label in NormalServerWidget.HEADER_LABEL)
        )

        for column in range(self.horizontalHeader().count()):
            self.horizontalHeaderItem(column).setFont(QFont(APP().customFontName))

        # Install custom header
        self.setVerticalHeader(NormalServerVerticalHeader(self))

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

    def flushRow(self, row, server):
        for column in range(self.columnCount()):
            oldItem = self.item(row, column)
            newItem = QTableWidgetItem(
                NormalServerWidget.HEADER_LABEL_GET_FUNC[column](server)
            )

            if oldItem is None:
                # Item does not exists
                newItem.setFont(QFont(APP().customFontName))
            else:
                # Use existing
                newItem.setFont(oldItem.font())
                newItem.setForeground(oldItem.foreground())

            if column == 0:
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
            shouldInsertRow = True
        else:
            shouldInsertRow = False

        for row, server in enumerate(self.ServerList):
            if shouldInsertRow:
                self.insertRow(row)

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

    def moveUpSelectedItem(self):
        if APP().MainWidget.modified:
            self.saveChangeFirst.exec()

            return

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

    def moveDownSelectedItem(self):
        if APP().MainWidget.modified:
            self.saveChangeFirst.exec()

            return

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

    def duplicateSelectedItem(self):
        if APP().MainWidget.modified:
            self.saveChangeFirst.exec()

            return

        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            if 0 <= index < len(self.ServerList):
                APP().MainWidget.importServer(**self.ServerList[index])

        # Sync it
        ServerStorage.sync()

    def deleteSelectedItem(self):
        if APP().MainWidget.modified:
            self.saveChangeFirst.exec()

            return

        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        self.questionDel0Box.isMulti = bool(len(indexes) > 1)
        self.questionDel0Box.possibleRemark = (
            f'{indexes[0] + 1} - {self.ServerList[indexes[0]]["remark"]}'
        )
        self.questionDel0Box.setText(self.questionDel0Box.getText())

        if self.questionDel0Box.exec() == MessageBox.StandardButton.No.value:
            # Do not delete
            return

        if self.activatedItemIndex in indexes:
            takedActivated = True
        else:
            takedActivated = False

        for i in range(len(indexes)):
            takedRow = indexes[i] - i

            self.blockSignals(True)
            self.removeRow(takedRow)
            self.blockSignals(False)

            self.ServerList.pop(takedRow)
            self.ScrollList.pop(takedRow)

            if not takedActivated and takedRow < self.activatedItemIndex:
                APP().ActivatedItemIndex = str(self.activatedItemIndex - 1)

        # Sync it
        ServerStorage.sync()

        if takedActivated:
            if APP().tray.ConnectAction.isConnected():
                # Trigger disconnect
                APP().tray.ConnectAction.trigger()
            APP().ActivatedItemIndex = str(-1)

        # Don't use setCurrentItemXXX since the
        # selection may not be changed. Just switch context
        # and change index

        # Don't use currentFocus since it may have been deleted. Get
        # current row from self
        self.switchContext(self.currentRow())

        self.blockSignals(True)
        self.setCurrentIndex(self.indexFromItem(self.item(self.currentRow(), 0)))
        self.blockSignals(False)

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

        def doNotSwitchCallback():
            self.blockSignals(True)
            self.setCurrentIndex(self.indexFromItem(prevItem))
            self.blockSignals(False)

        def doNotSwitch():
            self.doNotSwitchCallback = doNotSwitchCallback

        self.saveScrollBarValue(prevRow)

        if APP().MainWidget is not None and APP().MainWidget.modified:
            choice = self.questionSaveBox.exec()

            if choice == MessageBox.ButtonRole.AcceptRole.value:
                # Save
                if APP().MainWidget.SaveAsServerAction.save(
                    successCallback=lambda: self.switchContext(currRow),
                ):
                    pass
                else:
                    # Do not switch
                    doNotSwitch()

            elif choice == MessageBox.ButtonRole.DestructiveRole.value:
                # Discard
                self.switchContext(currRow)

                APP().MainWidget.markAsSaved()  # Fake saved

            elif choice == MessageBox.ButtonRole.RejectRole.value:
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

        if APP().MainWidget is not None and APP().MainWidget.modified:
            self.saveChangeFirst.exec()

            return

        if APP().tray.ConnectAction.isConnecting():
            # Show the MessageBox asynchronously
            self.progressWaitBox.open()

            return

        if self.activatedItemIndex >= 0:
            # De-activate
            self.activateItemByIndex(self.activatedItemIndex, activate=False)

        newIndex = item.row()

        # Activate
        self.activateItemByIndex(newIndex, activate=True)

        if APP().tray.ConnectAction.isConnected():
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
            list(_(label) for label in NormalServerWidget.HEADER_LABEL)
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
            font.setPointSize(int(APP().EditorWidgetPointSize))

            self.plainTextEdit.setFont(font)
        except Exception:
            # Any non-exit exceptions

            pass

        self.serverEditorTabWidget = QWidget()
        self.serverEditorTabWidgetLayout = QVBoxLayout(self.serverEditorTabWidget)
        self.serverEditorTabWidgetLayout.addWidget(self.plainTextEdit)

        # Advance for Normal Server Widget
        self.editorTab = QTabWidget(self)
        # Note: Set tab text later
        self.editorTab.addTab(self.serverEditorTabWidget, '')

        self.normalServerWidget = NormalServerWidget(parent=self)

        # Buttons
        self.moveUpButton = PushButton(_('Move Up'))
        self.moveUpButton.clicked.connect(
            lambda: self.normalServerWidget.moveUpSelectedItem()
        )
        self.moveDownButton = PushButton(_('Move Down'))
        self.moveDownButton.clicked.connect(
            lambda: self.normalServerWidget.moveDownSelectedItem()
        )
        self.duplicateButton = PushButton(_('Duplicate'))
        self.duplicateButton.clicked.connect(
            lambda: self.normalServerWidget.duplicateSelectedItem()
        )
        self.deleteButton = PushButton(_('Delete'))
        self.deleteButton.clicked.connect(
            lambda: self.normalServerWidget.deleteSelectedItem()
        )

        # Button Layout
        self.buttonWidget = QWidget()
        self.buttonWidgetLayout = QGridLayout(parent=self.buttonWidget)
        self.buttonWidgetLayout.addWidget(self.moveUpButton, 0, 0)
        self.buttonWidgetLayout.addWidget(self.moveDownButton, 0, 1)
        self.buttonWidgetLayout.addWidget(self.duplicateButton, 1, 0)
        self.buttonWidgetLayout.addWidget(self.deleteButton, 1, 1)

        self.normalServerTabWidget = QWidget()
        self.normalServerTabWidgetLayout = QVBoxLayout(self.normalServerTabWidget)
        self.normalServerTabWidgetLayout.addWidget(self.normalServerWidget)
        self.normalServerTabWidgetLayout.addWidget(self.buttonWidget)

        # Note: Reserved for future extension
        # self.subscriptionWidget = QWidget(parent=self)
        #
        # self.subscriptionTabWidget = QWidget()
        # self.subscriptionTabWidgetLayout = QVBoxLayout(self.subscriptionTabWidget)
        # self.subscriptionTabWidgetLayout.addWidget(self.subscriptionWidget)

        self.serverTab = TabWidget(self)
        self.serverTab.addTab(self.normalServerTabWidget, _('Server'))
        # Note: Reserved for future extension
        # self.serverTab.addTab(self.subscriptionTabWidget, '')

        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.serverTab)
        self.splitter.addWidget(self.editorTab)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

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
                    callback=lambda: self.normalServerWidget.selectAll(),
                    parent=self,
                ),
                Seperator(),
                ScrollToActivatedServerAction(parent=self.normalServerWidget),
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

        routingMenu = {
            'name': 'Routing',
            'actions': [
                RoutingAction(parent=self),
            ],
        }

        viewMenu = {
            'name': 'View',
            'actions': [
                ZoomInAction(parent=self),
                ZoomOutAction(parent=self),
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
        for menuDict in (fileMenu, editMenu, routingMenu, viewMenu, helpMenu):
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

        try:
            self.setGeometry(
                100,
                100,
                *list(int(size) for size in APP().MainWidgetWindowSize.split(',')),
            )
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 1440, 1440 * GOLDEN_RATIO)

        moveToCenter(self)

    def importServer(self, remark, config, syncStorage=False):
        server = {'remark': remark, 'config': config}

        self.ServerList.append(server)

        if syncStorage:
            # Sync it
            ServerStorage.sync()

        row = self.normalServerWidget.rowCount()

        self.normalServerWidget.insertRow(row)
        self.normalServerWidget.appendScrollBarEntry()
        self.normalServerWidget.flushRow(row, server)

        item = QTableWidgetItem(str(row + 1))
        item.setFont(QFont(APP().customFontName))

        if len(self.ServerList) == 1:
            # The first one. Click it
            self.normalServerWidget.setCurrentItemByIndex(0)

            # Try to be user-friendly in some extreme cases
            if not APP().tray.ConnectAction.isConnected():
                # Activate automatically
                self.normalServerWidget.activateItemByIndex(0)

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
        return self.normalServerWidget.activatedItemIndex

    @property
    def selectedIndex(self):
        return self.normalServerWidget.selectedIndex

    @property
    def rowCount(self):
        return self.normalServerWidget.rowCount()

    @property
    def currentFocus(self):
        return self.normalServerWidget.currentFocus

    def saveScrollBarValue(self, index):
        self.normalServerWidget.saveScrollBarValue(index)

    def restoreScrollBarValue(self, index):
        self.normalServerWidget.restoreScrollBarValue(index)

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

            if choice == MessageBox.ButtonRole.AcceptRole.value:
                # Save
                # If save success, close the window.
                return self.SaveAsServerAction.save(successCallback=lambda: self.hide())

            if choice == MessageBox.ButtonRole.DestructiveRole.value:
                # Discard
                self.hide()
                self.normalServerWidget.setEmptyItem()
                self.markAsSaved()  # Fake saved

                return True

            if choice == MessageBox.ButtonRole.RejectRole.value:
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
        APP().MainWidgetWindowSize = (
            f'{self.geometry().width()},{self.geometry().height()}'
        )
        APP().ServerWidgetSectionSizeTable = ujson.dumps(
            self.normalServerWidget.sectionSizeTable,
            ensure_ascii=False,
            escape_forward_slashes=False,
        )
        APP().EditorWidgetPointSize = str(self.plainTextEdit.font().pointSize())

    def retranslate(self):
        with StateContext(self):
            if self.modified:
                # Keep modified mark
                self.setWindowTitle(_('Edit Server Configuration') + self.modifiedMark)
            else:
                self.setWindowTitle(_(self.windowTitle()))
