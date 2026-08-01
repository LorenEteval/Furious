"""Integrate Hysteria 1 configuration, editor, routing, and startup."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Plugins.API import FuriousPlugin, PluginProtocol, PluginRouting
from Furious.Plugins.Official.Configuration import (
    BLANK_CONFIG_HYSTERIA1,
    ConfigHysteria1,
)

import copy
import logging

from .Core import Hysteria1

__all__ = ['Hysteria1Plugin']

logger = logging.getLogger(__name__)


class Hysteria1Plugin(FuriousPlugin):
    """Provide official Hysteria 1 support."""

    pluginId = 'official.hysteria1'
    displayName = 'Hysteria1'
    protocols = (
        PluginProtocol(
            'hysteria1',
            'hysteria1',
            'Add Hysteria1 Server...',
            50,
            True,
        ),
    )
    configurationTypes = (ConfigHysteria1,)
    coreTypes = (Hysteria1,)

    def configFromString(self, config: str, **kwargs):
        """Parse a Hysteria 1 share URI."""
        return (
            ConfigHysteria1(config, **kwargs)
            if config.startswith('hysteria://')
            else None
        )

    def configFromDict(self, config: dict, **kwargs):
        """Recognize Hysteria 1 configuration mappings."""
        if config.get('server') is None:
            return None

        fields = (
            'protocol',
            'up_mbps',
            'down_mbps',
            'auth_str',
            'alpn',
            'server_name',
            'insecure',
            'recv_window_conn',
            'recv_window',
            'fast_open',
            'lazy_start',
        )
        if any(config.get(field) is not None for field in fields) or isinstance(
            config.get('obfs'), str
        ):
            return ConfigHysteria1(config, **kwargs)

        return None

    def blankConfig(self, protocol, **kwargs):
        """Construct a blank Hysteria 1 configuration."""
        return ConfigHysteria1(copy.deepcopy(BLANK_CONFIG_HYSTERIA1), **kwargs)

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create the Hysteria 1 editor."""
        # Plugin discovery can occur while the Furious.Qt package is initializing.
        from .GuiHysteria1 import GuiHysteria1

        return GuiHysteria1(parent=parent, **kwargs)

    def routingOptions(self, config=None):
        """Return the routing modes supported by Hysteria 1."""
        return tuple(
            PluginRouting(routing.value, routing.value) for routing in AppBuiltinRouting
        )

    def startCore(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        """Configure Hysteria 1 routing files and start its core."""
        if routing == AppBuiltinRouting.BypassMainlandChina.value:
            if not proxyModeOnly and SystemRuntime.isTUNMode():
                # Defer Qt access until the application has finished importing it.
                from Furious.Qt.QtWidgets import showMBoxDirectRulesNotAllowed

                showMBoxDirectRulesNotAllowed()

                return None, False

            routingObject = {
                'rule': DATA_DIR / 'hysteria' / 'bypass-mainland-China.acl',
                'mmdb': DATA_DIR / 'hysteria' / 'country.mmdb',
            }
        elif routing == AppBuiltinRouting.Custom.value:
            routingObject = {
                'rule': config.get('acl', ''),
                'mmdb': config.get('mmdb', ''),
            }
        else:
            routingObject = {'rule': '', 'mmdb': ''}

        if log:
            logger.info(f'core {Hysteria1.name()} configured')
            logger.info(f'routing is {routing}')
            logger.info(f'RoutingObject: {routingObject}')

        process = Hysteria1(exitCallback=exitCallback, msgCallback=msgCallback)
        success = process.start(
            config,
            Hysteria1.rule(routingObject.get('rule', '')),
            Hysteria1.mmdb(routingObject.get('mmdb', '')),
            **kwargs,
        )

        return process, success

    def prepareDownloadTest(self, config, port: int):
        """Create a Hysteria 1 configuration with one local HTTP proxy."""
        configcopy = config.deepcopy()
        configcopy['http'] = {
            'listen': f'127.0.0.1:{port}',
            'timeout': 300,
            'disable_udp': False,
        }
        configcopy.pop('socks5', '')

        return configcopy

    def coreVersions(self):
        """Return the bundled Hysteria 1 version."""
        return (Hysteria1.version(),)

    def coreExitMessage(self, core, exitcode: int):
        """Interpret the Hysteria 1 remote-network exit code."""
        if exitcode == Hysteria1.ExitCode.RemoteNetworkError.value:
            return 'Connection to server has been lost'

        return None
