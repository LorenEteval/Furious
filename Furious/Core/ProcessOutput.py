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

"""Transport bounded child-process output without owning process lifecycle."""

from __future__ import annotations

from Furious.Frozenlib import SystemRuntime
from Furious.Qt.Signals import connectWeakly

from PySide6 import QtCore

from typing import Callable

import os
import sys
import time
import uuid
import queue
import threading
import multiprocessing
import multiprocessing.queues

__all__ = ['MsgQueue', 'ProcessOutputRedirector']


class MsgQueue(multiprocessing.queues.Queue):
    """Continuously drain a bounded child-process log queue into a callback."""

    MSG_PRODUCE_THRESHOLD = 1024
    ACTIVE_DRAIN_INTERVAL = 16
    MAXIMUM_IDLE_DRAIN_INTERVAL = 256
    DRAIN_INTERVAL = ACTIVE_DRAIN_INTERVAL
    MAXIMUM_PENDING_MESSAGES = 1024
    MAXIMUM_MESSAGE_CHARACTERS = 64 * 1024
    MAXIMUM_MESSAGES_PER_TICK = 512
    TRUNCATION_MARKER = '\n... [core log message truncated]'

    def __init__(self, **kwargs):
        """Initialize the bounded queue and its GUI-thread drain timer."""
        callback = kwargs.pop('msgCallback', None)
        maximum = kwargs.pop('maximumPendingMessages', self.MAXIMUM_PENDING_MESSAGES)

        super().__init__(
            maxsize=maximum,
            **kwargs,
            ctx=multiprocessing.get_context(),
        )

        self.timer = QtCore.QTimer()
        self._timerConnection = connectWeakly(
            self.timer.timeout,
            self,
            'processMsg',
        )
        self.timeout = self.ACTIVE_DRAIN_INTERVAL
        self.callback = callback
        self._disposed = False

    def getNoWait(self) -> str:
        """Return one queued message or an empty value."""
        try:
            return self.get_nowait()
        except Exception:
            # Any non-exit exceptions

            return ''

    def getTimeout(self) -> int:
        """Return the current adaptive drain interval."""
        return self.timeout

    def setTimeout(self, timeout: int):
        """Set the adaptive drain interval."""
        self.timeout = timeout

    def startTimer(self):
        """Start draining on the queue owner's Qt thread."""
        if not self._disposed:
            self.timer.start(self.getTimeout())

    def stopTimer(self):
        """Stop draining output."""
        self.timer.stop()

    def dispose(self):
        """Idempotently release the Qt timer and queue handles."""
        if self._disposed:
            return

        self._disposed = True
        self.stopTimer()

        if self._timerConnection is not None:
            try:
                QtCore.QObject.disconnect(self._timerConnection)
            except (RuntimeError, TypeError):
                pass

            self._timerConnection = None

        self.timer.deleteLater()
        self.callback = None

        try:
            self.close()
        except (OSError, ValueError):
            pass

    def putMessage(self, message) -> bool:
        """Queue one bounded message without blocking a child process."""
        text = str(message)

        if len(text) > self.MAXIMUM_MESSAGE_CHARACTERS:
            mark = self.TRUNCATION_MARKER
            text = text[: self.MAXIMUM_MESSAGE_CHARACTERS - len(mark)] + mark

        try:
            self.put_nowait(text)
        except (queue.Full, OSError, ValueError):
            return False

        return True

    def processMsg(self):
        """Drain one bounded batch and adapt polling to recent activity."""
        if not callable(self.callback):
            return

        hasMessages = False
        appendMany = getattr(self.callback, 'appendMany', None)
        messages = [] if callable(appendMany) else None

        for _ in range(self.MAXIMUM_MESSAGES_PER_TICK):
            message = self.getNoWait()

            if not message:
                break

            hasMessages = True

            if not message.isspace():
                if messages is None:
                    self.callback(message)
                else:
                    messages.append(message)

        if messages:
            appendMany(messages)

        nextTimeout = (
            self.ACTIVE_DRAIN_INTERVAL
            if hasMessages
            else min(
                self.MAXIMUM_IDLE_DRAIN_INTERVAL,
                max(self.ACTIVE_DRAIN_INTERVAL, self.getTimeout() * 2),
            )
        )

        if nextTimeout != self.getTimeout():
            self.setTimeout(nextTimeout)
            self.startTimer()


class ProcessOutputRedirector:
    """Redirect child-process output into the application message queue."""

    TemporaryDir = QtCore.QTemporaryDir()

    @staticmethod
    def launch(msgQueue: MsgQueue, entrypoint: Callable[[], None], redirect: bool):
        """Run an entry point while forwarding output to a message queue."""
        if not callable(entrypoint):
            return

        if (
            not ProcessOutputRedirector.TemporaryDir.isValid()
            or not redirect
            or SystemRuntime.isPythonw()
        ):
            entrypoint()

            return

        temporaryFile = ProcessOutputRedirector.TemporaryDir.filePath(str(uuid.uuid4()))
        tmpFileStream = open(temporaryFile, 'w+b')

        stdoutFileno = sys.stdout.fileno()
        stderrFileno = sys.stderr.fileno()

        sys.stdout.close()
        sys.stderr.close()

        os.dup2(tmpFileStream.fileno(), stdoutFileno)
        os.dup2(tmpFileStream.fileno(), stderrFileno)

        sys.stdout = tmpFileStream
        sys.stderr = tmpFileStream

        def produceMsg():
            """Forward output until the child process ends."""
            with open(temporaryFile, 'rb') as stream:
                while True:
                    for line in iter(stream.readline, b''):
                        if line and not line.isspace():
                            try:
                                msgQueue.putMessage(line.decode('utf-8', 'replace'))
                            except (OSError, ValueError):
                                pass

                    time.sleep(MsgQueue.MSG_PRODUCE_THRESHOLD / 1000)

        threading.Thread(target=produceMsg, daemon=True).start()

        with tmpFileStream:
            entrypoint()
