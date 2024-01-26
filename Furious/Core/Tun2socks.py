from __future__ import annotations

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.Library import *
from Furious.Utility import *

import time

__all__ = ['Tun2socks']


def startTun2socks(*args, **kwargs):
    try:
        import tun2socks
    except ImportError:
        # Fake running process
        while True:
            time.sleep(1)
    else:
        tun2socks.startFromArgs(*args, **kwargs)


class Tun2socks(CoreProcess):
    class ExitCode:
        # Windows shutting down
        SystemShuttingDown = 0x40010004

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
            args=(device, networkInterface, logLevel, proxy, restAPI),
            **kwargs,
        )

    def stop(self):
        SystemRoutingTable.deleteRelations()

        super().stop()
