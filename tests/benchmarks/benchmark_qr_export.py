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

"""Benchmark real QR rendering and synchronous/asynchronous QR windows."""

from __future__ import annotations

import os
import sys

from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

repositoryRoot = Path(__file__).resolve().parents[2]

if str(repositoryRoot) not in sys.path:
    sys.path.insert(0, str(repositoryRoot))

from Furious.Backends.Xray import XrayPlugin
from Furious.Plugins import PluginRegistry, profileFromAny

from PySide6 import QtCore

from tests.support import application, collectAtBoundary, isolatedSettings

from importlib import import_module
from unittest import mock

import argparse
import time

qrCodeModule = import_module('Furious.Window.QRCodeWindow')


def profiles(count: int, registry: PluginRegistry):
    """Return independent SOCKS profiles handled by the real exporter."""
    baseProfile = profileFromAny(
        'socks://benchmark.example:1080#Benchmark',
        registry=registry,
    )
    result = []

    for index in range(count):
        profile = baseProfile.deepcopy()
        profile.metadata.displayName = f'Benchmark {index + 1}'
        result.append(profile)

    return result


def pumpUntil(predicate, timeout: float):
    """Pump the real Qt event loop until completion or a bounded timeout."""
    app = application()
    deadline = time.perf_counter() + timeout

    while time.perf_counter() < deadline:
        app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)

        if predicate():
            return

        QtCore.QThread.msleep(1)

    raise TimeoutError(f'QR benchmark exceeded {timeout:g} seconds')


class TrackingQRCodeWindow(qrCodeModule.QRCodeWindow):
    """Record first native presentation milestones without changing behavior."""

    shownAt = None
    paintedAt = None
    finishedAt = None

    def showEvent(self, event):
        """Record the first result-window show event."""
        if type(self).shownAt is None:
            type(self).shownAt = time.perf_counter()

        super().showEvent(event)

    def paintEvent(self, event):
        """Record the first result-window paint event."""
        if type(self).paintedAt is None:
            type(self).paintedAt = time.perf_counter()

        super().paintEvent(event)

    def finishExport(self):
        """Record completion of the window-owned incremental export."""
        wasExporting = self.isExporting()

        super().finishExport()

        if wasExporting and not self.isExporting():
            type(self).finishedAt = time.perf_counter()


def resetMilestones():
    """Reset class-level measurements before an independent run."""
    TrackingQRCodeWindow.shownAt = None
    TrackingQRCodeWindow.paintedAt = None
    TrackingQRCodeWindow.finishedAt = None


def elapsed(started: float, milestone: float | None):
    """Return one relative duration, preserving an absent milestone as None."""
    return None if milestone is None else milestone - started


def benchmarkImages(count: int):
    """Render representative payloads without constructing Qt windows."""
    started = time.perf_counter()
    lastImage = None

    for index in range(count):
        payload = (
            f'socks://benchmark-user:benchmark-password@node-{index}.example:1080'
            f'#Benchmark-QR-Code-{index}'
        )
        lastImage = qrCodeModule.createQRCodeImage(payload)

    duration = time.perf_counter() - started

    return {
        'mode': 'images',
        'count': count,
        'duration_s': duration,
        'codes_per_s': count / duration,
        'last_width': lastImage.width(),
        'last_height': lastImage.height(),
    }


def benchmarkWindow(mode: str, count: int, timeout: float):
    """Exercise the real exporter, QR renderer, tab pages, and presentation."""
    registry = PluginRegistry()
    registry.register(XrayPlugin())

    try:
        setupStarted = time.perf_counter()
        serverProfiles = profiles(count, registry)
        profileSetupDuration = time.perf_counter() - setupStarted
        resetMilestones()
        window = TrackingQRCodeWindow()
        started = time.perf_counter()

        with mock.patch.object(
            qrCodeModule,
            'MAXIMUM_QR_EXPORT_PROFILES',
            count,
        ), mock.patch.object(
            qrCodeModule.Storage,
            'UserServers',
            return_value=serverProfiles,
        ), mock.patch.object(
            qrCodeModule,
            'exportConfiguration',
            side_effect=registry.exportConfig,
        ):
            if mode == 'synchronous':
                window.initTabByIndex(range(count))
                buildFinished = time.perf_counter()
                window.show()
                pumpUntil(
                    lambda: TrackingQRCodeWindow.paintedAt is not None,
                    timeout,
                )
                finishedAt = time.perf_counter()
                result = {
                    'mode': mode,
                    'count': count,
                    'profile_setup_s': profileSetupDuration,
                    'build_s': buildFinished - started,
                    'result_show_s': elapsed(started, TrackingQRCodeWindow.shownAt),
                    'result_first_paint_s': elapsed(
                        started,
                        TrackingQRCodeWindow.paintedAt,
                    ),
                    'duration_s': finishedAt - started,
                    'tabs': window.tabCount(),
                }
            else:
                window.startExportByIndex(range(count))
                returnedAt = time.perf_counter()
                pumpUntil(
                    lambda: TrackingQRCodeWindow.finishedAt is not None,
                    timeout,
                )

                result = {
                    'mode': mode,
                    'count': count,
                    'profile_setup_s': profileSetupDuration,
                    'start_return_s': returnedAt - started,
                    'result_show_s': elapsed(started, TrackingQRCodeWindow.shownAt),
                    'result_first_paint_s': elapsed(
                        started,
                        TrackingQRCodeWindow.paintedAt,
                    ),
                    'duration_s': elapsed(
                        started,
                        TrackingQRCodeWindow.finishedAt,
                    ),
                    'tabs': window.tabCount(),
                }

        if result['tabs'] != count:
            raise RuntimeError(f"expected {count} tabs, got {result['tabs']}")

        window.close()
        collectAtBoundary()

        return result
    finally:
        registry.shutdown()


def main():
    """Run one explicitly selected benchmark workload."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--mode',
        choices=('images', 'synchronous', 'asynchronous'),
        default='asynchronous',
    )
    parser.add_argument('--count', type=int, default=5_000)
    parser.add_argument('--timeout', type=float, default=900.0)
    arguments = parser.parse_args()

    if arguments.count < 1:
        parser.error('--count must be at least 1')

    application()

    with isolatedSettings():
        if arguments.mode == 'images':
            result = benchmarkImages(arguments.count)
        else:
            result = benchmarkWindow(
                arguments.mode,
                arguments.count,
                max(arguments.timeout, 1.0),
            )

    print(' '.join(f'{key}={value}' for key, value in result.items()))


if __name__ == '__main__':
    main()
