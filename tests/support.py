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

"""Provide isolated Qt, settings, and lifetime helpers for the test suite."""

from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager

import os
import gc
import time
import uuid
import ctypes
import tempfile
import weakref

# Select the headless platform before importing any Qt module.  This process is
# deliberately independent from any production Furious process and its native
# windows.
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from shiboken6 import isValid


class _DisconnectedController:
    """Provide the read-only connection state required by theme-aware widgets."""

    interactionEnabled = True

    @staticmethod
    def isConnected() -> bool:
        """Return the deterministic disconnected state used by UI tests."""
        return False


class TestApplication(QApplication):
    """Provide only application attributes required to construct real widgets."""

    __test__ = False

    def __init__(self):
        """Initialize one side-effect-free application for this test process."""
        super().__init__([])

        self.setApplicationName('Furious Tests')
        self.setOrganizationName('Furious Tests')
        self.setOrganizationDomain('tests.invalid')

        self.connectionController = _DisconnectedController()
        self.routingController = None
        self.settingsController = None
        self.systemTray = None
        self.mainWindow = None
        self.logManager = None
        self.logPage = None
        self.customFontName = ''
        self.threadPool = QtCore.QThreadPool(self)

    @staticmethod
    def theme() -> str:
        """Return a stable theme without consulting host appearance settings."""
        return 'Dark'

    @staticmethod
    def usesForcedDarkTheme() -> bool:
        """Return whether the test theme represents a user-forced preference."""
        return False

    @staticmethod
    def isExiting() -> bool:
        """Return whether the application is currently exiting."""
        return False

    @staticmethod
    def applyThemePreference():
        """Accept controller callbacks without mutating host appearance."""


_application = None


def application() -> QApplication:
    """Return the single QApplication-compatible instance for all tests."""
    global _application

    current = QApplication.instance()

    if current is None:
        _application = TestApplication()

        current = _application

    return current


def processQtEvents(rounds: int = 3):
    """Drain regular and deferred-delete events deterministically."""
    app = application()

    for _index in range(max(1, rounds)):
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)


def waitFor(predicate, timeout: float = 2.0) -> bool:
    """Pump Qt events until *predicate* succeeds or a bounded timeout expires."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        processQtEvents(1)

        if predicate():
            return True

        QtCore.QThread.msleep(1)

    processQtEvents()

    return bool(predicate())


def closeTransient(widget) -> weakref.ReferenceType:
    """Close one transient through its production path and return a weak ref."""
    reference = weakref.ref(widget)

    widget.close()

    return reference


def collectAtBoundary():
    """Collect Python cycles at a diagnostic batch boundary, then drain Qt."""
    processQtEvents()

    gc.collect()

    processQtEvents()


def qObjectCount(qobjectType) -> int:
    """Count valid Python wrappers of one application-owned QObject type."""
    count = 0

    for value in gc.get_objects():
        try:
            if isinstance(value, qobjectType) and isValid(value):
                count += 1
        except (ReferenceError, RuntimeError):
            continue

    return count


def currentRSS() -> int | None:
    """Return current resident memory where a stable platform API is available."""
    if os.name == 'nt':

        class ProcessMemoryCounters(ctypes.Structure):
            """Match the Windows PROCESS_MEMORY_COUNTERS structure."""

            _fields_ = (
                ('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            )

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)

        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = ()
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p

        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        )
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int

        process = kernel32.GetCurrentProcess()

        if psapi.GetProcessMemoryInfo(
            process,
            ctypes.byref(counters),
            counters.cb,
        ):
            return int(counters.WorkingSetSize)

        return None

    statm = Path('/proc/self/statm')

    if statm.exists():
        residentPages = int(statm.read_text(encoding='ascii').split()[1])

        return residentPages * int(os.sysconf('SC_PAGE_SIZE'))

    return None


@contextmanager
def isolatedSettings():
    """Route every QSettings read/write to one temporary test namespace."""
    app = application()

    with tempfile.TemporaryDirectory(prefix='furious-tests-settings-') as directory:
        oldOrganization, oldApplication = (
            app.organizationName(),
            app.applicationName(),
        )

        namespace = uuid.uuid4().hex

        QtCore.QSettings.setDefaultFormat(QtCore.QSettings.Format.IniFormat)
        QtCore.QSettings.setPath(
            QtCore.QSettings.Format.IniFormat,
            QtCore.QSettings.Scope.UserScope,
            directory,
        )

        app.setOrganizationName(f'Furious Tests {namespace}')
        app.setApplicationName(f'Furious Tests {namespace}')

        settings = QtCore.QSettings()
        settings.clear()
        settings.sync()

        try:
            yield settings
        finally:
            settings.clear()
            settings.sync()

            app.setOrganizationName(oldOrganization)
            app.setApplicationName(oldApplication)
