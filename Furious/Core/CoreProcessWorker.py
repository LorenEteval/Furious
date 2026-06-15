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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *

from PySide6 import QtCore

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Tuple, Union

import os
import sys
import time
import uuid
import logging
import threading
import multiprocessing
import multiprocessing.queues

__all__ = [
    'MsgQueue',
    'CoreLaunchSpec',
    'CoreProcessState',
    'CoreProcessMonitor',
    'CoreProcessWorker',
    'ProcessOutputRedirector',
]

logger = logging.getLogger(__name__)


class CoreProcessState(Enum):
    Idle = 'idle'
    Starting = 'starting'
    Running = 'running'
    Stopping = 'stopping'
    Exited = 'exited'
    Failed = 'failed'


@dataclass
class CoreLaunchSpec:
    target: Callable
    args: Tuple[Any, ...] = field(default_factory=tuple)
    processKwargs: Dict[str, Any] = field(default_factory=dict)
    daemon: bool = True
    waitCore: bool = True
    waitTime: int = 2500

    def __post_init__(self):
        self.args = tuple(self.args)
        self.processKwargs = dict(self.processKwargs)

        self.daemon = self.processKwargs.pop('daemon', self.daemon)
        self.waitCore = self.processKwargs.pop('waitCore', self.waitCore)
        self.waitTime = self.processKwargs.pop('waitTime', self.waitTime)

    @classmethod
    def fromProcessKwargs(cls, **kwargs):
        daemon = kwargs.pop('daemon', True)
        waitCore = kwargs.pop('waitCore', True)
        waitTime = kwargs.pop('waitTime', 2500)
        target = kwargs.pop('target', None)
        args = kwargs.pop('args', tuple())

        return cls(
            target=target,
            args=args,
            processKwargs=kwargs,
            daemon=daemon,
            waitCore=waitCore,
            waitTime=waitTime,
        )

    def toProcessKwargs(self):
        kwargs = dict(self.processKwargs)
        kwargs.update(
            {
                'target': self.target,
                'args': tuple(self.args),
            }
        )

        return kwargs


class MsgQueue(multiprocessing.queues.Queue):
    MSG_PRODUCE_THRESHOLD = 1024
    OPTIMIZER_MIN_FREQ = 2
    OPTIMIZER_MAX_FREQ = 256

    def __init__(self, **kwargs):
        msgCallback = kwargs.pop('msgCallback', None)
        backgroundOptimizer = kwargs.pop('backgroundOptimizer', None)

        super().__init__(**kwargs, ctx=multiprocessing.get_context())

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.processMsg)
        self.timeout = MsgQueue.MSG_PRODUCE_THRESHOLD
        self.callback = msgCallback
        self.backgroundOptimizer = backgroundOptimizer

    def getNoWait(self) -> str:
        try:
            return self.get_nowait()
        except Exception:
            # Any non-exit exceptions

            return ''

    def getTimeout(self) -> int:
        return self.timeout

    def setTimeout(self, timeout: int):
        self.timeout = timeout

    def startTimer(self):
        self.timer.start(self.getTimeout())

    def stopTimer(self):
        self.timer.stop()

    @property
    def optimizer(self):
        try:
            return self.backgroundOptimizer()
        except Exception:
            # Any non-exit exceptions

            return None

    def processMsg(self):
        msg = self.getNoWait()

        if not callable(self.callback):
            # Nothing to do
            return

        if msg and not msg.isspace():
            # Call message callback
            self.callback(msg)

            if self.optimizer is not None and self.optimizer.isVisible():
                # Logger window is visible: maximum loading speed for user

                # 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 2, 2, ...
                # For timeout value 2 Furious can handle at about 500 messages per second
                self.setTimeout(
                    max(MsgQueue.OPTIMIZER_MIN_FREQ, self.getTimeout() // 2)
                )
                self.startTimer()
            else:
                # Logger window does not exist or is not visible: low speed in background
                # to avoid consuming too much CPU resources

                # 1024, 512, 256, 256, 256, ...
                # For timeout value 256 Furious can handle at about 4 messages per second
                self.setTimeout(
                    max(MsgQueue.OPTIMIZER_MAX_FREQ, self.getTimeout() // 2)
                )
                self.startTimer()
        else:
            # Reset timeout value
            self.setTimeout(MsgQueue.MSG_PRODUCE_THRESHOLD)
            self.startTimer()


class CoreProcessMonitor(CoreProcessFactory, ABC):
    StopJoinTimeout = 3

    def __init__(self, **kwargs):
        exitCallback = kwargs.pop('exitCallback', None)

        super().__init__(exitCallback)

        self._process = None
        self._state = CoreProcessState.Idle
        self._lastExitCode = None

        self._daemon = QtCore.QTimer()
        self._daemon.timeout.connect(self.queryIsAlive)

    @property
    def process(self) -> Union[multiprocessing.Process, None]:
        return self._process

    @process.setter
    def process(self, process: Union[multiprocessing.Process, None]):
        self._process = process

    @property
    def daemon(self) -> QtCore.QTimer:
        return self._daemon

    @property
    def state(self) -> CoreProcessState:
        return self._state

    def setState(self, state: CoreProcessState):
        self._state = state

    @property
    def lastExitCode(self):
        return self._lastExitCode

    def setLastExitCode(self, exitCode):
        self._lastExitCode = exitCode

    def isAlive(self) -> bool:
        if isinstance(self.process, multiprocessing.Process):
            return self.process.is_alive()
        else:
            return False

    def queryIsAlive(self):
        if isinstance(self.process, multiprocessing.Process):
            if self.process.is_alive():
                return True
            else:
                self.handleInternalProcessStopped()

                return False
        else:
            return False

    def handleInternalProcessStopped(self, *args, **kwargs):
        raise NotImplementedError

    def closeProcess(self):
        if isinstance(self.process, multiprocessing.Process):
            try:
                self.process.close()
            except Exception:
                # close() can fail if the process handle is still considered active.
                pass

        self.process = None


class CoreProcessWorker(CoreProcessMonitor, ABC):
    def __init__(self, **kwargs):
        msgCallback = kwargs.pop('msgCallback', None)
        # Optimizer is AppLoggerWindow.Core window
        backgroundOptimizer = kwargs.pop('backgroundOptimizer', AppLoggerWindow.Core)

        super().__init__(**kwargs)

        self.msgQueue = MsgQueue(
            msgCallback=msgCallback, backgroundOptimizer=backgroundOptimizer
        )

    def handleInternalProcessStopped(self):
        exitcode = self.process.exitcode

        logger.error(f'{self.name()} stopped unexpectedly with exitcode {exitcode}')

        self.msgQueue.stopTimer()
        self.daemon.stop()

        self.setLastExitCode(exitcode)
        self.setState(CoreProcessState.Failed)
        self.callExitCallback(exitcode)

        # Reset internal process
        self.closeProcess()

    def start(self, **kwargs) -> bool:
        return self.startWithSpec(CoreLaunchSpec.fromProcessKwargs(**kwargs))

    def startWithSpec(self, launchSpec: CoreLaunchSpec) -> bool:
        if not isinstance(launchSpec, CoreLaunchSpec):
            logger.error(f'invalid launch spec for {self.name()}: {launchSpec}')

            self.setState(CoreProcessState.Failed)

            return False

        if not callable(launchSpec.target):
            logger.error(
                f'invalid launch target for {self.name()}: {launchSpec.target}'
            )

            self.setState(CoreProcessState.Failed)

            return False

        if self.isAlive():
            logger.warning(f'{self.name()} is already running. Stop it before restart')

            self.stop()

        self.setState(CoreProcessState.Starting)

        try:
            self.process = multiprocessing.Process(
                **launchSpec.toProcessKwargs(), daemon=launchSpec.daemon
            )
            self.process.start()
        except Exception as ex:
            logger.error(f'{self.name()} start failed: {ex}')

            self.setState(CoreProcessState.Failed)
            self.closeProcess()

            return False

        logger.info(f'{self.name()} {self.version()} started')

        self.msgQueue.setTimeout(MsgQueue.MSG_PRODUCE_THRESHOLD)
        self.msgQueue.startTimer()

        if launchSpec.waitCore:
            # Wait for the core to start up completely
            PySide6Legacy.eventLoopWait(launchSpec.waitTime)

        if self.queryIsAlive():
            self.setState(CoreProcessState.Running)

            # Start core daemon
            self.daemon.start(CORE_CHECK_ALIVE_INTERVAL)

            return True
        else:
            return False

    def stop(self):
        self.msgQueue.stopTimer()
        self.daemon.stop()

        if not isinstance(self.process, multiprocessing.Process):
            return

        self.setState(CoreProcessState.Stopping)

        if self.process.is_alive():
            self.process.terminate()
            self.process.join(CoreProcessMonitor.StopJoinTimeout)

            if self.process.is_alive():
                logger.warning(
                    f'{self.name()} did not terminate in '
                    f'{CoreProcessMonitor.StopJoinTimeout}s. Kill it'
                )

                self.process.kill()
                self.process.join(CoreProcessMonitor.StopJoinTimeout)

        exitcode = self.process.exitcode

        logger.info(f'{self.name()} terminated with exitcode {exitcode}')

        self.setLastExitCode(exitcode)
        self.setState(CoreProcessState.Exited)
        self.closeProcess()


class ProcessOutputRedirector:
    TemporaryDir = QtCore.QTemporaryDir()

    @staticmethod
    def launch(
        msgQueue: multiprocessing.Queue, entrypoint: Callable[[], None], redirect: bool
    ):
        if not callable(entrypoint):
            return

        if (
            not ProcessOutputRedirector.TemporaryDir.isValid()
            or not redirect
            # pythonw.exe
            or SystemRuntime.isPythonw()
        ):
            # Call entrypoint directly
            entrypoint()

            return

        temporaryFile = ProcessOutputRedirector.TemporaryDir.filePath(str(uuid.uuid4()))
        tmpFileStream = open(temporaryFile, 'w+b')
        stdoutFileno_ = sys.stdout.fileno()
        stderrFileno_ = sys.stderr.fileno()

        sys.stdout.close()
        sys.stderr.close()

        # Redirect
        os.dup2(tmpFileStream.fileno(), stdoutFileno_)
        os.dup2(tmpFileStream.fileno(), stderrFileno_)

        sys.stdout = tmpFileStream
        sys.stderr = tmpFileStream

        def produceMsg():
            with open(temporaryFile, 'rb') as file:
                while True:
                    for line in iter(file.readline, b''):
                        if line and not line.isspace():
                            try:
                                msgQueue.put_nowait(line.decode('utf-8', 'replace'))
                            except Exception:
                                # Any non-exit exceptions

                                pass

                    time.sleep(MsgQueue.MSG_PRODUCE_THRESHOLD / 1000)

        msgThread = threading.Thread(target=produceMsg, daemon=True)
        msgThread.start()

        with tmpFileStream:
            entrypoint()
