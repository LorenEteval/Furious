from Furious.Core.Core import Core
from Furious.Utility.RoutingTable import RoutingTable


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
            waitTime=1000,
            **kwargs,
        )

    def stop(self):
        RoutingTable.deleteRelations()

        super().stop()
