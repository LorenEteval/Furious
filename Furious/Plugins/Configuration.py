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
