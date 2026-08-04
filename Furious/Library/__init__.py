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

"""Expose domain configuration, encoding, and persistent storage services."""

from __future__ import annotations

from .Configuration import (
    ConfigFactory,
    ConfigurationRegistry,
    configFactoryBlank,
    configFactoryFromAny,
    configFactoryFromDict,
    configurationRegistry,
    registerConfigurationProvider,
)
from .Encoder import Base64Encoder, JSONEncoder, PyBase64Encoder, UJSONEncoder
from .Storage import Storage

__all__ = [
    'Base64Encoder',
    'ConfigFactory',
    'ConfigurationRegistry',
    'JSONEncoder',
    'PyBase64Encoder',
    'Storage',
    'UJSONEncoder',
    'configFactoryBlank',
    'configFactoryFromAny',
    'configFactoryFromDict',
    'configurationRegistry',
    'registerConfigurationProvider',
]
