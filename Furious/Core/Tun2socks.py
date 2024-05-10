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
from Furious.QtFramework import *
from Furious.Library import *
from Furious.Utility import *

import time
import multiprocessing

__all__ = ['Tun2socks']


def startTun2socks(msgQueue: multiprocessing.Queue, *args):
    try:
        import tun2socks
    except ImportError:
        # Fake running process
        while True:
            time.sleep(1)
    else:
        if versionToValue(tun2socks.__version__) <= versionToValue('2.5.1.1'):
            redirect = False
        else:
            redirect = True

        StdoutRedirectHelper.launch(
            msgQueue, lambda: tun2socks.startFromArgs(*args), redirect
        )


class Tun2socks(CoreProcess):
    class ExitCode:
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.cleanup = None

    @staticmethod
    def name() -> str:
        return 'Tun2socks'

    @staticmethod
    def version() -> str:
        try:
            import tun2socks

            return tun2socks.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(
        self,
        device: str,
        networkInterface: str,
        logLevel: str,
        proxy: str,
        restAPI: str,
        **kwargs,
    ) -> bool:
        return super().start(
            target=startTun2socks,
            args=(self.msgQueue, device, networkInterface, logLevel, proxy, restAPI),
            **kwargs,
        )

    def stop(self):
        SystemRoutingTable.deleteRelations()

        if callable(self.cleanup):
            self.cleanup()

        super().stop()
