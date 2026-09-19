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

"""Verify the managed External Core process without third-party executables."""

from __future__ import annotations

from Furious.Backends.ExternalCore import ConfigExternalCore, ExternalCoreProcess
from Furious.Backends.ExternalCore.Plugin import (
    ExternalCorePlugin,
    ExternalCoreRuntimeFactory,
)
from Furious.Interface import CoreRuntime, RuntimeExit, RuntimeStartError, RuntimeState
from Furious.Plugins.API import (
    CoreRuntimeRequest,
    SubscriptionItem,
    SubscriptionResult,
)
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.ConnectionManager import ConnectionManager
from Furious.Service.DnsResolver import DnsResolver
from Furious.Service.RuntimeLease import RuntimeEventRouter, RuntimeLease
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)

from PySide6 import QtCore

from tests.support import application, waitFor as waitForQt

import os
import sys
import json
import time
import tempfile
import shutil
import threading
import subprocess
import unittest

from unittest import mock

from pathlib import Path


class _RuntimeOwner(QtCore.QObject):
    """Record routed External Core exits and their consuming Qt thread."""

    def __init__(self):
        super().__init__()
        self.events = []

    def runtimeExited(self, runtime, event):
        self.events.append((runtime, event, QtCore.QThread.currentThread()))


class ExternalCoreProcessTest(unittest.TestCase):
    """Exercise structured launch, output, failure, and repeated shutdown."""

    @staticmethod
    def waitFor(predicate, timeout: float = 5.0) -> bool:
        """Wait for a deterministic fixture condition without a Qt event loop."""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if predicate():
                return True

            time.sleep(0.02)

        return predicate()

    @staticmethod
    def configuration(arguments, cwd: str, environment=None):
        """Build one valid Python-backed External Core fixture profile."""
        return ConfigExternalCore(
            {
                'type': 'external-core',
                'executable': str(Path(sys.executable).resolve()),
                'workingDirectory': cwd,
                'arguments': list(arguments),
                'environment': dict(environment or {}),
                'httpProxy': '127.0.0.1:10809',
                'socksProxy': '127.0.0.1:10808',
                'shutdownTimeout': 1,
            }
        )

    def testShutdownTimeoutRejectsNonFiniteAndOverflowingValues(self):
        """Reject invalid wait values before any executable can be acquired."""
        for value in (float('nan'), float('inf'), -float('inf'), 10**400):
            with self.subTest(value=str(value)[:20]):
                config = self.configuration(['-c', 'pass'], str(Path.cwd()))
                config['shutdownTimeout'] = value

                self.assertTrue(config.validateProcess())

                runtime = ExternalCoreProcess(config)

                with mock.patch(
                    'Furious.Backends.ExternalCore.Process.subprocess.Popen'
                ) as spawn:
                    with self.assertRaises(RuntimeStartError):
                        runtime.start()

                    spawn.assert_not_called()

                runtime.dispose()

    def testFailedReapRetainsChildUntilRetrySucceeds(self):
        """Keep independently observed live execution after every escalation fails."""
        runtime = ExternalCoreProcess(
            self.configuration(['-c', 'pass'], str(Path.cwd()))
        )

        child = mock.Mock(pid=1234)
        child.poll.return_value = None

        runtime._process = child
        runtime.setState(RuntimeState.Alive)

        with mock.patch.object(runtime, '_requestStop'), mock.patch.object(
            runtime, '_terminate'
        ), mock.patch.object(runtime, '_kill'), mock.patch.object(
            runtime, '_waitForExit', return_value=False
        ):
            with self.assertRaisesRegex(RuntimeError, 'could not be reaped'):
                runtime.dispose()

        self.assertIsNone(child.poll())
        self.assertIs(runtime.process, child)
        self.assertIs(runtime.state, RuntimeState.Stopping)

        child.poll.return_value = 0

        runtime.dispose()

        self.assertIsNone(runtime.process)
        self.assertIs(runtime.state, RuntimeState.Disposed)

    def testFailedThreadJoinRetainsReaderAndWatcherUntilRetry(self):
        """A reaped child does not prove its pipe readers or watcher have exited."""
        runtime = ExternalCoreProcess(
            self.configuration(['-c', 'pass'], str(Path.cwd()))
        )

        child = mock.Mock()
        child.poll.return_value = 0
        reader, watcher = mock.Mock(), mock.Mock()
        reader.is_alive.return_value = watcher.is_alive.return_value = True

        runtime._process = child
        runtime._readerThreads = [reader]
        runtime._watcherThread = watcher

        with self.assertRaisesRegex(RuntimeError, 'reader or watcher'):
            runtime.dispose()

        self.assertIs(runtime.process, child)
        self.assertEqual(runtime._readerThreads, [reader])
        self.assertIs(runtime._watcherThread, watcher)

        reader.is_alive.return_value = watcher.is_alive.return_value = False

        runtime.dispose()

        self.assertEqual(runtime._readerThreads, [])
        self.assertIsNone(runtime._watcherThread)
        self.assertIsNone(runtime.process)

    def testDisposedRuntimeCannotAcquireAnotherProcess(self):
        """Disposal is terminal even when the stored launch specification is valid."""
        runtime = ExternalCoreProcess(
            self.configuration(['-c', 'pass'], str(Path.cwd()))
        )
        runtime.dispose()

        try:
            with mock.patch(
                'Furious.Backends.ExternalCore.Process.subprocess.Popen'
            ) as spawn:
                with self.assertRaises(RuntimeStartError):
                    runtime.start()

                spawn.assert_not_called()
        finally:
            runtime.dispose()

    def testPartialThreadStartupReapsChildAndClosesEveryPipe(self):
        """A failed reader or watcher releases all earlier acquisitions."""
        originalStart = threading.Thread.start
        originalPopen = subprocess.Popen

        for failAt in (1, 2, 3):
            with self.subTest(failAt=failAt):
                threads = []
                children = []
                runtime = ExternalCoreProcess(
                    self.configuration(
                        ['-u', '-c', 'import time; time.sleep(60)'], str(Path.cwd())
                    )
                )

                def startThread(thread):
                    threads.append(thread)

                    if len(threads) == failAt:
                        raise RuntimeError('thread startup fixture failure')

                    originalStart(thread)

                def spawn(*args, **kwargs):
                    child = originalPopen(*args, **kwargs)
                    children.append(child)
                    return child

                try:
                    with mock.patch('threading.Thread.start', startThread), mock.patch(
                        'Furious.Backends.ExternalCore.Process.subprocess.Popen',
                        side_effect=spawn,
                    ):
                        with self.assertRaises(RuntimeStartError):
                            runtime.start()

                    child = children[0]

                    self.assertIsNotNone(child.poll())
                    self.assertTrue(child.stdout.closed)
                    self.assertTrue(child.stderr.closed)
                    self.assertTrue(all(not thread.is_alive() for thread in threads))

                    self.assertIsNone(runtime.process)
                    self.assertIsNone(runtime._watcherThread)
                    self.assertFalse(runtime._readerThreads)
                    self.assertIs(runtime.state, RuntimeState.Failed)
                finally:
                    for child in children:
                        if child.poll() is None:
                            child.kill()

                        child.wait(timeout=5)

                    for thread in threads:
                        if thread.ident is not None:
                            thread.join(5)

                    for child in children:
                        for stream in (child.stdout, child.stderr):
                            if stream is not None:
                                stream.close()

                    runtime._watcherThread = None

                    runtime.dispose()

    def testWindowsTaskkillHasBoundedWait(self):
        """Never allow the fully mocked host shutdown command to wait forever."""
        process = mock.Mock(pid=1234)

        with mock.patch('Furious.Backends.ExternalCore.Process.subprocess.run') as run:
            ExternalCoreProcess._windowsTaskkill(process, force=True)

        run.assert_called_once_with(
            ['taskkill', '/PID', '1234', '/T', '/F'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            shell=False,
            timeout=ExternalCoreProcess.ForcedShutdownTimeout,
        )

    def testStructuredArgumentsCwdEnvironmentAndOutput(self):
        """Pass spaces literally and capture both output streams safely."""
        with tempfile.TemporaryDirectory(
            prefix='furious external core ', dir=Path.cwd()
        ) as directory:
            resultPath = Path(directory) / 'result with spaces.json'
            payload = 'argument with spaces'
            code = (
                'import json,os,pathlib,sys,time; '
                'pathlib.Path(sys.argv[1]).write_text('
                'json.dumps({"cwd":os.getcwd(),"arg":sys.argv[2],'
                '"env":os.environ.get("FURIOUS_EXTERNAL_TEST")}),'
                'encoding="utf-8"); '
                'print("stdout fixture",flush=True); '
                'print("stderr fixture",file=sys.stderr,flush=True); '
                'time.sleep(60)'
            )

            config = self.configuration(
                ['-u', '-c', code, str(resultPath), payload],
                directory,
                {'FURIOUS_EXTERNAL_TEST': 'Unicode ✓'},
            )

            messages = []
            runtime = ExternalCoreProcess(config, msgCallback=messages.append)

            runtime.start()

            self.assertTrue(self.waitFor(resultPath.exists))
            self.assertTrue(
                self.waitFor(
                    lambda: any('stdout fixture' in message for message in messages)
                    and any(
                        '[stderr] stderr fixture' in message for message in messages
                    )
                )
            )

            result = json.loads(resultPath.read_text(encoding='utf-8'))

            self.assertEqual(Path(result['cwd']), Path(directory))
            self.assertEqual(result['arg'], payload)
            self.assertEqual(result['env'], 'Unicode ✓')

            runtime.stop()

            self.assertFalse(runtime.isRunning())
            self.assertFalse(runtime._readerThreads)

    def testReaderBatchesCompleteLinesAndPreservesTrailingPartialLine(self):
        """Use one callback per read chunk without buffering complete lines."""

        class BatchCallback:
            """Record batch and compatibility callback traffic separately."""

            def __init__(self):
                self.single = []
                self.batches = []

            def __call__(self, message):
                self.single.append(message)

            def appendMany(self, messages):
                self.batches.append(tuple(messages))

        callback = BatchCallback()
        runtime = ExternalCoreProcess(ConfigExternalCore(), msgCallback=callback)
        stream = mock.Mock()
        stream.fileno.return_value = 123

        with mock.patch(
            'Furious.Backends.ExternalCore.Process.os.read',
            side_effect=(b'first\nsecond\r\npar', b'tial', b''),
        ):
            runtime._readStream(stream, 'stderr')

        self.assertEqual(
            callback.batches,
            [('[stderr] first', '[stderr] second')],
        )
        self.assertEqual(callback.single, ['[stderr] partial'])
        stream.close.assert_called_once_with()

    def testMissingExecutableAndImmediateExitFailStartup(self):
        """Report authoritative path and early non-zero-exit failures."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            missing = self.configuration([], directory)
            missing['executable'] = str(Path(directory) / 'missing executable')

            runtime = ExternalCoreProcess(missing)

            with self.assertRaises(RuntimeStartError) as raised:
                runtime.start()

            self.assertEqual(raised.exception.message, 'Executable does not exist')
            runtime.dispose()

            invalidCwd = self.configuration([], directory)
            invalidCwd['workingDirectory'] = str(Path(directory) / 'missing cwd')

            runtime = ExternalCoreProcess(invalidCwd)

            with self.assertRaises(RuntimeStartError) as raised:
                runtime.start()

            self.assertEqual(
                raised.exception.message,
                'Working directory does not exist',
            )
            runtime.dispose()

            invalidEnvironment = self.configuration([], directory)
            invalidEnvironment['environment'] = ['TOKEN=value']

            runtime = ExternalCoreProcess(invalidEnvironment)

            with self.assertRaises(RuntimeStartError) as raised:
                runtime.start()

            self.assertEqual(
                raised.exception.message,
                'Environment overrides must be a mapping',
            )
            runtime.dispose()

            earlyExit = self.configuration(
                ['-c', 'import sys; sys.exit(7)'],
                directory,
            )

            exits = []
            runtime = ExternalCoreProcess(
                earlyExit,
                exitCallback=lambda _runtime, event: exits.append(event),
            )
            runtime.start()
            self.assertTrue(self.waitFor(lambda: bool(exits)))
            self.assertEqual(exits[0].code, 7)

            runtime.dispose()

    def testApplicationTun2socksUsesOnlyTheConfiguredRemoteAddress(self):
        """Keep process paths separate from opt-in TUN routing metadata."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)
            executable = config['executable']

            registry = PluginRegistry()
            registry.register(ExternalCorePlugin())

            self.assertFalse(config.usesApplicationTun2socks())
            self.assertFalse(registry.usesApplicationTun2socks(config))
            self.assertEqual(config.itemAddress, '')
            self.assertNotEqual(config.itemAddress, executable)

            config['useApplicationTun2socks'] = True
            missingAddressError = (
                'TUN remote address is required when application '
                'tun2socks is enabled'
            )

            self.assertIn(missingAddressError, config.validateProcess())

            for address in (
                'actual-server.example.com',
                '203.0.113.42',
                '2001:db8::42',
            ):
                config['tunRemoteAddress'] = address

                self.assertTrue(config.usesApplicationTun2socks())
                self.assertTrue(registry.usesApplicationTun2socks(config))
                self.assertEqual(config.itemAddress, address)
                self.assertNotIn(missingAddressError, config.validateProcess())

            registry.shutdown()

    def testFactoryPublishesTheConfiguredProxyReadinessBoundary(self):
        """Keep endpoint readiness in startup orchestration, not process start."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)
            factory = ExternalCoreRuntimeFactory()
            request = CoreRuntimeRequest(config, '')
            prepared = factory.create(request)

            try:
                self.assertEqual(prepared.readiness.endpoint, config.httpProxy())
            finally:
                prepared.runtime.dispose()

    def testDisabledApplicationTun2socksSkipsTheHostTunRuntime(self):
        """Do not enter ConnectionManager's TUN path for an opted-out profile."""

        class NoCoreRuntimeConnectionManager(ConnectionManager):
            """Pretend the external process started without launching a child."""

            def _startCoreRuntime(self, *args, **kwargs):
                """Return one successful process-free fixture launch."""
                return None, True

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)

            registry = mock.Mock()
            registry.prepareTUN.return_value = False
            registry.usesApplicationTun2socks.return_value = False

            manager = NoCoreRuntimeConnectionManager()

            with (
                mock.patch(
                    'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                    return_value=True,
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.getPluginRegistry',
                    return_value=registry,
                ),
                mock.patch('Furious.Service.ConnectionManager.Tun2socks') as tun2socks,
            ):
                self.assertTrue(manager.start(config, '', deepcopy=False))

            registry.usesApplicationTun2socks.assert_called_once_with(config)
            tun2socks.assert_not_called()
            manager.cleanup()

    def testEnabledApplicationTun2socksResolvesOnlyTheRemoteAddress(self):
        """Send the configured network destination, never the executable, to DNS."""

        class NoCoreRuntimeConnectionManager(ConnectionManager):
            """Pretend the external process started without launching a child."""

            def _startCoreRuntime(self, *args, **kwargs):
                """Return one successful process-free fixture launch."""
                return None, True

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)
            config['useApplicationTun2socks'] = True
            config['tunRemoteAddress'] = 'actual-server.example.com'

            executable = config['executable']

            registry = mock.Mock()
            registry.prepareTUN.return_value = False
            registry.usesApplicationTun2socks.return_value = True

            dnsResolver = mock.Mock()
            dnsResolver.resolve.return_value = (True, [])

            tunRuntime = mock.Mock(spec=CoreRuntime)
            tunRuntime.isRunning.return_value = False

            manager = NoCoreRuntimeConnectionManager(dnsResolver=dnsResolver)

            with (
                mock.patch(
                    'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                    return_value=True,
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.getPluginRegistry',
                    return_value=registry,
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userDefaultPrimaryGatewayIP',
                    return_value='192.168.50.1',
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userPrimaryAdapterInterfaceIP',
                    return_value='192.168.50.20',
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userTcpSendBufferSize',
                    return_value=1,
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userTcpReceiveBufferSize',
                    return_value=1,
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userTcpAutoTuning',
                    return_value='False',
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.userBypassTUNAdapterInterfaceIP',
                    return_value='',
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.SystemRoutingTable.delete'
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.Tun2socks',
                    return_value=tunRuntime,
                ),
            ):
                self.assertFalse(manager.start(config, '', deepcopy=False))

            dnsResolver.resolve.assert_called_once_with('actual-server.example.com')

            self.assertNotEqual(dnsResolver.resolve.call_args.args[0], executable)

            manager.cleanup()

    def testMissingTunRemoteAddressFailsBeforeProcessLaunch(self):
        """Reject opted-in TUN integration before spawning the executable."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)
            config['useApplicationTun2socks'] = True

            runtime = ExternalCoreProcess(config)

            with self.assertRaises(RuntimeStartError) as raised:
                runtime.start()

            self.assertIsNone(runtime.process)
            self.assertEqual(
                raised.exception.message,
                'TUN remote address is required when application '
                'tun2socks is enabled',
            )

            runtime.dispose()

    def testUnexpectedExitCallsBackAndRepeatedShutdownDoesNotRetainThreads(self):
        """Notice post-start failure and leave no workers across restarts."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            callbackEvent = threading.Event()
            callbackValues = []

            def exited(runtime, event):
                """Record one unexpected process exit from the watcher thread."""
                callbackValues.append((runtime, event))
                callbackEvent.set()

            config = self.configuration(
                ['-c', 'import time,sys; time.sleep(.5); sys.exit(9)'],
                directory,
            )
            runtime = ExternalCoreProcess(config, exitCallback=exited)

            runtime.start()
            self.assertTrue(callbackEvent.wait(5))
            self.assertIs(callbackValues[0][0], runtime)
            self.assertIsInstance(callbackValues[0][1], RuntimeExit)
            self.assertEqual(callbackValues[0][1].code, 9)

            runtime.stop()

            longRunning = self.configuration(
                ['-c', 'import time; time.sleep(60)'],
                directory,
            )

            for _index in range(3):
                current = ExternalCoreProcess(longRunning)
                current.start()
                current.stop()

                self.assertFalse(current.isRunning())
                self.assertFalse(current._readerThreads)
                self.assertIsNone(current._watcherThread)
                current.dispose()

            runtime.dispose()

            self.assertIsNone(runtime.process)
            self.assertIsNone(runtime._watcherThread)

    def testWatcherExitIsRoutedToTheQtOwnerThread(self):
        """Never let the subprocess watcher manipulate a Qt owner directly."""
        app = application()

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration(
                ['-c', 'import sys,time; time.sleep(.1); sys.exit(17)'],
                directory,
            )
            owner = _RuntimeOwner()
            router = RuntimeEventRouter()
            runtime = ExternalCoreProcess(config, exitCallback=router.publish)
            router.attach(runtime, owner)
            lease = RuntimeLease(runtime, router)

            runtime.start()

            self.assertTrue(waitForQt(lambda: bool(owner.events), timeout=5))
            self.assertIs(owner.events[0][0], runtime)
            self.assertEqual(owner.events[0][1].code, 17)
            self.assertIs(owner.events[0][2], app.thread())

            lease.release()

    @unittest.skipUnless(os.name == 'nt', 'Windows executable path coverage')
    def testExecutablePathContainingSpaces(self):
        """Launch a copied interpreter whose local path contains spaces."""
        with tempfile.TemporaryDirectory(
            prefix='furious executable path ', dir=Path.cwd()
        ) as directory:
            executable = Path(directory) / 'python executable.exe'

            # The interpreter and checkout can be on different Windows volumes.
            # Copy the base interpreter (not a venv redirector) and its DLLs;
            # PYTHONHOME supplies its existing standard library without installing
            # an environment or writing into the interpreter's directory.
            shutil.copy2(sys._base_executable, executable)

            for library in Path(sys.base_prefix).glob('python*.dll'):
                shutil.copy2(library, directory)

            config = self.configuration(
                ['-c', 'import time; print("ready", flush=True); time.sleep(60)'],
                directory,
                environment={'PYTHONHOME': sys.base_prefix},
            )
            config['executable'] = str(executable)

            messages = []
            runtime = ExternalCoreProcess(config, msgCallback=messages.append)

            try:
                runtime.start()

                self.assertTrue(
                    self.waitFor(
                        lambda: any('ready' in message for message in messages)
                    ),
                    messages,
                )
                self.assertTrue(runtime.isRunning())
            finally:
                runtime.stop()

            self.assertFalse(runtime.isRunning())

    def testSubscriptionCannotIntroduceAnExecutableProfile(self):
        """Reject executable configurations received from subscription data."""

        class ExternalConfigurationRegistry(PluginRegistry):
            """Return one deterministic untrusted subscription item."""

            def decodeSubscription(self, data: bytes, decoderId=None):
                """Return an External Core mapping regardless of payload."""
                return SubscriptionResult(
                    'fixture',
                    (
                        SubscriptionItem(
                            configuration={
                                'type': 'external-core',
                                'executable': str(Path(sys.executable).resolve()),
                                'arguments': [],
                                'environment': {},
                                'httpProxy': '127.0.0.1:10809',
                            }
                        ),
                    ),
                )

        registry = ExternalConfigurationRegistry()
        registry.register(ExternalCorePlugin())

        result = SubscriptionImportService(registry).importPayload(
            b'untrusted',
            SubscriptionSource('fixture'),
        )

        self.assertEqual(result.profiles, tuple())
        self.assertEqual(result.rejectedItems, 1)

        registry.shutdown()


class DnsResolverRobustnessTest(unittest.TestCase):
    """Verify expected negative DNS responses do not raise raw exceptions."""

    def testResponseWithoutAnswerReportsResolutionFailure(self):
        """Treat a valid DNS JSON response without Answer as a normal failure."""

        class ReplyData:
            """Provide the QByteArray-compatible method used by the resolver."""

            @staticmethod
            def data():
                """Return a deterministic NXDOMAIN-style DNS response."""
                return b'{"Status":3,"Comment":"NXDOMAIN"}'

        class Reply:
            """Return the fixture response body through the network-reply API."""

            @staticmethod
            def readAll():
                """Return the response data wrapper."""
                return ReplyData()

        result = {
            'error': False,
            'depth': 1,
            'reference': [],
            'result': {},
        }

        DnsResolver.successCallback(
            mock.Mock(),
            Reply(),
            domain='missing.example',
            resultMap=result,
        )

        self.assertTrue(result['error'])
        self.assertEqual(result['depth'], 0)
        self.assertEqual(result['result'], {})

    def testCyclicReferenceIsRejectedWithoutAnotherRequest(self):
        """Stop a CNAME cycle before it can recurse indefinitely."""

        class ReplyData:
            """Provide one deterministic CNAME response body."""

            @staticmethod
            def data():
                """Return an alias pointing back to the traversal origin."""
                return b'{"Status":0,"Answer":[{"type":5,"data":"a.example."}]}'

        class Reply:
            """Return the fixture response body."""

            @staticmethod
            def readAll():
                """Return the response data wrapper."""
                return ReplyData()

        result = {
            'error': False,
            'depth': 1,
            'reference': [],
            'result': {},
            'visited': {'a.example', 'b.example'},
        }

        resolver = mock.Mock()

        with mock.patch.object(resolver, 'webGET') as webGet:
            DnsResolver.successCallback(
                resolver,
                Reply(),
                domain='b.example',
                resultMap=result,
                referenceDepth=1,
                ancestry=('a.example', 'b.example'),
            )

        webGet.assert_not_called()

        self.assertTrue(result['error'])
        self.assertEqual(result['depth'], 0)

    def testReferenceDepthIsBounded(self):
        """Reject another CNAME after the documented traversal limit."""

        class ReplyData:
            """Provide one deterministic CNAME response body."""

            @staticmethod
            def data():
                """Return one previously unseen alias."""
                return b'{"Status":0,"Answer":[{"type":5,"data":"next.example"}]}'

        class Reply:
            """Return the fixture response body."""

            @staticmethod
            def readAll():
                """Return the response data wrapper."""
                return ReplyData()

        result = {
            'error': False,
            'depth': 1,
            'reference': [],
            'result': {},
            'visited': {'current.example'},
        }

        resolver = mock.Mock(MAX_REFERENCE_DEPTH=DnsResolver.MAX_REFERENCE_DEPTH)

        with mock.patch.object(resolver, 'webGET') as webGet:
            DnsResolver.successCallback(
                resolver,
                Reply(),
                domain='current.example',
                resultMap=result,
                referenceDepth=DnsResolver.MAX_REFERENCE_DEPTH,
                ancestry=('current.example',),
            )

        webGet.assert_not_called()

        self.assertTrue(result['error'])
        self.assertEqual(result['depth'], 0)


if __name__ == '__main__':
    unittest.main()
