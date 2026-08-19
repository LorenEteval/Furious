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

"""Provide widgets for user servers Qt table view."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import *
from Furious.Repository import *
from Furious.Plugins import (
    blankProfile,
    exportConfiguration,
    getPluginRegistry,
    profileFromAny,
)
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import (
    ConnectionManager,
    SubscriptionManager,
    SubscriptionUpdateBatch,
    coreLogCallback,
)
from Furious.Widget.WaitingSpinner import WaitingSpinner

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

__all__ = ['ServerTableView']

logger = logging.getLogger(__name__)

registerAppSettings('ActivatedItemIndex')
# Migrate legacy settings
registerAppSettings('ServerWidgetSectionSizeTable')
registerAppSettings('UserServersHeaderViewState')


def appIsExiting() -> bool:
    """Return the app is exiting value used by the application."""
    app = APP()

    if app is None:
        return True
    else:
        isExiting = getattr(app, 'isExiting', None)

        if callable(isExiting):
            return isExiting()
        else:
            return True


class MBoxUpdateSubsInfo(AppQMessageBox):
    """Represent m box update subs info."""

    def __init__(self, *args, **kwargs):
        """Initialize the MBoxUpdateSubsInfo."""
        self.successArgs = kwargs.pop('successArgs', list())
        self.failureArgs = kwargs.pop('failureArgs', list())

        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))

    def customText(self):
        """Return the user-facing message text for the m box update subs info."""
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
        """Keep long subscription summaries readable in the Fluent dialog."""
        if PLATFORM == 'Windows':
            self.setContentMinimumWidth(
                max((len(row) + 10) for row in self.text().split('\n'))
                * self.fontMetrics().averageCharWidth(),
            )

    def retranslate(self):
        """Refresh translated text for the m box update subs info."""
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())
        self.setColumnMinWidth()

        # Ignore informative text, buttons

        self.moveToCenter()


class TestPingLatencyWorker(QtCore.QObject, QtCore.QRunnable):
    """Run test ping latency work in the background."""

    finished = QtCore.Signal()

    def __init__(self, factory: ServerProfile):
        # Explictly called __init__
        """Initialize the TestPingLatencyWorker."""
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.factory = factory

    def run(self):
        """Run the test ping latency worker task."""
        index = self.factory.index

        if self.factory.deleted or index < 0 or index >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        assert isinstance(self.factory, ServerProfile)

        try:
            result = icmplib.ping(
                self.factory.itemAddress,
                count=1,
                timeout=2,
                interval=1,
            )
        except Exception as ex:
            # Any non-exit exceptions

            self.factory.metadata.latency = classname(ex)
        else:
            # Result address should not be empty
            if result.address and result.is_alive:
                self.factory.metadata.latency = f'{round(result.avg_rtt)}ms'
            else:
                if result.packet_loss == 1:
                    self.factory.metadata.latency = 'Timeout'
                else:
                    self.factory.metadata.latency = 'Error'
        finally:
            # Extra guard
            if not appIsExiting():
                self.finished.emit()


class TestTcpingLatencyWorker(QtCore.QObject, QtCore.QRunnable):
    """Run test tcping latency work in the background."""

    finished = QtCore.Signal()

    def __init__(self, factory: ServerProfile):
        # Explictly called __init__
        """Initialize the TestTcpingLatencyWorker."""
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.factory = factory

    def run(self):
        """Run the test tcping latency worker task."""
        index = self.factory.index

        if self.factory.deleted or index < 0 or index >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        assert isinstance(self.factory, ServerProfile)

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

            self.factory.metadata.latency = classname(ex)
        else:
            if rtts:
                self.factory.metadata.latency = f'{round(rtts[0] * 1000)}ms'
            else:
                self.factory.metadata.latency = 'Timeout'
        finally:
            # Extra guard
            if not appIsExiting():
                self.finished.emit()


class TestDownloadSpeedWorker(HttpGetManager):
    """Run test download speed work in the background."""

    progressed = QtCore.Signal()
    finished = QtCore.Signal(object)

    def __init__(
        self,
        factory: ServerProfile,
        port: int,
        timeout: int,
        parent=None,
        **kwargs,
    ):
        """Initialize the TestDownloadSpeedWorker."""
        actionMessage = kwargs.pop('actionMessage', 'test download speed')

        super().__init__(parent, actionMessage=actionMessage)

        self.factory = factory
        self.port = port
        self.timeout = timeout
        self.kwargs = kwargs

        self.hasSpeedResult = False
        self.totalBytesRead = 0

        self.hasDataCounter = 0

        self.coreManager = ConnectionManager()

        self.networkReply = None
        self.elapsedTimer = QtCore.QElapsedTimer()

        self.timeoutTimer = QtCore.QTimer(self)
        self.timeoutTimer.setSingleShot(True)
        self.timeoutTimer.timeout.connect(self.handleTimeout)

    def completionCallback(self, **kwargs):
        """Perform the required completion hook."""
        self.timeoutTimer.stop()
        self.finished.emit(self)

    def sync(self):
        # Extra guard
        """Persist the current test download speed worker data."""
        if not appIsExiting():
            self.progressed.emit()

    def isFinished(self) -> bool:
        """Return whether finished."""
        if isinstance(self.networkReply, QNetworkReply):
            return self.networkReply.isFinished()
        else:
            return True

    def abort(self):
        """Cancel the active test download speed worker operation."""
        if isinstance(self.networkReply, QNetworkReply):
            self.networkReply.abort()

    def handleTimeout(self):
        """Handle timeout."""
        try:
            if not self.isFinished():
                self.abort()
        finally:
            self.runCompletionCallback()

    def coreExitCallback(self, config: CoreConfiguration, exitcode: int):
        """Handle the core exit callback."""
        try:
            if exitcode == CoreRuntime.ExitCode.ConfigurationError.value:
                self.factory.metadata.speed = 'Invalid'
                self.sync()
            elif exitcode == CoreRuntime.ExitCode.ServerStartFailure.value:
                self.factory.metadata.speed = 'Core start failed'
                self.sync()
            elif exitcode == CoreRuntime.ExitCode.SystemShuttingDown.value:
                pass
            else:
                self.factory.metadata.speed = f'Core exited {exitcode}'
                self.sync()
        finally:
            self.runCompletionCallback()

    def _startCoreRuntime(self, config) -> bool:
        """Prepare and start a download test through its runtime factory."""
        configcopy = getPluginRegistry().prepareDownloadTest(config, self.port)

        if configcopy is None:
            self.factory.metadata.speed = 'Invalid'
            self.sync()

            return False

        self.factory.metadata.speed = 'Starting'
        self.sync()

        return self.coreManager.start(
            configcopy,
            AppBuiltinRouting.Global.value,
            self.coreExitCallback,
            msgCallbackCore=coreLogCallback(AppLogManager()),
            deepcopy=False,
            proxyModeOnly=True,
            log=False,
        )

    def start(self):
        """Start the test download speed worker."""
        try:
            if appIsExiting():
                raise

            index = self.factory.index

            if self.factory.deleted or index < 0 or index >= len(Storage.UserServers()):
                # Invalid item. Do nothing
                return

            assert isinstance(self.factory, ServerProfile)

            if not self.factory.isValid():
                # Configuration is invalid
                self.factory.metadata.speed = 'Invalid'
                self.sync()
            else:
                if not self._startCoreRuntime(self.factory) or appIsExiting():
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
                self.runCompletionCallback()

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()

            # Convert to seconds
            elapsedSecond = self.elapsedTimer.elapsed() / 1000
            downloadSpeed = self.totalBytesRead / elapsedSecond / 1024 / 1024

            self.factory.metadata.speed = f'{downloadSpeed:.2f} MiB/s'
        else:
            self.factory.metadata.speed = 'Core start failed'

        self.coreManager.stopAll()
        self.sync()

    def hasDataCallback(self, networkReply, **kwargs):
        """Handle newly available network response data."""
        self.hasDataCounter += 1

        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()

            # Convert to seconds
            elapsedSecond = self.elapsedTimer.elapsed() / 1000
            downloadSpeed = self.totalBytesRead / elapsedSecond / 1024 / 1024

            # Has speed test result
            self.hasSpeedResult = True
            self.factory.metadata.speed = f'{downloadSpeed:.2f} MiB/s'

            # Limited to save CPU resources
            if self.hasDataCounter % 25 == 0:
                self.sync()

    def failureCallback(self, networkReply, **kwargs):
        """Handle a failed network operation."""
        if not self.hasSpeedResult:
            if not self.coreManager.allRunning():
                # Core ExitCallback has been called
                return

            if (
                networkReply.error()
                == QNetworkReply.NetworkError.OperationCanceledError
            ):
                # Canceled by application
                self.factory.metadata.speed = 'Canceled'
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
                    self.factory.metadata.speed = error[:-5]
                else:
                    self.factory.metadata.speed = error

        self.coreManager.stopAll()
        self.sync()


class DownloadSpeedTestJob:
    """Represent download speed test job."""

    def __init__(
        self,
        index: int,
        factory: ServerProfile,
        timeout: int,
        logActionMessage=False,
    ):
        """Initialize the DownloadSpeedTestJob."""
        super().__init__()

        self.index = index
        self.factory = factory
        self.timeout = timeout
        self.logActionMessage = logActionMessage


class DownloadSpeedTestScheduler(QtCore.QObject):
    """Schedule and coordinate download speed test jobs."""

    SinglePort = 20809
    MultiPortStart = 30000
    MultiPortStop = 40000

    def __init__(self, table, isMulti: bool, parent=None):
        """Initialize the DownloadSpeedTestScheduler."""
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
        factory: ServerProfile,
        timeout: int,
        logActionMessage=False,
    ):
        """Handle enqueue for the download speed test scheduler."""
        self.queue.append(
            DownloadSpeedTestJob(index, factory, timeout, logActionMessage)
        )
        self.scheduleDrain()

    def enqueueMany(self, jobs: list[DownloadSpeedTestJob]):
        """Handle enqueue many for the download speed test scheduler."""
        self.queue.extend(jobs)

        self.scheduleDrain()

    def cancelAll(self):
        """Return whether cel all."""
        self.queue.clear()

        for worker, _, _ in list(self.activeJobs.values()):
            assert isinstance(worker, TestDownloadSpeedWorker)

            if not worker.isFinished():
                worker.abort()

            worker.coreManager.stopAll()
            worker.runCompletionCallback()

    def scheduleDrain(self):
        """Handle schedule drain for the download speed test scheduler."""
        if self.drainScheduled:
            return

        self.drainScheduled = True

        QtCore.QTimer.singleShot(0, self.drain)

    def drain(self):
        """Handle drain for the download speed test scheduler."""
        self.drainScheduled = False

        if appIsExiting():
            self.cancelAll()

            return

        while self.queue and len(self.activeJobs) < self.maxConcurrency:
            job = self.queue.popleft()

            assert isinstance(job.factory, ServerProfile)

            if job.factory.deleted:
                continue

            port = self.allocatePort()

            if port is None:
                self.queue.appendleft(job)

                break

            self.startJob(job, port)

    def allocatePort(self) -> Union[int, None]:
        """Return whether allocate port."""
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
        """Handle release port for the download speed test scheduler."""
        self.activePorts.discard(port)

    def startJob(self, job: DownloadSpeedTestJob, port: int):
        """Start job."""
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
        """Handle worker finished."""
        workerId = id(worker)

        try:
            _, _, port = self.activeJobs.pop(workerId)
        except KeyError:
            return

        self.releasePort(port)

        # Completed workers are children of the long-lived scheduler.  Merely
        # removing the Python dictionary entry would leave every worker (and
        # its network/timer children) in the scheduler's QObject tree.
        worker.deleteLater()

        self.scheduleDrain()


class DeleteServersProgressDialog(AppQTransientDialog):
    """Present progress and cancellation controls for delete servers."""

    def __init__(self, table, indexes, showTrayMessage=True, parent=None):
        """Initialize the DeleteServersProgressDialog."""
        super().__init__(parent)

        self.table = table
        self.indexes = list(indexes)
        self.showTrayMessage = showTrayMessage
        self.total = len(self.indexes)
        self.nextIndex = 0
        self.deletedCount = 0
        self.deletedActivated = False
        self.canceled = False
        self.finishedDeletion = False
        self.currentRemark = ''

        self.setWindowTitle(_('Delete'))
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
        self.cancelButton.clicked.connect(self.cancel)

        statusLayout = QHBoxLayout()
        statusLayout.addWidget(self.spinner)
        statusLayout.addWidget(self.statusLabel, 1)

        layout = QVBoxLayout()
        layout.addLayout(statusLayout)
        layout.addWidget(self.detailLabel)
        layout.addWidget(self.cancelButton)

        self.setLayout(layout)

        self.updateStatus()

    def setWidthAndHeight(self):
        """Apply the default size for the delete servers progress dialog."""
        self.resize(420, 150)

    def open(self):
        """Open the delete servers progress dialog asynchronously."""
        self.spinner.start()

        QtCore.QTimer.singleShot(0, self.deleteNext)

        return super().open()

    def reject(self):
        """Reject the current delete servers progress dialog values."""
        self.cancel()

    def cancel(self):
        """Cancel the delete servers progress dialog operation."""
        self.canceled = True
        self.cancelButton.setEnabled(False)
        self.updateStatus()

    def updateStatus(self):
        """Update status."""
        if self.canceled:
            self.statusLabel.setText(
                _('Canceling delete') + f'... {self.deletedCount}/{self.total}'
            )
        else:
            self.statusLabel.setText(
                _('Deleting') + f'... {self.deletedCount}/{self.total}'
            )

        if self.currentRemark:
            self.detailLabel.setText(_('Current') + f': {self.currentRemark}')
        else:
            self.detailLabel.setText('')

    @staticmethod
    def limitedRemark(remark: str) -> str:
        """Return the limited remark value used by the delete servers progress dialog."""
        remark = str(remark).strip()

        if len(remark) <= 120:
            return remark

        return remark[:117] + '...'

    def deleteNext(self):
        """Delete next."""
        if self.canceled or self.nextIndex >= self.total:
            self.finishDeletion()

            return

        originalIndex = self.indexes[self.nextIndex]
        self.nextIndex += 1
        deleteIndex = originalIndex - self.deletedCount

        if deleteIndex < 0 or deleteIndex >= len(Storage.UserServers()):
            self.updateStatus()
            QtCore.QTimer.singleShot(0, self.deleteNext)

            return

        factory = Storage.UserServers()[deleteIndex]

        self.currentRemark = self.limitedRemark(factory.itemRemark)

        if originalIndex == Storage.UserActivatedItemIndex():
            self.deletedActivated = True

        self.table.sourceModel.beginRemoveRows(
            QtCore.QModelIndex(),
            deleteIndex,
            deleteIndex,
        )

        factory.deleted = True

        Storage.UserServers().pop(deleteIndex)

        self.table.sourceModel.endRemoveRows()

        if not self.deletedActivated and deleteIndex < Storage.UserActivatedItemIndex():
            AppSettings.set(
                'ActivatedItemIndex', str(Storage.UserActivatedItemIndex() - 1)
            )

        self.deletedCount += 1
        self.updateStatus()

        QtCore.QTimer.singleShot(0, self.deleteNext)

    def finishDeletion(self):
        """Handle finish deletion for the delete servers progress dialog."""
        if self.finishedDeletion:
            return

        self.finishedDeletion = True
        self.spinner.stop()

        self.table.sourceModel.refreshIndexes()
        self.table.sourceModel.emitAllChanged()

        if self.deletedActivated:
            # Set invalid first
            AppSettings.set('ActivatedItemIndex', str(-1))

            self.table.activeServerChanged.emit()

            controller = AppConnectionController()

            if controller.isConnected():
                controller.startDisconnection(
                    _('Disconnected') if self.showTrayMessage else ''
                )

        self.accept()

    def retranslate(self):
        """Refresh translated text for the delete servers progress dialog."""
        self.setWindowTitle(_(self.windowTitle()))
        self.cancelButton.setText(_(self.cancelButton.text()))
        self.updateStatus()


class ServerTableHorizontalHeader(AppQHeaderView):
    """Provide the user servers Qt table view horizontal table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the ServerTableHorizontalHeader."""
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class ServerTableVerticalHeader(AppQHeaderView):
    """Provide the user servers Qt table view vertical table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the ServerTableVerticalHeader."""
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class ServerTableColumn:
    """Describe and render user servers Qt table view table columns."""

    def __init__(self, name: str, func: Callable[[CoreConfiguration], str] = None):
        """Initialize the ServerTableColumn."""
        self.name = name
        self.func = func

    def __call__(self, item: ServerProfile) -> str:
        """Invoke the user servers Qt table view headers as a callable."""
        if callable(self.func):
            return self.func(item)
        else:
            return getattr(item, f'item{self}')

    def __eq__(self, other):
        """Compare the user servers Qt table view headers with another value."""
        return str(self) == str(other)

    def __str__(self):
        """Return the display text for the user servers Qt table view headers."""
        return self.name


def _subscriptionRemark(item: ServerProfile) -> str:
    """Resolve a persisted subscription ID to its user-visible remark."""
    if not item.itemSubscriptionManaged:
        return ''

    subscription = Storage.UserSubs().get(item.itemSubscription, {})

    if not subscription:
        return _('Unknown Subscription')

    remark = subscription.get('remark', '') or item.itemSubscription

    return (
        remark if subscription.get('enabled', True) else f'{remark} ({_("Disabled")})'
    )


class UserServersTableModel(QtCore.QAbstractTableModel):
    """Expose user servers table data through a Qt item model."""

    SortRole = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, headers: list[ServerTableColumn], parent=None):
        """Initialize the UserServersTableModel."""
        super().__init__(parent)

        self.headers = headers

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of rows exposed by the model."""
        if parent.isValid():
            return 0

        return len(Storage.UserServers())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of columns exposed by the model."""
        if parent.isValid():
            return 0

        return len(self.headers)

    def flags(self, index):
        """Return the Qt item flags for a model index."""
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Return the data managed by the user servers table model."""
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
        """Return display data for a table header section."""
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            if 0 <= section < len(self.headers):
                return _(str(self.headers[section]))

            return None

        return section + 1

    @staticmethod
    def testResultSortValue(text: str, suffix: str):
        """Return the test result sort value value used by the user servers table model."""
        if text.endswith(suffix):
            text = text[: -len(suffix)]

        try:
            return float(text)
        except Exception:
            # Any non-exit exceptions

            return abs(hash(text)) + 2**20

    def emitRowChanged(self, row: int, column: Union[int, None] = None):
        """Handle emit row changed for the user servers table model."""
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
        """Handle emit all changed for the user servers table model."""
        if self.rowCount() == 0 or self.columnCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            [],
        )

    @staticmethod
    def refreshIndexes():
        """Refresh indexes."""
        for index, item in enumerate(Storage.UserServers()):
            item.index = index

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        """Sort the user servers table model."""
        if column < 0 or column >= self.columnCount():
            return

        activatedIndex = Storage.UserActivatedItemIndex()

        if 0 <= activatedIndex < len(Storage.UserServers()):
            activatedServerId = id(Storage.UserServers()[activatedIndex])
        else:
            activatedServerId = None

        header = self.headers[column]

        def keyFn(factory: ServerProfile):
            """Return the key fn value used by the user servers table model."""
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
    """Filter and sort user servers sort filter data."""

    def __init__(self, parent=None):
        """Initialize the UserServersSortFilterProxyModel."""
        super().__init__(parent)

        self.searchPattern = ''
        self.searchCaseSensitive = False
        self.searchUseRegex = True
        self.searchRegex = None
        self.subscriptionFilter = None
        self.sortSuspended = False

        self.setSortRole(UserServersTableModel.SortRole)
        self.setDynamicSortFilter(True)

    def sort(
        self,
        column: int,
        order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.AscendingOrder,
    ):
        """Sort the user servers sort filter proxy model."""
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
        """Set search pattern."""
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

    def setSubscriptionFilter(self, unique: str | None):
        """Limit rows to manual profiles or one subscription group."""
        self.subscriptionFilter = unique
        self.invalidateFilter()

    def filterAcceptsRow(self, sourceRow: int, sourceParent) -> bool:
        """Filter accepts row."""
        model = self.sourceModel()

        if model is None:
            return True

        if 0 <= sourceRow < len(Storage.UserServers()):
            profile = Storage.UserServers()[sourceRow]

            if self.subscriptionFilter == '':
                if profile.itemSubscriptionManaged:
                    return False
            elif (
                self.subscriptionFilter is not None
                and profile.itemSubscription != self.subscriptionFilter
            ):
                return False

        if not self.searchPattern or self.searchRegex is None:
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
        """Return display data for a table header section."""
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


class ServerTableView(
    Mixins.QTranslatable,
    Mixins.CleanupOnExit,
    AppQTableView,
):
    """Represent user servers Qt table view."""

    activeServerChanged = QtCore.Signal()

    RowHeight = 42

    Headers = [
        ServerTableColumn('Remark'),
        ServerTableColumn('Protocol'),
        ServerTableColumn('Address'),
        ServerTableColumn('Port'),
        ServerTableColumn('Transport'),
        ServerTableColumn('TLS'),
        ServerTableColumn('Subscription', _subscriptionRemark),
        ServerTableColumn('Latency'),
        ServerTableColumn('Speed'),
    ]

    def __init__(self, *args, **kwargs):
        """Initialize the server table view."""
        configurationEditorFactory = kwargs.pop('configurationEditorFactory')
        self.qrCodeWindowFactory = kwargs.pop('qrCodeWindowFactory')
        importActionsFactory = kwargs.pop('importActionsFactory')

        super().__init__(*args, **kwargs)

        self.sourceModel = UserServersTableModel(self.Headers, parent=self)
        self.proxyModel = UserServersSortFilterProxyModel(parent=self)
        self.proxyModel.setSourceModel(self.sourceModel)
        self.setModel(self.proxyModel)

        self.subsManager = SubscriptionManager(parent=self)
        self.subsManager.subscriptionsChanged.connect(self._handleSubscriptionsChanged)
        self.subsManager.updateCompleted.connect(
            self._handleSubscriptionUpdateCompleted
        )

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

        self.configurationEditor = configurationEditorFactory()

        # Install custom header
        self.setHorizontalHeader(
            ServerTableHorizontalHeader(
                parent=self,
                legacySectionSizeSettingsName='ServerWidgetSectionSizeTable',
                sectionSizeSettingsName='UserServersHeaderViewState',
            )
        )
        self.setVerticalHeader(ServerTableVerticalHeader(self))
        self.setDefaultRowHeight(self.RowHeight)

        self.horizontalHeader().setCustomSectionResizeMode()
        self.horizontalHeader().restoreSectionSize()

        self.proxyModel.sortSuspended = True
        self.setSortingEnabled(True)
        self.proxyModel.sortSuspended = False
        self.proxyModel.sort(-1)

        # Selection
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        self.customizeJSONConfigActionRef = AppQAction(
            _('Customize JSON Configuration...'),
            icon=bootstrapIcon('braces-asterisk.svg'),
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
            AppQSeparator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            AppQSeparator(),
            self.activateSelectedServerActionRef,
            AppQAction(
                _('Scroll To Activated Server'),
                callback=lambda: self.scrollToActivatedItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_G,
                ),
            ),
            AppQSeparator(),
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
            AppQSeparator(),
            self.advancedActionRef,
            AppQSeparator(),
            AppQAction(
                _('New Empty Configuration'),
                callback=lambda: self.newEmptyItem(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_N,
                ),
            ),
            *importActionsFactory(),
            AppQSeparator(),
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
        """Return the selected index value."""
        indexes = list(
            self.sourceRowFromProxyIndex(index)
            for index in self.selectionModel().selectedRows()
        )

        return sorted(list(set(index for index in indexes if index >= 0)))

    def sourceIndexFromProxyIndex(self, index: QtCore.QModelIndex):
        """Return the source index from proxy index value used by the user servers Qt table view."""
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapToSource(index)

    def proxyIndexFromSourceIndex(self, index: QtCore.QModelIndex):
        """Return the proxy index from source index value used by the user servers Qt table view."""
        if not index.isValid():
            return QtCore.QModelIndex()

        return self.proxyModel.mapFromSource(index)

    def sourceRowFromProxyIndex(self, index: QtCore.QModelIndex) -> int:
        """Return the source row from proxy index value used by the user servers Qt table view."""
        sourceIndex = self.sourceIndexFromProxyIndex(index)

        if sourceIndex.isValid():
            return sourceIndex.row()

        return -1

    def sourceRowFromProxyRow(self, row: int) -> int:
        """Return the source row from proxy row value used by the user servers Qt table view."""
        return self.sourceRowFromProxyIndex(self.proxyModel.index(row, 0))

    def proxyIndexFromSourceRow(self, row: int, column: int = 0):
        """Return the proxy index from source row value used by the user servers Qt table view."""
        if row < 0 or row >= self.sourceModel.rowCount():
            return QtCore.QModelIndex()

        return self.proxyIndexFromSourceIndex(self.sourceModel.index(row, column))

    def selectMultipleRows(self, indexes: list[int], clearCurrentSelection: bool):
        """Select multiple rows."""
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
        """Update the user servers Qt table view for a disconnected state."""
        super().disconnectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def connectedCallback(self):
        """Update the user servers Qt table view for a connected state."""
        super().connectedCallback()

        self.activateItemByIndex(Storage.UserActivatedItemIndex(), True)

    def handleItemSelectionChanged(self, *args):
        """Handle item selection changed."""
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
        """Handle item activated."""
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

        if AppConnectionController().isConnecting():
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

        if AppConnectionController().isConnected():
            AppConnectionController().startReconnection()

    def getGuiEditorByFactory(
        self, factory, **kwargs
    ) -> Union[GuiEditorWidgetQDialog, None]:
        """Return GUI editor by factory."""
        editor = getPluginRegistry().createEditorForConfig(
            factory, parent=self, **kwargs
        )

        if editor is not None:
            # These editors are created for a single add/edit operation. A Qt
            # parent alone would keep every closed native widget tree alive for
            # the lifetime of the server table.
            editor.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        return editor

    @QtCore.Slot(QtCore.QModelIndex)
    def handleItemDoubleClicked(self, modelIndex: QtCore.QModelIndex):
        """Handle item double clicked."""
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

        guiEditor.setWindowTitle(f'{index + 1} - ' + factory.itemRemark)

        try:
            guiEditor.factoryToInput(factory)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'error while converting factory to input: {ex}')

        # Keep operation metadata on the transient editor and use QObject-bound
        # slots.  Partials stored by PySide otherwise retain both the complete
        # editor tree and this application-lifetime table until disconnection.
        guiEditor._modContext = (index, factory)
        guiEditor.accepted.connect(self.handleGuiEditorAccepted)
        guiEditor.rejected.connect(self.handleGuiEditorRejected)
        guiEditor.open()

    @QtCore.Slot()
    def handleGuiEditorAccepted(self):
        """Handle GUI editor accepted."""
        editor = self.sender()

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        index, factory = editor._modContext

        logger.debug(f'guiEditor accepted with index {index}')

        modified = editor.inputToFactory(factory)

        # Still flush to row since remark may be modified
        self.flushRow(index, factory)

        if modified and index == Storage.UserActivatedItemIndex():
            showMBoxNewChangesNextTime()

        editor.accepted.disconnect()
        editor.rejected.disconnect()

        del editor._modContext

    @QtCore.Slot()
    def handleGuiEditorRejected(self):
        """Handle GUI editor rejected."""
        editor = self.sender()

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        editor.accepted.disconnect()
        editor.rejected.disconnect()

        if hasattr(editor, '_modContext'):
            del editor._modContext

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        """Handle custom context menu requested."""
        self.contextMenu.exec(self.viewport().mapToGlobal(point))

    def customSortFn(self, clickedIndex, **kwargs):
        """Handle custom sort fn for the user servers Qt table view."""
        order = (
            QtCore.Qt.SortOrder.DescendingOrder
            if kwargs.get('reverse', False)
            else QtCore.Qt.SortOrder.AscendingOrder
        )

        self.sortByColumn(clickedIndex, order)

    def activatedIndex(self):
        """Activate d index."""
        return self.proxyIndexFromSourceRow(Storage.UserActivatedItemIndex(), 0)

    def activateItemByIndex(self, index, activate):
        """Activate item by index."""
        oldIndex = Storage.UserActivatedItemIndex()
        changed = activate and oldIndex != int(index)

        if activate:
            AppSettings.set('ActivatedItemIndex', str(index))

        self.sourceModel.emitRowChanged(oldIndex)
        self.sourceModel.emitRowChanged(index)

        if changed:
            self.activeServerChanged.emit()

    def flushItem(self, row: int, column: int, item: ServerProfile):
        """Refresh item."""
        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        def searchIndex(start, stop, step=1):
            """Search index."""
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
        """Search the user servers Qt table view."""
        self.proxyModel.setSearchPattern(
            pattern,
            caseSensitive=caseSensitive,
            regex=regex,
        )

    def clearSearch(self):
        """Clear search."""
        self.search('')

    def filterBySubscription(self, unique: str | None):
        """Show all, manual, or one subscription group's profiles."""
        self.proxyModel.setSubscriptionFilter(unique)

    def addServerViaGui(
        self,
        protocol,
        windowTitle: str = APPLICATION_NAME,
        **kwargs,
    ):
        """Add server via GUI."""
        factory = blankProfile(protocol)

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

        guiEditor._addContext = factory
        guiEditor.accepted.connect(self.handleAddServerViaGuiAccepted)
        guiEditor.rejected.connect(self.handleAddServerViaGuiRejected)
        guiEditor.open()

    @QtCore.Slot()
    def handleAddServerViaGuiAccepted(self):
        """Handle add server via GUI accepted."""
        editor = self.sender()

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        factory = editor._addContext

        editor.inputToFactory(factory)

        self.appendNewItemByFactory(factory)

        editor.accepted.disconnect()
        editor.rejected.disconnect()

        del editor._addContext

    @QtCore.Slot()
    def handleAddServerViaGuiRejected(self):
        """Handle add server via GUI rejected."""
        editor = self.sender()

        if not isinstance(editor, GuiEditorWidgetQDialog):
            return

        editor.accepted.disconnect()
        editor.rejected.disconnect()

        if hasattr(editor, '_addContext'):
            del editor._addContext

    def flushRow(self, row: int, item: ServerProfile):
        """Refresh row."""
        itemIndex = item.index

        if item.deleted or itemIndex < 0 or itemIndex >= len(Storage.UserServers()):
            # Invalid item. Do nothing
            return

        if row != itemIndex:
            row = itemIndex

        self.sourceModel.emitRowChanged(row)

        if row == Storage.UserActivatedItemIndex():
            self.activeServerChanged.emit()

    def flushAll(self):
        # Refresh index
        """Refresh all."""
        self.sourceModel.refreshIndexes()
        self.sourceModel.emitAllChanged()

    def swapItem(self, index0: int, index1: int):
        """Handle swap item for the user servers Qt table view."""

        def swapSequenceItem(sequence: MutableSequence, param0: int, param1: int):
            """Handle swap sequence item for the user servers Qt table view."""
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
        """Handle new empty item for the user servers Qt table view."""
        self.appendNewItem(remark=_('Untitled'), acceptInvalid=True)

    def moveUpItemByIndex(self, index):
        """Move up item by index."""
        if index <= 0 or index >= len(Storage.UserServers()):
            # The top item, or does not exist. Do nothing
            return

        self.swapItem(index, index - 1)

    def moveUpSelectedItem(self):
        """Move up selected item."""
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
        """Move down item by index."""
        if index < 0 or index >= len(Storage.UserServers()) - 1:
            # The bottom item, or does not exist. Do nothing
            return

        self.swapItem(index, index + 1)

    def moveDownSelectedItem(self):
        """Move down selected item."""
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
        """Handle duplicate selected item for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            if 0 <= index < len(Storage.UserServers()):
                deepcopy = Storage.UserServers()[index].independentCopy()

                # A duplicate is a new manual profile, not another profile
                # managed by the source subscription.
                self.appendNewItem(
                    remark=deepcopy.itemRemark,
                    config=deepcopy,
                )

    def deleteItemByIndex(
        self, indexes, showTrayMessage=True, showProgress=True
    ) -> int:
        """Delete item by index."""
        indexes = sorted(set(indexes))

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return 0

        if showProgress and len(indexes) > 1:
            dialog = DeleteServersProgressDialog(
                self,
                indexes,
                showTrayMessage=showTrayMessage,
                parent=self.window(),
            )
            dialog.open()

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

            self.activeServerChanged.emit()

            controller = AppConnectionController()

            if controller.isConnected():
                controller.startDisconnection(
                    _('Disconnected') if showTrayMessage else ''
                )

        return len(indexes)

    def deleteSelectedItem(self):
        """Delete selected item."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def handleResultCode(_indexes, code):
            """Handle result code."""
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
        mbox.possibleRemark = (
            f'{indexes[0] + 1} - ' + Storage.UserServers()[indexes[0]].itemRemark
        )
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def editSelectedItemConfiguration(self):
        """Handle edit selected item configuration for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        if len(indexes) != 1:
            # Should not reach here
            return

        index = indexes[0]
        title = f'{index + 1} - ' + Storage.UserServers()[index].itemRemark

        self.configurationEditor.currentIndex = index
        self.configurationEditor.customWindowTitle = title
        self.configurationEditor.setWindowTitle(title)
        self.configurationEditor.setPlainText(
            Storage.UserServers()[index].toJSONString(), True
        )
        self.configurationEditor.show()

    def activateSelectedServer(self):
        """Activate selected server."""
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
        """Handle scroll to activated item for the user servers Qt table view."""
        activatedItem = self.activatedIndex()

        if activatedItem.isValid():
            self.setCurrentIndex(activatedItem)
            self.scrollTo(activatedItem)

    def rowFromFactory(self, fallbackIndex: int, factory: ServerProfile) -> int:
        """Return the row from factory value."""
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

    def flushDownloadSpeedItem(self, fallbackIndex: int, factory: ServerProfile):
        """Refresh download speed item."""
        index = self.rowFromFactory(fallbackIndex, factory)

        if index < 0:
            return

        self.flushItem(index, self.Headers.index('Speed'), factory)

    def testSelectedItemPingLatency(self):
        """Handle test selected item ping latency for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)

        for index, reference in zip(indexes, references):
            if appIsExiting():
                break

            assert isinstance(reference, ServerProfile)

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
        """Handle test selected item tcping latency for the user servers Qt table view."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        # Real selected factory
        references = list(Storage.UserServers()[index] for index in indexes)

        for index, reference in zip(indexes, references):
            if appIsExiting():
                break

            assert isinstance(reference, ServerProfile)

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
        factory: ServerProfile,
        port: int,
        timeout: int,
        isMulti: bool,
        counter=0,
        step=100,
        logActionMessage=False,
    ):
        """Handle test download speed by factory for the user servers Qt table view."""
        scheduler = (
            self.downloadSpeedMultiScheduler if isMulti else self.downloadSpeedScheduler
        )
        scheduler.enqueue(index, factory, timeout, logActionMessage)

    def testSelectedItemDownloadSpeedWithTimeoutXXX(
        self,
        scheduler: DownloadSpeedTestScheduler,
        timeout: int,
    ):
        """Handle test selected item download speed with timeout xxx for the user servers Qt table view."""
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
        """Handle test selected item download speed with timeout for the user servers Qt table view."""
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.downloadSpeedScheduler,
            timeout,
        )

    def testSelectedItemDownloadSpeedWithTimeoutMulti(self, timeout: int):
        """Handle test selected item download speed with timeout multi for the user servers Qt table view."""
        self.testSelectedItemDownloadSpeedWithTimeoutXXX(
            self.downloadSpeedMultiScheduler,
            timeout,
        )

    def testSelectedItemDownloadSpeed(self):
        """Handle test selected item download speed for the user servers Qt table view."""
        self.testSelectedItemDownloadSpeedWithTimeout(5000)

    def testSelectedItemDownloadSpeedMulti(self):
        """Handle test selected item download speed multi for the user servers Qt table view."""
        self.testSelectedItemDownloadSpeedWithTimeoutMulti(5000)

    def clearSelectedItemTestResult(self):
        """Clear selected item test result."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        for index in indexes:
            factory = Storage.UserServers()[index]
            factory.metadata.latency = ''
            factory.metadata.speed = ''

            self.flushItem(index, self.Headers.index('Latency'), factory)
            self.flushItem(index, self.Headers.index('Speed'), factory)

    def cleanup(self):
        """Release resources owned by the user servers Qt table view."""
        self.downloadSpeedScheduler.cancelAll()
        self.downloadSpeedMultiScheduler.cancelAll()

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        """Update subs by unique."""
        kwargs.pop('parent', None)

        self.subsManager.configureHttpProxy(httpProxy)
        self.subsManager.updateSubsByUnique(unique, **kwargs)

    def updateSubs(self, httpProxy: Union[str, None], **kwargs):
        """Update subs."""
        self.selectionModel().clearSelection()

        kwargs.pop('parent', None)

        self.subsManager.configureHttpProxy(httpProxy)
        self.subsManager.updateSubs(**kwargs)

    @QtCore.Slot()
    def _handleSubscriptionsChanged(self):
        """Refresh the table after the service commits repository changes."""
        self.sourceModel.beginResetModel()
        self.sourceModel.endResetModel()
        self.sourceModel.refreshIndexes()

        self.proxyModel.invalidate()

        self.flushAll()

        self.activeServerChanged.emit()

    @QtCore.Slot(object)
    def _handleSubscriptionUpdateCompleted(self, batch: SubscriptionUpdateBatch):
        """Present one semantic subscription update result batch."""
        if not batch.showMessageBox:
            return

        mbox = MBoxUpdateSubsInfo(
            successArgs=list(batch.successful),
            failureArgs=list(batch.failed),
            parent=self.window(),
        )
        mbox.setIcon(
            AppQMessageBox.Icon.Information
            if batch.successful
            else AppQMessageBox.Icon.Critical
        )
        mbox.setText(mbox.customText())
        mbox.setColumnMinWidth()
        mbox.open()

    def appendNewItemByFactory(self, factory: CoreConfiguration | ServerProfile):
        """Append new item by factory."""
        factory = ensureProfile(factory)
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
            if not AppConnectionController().isConnected():
                # Activate automatically
                self.activateItemByIndex(0, True)

    def appendNewItem(self, **kwargs):
        """Append new item."""
        acceptInvalid = kwargs.pop('acceptInvalid', False)

        model = {
            'remark': kwargs.pop('remark', ''),
            'config': kwargs.pop('config', ''),
            'subsId': kwargs.pop('subsId', ''),
        }
        tostr = f'{model}'

        factory = profileFromAny(model.pop('config', ''), **model)

        if factory.isValid():
            self.appendNewItemByFactory(factory)
        else:
            if acceptInvalid:
                self.appendNewItemByFactory(factory)
            else:
                logger.error(f'invalid item: {tostr}')

    def exportSelectedItemURI(self):
        """Export selected item URI."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        def toURI(factory) -> str:
            """Export the configuration as a share URI."""
            assert isinstance(factory, ServerProfile)

            try:
                return exportConfiguration(factory)
            except Exception:
                # Any non-exit exceptions

                return ''

        # TODO: MessageBox?
        QApplication.clipboard().setText(
            '\n'.join(list(toURI(Storage.UserServers()[index]) for index in indexes))
        )

    def exportSelectedItemQR(self):
        """Export selected item QR."""
        indexes = self.selectedIndex

        if len(indexes) == 0:
            # Nothing selected. Do nothing
            return

        window = self.qrCodeWindowFactory()
        window.initTabByIndex(indexes)

        if window.tabCount() > 0:
            window.show()

    def exportSelectedItemJSON(self):
        """Export selected item JSON."""
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
        """Show tab and spaces."""
        self.configurationEditor.showTabAndSpaces()

    def hideTabAndSpaces(self):
        """Hide tab and spaces."""
        self.configurationEditor.hideTabAndSpaces()

    def keyPressEvent(self, event):
        """Handle a key press for the user servers Qt table view."""
        if event.key() == QtCore.Qt.Key.Key_Return:
            if PLATFORM == 'Darwin':
                # Activate by Enter key on macOS
                self.handleItemActivated(self.currentIndex())
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def retranslate(self):
        """Refresh translated text for the user servers Qt table view."""
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            len(self.Headers) - 1,
        )
