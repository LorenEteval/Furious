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

"""Provide JSON and Base64 encoder implementations."""

from __future__ import annotations

from typing import Any, AnyStr

import json
import ujson
import base64
import pybase64

__all__ = [
    'JSONEncoder',
    'UJSONEncoder',
    'Base64Encoder',
    'PyBase64Encoder',
]


class JSONEncoder:
    """Encode and decode data using JSON."""

    @staticmethod
    def encode(data: Any, **kwargs) -> str:
        """Encode data with the JSON encoder."""
        ensure_ascii = kwargs.pop('ensure_ascii', False)

        return json.dumps(data, ensure_ascii=ensure_ascii, **kwargs)

    @staticmethod
    def decode(data: AnyStr, **kwargs) -> Any:
        """Decode data with the JSON encoder."""
        return json.loads(data, **kwargs)


class UJSONEncoder:
    """Encode and decode data using ujson."""

    @staticmethod
    def encode(data: Any, **kwargs) -> str:
        """Encode data with the ujson encoder."""
        ensure_ascii = kwargs.pop('ensure_ascii', False)
        escape_forward_slashes = kwargs.pop('escape_forward_slashes', False)

        return ujson.dumps(
            data,
            ensure_ascii=ensure_ascii,
            escape_forward_slashes=escape_forward_slashes,
            **kwargs,
        )

    @staticmethod
    def decode(data: AnyStr, **kwargs) -> Any:
        """Decode data with the ujson encoder."""
        return ujson.loads(data, **kwargs)


class Base64Encoder:
    """Encode and decode data using base64."""

    @staticmethod
    def encode(data: Any, **kwargs) -> bytes:
        """Encode data with the base64 encoder."""
        return base64.b64encode(data, **kwargs)

    @staticmethod
    def decode(data: Any, **kwargs) -> bytes:
        """Decode data with the base64 encoder."""
        validate = kwargs.pop('validate', False)

        return base64.b64decode(data, validate=validate, **kwargs)


class PyBase64Encoder:
    """Encode and decode data using py base64."""

    @staticmethod
    def encode(data: Any, **kwargs) -> bytes:
        """Encode data with the py base64 encoder."""
        return pybase64.b64encode(data, **kwargs)

    @staticmethod
    def decode(data: Any, **kwargs) -> bytes:
        """Decode data with the py base64 encoder."""
        validate = kwargs.pop('validate', False)

        return pybase64.b64decode(data, validate=validate, **kwargs)
