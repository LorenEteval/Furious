# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Interface import *
from Furious.Utility import *

from PySide6 import QtCore

from abc import ABC
from typing import Callable

import os
import sys
import time
import uuid
import logging
import threading
import multiprocessing

__all__ = ['CoreProcess', 'StdoutRedirectHelper']

logger = logging.getLogger(__name__)


class CoreProcess(CoreFactory, ABC):
    MSG_PRODUCE_THRESHOLD = 250

    def __init__(self, **kwargs):
        exitCallback = kwargs.pop('exitCallback', None)

        super().__init__(exitCallback)

        self._process = None
        self._msgQueue = multiprocessing.Queue()
        self._msgCallback = kwargs.pop('msgCallback', None)

        @QtCore.Slot()
        def handleMsgTimemout():
            msg = self.getMsgNoWait()

            if msg and not msg.isspace():
                if callable(self._msgCallback):
                    self._msgCallback(msg)

        self._msgTimer = QtCore.QTimer()
        self._msgTimer.timeout.connect(handleMsgTimemout)

        @QtCore.Slot()
        def handleDaemonTimemout():
            self.checkIsRunning()

        self._daemonTimer = QtCore.QTimer()
        self._daemonTimer.timeout.connect(handleDaemonTimemout)

    @property
    def msgQueue(self) -> multiprocessing.Queue:
        return self._msgQueue

    def registerMsgCallback(self, msgCallback) -> CoreProcess:
        self._msgCallback = msgCallback

        return self

    def isRunning(self) -> bool:
        if isinstance(self._process, multiprocessing.Process):
            return self._process.is_alive()
        else:
            return False

    def checkIsRunning(self) -> bool:
        if isinstance(self._process, multiprocessing.Process):
            if self._process.is_alive():
                return True
            else:
                logger.error(
                    f'{self.name()} stopped unexpectedly with exitcode {self._process.exitcode}'
                )

                self._msgTimer.stop()
                self._daemonTimer.stop()

                if callable(self._exitCallback):
                    self._exitCallback(self, self._process.exitcode)

                # Reset internal process
                self._process = None

                return False
        else:
            return False

    def start(self, **kwargs) -> bool:
        daemon = kwargs.pop('daemon', True)
        waitCore = kwargs.pop('waitCore', True)
        waitTime = kwargs.pop('waitTime', 2500)

        self._process = multiprocessing.Process(**kwargs, daemon=daemon)
        self._process.start()

        logger.info(f'{self.name()} {self.version()} started')

        self._msgTimer.start(self.MSG_PRODUCE_THRESHOLD)

        if waitCore:
            # Wait for the core to start up completely
            PySide6LegacyEventLoopWait(waitTime)

        if self.checkIsRunning():
            if AppSettings.isStateON_('PowerSaveMode'):
                # Power optimization
                logger.info(f'no core daemon for {self.name()} in power save mode')

                self._daemonTimer.stop()
            else:
                # Start core daemon
                self._daemonTimer.start(CORE_CHECK_ALIVE_INTERVAL)

            return True
        else:
            return False

    def stop(self):
        if self.isRunning():
            self._msgTimer.stop()
            self._daemonTimer.stop()

            self._process.terminate()
            self._process.join()

            logger.info(
                f'{self.name()} terminated with exitcode {self._process.exitcode}'
            )

    def getMsgNoWait(self) -> str:
        try:
            return self._msgQueue.get_nowait()
        except Exception:
            # Any non-exit exceptions

            return ''


class StdoutRedirectHelper:
    TemporaryDir = QtCore.QTemporaryDir()

    @staticmethod
    def launch(
        msgQueue: multiprocessing.Queue, entrypoint: Callable[[], None], redirect: bool
    ):
        if not callable(entrypoint):
            return

        if (
            not StdoutRedirectHelper.TemporaryDir.isValid()
            or not redirect
            # pythonw.exe
            or isPythonw()
        ):
            # Call entrypoint directly
            entrypoint()

            return

        temporaryFile = StdoutRedirectHelper.TemporaryDir.filePath(str(uuid.uuid4()))
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

                    time.sleep(CoreProcess.MSG_PRODUCE_THRESHOLD / 1000)

        msgThread = threading.Thread(target=produceMsg, daemon=True)
        msgThread.start()

        with tmpFileStream:
            entrypoint()
