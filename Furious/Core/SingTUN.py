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

"""Spawn-only sing-tun bridge with authoritative readiness and cooperative stop."""

from __future__ import annotations

from Furious.Core.MultiprocessingRuntime import (
    MultiprocessingRuntime,
    ProcessLaunchSpec,
)
from Furious.Core.ProcessOutput import ProcessOutputRedirector
from Furious.Frozenlib.PythonCompatibility import PythonCompatibility
from Furious.Interface import RuntimeExit, RuntimeExitReason, RuntimeStartError

import copy
import importlib
import json
import multiprocessing
import threading


def _nativeError(engine):
    try:
        error = engine.status.get('error', '')
    except (AttributeError, RuntimeError):
        return ''

    return error if isinstance(error, str) else ''


def _runEngine(config, control, engineFactory=None):
    """Child control remains responsive while native startup runs on its own thread."""
    engine = None
    worker = None
    complete = threading.Event()
    errors = []
    requested = False

    try:
        if engineFactory is None:
            binding = importlib.import_module('sing_tun')

            engine = binding.Engine(binding.Config(**config))
        else:
            engine = engineFactory(config)

        def initialize():
            try:
                engine.start()
            except BaseException as ex:
                errors.append(ex)
            finally:
                complete.set()

        worker = threading.Thread(target=initialize, name='sing-tun-initialize')
        worker.start()

        announced = False

        while True:
            if control.poll(0.05):
                try:
                    command = control.recv_bytes(64)
                except (EOFError, OSError):
                    command = b'stop'

                if command == b'stop':
                    requested = True

                    engine.stop()

            if not complete.is_set():
                continue

            if errors and not requested:
                raise errors[0]

            if not announced and not requested:
                if not engine.ready:
                    raise RuntimeError('sing-tun did not become ready')

                control.send_bytes(
                    json.dumps(
                        {'state': 'ready', 'device_name': engine.device_name}
                    ).encode()
                )

                announced = True

            if engine.wait(0):
                break

        worker.join()

        engine.close(5)

        try:
            control.send_bytes(b'{"state":"stopped"}')
        except (EOFError, OSError):
            pass
    except BaseException as ex:
        if isinstance(ex, ImportError):
            message = 'sing-tun package is unavailable or incompatible'
        else:
            message = str(ex) or 'sing-tun native startup or cleanup failed'

        nativeMessage = _nativeError(engine)

        if nativeMessage:
            message = 'sing-tun: ' + nativeMessage

        try:
            control.send_bytes(
                json.dumps({'state': 'failed', 'error': message}).encode()
            )
        except (OSError, EOFError):
            pass

        raise RuntimeError(message) from None
    finally:
        try:
            if engine is not None:
                try:
                    engine.stop()
                except BaseException:
                    pass

                if worker is not None:
                    worker.join(5)

                try:
                    engine.close(5)
                except BaseException:
                    # The authoritative failure was already published above.
                    # Preserve that failure if cleanup also fails; the parent
                    # retains recovery for incomplete cleanup.
                    pass
        finally:
            control.close()


def startSingTUN(output, config, control):
    """Import the Go binding only inside the spawned child."""
    ProcessOutputRedirector.launch(output, lambda: _runEngine(config, control), True)


class SingTUN(MultiprocessingRuntime):
    """Own IPC, child execution, and registered attempt-local host restoration."""

    CooperativeStopTimeout = 6

    def __init__(self, config, *, hostPlan=None, **kwargs):
        context = multiprocessing.get_context('spawn')

        self._control, self._childControl = context.Pipe()
        self._status = {'state': 'created'}
        self._hostPlan = hostPlan
        self._started = False
        self._cleanExit = False
        self._nativeWasReady = False
        self.cleanup = None
        self._configuration = copy.deepcopy(config)

        try:
            super().__init__(
                lambda output: ProcessLaunchSpec(
                    target=startSingTUN,
                    args=(output, copy.deepcopy(config), self._childControl),
                ),
                processContext=context,
                **kwargs,
            )
        except BaseException:
            self._control.close()
            self._childControl.close()

            raise

    @staticmethod
    def name():
        return 'sing-tun'

    @staticmethod
    def version():
        try:
            return PythonCompatibility.distributionVersion('sing-tun')
        except PythonCompatibility.PackageNotFoundError:
            return 'unavailable'

    def start(self):
        if self._started:
            raise RuntimeStartError('sing-tun runtimes are one-shot')

        self._started = True

        try:
            if self._hostPlan is not None:
                configuration = self._hostPlan.configuration
            else:
                configuration = self._configuration

            self._launch = ProcessLaunchSpec(
                target=startSingTUN,
                args=(self._output, copy.deepcopy(configuration), self._childControl),
            )

            if self._hostPlan is not None:
                self._hostPlan.markActivated()

            super().start()

            self._monitor.setInterval(50)
        finally:
            self._childControl.close()

    def _readStatus(self):
        try:
            for _ in range(8):
                if self._control.closed or not self._control.poll():
                    break

                status = json.loads(self._control.recv_bytes(4096))

                if not isinstance(status, dict) or status.get('state') not in (
                    'ready',
                    'failed',
                    'stopped',
                ):
                    raise ValueError()

                if status['state'] == 'ready':
                    name = status.get('device_name')

                    if (
                        not isinstance(name, str)
                        or not 1 <= len(name) <= 32
                        or not all(
                            character.isascii()
                            and (character.isalnum() or character in '_.-')
                            for character in name
                        )
                    ):
                        raise ValueError()

                    self._nativeWasReady = True

                elif status['state'] == 'failed':
                    error = status.get('error')

                    if not isinstance(error, str) or not error:
                        raise ValueError()

                if self._status.get('state') == 'failed':
                    continue

                self._status = {**self._status, **status}
                self._cleanExit = status['state'] == 'stopped'
        except EOFError:
            pass
        except (OSError, ValueError, TypeError) as ex:
            if isinstance(ex, OSError) and str(ex) != 'bad message length':
                # Windows can report a normal peer close as a broken pipe.
                return

            self._status = {
                'state': 'failed',
                'error': 'Invalid sing-tun status message',
            }

    @property
    def ready(self):
        self._readStatus()

        return self._status.get('state') == 'ready' and self.isRunning()

    @property
    def deviceName(self):
        self._readStatus()

        return self._status.get('device_name', '')

    @property
    def startupError(self):
        self._readStatus()

        return self._status.get('error', '')

    def _pollProcess(self):
        self._readStatus()

        super()._pollProcess()

    def interpretExit(self, exitcode, *, requested=False):
        self._readStatus()

        if self.startupError:
            if self._nativeWasReady:
                reason = RuntimeExitReason.Unexpected
            else:
                reason = RuntimeExitReason.StartFailure

            return RuntimeExit(exitcode, reason, message=self.startupError)

        return super().interpretExit(exitcode, requested=requested)

    def stop(self):
        if self._hostPlan is not None:
            self._hostPlan.drain()

        process = self._process

        if process is not None and process.is_alive():
            self._stopRequested = True

            try:
                self._control.send_bytes(b'stop')
            except (OSError, EOFError):
                pass

            # Native close has a five-second deadline; allow it to complete
            # before falling back to the shared exact-child escalation path.
            process.join(self.CooperativeStopTimeout)

        self._readStatus()

        errors = []

        try:
            super().stop()
        except Exception as ex:
            # Any non-exit exceptions

            errors.append(str(ex))

        # A stopped process is not proof of host restoration. Failure keeps the
        # lease retryable, even after its process handle has been released.
        if self._hostPlan is not None:
            try:
                if self._process is None or not self._process.is_alive():
                    self._hostPlan.finishCleanup(self._cleanExit or not self._started)
                else:
                    # A retained live child prevents native recovery, but host
                    # DNS snapshots can be restored independently.
                    self._hostPlan.finishDNSCleanup()
            except Exception as ex:
                # Any non-exit exceptions

                errors.append(str(ex))

        if callable(self.cleanup):
            try:
                self.cleanup()
            except Exception as ex:
                # Any non-exit exceptions

                errors.append(str(ex))

        if errors:
            raise RuntimeError('; '.join(errors))

    def dispose(self):
        super().dispose()

        self._control.close()
        self._childControl.close()
