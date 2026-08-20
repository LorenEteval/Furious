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

"""Exercise Frozenlib state helpers and mocked host-operation boundaries."""

from __future__ import annotations

from Furious.Controllers.SettingsController import SettingsController
from Furious.Frozenlib import AppSettings, Mixins
from Furious.Window.SettingsPage import _ToggleSettingsCard

from PySide6 import QtCore
from PySide6.QtWidgets import QPushButton

from unittest import mock

import importlib
import logging
import socket
import subprocess
import sys
import threading
import types
import unittest

from tests.support import application, isolatedSettings, processQtEvents

StartupOnBootModule = importlib.import_module('Furious.Frozenlib.StartupOnBoot')
SystemProxyModule = importlib.import_module('Furious.Frozenlib.SystemProxy')
SystemRoutingTableModule = importlib.import_module(
    'Furious.Frozenlib.SystemRoutingTable'
)
TcpingModule = importlib.import_module('Furious.Frozenlib.Tcping')
UtilityModule = importlib.import_module('Furious.Frozenlib.Utility')
Win32SessionModule = importlib.import_module('Furious.Frozenlib.Win32Session')


class FrozenlibQtContextTest(unittest.TestCase):
    """Verify Qt context helpers restore exact prior state when nested."""

    @classmethod
    def setUpClass(cls):
        """Create the suite-owned QApplication before constructing widgets."""
        application()

    def testDisabledContextPreservesPriorAndNestedState(self):
        """Restore both initially enabled and initially disabled widgets."""
        button = QPushButton()

        with Mixins.QSetDisabledContext(button):
            self.assertFalse(button.isEnabled())

            with Mixins.QSetDisabledContext(button):
                self.assertFalse(button.isEnabled())

            self.assertFalse(button.isEnabled())

        self.assertTrue(button.isEnabled())

        button.setDisabled(True)

        with Mixins.QSetDisabledContext(button):
            self.assertFalse(button.isEnabled())

        self.assertFalse(button.isEnabled())

        button.deleteLater()

        processQtEvents()

    def testSignalContextPreservesPriorAndNestedState(self):
        """Restore both initially unblocked and initially blocked QObjects."""
        qobject = QtCore.QObject()

        with Mixins.QBlockSignalContext(qobject):
            self.assertTrue(qobject.signalsBlocked())

            with Mixins.QBlockSignalContext(qobject):
                self.assertTrue(qobject.signalsBlocked())

            self.assertTrue(qobject.signalsBlocked())

        self.assertFalse(qobject.signalsBlocked())

        qobject.blockSignals(True)

        with Mixins.QBlockSignalContext(qobject):
            self.assertTrue(qobject.signalsBlocked())

        self.assertTrue(qobject.signalsBlocked())

    def testFailedToggleRequestRestoresPersistedState(self):
        """Keep a switch synchronized when its host-side callback fails."""
        with isolatedSettings():
            AppSettings.turnOFF('StartupOnBoot')
            callback = mock.Mock(return_value=False)

            card = _ToggleSettingsCard(None, 'StartupOnBoot', callback)
            card.checkBox.setChecked(True)

            callback.assert_called_once_with(True)

            self.assertFalse(card.checkBox.isChecked())
            self.assertTrue(AppSettings.isStateOFF('StartupOnBoot'))

            card.deleteLater()

            processQtEvents()


class FrozenlibUtilityTest(unittest.TestCase):
    """Verify bounded caches, commands, throttling, and dual-stack probes."""

    def tearDown(self):
        """Clear shared utility caches so tests remain order-independent."""
        UtilityModule.isValidIPAddress.cache_clear()
        UtilityModule.parseHostPort.cache_clear()
        UtilityModule.absolutePath.cache_clear()
        UtilityModule.versionToValue.cache_clear()

    def testCallRateLimitedSkipsExcessCallsWithoutSleeping(self):
        """Throttle on the leading edge without blocking the caller thread."""
        calls = []

        @UtilityModule.callRateLimited(maxCallPerSecond=2)
        def callback(value):
            calls.append(value)

            return value

        with (
            mock.patch.object(
                UtilityModule.time,
                'monotonic',
                side_effect=(10.0, 10.1, 10.5),
            ),
            mock.patch.object(UtilityModule.time, 'sleep') as sleep,
        ):
            self.assertEqual(callback('first'), 'first')
            self.assertIsNone(callback('suppressed'))
            self.assertEqual(callback('second'), 'second')

        self.assertEqual(calls, ['first', 'second'])

        sleep.assert_not_called()

    def testRateLimitRejectsInvalidRates(self):
        """Reject zero and negative rates instead of dividing or sleeping."""
        with self.assertRaises(ValueError):
            UtilityModule.callRateLimited(0)

        with self.assertRaises(ValueError):
            UtilityModule.callRateLimited(-1)

    def testExternalCommandsHaveAnOverridableBoundedTimeout(self):
        """Apply the shared timeout without invoking a real child process."""
        completed = subprocess.CompletedProcess(['fixture'], 0)

        with (
            mock.patch.object(UtilityModule, 'PLATFORM', 'Linux'),
            mock.patch.object(
                UtilityModule.subprocess,
                'run',
                return_value=completed,
            ) as run,
        ):
            self.assertIs(
                UtilityModule.runExternalCommand(['fixture']),
                completed,
            )
            self.assertIs(
                UtilityModule.runExternalCommand(['fixture'], timeout=1.5),
                completed,
            )

        self.assertEqual(
            run.call_args_list,
            [
                mock.call(['fixture'], timeout=30.0),
                mock.call(['fixture'], timeout=1.5),
            ],
        )

    def testHostPortCacheIsBoundedAndRetainsIPv6Parsing(self):
        """Bound externally influenced keys while preserving IPv6 authority parsing."""
        for index in range(UtilityModule.parseHostPort.cache_info().maxsize + 25):
            UtilityModule.parseHostPort(f'host-{index}.example:443')

        info = UtilityModule.parseHostPort.cache_info()

        self.assertIsNotNone(info.maxsize)
        self.assertLessEqual(info.currsize, info.maxsize)
        self.assertEqual(
            UtilityModule.parseHostPort('[2001:db8::1]:8443'),
            ('2001:db8::1', '8443'),
        )

    def testTcpingUsesResolverIPv6AndFallsBackToIPv4(self):
        """Use getaddrinfo candidates rather than IPv4-only gethostbyname."""
        candidates = [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                '',
                ('2001:db8::1', 443, 0, 0),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                '',
                ('192.0.2.1', 443),
            ),
        ]
        sockets = []

        class FakeSocket:
            """Record one fully mocked TCP connection attempt."""

            def __init__(self, family, socketType, protocol):
                self.family = family
                self.socketType = socketType
                self.protocol = protocol
                self.timeout = None
                self.address = None

                sockets.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def settimeout(self, timeout):
                self.timeout = timeout

            def connect(self, address):
                self.address = address

                if self.family == socket.AF_INET6:
                    raise OSError('IPv6 fixture unavailable')

        with (
            mock.patch.object(
                TcpingModule.socket,
                'getaddrinfo',
                return_value=candidates,
            ) as getaddrinfo,
            mock.patch.object(TcpingModule.socket, 'socket', side_effect=FakeSocket),
            mock.patch.object(
                TcpingModule.time,
                'perf_counter',
                side_effect=(10.0, 10.125),
            ),
        ):
            sent, rtts = TcpingModule.tcping(
                'dual-stack.example',
                443,
                timeout=0.5,
                count=1,
                interval=0,
            )

        self.assertEqual(sent, 1)
        self.assertEqual(rtts, [0.125])
        self.assertEqual(
            [item.family for item in sockets], [socket.AF_INET6, socket.AF_INET]
        )
        self.assertEqual(sockets[0].address, ('2001:db8::1', 443, 0, 0))
        self.assertEqual(sockets[1].address, ('192.0.2.1', 443))
        self.assertEqual([item.timeout for item in sockets], [0.5, 0.5])

        getaddrinfo.assert_called_once_with(
            'dual-stack.example',
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )


class MockedPlatformHelperTest(unittest.TestCase):
    """Exercise platform helpers without touching host startup or networking."""

    def testProxyDaemonClearsIndependentExitAndCanRestart(self):
        """Release an exited daemon reference without retaining a stale owner."""
        proxy = SystemProxyModule._SystemProxy()
        started = [threading.Event(), threading.Event()]
        release = [threading.Event(), threading.Event()]
        attempts = iter(zip(started, release))

        def runDaemon():
            """Block each fully mocked daemon until the test releases it."""
            startedEvent, releaseEvent = next(attempts)
            startedEvent.set()
            releaseEvent.wait(1)

        native = types.SimpleNamespace(daemon_on_=mock.Mock(side_effect=runDaemon))
        firstThread, secondThread = None, None

        with (
            mock.patch.object(SystemProxyModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                SystemProxyModule,
                'handleAppSystemProxyMode',
                return_value=True,
            ),
            mock.patch.dict(sys.modules, {'sysproxy': native}),
        ):
            try:
                proxy.daemonOn_()
                self.assertTrue(started[0].wait(1))

                firstThread = proxy._daemonThread
                release[0].set()
                firstThread.join(1)

                self.assertFalse(firstThread.is_alive())
                self.assertIsNone(proxy._daemonThread)

                proxy.daemonOn_()
                self.assertTrue(started[1].wait(1))
                secondThread = proxy._daemonThread

                self.assertIsNot(secondThread, firstThread)
                self.assertEqual(native.daemon_on_.call_count, 2)
            finally:
                release[0].set()
                release[1].set()

                for thread in (firstThread, secondThread):
                    if isinstance(thread, threading.Thread):
                        thread.join(1)

    def testProxyDaemonShutdownWaitIsBounded(self):
        """Retain a still-live proxy daemon after one bounded shutdown wait."""
        proxy = SystemProxyModule._SystemProxy()
        proxy.DaemonShutdownTimeout = 0.01

        release = threading.Event()

        thread = threading.Thread(target=release.wait, daemon=True)
        thread.start()

        proxy._daemonThread = thread
        native = types.SimpleNamespace(daemon_off=mock.Mock(return_value=True))

        with (
            mock.patch.object(SystemProxyModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                SystemProxyModule,
                'handleAppSystemProxyMode',
                return_value=True,
            ),
            mock.patch.dict(sys.modules, {'sysproxy': native}),
        ):
            try:
                proxy.daemonOff()

                self.assertIs(proxy._daemonThread, thread)
                self.assertTrue(thread.is_alive())

                native.daemon_off.assert_called_once_with()
            finally:
                release.set()
                thread.join(1)

    def testSessionShutdownWaitIsBounded(self):
        """Return from shutdown while retaining a still-live session listener."""
        session = Win32SessionModule._Win32Session()
        session.ShutdownTimeout = 0.01

        release = threading.Event()

        thread = threading.Thread(target=release.wait, daemon=True)
        thread.start()

        session._daemonThread = thread
        native = types.SimpleNamespace(off=mock.Mock(return_value=True))

        with (
            mock.patch.object(Win32SessionModule, 'PLATFORM', 'Windows'),
            mock.patch.dict(sys.modules, {'win32session': native}),
        ):
            try:
                self.assertFalse(session.off())
                self.assertIs(session._daemonThread, thread)
                self.assertTrue(thread.is_alive())

                native.off.assert_called_once_with()
            finally:
                release.set()
                thread.join(1)

    def testSessionStartFailureIsLoggedAndClearsReference(self):
        """Return failure instead of leaking a thread-start exception."""

        class FailingThread:
            """Provide one deterministic thread whose start always fails."""

            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

            def is_alive(self):
                return False

            def start(self):
                raise RuntimeError('fixture start failure')

        session = Win32SessionModule._Win32Session()
        native = types.SimpleNamespace(run=mock.Mock())

        with (
            mock.patch.object(Win32SessionModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                Win32SessionModule.threading,
                'Thread',
                FailingThread,
            ),
            mock.patch.dict(sys.modules, {'win32session': native}),
            self.assertLogs(Win32SessionModule.logger, logging.ERROR) as logs,
        ):
            self.assertFalse(session.run())

        self.assertIsNone(session._daemonThread)

        native.run.assert_not_called()

        self.assertIn('failed to start Windows session listener', logs.output[0])

    def testStartupHelpersReturnMockedHostResults(self):
        """Expose success and failure instead of discarding registration results."""
        with (
            mock.patch.object(StartupOnBootModule, 'PLATFORM', 'Linux'),
            mock.patch.object(
                StartupOnBootModule.SystemRuntime,
                'isScriptMode',
                return_value=False,
            ),
            mock.patch.object(
                StartupOnBootModule.os,
                'makedirs',
                side_effect=PermissionError,
            ),
        ):
            self.assertFalse(StartupOnBootModule.StartupOnBoot.on_())

        with (
            mock.patch.object(StartupOnBootModule, 'PLATFORM', 'Linux'),
            mock.patch.object(
                StartupOnBootModule.os,
                'remove',
                side_effect=FileNotFoundError,
            ),
        ):
            self.assertTrue(StartupOnBootModule.StartupOnBoot.off())

    def testStartupSettingChangesOnlyAfterHostSuccess(self):
        """Do not persist a state that the mocked host rejected."""
        with isolatedSettings():
            AppSettings.turnOFF('StartupOnBoot')

            with mock.patch(
                'Furious.Controllers.SettingsController.StartupOnBoot.on_',
                return_value=False,
            ):
                self.assertFalse(SettingsController.setStartupOnBoot(True))

            self.assertTrue(AppSettings.isStateOFF('StartupOnBoot'))

            with mock.patch(
                'Furious.Controllers.SettingsController.StartupOnBoot.on_',
                return_value=True,
            ):
                self.assertTrue(SettingsController.setStartupOnBoot(True))

            self.assertTrue(AppSettings.isStateON_('StartupOnBoot'))

            with mock.patch(
                'Furious.Controllers.SettingsController.StartupOnBoot.off',
                return_value=False,
            ):
                self.assertFalse(SettingsController.setStartupOnBoot(False))

            self.assertTrue(AppSettings.isStateON_('StartupOnBoot'))

    def testLinuxSystemProxyUsesOnlyMockedCommands(self):
        """Cover proxy configuration without changing the real desktop proxy."""
        with (
            mock.patch.object(SystemProxyModule, 'PLATFORM', 'Linux'),
            mock.patch.object(
                SystemProxyModule,
                'handleAppSystemProxyMode',
                return_value=True,
            ),
            mock.patch.object(SystemProxyModule, 'linuxProxyConfig') as configure,
        ):
            SystemProxyModule.SystemProxy.set(
                '127.0.0.1:10809',
                'localhost;127.0.0.1',
            )

        self.assertEqual(configure.call_count, 6)
        self.assertEqual(
            configure.call_args_list[-1],
            mock.call('proxy', 'mode', 'manual'),
        )

    def testRoutingTableUsesOnlyMockedCommands(self):
        """Cover route command construction without changing real routes."""
        completed = subprocess.CompletedProcess(
            ['route'],
            0,
            stdout=b'',
            stderr=b'',
        )

        with (
            mock.patch.object(SystemRoutingTableModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                SystemRoutingTableModule,
                'runExternalCommand',
                return_value=completed,
            ) as run,
        ):
            SystemRoutingTableModule.SystemRoutingTable.add(
                '203.0.113.0',
                '192.0.2.1',
            )

        run.assert_called_once_with(
            ['route', 'add', '203.0.113.0', '192.0.2.1', 'metric', '5'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def testDnsHelperUsesOnlyMockedCommands(self):
        """Cover DNS command construction without changing host DNS settings."""
        completed = subprocess.CompletedProcess(
            ['netsh'],
            0,
            stdout=b'',
            stderr=b'',
        )

        with (
            mock.patch.object(SystemRoutingTableModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                SystemRoutingTableModule,
                'runExternalCommand',
                return_value=completed,
            ) as run,
        ):
            SystemRoutingTableModule.SystemRoutingTable.WIN32SetInterfaceDNS(
                'Fixture Adapter',
                address='192.0.2.53',
                dhcp=False,
            )

        run.assert_called_once_with(
            'netsh interface ip set dns name="Fixture Adapter" static 192.0.2.53',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            check=True,
        )

    def testSessionHelperUsesOnlyMockedNativeModule(self):
        """Cover session startup and shutdown without host-session monitoring."""
        native = types.SimpleNamespace(
            set=mock.Mock(),
            run=mock.Mock(),
            off=mock.Mock(return_value=True),
        )
        session = Win32SessionModule._Win32Session()
        callback = mock.Mock()

        with (
            mock.patch.object(Win32SessionModule, 'PLATFORM', 'Windows'),
            mock.patch.dict(sys.modules, {'win32session': native}),
        ):
            self.assertTrue(session.set(callback))
            self.assertTrue(session.run())
            self.assertTrue(session.off())

        native.set.assert_called_once_with(callback)
        native.run.assert_called_once_with()
        native.off.assert_called_once_with()

        self.assertIsNone(session._daemonThread)


if __name__ == '__main__':
    unittest.main()
