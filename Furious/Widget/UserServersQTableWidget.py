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
from Furious.Interface import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Core import *
from Furious.TrayActions.Import import *
from Furious.Widget.GuiHysteria1 import *
from Furious.Widget.GuiHysteria2 import *
from Furious.Widget.GuiShadowsocks import *
from Furious.Widget.GuiTrojan import *
from Furious.Widget.GuiVLESS import *
from Furious.Widget.GuiVMess import *
from Furious.Window.QRCodeWindow import *
from Furious.Window.TextEditorWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

from typing import Callable, Union, MutableSequence

import queue
import logging
import icmplib
import functools

__all__ = ['UserServersQTableWidget']

logger = logging.getLogger(__name__)

registerAppSettings('ActivatedItemIndex')
# Migrate legacy settings
registerAppSettings('ServerWidgetSectionSizeTable')
registerAppSettings('UserServersHeaderViewState')


class UpdateSubsInfoMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        self.successArgs = kwargs.pop('successArgs', list())
        self.failureArgs = kwargs.pop('failureArgs', list())

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))

    def customText(self):
        if self.successArgs:
            text = _('Update subscription completed') + '\n\n'
        else:
            text = _('Update subscription failed')

        for param in self.successArgs:
            remark, webURL = param['remark'], param['webURL']

            text += (
                f'\U00002705 {remark} - {webURL} '
                + _('Configuration has been updated')
                + '\n'
            )

        if self.successArgs and self.failureArgs:
            text += '\n'
        elif self.failureArgs:
            text += '\n\n'

        for param in self.failureArgs:
            error, remark, webURL = (
                param['error'],
                param['remark'],
                param['webURL'],
            )

            # error is the specific failure reason. Not used
            # for mbox elegant appearance

            text += (
                f'\U0000274c {remark} - {webURL} '
                + _('Configuration update failed')
                + '\n'
            )

        return text

    def setColumnMinWidth(self):
        if PLATFORM == 'Windows':
            self.findChild(QGridLayout).setColumnMinimumWidth(
                2,
                max((len(row) + 10) for row in self.text().split('\n'))
                * self.fontMetrics().averageCharWidth(),
            )

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())
        self.setColumnMinWidth()

        # Ignore informative text, buttons

        self.moveToCenter()


class SubscriptionManager(WebGETManager):
    def __init__(self, parent, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'update subs')

        super().__init__(parent, actionMessage=actionMessage, mustCallOnce=False)

    def handleItemDeletionAndInsertion(self, **kwargs):
        successArgs = kwargs.pop('successArgs', list())
        failureArgs = kwargs.pop('failureArgs', list())
        showMessageBox = kwargs.pop('showMessageBox', True)

        for param in successArgs:
            uris, unique = param['uris'], param['unique']

            parent = self.parent()

            if isinstance(parent, UserServersQTableWidget):
                isConnected = APP().isSystemTrayConnected()

                subsIndexes = list(
                    index
                    for index, server in enumerate(Storage.UserServers())
                    if server.getExtras('subsId') == unique
                )

                subsGroupIndex = -1
                activatedIndex = Storage.UserActivatedItemIndex()

                if activatedIndex in subsIndexes:
                    for index, server in enumerate(Storage.UserServers()):
                        if index <= activatedIndex:
                            if server.getExtras('subsId') == unique:
                                subsGroupIndex += 1
                        else:
                            break

                parent.deleteItemByIndex(
                    subsIndexes, showTrayMessage=bool(subsGroupIndex < 0)
                )

                remaining = len(Storage.UserServers())

                for uri in uris:
                    parent.appendNewItem(config=uri, subsId=unique)

                if subsGroupIndex >= 0:
                    newIndex = remaining + subsGroupIndex

                    if newIndex < len(Storage.UserServers()):
                        parent.activateItemByIndex(newIndex, True)

                        if isConnected and not APP().isSystemTrayConnected():
                            # Trigger connect
                            APP().systemTray.ConnectAction.trigger()

        if showMessageBox:
            mbox = UpdateSubsInfoMBox(
                successArgs=successArgs,
                failureArgs=failureArgs,
                parent=kwargs.pop('parent', None),
            )

            if successArgs:
                mbox.setIcon(AppQMessageBox.Icon.Information)
            else:
                mbox.setIcon(AppQMessageBox.Icon.Critical)

            mbox.setText(mbox.customText())
            mbox.setColumnMinWidth()

            # Show the MessageBox asynchronously
            mbox.open()

    def mustCall(self, **kwargs):
        depthMap = kwargs.get('depthMap', {})
        depthMap['depth'] -= 1

        if depthMap['depth'] == 0:
            self.handleItemDeletionAndInsertion(**kwargs)

    def successCallback(self, networkReply, **kwargs):
        remark = kwargs.get('remark', '')
        webURL = kwargs.get('webURL', '')
        successArgs = kwargs.get('successArgs', list())
        failureArgs = kwargs.get('failureArgs', list())

        data = networkReply.readAll().data()

        try:
            uris = list(
                filter(
                    lambda x: x != '',
                    PyBase64Encoder.decode(data).decode().split('\n'),
                )
            )
        except Exception as ex:
            # Any non-exit exceptions

            def classname(ob) -> str:
                return ob.__class__.__name__

            logger.error(f'parse share link from \'{webURL}\' failed: {ex}')

            failureArgs.append({'error': classname(ex), **kwargs})
        else:
            logger.info(
                f'update subs ({remark}, {webURL}) success. Got {len(uris)} share link'
            )

            successArgs.append({'uris': uris, **kwargs})

    def failureCallback(self, networkReply, **kwargs):
        remark = kwargs.get('remark', '')
        webURL = kwargs.get('webURL', '')
        successArgs = kwargs.get('successArgs', list())
        failureArgs = kwargs.get('failureArgs', list())

        logger.error(
            f'update subs ({remark}, {webURL}) failed: {networkReply.errorString()}'
        )

        failureArgs.append({'error': networkReply.errorString(), **kwargs})

    def updateSubsByWebGET(self, **kwargs):
        url = kwargs.get('webURL', '')

        if not url:
            # Has url empty check
            return

        logActionMessage = kwargs.pop('logActionMessage', False)

        self.webGET(url, logActionMessage=logActionMessage, **kwargs)

    def updateSubsByUnique(self, unique: str, **kwargs):
        depthMap = kwargs.get('depthMap', {'depth': 1})
        successArgs = kwargs.get('successArgs', list())
        failureArgs = kwargs.get('failureArgs', list())

        if kwargs.get('depthMap') is None:
            kwargs['depthMap'] = depthMap

        if kwargs.get('successArgs') is None:
            kwargs['successArgs'] = successArgs

        if kwargs.get('failureArgs') is None:
            kwargs['failureArgs'] = failureArgs

        self.updateSubsByWebGET(unique=unique, **Storage.UserSubs()[unique], **kwargs)

    def updateSubs(self, **kwargs):
        depthMap = {'depth': len(Storage.UserSubs())}
        successArgs = list()
        failureArgs = list()

        for key in Storage.UserSubs().keys():
            self.updateSubsByUnique(
                key,
                depthMap=depthMap,
                successArgs=successArgs,
                failureArgs=failureArgs,
                **kwargs,
            )


class TestPingLatencyWorker(QtCore.QObject, QtCore.QRunnable):
    finished = QtCore.Signal()

    def __init__(self, factory: ConfigFactory):
        # Explictly called __init__
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.factory = factory

    def run(self):
        index = self.factory.index

        if self.factory.deleted or index < 0 or index >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        assert isinstance(self.factory, ConfigFactory)

        try:
            result = icmplib.ping(
                self.factory.itemAddress,
                count=1,
                timeout=2,
                interval=1,
            )
        except Exception as ex:
            # Any non-exit exceptions

            def classname(ob) -> str:
                return ob.__class__.__name__

            self.factory.setExtras('delayResult', classname(ex))

            # Extra guard
            if APP() is not None and not APP().isExiting():
                self.finished.emit()
        else:
            # Result address should not be empty
            if result.address and result.is_alive:
                self.factory.setExtras('delayResult', f'{round(result.avg_rtt)}ms')
            else:
                if result.packet_loss == 1:
                    self.factory.setExtras('delayResult', 'Timeout')
                else:
                    self.factory.setExtras('delayResult', 'Error')

            # Extra guard
            if APP() is not None and not APP().isExiting():
                self.finished.emit()


class TestTcpingLatencyWorker(QtCore.QObject, QtCore.QRunnable):
    finished = QtCore.Signal()

    def __init__(self, factory: ConfigFactory):
        # Explictly called __init__
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.factory = factory

    def run(self):
        index = self.factory.index

        if self.factory.deleted or index < 0 or index >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        assert isinstance(self.factory, ConfigFactory)

        try:
            sent, rtts = tcping(
                self.factory.itemAddress,
                int(self.factory.itemPort.split(',')[0]),
                count=1,
                timeout=2,
                interval=1,
            )
        except Exception as ex:
            # Any non-exit exceptions

            def classname(ob) -> str:
                return ob.__class__.__name__

            self.factory.setExtras('delayResult', classname(ex))

            # Extra guard
            if APP() is not None and not APP().isExiting():
                self.finished.emit()
        else:
            if rtts:
                self.factory.setExtras('delayResult', f'{round(rtts[0] * 1000)}ms')
            else:
                self.factory.setExtras('delayResult', 'Timeout')

            # Extra guard
            if APP() is not None and not APP().isExiting():
                self.finished.emit()


class TestDownloadSpeedWorker(WebGETManager):
    progressed = QtCore.Signal()

    def __init__(
        self,
        factory: ConfigFactory,
        port: int,
        timeout: int,
        parent=None,
        **kwargs,
    ):
        actionMessage = kwargs.pop('actionMessage', 'test download speed')

        super().__init__(parent, actionMessage=actionMessage)

        self.factory = factory
        self.port = port
        self.timeout = timeout
        self.kwargs = kwargs

        self.hasSpeedResult = False
        self.totalBytesRead = 0

        self.hasDataCounter = 0

        self.coreManager = CoreManager()

        self.networkReply = None
        self.elapsedTimer = QtCore.QElapsedTimer()

        self.timeoutTimer = QtCore.QTimer()
        self.timeoutTimer.setSingleShot(True)
        self.timeoutTimer.timeout.connect(self.handleTimeout)

    @property
    def sema(self):
        parent = self.parent()

        # parent must be properly set
        assert isinstance(parent, UserServersQTableWidget)

        return parent.testDownloadSpeedMultiSema

    def mustCall(self):
        self.sema.release(1)

    def sync(self):
        # Extra guard
        if APP() is not None and not APP().isExiting():
            self.progressed.emit()

    def isFinished(self) -> bool:
        if isinstance(self.networkReply, QNetworkReply):
            return self.networkReply.isFinished()
        else:
            return True

    def abort(self):
        if isinstance(self.networkReply, QNetworkReply):
            self.networkReply.abort()

    def handleTimeout(self):
        try:
            if not self.isFinished():
                self.abort()
        finally:
            self.must()

    def coreExitCallback(self, config: ConfigFactory, exitcode: int):
        try:
            if exitcode == CoreProcessFactory.ExitCode.ConfigurationError.value:
                self.factory.setExtras('speedResult', f'Invalid')
                self.sync()
            elif exitcode == CoreProcessFactory.ExitCode.ServerStartFailure.value:
                self.factory.setExtras('speedResult', f'Core start failed')
                self.sync()
            elif exitcode == CoreProcessFactory.ExitCode.SystemShuttingDown.value:
                pass
            else:
                self.factory.setExtras('speedResult', f'Core exited {exitcode}')
                self.sync()
        finally:
            self.must()

    @staticmethod
    def coreMsgCallback(line):
        try:
            AppLoggerWindow.Core().appendLine(line)
        except Exception:
            # Any non-exit exceptions

            pass

    @functools.singledispatchmethod
    def _startCore(self, config) -> bool:
        self.factory.setExtras('speedResult', 'Invalid')
        self.sync()

        # Unrecognized core. Return
        return False

    @_startCore.register(ConfigXray)
    def _(self, config) -> bool:
        self.factory.setExtras('speedResult', 'Starting')
        self.sync()

        configcopy = config.deepcopy()
        # Force redirect
        configcopy['inbounds'] = [
            {
                'tag': 'http',
                'port': self.port,
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

        try:
            for outboundObject in configcopy['outbounds']:
                if outboundObject['tag'] == f'proxy':
                    # Avoid confusion with potentially existing 'proxy' tag
                    outboundObject['tag'] = f'proxy{self.port}'
        except Exception:
            # Any non-exit exceptions

            pass

        self.coreManager.start(
            configcopy,
            'Global',
            self.coreExitCallback,
            msgCallbackCore=self.coreMsgCallback,
            deepcopy=False,
            proxyModeOnly=True,
            log=False,
        )

        return True

    @_startCore.register(ConfigHysteria1)
    @_startCore.register(ConfigHysteria2)
    def _(self, config) -> bool:
        self.factory.setExtras('speedResult', 'Starting')
        self.sync()

        configcopy = config.deepcopy()
        # Force redirect
        configcopy['http'] = {
            'listen': f'127.0.0.1:{self.port}',
            'timeout': 300,
            'disable_udp': False,
        }
        # No socks inbounds
        configcopy.pop('socks5', '')

        self.coreManager.start(
            configcopy,
            'Global',
            self.coreExitCallback,
            msgCallbackCore=self.coreMsgCallback,
            deepcopy=False,
            proxyModeOnly=True,
            log=False,
        )

        return True

    def start(self):
        try:
            if not APP().isExiting():
                index = self.factory.index

                if (
                    self.factory.deleted
                    or index < 0
                    or index >= len(Storage.UserServers())
                ):
                    # Invalid item. Do nothing
                    return

                assert isinstance(self.factory, ConfigFactory)

                if not self.factory.isValid():
                    # Configuration is invalid
                    self.factory.setExtras('speedResult', 'Invalid')
                    self.sync()
                else:
                    if not self._startCore(self.factory) or APP().isExiting():
                        return

                    self.configureHttpProxy(f'127.0.0.1:{self.port}')

                    self.networkReply = self.webGET(
                        NETWORK_SPEED_TEST_URL, **self.kwargs
                    )

                    self.elapsedTimer.start()
                    self.timeoutTimer.start(self.timeout)
        finally:
            if self.networkReply is None:
                self.must()

    def successCallback(self, networkReply, **kwargs):
        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()

            # Convert to seconds
            elapsedSecond = self.elapsedTimer.elapsed() / 1000
            downloadSpeed = self.totalBytesRead / elapsedSecond / 1024 / 1024

            self.factory.setExtras('speedResult', f'{downloadSpeed:.2f} MiB/s')
        else:
            self.factory.setExtras('speedResult', f'Core start failed')

        self.coreManager.stopAll()
        self.sync()

    def hasDataCallback(self, networkReply, **kwargs):
        self.hasDataCounter += 1

        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()

            # Convert to seconds
            elapsedSecond = self.elapsedTimer.elapsed() / 1000
            downloadSpeed = self.totalBytesRead / elapsedSecond / 1024 / 1024

            # Has speed test result
            self.hasSpeedResult = True
            self.factory.setExtras('speedResult', f'{downloadSpeed:.2f} MiB/s')

            # Limited to save CPU resources
            if self.hasDataCounter % 20 == 0:
                self.sync()

    def failureCallback(self, networkReply, **kwargs):
        if not self.hasSpeedResult:
            if not self.coreManager.allRunning():
                # Core ExitCallback has been called
                return

            if (
                networkReply.error()
                == QNetworkReply.NetworkError.OperationCanceledError
            ):
                # Canceled by application
                self.factory.setExtras('speedResult', 'Canceled')
            else:
                try:
                    error = networkReply.error().name
                except Exception:
                    # Any non-exit exceptions

                    error = 'UnknownError'

                if isinstance(error, bytes):
                    # Some old version PySide6 returns it as bytes. Protect it.
                    error = error.decode('utf-8', 'replace')
                elif isinstance(error, str):
                    pass
                else:
                    error = 'UnknownError'

                if error != 'UnknownError' and error.endswith('Error'):
                    self.factory.setExtras('speedResult', error[:-5])
                else:
                    self.factory.setExtras('speedResult', error)

        self.coreManager.stopAll()
        self.sync()


class UserServersQTableWidgetHorizontalHeader(AppQHeaderView):
    class SortOrder:
        Ascending_ = False
        Descending = True

    @staticmethod
    def emptyClickGuard():
        return False

    def __init__(self, *args, **kwargs):
        self.clickGuardFn = kwargs.pop('clickGuardFn', self.emptyClickGuard)
        self.customSortFn = kwargs.pop('customSortFn', None)

        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

        self.sortOrderTable = list(
            self.SortOrder.Ascending_ for i in range(self.columnCount)
        )

        self.sectionClicked.connect(self.handleSectionClicked)

    def customSort(self, clickedIndex):
        self.customSortFn(clickedIndex, reverse=self.sortOrderTable[clickedIndex])
        # Toggle
        self.sortOrderTable[clickedIndex] = not self.sortOrderTable[clickedIndex]

    @QtCore.Slot(int)
    def handleSectionClicked(self, clickedIndex: int):
        if callable(self.clickGuardFn) and self.clickGuardFn():
            # Guarded. Do nothing
            return

        if self.customSortFn is None:
            # Sorting is not supported
            return

        parent = self.parent()

        if isinstance(parent, AppQTableWidget):
            # Support item activation
            activatedIndex = Storage.UserActivatedItemIndex()

            if activatedIndex < 0:
                activatedServerId = None
            else:
                activatedServerId = id(Storage.UserServers()[activatedIndex])

                # De-activated temporarily for sorting
                parent.activateItemByIndex(activatedIndex, False)

            self.customSort(clickedIndex)

            if activatedServerId is not None:
                foundActivatedItem = False

                for index, server in enumerate(Storage.UserServers()):
                    if activatedServerId == id(server):
                        foundActivatedItem = True

                        parent.setCurrentItem(parent.item(index, 0))
                        parent.activateItemByIndex(index, True)

                        break

                # Object id should be found
                assert foundActivatedItem

        else:
            # Not yet implemented
            pass


class UserServersQTableWidgetVerticalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class UserServersQTableWidgetHeaders:
    def __init__(self, name: str, func: Callable[[ConfigFactory], str] = None):
        self.name = name
        self.func = func

    def __call__(self, item: ConfigFactory) -> str:
        if callable(self.func):
            return self.func(item)
        else:
            return getattr(item, f'item{self}')

    def __eq__(self, other):
        return str(self) == str(other)

    def __str__(self):
        return self.name


# ALL Headers VALUE
_TRANSLATABLE_HEADERS = [
    _('Remark'),
    _('Protocol'),
    _('Address'),
    _('Port'),
    _('Transport'),
    _('TLS'),
    _('Subscription'),
    _('Latency'),
    _('Speed'),
]


class UserServersQTableWidget(Mixins.QTranslatable, AppQTableWidget):
    Headers = [
        UserServersQTableWidgetHeaders('Remark'),
        UserServersQTableWidgetHeaders('Protocol'),
        UserServersQTableWidgetHeaders('Address'),
        UserServersQTableWidgetHeaders('Port'),
        UserServersQTableWidgetHeaders('Transport'),
        UserServersQTableWidgetHeaders('TLS'),
        UserServersQTableWidgetHeaders('Subscription'),
        UserServersQTableWidgetHeaders('Latency'),
        UserServersQTableWidgetHeaders('Speed'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.subsManager = SubscriptionManager(parent=self)

        self.testDownloadSpeedQueue = queue.Queue()
        self.testDownloadSpeedTimer = QtCore.QTimer()
        self.testDownloadSpeedTimer.timeout.connect(self.handleTestDownloadSpeedJob)

        self.testDownloadSpeedQueueMulti = queue.Queue()
        self.testDownloadSpeedTimerMulti = QtCore.QTimer()
        self.testDownloadSpeedTimerMulti.timeout.connect(
            self.handleTestDownloadSpeedJobMulti
        )

        self.testDownloadSpeedMultiPort = 30000
        self.testDownloadSpeedMultiSema = QtCore.QSemaphore(max(OS_CPU_COUNT // 2, 1))

        # Text Editor Window
        self.textEditorWindow = TextEditorWindow(parent=self.parent())

        # Must set before flush all
        self.setColumnCount(len(self.Headers))

        # Flush all data to table
        self.flushAll()

        # Install custom header
        self.setHorizontalHeader(
            UserServersQTableWidgetHorizontalHeader(
                parent=self,
                clickGuardFn=lambda: False,
                customSortFn=self.customSortFn,
                legacySectionSizeSettingsName='ServerWidgetSectionSizeTable',
                sectionSizeSettingsName='UserServersHeaderViewState',
            )
        )
        self.setVerticalHeader(UserServersQTableWidgetVerticalHeader(self))

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.setHorizontalHeaderLabels(list(_(str(header)) for header in self.Headers))

        # Selection
        self.setSelectionColor(AppHue.disconnectedColor())
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        self.customizeJSONConfigActionRef = AppQAction(
            _('Customize JSON Configuration...'),
            icon=bootstrapIcon('pencil-square.svg'),
            callback=lambda: self.editSelectedItemConfiguration(),
            shortcut=QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_E,
            ),
        )

        self.advancedActionRef = AppQAction(
            _('Advanced...'),
            menu=AppQMenu(
                self.customizeJSONConfigActionRef,
                AppQSeperator(),
                AppQAction(
                    _('Show Furious Log...'),
                    callback=lambda: AppLoggerWindow.Self().showMaximized(),
                    shortcut=QtCore.QKeyCombination(
                        QtCore.Qt.KeyboardModifier.ControlModifier
                        | QtCore.Qt.KeyboardModifier.ShiftModifier,
                        QtCore.Qt.Key.Key_F,
                    ),
                ),
                AppQAction(
                    _('Show Core Log...'),
                    callback=lambda: AppLoggerWindow.Core().showMaximized(),
                    shortcut=QtCore.QKeyCombination(
                        QtCore.Qt.KeyboardModifier.ControlModifier
                        | QtCore.Qt.KeyboardModifier.ShiftModifier,
                        QtCore.Qt.Key.Key_C,
                    ),
                ),
                AppQAction(
                    _('Show Tun2socks Log...'),
                    callback=lambda: AppLoggerWindow.TUN_().showMaximized(),
                    shortcut=QtCore.QKeyCombination(
                        QtCore.Qt.KeyboardModifier.ControlModifier
                        | QtCore.Qt.KeyboardModifier.ShiftModifier,
                        QtCore.Qt.Key.Key_T,
                    ),
                ),
            ),
            useActionGroup=False,
            checkable=True,
        )

        contextMenuActions = [
            AppQAction(
                _('Move Up'),
                callback=lambda: self.moveUpSelectedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Up,
                ),
            ),
            AppQAction(
                _('Move Down'),
                callback=lambda: self.moveDownSelectedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Down,
                ),
            ),
            AppQAction(
                _('Duplicate'),
                callback=lambda: self.duplicateSelectedItem(),
            ),
            AppQAction(
                _('Delete'),
                callback=lambda: self.deleteSelectedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.Key.Key_Delete,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Scroll To Activated Server'),
                callback=lambda: self.scrollToActivatedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_G,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Test Ping Latency'),
                callback=lambda: self.testSelectedItemPingLatency(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_P,
                ),
            ),
            AppQAction(
                _('Test Tcping Latency'),
                callback=lambda: self.testSelectedItemTcpingLatency(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_O,
                ),
            ),
            AppQAction(
                _('Test Download Speed (Multithreaded)'),
                callback=lambda: self.testSelectedItemDownloadSpeedMulti(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_M,
                ),
            ),
            AppQAction(
                _('Test Download Speed'),
                callback=lambda: self.testSelectedItemDownloadSpeed(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_T,
                ),
            ),
            AppQAction(
                _('Clear Test Results'),
                callback=lambda: self.clearSelectedItemTestResult(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_R,
                ),
            ),
            AppQSeperator(),
            self.advancedActionRef,
            AppQSeperator(),
            AppQAction(
                _('New Empty Configuration'),
                callback=lambda: self.newEmptyItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_N,
                ),
            ),
            ImportFromFileAction(),
            ImportURIFromClipboardAction(
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_V,
                ),
            ),
            ImportJSONFromClipboardAction(
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_J,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Export Share Link To Clipboard'),
                callback=lambda: self.exportSelectedItemURI(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Export As QR Code'),
                icon=bootstrapIcon('qr-code.svg'),
                callback=lambda: self.exportSelectedItemQR(),
            ),
            AppQAction(
                _('Export JSON Configuration To Clipboard'),
                callback=lambda: self.exportSelectedItemJSON(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_J,
                ),
            ),
        ]

        self.contextMenu = AppQMenu(*contextMenuActions)

        # Add actions to self in order to activate shortcuts
        self.addActions(self.contextMenu.actions())
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

        # Distinguish double-click and activated
        self.doubleClickedFlag = False

        # Signals
        self.itemChanged.connect(self.handleItemChanged)
        self.itemSelectionChanged.connect(self.handleItemSelectionChanged)
        self.itemActivated.connect(self.handleItemActivated)
        self.itemDoubleClicked.connect(self.handleItemDoubleClicked)

        if self.activatedItem() is not None:
            self.setCurrentItem(self.activatedItem())
            self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemChanged(self, item: QTableWidgetItem):
        pass

        # TODO: In use?
        # index = item.row()
        #
        # if self.item(index, 0) is None:
        #     return
        #
        # itemText = self.item(index, 0).text()
        #
        # if Storage.UserServers()[index].getExtras('remark') != itemText:
        #     Storage.UserServers()[index].setExtras('remark', itemText)

    @QtCore.Slot()
    def handleItemSelectionChanged(self):
        if len(self.selectedIndex) > 1:
            self.customizeJSONConfigActionRef.setDisabled(True)
        else:
            self.customizeJSONConfigActionRef.setDisabled(False)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemActivated(self, item: QTableWidgetItem):
        if self.doubleClickedFlag:
            # Ignore double-click
            self.doubleClickedFlag = False

            return

        oldIndex = Storage.UserActivatedItemIndex()
        newIndex = item.row()

        if oldIndex == newIndex:
            # Same item activated. Do nothing
            return

        if APP().systemTray.ConnectAction.isConnecting():
            mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
            mbox.setWindowTitle(_('Connecting'))
            mbox.setText(_('Connecting. Please wait...'))

            if PLATFORM != 'Darwin':
                # Show the MessageBox asynchronously
                mbox.open()
            else:
                # Show the MessageBox asynchronously
                # TODO: Verify
                mbox.open()

            return

        if oldIndex >= 0:
            self.activateItemByIndex(oldIndex, False)

        self.activateItemByIndex(newIndex, True)

        if APP().isSystemTrayConnected():
            APP().systemTray.ConnectAction.doReconnect()

    @functools.lru_cache(None)
    def getGuiEditorByProtocol(self, protocol: Protocol, **kwargs):
        logger.debug(f'getGuiEditorByProtocol called with protocol {protocol.value}')

        if protocol == Protocol.VMess:
            return GuiVMess(parent=self, **kwargs)
        if protocol == Protocol.VLESS:
            return GuiVLESS(parent=self, **kwargs)
        if protocol == Protocol.Shadowsocks:
            return GuiShadowsocks(parent=self, **kwargs)
        if protocol == Protocol.Trojan:
            return GuiTrojan(parent=self, **kwargs)
        if protocol == Protocol.Hysteria2:
            return GuiHysteria2(parent=self, **kwargs)
        if protocol == Protocol.Hysteria1:
            return GuiHysteria1(parent=self, **kwargs)

        return None

    @functools.singledispatchmethod
    def getGuiEditorByFactory(
        self, factory, **kwargs
    ) -> Union[GuiEditorWidgetQDialog, None]:
        return None

    @getGuiEditorByFactory.register(ConfigXray)
    def _(self, factory, **kwargs):
        return self.getGuiEditorByProtocol(
            Protocol.toEnum(factory.proxyProtocol), **kwargs
        )

    @getGuiEditorByFactory.register(ConfigHysteria1)
    def _(self, factory, **kwargs):
        return self.getGuiEditorByProtocol(Protocol.Hysteria1, **kwargs)

    @getGuiEditorByFactory.register(ConfigHysteria2)
    def _(self, factory, **kwargs):
        return self.getGuiEditorByProtocol(Protocol.Hysteria2, **kwargs)

    @QtCore.Slot(QTableWidgetItem)
    def handleItemDoubleClicked(self, item: QTableWidgetItem):
        self.doubleClickedFlag = True

        index = item.row()
        factory = Storage.UserServers()[index]

        # Do not translate window title
        guiEditor = self.getGuiEditorByFactory(factory, translatable=False)

        if guiEditor is None:
            # Unrecognized.
            showUnrecognizedConfigMBox()

            return

        guiEditor.setWindowTitle(f'{index + 1} - ' + factory.getExtras('remark'))

        try:
            guiEditor.factoryToInput(factory)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        guiEditor.accepted.connect(
            functools.partial(
                self.handleGuiEditorAccepted,
                guiEditor,
                index,
                factory,
            )
        )
        guiEditor.rejected.connect(
            functools.partial(
                self.handleGuiEditorRejected,
                guiEditor,
            )
        )
        guiEditor.open()

    def handleGuiEditorAccepted(
        self,
        editor: GuiEditorWidgetQDialog,
        index: int,
        factory: ConfigFactory,
    ):
        logger.debug(f'guiEditor accepted with index {index}')

        modified = editor.inputToFactory(factory)

        # Still flush to row since remark may be modified
        self.flushRow(index, factory)

        if modified and index == Storage.UserActivatedItemIndex():
            showNewChangesNextTimeMBox()

        editor.accepted.disconnect()
        editor.rejected.disconnect()

    @staticmethod
    def handleGuiEditorRejected(editor: GuiEditorWidgetQDialog):
        editor.accepted.disconnect()
        editor.rejected.disconnect()

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def customSortFn(self, clickedIndex, **kwargs):
        def keyFn(server):
            data = self.Headers[clickedIndex](server)

            if clickedIndex == self.Headers.index('Latency'):
                if data.endswith('ms'):
                    # Strip value
                    data = data[:-2]

                try:
                    return float(data)
                except Exception:
                    # Any non-exit exceptions

                    return abs(hash(data)) + 2**20

            if clickedIndex == self.Headers.index('Speed'):
                if data.endswith(' MiB/s'):
                    # Strip value
                    data = data[:-6]

                try:
                    return float(data)
                except Exception:
                    # Any non-exit exceptions

                    return abs(hash(data)) + 2**20

            return data

        Storage.UserServers().sort(key=keyFn, **kwargs)

        # Index is refreshed by calling flushAll()
        self.flushAll()

    def activatedItem(self) -> QTableWidgetItem:
        return self.item(Storage.UserActivatedItemIndex(), 0)

    def activateItemByIndex(self, index, activate):
        super().activateItemByIndex(index, activate)

        if activate:
            AppSettings.set('ActivatedItemIndex', str(index))

    def flushItem(self, row: int, column: int, item: ConfigFactory):
        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        def searchIndex(start, stop, step=1):
            nonlocal itemIndex

            for _index in range(start, stop, step):
                if id(item) == id(Storage.UserServers()[_index]):
                    itemIndex = _index

                    item.index = itemIndex

                    return True

            return False

        if id(item) != id(Storage.UserServers()[itemIndex]):
            # itemIndex doesn't match
            if searchIndex(itemIndex - 1, -1, -1) or searchIndex(
                itemIndex + 1, len(Storage.UserServers())
            ):
                pass
            else:
                # Item isn't found in user servers. Do nothing
                return

        if row != itemIndex:
            # Adjust row value
            row = itemIndex
        else:
            pass

        header = self.Headers[column]
        text = header(item)

        oldItem = self.item(row, column)
        newItem = QTableWidgetItem(text)
        newItem.setToolTip(text)

        if oldItem is None:
            # Item does not exist
            newItem.setFont(QFont(AppFontName()))

            if str(header) == 'Latency' or str(header) == 'Speed':
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

        #
        # Legacy flags. Not used
        #
        # if str(header) == 'Remark':
        #     # Remark is editable
        #     newItem.setFlags(
        #         QtCore.Qt.ItemFlag.ItemIsEnabled
        #         | QtCore.Qt.ItemFlag.ItemIsSelectable
        #         | QtCore.Qt.ItemFlag.ItemIsEditable
        #     )
        # else:
        #     newItem.setFlags(
        #         QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        #     )

        # Remark is now editable via GUI window
        newItem.setFlags(
            QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        )

        self.setItem(row, column, newItem)

    def addServerViaGui(
        self,
        protocol: Protocol,
        windowTitle: str = APPLICATION_NAME,
        **kwargs,
    ):
        factory = configFactoryBlank(protocol)

        guiEditor = self.getGuiEditorByFactory(factory, **kwargs)

        if guiEditor is None:
            # Unrecognized. Do nothing
            return

        guiEditor.setWindowTitle(windowTitle)

        try:
            guiEditor.factoryToInput(factory)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        guiEditor.accepted.connect(
            functools.partial(
                self.handleAddServerViaGuiAccepted,
                guiEditor,
                factory,
            )
        )
        guiEditor.rejected.connect(
            functools.partial(
                self.handleAddServerViaGuiRejected,
                guiEditor,
            )
        )
        guiEditor.open()

    def handleAddServerViaGuiAccepted(
        self,
        editor: GuiEditorWidgetQDialog,
        factory: ConfigFactory,
    ):
        editor.inputToFactory(factory)

        self.appendNewItemByFactory(factory)

        editor.accepted.disconnect()
        editor.rejected.disconnect()

    def handleAddServerViaGuiRejected(self, editor: GuiEditorWidgetQDialog):
        editor.accepted.disconnect()
        editor.rejected.disconnect()

    def flushRow(self, row: int, item: ConfigFactory):
        for column in list(range(self.columnCount())):
            self.flushItem(row, column, item)

    def flushAll(self):
        # Refresh index
        for index, item in enumerate(Storage.UserServers()):
            item.index = index

        if self.rowCount() == 0:
            # Should insert row
            for index, item in enumerate(Storage.UserServers()):
                self.insertRow(index)
                self.flushRow(index, item)
        else:
            for index, item in enumerate(Storage.UserServers()):
                self.flushRow(index, item)

    def swapItem(self, index0: int, index1: int):
        def swapSequenceItem(sequence: MutableSequence, param0: int, param1: int):
            swap = sequence[param0]

            sequence[param0] = sequence[param1]
            sequence[param1] = swap

        swapSequenceItem(Storage.UserServers(), index0, index1)

        # Refresh index
        Storage.UserServers()[index0].index = index1
        Storage.UserServers()[index1].index = index0

        self.flushRow(index0, Storage.UserServers()[index0])
        self.flushRow(index1, Storage.UserServers()[index1])

        if index0 == Storage.UserActivatedItemIndex():
            # De-activate
            self.activateItemByIndex(index0, False)
            # Activate
            self.activateItemByIndex(index1, True)
        elif index1 == Storage.UserActivatedItemIndex():
            # De-activate
            self.activateItemByIndex(index1, False)
            # Activate
            self.activateItemByIndex(index0, True)

    def newEmptyItem(self):
        self.appendNewItem(remark=_('Untitled'), acceptInvalid=True)

    def moveUpItemByIndex(self, index):
        if index <= 0 or index >= len(Storage.UserServers()):
            # The top item, or does not exist. Do nothing
            return

        self.swapItem(index, index - 1)

    def moveUpSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            self.moveUpItemByIndex(index)

        with Mixins.QBlockSignalContext(self):
            self.setCurrentIndex(self.indexFromItem(self.item(indexes[-1] - 1, 0)))

        self.selectMultipleRows(list(index - 1 for index in indexes), True)

    def moveDownItemByIndex(self, index):
        if index < 0 or index >= len(Storage.UserServers()) - 1:
            # The bottom item, or does not exist. Do nothing
            return

        self.swapItem(index, index + 1)

    def moveDownSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes[::-1]:
            self.moveDownItemByIndex(index)

        with Mixins.QBlockSignalContext(self):
            self.setCurrentIndex(self.indexFromItem(self.item(indexes[0] + 1, 0)))

        self.selectMultipleRows(list(index + 1 for index in indexes), True)

    def duplicateSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            if 0 <= index < len(Storage.UserServers()):
                deepcopy = Storage.UserServers()[index].deepcopy()

                # Do not clone subsId
                self.appendNewItem(
                    remark=deepcopy.getExtras('remark'),
                    config=deepcopy,
                )

    def deleteItemByIndex(self, indexes, showTrayMessage=True) -> int:
        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return 0

        if Storage.UserActivatedItemIndex() in indexes:
            deleteActivated = True
        else:
            deleteActivated = False

        # Note: param indexes must be sorted
        for i in range(len(indexes)):
            deleteIndex = indexes[i] - i

            with Mixins.QBlockSignalContext(self):
                self.removeRow(deleteIndex)

            Storage.UserServers()[deleteIndex].deleted = True
            Storage.UserServers().pop(deleteIndex)

            if not deleteActivated and deleteIndex < Storage.UserActivatedItemIndex():
                AppSettings.set(
                    'ActivatedItemIndex', str(Storage.UserActivatedItemIndex() - 1)
                )

        if deleteActivated:
            # Set invalid first
            AppSettings.set('ActivatedItemIndex', str(-1))

            if APP().isSystemTrayConnected():
                if showTrayMessage:
                    # Trigger disconnect
                    APP().systemTray.ConnectAction.trigger()
                else:
                    # Trigger disconnect silently
                    APP().systemTray.ConnectAction.doDisconnect()

        return len(indexes)

    def deleteSelectedItem(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def handleResultCode(_indexes, code):
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                self.deleteItemByIndex(_indexes)
            else:
                pass

        if PLATFORM == 'Windows':
            # Windows
            mbox = QuestionDeleteMBox(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = QuestionDeleteMBox(
                icon=AppQMessageBox.Icon.Question, parent=self.parent()
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = f'{indexes[0] + 1} - {self.item(indexes[0], 0).text()}'
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def editSelectedItemConfiguration(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        if len(indexes) != 1:
            # Should not reach here
            return

        index = indexes[0]
        title = f'{index + 1} - ' + Storage.UserServers()[index].getExtras('remark')

        self.textEditorWindow.currentIndex = index
        self.textEditorWindow.customWindowTitle = title
        self.textEditorWindow.setWindowTitle(title)
        self.textEditorWindow.setPlainText(
            Storage.UserServers()[index].toJSONString(), True
        )
        self.textEditorWindow.show()

    def scrollToActivatedItem(self):
        activatedItem = self.activatedItem()

        self.setCurrentItem(activatedItem)
        self.scrollToItem(activatedItem)

    def testSelectedItemPingLatency(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)

        for index, reference in zip(indexes, references):
            if APP().isExiting():
                break

            assert isinstance(reference, ConfigFactory)

            if reference.deleted:
                continue

            worker = TestPingLatencyWorker(reference)
            worker.setAutoDelete(True)
            worker.finished.connect(
                functools.partial(
                    self.flushItem,
                    index,
                    self.Headers.index('Latency'),
                    reference,
                )
            )

            AppThreadPool().start(worker)

    def testSelectedItemTcpingLatency(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)

        for index, reference in zip(indexes, references):
            if APP().isExiting():
                break

            assert isinstance(reference, ConfigFactory)

            if reference.deleted:
                continue

            worker = TestTcpingLatencyWorker(reference)
            worker.setAutoDelete(True)
            worker.finished.connect(
                functools.partial(
                    self.flushItem,
                    index,
                    self.Headers.index('Latency'),
                    reference,
                )
            )

            AppThreadPool().start(worker)

    def testDownloadSpeedByFactory(
        self,
        index: int,
        factory: ConfigFactory,
        port: int,
        timeout: int,
        isMulti: bool,
        counter=0,
        step=100,
        logActionMessage=False,
    ):
        worker = TestDownloadSpeedWorker(
            factory,
            port,
            timeout,
            parent=self,
            logActionMessage=logActionMessage,
        )
        worker.progressed.connect(
            functools.partial(
                self.flushItem,
                index,
                self.Headers.index('Speed'),
                factory,
            )
        )
        worker.start()

        if not isMulti:
            while (
                not APP().isExiting() and not worker.isFinished() and counter < timeout
            ):
                PySide6Legacy.eventLoopWait(step)

                counter += step

            if not worker.isFinished():
                worker.abort()

                while not worker.isFinished():
                    PySide6Legacy.eventLoopWait(step)

        if APP().isExiting():
            if not worker.isFinished():
                worker.abort()

            # Stop timer
            self.testDownloadSpeedTimer.stop()
            self.testDownloadSpeedTimerMulti.stop()

    def handleTestDownloadSpeedJobXXX(
        self,
        jobQueue: queue.Queue,
        jobTimer: QtCore.QTimer,
        isMulti: bool,
    ):
        if APP().isExiting():
            jobTimer.stop()

            return

        if isMulti and not self.testDownloadSpeedMultiSema.tryAcquire(1):
            return

        try:
            index, factory, timeout = jobQueue.get_nowait()
        except queue.Empty:
            # Queue is empty

            if isMulti:
                self.testDownloadSpeedMultiSema.release(1)

            # Power Optimization. Timer gets fired only when needed
            jobTimer.stop()

            return

        def fetchNextJob():
            if not APP().isExiting():
                # Fetch next job.
                if self.isVisible():
                    interval = max(1.0, 1000 / len(Storage.UserServers()))
                    interval = min(interval, 50)

                    jobTimer.start(int(interval))
                else:
                    jobTimer.start(50)
            else:
                jobTimer.stop()

        if isMulti:
            if self.testDownloadSpeedMultiPort >= 40000:
                self.testDownloadSpeedMultiPort = 30000

            testDownloadSpeedPort = self.testDownloadSpeedMultiPort

            self.testDownloadSpeedMultiPort += 1

            fetchNextJob()
        else:
            testDownloadSpeedPort = 20809

        assert isinstance(factory, ConfigFactory)

        if factory.deleted:
            # Invalid item. Do nothing.
            if isMulti:
                self.testDownloadSpeedMultiSema.release(1)

            fetchNextJob()
        else:
            if not APP().isExiting():
                self.testDownloadSpeedByFactory(
                    index,
                    factory,
                    testDownloadSpeedPort,
                    timeout,
                    isMulti,
                )

            fetchNextJob()

    @QtCore.Slot()
    def handleTestDownloadSpeedJob(self):
        self.handleTestDownloadSpeedJobXXX(
            self.testDownloadSpeedQueue,
            self.testDownloadSpeedTimer,
            False,
        )

    @QtCore.Slot()
    def handleTestDownloadSpeedJobMulti(self):
        self.handleTestDownloadSpeedJobXXX(
            self.testDownloadSpeedQueueMulti,
            self.testDownloadSpeedTimerMulti,
            True,
        )

    def testSelectedItemDownloadSpeedWithTimeoutXXX(
        self,
        jobQueue: queue.Queue,
        jobTimer: QtCore.QTimer,
        timeout: int,
    ):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)

        for index, reference in zip(indexes, references):
            try:
                # Served by FIFO
                jobQueue.put_nowait((index, reference, timeout))
            except Exception:
                # Any non-exit exceptions

                pass

        if not jobTimer.isActive():
            # # Power Optimization. Timer gets fired only when needed
            jobTimer.start(250)

    def testSelectedItemDownloadSpeedWithTimeout(self, timeout: int):
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.testDownloadSpeedQueue,
            self.testDownloadSpeedTimer,
            timeout,
        )

    def testSelectedItemDownloadSpeedWithTimeoutMulti(self, timeout: int):
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.testDownloadSpeedQueueMulti,
            self.testDownloadSpeedTimerMulti,
            timeout,
        )

    def testSelectedItemDownloadSpeed(self):
        self.testSelectedItemDownloadSpeedWithTimeout(5000)

    def testSelectedItemDownloadSpeedMulti(self):
        self.testSelectedItemDownloadSpeedWithTimeoutMulti(5000)

    def clearSelectedItemTestResult(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            factory = Storage.UserServers()[index]
            factory.setExtras('delayResult', '')
            factory.setExtras('speedResult', '')

            self.flushItem(index, self.Headers.index('Latency'), factory)
            self.flushItem(index, self.Headers.index('Speed'), factory)

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        self.subsManager.configureHttpProxy(httpProxy)
        self.subsManager.updateSubsByUnique(unique, **kwargs)

    def updateSubs(self, httpProxy: Union[str, None], **kwargs):
        self.subsManager.configureHttpProxy(httpProxy)
        self.subsManager.updateSubs(**kwargs)

    def appendNewItemByFactory(self, factory: ConfigFactory):
        index = len(Storage.UserServers())

        # Set index
        factory.index = index

        Storage.UserServers().append(factory)

        row = self.rowCount()

        assert index == row

        self.insertRow(row)
        self.flushRow(row, factory)

        if index == 0:
            # The first one. Click it
            self.setCurrentItem(self.item(0, 0))

            # Try to be user-friendly in some extreme cases
            if not APP().isSystemTrayConnected():
                # Activate automatically
                self.activateItemByIndex(0, True)

    def appendNewItem(self, **kwargs):
        acceptInvalid = kwargs.pop('acceptInvalid', False)

        model = {
            'remark': kwargs.pop('remark', ''),
            'config': kwargs.pop('config', ''),
            'subsId': kwargs.pop('subsId', ''),
        }
        tostr = f'{model}'

        factory = configFactoryFromAny(model.pop('config', ''), **model)

        if factory.isValid():
            self.appendNewItemByFactory(factory)
        else:
            if acceptInvalid:
                self.appendNewItemByFactory(factory)
            else:
                logger.error(f'invalid item: {tostr}')

    def exportSelectedItemURI(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def toURI(factory) -> str:
            assert isinstance(factory, ConfigFactory)

            try:
                return factory.toURI()
            except Exception:
                # Any non-exit exceptions

                return ''

        # TODO: MessageBox?
        QApplication.clipboard().setText(
            '\n'.join(list(toURI(Storage.UserServers()[index]) for index in indexes))
        )

    def exportSelectedItemQR(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        window = QRCodeWindow()
        window.initTabByIndex(indexes)

        if window.tabCount() > 0:
            window.show()

    def exportSelectedItemJSON(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # TODO: MessageBox?
        QApplication.clipboard().setText(
            '\n'.join(
                list(Storage.UserServers()[index].toJSONString() for index in indexes)
            )
        )

    def showTabAndSpaces(self):
        self.textEditorWindow.showTabAndSpaces()

    def hideTabAndSpaces(self):
        self.textEditorWindow.hideTabAndSpaces()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Return:
            if PLATFORM == 'Darwin':
                # Activate by Enter key on macOS
                self.itemActivated.emit(self.currentItem())
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def disconnectedCallback(self):
        super().disconnectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def connectedCallback(self):
        super().connectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def retranslate(self):
        self.setHorizontalHeaderLabels(list(_(str(header)) for header in self.Headers))
