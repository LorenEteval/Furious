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

"""Measure the checked-out log manager and compare saved JSON timing reports."""

from __future__ import annotations

from Furious.Service.LogManager import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)

from PySide6 import QtCore

from tests.support import application, processQtEvents

from contextlib import contextmanager
from pathlib import Path

import argparse
import json
import math
import platform
import time

MEASUREMENTS = (
    'steady_append_ms',
    'core_rollover_us',
    'category_snapshot_us',
    'global_snapshot_us',
    'retention_heavy_ms',
)


def validateReport(report):
    """Reject incomparable workloads and invalid timing values before division."""
    if (
        not isinstance(report, dict)
        or type(report.get('schema')) is not int
        or report['schema'] != 1
    ):
        raise ValueError('expected a log-manager benchmark report with schema 1')

    entries = report.get('entries')

    if type(entries) is not int or entries < 10:
        raise ValueError('report entries must be an integer of at least 10')

    measurements = report.get('measurements')

    if not isinstance(measurements, dict) or set(measurements) != set(MEASUREMENTS):
        raise ValueError('report measurement names do not match this workload')

    for name, value in measurements.items():
        if type(value) not in (int, float) or value <= 0 or not math.isfinite(value):
            raise ValueError(f'{name} must be a positive finite timing')

    return report


def compareReports(current, baseline):
    """Return informational current/baseline ratios for identical workloads."""
    validateReport(current)
    validateReport(baseline)

    if current['entries'] != baseline['entries']:
        raise ValueError('baseline entries must match --entries')

    return {
        name: current['measurements'][name] / baseline['measurements'][name]
        for name in MEASUREMENTS
    }


@contextmanager
def _manager(**options):
    """Release the exact benchmark QObject and queued cleanup between workloads."""
    manager = LogManager(**options)

    try:
        yield manager
    finally:
        manager.deleteLater()
        processQtEvents()


def run(entries=50_000):
    """Measure five fixed workloads using only the current implementation."""
    if type(entries) is not int or entries < 10:
        raise ValueError('entries must be an integer of at least 10')

    application()
    measurements = {}

    with _manager(maximumEntries=entries, autoClearEnabled=False) as manager:
        started = time.perf_counter_ns()

        for index in range(entries):
            manager.append(str(index), APPLICATION_LOG_CATEGORY)

        measurements['steady_append_ms'] = (time.perf_counter_ns() - started) / 1e6

    threshold = entries * 2 // 5

    with _manager(maximumEntries=entries, autoClearMaximumEntries=threshold) as manager:
        for index in range(threshold):
            manager.append(str(index), CORE_LOG_CATEGORY)
        for index in range(threshold):
            manager.append(str(index), TUN2SOCKS_LOG_CATEGORY)

        started = time.perf_counter_ns()
        manager.append('trigger', CORE_LOG_CATEGORY)
        measurements['core_rollover_us'] = (time.perf_counter_ns() - started) / 1e3

    with _manager(maximumEntries=entries, autoClearEnabled=False) as manager:
        for index in range(entries * 3 // 5):
            manager.append(
                str(index),
                CORE_LOG_CATEGORY if index % 5 == 0 else APPLICATION_LOG_CATEGORY,
            )

        started = time.perf_counter_ns()
        manager.snapshot(CORE_LOG_CATEGORY)
        measurements['category_snapshot_us'] = (time.perf_counter_ns() - started) / 1e3

        started = time.perf_counter_ns()
        manager.snapshot()
        measurements['global_snapshot_us'] = (time.perf_counter_ns() - started) / 1e3

    with _manager(
        maximumEntries=max(1, entries // 50), autoClearEnabled=False
    ) as manager:
        started = time.perf_counter_ns()

        for index in range(entries):
            manager.append(str(index), APPLICATION_LOG_CATEGORY)

        measurements['retention_heavy_ms'] = (time.perf_counter_ns() - started) / 1e6

    return validateReport(
        {
            'schema': 1,
            'entries': entries,
            'environment': {
                'python': platform.python_version(),
                'platform': platform.platform(),
                'qt': QtCore.qVersion(),
            },
            'measurements': measurements,
        }
    )


def main(argv=None):
    """Write a current report, optionally comparing a data-only baseline file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entries', type=int, default=50_000)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--baseline', type=Path)
    arguments = parser.parse_args(argv)

    if arguments.entries < 10:
        parser.error('--entries must be at least 10')

    baseline = None

    if arguments.baseline is not None:
        try:
            baseline = validateReport(
                json.loads(arguments.baseline.read_text(encoding='utf-8'))
            )
            if baseline['entries'] != arguments.entries:
                raise ValueError('baseline entries must match --entries')
        except (OSError, ValueError) as error:
            parser.error(str(error))

    report = run(arguments.entries)

    if baseline is not None:
        report['comparison'] = {
            'baseline': {
                key: baseline[key]
                for key in ('schema', 'entries', 'environment', 'measurements')
                if key in baseline
            },
            'ratios': compareReports(report, baseline),
        }

    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)

    if arguments.output is not None:
        arguments.output.write_text(serialized + '\n', encoding='utf-8')

    print(serialized)


if __name__ == '__main__':
    main()
