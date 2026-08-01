"""Register official plugins and discover third-party Furious plugins."""

from __future__ import annotations

from importlib import metadata

import logging
import threading

from .API import PLUGIN_API_VERSION, FuriousPlugin, PluginProtocol, PluginRouting

__all__ = [
    'PLUGIN_ENTRY_POINT_GROUP',
    'PluginRegistry',
    'getPluginRegistry',
    'registerPlugin',
]

PLUGIN_ENTRY_POINT_GROUP = 'furious.plugins'

logger = logging.getLogger(__name__)


def _normalizeProtocol(protocol) -> str:
    """Return a case-insensitive protocol identifier."""
    value = getattr(protocol, 'value', protocol)

    return str(value).strip().casefold()


class PluginRegistry:
    """Store plugins and route host operations to the owning plugin."""

    def __init__(self):
        """Initialize an empty plugin registry."""
        self._plugins = {}
        self._protocols = {}
        self._configurationTypes = {}
        self._coreTypes = {}

    def register(self, plugin: FuriousPlugin):
        """Register a plugin after validating all of its public identifiers."""
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

        protocolKeys = []
        for descriptor in plugin.protocols:
            if not isinstance(descriptor, PluginProtocol):
                raise TypeError('plugin protocols must contain PluginProtocol values')

            key = _normalizeProtocol(descriptor.id)
            if not key:
                raise ValueError('plugin protocol ID cannot be empty')
            if key in self._protocols or key in protocolKeys:
                raise ValueError(f'protocol {descriptor.id!r} is already registered')

            protocolKeys.append(key)

        configurationTypes = []
        for configType in plugin.configurationTypes:
            if not isinstance(configType, type):
                raise TypeError('plugin configuration types must be classes')
            if any(
                issubclass(configType, registeredType)
                or issubclass(registeredType, configType)
                for registeredType in (
                    *self._configurationTypes,
                    *configurationTypes,
                )
            ):
                raise ValueError(
                    f'configuration type {configType.__name__!r} overlaps a registered type'
                )
            configurationTypes.append(configType)

        coreTypes = []
        for coreType in plugin.coreTypes:
            if not isinstance(coreType, type):
                raise TypeError('plugin core types must be classes')
            if any(
                issubclass(coreType, registeredType)
                or issubclass(registeredType, coreType)
                for registeredType in (
                    *self._coreTypes,
                    *coreTypes,
                )
            ):
                raise ValueError(
                    f'core type {coreType.__name__!r} overlaps a registered type'
                )
            coreTypes.append(coreType)

        self._plugins[pluginId] = plugin

        for key, descriptor in zip(protocolKeys, plugin.protocols):
            self._protocols[key] = (plugin, descriptor)
        for configType in plugin.configurationTypes:
            self._configurationTypes[configType] = plugin
        for coreType in plugin.coreTypes:
            self._coreTypes[coreType] = plugin

        logger.info(f'registered plugin {pluginId!r}')

        return plugin

    def plugins(self):
        """Return registered plugins in registration order."""
        return tuple(self._plugins.values())

    def protocolDescriptors(self):
        """Return contributed protocols in their requested menu order."""
        descriptors = list(
            descriptor for _plugin, descriptor in self._protocols.values()
        )

        return tuple(sorted(descriptors, key=lambda descriptor: descriptor.menuOrder))

    def pluginForProtocol(self, protocol):
        """Return the plugin that owns a protocol identifier."""
        entry = self._protocols.get(_normalizeProtocol(protocol))

        return entry[0] if entry is not None else None

    def pluginForConfig(self, config):
        """Return the plugin that owns a configuration instance."""
        for configType, plugin in self._configurationTypes.items():
            if isinstance(config, configType):
                return plugin

        return None

    def pluginForCore(self, core):
        """Return the plugin that owns a running core instance."""
        for coreType, plugin in self._coreTypes.items():
            if isinstance(core, coreType):
                return plugin

        return None

    def configFromString(self, config: str, **kwargs):
        """Ask plugins to parse textual configuration data."""
        for plugin in self.plugins():
            factory = plugin.configFromString(config, **kwargs)
            if factory is not None:
                return factory

        return None

    def configFromDict(self, config: dict, **kwargs):
        """Ask plugins to parse configuration mapping data."""
        for plugin in self.plugins():
            factory = plugin.configFromDict(config, **kwargs)
            if factory is not None:
                return factory

        return None

    def blankConfig(self, protocol, **kwargs):
        """Construct a blank configuration through the owning plugin."""
        plugin = self.pluginForProtocol(protocol)

        return plugin.blankConfig(protocol, **kwargs) if plugin is not None else None

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Construct a protocol editor through the owning plugin."""
        plugin = self.pluginForProtocol(protocol)
        if plugin is None:
            return None

        return plugin.createEditorForProtocol(protocol, parent=parent, **kwargs)

    def createEditorForConfig(self, config, parent=None, **kwargs):
        """Construct a configuration editor through the owning plugin."""
        plugin = self.pluginForConfig(config)
        if plugin is None:
            return None

        return plugin.createEditorForConfig(config, parent=parent, **kwargs)

    def managementActions(self, plugin, parent=None, **kwargs):
        """Return management actions contributed by one registered plugin."""
        if self._plugins.get(plugin.pluginId) is not plugin:
            raise ValueError(f'plugin {plugin.pluginId!r} is not registered')

        try:
            return tuple(plugin.createManagementActions(parent=parent, **kwargs))
        except Exception as ex:
            logger.error(
                f'failed to create management actions for {plugin.pluginId!r}: {ex}'
            )

            return tuple()

    def routingOptions(self, config):
        """Return validated routing modes supported by a configuration's plugin."""
        plugin = self.pluginForConfig(config)
        if plugin is None:
            return tuple()

        try:
            options = tuple(plugin.routingOptions(config))
            optionIds = set()
            for option in options:
                if not isinstance(option, PluginRouting):
                    raise TypeError(
                        'plugin routing options must be PluginRouting values'
                    )

                if not isinstance(option.id, str):
                    raise TypeError('plugin routing option ID must be a string')
                if not option.id.strip():
                    raise ValueError('plugin routing option ID cannot be empty')
                if not isinstance(option.displayName, str):
                    raise TypeError(
                        'plugin routing option display name must be a string'
                    )

                optionId = option.id
                if optionId in optionIds:
                    raise ValueError(
                        f'routing option {option.id!r} is already registered'
                    )

                optionIds.add(optionId)

            return options
        except Exception as ex:
            logger.error(
                f'failed to obtain routing options for {plugin.pluginId!r}: {ex}'
            )

            return tuple()

    def normalizeRouting(self, config, routing):
        """Return a supported routing value or the plugin's first option."""
        options = self.routingOptions(config)
        if not options:
            return routing

        optionIds = tuple(option.id for option in options)

        return routing if routing in optionIds else optionIds[0]

    def configureEnvironment(self):
        """Allow every plugin to configure its core process environment."""
        for plugin in self.plugins():
            try:
                plugin.configureEnvironment()
            except Exception as ex:
                logger.error(f'environment hook failed for {plugin.pluginId!r}: {ex}')

    def coreVersions(self):
        """Return version strings reported by every registered plugin core."""
        versions = []
        for plugin in self.plugins():
            try:
                versions.extend(plugin.coreVersions())
            except Exception as ex:
                logger.error(
                    f'failed to obtain core versions for {plugin.pluginId!r}: {ex}'
                )

        return tuple(filter(None, versions))

    def logTimestampPatterns(self):
        """Return timestamp expressions contributed by registered plugins."""
        patterns = []
        for plugin in self.plugins():
            try:
                patterns.extend(plugin.logTimestampPatterns())
            except Exception as ex:
                logger.error(
                    f'failed to obtain log patterns for {plugin.pluginId!r}: {ex}'
                )

        return tuple(filter(None, patterns))

    def coreExitMessage(self, core, exitcode: int):
        """Return the owning plugin's special exit message, if any."""
        plugin = self.pluginForCore(core)
        if plugin is None:
            return None

        try:
            return plugin.coreExitMessage(core, exitcode)
        except Exception as ex:
            logger.error(f'failed to interpret core exit for {plugin.pluginId!r}: {ex}')

            return None

    def afterConnected(self, httpProxy=None):
        """Notify every registered plugin after a connection succeeds."""
        for plugin in self.plugins():
            try:
                plugin.afterConnected(httpProxy)
            except Exception as ex:
                logger.error(
                    f'post-connection hook failed for {plugin.pluginId!r}: {ex}'
                )

    def discover(self):
        """Load third-party plugins exposed through Python entry points."""
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


_registry = PluginRegistry()
_registryLock = threading.RLock()
_registryInitialized = False
_officialPluginTypes = tuple()


def _setOfficialPluginTypes(pluginTypes):
    """Configure bundled plugin classes before registry initialization."""
    global _officialPluginTypes

    with _registryLock:
        if _registryInitialized:
            raise RuntimeError('plugin registry is already initialized')

        _officialPluginTypes = tuple(pluginTypes)


def getPluginRegistry() -> PluginRegistry:
    """Return the process-wide registry after lazy official/external discovery."""
    global _registry, _registryInitialized

    with _registryLock:
        if not _registryInitialized:
            registry = PluginRegistry()
            for pluginType in _officialPluginTypes:
                registry.register(pluginType())

            registry.discover()
            _registry = registry
            _registryInitialized = True

    return _registry


def registerPlugin(plugin: FuriousPlugin):
    """Register a plugin programmatically and return it."""
    return getPluginRegistry().register(plugin)
