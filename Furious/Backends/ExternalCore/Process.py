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

"""Launch, monitor, log, and stop a user-configured local program."""

from __future__ import annotations

from Furious.Core import CoreProcessState
from Furious.Interface import RuntimeKernel

from .Configuration import ConfigExternalCore

from pathlib import Path
from typing import BinaryIO, Optional

import os
import signal
import logging
import subprocess
import threading

__all__ = ['ExternalCoreProcess']

logger = logging.getLogger(__name__)


class ExternalCoreProcess(RuntimeKernel):
    """Manage one direct external process and its output-reader threads."""

    StartupObservationTimeout = 0.25
    ForcedShutdownTimeout = 3.0
    MaximumPendingOutput = 65536

    def __init__(self, *, exitCallback=None, msgCallback=None):
        """Initialize an idle process runtime with explicit callback ownership."""
        super().__init__(exitCallback)

        self._messageCallback = msgCallback
        self._process: Optional[subprocess.Popen] = None
        self._readerThreads: list[threading.Thread] = []
        self._watcherThread: Optional[threading.Thread] = None
        self._state = CoreProcessState.Idle
        self._lastExitCode = None
        self._shutdownTimeout = 5.0
        self._stopping = threading.Event()
        self._lock = threading.RLock()

    @staticmethod
    def name() -> str:
        """Return the user-visible runtime name."""
        return 'External Core'

    @staticmethod
    def version() -> str:
        """Return no bundled version for a user-managed executable."""
        return ''

    @property
    def process(self) -> Optional[subprocess.Popen]:
        """Return the currently owned subprocess handle."""
        with self._lock:
            return self._process

    @property
    def state(self) -> CoreProcessState:
        """Return the current process lifecycle state."""
        with self._lock:
            return self._state

    @property
    def lastExitCode(self):
        """Return the most recently observed process exit code."""
        with self._lock:
            return self._lastExitCode

    def isAlive(self) -> bool:
        """Return whether the configured external process is still running."""
        process = self.process

        return process is not None and process.poll() is None

    def _emitOutput(self, message: str):
        """Forward one decoded core-output line to the unified core log."""
        if not message or not callable(self._messageCallback):
            return

        try:
            self._messageCallback(message)
        except Exception:
            # Any non-exit exceptions

            logger.exception('external core output callback failed')

    def _readStream(self, stream: BinaryIO, label: str):
        """Drain one child pipe until EOF without retaining process output."""
        pending = b''

        try:
            while True:
                chunk = os.read(stream.fileno(), 4096)

                if not chunk:
                    break

                pending += chunk
                lines = pending.split(b'\n')
                pending = lines.pop()

                for line in lines:
                    message = line.decode('utf-8', 'replace').rstrip('\r')

                    if not message:
                        continue

                    self._emitOutput(
                        message if label == 'stdout' else f'[stderr] {message}'
                    )

                if len(pending) >= self.MaximumPendingOutput:
                    message = pending.decode('utf-8', 'replace')

                    self._emitOutput(
                        message if label == 'stdout' else f'[stderr] {message}'
                    )
                    pending = b''

            if pending:
                message = pending.decode('utf-8', 'replace').rstrip('\r')

                if not message:
                    return

                self._emitOutput(
                    message if label == 'stdout' else f'[stderr] {message}'
                )
        except (OSError, ValueError) as ex:
            if not self._stopping.is_set():
                logger.error(f'failed to read external core {label}: {ex}')
        finally:
            try:
                stream.close()
            except (OSError, ValueError):
                pass

    def _startReaders(self, process: subprocess.Popen):
        """Start one bounded-lifetime reader for each captured output pipe."""
        readers = []

        for stream, label in (
            (process.stdout, 'stdout'),
            (process.stderr, 'stderr'),
        ):
            if stream is None:
                continue

            thread = threading.Thread(
                target=self._readStream,
                args=(stream, label),
                daemon=True,
            )
            thread.start()

            readers.append(thread)

        with self._lock:
            self._readerThreads = readers

    def _joinReaders(self, process: Optional[subprocess.Popen] = None):
        """Finish pipe readers, closing inherited pipes if descendants retain them."""
        with self._lock:
            readers = tuple(self._readerThreads)

            self._readerThreads.clear()

        current = threading.current_thread()

        for thread in readers:
            if thread is not current:
                thread.join(0.5)

        pending = tuple(thread for thread in readers if thread.is_alive())

        if pending and process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is None:
                    continue

                try:
                    stream.close()
                except (OSError, ValueError):
                    pass

            for thread in pending:
                if thread is not current:
                    thread.join(self.ForcedShutdownTimeout)

    def _watch(self, process: subprocess.Popen):
        """Reap the process and report an unexpected exit exactly once."""
        exitCode = process.wait()

        self._joinReaders(process)

        with self._lock:
            if self._process is not process:
                return

            stopping = self._stopping.is_set()

            self._lastExitCode = exitCode
            self._state = (
                CoreProcessState.Exited if stopping else CoreProcessState.Failed
            )

        if stopping:
            logger.info(f'external core process exited with code {exitCode}')

            return

        logger.error(f'external core process exited unexpectedly with code {exitCode}')

        self.callExitCallback(exitCode)

    def _startWatcher(self, process: subprocess.Popen):
        """Start the single process-reaping watcher thread."""
        watcher = threading.Thread(target=self._watch, args=(process,), daemon=True)

        with self._lock:
            self._watcherThread = watcher

        watcher.start()

    @staticmethod
    def _creationOptions() -> dict:
        """Return process-group options suitable for the current platform."""
        if os.name == 'nt':
            return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}

        return {'start_new_session': True}

    def start(self, config: ConfigExternalCore, **kwargs) -> bool:
        """Validate and directly launch the configured executable."""
        if not isinstance(config, ConfigExternalCore):
            self.setStartError('Invalid External Core configuration')

            return False

        if self.process is not None:
            if self.isAlive():
                logger.warning(
                    'External Core is already running. Stop it before restart'
                )

            self.stop()

        self.clearStartError()
        self._stopping.clear()

        with self._lock:
            self._state = CoreProcessState.Starting
            self._lastExitCode = None

        errors = config.validateProcess()

        if errors:
            self.setStartError(errors[0])

            logger.error(f'external core configuration is invalid: {"; ".join(errors)}')

            with self._lock:
                self._state = CoreProcessState.Failed

            return False

        command = config.command()
        cwd = str(config.get('workingDirectory', '')).strip()

        if not cwd:
            cwd = str(Path(command[0]).parent)

        environment = config.processEnvironment()

        self._shutdownTimeout = config.shutdownTimeout()

        logger.info(f'starting external core executable {command[0]!r}')
        logger.info(f'external core working directory: {cwd!r}')
        logger.info('external core arguments and environment are not logged')

        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                shell=False,
                **self._creationOptions(),
            )
        except FileNotFoundError as ex:
            self.setStartError('Executable does not exist')

            logger.error(f'failed to launch external core: {ex}')
        except PermissionError as ex:
            self.setStartError('Permission denied while launching external core')

            logger.error(f'failed to launch external core: {ex}')
        except OSError as ex:
            self.setStartError('Failed to launch external core')

            logger.error(f'failed to launch external core: {ex}')
        else:
            with self._lock:
                self._process = process

            self._startReaders(process)

            try:
                exitCode = process.wait(timeout=self.StartupObservationTimeout)
            except subprocess.TimeoutExpired:
                with self._lock:
                    self._state = CoreProcessState.Running

                logger.info(f'external core process started with PID {process.pid}')

                self._startWatcher(process)

                return True

            self._joinReaders(process)
            self.setStartError('External core exited during startup')

            with self._lock:
                self._lastExitCode = exitCode
                self._state = CoreProcessState.Failed

            logger.error(
                f'external core process exited during startup with code {exitCode}'
            )

            return False

        with self._lock:
            self._state = CoreProcessState.Failed

        return False

    @staticmethod
    def _waitForExit(process: subprocess.Popen, timeout: float) -> bool:
        """Wait for *process* and return whether it exited within *timeout*."""
        try:
            process.wait(timeout=max(0.1, timeout))

            return True
        except subprocess.TimeoutExpired:
            return False

    @staticmethod
    def _windowsTaskkill(process: subprocess.Popen, force: bool):
        """Ask Windows to terminate the process tree without using a shell."""
        command = ['taskkill', '/PID', str(process.pid), '/T']

        if force:
            command.append('/F')

        try:
            subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
            )
        except OSError as ex:
            logger.warning(f'could not invoke Windows process-tree shutdown: {ex}')

    def _requestStop(self, process: subprocess.Popen):
        """Request graceful shutdown for the owned process group."""
        if os.name == 'nt':
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            except OSError as ex:
                logger.warning(f'could not signal external core process group: {ex}')

            return

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError as ex:
            if not isinstance(ex, ProcessLookupError):
                logger.warning(f'could not signal external core process group: {ex}')

    def _terminate(self, process: subprocess.Popen):
        """Escalate shutdown while including descendants where practical."""
        if os.name == 'nt':
            self._windowsTaskkill(process, force=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError as ex:
                if not isinstance(ex, ProcessLookupError):
                    logger.warning(f'could not terminate external core process: {ex}')

    def _kill(self, process: subprocess.Popen):
        """Force-stop the process tree and fall back to the direct child."""
        try:
            if os.name == 'nt':
                self._windowsTaskkill(process, force=True)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError) as ex:
            logger.warning(f'failed to kill external core process tree: {ex}')

        if process.poll() is None:
            try:
                process.kill()
            except OSError as ex:
                logger.error(f'failed to kill external core process: {ex}')

    def stop(self):
        """Stop, reap, and release the external process and reader threads."""
        process = self.process

        if process is None:
            return

        self._stopping.set()

        with self._lock:
            self._state = CoreProcessState.Stopping

        if process.poll() is None:
            logger.info(f'requesting external core shutdown for PID {process.pid}')

            self._requestStop(process)

            firstWait = self._shutdownTimeout / 2

            if not self._waitForExit(process, firstWait):
                logger.warning('external core did not stop gracefully; terminating it')

                self._terminate(process)

                if not self._waitForExit(process, self._shutdownTimeout - firstWait):
                    logger.warning('external core did not terminate; killing it')

                    self._kill(process)
                    self._waitForExit(process, self.ForcedShutdownTimeout)

        exitCode = process.poll()

        if exitCode is None:
            logger.error('external core process could not be reaped')
        else:
            logger.info(f'external core process stopped with code {exitCode}')

        self._joinReaders(process)

        with self._lock:
            watcher = self._watcherThread

            self._watcherThread = None

        if watcher is not None and watcher is not threading.current_thread():
            watcher.join(self.ForcedShutdownTimeout)

        with self._lock:
            self._lastExitCode = exitCode
            self._state = CoreProcessState.Exited
            self._process = None

    def dispose(self):
        """Release all process, thread, and callback ownership."""
        self.stop()
        self._messageCallback = None
        self._exitCallback = None
