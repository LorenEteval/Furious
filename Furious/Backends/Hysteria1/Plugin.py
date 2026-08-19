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

"""Integrate Hysteria 1 configuration, editor, routing, and startup."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Plugins.API import *
from Furious.Backends.Configuration import *

from .Process import *
from .ProtocolEditors import HYSTERIA1_PROTOCOL_EDITORS
from .Protocols import HYSTERIA1_PROTOCOL_HANDLERS

import logging

__all__ = ['Hysteria1Plugin']

logger = logging.getLogger(__name__)


class Hysteria1CoreRuntimeFactory(CoreRuntimeFactory):
    """Construct Hysteria 1 core runtimes independently of protocol handling."""

    factoryId = 'official.hysteria1'
    configurationTypes = (ConfigHysteria1,)
    runtimeTypes = (Hysteria1,)

    def routingOptions(self, config=None):
        """Return the routing modes supported by Hysteria 1."""
        return tuple(
            RoutingOption(routing.value, routing.value, translatable=True)
            for routing in AppBuiltinRouting
        )

    def create(self, request: CoreRuntimeRequest):
        """Configure routing and create a Hysteria 1 core-runtime launch."""
        config, routing = (
            request.configuration,
            request.routing,
        )

        if routing == AppBuiltinRouting.BypassMainlandChina.value:
            if not request.proxyModeOnly and SystemRuntime.isTUNMode():
                # Defer Qt access until the application has finished importing it.
                from Furious.Qt.QtWidgets import showMBoxDirectRulesNotAllowed

                showMBoxDirectRulesNotAllowed()

                return None

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

        if request.log:
            logger.info(f'core {Hysteria1.name()} configured')
            logger.info(f'routing is {routing}')
            logger.info(f'RoutingObject: {routingObject}')

        runtime = Hysteria1(
            exitCallback=request.exitCallback,
            msgCallback=request.messageCallback,
        )

        return CoreRuntimeLaunch(
            runtime,
            config,
            arguments=(
                Hysteria1.rule(routingObject.get('rule', '')),
                Hysteria1.mmdb(routingObject.get('mmdb', '')),
            ),
            options=request.options,
        )

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


class Hysteria1Plugin(FuriousPlugin):
    """Bundle official Hysteria 1 protocol and runtime capabilities."""

    metadata = PluginMetadata(
        'official.hysteria1',
        'Hysteria1',
        description='Official Hysteria 1 protocol, editor, and runtime support.',
        provider='Furious',
    )

    def __init__(self):
        """Create an isolated Hysteria 1 runtime factory."""
        self.capabilities = (
            *HYSTERIA1_PROTOCOL_HANDLERS,
            *HYSTERIA1_PROTOCOL_EDITORS,
            Hysteria1CoreRuntimeFactory(),
        )
