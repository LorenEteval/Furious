# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Core.Core import Core
from Furious.Utility.RoutingTable import RoutingTable

import functools


def startTun2socks(*args, **kwargs):
    try:
        import tun2socks
    except ImportError:
        # Fake running process
        while True:
            pass
    else:
        tun2socks.startFromArgs(*args, **kwargs)


class Tun2socks(Core):
    class ExitCode:
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def name():
        return 'Tun2socks'

    @staticmethod
    @functools.lru_cache(None)
    def version():
        try:
            import tun2socks

            return tun2socks.__version__
        except Exception:
            # Any non-exit exceptions

            return '0.0.0'

    def start(self, device, networkInterface, logLevel, proxy, restAPI, **kwargs):
        super().start(
            target=startTun2socks,
            args=(device, networkInterface, logLevel, proxy, restAPI),
            **kwargs,
        )

    def stop(self):
        RoutingTable.deleteRelations()

        super().stop()
