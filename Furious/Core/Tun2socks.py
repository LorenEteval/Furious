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

"""Wrap the embedded tun2socks process used by TUN mode."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Core.CoreProcessWorker import *

import time
import functools
import multiprocessing

__all__ = ['Tun2socks']


def startTun2socks(msgQueue: multiprocessing.Queue, *args):
    """Start tun2socks."""
    try:
        import tun2socks
    except ImportError:
        # Fake running process
        while True:
            time.sleep(3600)
    else:
        if versionToValue(tun2socks.__version__) <= versionToValue('2.5.1.1'):
            redirect = False
        else:
            redirect = True

        ProcessOutputRedirector.launch(
            msgQueue,
            functools.partial(tun2socks.startFromArgs, *args),
            redirect,
        )


class Tun2socks(CoreProcessWorker):
    """Manage the tun2socks subprocess used by TUN mode."""

    class ExitCode:
        # Windows shutting down
        """Enumerate process exit codes."""
        SystemShuttingDown = 0x40010004

    def __init__(self, **kwargs):
        """Initialize the Tun2socks."""
        backgroundOptimizer = kwargs.pop('backgroundOptimizer', AppLogPage)

        super().__init__(**kwargs, backgroundOptimizer=backgroundOptimizer)

        self.cleanup = None

    @staticmethod
    def name() -> str:
        """Return the process implementation name."""
        return 'Tun2socks'

    @staticmethod
    def version() -> str:
        """Return the bundled core version."""
        try:
            import tun2socks

            return tun2socks.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def launchSpec(
        self,
        device: str,
        networkInterface: str,
        logLevel: str,
        proxy: str,
        restAPI: str,
        tcpSendBufferSize: str = '',
        tcpReceiveBufferSize: str = '',
        tcpAutoTuning: bool = False,
        **kwargs,
    ) -> CoreLaunchSpec:
        """Build the child-process launch specification."""
        return CoreLaunchSpec(
            target=startTun2socks,
            args=(
                self.msgQueue,
                device,
                networkInterface,
                logLevel,
                proxy,
                restAPI,
                tcpSendBufferSize,
                tcpReceiveBufferSize,
                tcpAutoTuning,
            ),
            processKwargs=kwargs,
        )

    def start(
        self,
        device: str,
        networkInterface: str,
        logLevel: str,
        proxy: str,
        restAPI: str,
        tcpSendBufferSize: str = '',
        tcpReceiveBufferSize: str = '',
        tcpAutoTuning: bool = False,
        **kwargs,
    ) -> bool:
        """Start the tun2socks."""
        launchSpec = self.launchSpec(
            device,
            networkInterface,
            logLevel,
            proxy,
            restAPI,
            tcpSendBufferSize,
            tcpReceiveBufferSize,
            tcpAutoTuning,
            **kwargs,
        )

        return self.startWithSpec(launchSpec)

    def stop(self):
        """Stop the tun2socks."""
        if PLATFORM == 'Linux':
            # Stop tunnel first
            super().stop()

            SystemRoutingTable.deleteRelations()

            if callable(self.cleanup):
                self.cleanup()
        else:
            SystemRoutingTable.deleteRelations()

            if callable(self.cleanup):
                self.cleanup()

            super().stop()
