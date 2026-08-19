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

"""Construct and export profiles through registered protocol capabilities."""

from __future__ import annotations

from Furious.Models import CoreConfiguration, ServerProfile, ensureProfile

from typing import Mapping, Union

import logging
import ujson

from .Registry import getPluginRegistry

__all__ = [
    'blankConfiguration',
    'configurationFromAny',
    'configurationFromMapping',
    'exportConfiguration',
    'blankProfile',
    'profileFromAny',
    'profileFromMapping',
]

logger = logging.getLogger(__name__)


def configurationFromMapping(
    config: Mapping, registry=None, **kwargs
) -> CoreConfiguration:
    """Construct a connection document from a normalized mapping."""
    if not isinstance(config, Mapping):
        return CoreConfiguration()

    try:
        factory = (registry or getPluginRegistry()).configFromDict(
            dict(config), **kwargs
        )
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'failed to recognize configuration mapping: {ex}')

        factory = None

    return factory if factory is not None else CoreConfiguration(dict(config))


def configurationFromAny(
    config: Union[str, Mapping, CoreConfiguration, ServerProfile],
    registry=None,
    **kwargs,
) -> CoreConfiguration:
    """Construct a connection document from supported input data."""
    if isinstance(config, ServerProfile):
        return config.connection.deepcopy()

    if isinstance(config, CoreConfiguration):
        return config.deepcopy()

    if isinstance(config, str):
        registry = registry or getPluginRegistry()
        result = registry.parseURI(config, **kwargs)

        if result is not None:
            return result.configuration

        try:
            return configurationFromMapping(
                ujson.loads(config), registry=registry, **kwargs
            )
        except Exception:
            # Any non-exit exceptions

            return CoreConfiguration()

    if isinstance(config, Mapping):
        return configurationFromMapping(config, registry=registry, **kwargs)

    return CoreConfiguration()


def blankConfiguration(protocol, registry=None, **kwargs) -> CoreConfiguration:
    """Create a blank connection through an exact protocol capability."""
    factory = (registry or getPluginRegistry()).blankConfig(protocol, **kwargs)

    return factory if factory is not None else CoreConfiguration()


def exportConfiguration(config, remark: str = '', registry=None) -> str:
    """Export a profile through its owning protocol capability."""
    try:
        return (registry or getPluginRegistry()).exportConfig(config, remark)
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'failed to export configuration: {ex}')

        return ''


def profileFromMapping(config: Mapping, registry=None, **metadata) -> ServerProfile:
    """Construct a metadata-separated profile from a connection mapping."""
    return ensureProfile(
        configurationFromMapping(config, registry=registry),
        **metadata,
    )


def profileFromAny(
    config: Union[str, Mapping, CoreConfiguration, ServerProfile],
    registry=None,
    **metadata,
) -> ServerProfile:
    """Construct a metadata-separated profile from supported input data."""
    if isinstance(config, ServerProfile):
        profile = config.deepcopy()

        for name, value in metadata.items():
            profile.metadata.set(name, value)

        return profile

    if isinstance(config, str):
        registry = registry or getPluginRegistry()
        result = registry.parseURI(config)

        if result is not None:
            parsedMetadata = dict(result.metadata)
            parsedMetadata.update(metadata)

            return ServerProfile.fromConfiguration(
                result.configuration,
                parsedMetadata,
            )

    return ensureProfile(
        configurationFromAny(config, registry=registry),
        **metadata,
    )


def blankProfile(protocol, registry=None, **metadata) -> ServerProfile:
    """Create a metadata-separated blank profile for *protocol*."""
    return ensureProfile(
        blankConfiguration(protocol, registry=registry),
        **metadata,
    )
