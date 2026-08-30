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

"""Exercise event-driven connection startup with real Qt event delivery."""

from __future__ import annotations

from Furious.Interface import CoreRuntime
from Furious.Plugins import CoreRuntimeLaunch, CoreRuntimeStartup
from Furious.Qt.Signals import singleShotWeakly
from Furious.Service.ConnectionManager import (
    ConnectionManager,
    ConnectionStartStage,
)
from Furious.Service.DnsResolver import DnsResolutionOperation

from PySide6 import QtCore, QtNetwork

from tests.support import application, processQtEvents, waitFor

import importlib
import unittest

from unittest import TestCase, mock


class _Configuration:
    """Provide the endpoint values used by manager-only tests."""

    def httpProxy(self):
        """Return a deterministic local proxy endpoint."""
        return '127.0.0.1:18080'

    def socksProxy(self):
        """Return a deterministic local SOCKS endpoint."""
        return '127.0.0.1:18081'

    def remoteAddress(self):
        """Avoid DNS during mocked TUN tests."""
        return '192.0.2.1'


class _Runtime(CoreRuntime):
    """Provide an observable in-process stand-in for a core runtime."""

    def __init__(self, exitCallback=None):
        """Initialize an idle runtime and lifecycle counters."""
        super().__init__(exitCallback)

        self.alive = False
        self.startOptions = []
        self.stopCount = 0
        self.disposeCount = 0
        self.confirmCount = 0

    @staticmethod
    def name():
        """Return the fixture runtime name."""
        return 'Async Fixture'

    @staticmethod
    def version():
        """Return a fixture version."""
        return '1.0'

    def start(self, _configuration=None, *_args, **kwargs):
        """Become live and retain launch options."""
        self.startOptions.append(dict(kwargs))
        self.alive = True

        return True

    def stop(self):
        """Stop this exact runtime."""
        self.stopCount += 1
        self.alive = False

    def dispose(self):
        """Record final resource disposal."""
        self.disposeCount += 1
        self._exitCallback = None

    def isAlive(self):
        """Return the controlled process-survival state."""
        return self.alive

    def confirmStartup(self):
        """Record readiness confirmation."""
        if not self.alive:
            return False

        self.confirmCount += 1

        return True

    def fail(self, exitcode=61):
        """Simulate an early child-process exit."""
        self.alive = False
        self.callExitCallback(exitcode)


class _Registry:
    """Return prepared launches in deterministic order."""

    def __init__(self, launches):
        """Retain a launch queue."""
        self.launches = list(launches)

    def createCoreRuntime(self, *_args, **_kwargs):
        """Return the next prepared runtime launch."""
        return self.launches.pop(0)


class _ResolverFixture(QtCore.QObject):
    """Complete one recursive-resolution state through a real Qt timer."""

    def __init__(self):
        """Initialize without a pending result."""
        super().__init__()

        self.resultMap = None

    @staticmethod
    def _newResultMap(domain):
        """Return the minimum state required by the observer."""
        return {
            'domain': domain,
            'depth': 0,
            'error': False,
            'reference': [],
            'result': {},
        }

    def _beginResolve(self, resultMap):
        """Schedule asynchronous completion."""
        self.resultMap = resultMap
        resultMap['depth'] = 1
        singleShotWeakly(0, self, '_complete')

    def _complete(self):
        """Publish one deterministic address through shared state."""
        self.resultMap['result']['192.0.2.10'] = True
        self.resultMap['depth'] = 0


class ConnectionStartupAsyncTest(TestCase):
    """Verify readiness, cancellation, rollback, and compatibility."""

    def setUp(self):
        """Ensure a Qt application exists for real timer/socket delivery."""
        self.app = application()
        self.servers = []
        self.managers = []

    def tearDown(self):
        """Release every exact manager and local listener."""
        for manager in self.managers:
            manager.cleanup()

        for server in self.servers:
            server.close()
            server.deleteLater()

        processQtEvents()

    def _manager(self):
        """Return a manager with host TUN disabled at the test boundary."""
        manager = ConnectionManager()
        manager._prepareTUNPolicy = mock.Mock(return_value=(False, False))
        self.managers.append(manager)

        return manager

    def _server(self):
        """Listen on one real loopback endpoint."""
        server = QtNetwork.QTcpServer(self.app)
        self.assertTrue(
            server.listen(
                QtNetwork.QHostAddress.SpecialAddress.LocalHost,
                0,
            )
        )
        self.servers.append(server)

        return server

    def _operation(self, manager, launch):
        """Start one operation through an injected registry."""
        registry = _Registry([launch])
        patcher = mock.patch(
            'Furious.Service.ConnectionManager.getPluginRegistry',
            return_value=registry,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        return manager.startAsync(
            _Configuration(),
            'Global',
            deepcopy=False,
        )

    def testLocalEndpointReadinessCompletesEarlyAndKeepsQtResponsive(self):
        """Commit as soon as a real listener accepts while timers still run."""
        server = self._server()
        endpoint = f'127.0.0.1:{server.serverPort()}'
        runtime = _Runtime()
        launch = CoreRuntimeLaunch(
            runtime,
            _Configuration(),
            startup=CoreRuntimeStartup(endpoint=endpoint, timeout=1500),
        )
        manager = self._manager()
        operation = self._operation(manager, launch)
        succeeded = []
        timerEvents = []
        operation.succeeded.connect(succeeded.append)
        QtCore.QTimer.singleShot(0, lambda: timerEvents.append(True))

        self.assertEqual(operation.stage, ConnectionStartStage.Pending)
        self.assertTrue(waitFor(lambda: bool(succeeded), timeout=0.5))
        self.assertEqual(timerEvents, [True])
        self.assertEqual(manager.runtimes, [runtime])
        self.assertEqual(runtime.confirmCount, 1)
        self.assertFalse(runtime.startOptions[0]['waitCore'])

    def testReadinessTimeoutRollsBackTheExactRuntime(self):
        """Fail a live process whose promised local endpoint never appears."""
        server = self._server()
        port = server.serverPort()
        server.close()
        runtime = _Runtime()
        manager = self._manager()
        operation = self._operation(
            manager,
            CoreRuntimeLaunch(
                runtime,
                _Configuration(),
                startup=CoreRuntimeStartup(
                    endpoint=f'127.0.0.1:{port}',
                    timeout=60,
                    retryInterval=5,
                ),
            ),
        )
        failures = []
        operation.failed.connect(lambda *_args: failures.append(_args))

        self.assertTrue(waitFor(lambda: bool(failures)))
        self.assertEqual(manager.runtimes, [])
        self.assertEqual(runtime.stopCount, 1)
        self.assertEqual(runtime.disposeCount, 1)

    def testEarlyRuntimeExitFailsOnceAndIgnoresLateProbeEvents(self):
        """Let process termination own the terminal result before timeout."""
        runtime = _Runtime()
        manager = self._manager()
        operation = self._operation(
            manager,
            CoreRuntimeLaunch(
                runtime,
                _Configuration(),
                startup=CoreRuntimeStartup(
                    endpoint='127.0.0.1:1',
                    timeout=500,
                ),
            ),
        )
        failures = []
        operation.failed.connect(lambda *_args: failures.append(_args))

        processQtEvents()
        singleShotWeakly(0, runtime, 'fail')

        self.assertTrue(waitFor(lambda: bool(failures)))
        processQtEvents(5)
        self.assertEqual(len(failures), 1)
        self.assertEqual(runtime.stopCount, 1)
        self.assertEqual(runtime.disposeCount, 1)

    def testCancellationAndReplacementCannotCommitAStaleGeneration(self):
        """Cancel the first generation before a second ready launch commits."""
        server = self._server()
        first = _Runtime()
        second = _Runtime()
        manager = self._manager()
        registry = _Registry(
            [
                CoreRuntimeLaunch(
                    first,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint='127.0.0.1:1',
                        timeout=5000,
                    ),
                ),
                CoreRuntimeLaunch(
                    second,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint=f'127.0.0.1:{server.serverPort()}',
                        timeout=500,
                    ),
                ),
            ]
        )

        with mock.patch(
            'Furious.Service.ConnectionManager.getPluginRegistry',
            return_value=registry,
        ):
            firstOperation = manager.startAsync(
                _Configuration(),
                'Global',
                deepcopy=False,
            )
            cancelled = []
            firstOperation.cancelled.connect(cancelled.append)
            processQtEvents()

            secondOperation = manager.startAsync(
                _Configuration(),
                'Global',
                deepcopy=False,
            )
            succeeded = []
            secondOperation.succeeded.connect(succeeded.append)

            self.assertTrue(waitFor(lambda: bool(succeeded)))

        self.assertEqual(cancelled, [firstOperation])
        self.assertEqual(first.stopCount, 1)
        self.assertEqual(first.disposeCount, 1)
        self.assertEqual(manager.runtimes, [second])

    def testLegacyLaunchRetainsSynchronousStartOptions(self):
        """Do not inject waitCore into a plugin without async capability."""
        runtime = _Runtime()
        manager = self._manager()
        operation = self._operation(
            manager,
            CoreRuntimeLaunch(runtime, _Configuration()),
        )
        succeeded = []
        operation.succeeded.connect(succeeded.append)

        self.assertTrue(waitFor(lambda: bool(succeeded)))
        self.assertEqual(runtime.startOptions, [{}])
        self.assertEqual(runtime.confirmCount, 0)
        self.assertEqual(manager.runtimes, [runtime])

    def testDnsResolutionOperationCompletesAndCancelsWithoutNestedWait(self):
        """Observe recursive DNS state through timers and suppress stale cancel."""
        resolver = _ResolverFixture()
        operation = DnsResolutionOperation(
            resolver,
            'example.test',
            timeout=200,
        )
        results = []
        operation.finished.connect(
            lambda error, addresses: results.append((error, addresses))
        )
        operation.start()

        self.assertTrue(waitFor(lambda: bool(results)))
        self.assertEqual(results, [(False, ['192.0.2.10'])])

        cancelled = DnsResolutionOperation(
            resolver,
            'cancelled.test',
            timeout=200,
        )
        staleResults = []
        cancelled.finished.connect(
            lambda error, addresses: staleResults.append((error, addresses))
        )
        cancelled.start()
        cancelled.cancel()
        processQtEvents(5)

        self.assertEqual(staleResults, [])
        operation.deleteLater()
        cancelled.deleteLater()
        resolver.deleteLater()

    def testLinuxTunPreservesDeviceBeforeRuntimeOrderingWithoutNestedWait(self):
        """Create and observe the Linux device before launching tun2socks."""
        module = importlib.import_module('Furious.Service.ConnectionManager')
        server = self._server()
        primary = _Runtime()
        tun = _Runtime()
        tun.cleanup = None
        events = []
        deviceChecks = 0

        def tunFactory(**kwargs):
            tun.setExitCallback(kwargs.get('exitCallback'))

            return tun

        originalTunStart = tun.start

        def startTun(*args, **kwargs):
            events.append('tun-start')

            return originalTunStart(*args, **kwargs)

        tun.start = startTun

        def findDevice(_name):
            nonlocal deviceChecks

            deviceChecks += 1
            events.append('find-device')

            return deviceChecks >= 2

        def executeScript(*_args, **_kwargs):
            events.append('script')

            return True

        manager = ConnectionManager()
        manager._prepareTUNPolicy = mock.Mock(return_value=(False, True))
        self.managers.append(manager)
        registry = _Registry(
            [
                CoreRuntimeLaunch(
                    primary,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint=f'127.0.0.1:{server.serverPort()}',
                        timeout=500,
                    ),
                )
            ]
        )
        shortSurvival = CoreRuntimeStartup(timeout=20, retryInterval=5)

        with (
            mock.patch.object(module, 'PLATFORM', 'Linux'),
            mock.patch.object(module, 'Tun2socks', side_effect=tunFactory),
            mock.patch.object(
                module,
                'CoreRuntimeStartup',
                return_value=shortSurvival,
            ),
            mock.patch.object(
                module,
                'getPluginRegistry',
                return_value=registry,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'managedRoutes',
                [],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'getDefaultGateway',
                return_value=[('192.0.2.254', 'eth0')],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'LinuxFindTUNDevice',
                side_effect=findDevice,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'LinuxGetIpRoute',
                return_value='',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'LinuxExecutePrivilegedScript',
                side_effect=executeScript,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'LinuxDeleteTUNDevice',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'deleteRelations',
            ),
            mock.patch.object(
                module.SystemRuntime,
                'flatpakID',
                return_value='',
            ),
            mock.patch.object(
                module.PySide6Legacy,
                'eventLoopWait',
                side_effect=AssertionError('nested event loop used'),
            ),
        ):
            operation = manager.startAsync(
                _Configuration(),
                'Global',
                deepcopy=False,
            )
            succeeded = []
            operation.succeeded.connect(succeeded.append)

            self.assertTrue(waitFor(lambda: bool(succeeded)))

        self.assertEqual(
            events[:4],
            ['find-device', 'script', 'find-device', 'tun-start'],
        )
        self.assertEqual(manager.runtimes, [primary, tun])
        self.assertFalse(tun.startOptions[0]['waitCore'])

    def testWindowsTunStartsRuntimeBeforeObservingAndMutatingDevice(self):
        """Keep the Windows launch, device, then host-mutation sequence."""
        module = importlib.import_module('Furious.Service.ConnectionManager')
        server = self._server()
        primary = _Runtime()
        tun = _Runtime()
        tun.cleanup = None
        events = []

        def tunFactory(**kwargs):
            tun.setExitCallback(kwargs.get('exitCallback'))

            return tun

        originalTunStart = tun.start

        def startTun(*args, **kwargs):
            events.append('tun-start')

            return originalTunStart(*args, **kwargs)

        tun.start = startTun

        def findDevice(_name):
            events.append('find-device')

            return True

        def addRelations():
            events.append('add-relations')

        manager = ConnectionManager()
        manager._prepareTUNPolicy = mock.Mock(return_value=(False, True))
        self.managers.append(manager)
        registry = _Registry(
            [
                CoreRuntimeLaunch(
                    primary,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint=f'127.0.0.1:{server.serverPort()}',
                        timeout=500,
                    ),
                )
            ]
        )

        with (
            mock.patch.object(module, 'PLATFORM', 'Windows'),
            mock.patch.object(module, 'Tun2socks', side_effect=tunFactory),
            mock.patch.object(
                module,
                'getPluginRegistry',
                return_value=registry,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'managedRoutes',
                [],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'delete',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'getDefaultGateway',
                return_value=[('192.0.2.254', '192.0.2.10')],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'WIN32IpconfigFindContent',
                side_effect=findDevice,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'WIN32GetInterfaceAliasByIP',
                return_value='Ethernet',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'WIN32SetInterfaceDNS',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'WIN32FlushDNSCache',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'setDeviceGateway',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'addRelations',
                side_effect=addRelations,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'deleteRelations',
            ),
            mock.patch.object(
                module.PySide6Legacy,
                'eventLoopWait',
                side_effect=AssertionError('nested event loop used'),
            ),
        ):
            operation = manager.startAsync(
                _Configuration(),
                'Global',
                deepcopy=False,
            )
            succeeded = []
            operation.succeeded.connect(succeeded.append)

            self.assertTrue(waitFor(lambda: bool(succeeded)))

        self.assertEqual(
            events[:3],
            ['tun-start', 'find-device', 'add-relations'],
        )
        self.assertEqual(manager.runtimes, [primary, tun])

    def testDarwinTunSurvivalPrecedesDnsAndRouteMutation(self):
        """Observe tun2socks survival before applying macOS host networking."""
        module = importlib.import_module('Furious.Service.ConnectionManager')
        server = self._server()
        primary = _Runtime()
        tun = _Runtime()
        tun.cleanup = None
        events = []

        def tunFactory(**kwargs):
            tun.setExitCallback(kwargs.get('exitCallback'))

            return tun

        originalTunStart = tun.start

        def startTun(*args, **kwargs):
            events.append('tun-start')

            return originalTunStart(*args, **kwargs)

        tun.start = startTun

        def dnsServers():
            events.append('read-dns')

            return [('Wi-Fi', ['192.0.2.53'])]

        manager = ConnectionManager()
        manager._prepareTUNPolicy = mock.Mock(return_value=(False, True))
        self.managers.append(manager)
        registry = _Registry(
            [
                CoreRuntimeLaunch(
                    primary,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint=f'127.0.0.1:{server.serverPort()}',
                        timeout=500,
                    ),
                )
            ]
        )
        shortSurvival = CoreRuntimeStartup(timeout=20, retryInterval=5)

        with (
            mock.patch.object(module, 'PLATFORM', 'Darwin'),
            mock.patch.object(module, 'Tun2socks', side_effect=tunFactory),
            mock.patch.object(
                module,
                'CoreRuntimeStartup',
                return_value=shortSurvival,
            ),
            mock.patch.object(
                module,
                'getPluginRegistry',
                return_value=registry,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'managedRoutes',
                [],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'getDefaultGateway',
                return_value=['192.0.2.254'],
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'DarwinGetDNSServers',
                side_effect=dnsServers,
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'DarwinSetDNSServers',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'setDeviceGateway',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'addRelations',
            ),
            mock.patch.object(
                module.SystemRoutingTable,
                'deleteRelations',
            ),
            mock.patch.object(
                module.PySide6Legacy,
                'eventLoopWait',
                side_effect=AssertionError('nested event loop used'),
            ),
        ):
            operation = manager.startAsync(
                _Configuration(),
                'Global',
                deepcopy=False,
            )
            succeeded = []
            operation.succeeded.connect(succeeded.append)

            self.assertTrue(waitFor(lambda: bool(succeeded)))

        self.assertEqual(events, ['tun-start', 'read-dns'])
        self.assertEqual(manager.runtimes, [primary, tun])

    def testRepeatedCancellationReleasesOperationTimersAndRuntimes(self):
        """Keep repeated startup cancellation bounded and independently owned."""
        manager = self._manager()

        for _index in range(12):
            runtime = _Runtime()
            operation = self._operation(
                manager,
                CoreRuntimeLaunch(
                    runtime,
                    _Configuration(),
                    startup=CoreRuntimeStartup(
                        endpoint='127.0.0.1:1',
                        timeout=5000,
                    ),
                ),
            )
            processQtEvents()
            self.assertTrue(manager.cancelStart(operation))
            processQtEvents()
            self.assertEqual(runtime.stopCount, 1)
            self.assertEqual(runtime.disposeCount, 1)
            self.assertIsNone(manager._activeStartOperation)


if __name__ == '__main__':
    application()
    unittest.main()
