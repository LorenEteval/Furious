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

"""Verify typed runtime lifecycle, ownership transfer, and Qt-thread handoff."""

from Furious.Core import MultiprocessingRuntime, ProcessLaunchSpec
from Furious.Interface import (
    CoreRuntime,
    RuntimeExitReason,
    RuntimeStartError,
    RuntimeState,
)
from Furious.Service.RuntimeLease import (
    RuntimeEventRouter,
    RuntimeLease,
    RuntimeLeaseState,
)
from Furious.Service.ConnectionManager import ConnectionManager, _ConnectionStartAttempt

from PySide6 import QtCore

from tests.support import application, collectAtBoundary, processQtEvents, waitFor

from unittest import TestCase, mock

import threading
import weakref


class _Runtime(CoreRuntime):
    """Provide an execution-free runtime for lease tests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stopCount = 0

    @staticmethod
    def name():
        return 'Lease fixture'

    @staticmethod
    def version():
        return '1'

    def start(self):
        self.setState(RuntimeState.Alive)

    def stop(self):
        self.stopCount += 1
        self.setState(RuntimeState.Exited)

    def publishCode(self, exitcode):
        """Interpret and publish one fixture process-exit code."""
        self.publishExit(self.interpretExit(exitcode))


class _ProcessRuntime(MultiprocessingRuntime):
    """Provide names around the reusable multiprocessing implementation."""

    def __init__(self, **kwargs):
        super().__init__(
            lambda _output: ProcessLaunchSpec(lambda: None),
            **kwargs,
        )

    @staticmethod
    def name():
        return 'Process fixture'

    @staticmethod
    def version():
        return '1'


class _AttemptOwner(QtCore.QObject):
    """Record runtime exits and the Qt thread that consumed them."""

    def __init__(self):
        super().__init__()
        self.events = []

    def runtimeExited(self, runtime, event):
        self.events.append((runtime, event, QtCore.QThread.currentThread()))


class RuntimeLifecycleTest(TestCase):
    """Exercise semantic exits independently from connection readiness."""

    @classmethod
    def setUpClass(cls):
        cls.app = application()

    def testFailedLeaseReleaseRemainsOwnedUntilSuccessfulRetry(self):
        """Rollback retains failed resources and blocks replacement admission."""
        manager = ConnectionManager()
        attempt = _ConnectionStartAttempt(manager, None)
        owner = _AttemptOwner()
        runtime = _Runtime()
        router = RuntimeEventRouter()
        router.attach(runtime, owner)
        lease = attempt.ownRuntime(runtime, router)
        with mock.patch.object(
            runtime, 'dispose', side_effect=RuntimeError('still owned')
        ):
            attempt.rollback()
            self.assertEqual(manager._pendingReleases, [lease])
            self.assertIs(lease.state, RuntimeLeaseState.Releasing)
            runtime.publishCode(0)
            processQtEvents()
            self.assertEqual(owner.events, [])
            for start in (manager.start, manager.startAsync):
                with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'):
                    start(None, '')
            with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'):
                manager.stopAll()
            self.assertEqual(manager._pendingReleases, [lease])
            resolver = mock.Mock()
            manager._dnsResolver = resolver
            with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'):
                manager.cleanup()
            resolver.dispose.assert_called_once_with()
            self.assertIsNone(manager._dnsResolver)
            self.assertEqual(manager._pendingReleases, [lease])
        manager.stopAll()
        self.assertEqual(manager._pendingReleases, [])
        self.assertIs(lease.state, RuntimeLeaseState.Released)
        manager.cleanup()
        owner.deleteLater()
        processQtEvents()

    def testFailedCommittedReleaseStillCleansIndependentRuntimes(self):
        """One refusal must not prevent reverse release of other committed leases."""
        manager = ConnectionManager()
        first, second = _Runtime(), _Runtime()
        leases = [
            RuntimeLease(runtime, RuntimeEventRouter()) for runtime in (first, second)
        ]
        manager._leases.extend(leases)
        with mock.patch.object(second, 'dispose', side_effect=RuntimeError('retry')):
            with self.assertRaisesRegex(RuntimeError, 'cleanup is incomplete'):
                manager.stopAll()
            self.assertIs(first.state, RuntimeState.Disposed)
            self.assertEqual(manager._pendingReleases, [leases[1]])
        manager.stopAll()
        manager.cleanup()
        processQtEvents()

    def testMultiprocessingFailedEscalationRetainsLiveChild(self):
        """Do not manufacture an exit or lose the handle of a surviving child."""
        runtime = _ProcessRuntime()
        child = mock.Mock()
        child.is_alive.return_value = True
        child.exitcode = None
        runtime._process = child
        runtime.setState(RuntimeState.Alive)
        with self.assertRaisesRegex(RuntimeError, 'did not stop'):
            runtime.dispose()
        self.assertTrue(child.is_alive())
        self.assertIs(runtime.process, child)
        self.assertIsNone(runtime.lastExit)
        child.close.assert_not_called()
        child.is_alive.return_value = False
        child.exitcode = 0
        runtime.dispose()
        self.assertIsNone(runtime.process)
        self.assertIs(runtime.state, RuntimeState.Disposed)

    def testMultiprocessingCloseFailureRetainsHandleForRetry(self):
        """Physical exit and handle release need independent evidence."""
        runtime = _ProcessRuntime()
        child = mock.Mock()
        child.is_alive.return_value = False
        child.exitcode = 0
        child.close.side_effect = OSError('handle still owned')
        runtime._process = child
        with self.assertRaisesRegex(RuntimeError, 'could not be closed'):
            runtime.dispose()
        self.assertIs(runtime.process, child)
        self.assertIsNot(runtime.state, RuntimeState.Disposed)
        child.close.side_effect = None
        runtime.dispose()
        self.assertIsNone(runtime.process)
        self.assertIs(runtime.state, RuntimeState.Disposed)

    def testWatcherThreadExitIsConsumedOnRouterQtThread(self):
        """Queue a worker-thread publication onto the Qt owner's thread."""
        owner = _AttemptOwner()
        router = RuntimeEventRouter()
        runtime = _Runtime(exitCallback=router.publish)
        router.attach(runtime, owner)
        lease = RuntimeLease(runtime, router)

        thread = threading.Thread(target=runtime.publishCode, args=(9,))

        thread.start()
        thread.join()

        self.assertTrue(waitFor(lambda: bool(owner.events)))
        self.assertIs(owner.events[0][2], self.app.thread())
        self.assertEqual(owner.events[0][1].code, 9)

        lease.release()

    def testRouterRejectsAnUntypedRuntimeExit(self):
        """Require interpretation at the concrete runtime boundary."""
        router = RuntimeEventRouter()
        runtime = _Runtime()

        with self.assertRaisesRegex(TypeError, 'requires a RuntimeExit'):
            router.publish(runtime, 23)

        router.deleteLater()

    def testRepeatedRoutersAvoidPackagedBoundMethodRetention(self):
        """Keep released queued routers out of Nuitka-like callback protection."""
        originalConnect = QtCore.SignalInstance.connect
        protectedCallbacks = []
        references = []

        def protectingConnect(signal, callback, *args, **kwargs):
            if getattr(callback, '__self__', None) is not None:
                protectedCallbacks.append(callback)

            return originalConnect(signal, callback, *args, **kwargs)

        with mock.patch.object(
            QtCore.SignalInstance,
            'connect',
            protectingConnect,
        ):
            for _index in range(32):
                router = RuntimeEventRouter()
                references.append(weakref.ref(router))

                router.finishRelease()
                router.deleteLater()

        del router
        collectAtBoundary()

        self.assertEqual(protectedCallbacks, [])
        self.assertTrue(all(reference() is None for reference in references))

    def testCommitNearQueuedExitUsesOneStableRoute(self):
        """Deliver an already queued exit exactly once to the committed owner."""
        owner = _AttemptOwner()
        committed = []
        router = RuntimeEventRouter()
        runtime = _Runtime(exitCallback=router.publish)
        router.attach(runtime, owner)
        lease = RuntimeLease(runtime, router)

        runtime.publishCode(11)
        lease.commit(lambda current, event: committed.append((current, event)))

        processQtEvents()

        self.assertEqual(owner.events, [])
        self.assertEqual(len(committed), 1)
        self.assertIs(committed[0][0], runtime)
        self.assertEqual(committed[0][1].code, 11)

        lease.release()

    def testPostCommitDuplicateExitIsDeliveredOnce(self):
        """Keep one terminal authority after ownership has transferred."""
        owner = _AttemptOwner()
        committed = []

        router = RuntimeEventRouter()
        runtime = _Runtime(exitCallback=router.publish)
        router.attach(runtime, owner)
        lease = RuntimeLease(runtime, router)

        lease.commit(lambda current, event: committed.append((current, event)))

        runtime.publishCode(12)
        runtime.publishCode(13)

        processQtEvents()

        self.assertEqual(owner.events, [])
        self.assertEqual(len(committed), 1)
        self.assertEqual(committed[0][1].code, 12)

        lease.release()

    def testReleaseSuppressesLateQueuedExitAndIsIdempotent(self):
        """Ignore late notifications and clean the exact runtime only once."""
        owner = _AttemptOwner()
        router = RuntimeEventRouter()
        runtime = _Runtime(exitCallback=router.publish)
        router.attach(runtime, owner)
        lease = RuntimeLease(runtime, router)

        runtime.publishCode(13)

        lease.release()
        lease.release()

        processQtEvents()

        self.assertEqual(owner.events, [])
        self.assertEqual(runtime.stopCount, 1)
        self.assertIs(runtime.state, RuntimeState.Disposed)

    def testMultiprocessingRuntimePublishesOneInterpretedExit(self):
        """Detect, reap, and publish one raw child transition internally."""
        process = mock.Mock()
        process.is_alive.side_effect = (True, True, False)
        process.exitcode = CoreRuntime.ExitCode.ConfigurationError.value
        events = []

        with mock.patch(
            'Furious.Core.MultiprocessingRuntime.multiprocessing.Process',
            return_value=process,
        ):
            runtime = _ProcessRuntime(
                exitCallback=lambda current, event: events.append((current, event))
            )

            runtime.start()

            self.assertIs(runtime.state, RuntimeState.Alive)
            self.assertTrue(runtime.isRunning())

            runtime._pollProcess()
            runtime._pollProcess()

        self.assertEqual(len(events), 1)
        self.assertIs(events[0][1].reason, RuntimeExitReason.InvalidConfiguration)
        self.assertEqual(events[0][1].code, 23)
        process.close.assert_called_once_with()

        runtime.dispose()

        self.assertIsNone(runtime._monitorConnection)
        self.assertIsNone(runtime._output._timerConnection)

        runtime.dispose()

    def testLaunchFactoryFailureDisposesAcquiredOutput(self):
        """Release the real queue, callback, and Qt timer before returning failure."""
        outputs = []
        destroyed = []

        def fail(output):
            outputs.append(output)
            output.timer.destroyed.connect(lambda: destroyed.append(True))
            raise ValueError('fixture preparation failure')

        runtime = _ProcessRuntime.__new__(_ProcessRuntime)

        try:
            with self.assertRaisesRegex(ValueError, 'fixture preparation failure'):
                MultiprocessingRuntime.__init__(
                    runtime, fail, msgCallback=lambda _: None
                )

            processQtEvents()

            self.assertEqual(destroyed, [True])
            self.assertTrue(outputs[0]._closed)
            self.assertIsNone(outputs[0].callback)
            self.assertIsNone(outputs[0]._timerConnection)
        finally:
            outputs[0].dispose()

            processQtEvents()

    def testMultiprocessingSpawnFailureRaisesStructuredError(self):
        """Represent expected acquisition failure without mutable side state."""
        process = mock.Mock()
        process.start.side_effect = OSError('fixture spawn failure')

        with mock.patch(
            'Furious.Core.MultiprocessingRuntime.multiprocessing.Process',
            return_value=process,
        ):
            runtime = _ProcessRuntime()

            with self.assertRaises(RuntimeStartError) as raised:
                runtime.start()

        self.assertIs(raised.exception.reason, RuntimeExitReason.StartFailure)
        self.assertIn('fixture spawn failure', raised.exception.details)

        runtime.dispose()

        self.assertIsNone(runtime._monitorConnection)
        self.assertIsNone(runtime._output._timerConnection)


if __name__ == '__main__':
    import unittest

    unittest.main()
