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

"""Provide bounded asynchronous TCP latency probes in one Qt network thread."""

from __future__ import annotations

from Furious.Qt.Signals import connectWeakly

from PySide6 import QtCore
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from shiboken6 import delete as deleteQObject

from dataclasses import dataclass

import collections
import weakref

__all__ = [
    'TcpingCancelEvent',
    'TcpingEngine',
    'TcpingRequest',
    'TcpingRequestBatchEvent',
    'TcpingResultEvent',
    'TcpingThread',
]


TCPING_REQUEST_EVENT_TYPE, TCPING_CANCEL_EVENT_TYPE, TCPING_RESULT_EVENT_TYPE = (
    QtCore.QEvent.Type(QtCore.QEvent.registerEventType()),
    QtCore.QEvent.Type(QtCore.QEvent.registerEventType()),
    QtCore.QEvent.Type(QtCore.QEvent.registerEventType()),
)


@dataclass(frozen=True)
class TcpingRequest:
    """Describe one unique endpoint probe without retaining a live profile."""

    requestId: int
    address: str
    port: int
    timeoutMilliseconds: int = 2000


class TcpingRequestBatchEvent(QtCore.QEvent):
    """Carry one coalesced request batch into the networking thread."""

    def __init__(self, requests):
        """Initialize the TcpingRequestBatchEvent."""
        super().__init__(TCPING_REQUEST_EVENT_TYPE)

        self.requests = tuple(requests)


class TcpingCancelEvent(QtCore.QEvent):
    """Carry request cancellation into the networking thread."""

    def __init__(self, requestIds):
        """Initialize the TcpingCancelEvent."""
        super().__init__(TCPING_CANCEL_EVENT_TYPE)

        self.requestIds = frozenset(requestIds)


class TcpingResultEvent(QtCore.QEvent):
    """Carry one probe result back to its GUI-thread scheduler."""

    def __init__(self, requestId: int, result):
        """Initialize the TcpingResultEvent."""
        super().__init__(TCPING_RESULT_EVENT_TYPE)

        self.requestId = requestId
        self.result = result


class TcpingProbe(QtCore.QObject):
    """Own one asynchronous socket and timeout inside the networking thread."""

    finished = QtCore.Signal(int, object, bool, bool)

    def __init__(self, request: TcpingRequest, parent=None):
        """Initialize the TcpingProbe."""
        super().__init__(parent)

        self.request = request
        self.completionHasRun = False
        self.elapsedTimer = QtCore.QElapsedTimer()
        self.socket = QTcpSocket(self)
        self.timeoutTimer = QtCore.QTimer(self)
        self.timeoutTimer.setSingleShot(True)

        connectWeakly(
            self.socket.connected,
            self,
            'handleConnected',
            sender=self.socket,
        )
        connectWeakly(
            self.socket.errorOccurred,
            self,
            'handleSocketError',
            sender=self.socket,
        )
        connectWeakly(
            self.timeoutTimer.timeout,
            self,
            'handleTimeout',
            sender=self.timeoutTimer,
        )

    def start(self):
        """Start one non-blocking TCP connection attempt."""
        self.elapsedTimer.start()
        self.timeoutTimer.start(self.request.timeoutMilliseconds)
        self.socket.connectToHost(self.request.address, self.request.port)

    @QtCore.Slot()
    def handleConnected(self):
        """Publish elapsed time after Qt completes the TCP handshake."""
        milliseconds = round(self.elapsedTimer.nsecsElapsed() / 1_000_000)

        self.complete(f'{max(milliseconds, 0)}ms')

    @QtCore.Slot(QAbstractSocket.SocketError)
    def handleSocketError(self, _error):
        """Treat a rejected or unreachable endpoint as a timed-out probe."""
        self.complete('Timeout')

    @QtCore.Slot()
    def handleTimeout(self):
        """Abort a connection attempt that exceeded the bounded deadline."""
        self.complete('Timeout', deadlineExpired=True)

    def complete(self, result, *, deadlineExpired=False, cancelled=False):
        """Stop owned resources and publish exactly one terminal outcome."""
        if self.completionHasRun:
            return

        self.completionHasRun = True
        self.timeoutTimer.stop()

        if self.socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self.socket.abort()

        self.finished.emit(
            self.request.requestId,
            result,
            bool(deadlineExpired),
            bool(cancelled),
        )

    def cancel(self):
        """Abort this probe without publishing a user-visible result."""
        self.complete(None, cancelled=True)


class TcpingEngine(QtCore.QObject):
    """Own a bounded adaptive set of probes in one dedicated event loop."""

    InitialConcurrency = 2

    def __init__(
        self,
        resultReceiver,
        maxConcurrency: int,
        parent=None,
        **kwargs,
    ):
        """Initialize the TcpingEngine without constructing thread-bound children."""
        super().__init__(parent)

        self.resultReceiver = weakref.ref(resultReceiver)
        self.maxConcurrency = max(int(maxConcurrency), 1)
        self.currentConcurrency = min(self.InitialConcurrency, self.maxConcurrency)
        self.probeFactory = kwargs.pop('probeFactory', TcpingProbe)

        self.pendingRequests = collections.deque()
        self.activeProbes = {}
        self.responsiveCompletionCount = 0
        self.stopping = False

    def event(self, event):
        """Consume request/cancellation commands in this object's thread."""
        if event.type() == TCPING_REQUEST_EVENT_TYPE:
            self.enqueueRequests(event.requests)

            return True

        if event.type() == TCPING_CANCEL_EVENT_TYPE:
            self.cancelRequests(event.requestIds)

            return True

        return super().event(event)

    def enqueueRequests(self, requests):
        """Queue unique endpoints and start work within the current window."""
        if self.stopping:
            return

        self.pendingRequests.extend(requests)
        self.drain()

    def drain(self):
        """Construct sockets incrementally inside the networking thread."""
        while (
            not self.stopping
            and self.pendingRequests
            and len(self.activeProbes) < self.currentConcurrency
        ):
            request = self.pendingRequests.popleft()
            probe = self.probeFactory(request, parent=self)

            self.activeProbes[request.requestId] = probe

            connectWeakly(
                probe.finished,
                self,
                'handleProbeFinished',
                sender=probe,
            )

            probe.start()

    @QtCore.Slot(int, object, bool, bool)
    def handleProbeFinished(
        self,
        requestId: int,
        result,
        deadlineExpired: bool,
        cancelled: bool,
    ):
        """Release one probe, adapt the window, and post a result to the GUI."""
        probe = self.activeProbes.pop(requestId, None)

        if probe is None:
            return

        probe.deleteLater()

        if not cancelled:
            self.recordOutcome(deadlineExpired)
            self.postResult(requestId, result)

        self.drain()

    def recordOutcome(self, deadlineExpired: bool):
        """Use additive increase and timeout-driven multiplicative decrease."""
        if deadlineExpired:
            self.currentConcurrency = max(self.currentConcurrency // 2, 1)
            self.responsiveCompletionCount = 0

            return

        self.responsiveCompletionCount += 1

        growthThreshold = max(self.currentConcurrency * 2, 4)

        if (
            self.responsiveCompletionCount >= growthThreshold
            and self.currentConcurrency < self.maxConcurrency
        ):
            self.currentConcurrency += 1
            self.responsiveCompletionCount = 0

    def postResult(self, requestId: int, result):
        """Post one immutable result without retaining the GUI scheduler."""
        receiver = self.resultReceiver()

        if receiver is None:
            return

        try:
            QtCore.QCoreApplication.postEvent(
                receiver, TcpingResultEvent(requestId, result)
            )
        except RuntimeError:
            # The receiver's native QObject was deleted between weak resolution
            # and the thread-safe event post.
            pass

    def cancelRequests(self, requestIds):
        """Remove queued requests and abort matching active sockets."""
        requestIds = set(requestIds)

        self.pendingRequests = collections.deque(
            request
            for request in self.pendingRequests
            if request.requestId not in requestIds
        )

        for requestId in requestIds:
            probe = self.activeProbes.get(requestId)

            if probe is not None:
                probe.cancel()

        self.drain()

    @QtCore.Slot()
    def shutdown(self):
        """Abort every owned socket before the dedicated event loop stops."""
        if self.stopping:
            return

        self.stopping = True
        self.pendingRequests.clear()

        for probe in list(self.activeProbes.values()):
            probe.cancel()


class TcpingThread(QtCore.QThread):
    """Run and finally destroy one Tcping engine in its own native thread."""

    def __init__(self, engine: TcpingEngine, parent=None):
        """Initialize the TcpingThread."""
        super().__init__(parent)

        self.engine = engine

    def run(self):
        """Run the event loop, then synchronously destroy its stopped engine."""
        try:
            self.exec()
        finally:
            self.engine.shutdown()

            deleteQObject(self.engine)

            self.engine = None
