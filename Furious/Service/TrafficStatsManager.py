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

"""Sample plugin-provided traffic counters without blocking the Qt UI."""

from __future__ import annotations

from Furious.Frozenlib import APP, Mixins
from Furious.Plugins import TrafficCounters, getPluginRegistry

from PySide6 import QtCore

from concurrent.futures import Future, ThreadPoolExecutor

import time
import logging

__all__ = [
    'TrafficStatsManager',
    'formatTrafficSpeed',
    'formatTrafficUsage',
]

logger = logging.getLogger(__name__)

KIBIBYTE = 1024
MEBIBYTE = KIBIBYTE * KIBIBYTE
TRAFFIC_STATS_SAMPLE_INTERVAL = 2000


def formatTrafficSpeed(bytesPerSecond: float) -> str:
    """Format a byte rate using compact binary units."""
    try:
        value = max(float(bytesPerSecond), 0.0)
    except (TypeError, ValueError):
        value = 0.0

    if value < KIBIBYTE:
        return '< 1 KiB/s'

    if value >= MEBIBYTE:
        amount = value / MEBIBYTE
        unit = 'MiB/s'
    else:
        amount = value / KIBIBYTE
        unit = 'KiB/s'

    formatted = f'{amount:.2f}'.rstrip('0').rstrip('.')

    return f'{formatted} {unit}'


def formatTrafficUsage(bytesUsed: int) -> str:
    """Format cumulative traffic using compact binary units."""
    try:
        value = max(int(bytesUsed), 0)
    except (TypeError, ValueError, OverflowError):
        value = 0

    if value < KIBIBYTE:
        return f'{value} B'

    amount = float(value)
    units = ('KiB', 'MiB', 'GiB', 'TiB', 'PiB')

    for unit in units:
        amount /= KIBIBYTE

        if amount < KIBIBYTE or unit == units[-1]:
            formatted = f'{amount:.2f}'.rstrip('0').rstrip('.')

            return f'{formatted} {unit}'

    return f'{value} B'


def _queryTrafficStats(monitor):
    """Query counters in a worker thread and timestamp the result."""
    try:
        counters = monitor.query(monitor.target)
    except Exception:
        # Any non-exit exceptions

        counters = None

    return counters, time.monotonic()


class TrafficStatsManager(
    Mixins.ConnectionAware,
    Mixins.CleanupOnExit,
    QtCore.QObject,
):
    """Publish plugin traffic usage and rates while its parent is visible."""

    speedChanged = QtCore.Signal(float, float)
    usageChanged = QtCore.Signal(object, object)
    statisticsUnavailable = QtCore.Signal()
    _sampleReady = QtCore.Signal(int, object, float)

    def __init__(self, parent=None):
        """Initialize the timer and lazy worker-thread state."""
        super().__init__(parent)

        self._executor = None
        self._future = None
        self._monitor = None
        self._generation = 0
        self._queryInFlight = False
        self._previousCounters = None
        self._previousSampleTime = None

        self._sampleTimer = QtCore.QTimer(self)
        self._sampleTimer.setInterval(TRAFFIC_STATS_SAMPLE_INTERVAL)
        self._sampleTimer.timeout.connect(self._requestSample)
        self._sampleReady.connect(self._consumeResult)

        if parent is not None:
            parent.installEventFilter(self)

    def _parentIsVisible(self) -> bool:
        """Return whether the parent widget can currently display updates."""
        parent = self.parent()

        if parent is None or not hasattr(parent, 'isVisible'):
            return True

        return parent.isVisible() and not (
            hasattr(parent, 'isMinimized') and parent.isMinimized()
        )

    def _suspendSampling(self):
        """Pause polling and discard the current rate baseline."""
        wasActive = self._sampleTimer.isActive() or self._queryInFlight
        self._sampleTimer.stop()

        if wasActive:
            self._generation += 1
            self._resetSamples()

    def _resumeSampling(self):
        """Resume polling when a monitor and visible parent are available."""
        if self._monitor is None or not self._parentIsVisible():
            return

        if not self._ensureExecutor():
            self.statisticsUnavailable.emit()

            return

        self._sampleTimer.start()
        self._requestSample()

    @QtCore.Slot()
    def _syncSamplingVisibility(self):
        """Synchronize polling with the parent widget's visibility."""
        if self._parentIsVisible():
            self._resumeSampling()
        else:
            self._suspendSampling()

    def eventFilter(self, watched, event):
        """Pause traffic queries while the parent widget is not visible."""
        if watched is self.parent():
            eventType = event.type()

            if eventType == QtCore.QEvent.Type.Hide:
                self._suspendSampling()
            elif eventType in (
                QtCore.QEvent.Type.Show,
                QtCore.QEvent.Type.WindowStateChange,
            ):
                QtCore.QTimer.singleShot(0, self._syncSamplingVisibility)

        return super().eventFilter(watched, event)

    @staticmethod
    def _activeProcesses():
        """Return the processes owned by the active tray connection."""
        try:
            return tuple(APP().systemTray.ConnectAction.coreManager.processesPool)
        except (AttributeError, RuntimeError):
            return tuple()

    def _closeExecutor(self):
        """Cancel queued work and release the background query executor."""
        future = self._future
        executor = self._executor

        self._future = None
        self._executor = None

        if future is not None:
            future.cancel()

        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def _ensureExecutor(self) -> bool:
        """Create the single background query thread when needed."""
        if self._executor is not None:
            return True

        try:
            self._executor = ThreadPoolExecutor(max_workers=1)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'failed to start traffic statistics worker: {ex}')

            self._closeExecutor()

            return False

        return True

    def _futureCompleted(self, generation: int, future: Future):
        """Forward a worker result to the manager's Qt thread."""
        try:
            counters, sampledAt = future.result()
        except Exception:
            # Any non-exit exceptions

            counters, sampledAt = None, time.monotonic()

        try:
            self._sampleReady.emit(generation, counters, sampledAt)
        except RuntimeError:
            # The application may be closing after the query completed.
            pass

    def _resetSamples(self):
        """Discard the previous counter baseline and in-flight marker."""
        self._queryInFlight = False
        self._previousCounters = None
        self._previousSampleTime = None

    def _activateMonitor(self, monitor):
        """Begin sampling one plugin-provided monitor."""
        self._sampleTimer.stop()
        self._generation += 1
        self._monitor = monitor
        self._resetSamples()

        if monitor is None:
            self._closeExecutor()
            self.statisticsUnavailable.emit()

            return

        self._resumeSampling()

    @QtCore.Slot()
    def _requestSample(self):
        """Queue one statistics query unless another query is still running."""
        if self._monitor is None or self._queryInFlight or not self._parentIsVisible():
            return

        if not self._ensureExecutor():
            self.statisticsUnavailable.emit()

            return

        try:
            future = self._executor.submit(_queryTrafficStats, self._monitor)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'failed to queue traffic statistics query: {ex}')

            return

        self._future = future
        self._queryInFlight = True

        future.add_done_callback(
            lambda completed, generation=self._generation: self._futureCompleted(
                generation,
                completed,
            )
        )

    def _updateSpeeds(self, counters: TrafficCounters, sampledAt: float):
        """Calculate and emit rates from one cumulative counter sample."""
        self.usageChanged.emit(counters.uplink, counters.downlink)

        previousCounters = self._previousCounters
        previousSampleTime = self._previousSampleTime

        self._previousCounters = counters
        self._previousSampleTime = sampledAt

        if previousCounters is None or previousSampleTime is None:
            self.speedChanged.emit(0.0, 0.0)

            return

        elapsed = sampledAt - previousSampleTime

        if elapsed <= 0:
            self.speedChanged.emit(0.0, 0.0)

            return

        uplinkDelta = max(counters.uplink - previousCounters.uplink, 0)
        downlinkDelta = max(counters.downlink - previousCounters.downlink, 0)

        self.speedChanged.emit(uplinkDelta / elapsed, downlinkDelta / elapsed)

    @QtCore.Slot(int, object, float)
    def _consumeResult(self, generation, counters, sampledAt):
        """Consume one worker result on Qt's GUI thread."""
        if not self._parentIsVisible():
            self._suspendSampling()

            return

        if generation != self._generation:
            return

        self._future = None
        self._queryInFlight = False

        if not isinstance(counters, TrafficCounters):
            self._previousCounters = None
            self._previousSampleTime = None
            self.statisticsUnavailable.emit()

            return

        self._updateSpeeds(counters, sampledAt)

    def connectedCallback(self):
        """Discover and activate statistics for the connected runtime."""
        monitor = getPluginRegistry().trafficStatsMonitorForKernels(
            self._activeProcesses()
        )
        self._activateMonitor(monitor)

    def disconnectedCallback(self):
        """Stop sampling and clear traffic speeds after disconnecting."""
        self._sampleTimer.stop()
        self._generation += 1
        self._monitor = None
        self._resetSamples()
        self._closeExecutor()
        self.statisticsUnavailable.emit()

    def cleanup(self):
        """Release the timer and background query executor."""
        self.disconnectedCallback()
