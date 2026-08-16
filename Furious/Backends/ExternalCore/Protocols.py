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

"""Contribute local External Core profile creation without a share URI."""

from __future__ import annotations

from Furious.Plugins.API import ProtocolDescriptor, ProtocolHandler

from .Configuration import (
    BLANK_CONFIG_EXTERNAL_CORE,
    EXTERNAL_CORE_TYPE,
    ConfigExternalCore,
)

import copy

__all__ = ['EXTERNAL_CORE_PROTOCOL_HANDLERS']


def _placeholder(value):
    return value


_ = _placeholder

_TRANSLATABLE = (_('Add External Core...'),)


class ExternalCoreProtocolHandler(ProtocolHandler):
    """Own local External Core mappings while declining URI import/export."""

    descriptor = ProtocolDescriptor(
        EXTERNAL_CORE_TYPE,
        'External Core',
        'Add External Core...',
        100,
        True,
        {
            'type': 'object',
            'required': ('type', 'executable', 'arguments', 'environment'),
        },
        True,
        False,
    )
    schemes = tuple()

    def supports(self, configuration) -> bool:
        """Return whether *configuration* is a local External Core profile."""
        return isinstance(configuration, ConfigExternalCore)

    def fromMapping(self, configuration, **kwargs):
        """Recognize only explicitly discriminated External Core mappings."""
        if configuration.get('type') != EXTERNAL_CORE_TYPE:
            return None

        return ConfigExternalCore(configuration)

    def blank(self, **kwargs):
        """Create a blank structured External Core profile."""
        return ConfigExternalCore(copy.deepcopy(BLANK_CONFIG_EXTERNAL_CORE))

    def export(self, configuration, remark: str = '') -> str:
        """Decline portable URI export for a machine-local executable."""
        return ''

    def validate(self, configuration):
        """Return process and local-proxy validation errors."""
        if not self.supports(configuration):
            return ('Unsupported protocol',)

        errors = list(configuration.validateProcess())

        if not configuration.httpProxy():
            errors.append('Local HTTP proxy endpoint is required')

        return tuple(errors)


EXTERNAL_CORE_PROTOCOL_HANDLERS = (ExternalCoreProtocolHandler(),)
