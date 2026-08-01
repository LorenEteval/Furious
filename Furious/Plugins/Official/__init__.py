"""Register the core plugins maintained with Furious itself."""

from __future__ import annotations

from .Hysteria1.Plugin import Hysteria1Plugin
from .Hysteria2.Plugin import Hysteria2Plugin
from .Xray.Plugin import XrayPlugin

__all__ = ['OFFICIAL_PLUGIN_TYPES']


OFFICIAL_PLUGIN_TYPES = (XrayPlugin, Hysteria1Plugin, Hysteria2Plugin)
