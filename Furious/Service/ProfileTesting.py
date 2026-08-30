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

"""Provide identity-safe latency and download-speed profile testing."""

from __future__ import annotations

from Furious.Frozenlib import (
    APP,
    AppBuiltinRouting,
    AppLogManager,
    AppSettings,
    NETWORK_SPEED_TEST_URL,
    OS_CPU_COUNT,
    classname,
)
from Furious.Core import CoreLaunchSpec
from Furious.Interface import CoreRuntime
from Furious.Models import ServerProfile, profileConnectionFingerprint
from Furious.Plugins import getPluginRegistry
from Furious.Qt.HttpGetManager import HttpGetManager
from Furious.Qt.Signals import connectWeakly, singleShotWeakly
from Furious.Repository import Storage
from Furious.Service.ConnectionManager import ConnectionManager
from Furious.Service.LogManager import CORE_LOG_CATEGORY
from Furious.Service.TcpingService import (
    TcpingCancelEvent,
    TcpingEngine,
    TcpingRequest,
    TcpingRequestBatchEvent,
    TcpingResultEvent,
    TcpingThread,
)

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkReply

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable, Iterable

import icmplib
import weakref
import collections

__all__ = [
    'DownloadSpeedTestOptions',
    'LatencyTestOptions',
    'LatencyTestType',
    'ProfileTestField',
    'ProfileTestJobState',
    'ProfileTestManager',
    'ProfileTestResult',
    'ProfileTestTarget',
]


def _appIsExiting() -> bool:
    """Return whether the application is absent or shutting down."""
    app = APP()

    if app is None:
        return True

    isExiting = getattr(app, 'isExiting', None)

    return isExiting() if callable(isExiting) else True


class ProfileTestField(Enum):
    """Identify the persisted profile result field produced by a test."""

    Latency = 'latency'
    DownloadSpeed = 'speed'


class ProfileTestJobState(Enum):
    """Describe one scheduler-owned test job lifecycle."""

    Pending = 'pending'
    Running = 'running'
    Completed = 'completed'
    Cancelled = 'cancelled'


class LatencyTestType(Enum):
    """Select the execution model used for a latency test."""

    Ping = 'ping'
    Tcping = 'tcping'


@dataclass(frozen=True)
class LatencyTestOptions:
    """Describe how one latency target should be tested."""

    testType: LatencyTestType
    timeoutMilliseconds: int = 2000

    def __post_init__(self):
        """Normalize and validate externally supplied latency options."""
        object.__setattr__(self, 'testType', LatencyTestType(self.testType))

        if self.timeoutMilliseconds <= 0:
            raise ValueError('latency timeout must be positive')


@dataclass(frozen=True)
class DownloadSpeedTestOptions:
    """Describe one download test independently of its profile identity."""

    timeoutMilliseconds: int
    testUrl: str
    logActionMessage: bool = False

    def __post_init__(self):
        """Validate explicit download-test parameters."""
        if self.timeoutMilliseconds <= 0:
            raise ValueError('download timeout must be positive')

        if not isinstance(self.testUrl, str):
            raise TypeError('download test URL must be a string')


@dataclass(frozen=True)
class ProfileTestResult:
    """Carry one presentation-compatible outcome from execution to write-back."""

    field: ProfileTestField
    value: str
    terminal: bool = True

    def __post_init__(self):
        """Normalize enum and stored display value."""
        object.__setattr__(self, 'field', ProfileTestField(self.field))
        object.__setattr__(self, 'value', str(self.value))


@dataclass(frozen=True)
class ProfileTestTarget:
    """Identify one immutable connection snapshot by repository identity."""

    profileId: str
    subscriptionSource: str
    connectionFingerprint: str
    snapshot: ServerProfile

    @classmethod
    def capture(cls, profile: ServerProfile):
        """Capture exactly what a test should execute at enqueue time."""
        return cls(
            profile.metadata.profileId,
            profile.metadata.subscriptionSource,
            profileConnectionFingerprint(profile),
            profile.deepcopy(),
        )


def _currentTargets(profiles: Iterable[ServerProfile]):
    """Index current valid profiles and their connection fingerprints."""
    result = {}

    for profile in profiles:
        if profile.deleted:
            continue

        try:
            fingerprint = profileConnectionFingerprint(profile)
        except (TypeError, ValueError):
            continue

        result[profile.metadata.profileId] = (profile, fingerprint)

    return result


def _resolveTarget(target: ProfileTestTarget, currentTargets):
    """Resolve a target only while the same logical connection still exists."""
    current = currentTargets.get(target.profileId)

    if current is None or current[1] != target.connectionFingerprint:
        return None

    return current[0]


@dataclass
class _LatencyTestJob:
    """Pair one stable target with explicit latency-test options."""

    target: ProfileTestTarget
    options: LatencyTestOptions
    state: ProfileTestJobState = ProfileTestJobState.Pending


@dataclass
class _TcpingRequestGroup:
    """Associate one endpoint probe with every target awaiting its result."""

    request: TcpingRequest
    endpointKey: tuple
    jobs: collections.deque
    result: object = None
    networkCompleted: bool = False


PING_RESULT_EVENT_TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())


class _PingResultEvent(QtCore.QEvent):
    """Carry one blocking Ping result back after QRunnable execution returns."""

    def __init__(self, job, result):
        """Initialize one immutable scheduler delivery."""
        super().__init__(PING_RESULT_EVENT_TYPE)

        self.job = job
        self.result = result


class _PingWorker(QtCore.QRunnable):
    """Measure one ICMP endpoint using an isolated profile snapshot."""

    def __init__(self, job: _LatencyTestJob, resultReceiver):
        """Retain only immutable work and a weak scheduler receiver."""
        super().__init__()

        self.job = job
        self.resultReceiver = weakref.ref(resultReceiver)

    def run(self):
        """Execute the bounded blocking ping outside the GUI thread."""
        profile = self.job.target.snapshot
        timeoutSeconds = self.job.options.timeoutMilliseconds / 1000

        try:
            response = icmplib.ping(
                profile.itemAddress,
                count=1,
                timeout=timeoutSeconds,
                interval=1,
            )
        except Exception as ex:
            latency = classname(ex)
        else:
            if response.address and response.is_alive:
                latency = f'{round(response.avg_rtt)}ms'
            elif response.packet_loss == 1:
                latency = 'Timeout'
            else:
                latency = 'Error'

        receiver = self.resultReceiver()

        if receiver is not None and not _appIsExiting():
            try:
                QtCore.QCoreApplication.postEvent(
                    receiver, _PingResultEvent(self.job, latency)
                )
            except RuntimeError:
                pass


class _LatencyScheduler(QtCore.QObject):
    """Own bounded Ping jobs and one coalescing TCPing networking thread."""

    MaximumTcpingConcurrency = 8
    TcpingResultBatchSize = 64

    def __init__(
        self,
        resolveTarget: Callable[[ProfileTestTarget], ServerProfile | None],
        publishResult: Callable[[ProfileTestTarget, ProfileTestResult], bool],
        *,
        pingConcurrency: int,
        tcpingConcurrency: int,
        parent=None,
        threadPool=None,
        pingWorkerFactory=_PingWorker,
    ):
        """Initialize explicit dependencies and owned execution resources."""
        super().__init__(parent)

        self._resolveTarget = resolveTarget
        self._publishResult = publishResult
        self.maxConcurrency = max(int(pingConcurrency), 1)
        self.tcpingMaxConcurrency = max(int(tcpingConcurrency), 1)
        self.threadPool = threadPool
        self._ownsThreadPool = self.threadPool is None

        if self.threadPool is None:
            self.threadPool = QtCore.QThreadPool(self)
            self.threadPool.setMaxThreadCount(self.maxConcurrency)

        self.pingWorkerFactory = pingWorkerFactory
        self.queue = collections.deque()
        self.activeJobs = {}
        self.tcpingRequests = {}
        self.tcpingEndpointRequests = {}
        self.tcpingCompletionQueue = collections.deque()
        self.nextTcpingRequestId = 1
        self.tcpingThread = None
        self.tcpingEngine = None
        self.drainScheduled = False
        self.tcpingCompletionScheduled = False
        self.shuttingDown = False

    def event(self, event):
        """Apply network-thread TCPing results in this object's Qt thread."""
        if isinstance(event, _PingResultEvent):
            self.handleWorkerFinished(event.job, event.result)

            return True

        if isinstance(event, TcpingResultEvent):
            self.handleTcpingResult(event.requestId, event.result)

            return True

        return super().event(event)

    def enqueue(self, profiles, options: LatencyTestOptions):
        """Capture profiles and route them to the selected execution model."""
        if options.testType is LatencyTestType.Tcping:
            self.enqueueTcping(profiles, options)

            return

        self.queue.extend(
            _LatencyTestJob(ProfileTestTarget.capture(profile), options)
            for profile in profiles
        )
        self.scheduleDrain()

    def ensureTcpingEngine(self):
        """Lazily start the one networking event loop owned by this scheduler."""
        if self.tcpingEngine is not None:
            return self.tcpingEngine

        if self.shuttingDown:
            raise RuntimeError('cannot start TCPing after scheduler shutdown')

        engine = TcpingEngine(self, self.tcpingMaxConcurrency)
        thread = TcpingThread(engine, self)
        engine.moveToThread(thread)

        self.tcpingThread = thread
        self.tcpingEngine = engine

        thread.start()

        return engine

    @staticmethod
    def tcpingEndpoint(profile):
        """Return one normalized and validated endpoint tuple."""
        address, port = (
            str(profile.itemAddress).strip(),
            int(profile.itemPort.split(',')[0]),
        )

        if not address or not 1 <= port <= 65535:
            raise ValueError('invalid TCP endpoint')

        return (address.casefold(), port), address, port

    def enqueueTcping(self, profiles, options: LatencyTestOptions):
        """Coalesce identical endpoints into one network-thread request."""
        requests = []

        for profile in profiles:
            job = _LatencyTestJob(ProfileTestTarget.capture(profile), options)

            try:
                endpointKey, address, port = self.tcpingEndpoint(job.target.snapshot)
            except Exception as ex:
                self.completeJob(job, classname(ex))

                continue

            requestKey = (*endpointKey, options.timeoutMilliseconds)
            group = self.tcpingEndpointRequests.get(requestKey)

            if group is None:
                request = TcpingRequest(
                    self.nextTcpingRequestId,
                    address,
                    port,
                    options.timeoutMilliseconds,
                )

                self.nextTcpingRequestId += 1

                group = _TcpingRequestGroup(
                    request,
                    requestKey,
                    collections.deque(),
                )

                self.tcpingRequests[request.requestId] = group
                self.tcpingEndpointRequests[requestKey] = group

                requests.append(request)

            job.state = ProfileTestJobState.Running
            group.jobs.append(job)

        if requests:
            QtCore.QCoreApplication.postEvent(
                self.ensureTcpingEngine(), TcpingRequestBatchEvent(requests)
            )

    def completeJob(self, job, value):
        """Publish one terminal latency result through the manager boundary."""
        result = ProfileTestResult(ProfileTestField.Latency, value)

        if job.state is not ProfileTestJobState.Cancelled and self._publishResult(
            job.target, result
        ):
            job.state = ProfileTestJobState.Completed
        else:
            job.state = ProfileTestJobState.Cancelled

    def handleTcpingResult(self, requestId: int, result):
        """Queue one endpoint result for bounded result fan-out."""
        group = self.tcpingRequests.get(requestId)

        if group is None or group.networkCompleted:
            return

        group.result = result
        group.networkCompleted = True

        if self.tcpingEndpointRequests.get(group.endpointKey) is group:
            self.tcpingEndpointRequests.pop(group.endpointKey, None)

        self.tcpingCompletionQueue.append(requestId)
        self.scheduleTcpingCompletion()

    def scheduleTcpingCompletion(self):
        """Schedule one bounded GUI-thread completion batch."""
        if self.tcpingCompletionScheduled:
            return

        self.tcpingCompletionScheduled = True

        singleShotWeakly(0, self, 'drainTcpingResults')

    def drainTcpingResults(self):
        """Apply at most one fixed result batch before yielding to Qt."""
        self.tcpingCompletionScheduled = False

        remaining = self.TcpingResultBatchSize

        while self.tcpingCompletionQueue and remaining:
            requestId = self.tcpingCompletionQueue[0]
            group = self.tcpingRequests.get(requestId)

            if group is None:
                self.tcpingCompletionQueue.popleft()

                continue

            while group.jobs and remaining:
                self.completeJob(group.jobs.popleft(), group.result)

                remaining -= 1

            if group.jobs:
                break

            self.tcpingRequests.pop(requestId, None)
            self.tcpingCompletionQueue.popleft()

        if self.tcpingCompletionQueue:
            self.scheduleTcpingCompletion()

    def scheduleDrain(self):
        """Schedule one bounded GUI-thread Ping queue drain."""
        if self.drainScheduled:
            return

        self.drainScheduled = True

        singleShotWeakly(0, self, 'drain')

    def drain(self):
        """Start valid blocking Ping jobs within the private-pool limit."""
        self.drainScheduled = False

        if _appIsExiting():
            self.cancelAll()

            return

        while self.queue and len(self.activeJobs) < self.maxConcurrency:
            job = self.queue.popleft()

            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled

                continue

            job.state = ProfileTestJobState.Running
            worker = self.pingWorkerFactory(job, self)

            self.activeJobs[id(job)] = (job, worker)
            self.threadPool.start(worker)

    @QtCore.Slot(object, object)
    def handleWorkerFinished(self, job, result):
        """Release one worker and publish only a still-current result."""
        active = self.activeJobs.pop(id(job), None)

        if active is None:
            return

        self.completeJob(job, result)
        self.scheduleDrain()

    def reconcileProfiles(self):
        """Invalidate every job whose stable target no longer resolves."""
        retained = collections.deque()

        for job in self.queue:
            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled
            else:
                retained.append(job)

        self.queue = retained

        for job, worker in list(self.activeJobs.values()):
            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled
                cancel = getattr(worker, 'cancel', None)

                if callable(cancel):
                    cancel()

        self.discardTcpingJobs(lambda job: self._resolveTarget(job.target) is None)
        self.scheduleDrain()

    def invalidateSubscriptions(self, subscriptionIds):
        """Discard work captured from the specified subscriptions."""
        subscriptionIds = {str(value) for value in subscriptionIds if value}
        retained = collections.deque()

        for job in self.queue:
            if job.target.subscriptionSource in subscriptionIds:
                job.state = ProfileTestJobState.Cancelled
            else:
                retained.append(job)

        self.queue = retained

        for job, worker in list(self.activeJobs.values()):
            if job.target.subscriptionSource in subscriptionIds:
                job.state = ProfileTestJobState.Cancelled
                cancel = getattr(worker, 'cancel', None)

                if callable(cancel):
                    cancel()

        self.discardTcpingJobs(
            lambda job: job.target.subscriptionSource in subscriptionIds
        )
        self.scheduleDrain()

    def discardTcpingJobs(self, predicate):
        """Cancel matching group members and abort empty endpoint requests."""
        cancelRequestIds = []

        for requestId, group in list(self.tcpingRequests.items()):
            retained = collections.deque()

            for job in group.jobs:
                if predicate(job):
                    job.state = ProfileTestJobState.Cancelled
                else:
                    retained.append(job)

            group.jobs = retained

            if not retained:
                self.tcpingRequests.pop(requestId, None)

                if self.tcpingEndpointRequests.get(group.endpointKey) is group:
                    self.tcpingEndpointRequests.pop(group.endpointKey, None)

                if not group.networkCompleted:
                    cancelRequestIds.append(requestId)

        if cancelRequestIds and self.tcpingEngine is not None:
            QtCore.QCoreApplication.postEvent(
                self.tcpingEngine, TcpingCancelEvent(cancelRequestIds)
            )

    def cancelAll(self):
        """Cancel pending work, active TCPing, and stale-mark active Ping."""
        for job in self.queue:
            job.state = ProfileTestJobState.Cancelled

        self.queue.clear()

        for job, worker in list(self.activeJobs.values()):
            job.state = ProfileTestJobState.Cancelled
            cancel = getattr(worker, 'cancel', None)

            if callable(cancel):
                cancel()

        self.discardTcpingJobs(lambda _job: True)

    def shutdown(self):
        """Stop the dedicated TCPing event loop exactly once."""
        if self.shuttingDown:
            return

        self.shuttingDown = True
        self.cancelAll()

        if self._ownsThreadPool and not self.threadPool.waitForDone(5000):
            raise RuntimeError('Ping worker pool did not stop')

        thread = self.tcpingThread
        engine = self.tcpingEngine

        if thread is None or engine is None:
            return

        if thread.isRunning():
            if not QtCore.QMetaObject.invokeMethod(
                engine, 'shutdown', QtCore.Qt.ConnectionType.BlockingQueuedConnection
            ):
                raise RuntimeError('failed to invoke TCPing engine shutdown')

            thread.quit()

            if not thread.wait(3000):
                raise RuntimeError('TCPing networking thread did not stop')

        self.tcpingEngine = None
        self.tcpingThread = None

        thread.deleteLater()


class _DownloadSpeedWorker(HttpGetManager):
    """Own one temporary core and proxied HTTP download test."""

    CoreStartupGraceMilliseconds = CoreLaunchSpec.DefaultWaitTime

    progressed = QtCore.Signal(object, object)
    finished = QtCore.Signal(object, object)

    def __init__(
        self,
        profile: ServerProfile,
        port: int,
        options: DownloadSpeedTestOptions,
        parent=None,
    ):
        """Initialize explicit test inputs and transient Qt resources."""
        super().__init__(parent, actionMessage='test download speed')

        self.profile = profile
        self.port = port
        self.options = options
        self.result = ProfileTestResult(
            ProfileTestField.DownloadSpeed,
            '',
            terminal=False,
        )
        self.hasSpeedResult = False
        self.totalBytesRead = 0
        self.hasDataCounter = 0
        self.cancelled = False
        self._startInProgress = False
        self._completionInProgress = False
        self._pendingCompletionKwargs = None
        self.coreManager = ConnectionManager()
        self.networkReply = None

        self.elapsedTimer = QtCore.QElapsedTimer()

        self.coreStartupTimer = QtCore.QTimer(self)
        self.coreStartupTimer.setSingleShot(True)

        self.timeoutTimer = QtCore.QTimer(self)
        self.timeoutTimer.setSingleShot(True)

        connectWeakly(
            self.coreStartupTimer.timeout,
            self,
            'startDownload',
            sender=self.coreStartupTimer,
        )
        connectWeakly(
            self.timeoutTimer.timeout,
            self,
            'handleTimeout',
            sender=self.timeoutTimer,
        )

    def setResult(self, value, *, publish=True):
        """Record one semantic outcome without mutating a profile object."""
        self.result = ProfileTestResult(
            ProfileTestField.DownloadSpeed, value, terminal=False
        )

        if publish:
            self.publishProgress()

    def publishProgress(self):
        """Publish a non-terminal result while this worker remains current."""
        if not self.cancelled and not self.completionHasRun and not _appIsExiting():
            self.progressed.emit(self, self.result)

    def completionCallback(self, **_kwargs):
        """Dispose runtime callbacks before publishing terminal completion."""
        self.coreStartupTimer.stop()
        self.timeoutTimer.stop()

        try:
            self.coreManager.stopAll()
        finally:
            self.finished.emit(self, replace(self.result, terminal=True))

    def runCompletionCallback(self, **kwargs):
        """Defer terminal publication until synchronous startup has unwound."""
        if self.completionHasRun or self._completionInProgress:
            return

        if self._startInProgress:
            if self._pendingCompletionKwargs is None:
                self._pendingCompletionKwargs = dict(kwargs)

            return

        self._completionInProgress = True

        try:
            super().runCompletionCallback(**kwargs)
        finally:
            self._completionInProgress = False

    def _completionRequested(self) -> bool:
        """Return whether startup must stop before acquiring another resource."""
        return (
            self.cancelled
            or self.completionHasRun
            or self._pendingCompletionKwargs is not None
        )

    def _finishStartPhase(self, phaseContinues: bool):
        """Unwind one startup phase before honoring deferred completion."""
        pendingCompletionKwargs = self._pendingCompletionKwargs

        self._startInProgress = False
        self._pendingCompletionKwargs = None

        if not phaseContinues or pendingCompletionKwargs is not None:
            self.runCompletionCallback(**(pendingCompletionKwargs or {}))

    def isFinished(self) -> bool:
        """Return whether the HTTP operation has no active reply."""
        if isinstance(self.networkReply, QNetworkReply):
            return self.networkReply.isFinished()

        return True

    def abort(self):
        """Abort the exact active HTTP reply if one exists."""
        if isinstance(self.networkReply, QNetworkReply):
            self.networkReply.abort()

    def cancel(self):
        """Cancel network/core work and complete exactly once."""
        if self.completionHasRun:
            return

        self.cancelled = True
        self.coreStartupTimer.stop()
        self.timeoutTimer.stop()

        if not self.isFinished():
            self.abort()

        self.runCompletionCallback()

    def handleTimeout(self):
        """Abort work that exceeds its explicit deadline."""
        try:
            if not self.isFinished():
                self.abort()
        finally:
            self.runCompletionCallback()

    def coreExitCallback(self, _config, exitcode: int):
        """Translate an unexpected temporary-core exit into a result."""
        if self.cancelled or self.completionHasRun:
            return

        try:
            if exitcode == CoreRuntime.ExitCode.ConfigurationError.value:
                self.setResult('Invalid')
            elif exitcode == CoreRuntime.ExitCode.ServerStartFailure.value:
                self.setResult('Core start failed')
            elif exitcode != CoreRuntime.ExitCode.SystemShuttingDown.value:
                self.setResult(f'Core exited {exitcode}')
        finally:
            self.runCompletionCallback()

    def _startCoreRuntime(self) -> bool:
        """Prepare and start one proxy-only temporary core."""
        config = getPluginRegistry().prepareDownloadTest(self.profile, self.port)

        if config is None:
            self.setResult('Invalid')

            return False

        self.setResult('Starting')

        return self.coreManager.start(
            config,
            AppBuiltinRouting.Global.value,
            self.coreExitCallback,
            msgCallbackCore=AppLogManager().callback(CORE_LOG_CATEGORY),
            deepcopy=False,
            proxyModeOnly=True,
            log=False,
            waitCore=False,
        )

    def start(self):
        """Launch the temporary core without blocking concurrent admission."""
        if self.completionHasRun or self._startInProgress:
            return

        self._startInProgress = True

        readinessScheduled = False

        try:
            if _appIsExiting() or self._completionRequested():
                return

            if not self.profile.isValid():
                self.setResult('Invalid')
            elif self._startCoreRuntime() and not (
                _appIsExiting() or self._completionRequested()
            ):
                self.coreStartupTimer.start(self.CoreStartupGraceMilliseconds)

                readinessScheduled = True
        finally:
            self._finishStartPhase(readinessScheduled)

    @QtCore.Slot()
    def startDownload(self):
        """Start HTTP only after the concurrently launched core can become ready."""
        if self.completionHasRun or self._startInProgress:
            return

        self._startInProgress = True

        downloadStarted = False

        try:
            if _appIsExiting() or self._completionRequested():
                return

            if not self.coreManager.allRunning():
                self.setResult('Core start failed')

                return

            self.configureHttpProxy(f'127.0.0.1:{self.port}')

            if self._completionRequested():
                return

            self.networkReply = self.webGET(
                self.options.testUrl,
                logActionMessage=self.options.logActionMessage,
            )

            if self._completionRequested():
                if not self.isFinished():
                    self.abort()

                return

            self.elapsedTimer.start()
            self.timeoutTimer.start(self.options.timeoutMilliseconds)

            downloadStarted = True
        finally:
            self._finishStartPhase(downloadStarted)

    def _currentSpeed(self):
        """Return a presentation-compatible MiB/s result."""
        elapsedSeconds = self.elapsedTimer.elapsed() / 1000
        speed = self.totalBytesRead / elapsedSeconds / 1024 / 1024

        return f'{speed:.2f} MiB/s'

    def successCallback(self, networkReply, **_kwargs):
        """Publish the final download speed or core-start failure."""
        if self.cancelled or self.completionHasRun:
            return

        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()
            self.setResult(self._currentSpeed(), publish=False)
        else:
            self.setResult('Core start failed', publish=False)

        self.coreManager.stopAll()
        self.publishProgress()

    def hasDataCallback(self, networkReply, **_kwargs):
        """Update bounded intermediate progress from newly available data."""
        if self.cancelled or self.completionHasRun:
            return

        self.hasDataCounter += 1

        if self.coreManager.allRunning():
            self.totalBytesRead += networkReply.readAll().length()
            self.hasSpeedResult = True
            self.setResult(self._currentSpeed(), publish=False)

            if self.hasDataCounter % 25 == 0:
                self.publishProgress()

    def failureCallback(self, networkReply, **_kwargs):
        """Translate one HTTP failure without exposing Qt enum details."""
        if self.cancelled or self.completionHasRun:
            return

        if not self.hasSpeedResult:
            if not self.coreManager.allRunning():
                return

            if (
                networkReply.error()
                == QNetworkReply.NetworkError.OperationCanceledError
            ):
                value = 'Canceled'
            else:
                try:
                    value = networkReply.error().name
                except Exception:
                    value = 'UnknownError'

                if isinstance(value, bytes):
                    value = value.decode('utf-8', 'replace')
                elif not isinstance(value, str):
                    value = 'UnknownError'

                if value != 'UnknownError' and value.endswith('Error'):
                    value = value[:-5]

            self.setResult(value, publish=False)

        self.coreManager.stopAll()
        self.publishProgress()


@dataclass
class _DownloadSpeedTestJob:
    """Pair one stable target with explicit download-test options."""

    target: ProfileTestTarget
    options: DownloadSpeedTestOptions
    state: ProfileTestJobState = ProfileTestJobState.Pending


class _DownloadSpeedScheduler(QtCore.QObject):
    """Schedule one serial or concurrent stream of download jobs."""

    def __init__(
        self,
        resolveTarget: Callable[[ProfileTestTarget], ServerProfile | None],
        publishResult: Callable[[ProfileTestTarget, ProfileTestResult], bool],
        *,
        maxConcurrency: int,
        portRange: range,
        parent=None,
        workerFactory=_DownloadSpeedWorker,
    ):
        """Initialize explicit identity, result, concurrency, and port inputs."""
        super().__init__(parent)

        if not isinstance(portRange, range) or len(portRange) == 0:
            raise ValueError('download test port range cannot be empty')

        self._resolveTarget = resolveTarget
        self._publishResult = publishResult
        self.maxConcurrency = max(int(maxConcurrency), 1)
        self.portRange = portRange
        self.workerFactory = workerFactory
        self.queue = collections.deque()
        self.activeJobs = {}
        self.activePorts = set()
        self.nextPort = portRange.start
        self.drainScheduled = False

    def enqueue(self, profiles, options: DownloadSpeedTestOptions):
        """Capture each profile with the same explicit operation options."""
        self.queue.extend(
            _DownloadSpeedTestJob(ProfileTestTarget.capture(profile), options)
            for profile in profiles
        )
        self.scheduleDrain()

    def cancelAll(self):
        """Cancel every pending and active job through one terminal path."""
        for job in self.queue:
            job.state = ProfileTestJobState.Cancelled

        self.queue.clear()

        for worker, job, _ in list(self.activeJobs.values()):
            job.state = ProfileTestJobState.Cancelled

            worker.cancel()

    def scheduleDrain(self):
        """Schedule valid pending jobs without recursive startup."""
        if self.drainScheduled:
            return

        self.drainScheduled = True

        singleShotWeakly(0, self, 'drain')

    def drain(self):
        """Start valid jobs while concurrency and local ports are available."""
        self.drainScheduled = False

        if _appIsExiting():
            self.cancelAll()

            return

        while self.queue and len(self.activeJobs) < self.maxConcurrency:
            job = self.queue.popleft()

            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled

                continue

            port = self.allocatePort()

            if port is None:
                self.queue.appendleft(job)

                break

            self.startJob(job, port)

    def allocatePort(self):
        """Reserve the next free port from this scheduler's explicit range."""
        for _ in range(len(self.portRange)):
            port = self.nextPort

            self.nextPort += 1

            if self.nextPort >= self.portRange.stop:
                self.nextPort = self.portRange.start

            if port not in self.activePorts:
                self.activePorts.add(port)

                return port

        return None

    def startJob(self, job: _DownloadSpeedTestJob, port: int):
        """Construct one scheduler-owned transient worker and start it."""
        job.state = ProfileTestJobState.Running

        worker = self.workerFactory(
            job.target.snapshot,
            port,
            job.options,
            parent=self,
        )

        self.activeJobs[id(worker)] = (worker, job, port)

        connectWeakly(
            worker.progressed,
            self,
            'handleWorkerProgressed',
            sender=worker,
        )
        connectWeakly(
            worker.finished,
            self,
            'handleWorkerFinished',
            sender=worker,
        )

        worker.start()

    @QtCore.Slot(object, object)
    def handleWorkerProgressed(self, worker, result):
        """Publish progress only while the exact target remains current."""
        active = self.activeJobs.get(id(worker))

        if active is None:
            return

        _, job, _ = active

        if not self._publishResult(job.target, result):
            job.state = ProfileTestJobState.Cancelled

            worker.cancel()

    @QtCore.Slot(object, object)
    def handleWorkerFinished(self, worker, result):
        """Release one terminal worker after disposing its runtime callbacks."""
        active = self.activeJobs.pop(id(worker), None)

        if active is None:
            return

        _, job, port = active

        if job.state is not ProfileTestJobState.Cancelled:
            if self._publishResult(job.target, result):
                job.state = ProfileTestJobState.Completed
            else:
                job.state = ProfileTestJobState.Cancelled

        self.activePorts.discard(port)
        worker.deleteLater()
        self.scheduleDrain()

    def reconcileProfiles(self):
        """Remove pending and active jobs whose identities became stale."""
        retained = collections.deque()

        for job in self.queue:
            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled
            else:
                retained.append(job)

        self.queue = retained

        for worker, job, _port in list(self.activeJobs.values()):
            if self._resolveTarget(job.target) is None:
                job.state = ProfileTestJobState.Cancelled

                worker.cancel()

        self.scheduleDrain()

    def invalidateSubscriptions(self, subscriptionIds):
        """Remove queued and active work owned by selected subscriptions."""
        subscriptionIds = {str(value) for value in subscriptionIds if value}
        retained = collections.deque()

        for job in self.queue:
            if job.target.subscriptionSource in subscriptionIds:
                job.state = ProfileTestJobState.Cancelled
            else:
                retained.append(job)

        self.queue = retained

        for worker, job, _port in list(self.activeJobs.values()):
            if job.target.subscriptionSource in subscriptionIds:
                job.state = ProfileTestJobState.Cancelled

                worker.cancel()

        self.scheduleDrain()


class ProfileTestManager(QtCore.QObject):
    """Own profile-test identity, execution, cancellation, and write-back."""

    resultApplied = QtCore.Signal(object, object)

    SerialDownloadPorts = range(20809, 20810)
    ConcurrentDownloadPorts = range(30000, 40000)

    def __init__(
        self,
        parent=None,
        *,
        profilesProvider: Callable[[], Iterable[ServerProfile]] | None = None,
        pingConcurrency: int | None = None,
        tcpingConcurrency: int | None = None,
        downloadConcurrency: int | None = None,
    ):
        """Construct long-lived schedulers beneath one service owner."""
        super().__init__(parent)

        halfCpu = max(OS_CPU_COUNT // 2, 1)
        pingConcurrency = halfCpu if pingConcurrency is None else pingConcurrency
        tcpingConcurrency = (
            min(halfCpu, _LatencyScheduler.MaximumTcpingConcurrency)
            if tcpingConcurrency is None
            else tcpingConcurrency
        )
        downloadConcurrency = (
            halfCpu if downloadConcurrency is None else downloadConcurrency
        )

        self._profilesProvider = profilesProvider or Storage.UserServers
        self._targets = _currentTargets(self._profilesProvider())
        self._latencyScheduler = _LatencyScheduler(
            self.resolveTarget,
            self.applyResult,
            pingConcurrency=pingConcurrency,
            tcpingConcurrency=tcpingConcurrency,
            parent=self,
        )
        self._serialDownloadScheduler = _DownloadSpeedScheduler(
            self.resolveTarget,
            self.applyResult,
            maxConcurrency=1,
            portRange=self.SerialDownloadPorts,
            parent=self,
        )
        self._concurrentDownloadScheduler = _DownloadSpeedScheduler(
            self.resolveTarget,
            self.applyResult,
            maxConcurrency=downloadConcurrency,
            portRange=self.ConcurrentDownloadPorts,
            parent=self,
        )
        self._shuttingDown = False

    def resolveTarget(self, target: ProfileTestTarget):
        """Resolve a captured target through the mutation-refreshed identity map."""
        return _resolveTarget(target, self._targets)

    def applyResult(self, target: ProfileTestTarget, result: ProfileTestResult) -> bool:
        """Validate and write one result at the subsystem's sole commit boundary."""
        profile = self.resolveTarget(target)

        if profile is None:
            return False

        self._writeResult(profile, result)

        return True

    def _writeResult(self, profile: ServerProfile, result: ProfileTestResult):
        """Persist one compatible display value and notify presentation owners."""
        setattr(profile.metadata, result.field.value, result.value)

        self.resultApplied.emit(profile, result)

    def testPing(self, profiles, *, timeoutMilliseconds=2000):
        """Queue ICMP latency tests for immutable profile snapshots."""
        self._latencyScheduler.enqueue(
            profiles,
            LatencyTestOptions(LatencyTestType.Ping, timeoutMilliseconds),
        )

    def testTcping(self, profiles, *, timeoutMilliseconds=2000):
        """Queue coalesced asynchronous TCP latency tests."""
        self._latencyScheduler.enqueue(
            profiles,
            LatencyTestOptions(LatencyTestType.Tcping, timeoutMilliseconds),
        )

    def testDownloadSpeed(
        self,
        profiles,
        *,
        timeoutMilliseconds=5000,
        concurrent=True,
        testUrl=None,
        logActionMessage=False,
    ):
        """Queue serial or concurrent downloads with explicit operation options."""
        if testUrl is None:
            try:
                configuredUrl = AppSettings.get('CustomNetworkSpeedTestURL')
            except AttributeError:
                configuredUrl = None

            testUrl = (
                configuredUrl
                if isinstance(configuredUrl, str)
                else NETWORK_SPEED_TEST_URL
            )

        options = DownloadSpeedTestOptions(
            timeoutMilliseconds,
            testUrl,
            bool(logActionMessage),
        )

        scheduler = (
            self._concurrentDownloadScheduler
            if concurrent
            else self._serialDownloadScheduler
        )
        scheduler.enqueue(profiles, options)

    def clearResults(self, profiles):
        """Clear both presentation-compatible result fields for current profiles."""
        results = (
            ProfileTestResult(ProfileTestField.Latency, ''),
            ProfileTestResult(ProfileTestField.DownloadSpeed, ''),
        )

        for profile in profiles:
            for result in results:
                self._writeResult(profile, result)

    def reconcileProfiles(self):
        """Refresh current identity once and proactively invalidate stale work."""
        self._targets = _currentTargets(self._profilesProvider())
        self._latencyScheduler.reconcileProfiles()
        self._serialDownloadScheduler.reconcileProfiles()
        self._concurrentDownloadScheduler.reconcileProfiles()

    def invalidateSubscriptions(self, subscriptionIds, *, clearResults=False):
        """Invalidate selected groups without disturbing unrelated work."""
        subscriptionIds = {str(value) for value in subscriptionIds if value}

        self._latencyScheduler.invalidateSubscriptions(subscriptionIds)
        self._serialDownloadScheduler.invalidateSubscriptions(subscriptionIds)
        self._concurrentDownloadScheduler.invalidateSubscriptions(subscriptionIds)

        if clearResults:
            profiles = [
                profile
                for profile in self._profilesProvider()
                if profile.metadata.subscriptionSource in subscriptionIds
            ]
            self.clearResults(profiles)

        self.reconcileProfiles()

    def shutdown(self):
        """Cancel exact work and stop every owned reusable execution resource."""
        if self._shuttingDown:
            return

        self._shuttingDown = True
        self._latencyScheduler.shutdown()
        self._serialDownloadScheduler.cancelAll()
        self._concurrentDownloadScheduler.cancelAll()
