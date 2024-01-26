from __future__ import annotations

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.Library import *
from Furious.Utility import *
from Furious.Core import *

import uuid
import logging

__all__ = ['CoreManager']

logger = logging.getLogger(__name__)


def fixLogObjectPath(config: ConfigurationFactory, attr: str, value: str, log=True):
    try:
        path = config['log'][attr]
    except Exception:
        # Any non-exit exceptions

        config['log'][attr] = path = ''

    if not isinstance(path, str) and not isinstance(path, bytes):
        config['log'][attr] = path = ''

    if path == '':
        if isPythonw() and StdoutRedirectHelper.TemporaryDir.isValid():
            # Redirect implementation for pythonw environment
            config['log'][attr] = StdoutRedirectHelper.TemporaryDir.filePath(value)
    else:
        # Relative path fails if booting on start up
        # on Windows, when packed using nuitka...

        # Fix relative path if needed. User cannot feel this operation.
        config['log'][attr] = getAbsolutePath(path)

    result = config['log'][attr]

    if result:
        try:
            # Create a new file
            with open(result, 'x'):
                pass
        except FileExistsError:
            pass
        except Exception:
            # Any non-exit exceptions

            pass

    if log:
        logger.info(
            f'{XrayCore.name()}: {attr} log is specified as \'{path}\'. '
            f'Fixed to \'{result}\''
        )


class CoreManager(SupportExitCleanup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.coresPool = []

    def start(
        self,
        config: ConfigurationFactory,
        routing: str,
        exitCallback=None,
        msgCallback=None,
        deepcopy=True,
        log=True,
        **kwargs,
    ) -> bool:
        if deepcopy:
            copy = config.deepcopy()
        else:
            copy = config

        if isinstance(copy, ConfigurationXray):
            if copy.get('log') is None or not isinstance(copy['log'], dict):
                copy['log'] = {
                    'access': '',
                    'error': '',
                    'loglevel': 'warning',
                }

            logRedirectValue = str(uuid.uuid4())

            # Fix logObject
            for attr in ['access', 'error']:
                fixLogObjectPath(copy, attr, logRedirectValue, log)

            if routing == 'Bypass Mainland China':
                routingObject = {
                    'domainStrategy': 'IPIfNonMatch',
                    'domainMatcher': 'hybrid',
                    'rules': [
                        {
                            'type': 'field',
                            'domain': [
                                'geosite:category-ads-all',
                            ],
                            'outboundTag': 'block',
                        },
                        {
                            'type': 'field',
                            'domain': [
                                'geosite:cn',
                            ],
                            'outboundTag': 'direct',
                        },
                        {
                            'type': 'field',
                            'ip': [
                                'geoip:private',
                                'geoip:cn',
                            ],
                            'outboundTag': 'direct',
                        },
                        {
                            'type': 'field',
                            'port': '0-65535',
                            'outboundTag': 'proxy',
                        },
                    ],
                }
            elif routing == 'Bypass Iran':
                routingObject = {
                    'domainStrategy': 'IPIfNonMatch',
                    'domainMatcher': 'hybrid',
                    'rules': [
                        {
                            'type': 'field',
                            'domain': [
                                'geosite:category-ads-all',
                                'iran:ads',
                            ],
                            'outboundTag': 'block',
                        },
                        {
                            'type': 'field',
                            'domain': [
                                'iran:ir',
                                'iran:other',
                            ],
                            'outboundTag': 'direct',
                        },
                        {
                            'type': 'field',
                            'ip': [
                                'geoip:private',
                                'geoip:ir',
                            ],
                            'outboundTag': 'direct',
                        },
                        {
                            'type': 'field',
                            'port': '0-65535',
                            'outboundTag': 'proxy',
                        },
                    ],
                }
            elif routing == 'Global':
                routingObject = {}
            elif routing == 'Custom':
                routingObject = copy.get('routing', {})
            else:
                routingObject = {}

            if log:
                logger.info(f'core {XrayCore.name()} configured')
                logger.info(f'routing is {routing}')
                logger.info(f'RoutingObject: {routingObject}')

            copy['routing'] = routingObject

            core = XrayCore(exitCallback=exitCallback, msgCallback=msgCallback)
            success = core.start(copy, **kwargs)
        elif isinstance(copy, ConfigurationHysteria1):
            if routing == 'Bypass Mainland China':
                routingObject = {
                    'rule': DATA_DIR / 'hysteria' / 'bypass-mainland-China.acl',
                    'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
                }
            elif routing == 'Bypass Iran':
                routingObject = {
                    'rule': DATA_DIR / 'hysteria' / 'bypass-Iran.acl',
                    'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
                }
            elif routing == 'Global':
                routingObject = {
                    'rule': '',
                    'mmdb': '',
                }
            elif routing == 'Custom':
                routingObject = {
                    'rule': copy.get('acl', ''),
                    'mmdb': copy.get('mmdb', ''),
                }
            else:
                routingObject = {
                    'rule': '',
                    'mmdb': '',
                }

            if log:
                logger.info(f'core {Hysteria1.name()} configured')
                logger.info(f'routing is {routing}')
                logger.info(f'RoutingObject: {routingObject}')

            core = Hysteria1(exitCallback=exitCallback, msgCallback=msgCallback)
            success = core.start(
                copy,
                Hysteria1.rule(routingObject.get('rule', '')),
                Hysteria1.mmdb(routingObject.get('mmdb', '')),
                **kwargs,
            )
        elif isinstance(copy, ConfigurationHysteria2):
            if log:
                logger.info(f'core {Hysteria2.name()} configured')

            core = Hysteria2(exitCallback=exitCallback, msgCallback=msgCallback)
            success = core.start(copy, **kwargs)
        else:
            core = None
            success = False

        if core is not None:
            self.coresPool.append(core)

        return success

    def allRunning(self) -> bool:
        return all(core.isRunning() for core in self.coresPool)

    def anyRunning(self) -> bool:
        return any(core.isRunning() for core in self.coresPool)

    def stopAll(self):
        if self.coresPool:
            for core in self.coresPool:
                if isinstance(core, CoreFactory):
                    core.stop()

            self.coresPool.clear()

    def cleanup(self):
        self.stopAll()
