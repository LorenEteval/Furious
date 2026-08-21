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

"""Discover plugins and index independently usable capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib import metadata
from typing import Optional
from urllib.parse import urlsplit

import logging
import threading

from .API import (
    PLUGIN_API_VERSION,
    ActionProvider,
    CapabilityKind,
    CoreRuntimeFactory,
    CoreRuntimeLaunch,
    CoreRuntimeRequest,
    FuriousPlugin,
    PluginCapability,
    PluginContext,
    PluginMetadata,
    ProtocolDescriptor,
    ProtocolEditorProvider,
    ProtocolHandler,
    ProtocolParseResult,
    RoutingOption,
    SubscriptionDecoder,
    SubscriptionItem,
    SubscriptionResult,
    TUNPreparationError,
    TrafficStatsMonitor,
    TrafficStatsProvider,
)

__all__ = [
    'PLUGIN_ENTRY_POINT_GROUP',
    'PluginRegistry',
    'getPluginRegistry',
    'initializePluginRegistry',
    'registerPlugin',
]

PLUGIN_ENTRY_POINT_GROUP = 'furious.plugins'
SUPPORTED_PLUGIN_API_VERSIONS = (PLUGIN_API_VERSION,)

logger = logging.getLogger(__name__)


def _normalizeIdentifier(value) -> str:
    """Return a case-insensitive capability identifier."""
    return str(getattr(value, 'value', value)).strip().casefold()


def _normalizeScheme(value) -> str:
    """Return a URI scheme without punctuation."""
    return str(value).strip().rstrip(':').casefold()


def _runtimeTypes(capability) -> tuple:
    """Return the capability's declared managed runtime types."""
    return tuple(getattr(capability, 'runtimeTypes', tuple()) or tuple())


def _schemeFromURI(uri: str) -> str:
    """Extract a normalized scheme from *uri*."""
    try:
        return _normalizeScheme(urlsplit(uri.strip()).scheme)
    except Exception:
        # Any non-exit exceptions

        return ''


def _connectionOf(value):
    """Return a profile's connection document or *value* itself."""
    return getattr(value, 'connection', value)


@dataclass
class _PluginValidationState:
    """Track conflicts discovered while validating one plugin atomically."""

    capabilityIds: set = field(default_factory=set)
    protocolIds: set = field(default_factory=set)
    schemes: set = field(default_factory=set)
    editorProtocols: set = field(default_factory=set)
    configurationTypes: list = field(default_factory=list)
    runtimeTypes: list = field(default_factory=list)
    trafficStatsRuntimeTypes: list = field(default_factory=list)


class PluginRegistry:
    """Own plugin lifecycle and dispatch through capability indexes."""

    def __init__(self):
        """Initialize an empty capability registry."""
        self._plugins = {}
        self._metadata = {}
        self._capabilities = {kind: {} for kind in CapabilityKind}
        self._capabilityEntries = []
        self._protocols = {}
        self._schemes = {}
        self._protocolEntries = []
        self._editors = {}
        self._protocolEditors = {}
        self._factories = {}
        self._configurationFactories = {}
        self._runtimeFactories = {}
        self._trafficStatsProviders = {}
        self._decoders = {}
        self._initializedPlugins = []
        self._closed = False

    @staticmethod
    def _kind(capability) -> CapabilityKind:
        """Return a validated capability kind."""
        try:
            return CapabilityKind(capability.capabilityKind)
        except Exception as ex:
            # Any non-exit exceptions

            raise TypeError('capability has an invalid capability kind') from ex

    @staticmethod
    def _id(capability) -> str:
        """Return a normalized non-empty capability identifier."""
        identifier = _normalizeIdentifier(capability.capabilityId)

        if not identifier:
            raise ValueError('capability ID cannot be empty')

        return identifier

    def _validatePluginMetadata(self, plugin):
        """Validate one plugin and return its normalized identity metadata."""
        if isinstance(plugin, type) and issubclass(plugin, FuriousPlugin):
            plugin = plugin()

        if not isinstance(plugin, FuriousPlugin):
            raise TypeError('plugin must be a FuriousPlugin instance')

        if plugin.apiVersion not in SUPPORTED_PLUGIN_API_VERSIONS:
            raise ValueError(
                f'plugin API {plugin.apiVersion!r} is not supported; '
                f'expected one of {SUPPORTED_PLUGIN_API_VERSIONS!r}'
            )

        pluginMetadata = plugin.pluginMetadata()

        if not isinstance(pluginMetadata, PluginMetadata):
            raise TypeError('plugin metadata must be a PluginMetadata value')

        pluginId = _normalizeIdentifier(pluginMetadata.id)

        if not pluginId:
            raise ValueError('plugin ID cannot be empty')

        if not str(pluginMetadata.displayName).strip():
            raise ValueError('plugin display name cannot be empty')

        for fieldName in ('version', 'description', 'provider'):
            if not isinstance(getattr(pluginMetadata, fieldName), str):
                raise TypeError(f'plugin metadata {fieldName} must be a string')

        if pluginId in self._plugins:
            raise ValueError(f'plugin {pluginMetadata.id!r} is already registered')

        return plugin, pluginId, pluginMetadata

    def _validateProtocolHandler(self, capability, state):
        """Validate and normalize one protocol handler."""
        descriptor = capability.descriptor

        if not isinstance(descriptor, ProtocolDescriptor):
            raise TypeError('protocol handlers must expose a ProtocolDescriptor value')

        protocolId = _normalizeIdentifier(descriptor.id)

        if not protocolId:
            raise ValueError('protocol ID cannot be empty')

        if not isinstance(descriptor.displayName, str):
            raise TypeError('protocol display name must be a string')

        if not isinstance(descriptor.addActionText, str):
            raise TypeError('protocol add-action text must be a string')

        if not isinstance(descriptor.editorWindowTitle, str):
            raise TypeError('protocol editor-window title must be a string')

        if not isinstance(descriptor.configurationSchema, Mapping):
            raise TypeError('protocol configuration schema must be a mapping')

        if not isinstance(descriptor.translatable, bool):
            raise TypeError('protocol translatable flag must be a boolean')

        if not isinstance(descriptor.subscriptionImportable, bool):
            raise TypeError('protocol subscription-importable flag must be a boolean')

        if protocolId in self._protocols or protocolId in state.protocolIds:
            raise ValueError(f'protocol {descriptor.id!r} is already registered')

        schemes = tuple(_normalizeScheme(scheme) for scheme in capability.schemes)

        if any(not scheme for scheme in schemes):
            raise ValueError(f'protocol {descriptor.id!r} has an empty URI scheme')

        for scheme in schemes:
            if scheme in self._schemes or scheme in state.schemes:
                raise ValueError(f'URI scheme {scheme!r} is already registered')

        state.protocolIds.add(protocolId)
        state.schemes.update(schemes)

        return protocolId, schemes

    def _validateProtocolEditor(self, capability, state):
        """Validate and normalize one protocol-editor provider."""
        protocolIds = tuple(
            _normalizeIdentifier(value) for value in capability.protocolIds
        )

        if not protocolIds or any(not value for value in protocolIds):
            raise ValueError('protocol editor providers must declare protocol IDs')

        for protocolId in protocolIds:
            if (
                protocolId in self._protocolEditors
                or protocolId in state.editorProtocols
            ):
                raise ValueError(
                    f'protocol {protocolId!r} already has an editor provider'
                )

        state.editorProtocols.update(protocolIds)

        return protocolIds

    @staticmethod
    def _validateDisjointTypes(values, label, existing, local):
        """Validate a capability's class types against global and local indexes."""
        for itemType in values:
            if not isinstance(itemType, type):
                raise TypeError(f'core runtime factory {label} types must be classes')

            if any(
                issubclass(itemType, registeredType)
                or issubclass(registeredType, itemType)
                for registeredType in (*existing, *local)
            ):
                raise ValueError(
                    f'{label} type {itemType.__name__!r} overlaps a registered type'
                )

            local.append(itemType)

    def _validateCoreRuntimeFactory(self, capability, state):
        """Validate and normalize one core-runtime factory."""
        configurationTypes = tuple(capability.configurationTypes)
        runtimeTypes = _runtimeTypes(capability)

        if not configurationTypes:
            raise ValueError(
                f'core runtime factory {capability.factoryId!r} must declare '
                f'configuration types'
            )

        self._validateDisjointTypes(
            configurationTypes,
            'configuration',
            tuple(self._configurationFactories),
            state.configurationTypes,
        )
        self._validateDisjointTypes(
            runtimeTypes,
            'runtime',
            tuple(self._runtimeFactories),
            state.runtimeTypes,
        )

        return configurationTypes, runtimeTypes

    def _validateTrafficStatsProvider(self, capability, state):
        """Validate and normalize one runtime traffic-statistics provider."""
        runtimeTypes = _runtimeTypes(capability)

        if not runtimeTypes:
            raise ValueError(
                f'traffic stats provider {capability.providerId!r} must '
                f'declare runtime types'
            )

        for runtimeType in runtimeTypes:
            if not isinstance(runtimeType, type):
                raise TypeError('traffic stats provider runtime types must be classes')

            if any(
                issubclass(runtimeType, registeredType)
                or issubclass(registeredType, runtimeType)
                for registeredType in (
                    *self._trafficStatsProviders,
                    *state.trafficStatsRuntimeTypes,
                )
            ):
                raise ValueError(
                    f'traffic stats runtime type '
                    f'{runtimeType.__name__!r} overlaps a registered type'
                )

            state.trafficStatsRuntimeTypes.append(runtimeType)

        return runtimeTypes

    @staticmethod
    def _validateSubscriptionDecoder(capability):
        """Validate one subscription decoder."""
        if not isinstance(capability.priority, int):
            raise TypeError('subscription decoder priority must be an integer')

    def _validateCapability(self, capability, state):
        """Validate one capability and return normalized registration data."""
        if not isinstance(capability, PluginCapability):
            raise TypeError('plugin capabilities must contain PluginCapability values')

        kind = self._kind(capability)
        capabilityId = self._id(capability)
        key = (kind, capabilityId)

        if capabilityId in self._capabilities[kind] or key in state.capabilityIds:
            raise ValueError(
                f'{kind.value} capability {capability.capabilityId!r} '
                f'is already registered'
            )

        state.capabilityIds.add(key)

        if isinstance(capability, ProtocolHandler):
            detail = self._validateProtocolHandler(capability, state)
        elif isinstance(capability, ProtocolEditorProvider):
            detail = self._validateProtocolEditor(capability, state)
        elif isinstance(capability, CoreRuntimeFactory):
            detail = self._validateCoreRuntimeFactory(capability, state)
        elif isinstance(capability, TrafficStatsProvider):
            detail = self._validateTrafficStatsProvider(capability, state)
        elif isinstance(capability, SubscriptionDecoder):
            self._validateSubscriptionDecoder(capability)
            detail = None
        else:
            detail = None

        return kind, capabilityId, capability, detail

    def _validatePlugin(self, plugin):
        """Validate *plugin* and return normalized registration data."""
        plugin, pluginId, pluginMetadata = self._validatePluginMetadata(plugin)
        capabilities = tuple(plugin.declaredCapabilities())
        state = _PluginValidationState()
        entries = tuple(
            self._validateCapability(capability, state) for capability in capabilities
        )

        return plugin, pluginId, pluginMetadata, entries

    def register(self, plugin: FuriousPlugin):
        """Register, index, and initialize one plugin atomically."""
        if self._closed:
            raise RuntimeError('plugin registry has already been shut down')

        plugin, pluginId, pluginMetadata, entries = self._validatePlugin(plugin)

        self._plugins[pluginId] = plugin
        self._metadata[pluginId] = pluginMetadata

        for kind, capabilityId, capability, detail in entries:
            entry = (plugin, capability)

            self._capabilities[kind][capabilityId] = entry
            self._capabilityEntries.append((kind, entry))

            if isinstance(capability, ProtocolHandler):
                protocolId, schemes = detail

                self._protocols[protocolId] = entry
                self._protocolEntries.append(entry)

                for scheme in schemes:
                    self._schemes[scheme] = entry
            elif isinstance(capability, ProtocolEditorProvider):
                self._editors[capabilityId] = entry

                for protocolId in detail:
                    self._protocolEditors[protocolId] = entry
            elif isinstance(capability, CoreRuntimeFactory):
                configurationTypes, runtimeTypes = detail

                self._factories[capabilityId] = entry

                for configType in configurationTypes:
                    self._configurationFactories[configType] = entry
                for runtimeType in runtimeTypes:
                    self._runtimeFactories[runtimeType] = entry
            elif isinstance(capability, TrafficStatsProvider):
                for runtimeType in detail:
                    self._trafficStatsProviders[runtimeType] = entry
            elif isinstance(capability, SubscriptionDecoder):
                self._decoders[capabilityId] = entry

        try:
            plugin.initialize(PluginContext(pluginId, self, pluginMetadata))
        except Exception:
            # Any non-exit exceptions

            try:
                plugin.shutdown()
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'plugin rollback failed for {pluginId!r}: {ex}')

            self._removePlugin(pluginId)

            raise

        self._initializedPlugins.append(plugin)

        logger.info(f'registered plugin {pluginMetadata.id!r}')

        return plugin

    def _removePlugin(self, pluginId: str):
        """Remove a partially registered plugin after initialization failure."""
        pluginId = _normalizeIdentifier(pluginId)
        plugin = self._plugins.pop(pluginId, None)
        self._metadata.pop(pluginId, None)

        if plugin is None:
            return

        self._capabilityEntries = [
            item for item in self._capabilityEntries if item[1][0] is not plugin
        ]

        for kind in CapabilityKind:
            self._capabilities[kind] = {
                key: entry
                for key, entry in self._capabilities[kind].items()
                if entry[0] is not plugin
            }

        self._protocolEntries = [
            entry for entry in self._protocolEntries if entry[0] is not plugin
        ]

        for name in (
            '_protocols',
            '_schemes',
            '_editors',
            '_protocolEditors',
            '_factories',
            '_configurationFactories',
            '_runtimeFactories',
            '_trafficStatsProviders',
            '_decoders',
        ):
            setattr(
                self,
                name,
                {
                    key: entry
                    for key, entry in getattr(self, name).items()
                    if entry[0] is not plugin
                },
            )

    def plugins(self):
        """Return initialized plugins in registration order."""
        return tuple(self._plugins.values())

    def plugin(self, pluginId: str):
        """Return the plugin registered with *pluginId*, if any."""
        return self._plugins.get(_normalizeIdentifier(pluginId))

    def metadataFor(self, plugin) -> Optional[PluginMetadata]:
        """Return normalized metadata for a registered plugin."""
        if isinstance(plugin, FuriousPlugin):
            plugin = plugin.pluginMetadata().id

        return self._metadata.get(_normalizeIdentifier(plugin))

    def capabilities(self, kind=None, plugin=None):
        """Return capabilities, optionally filtered by kind and plugin."""
        normalizedKind = CapabilityKind(kind) if kind is not None else None

        if plugin is not None and not isinstance(plugin, FuriousPlugin):
            plugin = self.plugin(plugin)

            if plugin is None:
                return tuple()

        return tuple(
            capability
            for entryKind, (owner, capability) in self._capabilityEntries
            if (normalizedKind is None or entryKind == normalizedKind)
            and (plugin is None or owner is plugin)
        )

    def capability(self, kind, capabilityId):
        """Return one capability by kind and identifier."""
        entry = self._capabilities[CapabilityKind(kind)].get(
            _normalizeIdentifier(capabilityId)
        )

        return entry[1] if entry is not None else None

    def pluginsWithCapability(self, kind):
        """Return plugins contributing at least one capability of *kind*."""
        kind = CapabilityKind(kind)
        owners = {id(owner) for owner, _capability in self._capabilities[kind].values()}

        return tuple(plugin for plugin in self.plugins() if id(plugin) in owners)

    def protocolDescriptors(self):
        """Return protocol descriptors in their requested menu order."""
        descriptors = [handler.descriptor for _plugin, handler in self._protocolEntries]

        return tuple(sorted(descriptors, key=lambda value: value.menuOrder))

    def protocolHandlers(self):
        """Return registered protocol handlers in registration order."""
        return self.capabilities(CapabilityKind.Protocol)

    def actionProviders(self):
        """Return registered plugin action providers."""
        return self.capabilities(CapabilityKind.ActionProvider)

    def protocolEditors(self):
        """Return registered protocol editor providers."""
        return self.capabilities(CapabilityKind.ProtocolEditor)

    def coreRuntimeFactories(self):
        """Return registered core-runtime factories."""
        return self.capabilities(CapabilityKind.CoreRuntimeFactory)

    def subscriptionDecoders(self):
        """Return subscription decoders in auto-detection priority order."""
        return tuple(
            sorted(
                self.capabilities(CapabilityKind.SubscriptionDecoder),
                key=lambda decoder: decoder.priority,
                reverse=True,
            )
        )

    def trafficStatsProviders(self):
        """Return registered runtime traffic-statistics providers."""
        return self.capabilities(CapabilityKind.TrafficStats)

    def pluginSettingsProviders(self):
        """Return providers contributing host-rendered settings sections."""
        return self.capabilities(CapabilityKind.PluginSettings)

    def navigationPageProviders(self):
        """Return providers contributing application navigation pages."""
        return self.capabilities(CapabilityKind.NavigationPage)

    def handlerForProtocol(self, protocol):
        """Return the handler registered for a protocol identifier."""
        entry = self._protocols.get(_normalizeIdentifier(protocol))

        return entry[1] if entry is not None else None

    def handlerForConfig(self, config):
        """Return the unique protocol handler that owns *config*."""
        config = _connectionOf(config)
        matches = []

        for _plugin, handler in self._protocolEntries:
            try:
                if handler.supports(config):
                    matches.append(handler)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'protocol ownership check failed for '
                    f'{handler.descriptor.id!r}: {ex}'
                )

        if len(matches) > 1:
            names = ', '.join(repr(handler.descriptor.id) for handler in matches)

            raise ValueError(f'configuration is claimed by multiple protocols: {names}')

        return matches[0] if matches else None

    def editorForProtocol(self, protocol):
        """Return the editor provider registered for *protocol*."""
        entry = self._protocolEditors.get(_normalizeIdentifier(protocol))

        return entry[1] if entry is not None else None

    def factoryForConfig(self, config):
        """Return the runtime factory whose configuration type matches *config*."""
        config = _connectionOf(config)

        for configType, (_plugin, factory) in self._configurationFactories.items():
            if isinstance(config, configType):
                return factory

        return None

    def runtimeFactoryFor(self, runtime):
        """Return the factory that owns *runtime*."""
        for runtimeType, (_plugin, factory) in self._runtimeFactories.items():
            if isinstance(runtime, runtimeType):
                return factory

        return None

    def trafficStatsProviderForRuntime(self, runtime):
        """Return the traffic-statistics provider that owns *runtime*."""
        for runtimeType, (_plugin, provider) in self._trafficStatsProviders.items():
            if isinstance(runtime, runtimeType):
                return provider

        return None

    def trafficStatsMonitorForRuntimes(self, runtimes):
        """Return the first monitor available for the active core runtimes."""
        for runtime in runtimes:
            provider = self.trafficStatsProviderForRuntime(runtime)

            if provider is None:
                continue

            try:
                monitor = provider.monitorForRuntime(runtime)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'failed to obtain traffic stats monitor from '
                    f'{provider.providerId!r}: {ex}'
                )

                continue

            if monitor is None:
                continue

            if not isinstance(monitor, TrafficStatsMonitor):
                logger.error(
                    f'traffic stats provider {provider.providerId!r} returned '
                    f'an invalid monitor'
                )

                continue

            if not callable(monitor.query):
                logger.error(
                    f'traffic stats provider {provider.providerId!r} returned '
                    f'a monitor without a query callable'
                )

                continue

            return monitor

        return None

    def pluginForProtocol(self, protocol):
        """Return the plugin that contributes *protocol*."""
        entry = self._protocols.get(_normalizeIdentifier(protocol))

        return entry[0] if entry is not None else None

    def pluginForConfig(self, config):
        """Return the plugin contributing the owning factory or protocol."""
        config = _connectionOf(config)

        for configType, (plugin, _factory) in self._configurationFactories.items():
            if isinstance(config, configType):
                return plugin

        handler = self.handlerForConfig(config)

        return (
            self.pluginForProtocol(handler.descriptor.id)
            if handler is not None
            else None
        )

    def pluginForRuntime(self, runtime):
        """Return the plugin that contributes a runtime's factory."""
        for runtimeType, (plugin, _factory) in self._runtimeFactories.items():
            if isinstance(runtime, runtimeType):
                return plugin

        return None

    def parseURI(self, uri: str, **kwargs):
        """Parse a URI and keep connection data separate from profile metadata."""
        entry = self._schemes.get(_schemeFromURI(uri))

        if entry is None:
            return None

        _plugin, handler = entry

        try:
            result = handler.parse(uri, **kwargs)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'failed to parse {handler.descriptor.id!r} configuration: {ex}. '
                f'URI: {uri!r}'
            )

            return None

        if result is None:
            return None

        if not isinstance(result, ProtocolParseResult):
            logger.error(
                f'protocol handler {handler.descriptor.id!r} returned an '
                f'invalid parse result'
            )

            return None

        try:
            owned = handler.supports(result.configuration)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'protocol ownership check failed for '
                f'{handler.descriptor.id!r}: {ex}'
            )

            return None

        if not owned:
            logger.error(
                f'protocol handler {handler.descriptor.id!r} returned a '
                f'configuration it does not own'
            )

            return None

        return result

    def configFromDict(self, config: dict, **kwargs):
        """Recognize a normalized mapping through registered capabilities."""
        matches = []

        for _plugin, handler in self._protocolEntries:
            try:
                result = handler.fromMapping(config, **kwargs)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'failed to recognize {handler.descriptor.id!r} mapping: {ex}'
                )

                continue

            if result is not None:
                try:
                    owned = handler.supports(result)
                except Exception as ex:
                    # Any non-exit exceptions

                    logger.error(
                        f'protocol ownership check failed for '
                        f'{handler.descriptor.id!r}: {ex}'
                    )

                    continue

                if not owned:
                    logger.error(
                        f'protocol handler {handler.descriptor.id!r} returned '
                        f'an unowned mapping result'
                    )

                    continue

                matches.append((handler, result))

        if len(matches) > 1:
            names = ', '.join(repr(item[0].descriptor.id) for item in matches)

            raise ValueError(f'configuration mapping is ambiguous: {names}')

        if matches:
            return matches[0][1]

        factoryMatches = []

        for _plugin, factory in self._factories.values():
            try:
                result = factory.fromMapping(config, **kwargs)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'failed to recognize {factory.factoryId!r} mapping: {ex}')

                continue

            if result is not None:
                if not isinstance(result, factory.configurationTypes):
                    logger.error(
                        f'core runtime factory {factory.factoryId!r} returned an '
                        f'unowned mapping result'
                    )

                    continue

                factoryMatches.append((factory, result))

        if len(factoryMatches) > 1:
            names = ', '.join(repr(item[0].factoryId) for item in factoryMatches)

            raise ValueError(
                f'core runtime configuration mapping is ambiguous: {names}'
            )

        return factoryMatches[0][1] if factoryMatches else None

    def blankConfig(self, protocol, **kwargs):
        """Create a blank configuration through an exact protocol handler."""
        handler = self.handlerForProtocol(protocol)

        if handler is None:
            return None

        try:
            result = handler.blank(**kwargs)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'failed to create blank {handler.descriptor.id!r} configuration: '
                f'{ex}'
            )

            return None

        if result is not None:
            try:
                if handler.supports(result):
                    return result
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'protocol ownership check failed for '
                    f'{handler.descriptor.id!r}: {ex}'
                )

                return None

        logger.error(
            f'protocol handler {handler.descriptor.id!r} returned an unowned '
            f'blank configuration'
        )

        return None

    def exportConfig(self, config, remark: str = '') -> str:
        """Export a configuration through its owning protocol handler."""
        handler = self.handlerForConfig(config)

        if handler is None:
            return ''

        if not remark:
            remark = str(getattr(config, 'itemRemark', ''))

        return handler.exportProfile(config, remark)

    def validateConfig(self, config):
        """Validate a configuration through its protocol capability."""
        handler = self.handlerForConfig(config)

        return (
            tuple(handler.validate(_connectionOf(config)))
            if handler is not None
            else ('Unsupported protocol',)
        )

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create an editor through an exact editor-provider capability."""
        protocolId = _normalizeIdentifier(protocol)
        provider = self.editorForProtocol(protocolId)

        return (
            provider.createEditor(protocolId, parent=parent, **kwargs)
            if provider is not None
            else None
        )

    def createEditorForConfig(self, config, parent=None, **kwargs):
        """Create an editor for a configuration through capability discovery."""
        handler = self.handlerForConfig(config)

        return (
            self.createEditorForProtocol(handler.descriptor.id, parent, **kwargs)
            if handler is not None
            else None
        )

    def managementActions(self, plugin, parent=None, **kwargs):
        """Aggregate management actions from one plugin's action providers."""
        if not isinstance(plugin, FuriousPlugin):
            plugin = self.plugin(plugin)

        if plugin is None or self.plugin(plugin.pluginMetadata().id) is not plugin:
            raise ValueError('plugin is not registered')

        actions = []

        for provider in self.capabilities(CapabilityKind.ActionProvider, plugin):
            try:
                actions.extend(provider.createActions(parent=parent, **kwargs))
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'failed to create management actions for '
                    f'{provider.providerId!r}: {ex}'
                )

        return tuple(actions)

    def prepareTUN(self, config) -> bool:
        """Ask a configuration's factory to prepare native TUN support."""
        factory = self.factoryForConfig(config)

        if factory is None:
            return False

        try:
            handled = factory.prepareTUN(_connectionOf(config))

            if not isinstance(handled, bool):
                raise TypeError('core runtime TUN preparation result must be a boolean')

            return handled
        except TUNPreparationError:
            # A managed native-TUN request must fail the connection rather than
            # silently changing the user's selected networking implementation.
            raise
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'TUN preparation failed for {factory.factoryId!r}: {ex}')

            return False

    def usesApplicationTun2socks(self, config) -> bool:
        """Return whether a configuration opts into host-managed tun2socks."""
        factory = self.factoryForConfig(config)

        if factory is None:
            return True

        try:
            enabled = factory.usesApplicationTun2socks(_connectionOf(config))

            if not isinstance(enabled, bool):
                raise TypeError(
                    'core runtime application tun2socks result must be a boolean'
                )

            return enabled
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'application tun2socks capability check failed for '
                f'{factory.factoryId!r}: {ex}'
            )

            return False

    def routingOptions(self, config):
        """Return validated routing modes from a configuration's factory."""
        factory = self.factoryForConfig(config)

        if factory is None:
            return tuple()

        try:
            options = tuple(factory.routingOptions(_connectionOf(config)))
            optionIds = set()

            for option in options:
                if not isinstance(option, RoutingOption):
                    raise TypeError(
                        'core runtime routing options must be RoutingOption values'
                    )

                if not isinstance(option.id, str) or not option.id.strip():
                    raise ValueError('routing option ID must be a non-empty string')

                if not isinstance(option.displayName, str):
                    raise TypeError('routing option display name must be a string')

                if not isinstance(option.translatable, bool):
                    raise TypeError('routing translatable flag must be a boolean')

                if option.id in optionIds:
                    raise ValueError(
                        f'routing option {option.id!r} is already registered'
                    )

                optionIds.add(option.id)

            return options
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'failed to obtain routing options for {factory.factoryId!r}: {ex}'
            )

            return tuple()

    def normalizeRouting(self, config, routing):
        """Return a supported routing value or the factory's first option."""
        options = self.routingOptions(config)

        if not options:
            return routing

        optionIds = tuple(option.id for option in options)

        return routing if routing in optionIds else optionIds[0]

    def createCoreRuntime(self, config, routing, **kwargs):
        """Create a prepared core-runtime launch for *config*."""
        factory = self.factoryForConfig(config)

        if factory is None:
            return None

        request = CoreRuntimeRequest(
            configuration=_connectionOf(config),
            routing=self.normalizeRouting(config, routing),
            exitCallback=kwargs.pop('exitCallback', None),
            messageCallback=kwargs.pop('messageCallback', None),
            proxyModeOnly=kwargs.pop('proxyModeOnly', False),
            log=kwargs.pop('log', True),
            options=kwargs,
        )
        launch = factory.create(request)

        if launch is None:
            return None

        if not isinstance(launch, CoreRuntimeLaunch):
            raise TypeError(
                'core runtime factory must return a CoreRuntimeLaunch value'
            )

        runtimeTypes = _runtimeTypes(factory)

        if runtimeTypes and not isinstance(launch.runtime, runtimeTypes):
            raise TypeError(
                f'core runtime factory {factory.factoryId!r} returned an '
                f'unowned runtime'
            )

        return launch

    def startCoreRuntime(self, config, routing, **kwargs):
        """Create and start the core runtime selected for *config*."""
        try:
            launch = self.createCoreRuntime(config, routing, **kwargs)

            return (
                (launch.runtime, launch.start())
                if launch is not None
                else (None, False)
            )
        except Exception as ex:
            # Any non-exit exceptions

            factory = self.factoryForConfig(config)
            factoryId = factory.factoryId if factory is not None else 'unknown'

            logger.error(f'core runtime start failed for {factoryId!r}: {ex}')

            return None, False

    def prepareDownloadTest(self, config, port: int):
        """Create a proxy-only test configuration through its runtime factory."""
        factory = self.factoryForConfig(config)

        return (
            factory.prepareDownloadTest(_connectionOf(config), port)
            if factory is not None
            else None
        )

    def decodeSubscription(self, data: bytes, decoderId=None):
        """Decode subscription bytes using an explicit or detected decoder."""
        if not isinstance(data, bytes):
            raise TypeError('subscription payload must be bytes')

        if decoderId:
            entry = self._decoders.get(_normalizeIdentifier(decoderId))
            candidates = (entry,) if entry is not None else tuple()
        else:
            candidates = tuple(
                sorted(
                    self._decoders.values(),
                    key=lambda value: value[1].priority,
                    reverse=True,
                )
            )

        for _plugin, decoder in candidates:
            try:
                result = decoder.decode(data)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'subscription decoder {decoder.decoderId!r} failed: {ex}')

                continue

            if result is None:
                continue

            if not isinstance(result, SubscriptionResult):
                logger.error(
                    f'subscription decoder {decoder.decoderId!r} returned an '
                    f'invalid result'
                )

                continue

            if _normalizeIdentifier(result.decoderId) != _normalizeIdentifier(
                decoder.decoderId
            ) or any(not isinstance(item, SubscriptionItem) for item in result.items):
                logger.error(
                    f'subscription decoder {decoder.decoderId!r} returned '
                    f'inconsistent metadata'
                )

                continue

            return result

        return None

    def configureEnvironment(self):
        """Allow every runtime factory to configure its execution environment."""
        for factory in self.coreRuntimeFactories():
            try:
                factory.configureEnvironment()
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'environment hook failed for {factory.factoryId!r}: {ex}')

    def coreVersions(self):
        """Return version strings reported by every core-runtime factory."""
        versions = []

        for factory in self.coreRuntimeFactories():
            try:
                versions.extend(factory.coreVersions())
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'failed to obtain core versions for {factory.factoryId!r}: {ex}'
                )

        return tuple(filter(None, versions))

    def logTimestampPatterns(self):
        """Return timestamp expressions contributed by runtime factories."""
        patterns = []

        for factory in self.coreRuntimeFactories():
            try:
                patterns.extend(factory.logTimestampPatterns())
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'failed to obtain log patterns for {factory.factoryId!r}: {ex}'
                )

        return tuple(filter(None, patterns))

    def coreExitMessage(self, core, exitcode: int):
        """Return the owning factory's special exit message, if any."""
        factory = self.runtimeFactoryFor(core)

        if factory is None:
            return None

        try:
            return factory.coreExitMessage(core, exitcode)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'failed to interpret core exit for {factory.factoryId!r}: {ex}'
            )

            return None

    def afterConnected(self, httpProxy=None):
        """Notify every core-runtime factory after a connection succeeds."""
        for factory in self.coreRuntimeFactories():
            try:
                factory.afterConnected(httpProxy)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'post-connection hook failed for {factory.factoryId!r}: {ex}'
                )

    def discover(self):
        """Load trusted third-party plugins exposed through entry points."""
        try:
            entryPoints = metadata.entry_points()

            if hasattr(entryPoints, 'select'):
                entryPoints = entryPoints.select(group=PLUGIN_ENTRY_POINT_GROUP)
            else:
                entryPoints = entryPoints.get(PLUGIN_ENTRY_POINT_GROUP, tuple())
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'failed to enumerate Furious plugins: {ex}')

            return

        for entryPoint in entryPoints:
            try:
                plugin = entryPoint.load()

                if isinstance(plugin, type) and issubclass(plugin, FuriousPlugin):
                    plugin = plugin()
                elif callable(plugin) and not isinstance(plugin, FuriousPlugin):
                    plugin = plugin()

                if isinstance(plugin, (tuple, list)):
                    for item in plugin:
                        self.register(item)
                else:
                    self.register(plugin)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'failed to load plugin {entryPoint.name!r}: {ex}')

    def shutdown(self):
        """Shut down initialized plugins in reverse registration order once."""
        if self._closed:
            return

        self._closed = True

        for plugin in reversed(self._initializedPlugins):
            try:
                plugin.shutdown()
            except Exception as ex:
                # Any non-exit exceptions

                pluginMetadata = plugin.pluginMetadata()

                logger.error(f'plugin shutdown failed for {pluginMetadata.id!r}: {ex}')

        self._initializedPlugins.clear()


class _PluginRegistryManager:
    """Own lazy creation of the process-wide plugin registry."""

    def __init__(self):
        """Initialize an empty process-registry owner."""
        self._registry: Optional[PluginRegistry] = None
        self._lock = threading.RLock()

    def initialize(self, pluginTypes=()) -> PluginRegistry:
        """Return the registry after discovering and reconciling plugins."""
        with self._lock:
            registry = self._registry

            if registry is None:
                registry = self._createRegistry(pluginTypes)

                self._registry = registry
            else:
                self._registerAdditionalPluginTypes(registry, pluginTypes)

            return registry

    @staticmethod
    def _createRegistry(pluginTypes) -> PluginRegistry:
        """Build a registry with host plugins taking discovery precedence."""
        registry = PluginRegistry()

        for pluginType in pluginTypes:
            registry.register(pluginType())

        registry.discover()

        return registry

    @staticmethod
    def _registerAdditionalPluginTypes(registry, pluginTypes):
        """Idempotently add host plugin types supplied after discovery."""
        for pluginType in pluginTypes:
            plugin = pluginType()
            pluginMetadata = plugin.pluginMetadata()

            registered = registry.plugin(pluginMetadata.id)

            if registered is None:
                registry.register(plugin)
            elif not isinstance(registered, pluginType):
                raise ValueError(
                    f'plugin {pluginMetadata.id!r} is already registered by '
                    f'{type(registered).__name__}'
                )


_registryManager = _PluginRegistryManager()


def initializePluginRegistry(pluginTypes=()) -> PluginRegistry:
    """Discover third-party plugins and register host-provided plugin types."""
    return _registryManager.initialize(pluginTypes)


def getPluginRegistry() -> PluginRegistry:
    """Return the process-wide registry, discovering external plugins lazily."""
    return initializePluginRegistry()


def registerPlugin(plugin: FuriousPlugin):
    """Register a plugin programmatically and return it."""
    return getPluginRegistry().register(plugin)
