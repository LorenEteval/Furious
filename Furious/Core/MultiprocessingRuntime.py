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

"""Own one multiprocessing-backed runtime and publish one terminal event."""

from __future__ import annotations

from Furious.Frozenlib import CORE_CHECK_ALIVE_INTERVAL
from Furious.Interface import (
    CoreRuntime,
    RuntimeExit,
    RuntimeExitReason,
    RuntimeStartError,
    RuntimeState,
)
from Furious.Qt.Signals import connectWeakly

from .ProcessOutput import MsgQueue

from PySide6 import QtCore

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Tuple

import logging
import multiprocessing

__all__ = ['MultiprocessingRuntime', 'ProcessLaunchSpec']

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessLaunchSpec:
    """Describe only OS-process construction, never readiness policy."""

    target: Callable
    args: Tuple[Any, ...] = field(default_factory=tuple)
    processOptions: Mapping[str, Any] = field(default_factory=dict)
    daemon: bool = True

    def __post_init__(self):
        """Freeze normalized argument and option containers."""
        if not callable(self.target):
            raise TypeError('process launch target must be callable')

        object.__setattr__(self, 'args', tuple(self.args))
        object.__setattr__(self, 'processOptions', dict(self.processOptions))

    def processKeywordArguments(self) -> dict:
        """Return multiprocessing.Process constructor arguments."""
        return {
            **dict(self.processOptions),
            'target': self.target,
            'args': self.args,
            'daemon': self.daemon,
        }


class MultiprocessingRuntime(CoreRuntime):
    """Own a child process, output queue, and one internal exit monitor."""

    StopJoinTimeout = 3

    def __init__(self, launchFactory, *, exitCallback=None, msgCallback=None):
        """Prepare an immutable launch specification around an owned queue."""
        super().__init__(exitCallback)

        self._process = None
        self._lastExit = None
        self._stopRequested = False
        self._exitPublished = False
        self._output = MsgQueue(msgCallback=msgCallback)

        try:
            launch = launchFactory(self._output)

            if not isinstance(launch, ProcessLaunchSpec):
                raise TypeError('launch factory must return ProcessLaunchSpec')
        except BaseException:
            # Construction has not transferred this resource to a service owner.
            self._output.dispose()

            raise

        self._launch = launch
        self._monitor = QtCore.QTimer()
        self._monitorConnection = connectWeakly(
            self._monitor.timeout,
            self,
            '_pollProcess',
        )

    @property
    def process(self):
        """Return the owned multiprocessing handle for diagnostics."""
        return self._process

    @property
    def lastExit(self):
        """Return the terminal event observed for the latest execution."""
        return self._lastExit

    @property
    def lastExitCode(self):
        """Return the latest raw code for compatibility diagnostics."""
        return self._lastExit.code if self._lastExit is not None else None

    def isRunning(self) -> bool:
        """Passively inspect the child without consuming its exit."""
        process = self._process

        return process is not None and process.is_alive()

    def start(self):
        """Spawn execution resources or raise a structured startup failure."""
        if self.state is RuntimeState.Disposed:
            raise RuntimeStartError('Runtime has already been disposed')

        if self.isRunning():
            raise RuntimeStartError('Runtime is already running')

        if not self._closeProcess():
            raise RuntimeStartError('Previous runtime handle could not be closed')

        self._stopRequested = False
        self._exitPublished = False
        self._lastExit = None

        self.setState(RuntimeState.Starting)

        try:
            process = multiprocessing.Process(**self._launch.processKeywordArguments())

            self._process = process

            process.start()
        except Exception as ex:
            # Any non-exit exceptions

            self.setState(RuntimeState.Failed)
            self._closeProcess()

            logger.error(f'{self.name()} start failed: {ex}')

            raise RuntimeStartError('Failed to start core', details=str(ex)) from ex

        self._output.setTimeout(MsgQueue.ACTIVE_DRAIN_INTERVAL)
        self._output.startTimer()
        self._monitor.start(CORE_CHECK_ALIVE_INTERVAL)

        if not process.is_alive():
            event = self._consumeExit()

            raise RuntimeStartError.fromExit(event)

        self.setState(RuntimeState.Alive)

        logger.info(f'{self.name()} {self.version()} started')

    def _consumeExit(self) -> RuntimeExit:
        """Reap and interpret one transition exactly once."""
        if self._lastExit is not None:
            return self._lastExit

        process = self._process
        code = process.exitcode if process is not None else None
        event = self.interpretExit(code, requested=self._stopRequested)

        self._lastExit = event
        self.setState(
            RuntimeState.Exited if not event.unexpected else RuntimeState.Failed
        )
        self._monitor.stop()
        self._output.stopTimer()
        self._closeProcess()

        return event

    def _pollProcess(self):
        """Detect a terminal transition without exposing polling to owners."""
        if self._process is None or self._process.is_alive():
            return

        event = self._consumeExit()

        if self._exitPublished:
            return

        self._exitPublished = True

        level = logger.error if event.unexpected else logger.info

        level(
            f'{self.name()} exited with code {event.code}; '
            f'reason={event.reason.value}'
        )

        self.publishExit(event)

    def _closeProcess(self):
        """Release a handle only after close succeeds; keep failures retryable."""
        process = self._process

        if process is None:
            return True

        try:
            process.join(0)
        except (AssertionError, OSError, ValueError):
            pass

        try:
            process.close()
        except (OSError, ValueError) as ex:
            logger.error(f'{self.name()} process handle could not be closed: {ex}')

            return False

        self._process = None

        return True

    def stop(self):
        """Idempotently terminate execution without disposing this object."""
        self._stopRequested = True

        self._monitor.stop()
        self._output.stopTimer()

        process = self._process

        if process is None:
            if self.state not in (RuntimeState.Created, RuntimeState.Disposed):
                self.setState(RuntimeState.Exited)

            return

        self.setState(RuntimeState.Stopping)

        if process.is_alive():
            process.terminate()
            process.join(self.StopJoinTimeout)

            if process.is_alive():
                logger.warning(
                    f'{self.name()} did not terminate in '
                    f'{self.StopJoinTimeout}s; killing it'
                )

                process.kill()
                process.join(self.StopJoinTimeout)

        if process.is_alive():
            raise RuntimeError(f'{self.name()} process did not stop after escalation')

        event = self._consumeExit()

        if not self._closeProcess():
            raise RuntimeError(f'{self.name()} process handle could not be closed')

        logger.info(f'{self.name()} stopped with exitcode {event.code}')

    def dispose(self):
        """Idempotently release process, timer, queue, and event ownership."""
        if self.state is RuntimeState.Disposed:
            return

        self.stop()

        if self._monitorConnection is not None:
            try:
                QtCore.QObject.disconnect(self._monitorConnection)
            except (RuntimeError, TypeError):
                pass

            self._monitorConnection = None

        self._monitor.deleteLater()
        self._output.dispose()

        super().dispose()
