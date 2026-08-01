"""Register the core plugins maintained with Furious itself."""

from __future__ import annotations

__all__ = ['registerOfficialPlugins']


def registerOfficialPlugins(registry):
    """Register the bundled Xray and Hysteria plugins."""
    from .Xray.Plugin import XrayPlugin
    from .Hysteria1.Plugin import Hysteria1Plugin
    from .Hysteria2.Plugin import Hysteria2Plugin

    registry.register(XrayPlugin())
    registry.register(Hysteria1Plugin())
    registry.register(Hysteria2Plugin())
