"""Define the public contract implemented by Furious core plugins."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    'PLUGIN_API_VERSION',
    'PluginProtocol',
    'PluginRouting',
    'FuriousPlugin',
]

PLUGIN_API_VERSION = 1


@dataclass(frozen=True)
class PluginProtocol:
    """Describe one server protocol contributed by a plugin."""

    id: str
    displayName: str
    addActionText: str
    menuOrder: int = 0
    separatorBefore: bool = False


@dataclass(frozen=True)
class PluginRouting:
    """Describe one routing mode supported by a core plugin."""

    id: str
    displayName: str
    separatorBefore: bool = False
    translatable: bool = False


class FuriousPlugin:
    """Provide configuration, UI, and process hooks for one proxy core family."""

    apiVersion = PLUGIN_API_VERSION
    pluginId = ''
    displayName = ''
    protocols = tuple()
    configurationTypes = tuple()
    coreTypes = tuple()

    def configFromString(self, config: str, **kwargs):
        """Construct a supported configuration from text or return ``None``."""
        return None

    def configFromDict(self, config: dict, **kwargs):
        """Construct a supported configuration mapping or return ``None``."""
        return None

    def blankConfig(self, protocol, **kwargs):
        """Construct a blank configuration for a contributed protocol."""
        return None

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create the configuration editor for a contributed protocol."""
        return None

    def createEditorForConfig(self, config, parent=None, **kwargs):
        """Create the configuration editor for a plugin configuration."""
        return self.createEditorForProtocol(config.itemProtocol, parent, **kwargs)

    def createManagementActions(self, parent=None, **kwargs):
        """Return optional actions for this plugin's management submenu."""
        return tuple()

    def prepareTUN(self, config) -> bool:
        """Prepare plugin-native TUN and return whether the plugin handles it."""
        return False

    def routingOptions(self, config=None):
        """Return routing modes supported for a plugin configuration."""
        return tuple()

    def configureEnvironment(self):
        """Set optional process environment required by the plugin core."""

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
        """Start the plugin core and return ``(process, success)``."""
        return None, False

    def prepareDownloadTest(self, config, port: int):
        """Return a proxy-only configuration for a download-speed test."""
        return None

    def coreVersions(self):
        """Return core version strings that should be treated as versions in logs."""
        return tuple()

    def logTimestampPatterns(self):
        """Return regular expressions for timestamps emitted by the plugin core."""
        return tuple()

    def coreExitMessage(self, core, exitcode: int):
        """Return a user-facing message key for a plugin-specific exit code."""
        return None

    def afterConnected(self, httpProxy=None):
        """Perform optional plugin maintenance after a connection succeeds."""
