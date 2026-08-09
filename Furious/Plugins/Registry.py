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

"""Discover plugins and index their independently usable capabilities."""

from __future__ import annotations

from importlib import metadata
from urllib.parse import urlsplit

import logging
import threading

from .API import *

__all__ = [
    'PLUGIN_ENTRY_POINT_GROUP',
    'PluginRegistry',
    'getPluginRegistry',
    'initializePluginRegistry',
    'registerPlugin',
]

PLUGIN_ENTRY_POINT_GROUP = 'furious.plugins'

logger = logging.getLogger(__name__)


def _normalizeIdentifier(value) -> str:
    """Return a case-insensitive capability identifier."""
    return str(getattr(value, 'value', value)).strip().casefold()


def _normalizeScheme(value) -> str:
    """Return a URI scheme without punctuation."""
    return str(value).strip().rstrip(':').casefold()


def _schemeFromURI(uri: str) -> str:
    """Extract a normalized scheme from *uri*."""
    try:
        return _normalizeScheme(urlsplit(uri.strip()).scheme)
    except Exception:
        return ''


class PluginRegistry:
    """Own plugin lifecycle and dispatch through indexed capabilities."""

    def __init__(self):
        """Initialize an empty capability registry."""
        self._plugins = {}
        self._protocols = {}
        self._schemes = {}
        self._protocolEntries = []
        self._backends = {}
        self._configurationBackends = {}
        self._coreBackends = {}
        self._decoders = {}
        self._initializedPlugins = []
        self._closed = False

    def _validatePlugin(self, plugin):
        """Validate *plugin* and return its normalized capability metadata."""
        if isinstance(plugin, type) and issubclass(plugin, FuriousPlugin):
            plugin = plugin()

        if not isinstance(plugin, FuriousPlugin):
            raise TypeError('plugin must be a FuriousPlugin instance')

        if plugin.apiVersion != PLUGIN_API_VERSION:
            raise ValueError(
                f'plugin API {plugin.apiVersion!r} is not supported; '
                f'expected {PLUGIN_API_VERSION}'
            )

        pluginId = str(plugin.pluginId).strip()

        if not pluginId:
            raise ValueError('plugin ID cannot be empty')

        if pluginId in self._plugins:
            raise ValueError(f'plugin {pluginId!r} is already registered')

        protocols = []
        localProtocolIds = set()
        localSchemes = set()

        for handler in plugin.protocolHandlers:
            if not isinstance(handler, ProtocolHandler):
                raise TypeError(
                    'plugin protocolHandlers must contain ProtocolHandler values'
                )

            descriptor = handler.descriptor

            if not isinstance(descriptor, ProtocolDescriptor):
                raise TypeError(
                    'protocol handlers must expose a ProtocolDescriptor value'
                )

            protocolId = _normalizeIdentifier(descriptor.id)

            if not protocolId:
                raise ValueError('protocol ID cannot be empty')

            if protocolId in self._protocols or protocolId in localProtocolIds:
                raise ValueError(f'protocol {descriptor.id!r} is already registered')

            schemes = tuple(_normalizeScheme(scheme) for scheme in handler.schemes)

            if any(not scheme for scheme in schemes):
                raise ValueError(f'protocol {descriptor.id!r} has an empty URI scheme')

            for scheme in schemes:
                if scheme in self._schemes or scheme in localSchemes:
                    raise ValueError(f'URI scheme {scheme!r} is already registered')

            localProtocolIds.add(protocolId)
            localSchemes.update(schemes)
            protocols.append((protocolId, schemes, handler))

        backends = []
        localBackendIds = set()
        localConfigurationTypes = []
        localCoreTypes = []

        for backend in plugin.coreBackends:
            if not isinstance(backend, CoreBackend):
                raise TypeError('plugin coreBackends must contain CoreBackend values')

            backendId = _normalizeIdentifier(backend.backendId)

            if not backendId:
                raise ValueError('backend ID cannot be empty')

            if backendId in self._backends or backendId in localBackendIds:
                raise ValueError(f'backend {backend.backendId!r} is already registered')

            configurationTypes = tuple(backend.configurationTypes)
            coreTypes = tuple(backend.coreTypes)

            for value, label, existing, local in (
                (
                    configurationTypes,
                    'configuration',
                    tuple(self._configurationBackends),
                    localConfigurationTypes,
                ),
                (coreTypes, 'core', tuple(self._coreBackends), localCoreTypes),
            ):
                for itemType in value:
                    if not isinstance(itemType, type):
                        raise TypeError(f'backend {label} types must be classes')

                    if any(
                        issubclass(itemType, registeredType)
                        or issubclass(registeredType, itemType)
                        for registeredType in (*existing, *local)
                    ):
                        raise ValueError(
                            f'{label} type {itemType.__name__!r} overlaps a '
                            f'registered type'
                        )

                    local.append(itemType)

            localBackendIds.add(backendId)
            backends.append((backendId, backend))

        decoders = []
        localDecoderIds = set()

        for decoder in plugin.subscriptionDecoders:
            if not isinstance(decoder, SubscriptionDecoder):
                raise TypeError(
                    'plugin subscriptionDecoders must contain SubscriptionDecoder values'
                )

            decoderId = _normalizeIdentifier(decoder.decoderId)

            if not decoderId:
                raise ValueError('subscription decoder ID cannot be empty')

            if decoderId in self._decoders or decoderId in localDecoderIds:
                raise ValueError(
                    f'subscription decoder {decoder.decoderId!r} is already registered'
                )

            if not isinstance(decoder.priority, int):
                raise TypeError('subscription decoder priority must be an integer')

            localDecoderIds.add(decoderId)
            decoders.append((decoderId, decoder))

        return plugin, pluginId, protocols, backends, decoders

    def register(self, plugin: FuriousPlugin):
        """Register, index, and initialize one plugin atomically."""
        if self._closed:
            raise RuntimeError('plugin registry has already been shut down')

        plugin, pluginId, protocols, backends, decoders = self._validatePlugin(plugin)

        self._plugins[pluginId] = plugin

        for protocolId, schemes, handler in protocols:
            entry = (plugin, handler)
            self._protocols[protocolId] = entry
            self._protocolEntries.append(entry)

            for scheme in schemes:
                self._schemes[scheme] = entry

        for backendId, backend in backends:
            self._backends[backendId] = (plugin, backend)

            for configType in backend.configurationTypes:
                self._configurationBackends[configType] = (plugin, backend)
            for coreType in backend.coreTypes:
                self._coreBackends[coreType] = (plugin, backend)

        for decoderId, decoder in decoders:
            self._decoders[decoderId] = (plugin, decoder)

        try:
            plugin.initialize(PluginContext(pluginId, self))
        except Exception:
            try:
                plugin.shutdown()
            except Exception as ex:
                logger.error(f'plugin rollback failed for {pluginId!r}: {ex}')

            self._removePlugin(pluginId)
            raise

        self._initializedPlugins.append(plugin)
        logger.info(f'registered plugin {pluginId!r}')

        return plugin

    def _removePlugin(self, pluginId: str):
        """Remove a partially registered plugin after initialization failure."""
        plugin = self._plugins.pop(pluginId, None)

        if plugin is None:
            return

        self._protocolEntries = [
            entry for entry in self._protocolEntries if entry[0] is not plugin
        ]
        self._protocols = {
            key: entry
            for key, entry in self._protocols.items()
            if entry[0] is not plugin
        }
        self._schemes = {
            key: entry for key, entry in self._schemes.items() if entry[0] is not plugin
        }
        self._backends = {
            key: entry
            for key, entry in self._backends.items()
            if entry[0] is not plugin
        }
        self._configurationBackends = {
            key: entry
            for key, entry in self._configurationBackends.items()
            if entry[0] is not plugin
        }
        self._coreBackends = {
            key: entry
            for key, entry in self._coreBackends.items()
            if entry[0] is not plugin
        }
        self._decoders = {
            key: entry
            for key, entry in self._decoders.items()
            if entry[0] is not plugin
        }

    def plugins(self):
        """Return initialized plugins in registration order."""
        return tuple(self._plugins.values())

    def corePlugins(self):
        """Return plugins that contribute at least one core backend."""
        return tuple(plugin for plugin in self.plugins() if plugin.coreBackends)

    def plugin(self, pluginId: str):
        """Return the plugin registered with *pluginId*, if any."""
        return self._plugins.get(pluginId)

    def protocolDescriptors(self):
        """Return protocol descriptors in their requested menu order."""
        descriptors = [handler.descriptor for _plugin, handler in self._protocolEntries]

        return tuple(sorted(descriptors, key=lambda value: value.menuOrder))

    def protocolHandlers(self):
        """Return registered protocol handlers in registration order."""
        return tuple(handler for _plugin, handler in self._protocolEntries)

    def coreBackends(self):
        """Return registered core backends in registration order."""
        return tuple(backend for _plugin, backend in self._backends.values())

    def subscriptionDecoders(self):
        """Return subscription decoders in auto-detection priority order."""
        return tuple(
            decoder
            for _plugin, decoder in sorted(
                self._decoders.values(),
                key=lambda value: value[1].priority,
                reverse=True,
            )
        )

    def handlerForProtocol(self, protocol):
        """Return the handler registered for a protocol identifier."""
        entry = self._protocols.get(_normalizeIdentifier(protocol))

        return entry[1] if entry is not None else None

    def handlerForConfig(self, config):
        """Return the unique protocol handler that owns *config*."""
        matches = []

        for _plugin, handler in self._protocolEntries:
            try:
                if handler.supports(config):
                    matches.append(handler)
            except Exception as ex:
                logger.error(
                    f'protocol ownership check failed for '
                    f'{handler.descriptor.id!r}: {ex}'
                )

        if len(matches) > 1:
            names = ', '.join(repr(handler.descriptor.id) for handler in matches)
            raise ValueError(f'configuration is claimed by multiple protocols: {names}')

        return matches[0] if matches else None

    def pluginForProtocol(self, protocol):
        """Return the plugin that contributes *protocol*."""
        entry = self._protocols.get(_normalizeIdentifier(protocol))

        return entry[0] if entry is not None else None

    def backendForConfig(self, config):
        """Return the backend whose configuration type matches *config*."""
        for configType, (_plugin, backend) in self._configurationBackends.items():
            if isinstance(config, configType):
                return backend

        return None

    def backendForCore(self, core):
        """Return the backend that owns a running core object."""
        for coreType, (_plugin, backend) in self._coreBackends.items():
            if isinstance(core, coreType):
                return backend

        return None

    def pluginForConfig(self, config):
        """Return the plugin that contributes the owning backend or protocol."""
        for configType, (plugin, _backend) in self._configurationBackends.items():
            if isinstance(config, configType):
                return plugin

        handler = self.handlerForConfig(config)

        if handler is None:
            return None

        return self.pluginForProtocol(handler.descriptor.id)

    def pluginForCore(self, core):
        """Return the plugin that contributes the core's backend."""
        for coreType, (plugin, _backend) in self._coreBackends.items():
            if isinstance(core, coreType):
                return plugin

        return None

    def configFromString(self, config: str, **kwargs):
        """Parse a URI through its directly indexed scheme handler."""
        entry = self._schemes.get(_schemeFromURI(config))

        if entry is None:
            return None

        _plugin, handler = entry

        try:
            result = handler.parse(config, **kwargs)
        except Exception as ex:
            logger.error(
                f'failed to parse {handler.descriptor.id!r} configuration: {ex}'
            )

            return None

        if result is not None and not handler.supports(result):
            logger.error(
                f'protocol handler {handler.descriptor.id!r} returned a '
                f'configuration it does not own'
            )

            return None

        return result

    def configFromDict(self, config: dict, **kwargs):
        """Recognize a normalized configuration through protocol handlers."""
        matches = []

        for _plugin, handler in self._protocolEntries:
            try:
                result = handler.fromMapping(config, **kwargs)
            except Exception as ex:
                logger.error(
                    f'failed to recognize {handler.descriptor.id!r} mapping: {ex}'
                )
                continue

            if result is not None:
                matches.append((handler, result))

        if len(matches) > 1:
            names = ', '.join(repr(item[0].descriptor.id) for item in matches)
            raise ValueError(f'configuration mapping is ambiguous: {names}')

        if matches:
            return matches[0][1]

        backendMatches = []

        for _plugin, backend in self._backends.values():
            try:
                result = backend.fromMapping(config, **kwargs)
            except Exception as ex:
                logger.error(f'failed to recognize {backend.backendId!r} mapping: {ex}')
                continue

            if result is not None:
                backendMatches.append((backend, result))

        if len(backendMatches) > 1:
            names = ', '.join(repr(item[0].backendId) for item in backendMatches)
            raise ValueError(f'backend configuration mapping is ambiguous: {names}')

        return backendMatches[0][1] if backendMatches else None

    def blankConfig(self, protocol, **kwargs):
        """Create a blank configuration through an exact protocol handler."""
        handler = self.handlerForProtocol(protocol)

        return handler.blank(**kwargs) if handler is not None else None

    def exportConfig(self, config, remark: str = '') -> str:
        """Export a configuration through its owning protocol handler."""
        handler = self.handlerForConfig(config)

        return handler.export(config, remark) if handler is not None else ''

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create an editor through an exact protocol handler."""
        handler = self.handlerForProtocol(protocol)

        return (
            handler.createEditor(parent=parent, **kwargs)
            if handler is not None
            else None
        )

    def createEditorForConfig(self, config, parent=None, **kwargs):
        """Create an editor through the configuration's protocol handler."""
        handler = self.handlerForConfig(config)

        return (
            handler.createEditor(parent=parent, **kwargs)
            if handler is not None
            else None
        )

    def managementActions(self, plugin, parent=None, **kwargs):
        """Aggregate management actions from one plugin's core backends."""
        if self._plugins.get(plugin.pluginId) is not plugin:
            raise ValueError(f'plugin {plugin.pluginId!r} is not registered')

        actions = []

        for backend in plugin.coreBackends:
            try:
                actions.extend(backend.createManagementActions(parent=parent, **kwargs))
            except Exception as ex:
                logger.error(
                    f'failed to create management actions for '
                    f'{backend.backendId!r}: {ex}'
                )

        return tuple(actions)

    def prepareTUN(self, config) -> bool:
        """Ask a configuration's backend to prepare native TUN support."""
        backend = self.backendForConfig(config)

        if backend is None:
            return False

        try:
            handled = backend.prepareTUN(config)

            if not isinstance(handled, bool):
                raise TypeError('backend TUN preparation result must be a boolean')

            return handled
        except Exception as ex:
            logger.error(f'TUN preparation failed for {backend.backendId!r}: {ex}')

            return False

    def routingOptions(self, config):
        """Return validated routing modes from a configuration's backend."""
        backend = self.backendForConfig(config)

        if backend is None:
            return tuple()

        try:
            options = tuple(backend.routingOptions(config))
            optionIds = set()

            for option in options:
                if not isinstance(option, RoutingOption):
                    raise TypeError(
                        'backend routing options must be RoutingOption values'
                    )

                if not isinstance(option.id, str) or not option.id.strip():
                    raise ValueError('routing option ID must be a non-empty string')

                if not isinstance(option.displayName, str):
                    raise TypeError('routing option display name must be a string')

                if not isinstance(option.translatable, bool):
                    raise TypeError(
                        'routing option translatable flag must be a boolean'
                    )

                if option.id in optionIds:
                    raise ValueError(
                        f'routing option {option.id!r} is already registered'
                    )

                optionIds.add(option.id)

            return options
        except Exception as ex:
            logger.error(
                f'failed to obtain routing options for {backend.backendId!r}: {ex}'
            )

            return tuple()

    def normalizeRouting(self, config, routing):
        """Return a supported routing value or the backend's first option."""
        options = self.routingOptions(config)

        if not options:
            return routing

        optionIds = tuple(option.id for option in options)

        return routing if routing in optionIds else optionIds[0]

    def decodeSubscription(self, data: bytes, decoderId=None):
        """Decode subscription bytes using an explicit or auto-detected decoder."""
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
        """Allow every backend to configure its process environment."""
        for _plugin, backend in self._backends.values():
            try:
                backend.configureEnvironment()
            except Exception as ex:
                logger.error(f'environment hook failed for {backend.backendId!r}: {ex}')

    def coreVersions(self):
        """Return version strings reported by every registered backend."""
        versions = []

        for _plugin, backend in self._backends.values():
            try:
                versions.extend(backend.coreVersions())
            except Exception as ex:
                logger.error(
                    f'failed to obtain core versions for {backend.backendId!r}: {ex}'
                )

        return tuple(filter(None, versions))

    def logTimestampPatterns(self):
        """Return timestamp expressions contributed by all backends."""
        patterns = []

        for _plugin, backend in self._backends.values():
            try:
                patterns.extend(backend.logTimestampPatterns())
            except Exception as ex:
                logger.error(
                    f'failed to obtain log patterns for {backend.backendId!r}: {ex}'
                )

        return tuple(filter(None, patterns))

    def coreExitMessage(self, core, exitcode: int):
        """Return the owning backend's special exit message, if any."""
        backend = self.backendForCore(core)

        if backend is None:
            return None

        try:
            return backend.coreExitMessage(core, exitcode)
        except Exception as ex:
            logger.error(
                f'failed to interpret core exit for {backend.backendId!r}: {ex}'
            )

            return None

    def afterConnected(self, httpProxy=None):
        """Notify every backend after a connection succeeds."""
        for _plugin, backend in self._backends.values():
            try:
                backend.afterConnected(httpProxy)
            except Exception as ex:
                logger.error(
                    f'post-connection hook failed for {backend.backendId!r}: {ex}'
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
                logger.error(f'plugin shutdown failed for {plugin.pluginId!r}: {ex}')

        self._initializedPlugins.clear()


_registry = PluginRegistry()
_registryLock = threading.RLock()
_registryInitialized = False


def initializePluginRegistry(pluginTypes=()) -> PluginRegistry:
    """Discover third-party plugins and register host-provided plugin types."""
    global _registry, _registryInitialized

    with _registryLock:
        if not _registryInitialized:
            registry = PluginRegistry()

            for pluginType in pluginTypes:
                registry.register(pluginType())

            registry.discover()
            _registry = registry
            _registryInitialized = True
        else:
            for pluginType in pluginTypes:
                plugin = pluginType()
                registered = _registry.plugin(plugin.pluginId)

                if registered is None:
                    _registry.register(plugin)
                elif not isinstance(registered, pluginType):
                    raise ValueError(
                        f'plugin {plugin.pluginId!r} is already registered by '
                        f'{type(registered).__name__}'
                    )

    return _registry


def getPluginRegistry() -> PluginRegistry:
    """Return the process-wide registry, discovering external plugins lazily."""
    return initializePluginRegistry()


def registerPlugin(plugin: FuriousPlugin):
    """Register a plugin programmatically and return it."""
    return getPluginRegistry().register(plugin)
