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

"""Define the capability contracts implemented by Furious plugins."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

__all__ = [
    'PLUGIN_API_VERSION',
    'CoreBackend',
    'FuriousPlugin',
    'PluginContext',
    'ProtocolDescriptor',
    'ProtocolHandler',
    'RoutingOption',
    'SubscriptionDecoder',
    'SubscriptionItem',
    'SubscriptionResult',
]

PLUGIN_API_VERSION = 2


@dataclass(frozen=True)
class ProtocolDescriptor:
    """Describe one user-visible proxy protocol."""

    id: str
    displayName: str
    addActionText: str
    menuOrder: int = 0
    separatorBefore: bool = False


@dataclass(frozen=True)
class RoutingOption:
    """Describe one routing mode supported by a core backend."""

    id: str
    displayName: str
    separatorBefore: bool = False
    translatable: bool = False


@dataclass(frozen=True)
class PluginContext:
    """Provide host services to a plugin during initialization."""

    pluginId: str
    registry: Any


@dataclass(frozen=True)
class SubscriptionItem:
    """Represent one profile emitted by a subscription decoder."""

    uri: Optional[str] = None
    configuration: Optional[Mapping[str, Any]] = None
    name: str = ''

    def __post_init__(self):
        """Require exactly one serialized or normalized profile value."""
        if (self.uri is None) == (self.configuration is None):
            raise ValueError(
                'a subscription item must contain exactly one URI or configuration'
            )


@dataclass(frozen=True)
class SubscriptionResult:
    """Return normalized entries produced from one subscription payload."""

    decoderId: str
    items: Tuple[SubscriptionItem, ...]


class ProtocolHandler:
    """Own one protocol's profile conversion and editor capability."""

    descriptor = ProtocolDescriptor('', '', '')
    schemes = tuple()

    def supports(self, configuration) -> bool:
        """Return whether this handler owns *configuration*."""
        return False

    def parse(self, uri: str, **kwargs):
        """Parse one supported URI or return ``None``."""
        return None

    def fromMapping(self, configuration: Mapping[str, Any], **kwargs):
        """Recognize one normalized configuration mapping or return ``None``."""
        return None

    def blank(self, **kwargs):
        """Create a blank configuration for this protocol."""
        return None

    def export(self, configuration, remark: str = '') -> str:
        """Serialize one owned configuration to a share URI."""
        return ''

    def createEditor(self, parent=None, **kwargs):
        """Create this protocol's editor, if it provides one."""
        return None


class SubscriptionDecoder:
    """Decode one subscription representation without importing profiles."""

    decoderId = ''
    displayName = ''
    priority = 0

    def decode(self, data: bytes) -> Optional[SubscriptionResult]:
        """Decode *data* or return ``None`` when the format does not match."""
        return None


class CoreBackend:
    """Run configurations for one proxy core independently of URI protocols."""

    backendId = ''
    configurationTypes = tuple()
    coreTypes = tuple()

    def fromMapping(self, configuration: Mapping[str, Any], **kwargs):
        """Recognize a full backend configuration not owned by one protocol."""
        return None

    def createManagementActions(self, parent=None, **kwargs):
        """Return optional actions for this backend's management submenu."""
        return tuple()

    def prepareTUN(self, config) -> bool:
        """Prepare native TUN and return whether the backend handles it."""
        return False

    def routingOptions(self, config=None):
        """Return routing modes supported for a backend configuration."""
        return tuple()

    def configureEnvironment(self):
        """Set optional environment required by this backend's process."""

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
        """Start the backend and return ``(process, success)``."""
        return None, False

    def prepareDownloadTest(self, config, port: int):
        """Return a proxy-only configuration for a download-speed test."""
        return None

    def coreVersions(self):
        """Return version strings reported by this backend."""
        return tuple()

    def logTimestampPatterns(self):
        """Return timestamp expressions emitted by this backend."""
        return tuple()

    def coreExitMessage(self, core, exitcode: int):
        """Return a user-facing message key for a special exit code."""
        return None

    def afterConnected(self, httpProxy=None):
        """Perform optional maintenance after a connection succeeds."""


class FuriousPlugin:
    """Group independently discoverable Furious capabilities."""

    apiVersion = PLUGIN_API_VERSION
    pluginId = ''
    displayName = ''
    protocolHandlers = tuple()
    coreBackends = tuple()
    subscriptionDecoders = tuple()

    def initialize(self, context: PluginContext):
        """Initialize the plugin after all of its capabilities are registered."""

    def shutdown(self):
        """Release resources owned by the plugin before application shutdown."""
