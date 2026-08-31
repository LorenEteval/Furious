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

"""Run copied subscription preparation work in a bounded Qt thread pool."""

from __future__ import annotations

from PySide6 import QtCore

from dataclasses import dataclass

import threading
import time

__all__ = [
    'SubscriptionPreparationJob',
    'SubscriptionPreparationOutcome',
    'SubscriptionPreparationRelay',
]


@dataclass(frozen=True)
class SubscriptionPreparationOutcome:
    """Return plain worker data to the subscription manager's Qt thread."""

    jobId: int
    stage: str
    context: dict
    value: object = None
    errorType: str = ''
    error: str = ''
    cancelled: bool = False
    duration: float = 0.0
    workerThreadId: int = 0


class SubscriptionPreparationRelay(QtCore.QObject):
    """Provide one process-lifetime queued result path for all pool jobs."""

    completed = QtCore.Signal(object)


class SubscriptionPreparationJob(QtCore.QRunnable):
    """Own one cancellable plain-data preparation callable."""

    def __init__(self, jobId: int, stage: str, context: dict, work, relay):
        """Capture copied operation context and a non-Qt work callable."""
        super().__init__()

        self.jobId = jobId
        self.stage = stage
        self.context = dict(context)
        self.work = work
        self.relay = relay
        self.cancelled = threading.Event()

        self.setAutoDelete(True)

    def cancel(self):
        """Make queued/running work stop cooperatively and reject its result."""
        self.cancelled.set()

    def run(self):
        """Execute without touching QObject, widget, model, or live repository state."""
        started = time.perf_counter()
        value = None
        errorType = ''
        error = ''

        try:
            if not self.cancelled.is_set():
                value = self.work(self.cancelled.is_set)
        except Exception as ex:
            # Any non-exit exceptions

            errorType = type(ex).__name__
            error = str(ex) or errorType

        try:
            self.relay.completed.emit(
                SubscriptionPreparationOutcome(
                    self.jobId,
                    self.stage,
                    self.context,
                    value,
                    errorType,
                    error,
                    self.cancelled.is_set(),
                    time.perf_counter() - started,
                    threading.get_ident(),
                )
            )
        except RuntimeError:
            # The owning manager may already be gone after an abnormal teardown.
            pass
