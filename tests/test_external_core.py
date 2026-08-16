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
from Furious.Backends.ExternalCore.Plugin import ExternalCorePlugin
from Furious.Plugins.API import SubscriptionItem, SubscriptionResult
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.ConnectionManager import ConnectionManager
from Furious.Service.DnsResolver import DnsResolver
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)

import os
import sys
import json
import time
import tempfile
import threading
import unittest

from unittest import mock

from pathlib import Path


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
            messages = []
            runtime = ExternalCoreProcess(msgCallback=messages.append)
            config = self.configuration(
                ['-u', '-c', code, str(resultPath), payload],
                directory,
                {'FURIOUS_EXTERNAL_TEST': 'Unicode ✓'},
            )

            self.assertTrue(runtime.start(config))
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

            self.assertFalse(runtime.isAlive())
            self.assertFalse(runtime._readerThreads)

    def testMissingExecutableAndImmediateExitFailStartup(self):
        """Report authoritative path and early non-zero-exit failures."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            missing = self.configuration([], directory)
            missing['executable'] = str(Path(directory) / 'missing executable')

            runtime = ExternalCoreProcess()

            self.assertFalse(runtime.start(missing))
            self.assertEqual(runtime.startError(), 'Executable does not exist')

            invalidCwd = self.configuration([], directory)
            invalidCwd['workingDirectory'] = str(Path(directory) / 'missing cwd')

            self.assertFalse(runtime.start(invalidCwd))
            self.assertEqual(
                runtime.startError(),
                'Working directory does not exist',
            )

            invalidEnvironment = self.configuration([], directory)
            invalidEnvironment['environment'] = ['TOKEN=value']

            self.assertFalse(runtime.start(invalidEnvironment))
            self.assertEqual(
                runtime.startError(),
                'Environment overrides must be a mapping',
            )

            earlyExit = self.configuration(
                ['-c', 'import sys; sys.exit(7)'],
                directory,
            )

            self.assertFalse(runtime.start(earlyExit))
            self.assertEqual(runtime.lastExitCode, 7)
            self.assertEqual(
                runtime.startError(),
                'External core exited during startup',
            )

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

    def testDisabledApplicationTun2socksSkipsTheHostTunRuntime(self):
        """Do not enter ConnectionManager's TUN path for an opted-out profile."""

        class NoKernelConnectionManager(ConnectionManager):
            """Pretend the external process started without launching a child."""

            def _startKernel(self, *args, **kwargs):
                """Return one successful process-free fixture launch."""
                return None, True

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)

            registry = mock.Mock()
            registry.prepareTUN.return_value = False
            registry.usesApplicationTun2socks.return_value = False

            manager = NoKernelConnectionManager()

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

        class NoKernelConnectionManager(ConnectionManager):
            """Pretend the external process started without launching a child."""

            def _startKernel(self, *args, **kwargs):
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

            manager = NoKernelConnectionManager()

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
                mock.patch('Furious.Service.ConnectionManager.Tun2socks'),
                mock.patch(
                    'Furious.Service.ConnectionManager.DnsResolver.configureHttpProxy'
                ),
                mock.patch(
                    'Furious.Service.ConnectionManager.DnsResolver.resolve',
                    return_value=(True, []),
                ) as resolve,
            ):
                self.assertFalse(manager.start(config, '', deepcopy=False))

            resolve.assert_called_once_with('actual-server.example.com')

            self.assertNotEqual(resolve.call_args.args[0], executable)

            manager.cleanup()

    def testMissingTunRemoteAddressFailsBeforeProcessLaunch(self):
        """Reject opted-in TUN integration before spawning the executable."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            config = self.configuration([], directory)
            config['useApplicationTun2socks'] = True

            runtime = ExternalCoreProcess()

            self.assertFalse(runtime.start(config))
            self.assertIsNone(runtime.process)
            self.assertEqual(
                runtime.startError(),
                'TUN remote address is required when application '
                'tun2socks is enabled',
            )

            runtime.dispose()

    def testUnexpectedExitCallsBackAndRepeatedShutdownDoesNotRetainThreads(self):
        """Notice post-start failure and leave no workers across restarts."""
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            callbackEvent = threading.Event()
            callbackValues = []

            def exited(runtime, exitCode):
                """Record one unexpected process exit from the watcher thread."""
                callbackValues.append((runtime, exitCode))
                callbackEvent.set()

            runtime = ExternalCoreProcess(exitCallback=exited)
            config = self.configuration(
                ['-c', 'import time,sys; time.sleep(.5); sys.exit(9)'],
                directory,
            )

            self.assertTrue(runtime.start(config))
            self.assertTrue(callbackEvent.wait(5))
            self.assertEqual(callbackValues, [(runtime, 9)])

            runtime.stop()

            longRunning = self.configuration(
                ['-c', 'import time; time.sleep(60)'],
                directory,
            )

            for _index in range(3):
                self.assertTrue(runtime.start(longRunning))

                runtime.stop()

                self.assertFalse(runtime.isAlive())
                self.assertFalse(runtime._readerThreads)
                self.assertIsNone(runtime._watcherThread)

            runtime.dispose()

    @unittest.skipUnless(os.name == 'nt', 'Windows executable hard-link coverage')
    def testExecutablePathContainingSpaces(self):
        """Launch an executable hard link whose local path contains spaces."""
        with tempfile.TemporaryDirectory(
            prefix='furious executable path ', dir=Path.cwd()
        ) as directory:
            executable = Path(directory) / 'python executable.exe'

            os.link(sys.executable, executable)

            config = self.configuration(
                ['-c', 'import time; time.sleep(60)'],
                directory,
            )
            config['executable'] = str(executable)

            runtime = ExternalCoreProcess()

            self.assertTrue(runtime.start(config))

            runtime.stop()

            self.assertFalse(runtime.isAlive())

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
            Reply(),
            domain='missing.example',
            resultMap=result,
        )

        self.assertTrue(result['error'])
        self.assertEqual(result['depth'], 0)
        self.assertEqual(result['result'], {})


if __name__ == '__main__':
    unittest.main()
