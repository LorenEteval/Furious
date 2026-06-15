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

import re
import logging
import icmplib
import functools
import collections

__all__ = ['UserServersQTableView']

logger = logging.getLogger(__name__)

registerAppSettings('ActivatedItemIndex')
# Migrate legacy settings
registerAppSettings('ServerWidgetSectionSizeTable')
registerAppSettings('UserServersHeaderViewState')


class MBoxUpdateSubsInfo(AppQMessageBox):
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

            if isinstance(parent, UserServersQTableView):
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
            mbox = MBoxUpdateSubsInfo(
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

        uris = None
        lastException = None

        try:
            decoded = PyBase64Encoder.decode(data).decode()
        except Exception as ex:
            # Any non-exit exceptions

            lastException = ex

            logger.error(
                f'parse base64 share link from \'{webURL}\' failed: {ex}. '
                f'Try to fall back to plain text'
            )
        else:
            # pybase64 decodes leniently and happily turns plain text into
            # garbage bytes, so only accept the base64 result when it actually
            # looks like share links.
            if '://' in decoded:
                uris = list(filter(lambda x: x != '', decoded.split('\n')))

        if uris is None:
            try:
                uris = list(
                    filter(
                        lambda x: x != '',
                        data.decode().split('\n'),
                    )
                )
            except Exception as ex:
                # Any non-exit exceptions

                lastException = ex

                logger.error(f'parse share link from \'{webURL}\' failed: {ex}')

        if uris is None:
            failureArgs.append({'error': classname(lastException), **kwargs})
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

        # Some providers reject the default Qt User-Agent (e.g. with 503),
        # so identify ourselves explicitly.
        request = QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(
            b'User-Agent',
            f'{APPLICATION_NAME}/{APPLICATION_VERSION}'.encode(),
        )

        self.webGET(request, logActionMessage=logActionMessage, **kwargs)

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
    finished = QtCore.Signal(object)

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

    def mustCall(self):
        self.timeoutTimer.stop()
        self.finished.emit(self)

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
            AppBuiltinRouting.Global.value,
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
            AppBuiltinRouting.Global.value,
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

                    # Use custom network speed test URL if possible
                    settings = AppSettings.get('CustomNetworkSpeedTestURL')

                    if isinstance(settings, str):
                        url = settings
                    else:
                        url = NETWORK_SPEED_TEST_URL

                    self.networkReply = self.webGET(url, **self.kwargs)

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
            if self.hasDataCounter % 25 == 0:
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


class DownloadSpeedTestJob:
    def __init__(
        self,
        index: int,
        factory: ConfigFactory,
        timeout: int,
        logActionMessage=False,
    ):
        super().__init__()

        self.index = index
        self.factory = factory
        self.timeout = timeout
        self.logActionMessage = logActionMessage


class DownloadSpeedTestScheduler(QtCore.QObject):
    SinglePort = 20809
    MultiPortStart = 30000
    MultiPortStop = 40000

    def __init__(self, table, isMulti: bool, parent=None):
        super().__init__(parent)

        self.table = table
        self.isMulti = isMulti
        self.maxConcurrency = max(OS_CPU_COUNT // 2, 1) if isMulti else 1

        self.queue = collections.deque()
        self.activeJobs = {}
        self.activePorts = set()
        self.nextMultiPort = self.MultiPortStart
        self.drainScheduled = False

    def enqueue(
        self,
        index: int,
        factory: ConfigFactory,
        timeout: int,
        logActionMessage=False,
    ):
        self.queue.append(
            DownloadSpeedTestJob(index, factory, timeout, logActionMessage)
        )
        self.scheduleDrain()

    def enqueueMany(self, jobs: list[DownloadSpeedTestJob]):
        self.queue.extend(jobs)

        self.scheduleDrain()

    def cancelAll(self):
        self.queue.clear()

        for worker, _, _ in list(self.activeJobs.values()):
            assert isinstance(worker, TestDownloadSpeedWorker)

            if not worker.isFinished():
                worker.abort()

            worker.coreManager.stopAll()
            worker.must()

    def scheduleDrain(self):
        if self.drainScheduled:
            return

        self.drainScheduled = True

        QtCore.QTimer.singleShot(0, self.drain)

    def drain(self):
        self.drainScheduled = False

        if APP().isExiting():
            self.cancelAll()

            return

        while self.queue and len(self.activeJobs) < self.maxConcurrency:
            job = self.queue.popleft()

            assert isinstance(job.factory, ConfigFactory)

            if job.factory.deleted:
                continue

            port = self.allocatePort()

            if port is None:
                self.queue.appendleft(job)

                break

            self.startJob(job, port)

    def allocatePort(self) -> Union[int, None]:
        if not self.isMulti:
            if self.activeJobs:
                return None

            return self.SinglePort

        portRange = self.MultiPortStop - self.MultiPortStart

        for _ in range(portRange):
            port = self.nextMultiPort
            self.nextMultiPort += 1

            if self.nextMultiPort >= self.MultiPortStop:
                self.nextMultiPort = self.MultiPortStart

            if port not in self.activePorts:
                self.activePorts.add(port)

                return port

        return None

    def releasePort(self, port: int):
        self.activePorts.discard(port)

    def startJob(self, job: DownloadSpeedTestJob, port: int):
        worker = TestDownloadSpeedWorker(
            job.factory,
            port,
            job.timeout,
            parent=self,
            logActionMessage=job.logActionMessage,
        )
        worker.progressed.connect(
            functools.partial(
                self.table.flushDownloadSpeedItem,
                job.index,
                job.factory,
            )
        )

        self.activeJobs[id(worker)] = (worker, job, port)

        worker.finished.connect(self.handleWorkerFinished)
        worker.start()

    @QtCore.Slot(object)
    def handleWorkerFinished(self, worker):
        workerId = id(worker)

        try:
            _, _, port = self.activeJobs.pop(workerId)
        except KeyError:
            return

        self.releasePort(port)
        worker.deleteLater()
        self.scheduleDrain()


class UserServersQTableViewHorizontalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class UserServersQTableViewVerticalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class UserServersQTableViewHeaders:
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


class UserServersTableModel(QtCore.QAbstractTableModel):
    SortRole = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, headers: list[UserServersQTableViewHeaders], parent=None):
        super().__init__(parent)

        self.headers = headers

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(Storage.UserServers())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(self.headers)

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()

        if row < 0 or row >= len(Storage.UserServers()):
            return None

        if column < 0 or column >= len(self.headers):
            return None

        server = Storage.UserServers()[row]
        header = self.headers[column]
        text = header(server)

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.ToolTipRole
        ):
            return text

        if role == QtCore.Qt.ItemDataRole.FontRole:
            font = QFont(AppFontName())

            if row == Storage.UserActivatedItemIndex():
                font.setBold(True)

            return font

        if role == QtCore.Qt.ItemDataRole.ForegroundRole:
            if row == Storage.UserActivatedItemIndex():
                return QColor(AppHue.currentColor())

            return None

        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if str(header) == 'Latency' or str(header) == 'Speed':
                return (
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )

            return None

        if role == self.SortRole:
            if str(header) == 'Latency':
                return self.testResultSortValue(text, 'ms')

            if str(header) == 'Speed':
                return self.testResultSortValue(text, ' MiB/s')

            return text

        return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            if 0 <= section < len(self.headers):
                return _(str(self.headers[section]))

            return None

        return section + 1

    @staticmethod
    def testResultSortValue(text: str, suffix: str):
        if text.endswith(suffix):
            text = text[: -len(suffix)]

        try:
            return float(text)
        except Exception:
            # Any non-exit exceptions

            return abs(hash(text)) + 2**20

    def emitRowChanged(self, row: int, column: Union[int, None] = None):
        if row < 0 or row >= self.rowCount():
            return

        if column is None:
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
        else:
            left = self.index(row, column)
            right = left

        self.dataChanged.emit(left, right, [])

    def emitAllChanged(self):
        if self.rowCount() == 0 or self.columnCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            [],
        )

    @staticmethod
    def refreshIndexes():
        for index, item in enumerate(Storage.UserServers()):
            item.index = index

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        if column < 0 or column >= self.columnCount():
            return

        activatedIndex = Storage.UserActivatedItemIndex()

        if 0 <= activatedIndex < len(Storage.UserServers()):
            activatedServerId = id(Storage.UserServers()[activatedIndex])
        else:
            activatedServerId = None

        header = self.headers[column]

        def keyFn(factory: ConfigFactory):
            data = header(factory)

            if str(header) == 'Latency':
                return self.testResultSortValue(data, 'ms')

            if str(header) == 'Speed':
                return self.testResultSortValue(data, ' MiB/s')

            return data

        self.layoutAboutToBeChanged.emit()

        Storage.UserServers().sort(
            key=keyFn,
            reverse=order == QtCore.Qt.SortOrder.DescendingOrder,
        )
        self.refreshIndexes()

        if activatedServerId is not None:
            for index, server in enumerate(Storage.UserServers()):
                if id(server) == activatedServerId:
                    AppSettings.set('ActivatedItemIndex', str(index))

                    break

        self.layoutChanged.emit()


class UserServersSortFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.searchPattern = ''
        self.searchCaseSensitive = False
        self.searchUseRegex = True
        self.searchRegex = None
        self.sortSuspended = False

        self.setSortRole(UserServersTableModel.SortRole)
        self.setDynamicSortFilter(True)

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        if self.sortSuspended:
            super().sort(-1, order)

            return

        if column < 0:
            super().sort(column, order)

            return

        model = self.sourceModel()

        if model is not None:
            model.sort(column, order)
            self.invalidate()

    def setSearchPattern(
        self,
        pattern: str,
        *,
        caseSensitive: bool = False,
        regex: bool = True,
    ):
        self.searchPattern = str(pattern or '')
        self.searchCaseSensitive = caseSensitive
        self.searchUseRegex = regex
        self.searchRegex = None

        if self.searchPattern:
            flags = 0 if caseSensitive else re.IGNORECASE
            regexPattern = (
                self.searchPattern if regex else re.escape(self.searchPattern)
            )

            try:
                self.searchRegex = re.compile(regexPattern, flags)
            except re.error as ex:
                logger.error(
                    f'invalid user servers search regex: {ex}. '
                    f'Fall back to literal matching'
                )

                self.searchRegex = re.compile(re.escape(self.searchPattern), flags)

        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow: int, sourceParent) -> bool:
        if not self.searchPattern or self.searchRegex is None:
            return True

        model = self.sourceModel()

        if model is None:
            return True

        searchableText = '\n'.join(
            str(
                model.data(
                    model.index(sourceRow, column, sourceParent),
                    QtCore.Qt.ItemDataRole.DisplayRole,
                )
                or ''
            )
            for column in range(model.columnCount(sourceParent))
        )

        return self.searchRegex.search(searchableText) is not None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation == QtCore.Qt.Orientation.Vertical
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            return section + 1

        return super().headerData(section, orientation, role)


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


class UserServersQTableView(
    Mixins.QTranslatable,
    Mixins.CleanupOnExit,
    AppQTableView,
):
    RowHeight = 42

    Headers = [
        UserServersQTableViewHeaders('Remark'),
        UserServersQTableViewHeaders('Protocol'),
        UserServersQTableViewHeaders('Address'),
        UserServersQTableViewHeaders('Port'),
        UserServersQTableViewHeaders('Transport'),
        UserServersQTableViewHeaders('TLS'),
        UserServersQTableViewHeaders('Subscription'),
        UserServersQTableViewHeaders('Latency'),
        UserServersQTableViewHeaders('Speed'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.sourceModel = UserServersTableModel(self.Headers, parent=self)
        self.proxyModel = UserServersSortFilterProxyModel(parent=self)
        self.proxyModel.setSourceModel(self.sourceModel)
        self.setModel(self.proxyModel)

        self.subsManager = SubscriptionManager(parent=self)

        self.downloadSpeedScheduler = DownloadSpeedTestScheduler(
            self,
            isMulti=False,
            parent=self,
        )
        self.downloadSpeedMultiScheduler = DownloadSpeedTestScheduler(
            self,
            isMulti=True,
            parent=self,
        )

        # Text Editor Window
        self.textEditorWindow = TextEditorWindow(parent=self.parent())

        # Install custom header
        self.setHorizontalHeader(
            UserServersQTableViewHorizontalHeader(
                parent=self,
                legacySectionSizeSettingsName='ServerWidgetSectionSizeTable',
                sectionSizeSettingsName='UserServersHeaderViewState',
            )
        )
        self.setVerticalHeader(UserServersQTableViewVerticalHeader(self))
        self.setDefaultRowHeight(self.RowHeight)

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.proxyModel.sortSuspended = True
        self.setSortingEnabled(True)
        self.proxyModel.sortSuspended = False
        self.proxyModel.sort(-1)

        # Selection
        self.setSelectionColor(AppHue.disconnectedColor())
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

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
            checkable=False,
        )

        self.activateSelectedServerActionRef = AppQAction(
            _('Activate Selected Server'),
            callback=lambda: self.activateSelectedServer(),
            shortcut=QtCore.QKeyCombination(
                QtCore.Qt.Key.Key_Enter,
            ),
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
            self.activateSelectedServerActionRef,
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
            ImportQRCodeOnTheScreenAction(),
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
        self.selectionModel().selectionChanged.connect(self.handleItemSelectionChanged)
        self.activated.connect(self.handleItemActivated)
        self.doubleClicked.connect(self.handleItemDoubleClicked)

        self.flushAll()

        if self.activatedIndex().isValid():
            self.setCurrentIndex(self.activatedIndex())
            self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    @property
    def selectedIndex(self):
        indexes = list(
            self.sourceRowFromProxyIndex(index)
            for index in self.selectionModel().selectedRows()
        )

        return sorted(list(set(index for index in indexes if index >= 0)))

    def sourceIndexFromProxyIndex(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapToSource(index)

    def proxyIndexFromSourceIndex(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapFromSource(index)

    def sourceRowFromProxyIndex(self, index: QtCore.QModelIndex) -> int:
        sourceIndex = self.sourceIndexFromProxyIndex(index)

        if sourceIndex.isValid():
            return sourceIndex.row()

        return -1

    def sourceRowFromProxyRow(self, row: int) -> int:
        return self.sourceRowFromProxyIndex(self.proxyModel.index(row, 0))

    def proxyIndexFromSourceRow(self, row: int, column: int = 0):
        if row < 0 or row >= self.sourceModel.rowCount():
            return QtCore.QModelIndex()

        return self.proxyIndexFromSourceIndex(self.sourceModel.index(row, column))

    def selectMultipleRows(self, indexes: list[int], clearCurrentSelection: bool):
        if clearCurrentSelection:
            self.selectionModel().clearSelection()

        selection = self.selectionModel().selection()

        for index in indexes:
            proxyIndex0 = self.proxyIndexFromSourceRow(index, 0)
            proxyIndex1 = self.proxyIndexFromSourceRow(index, len(self.Headers) - 1)

            if proxyIndex0.isValid() and proxyIndex1.isValid():
                selection.select(proxyIndex0, proxyIndex1)

        self.selectionModel().select(
            selection, QtCore.QItemSelectionModel.SelectionFlag.Select
        )

    def disconnectedCallback(self):
        super().disconnectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def connectedCallback(self):
        super().connectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def handleItemSelectionChanged(self, *args):
        if len(self.selectedIndex) > 1:
            for action in [
                self.customizeJSONConfigActionRef,
                self.activateSelectedServerActionRef,
            ]:
                action.setDisabled(True)
        else:
            for action in [
                self.customizeJSONConfigActionRef,
                self.activateSelectedServerActionRef,
            ]:
                action.setDisabled(False)

    @QtCore.Slot(QtCore.QModelIndex)
    def handleItemActivated(self, index: QtCore.QModelIndex):
        if self.doubleClickedFlag:
            # Ignore double-click
            self.doubleClickedFlag = False

            return

        oldIndex = Storage.UserActivatedItemIndex()
        newIndex = self.sourceRowFromProxyIndex(index)

        if newIndex < 0:
            return

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

    @QtCore.Slot(QtCore.QModelIndex)
    def handleItemDoubleClicked(self, modelIndex: QtCore.QModelIndex):
        self.doubleClickedFlag = True

        index = self.sourceRowFromProxyIndex(modelIndex)

        if index < 0:
            return

        factory = Storage.UserServers()[index]

        # Do not translate window title
        guiEditor = self.getGuiEditorByFactory(factory, translatable=False)

        if guiEditor is None:
            # Unrecognized.
            showMBoxUnrecognizedConfig()

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
            showMBoxNewChangesNextTime()

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
        order = (
            QtCore.Qt.SortOrder.DescendingOrder
            if kwargs.get('reverse', False)
            else QtCore.Qt.SortOrder.AscendingOrder
        )

        self.sortByColumn(clickedIndex, order)

    def activatedIndex(self):
        return self.proxyIndexFromSourceRow(Storage.UserActivatedItemIndex(), 0)

    def activateItemByIndex(self, index, activate):
        oldIndex = Storage.UserActivatedItemIndex()

        if activate:
            AppSettings.set('ActivatedItemIndex', str(index))

        self.sourceModel.emitRowChanged(oldIndex)
        self.sourceModel.emitRowChanged(index)

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

        self.sourceModel.emitRowChanged(row, column)

    def search(
        self,
        pattern: str,
        *,
        caseSensitive: bool = False,
        regex: bool = True,
    ):
        self.proxyModel.setSearchPattern(
            pattern,
            caseSensitive=caseSensitive,
            regex=regex,
        )

    def clearSearch(self):
        self.search('')

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
        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        if row != itemIndex:
            row = itemIndex

        self.sourceModel.emitRowChanged(row)

    def flushAll(self):
        # Refresh index
        self.sourceModel.refreshIndexes()
        self.sourceModel.emitAllChanged()

    def swapItem(self, index0: int, index1: int):
        def swapSequenceItem(sequence: MutableSequence, param0: int, param1: int):
            swap = sequence[param0]

            sequence[param0] = sequence[param1]
            sequence[param1] = swap

        activatedIndex = Storage.UserActivatedItemIndex()

        self.sourceModel.layoutAboutToBeChanged.emit()

        swapSequenceItem(Storage.UserServers(), index0, index1)

        # Refresh index
        self.sourceModel.refreshIndexes()

        self.sourceModel.layoutChanged.emit()

        if index0 == activatedIndex:
            # Activate
            self.activateItemByIndex(index1, True)
        elif index1 == activatedIndex:
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
            self.setCurrentIndex(self.proxyIndexFromSourceRow(indexes[-1] - 1))

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
            self.setCurrentIndex(self.proxyIndexFromSourceRow(indexes[0] + 1))

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

            self.sourceModel.beginRemoveRows(
                QtCore.QModelIndex(),
                deleteIndex,
                deleteIndex,
            )

            Storage.UserServers()[deleteIndex].deleted = True
            Storage.UserServers().pop(deleteIndex)

            self.sourceModel.endRemoveRows()

            if not deleteActivated and deleteIndex < Storage.UserActivatedItemIndex():
                AppSettings.set(
                    'ActivatedItemIndex', str(Storage.UserActivatedItemIndex() - 1)
                )

        # Refresh index
        self.sourceModel.refreshIndexes()
        self.sourceModel.emitAllChanged()

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
            mbox = MBoxQuestionDelete(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = MBoxQuestionDelete(
                icon=AppQMessageBox.Icon.Question, parent=self.parent()
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = f'{indexes[0] + 1} - ' + Storage.UserServers()[
            indexes[0]
        ].getExtras('remark')
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

    def activateSelectedServer(self):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        if len(indexes) != 1:
            # Should not reach here
            return

        item = self.proxyIndexFromSourceRow(indexes[0])

        if item.isValid():
            self.handleItemActivated(item)

    def scrollToActivatedItem(self):
        activatedItem = self.activatedIndex()

        if activatedItem.isValid():
            self.setCurrentIndex(activatedItem)
            self.scrollTo(activatedItem)

    def rowFromFactory(self, fallbackIndex: int, factory: ConfigFactory) -> int:
        if (
            0 <= factory.index < len(Storage.UserServers())
            and Storage.UserServers()[factory.index] is factory
        ):
            return factory.index

        if (
            0 <= fallbackIndex < len(Storage.UserServers())
            and Storage.UserServers()[fallbackIndex] is factory
        ):
            return fallbackIndex

        for index, item in enumerate(Storage.UserServers()):
            if item is factory:
                return index

        return -1

    def flushDownloadSpeedItem(self, fallbackIndex: int, factory: ConfigFactory):
        index = self.rowFromFactory(fallbackIndex, factory)

        if index < 0:
            return

        self.flushItem(index, self.Headers.index('Speed'), factory)

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
        scheduler = (
            self.downloadSpeedMultiScheduler if isMulti else self.downloadSpeedScheduler
        )
        scheduler.enqueue(index, factory, timeout, logActionMessage)

    def testSelectedItemDownloadSpeedWithTimeoutXXX(
        self,
        scheduler: DownloadSpeedTestScheduler,
        timeout: int,
    ):
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)
        jobs = list()

        for index, reference in zip(indexes, references):
            jobs.append(DownloadSpeedTestJob(index, reference, timeout))

        scheduler.enqueueMany(jobs)

    def testSelectedItemDownloadSpeedWithTimeout(self, timeout: int):
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.downloadSpeedScheduler,
            timeout,
        )

    def testSelectedItemDownloadSpeedWithTimeoutMulti(self, timeout: int):
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.downloadSpeedMultiScheduler,
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

    def cleanup(self):
        self.downloadSpeedScheduler.cancelAll()
        self.downloadSpeedMultiScheduler.cancelAll()

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

        self.sourceModel.beginInsertRows(QtCore.QModelIndex(), index, index)

        Storage.UserServers().append(factory)

        self.sourceModel.endInsertRows()
        self.sourceModel.refreshIndexes()

        self.flushRow(index, factory)

        if index == 0:
            # The first one. Click it
            self.setCurrentIndex(self.proxyIndexFromSourceRow(0))

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
                self.handleItemActivated(self.currentIndex())
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def retranslate(self):
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            len(self.Headers) - 1,
        )
