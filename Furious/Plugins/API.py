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

"""Define capability contracts implemented by Furious plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

__all__ = [
    'PLUGIN_API_VERSION',
    'ActionProvider',
    'CapabilityKind',
    'FuriousPlugin',
    'KernelFactory',
    'KernelLaunch',
    'KernelRequest',
    'PluginCapability',
    'PluginContext',
    'PluginMetadata',
    'ProtocolDescriptor',
    'ProtocolEditorProvider',
    'ProtocolHandler',
    'ProtocolParseResult',
    'RoutingOption',
    'SubscriptionDecoder',
    'SubscriptionItem',
    'SubscriptionResult',
]

PLUGIN_API_VERSION = 3


class CapabilityKind(str, Enum):
    """Identify independently discoverable plugin extension points."""

    ActionProvider = 'action-provider'
    Protocol = 'protocol'
    ProtocolEditor = 'protocol-editor'
    SubscriptionDecoder = 'subscription-decoder'
    KernelFactory = 'kernel-factory'
    Utility = 'utility'


@dataclass(frozen=True)
class PluginMetadata:
    """Describe a plugin independently from the capabilities it provides."""

    id: str
    displayName: str
    version: str = '1'
    description: str = ''
    provider: str = ''


class PluginCapability:
    """Define one independently queryable plugin capability."""

    capabilityKind = CapabilityKind.Utility

    @property
    def capabilityId(self) -> str:
        """Return the identifier unique within this capability kind."""
        return ''


class ActionProvider(PluginCapability):
    """Create optional host UI actions without implying a runtime capability."""

    capabilityKind = CapabilityKind.ActionProvider
    providerId = ''
    category = 'plugin'

    @property
    def capabilityId(self) -> str:
        """Return the action-provider identifier."""
        return self.providerId

    def createActions(self, parent=None, **kwargs):
        """Return actions contributed to the plugin management UI."""
        return tuple()


@dataclass(frozen=True)
class ProtocolDescriptor:
    """Describe one user-visible proxy protocol."""

    id: str
    displayName: str
    addActionText: str
    menuOrder: int = 0
    separatorBefore: bool = False
    configurationSchema: Mapping[str, Any] = field(default_factory=dict)
    translatable: bool = False


@dataclass(frozen=True)
class ProtocolParseResult:
    """Return a connection document and its URI-derived profile metadata."""

    configuration: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the metadata boundary exposed by a protocol parser."""
        if not isinstance(self.metadata, Mapping):
            raise TypeError('protocol parse metadata must be a mapping')


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
    metadata: PluginMetadata


@dataclass(frozen=True)
class SubscriptionItem:
    """Represent one profile emitted by a subscription decoder."""

    uri: Optional[str] = None
    configuration: Optional[Mapping[str, Any]] = None
    name: str = ''
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Require exactly one serialized or normalized profile value."""
        if (self.uri is None) == (self.configuration is None):
            raise ValueError(
                'a subscription item must contain exactly one URI or configuration'
            )

        if not isinstance(self.metadata, Mapping):
            raise TypeError('subscription item metadata must be a mapping')


@dataclass(frozen=True)
class SubscriptionResult:
    """Return normalized entries produced from one subscription payload."""

    decoderId: str
    items: Tuple[SubscriptionItem, ...]


class ProtocolHandler(PluginCapability):
    """Own one protocol's validation and serialization behavior."""

    capabilityKind = CapabilityKind.Protocol
    descriptor = ProtocolDescriptor('', '', '')
    schemes = tuple()

    @property
    def capabilityId(self) -> str:
        """Return the protocol identifier."""
        return self.descriptor.id

    def supports(self, configuration) -> bool:
        """Return whether this handler owns *configuration*."""
        return False

    def parse(self, uri: str, **kwargs):
        """Return a `ProtocolParseResult` or ``None`` for *uri*."""
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

    def validate(self, configuration) -> Tuple[str, ...]:
        """Return validation errors for one owned configuration."""
        if not self.supports(configuration):
            return ('Unsupported protocol',)

        validator = getattr(configuration, 'isValid', None)

        return tuple() if not callable(validator) or validator() else ('Invalid data',)


class ProtocolEditorProvider(PluginCapability):
    """Create Qt editors for one or more protocol identifiers."""

    capabilityKind = CapabilityKind.ProtocolEditor
    editorId = ''
    protocolIds = tuple()

    @property
    def capabilityId(self) -> str:
        """Return the editor-provider identifier."""
        return self.editorId

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Create an editor for *protocolId* or return ``None``."""
        return None


class SubscriptionDecoder(PluginCapability):
    """Decode one subscription representation without importing profiles."""

    capabilityKind = CapabilityKind.SubscriptionDecoder
    decoderId = ''
    displayName = ''
    priority = 0

    @property
    def capabilityId(self) -> str:
        """Return the subscription decoder identifier."""
        return self.decoderId

    def decode(self, data: bytes) -> Optional[SubscriptionResult]:
        """Decode *data* or return ``None`` when the format does not match."""
        return None


@dataclass(frozen=True)
class KernelRequest:
    """Describe one runtime-kernel construction request."""

    configuration: Any
    routing: str
    exitCallback: Any = None
    messageCallback: Any = None
    proxyModeOnly: bool = False
    log: bool = True
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KernelLaunch:
    """Bind a constructed kernel to its prepared start arguments."""

    kernel: Any
    configuration: Any
    arguments: Tuple[Any, ...] = tuple()
    options: Mapping[str, Any] = field(default_factory=dict)

    def start(self) -> bool:
        """Start the prepared kernel."""
        return bool(
            self.kernel.start(
                self.configuration,
                *self.arguments,
                **dict(self.options),
            )
        )


class KernelFactory(PluginCapability):
    """Construct runtime kernels independently from protocol handling."""

    capabilityKind = CapabilityKind.KernelFactory
    factoryId = ''
    configurationTypes = tuple()
    kernelTypes = tuple()

    @property
    def capabilityId(self) -> str:
        """Return the runtime factory identifier."""
        return self.factoryId

    def fromMapping(self, configuration: Mapping[str, Any], **kwargs):
        """Recognize a full backend configuration not owned by one protocol."""
        return None

    def prepareTUN(self, config) -> bool:
        """Prepare native TUN and return whether the backend handles it."""
        return False

    def routingOptions(self, config=None):
        """Return routing modes supported for a backend configuration."""
        return tuple()

    def configureEnvironment(self):
        """Set optional environment required by this backend's process."""

    def create(self, request: KernelRequest) -> Optional[KernelLaunch]:
        """Create a prepared runtime kernel launch."""
        return None

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
    metadata = PluginMetadata('', '')
    capabilities = tuple()

    def pluginMetadata(self) -> PluginMetadata:
        """Return this plugin's declarative metadata."""
        return self.metadata

    def declaredCapabilities(self) -> Tuple[PluginCapability, ...]:
        """Return the independently discoverable capabilities of this plugin."""
        return tuple(self.capabilities)

    def initialize(self, context: PluginContext):
        """Initialize the plugin after all of its capabilities are registered."""

    def shutdown(self):
        """Release resources owned by the plugin before application shutdown."""
