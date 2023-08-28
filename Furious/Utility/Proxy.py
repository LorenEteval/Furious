from Furious.Utility.Constants import PLATFORM

import logging
import subprocess

logger = logging.getLogger(__name__)


def runCommand(*args, **kwargs):
    return subprocess.run(*args, **kwargs)


def linuxProxyConfig(proxy_args, arg0, arg1):
    runCommand(
        [
            'gsettings',
            'set',
            'org.gnome.system.' + proxy_args,
            arg0,
            arg1,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def darwinProxyConfig(operation, *args):
    def getNetworkServices():
        command = runCommand(
            ['networksetup', '-listallnetworkservices'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        service = list(filter(lambda x: x != '', command.stdout.decode().split('\n')))

        return service[1:]

    for serviceName in getNetworkServices():
        runCommand(
            [
                'networksetup',
                f'-{operation}',
                serviceName,
                *args,
            ]
        )


class _Proxy:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._daemonThread = None

    @staticmethod
    def pac(pac_url):
        def _pac():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.pac(pac_url)
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    linuxProxyConfig('proxy', 'autoconfig-url', pac_url)
                    linuxProxyConfig('proxy', 'mode', 'auto')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setautoproxyurl', pac_url)
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _pac():
            logger.info('set proxy PAC success')
        else:
            logger.error('set proxy PAC failed')

    @staticmethod
    def set(server, bypass):
        def _set():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.set(server, bypass)
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    host, port = server.split(':')

                    linuxProxyConfig('proxy.http', 'host', host)
                    linuxProxyConfig('proxy.http', 'port', port)
                    linuxProxyConfig('proxy.https', 'host', host)
                    linuxProxyConfig('proxy.https', 'port', port)
                    linuxProxyConfig(
                        'proxy', 'ignore-hosts', str(list(bypass.split(';')))
                    )
                    linuxProxyConfig('proxy', 'mode', 'manual')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setwebproxy', *server.split(':'))
                    darwinProxyConfig('setsecurewebproxy', *server.split(':'))
                    darwinProxyConfig('setproxybypassdomains', *bypass.split(';'))
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _set():
            logger.info(f'set proxy server {server} success')
        else:
            logger.error(f'set proxy server {server} failed')

    @staticmethod
    def off():
        def _off():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy

                    return sysproxy.off()
                except Exception:
                    # Any non-exit exceptions

                    return False

            if PLATFORM == 'Linux':
                try:
                    linuxProxyConfig('proxy', 'mode', 'none')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                try:
                    darwinProxyConfig('setwebproxystate', 'off')
                    darwinProxyConfig('setsecurewebproxystate', 'off')
                    darwinProxyConfig('setautoproxystate', 'off')
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _off():
            logger.info('turn off proxy success')
        else:
            logger.error('turn off proxy failed')

    def daemonOn_(self):
        def _daemonOn_():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy
                    import threading

                    if self._daemonThread is not None:
                        return False

                    self._daemonThread = threading.Thread(
                        target=lambda: sysproxy.daemon_on_(), daemon=True
                    )
                    self._daemonThread.start()

                    return True
                except Exception:
                    # Any non-exit exceptions

                    return False

        if _daemonOn_():
            logger.info('turn on proxy daemon success')
        else:
            logger.error('turn on proxy daemon failed')

    def daemonOff(self):
        def _daemonOff():
            if PLATFORM == 'Windows':
                try:
                    import sysproxy
                    import threading

                    if self._daemonThread is None:
                        # Already in off state
                        return True

                    assert isinstance(self._daemonThread, threading.Thread)

                    if sysproxy.daemon_off():
                        self._daemonThread.join()

                        # Reset it
                        self._daemonThread = None

                        return True
                    else:
                        return False
                except Exception:
                    # Any non-exit exceptions

                    return False

            # Note: try to resolve non-Windows proxy daemon issue by
            # turning on StartupOnBoot by default. This should be
            # friendly for most of the users

        if _daemonOff():
            logger.info('turn off proxy daemon success')
        else:
            logger.error('turn off proxy daemon failed')


Proxy = _Proxy()
