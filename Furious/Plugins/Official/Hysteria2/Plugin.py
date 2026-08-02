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

"""Integrate Hysteria 2 configuration, editor, and process startup."""

from __future__ import annotations

from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Plugins.API import FuriousPlugin, PluginProtocol
from Furious.Plugins.Official.Configuration import (
    BLANK_CONFIG_HYSTERIA2,
    ConfigHysteria2,
)

import copy
import logging

from .Core import Hysteria2

__all__ = ['Hysteria2Plugin']

logger = logging.getLogger(__name__)

_TRANSLATABLE_ACTION_TEXT = [
    _('Add Hysteria2 Server...'),
]


class Hysteria2Plugin(FuriousPlugin):
    """Provide official Hysteria 2 support."""

    pluginId = 'official.hysteria2'
    displayName = 'Hysteria2'
    protocols = (
        PluginProtocol(
            'hysteria2',
            'hysteria2',
            'Add Hysteria2 Server...',
            60,
        ),
    )
    configurationTypes = (ConfigHysteria2,)
    coreTypes = (Hysteria2,)

    def configFromString(self, config: str, **kwargs):
        """Parse a Hysteria 2 share URI."""
        if config.startswith(
            (
                'hy2://',
                'hysteria2://',
                'hysteria2+realm://',
                'hysteria2+realm+http://',
            )
        ):
            return ConfigHysteria2(config, **kwargs)

        return None

    def configFromDict(self, config: dict, **kwargs):
        """Recognize Hysteria 2 configuration mappings."""
        if config.get('server') is None:
            return None

        fields = (
            'auth',
            'tls',
            'transport',
            'quic',
            'bandwidth',
            'tcpForwarding',
            'udpForwarding',
            'tcpTProxy',
            'udpTProxy',
            'fastOpen',
            'lazy',
        )
        if any(config.get(field) is not None for field in fields) or isinstance(
            config.get('obfs'), dict
        ):
            return ConfigHysteria2(config, **kwargs)

        return None

    def blankConfig(self, protocol, **kwargs):
        """Construct a blank Hysteria 2 configuration."""
        return ConfigHysteria2(copy.deepcopy(BLANK_CONFIG_HYSTERIA2), **kwargs)

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create the Hysteria 2 editor."""
        # Plugin discovery can occur while the Furious.Qt package is initializing.
        from .GuiHysteria2 import GuiHysteria2

        return GuiHysteria2(parent=parent, **kwargs)

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
        """Start the Hysteria 2 core."""
        if log:
            logger.info(f'core {Hysteria2.name()} configured')

        process = Hysteria2(exitCallback=exitCallback, msgCallback=msgCallback)

        return process, process.start(config, **kwargs)

    def prepareDownloadTest(self, config, port: int):
        """Create a Hysteria 2 configuration with one local HTTP proxy."""
        configcopy = config.deepcopy()
        configcopy['http'] = {
            'listen': f'127.0.0.1:{port}',
            'timeout': 300,
            'disable_udp': False,
        }
        configcopy.pop('socks5', '')

        return configcopy

    def coreVersions(self):
        """Return the bundled Hysteria 2 version."""
        return (Hysteria2.version(),)

    def logTimestampPatterns(self):
        """Return the timestamp format emitted by Hysteria 2."""
        return (r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})',)
