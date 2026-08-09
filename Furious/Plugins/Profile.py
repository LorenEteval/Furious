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

from Furious.Domain.Configuration import ConfigFactory

from typing import Mapping, Union

import logging
import ujson

from .Registry import getPluginRegistry

__all__ = [
    'blankConfiguration',
    'configurationFromAny',
    'configurationFromMapping',
    'exportConfiguration',
]

logger = logging.getLogger(__name__)


def configurationFromMapping(config: Mapping, **kwargs) -> ConfigFactory:
    """Construct a profile from a normalized mapping."""
    if not isinstance(config, dict):
        return ConfigFactory(**kwargs)

    try:
        factory = getPluginRegistry().configFromDict(config, **kwargs)
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'failed to recognize configuration mapping: {ex}')

        factory = None

    return factory if factory is not None else ConfigFactory(config, **kwargs)


def configurationFromAny(config: Union[str, Mapping], **kwargs) -> ConfigFactory:
    """Construct a profile from a share URI, JSON text, or mapping."""
    if isinstance(config, str):
        factory = getPluginRegistry().configFromString(config, **kwargs)

        if factory is not None:
            return factory

        try:
            return configurationFromMapping(ujson.loads(config), **kwargs)
        except Exception:
            # Any non-exit exceptions

            return ConfigFactory(**kwargs)

    if isinstance(config, dict):
        return configurationFromMapping(config, **kwargs)

    return ConfigFactory(**kwargs)


def blankConfiguration(protocol, **kwargs) -> ConfigFactory:
    """Create a blank profile through an exact protocol capability."""
    factory = getPluginRegistry().blankConfig(protocol, **kwargs)

    return factory if factory is not None else ConfigFactory(**kwargs)


def exportConfiguration(config, remark: str = '') -> str:
    """Export a profile through its owning protocol capability."""
    try:
        return getPluginRegistry().exportConfig(config, remark)
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'failed to export configuration: {ex}')

        return ''
