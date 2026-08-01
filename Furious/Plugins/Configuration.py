"""Dispatch configuration creation through the process-wide plugin registry."""

from __future__ import annotations

from Furious.Interface.ConfigFactory import ConfigFactory

from .Registry import getPluginRegistry

from typing import Union

import ujson

__all__ = ['configFactoryFromDict', 'configFactoryFromAny', 'configFactoryBlank']


def configFactoryFromDict(config: dict, **kwargs) -> ConfigFactory:
    """Construct a configuration mapping through the first matching plugin."""
    if not isinstance(config, dict):
        return ConfigFactory()

    factory = getPluginRegistry().configFromDict(config, **kwargs)

    return factory if factory is not None else ConfigFactory(config, **kwargs)


def configFactoryFromAny(config: Union[str, dict], **kwargs) -> ConfigFactory:
    """Construct configuration data through the first matching plugin."""
    if isinstance(config, str):
        factory = getPluginRegistry().configFromString(config, **kwargs)
        if factory is not None:
            return factory

        try:
            return configFactoryFromDict(ujson.loads(config), **kwargs)
        except Exception:
            return ConfigFactory(**kwargs)

    if isinstance(config, dict):
        return configFactoryFromDict(config, **kwargs)

    return ConfigFactory(**kwargs)


def configFactoryBlank(protocol, **kwargs) -> ConfigFactory:
    """Construct a blank configuration through the owning plugin."""
    factory = getPluginRegistry().blankConfig(protocol, **kwargs)

    return factory if factory is not None else ConfigFactory()
