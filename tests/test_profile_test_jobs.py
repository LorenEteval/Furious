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

"""Protect profile-test identity, scheduling, cancellation, and Qt lifetimes."""

from __future__ import annotations

from Furious.Backends.Configuration import ConfigXray
from Furious.Frozenlib import AppSettings, OS_CPU_COUNT
from Furious.Models import ServerProfile
from Furious.Repository import Storage
from Furious.Service.ProfileTesting import (
    DownloadSpeedTestOptions,
    LatencyTestOptions,
    LatencyTestType,
    ProfileTestField,
    ProfileTestJobState,
    ProfileTestManager,
    ProfileTestResult,
    ProfileTestTarget,
    _DownloadSpeedWorker,
    _PingResultEvent,
)
from Furious.Service.TcpingService import TcpingEngine
from Furious.Widget.ServerTableView import ServerTableView

from PySide6 import QtCore, QtNetwork
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    waitFor,
)

import threading
import unittest

from types import SimpleNamespace
from unittest import mock


class _ControlledDownloadWorker(QtCore.QObject):
    """Expose deterministic progress and completion through real Qt signals."""

    progressed = QtCore.Signal(object, object)
    finished = QtCore.Signal(object, object)
    instances = []

    def __init__(self, profile, port, options, parent=None):
        """Retain explicit inputs without changing the profile snapshot."""
        super().__init__(parent)

        self.profile = profile
        self.port = port
        self.options = options
        self.cancelCount = 0
        self.terminal = False
        self.result = ProfileTestResult(
            ProfileTestField.DownloadSpeed,
            '',
            terminal=False,
        )
        self.instances.append(self)

    def start(self):
        """Leave completion under explicit test control."""

    def publish(self, speed):
        """Publish one non-terminal result without mutating the snapshot."""
        if self.terminal:
            return

        self.result = ProfileTestResult(
            ProfileTestField.DownloadSpeed,
            speed,
            terminal=False,
        )
        self.progressed.emit(self, self.result)

    def finish(self, speed):
        """Complete this worker exactly once with an explicit result."""
        if self.terminal:
            return

        self.result = ProfileTestResult(ProfileTestField.DownloadSpeed, speed)
        self.terminal = True
        self.finished.emit(self, self.result)

    def cancel(self):
        """Record cancellation and publish one terminal cancellation signal."""
        if self.terminal:
            return

        self.cancelCount += 1
        self.terminal = True
        self.finished.emit(self, ProfileTestResult(ProfileTestField.DownloadSpeed, ''))


class _ControlledLatencyWorker(QtCore.QRunnable):
    """Leave a Ping QRunnable's result ordering under test control."""

    def __init__(self, job, receiver):
        """Retain the explicit job and scheduler receiver."""
        super().__init__()
        self.job = job
        self.receiver = receiver

    def run(self):
        """Do nothing because the controlled pool does not execute workers."""

    def finish(self, result):
        """Post one result through the production scheduler event boundary."""
        QtCore.QCoreApplication.postEvent(
            self.receiver,
            _PingResultEvent(self.job, result),
        )


class _ControlledThreadPool:
    """Collect scheduler-started QRunnables without executing them."""

    def __init__(self):
        """Initialize an empty worker list."""
        self.started = []

    def start(self, worker):
        """Record one worker for explicit signal delivery."""
        self.started.append(worker)

    @staticmethod
    def waitForDone(_timeout):
        """Represent a deterministic pool with no background execution."""
        return True


class _CoreManagerProbe:
    """Record exact runtime disposal before worker QObject deletion."""

    def __init__(self):
        """Initialize a stopped runtime owner."""
        self.stopCount = 0

    @staticmethod
    def allRunning():
        """Represent the core-death side of the reported race."""
        return False

    def stopAll(self):
        """Record callback and runtime disposal."""
        self.stopCount += 1


class _ImmediateCoreManager(_CoreManagerProbe):
    """Launch immediately while recording the embedded-core wait policy."""

    def __init__(self):
        """Initialize one ready runtime and its captured start calls."""
        super().__init__()

        self.startCalls = []

    def start(self, *args, **kwargs):
        """Record a non-blocking launch and report immediate process creation."""
        self.startCalls.append((args, kwargs))

        return True

    @staticmethod
    def allRunning():
        """Keep the fake runtime alive until the worker is cancelled."""
        return True


class _CancelDuringStartDownloadWorker(_DownloadSpeedWorker):
    """Re-enter subscription invalidation while a worker is starting."""

    instances = []

    def __init__(self, *args, **kwargs):
        """Retain wrappers so native deletion remains observable."""
        super().__init__(*args, **kwargs)
        self.instances.append(self)

    def _startCoreRuntime(self):
        """Cancel this worker at the reentrant runtime-start boundary."""
        self.parent().invalidateSubscriptions(
            {self.profile.metadata.subscriptionSource}
        )
        processQtEvents()

        return True


class ProfileTestServiceTest(unittest.TestCase):
    """Exercise the self-contained profile-test subsystem."""

    @classmethod
    def setUpClass(cls):
        """Create the shared isolated QApplication."""
        application()

    def setUp(self):
        """Reset controlled owners for each case."""
        self.profiles = []
        self.managers = []
        _ControlledDownloadWorker.instances = []
        _CancelDuringStartDownloadWorker.instances = []

    def tearDown(self):
        """Stop service-owned threads and collect deferred QObjects."""
        for manager in reversed(self.managers):
            manager.shutdown()
            manager.deleteLater()

        application().threadPool.waitForDone(5000)
        collectAtBoundary()

    @staticmethod
    def _profile(name: str, address: str, port: int = 443):
        """Build one valid-enough profile with stable identity."""
        return ServerProfile.fromConfiguration(
            ConfigXray(
                {
                    'outbounds': [
                        {
                            'tag': 'proxy',
                            'protocol': 'vless',
                            'settings': {
                                'vnext': [
                                    {
                                        'address': address,
                                        'port': port,
                                        'users': [{}],
                                    }
                                ]
                            },
                        }
                    ]
                }
            ),
            {'displayName': name},
        )

    def _setProfiles(self, profiles):
        """Commit one current repository view for the injected provider."""
        self.profiles[:] = profiles

        for index, profile in enumerate(self.profiles):
            profile.index = index

    def _manager(self, profiles, *, controlledDownloads=True):
        """Construct one manager around an injected current-profile provider."""
        self._setProfiles(profiles)
        manager = ProfileTestManager(
            profilesProvider=lambda: self.profiles,
            pingConcurrency=1,
            tcpingConcurrency=2,
            downloadConcurrency=1,
        )

        if controlledDownloads:
            manager._serialDownloadScheduler.workerFactory = _ControlledDownloadWorker
            manager._concurrentDownloadScheduler.workerFactory = (
                _ControlledDownloadWorker
            )

        self.managers.append(manager)

        return manager

    def testDefaultConcurrencyKeepsBlockingPingInPrivateHalfCpuPool(self):
        """Keep blocking Ping off shared workers with the requested default limit."""
        manager = ProfileTestManager(profilesProvider=lambda: self.profiles)
        self.managers.append(manager)
        scheduler = manager._latencyScheduler

        self.assertEqual(scheduler.maxConcurrency, max(OS_CPU_COUNT // 2, 1))
        self.assertIsInstance(scheduler.threadPool, QtCore.QThreadPool)
        self.assertIsNot(scheduler.threadPool, application().threadPool)
        self.assertEqual(
            scheduler.threadPool.maxThreadCount(),
            scheduler.maxConcurrency,
        )

    def testConcurrentDownloadLaunchesEveryAdmittedCoreBeforeReadinessWait(self):
        """Do not serialize admitted jobs behind each core's readiness grace."""
        profiles = [
            self._profile(f'profile-{index}', f'{index}.example') for index in range(4)
        ]
        manager = self._manager(profiles, controlledDownloads=False)
        scheduler = manager._concurrentDownloadScheduler
        scheduler.maxConcurrency = len(profiles)
        workers = []

        def workerFactory(*args, **kwargs):
            """Create a real worker around an immediate fake core runtime."""
            worker = _DownloadSpeedWorker(*args, **kwargs)
            worker.CoreStartupGraceMilliseconds = 60_000
            worker.coreManager = _ImmediateCoreManager()
            workers.append(worker)

            return worker

        scheduler.workerFactory = workerFactory
        registry = mock.Mock()
        registry.prepareDownloadTest.side_effect = lambda profile, _port: profile

        with (
            mock.patch(
                'Furious.Service.ProfileTesting.getPluginRegistry',
                return_value=registry,
            ),
            mock.patch('Furious.Service.ProfileTesting.AppLogManager'),
        ):
            manager.testDownloadSpeed(profiles, concurrent=True)
            processQtEvents()

        self.assertEqual(len(workers), len(profiles))
        self.assertFalse(scheduler.queue)
        self.assertEqual(len(scheduler.activeJobs), len(profiles))

        for profile, worker in zip(profiles, workers):
            self.assertEqual(profile.metadata.speed, 'Starting')
            self.assertIsNone(worker.networkReply)
            self.assertTrue(worker.coreStartupTimer.isActive())
            self.assertEqual(len(worker.coreManager.startCalls), 1)
            self.assertIs(
                worker.coreManager.startCalls[0][1].get('waitCore'),
                False,
            )

        manager.shutdown()

        self.assertTrue(
            all(not worker.coreStartupTimer.isActive() for worker in workers)
        )
        self.assertTrue(waitFor(lambda: all(not isValid(worker) for worker in workers)))

    def testDownloadReconciliationCancelsStaleAndStartsNextValidTarget(self):
        """Compact stale work while preserving a current reordered target."""
        active = self._profile('active', 'active.example')
        queued = self._profile('queued', 'queued.example')
        valid = self._profile('valid', 'valid.example')
        manager = self._manager((active, queued, valid))
        scheduler = manager._serialDownloadScheduler

        manager.testDownloadSpeed(
            (active, queued, valid),
            concurrent=False,
        )
        processQtEvents()

        first = _ControlledDownloadWorker.instances[0]
        active.deleted = True
        queued.deleted = True
        self._setProfiles((valid,))
        manager.reconcileProfiles()

        self.assertEqual(first.cancelCount, 1)
        self.assertEqual(len(scheduler.queue), 1)

        first.publish('stale result')
        self.assertEqual(valid.metadata.speed, '')
        processQtEvents()

        self.assertFalse(isValid(first))
        second = _ControlledDownloadWorker.instances[1]
        self.assertEqual(
            second.profile.metadata.profileId,
            valid.metadata.profileId,
        )

        second.finish('8.50 MiB/s')
        processQtEvents()

        self.assertEqual(valid.metadata.speed, '8.50 MiB/s')
        self.assertFalse(scheduler.queue)
        self.assertFalse(scheduler.activeJobs)

    def testConnectionEditCancelsRunningAndQueuedSnapshots(self):
        """Invalidate a stable ID when its connection fingerprint changes."""
        running = self._profile('running', 'old-running.example')
        queued = self._profile('queued', 'old-queued.example')
        manager = self._manager((running, queued))
        scheduler = manager._serialDownloadScheduler

        manager.testDownloadSpeed((running, queued), concurrent=False)
        processQtEvents()

        worker = _ControlledDownloadWorker.instances[0]
        running.connection['address'] = 'new-running.example'
        queued.connection['address'] = 'new-queued.example'
        manager.reconcileProfiles()

        self.assertEqual(worker.cancelCount, 1)
        self.assertFalse(scheduler.queue)
        processQtEvents()
        self.assertFalse(scheduler.activeJobs)

        worker.publish('stale result')
        self.assertEqual(running.metadata.speed, '')
        self.assertEqual(queued.metadata.speed, '')

    def testReorderAndSubscriptionMovePreserveLogicalJobs(self):
        """Ignore row and ownership metadata changes for unchanged connections."""
        firstProfile = self._profile('first', 'first.example')
        secondProfile = self._profile('second', 'second.example')
        manager = self._manager((firstProfile, secondProfile))
        scheduler = manager._serialDownloadScheduler

        manager.testDownloadSpeed(
            (firstProfile, secondProfile),
            concurrent=False,
        )
        processQtEvents()
        firstWorker = _ControlledDownloadWorker.instances[0]

        self._setProfiles((secondProfile, firstProfile))
        firstProfile.metadata.subscriptionSource = 'new-subscription'
        manager.reconcileProfiles()

        self.assertEqual(firstWorker.cancelCount, 0)
        self.assertEqual(len(scheduler.queue), 1)

        firstWorker.finish('1.00 MiB/s')
        processQtEvents()
        secondWorker = _ControlledDownloadWorker.instances[1]
        secondWorker.finish('2.00 MiB/s')
        processQtEvents()

        self.assertEqual(firstProfile.metadata.speed, '1.00 MiB/s')
        self.assertEqual(secondProfile.metadata.speed, '2.00 MiB/s')
        self.assertFalse(scheduler.queue)
        self.assertFalse(scheduler.activeJobs)

    def testRemovingEveryTargetLeavesDownloadSchedulerEmpty(self):
        """Cancel active work and compact the entire pending collection."""
        profiles = [
            self._profile('one', 'one.example'),
            self._profile('two', 'two.example'),
            self._profile('three', 'three.example'),
        ]
        manager = self._manager(profiles)
        scheduler = manager._serialDownloadScheduler

        manager.testDownloadSpeed(profiles, concurrent=False)
        processQtEvents()
        jobs = [entry[1] for entry in scheduler.activeJobs.values()]
        jobs.extend(scheduler.queue)
        worker = _ControlledDownloadWorker.instances[0]

        for profile in profiles:
            profile.deleted = True

        self._setProfiles(())
        manager.reconcileProfiles()
        processQtEvents()

        self.assertEqual(worker.cancelCount, 1)
        self.assertTrue(all(job.state is ProfileTestJobState.Cancelled for job in jobs))
        self.assertFalse(scheduler.queue)
        self.assertFalse(scheduler.activeJobs)

    def testPingDropsStaleRunningResultAndQueuedTarget(self):
        """Stale-mark active Ping and remove invalid pending work."""
        running = self._profile('running', 'running.example')
        queued = self._profile('queued', 'queued.example')
        valid = self._profile('valid', 'valid.example')
        manager = self._manager((running, queued, valid))
        scheduler = manager._latencyScheduler
        pool = _ControlledThreadPool()
        scheduler.threadPool = pool
        scheduler.pingWorkerFactory = _ControlledLatencyWorker

        manager.testPing((running, queued, valid))
        processQtEvents()
        first = pool.started[0]

        running.deleted = True
        queued.deleted = True
        self._setProfiles((valid,))
        manager.reconcileProfiles()

        self.assertIs(first.job.state, ProfileTestJobState.Cancelled)
        self.assertEqual(len(scheduler.queue), 1)

        first.finish('1ms')
        processQtEvents()

        self.assertEqual(valid.metadata.latency, '')
        self.assertEqual(len(pool.started), 2)

        second = pool.started[1]
        second.finish('7ms')
        processQtEvents()

        self.assertEqual(valid.metadata.latency, '7ms')
        self.assertFalse(scheduler.queue)
        self.assertFalse(scheduler.activeJobs)

    def testRealThreadPoolPingDiscardsResultAfterInPlaceEdit(self):
        """Exercise blocking Ping delivery while the target changes mid-call."""
        profile = self._profile('profile', 'old.example')
        manager = self._manager((profile,))
        scheduler = manager._latencyScheduler
        started = threading.Event()
        release = threading.Event()

        def ping(*_args, **_kwargs):
            """Hold the real worker until its target becomes stale."""
            started.set()
            release.wait(5)

            return SimpleNamespace(
                address='old.example',
                is_alive=True,
                avg_rtt=3.2,
                packet_loss=0,
            )

        try:
            with mock.patch(
                'Furious.Service.ProfileTesting.icmplib.ping',
                side_effect=ping,
            ):
                manager.testPing((profile,))
                processQtEvents()
                self.assertTrue(started.wait(2))

                profile.connection['address'] = 'new.example'
                manager.reconcileProfiles()
                release.set()

                self.assertTrue(waitFor(lambda: not scheduler.activeJobs, timeout=5000))

            self.assertEqual(profile.metadata.latency, '')
        finally:
            release.set()

    def testTcpingUsesOneNetworkThreadAndDeduplicatesEndpoints(self):
        """Probe a shared endpoint once in the dedicated Qt network thread."""
        server = QtNetwork.QTcpServer()
        self.assertTrue(
            server.listen(QtNetwork.QHostAddress.SpecialAddress.LocalHost, 0)
        )
        first = self._profile('first', '127.0.0.1', server.serverPort())
        second = self._profile('second', '127.0.0.1', server.serverPort())
        manager = self._manager((first, second))
        scheduler = manager._latencyScheduler
        guiEventDelivered = threading.Event()

        try:
            manager.testTcping((first, second))
            QtCore.QTimer.singleShot(0, guiEventDelivered.set)

            self.assertEqual(len(scheduler.tcpingRequests), 1)
            self.assertEqual(
                len(next(iter(scheduler.tcpingRequests.values())).jobs),
                2,
            )
            self.assertIs(scheduler.tcpingEngine.thread(), scheduler.tcpingThread)
            self.assertIsNot(scheduler.tcpingThread, application().thread())
            self.assertTrue(waitFor(lambda: not scheduler.tcpingRequests, timeout=2000))
            self.assertTrue(guiEventDelivered.is_set())
            self.assertRegex(first.metadata.latency, r'^\d+ms$')
            self.assertEqual(second.metadata.latency, first.metadata.latency)

            connections = 0

            while server.hasPendingConnections():
                socket = server.nextPendingConnection()
                connections += 1
                socket.deleteLater()

            self.assertEqual(connections, 1)
        finally:
            server.close()

    def testTcpingDoesNotCoalesceDifferentTimeoutPolicies(self):
        """Keep endpoint identity separate from explicit execution options."""
        first = self._profile('first', '192.0.2.1', 9)
        second = self._profile('second', '192.0.2.1', 9)
        manager = self._manager((first, second))
        scheduler = manager._latencyScheduler
        eventSink = QtCore.QObject()
        scheduler.tcpingEngine = eventSink

        try:
            manager.testTcping((first,), timeoutMilliseconds=1000)
            manager.testTcping((second,), timeoutMilliseconds=2000)

            self.assertEqual(len(scheduler.tcpingRequests), 2)
            self.assertEqual(
                {
                    group.request.timeoutMilliseconds
                    for group in scheduler.tcpingRequests.values()
                },
                {1000, 2000},
            )
        finally:
            scheduler.tcpingEngine = None
            eventSink.deleteLater()

    def testTcpingCancellationRemovesEndpointRequestImmediately(self):
        """Invalidate a TCPing group before a network result reaches profiles."""
        profile = self._profile('profile', '192.0.2.1', 9)
        profile.metadata.subscriptionSource = 'group-a'
        manager = self._manager((profile,))
        scheduler = manager._latencyScheduler

        manager.testTcping((profile,))
        group = next(iter(scheduler.tcpingRequests.values()))
        job = group.jobs[0]
        scheduler.invalidateSubscriptions({'group-a'})

        self.assertIs(job.state, ProfileTestJobState.Cancelled)
        self.assertFalse(scheduler.tcpingRequests)
        self.assertFalse(scheduler.tcpingEndpointRequests)
        processQtEvents()
        self.assertEqual(profile.metadata.latency, '')

    def testTcpingSharedResultFanOutIsBoundedPerGuiBatch(self):
        """Yield between fixed-size write-back batches for a shared endpoint."""
        profiles = tuple(
            self._profile(f'profile {index}', 'shared.example') for index in range(130)
        )
        manager = self._manager(profiles)
        scheduler = manager._latencyScheduler
        eventSink = QtCore.QObject()
        scheduler.tcpingEngine = eventSink

        try:
            manager.testTcping(profiles)
            requestId = next(iter(scheduler.tcpingRequests))
            scheduler.handleTcpingResult(requestId, '5ms')
            scheduler.drainTcpingResults()

            self.assertEqual(
                sum(profile.metadata.latency == '5ms' for profile in profiles),
                scheduler.TcpingResultBatchSize,
            )
            self.assertTrue(scheduler.tcpingCompletionQueue)

            while scheduler.tcpingCompletionQueue:
                scheduler.drainTcpingResults()

            self.assertTrue(
                all(profile.metadata.latency == '5ms' for profile in profiles)
            )
        finally:
            scheduler.tcpingEngine = None
            eventSink.deleteLater()

    def testTcpingAdaptiveWindowStaysBoundedAndBacksOffOnDeadline(self):
        """Grow conservatively on success and back off after a deadline."""
        receiver = QtCore.QObject()
        engine = TcpingEngine(receiver, maxConcurrency=8)

        self.assertEqual(engine.currentConcurrency, 2)

        for _index in range(4):
            engine.recordOutcome(False)

        self.assertEqual(engine.currentConcurrency, 3)
        engine.recordOutcome(True)
        self.assertEqual(engine.currentConcurrency, 1)

        for _index in range(200):
            engine.recordOutcome(False)

        self.assertEqual(engine.currentConcurrency, 8)
        engine.deleteLater()
        receiver.deleteLater()
        processQtEvents()

    def testTcpingNetworkingThreadHasRepeatableTerminalCleanup(self):
        """Stop and destroy the reusable engine and thread repeatedly."""
        for iteration in range(10):
            profile = self._profile(
                f'profile {iteration}',
                '192.0.2.1',
                9,
            )
            manager = self._manager((profile,))
            scheduler = manager._latencyScheduler
            engine = scheduler.ensureTcpingEngine()
            thread = scheduler.tcpingThread

            manager.shutdown()
            self.assertFalse(thread.isRunning())

            manager.deleteLater()
            self.managers.remove(manager)
            processQtEvents()

            self.assertFalse(isValid(engine))
            self.assertFalse(isValid(thread))

    def testSubscriptionInvalidationCannotDeleteWorkerDuringStart(self):
        """Defer terminal deletion until a reentrant start call unwinds."""
        profile = self._profile('profile', 'profile.example')
        profile.metadata.subscriptionSource = 'subscription-a'
        manager = self._manager((profile,), controlledDownloads=False)
        scheduler = manager._serialDownloadScheduler
        scheduler.workerFactory = _CancelDuringStartDownloadWorker

        for _index in range(25):
            manager.testDownloadSpeed((profile,), concurrent=False)
            processQtEvents()
            worker = _CancelDuringStartDownloadWorker.instances[-1]

            self.assertFalse(scheduler.activeJobs)
            self.assertFalse(scheduler.activePorts)
            self.assertFalse(isValid(worker))

    def testSubscriptionCommitInvalidatesOnlyItsOldProfileJobs(self):
        """Clear one committed group while preserving unrelated test work."""
        retained = self._profile('retained', 'retained.example')
        removed = self._profile('removed', 'removed.example')
        replacement = self._profile('replacement', 'replacement.example')
        other = self._profile('other', 'other.example')
        manual = self._profile('manual', 'manual.example')

        for profile in (retained, removed, replacement):
            profile.metadata.subscriptionSource = 'group-a'

        other.metadata.subscriptionSource = 'group-b'

        for profile in (retained, replacement, other, manual):
            profile.metadata.latency = f'{profile.itemRemark} latency'
            profile.metadata.speed = f'{profile.itemRemark} speed'

        manager = self._manager((retained, removed, other, manual))
        latencyScheduler = manager._latencyScheduler
        pool = _ControlledThreadPool()
        latencyScheduler.threadPool = pool
        latencyScheduler.pingWorkerFactory = _ControlledLatencyWorker

        manager.testPing((retained, removed, other))
        manager.testDownloadSpeed(
            (retained, removed, other),
            concurrent=False,
        )
        manager.testDownloadSpeed((retained,), concurrent=True)
        processQtEvents()

        activeLatency = pool.started[0]
        serialWorker = next(
            worker
            for worker in _ControlledDownloadWorker.instances
            if worker.port in manager.SerialDownloadPorts
        )
        concurrentWorker = next(
            worker
            for worker in _ControlledDownloadWorker.instances
            if worker.port in manager.ConcurrentDownloadPorts
        )

        self._setProfiles((retained, replacement, other, manual))
        manager.invalidateSubscriptions({'group-a'}, clearResults=True)

        self.assertIs(activeLatency.job.state, ProfileTestJobState.Cancelled)
        self.assertEqual(serialWorker.cancelCount, 1)
        self.assertEqual(concurrentWorker.cancelCount, 1)
        self.assertTrue(
            all(
                job.target.subscriptionSource == 'group-b'
                for job in latencyScheduler.queue
            )
        )
        self.assertTrue(
            all(
                job.target.subscriptionSource == 'group-b'
                for job in manager._serialDownloadScheduler.queue
            )
        )
        self.assertFalse(manager._concurrentDownloadScheduler.queue)

        self.assertEqual(retained.metadata.latency, '')
        self.assertEqual(retained.metadata.speed, '')
        self.assertEqual(replacement.metadata.latency, '')
        self.assertEqual(replacement.metadata.speed, '')
        self.assertEqual(other.metadata.latency, 'other latency')
        self.assertEqual(other.metadata.speed, 'other speed')
        self.assertEqual(manual.metadata.latency, 'manual latency')
        self.assertEqual(manual.metadata.speed, 'manual speed')

        activeLatency.finish('stale')
        processQtEvents()
        self.assertEqual(retained.metadata.latency, '')
        self.assertEqual(len(pool.started), 2)

        otherLatency = pool.started[1]
        otherLatency.finish('9ms')
        processQtEvents()
        otherDownload = next(
            worker
            for worker in _ControlledDownloadWorker.instances
            if worker.profile.metadata.profileId == other.metadata.profileId
        )
        otherDownload.finish('3.00 MiB/s')
        processQtEvents()

        self.assertEqual(other.metadata.latency, '9ms')
        self.assertEqual(other.metadata.speed, '3.00 MiB/s')
        self.assertFalse(
            any(
                worker.profile.metadata.profileId == replacement.metadata.profileId
                for worker in _ControlledDownloadWorker.instances
            )
        )

    def testWorkerReturnsResultsWithoutMutatingItsProfileSnapshot(self):
        """Keep worker execution independent from persistence write-back."""
        profile = self._profile('profile', 'profile.example')
        worker = _ControlledDownloadWorker(
            profile.deepcopy(),
            30000,
            DownloadSpeedTestOptions(5000, 'https://example.test'),
        )
        results = []
        worker.progressed.connect(lambda _worker, result: results.append(result))

        worker.publish('2.00 MiB/s')

        self.assertEqual(worker.profile.metadata.speed, '')
        self.assertEqual(results[-1].value, '2.00 MiB/s')
        worker.deleteLater()

    def testShutdownDoesNotCommitAnActiveDownloadProgressValue(self):
        """Treat service shutdown as cancellation rather than result write-back."""
        profile = self._profile('profile', 'profile.example')
        manager = self._manager((profile,))

        manager.testDownloadSpeed((profile,), concurrent=False)
        processQtEvents()
        worker = _ControlledDownloadWorker.instances[0]
        worker.publish('1.00 MiB/s')
        self.assertEqual(profile.metadata.speed, '1.00 MiB/s')

        profile.metadata.speed = ''
        manager.shutdown()
        processQtEvents()

        self.assertEqual(profile.metadata.speed, '')

    def testRuntimeCallbacksAreDisposedBeforeWorkerDeferredDeletion(self):
        """Make a late core-exit callback harmless after terminal disposal."""
        profile = self._profile('profile', 'profile.example')
        worker = _DownloadSpeedWorker(
            profile.deepcopy(),
            30000,
            DownloadSpeedTestOptions(5000, 'https://example.test'),
        )
        coreManager = _CoreManagerProbe()
        worker.coreManager = coreManager
        worker.finished.connect(lambda current, _result: current.deleteLater())

        worker.runCompletionCallback()

        self.assertEqual(coreManager.stopCount, 1)
        self.assertTrue(waitFor(lambda: not isValid(worker)))
        worker.coreExitCallback(profile.connection, 1)
        self.assertEqual(profile.metadata.speed, '')

    def testServerTableRepaintsOnlyTheCellCommittedByTheService(self):
        """Keep the one UI integration boundary limited to presentation."""
        with isolatedSettings():
            profile = self._profile('profile', 'profile.example')
            Storage.UserServers().append(profile)
            profile.index = 0
            AppSettings.set('ActivatedItemIndex', '-1')
            table = ServerTableView(
                configurationEditorFactory=QWidget,
                qrCodeWindowFactory=QWidget,
                importActionsFactory=tuple,
            )

            try:
                target = ProfileTestTarget.capture(profile)
                result = ProfileTestResult(
                    ProfileTestField.DownloadSpeed,
                    '4.00 MiB/s',
                )

                with mock.patch.object(table, 'flushItem') as repaint:
                    self.assertTrue(
                        table.profileTestManager.applyResult(target, result)
                    )

                self.assertEqual(profile.metadata.speed, '4.00 MiB/s')
                repaint.assert_called_once_with(
                    0,
                    table.Headers.index('Speed'),
                    profile,
                )
            finally:
                table.cleanup()
                table.deleteLater()
                Storage.UserServers().clear()
                Storage._UserServersStorage.cache_clear()
                Storage._UserSubsStorage.cache_clear()
                processQtEvents()


if __name__ == '__main__':
    unittest.main()
