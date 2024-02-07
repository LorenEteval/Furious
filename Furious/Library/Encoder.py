# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from __future__ import annotations

from Furious.Interface import *

from typing import Any, AnyStr

import json
import ujson
import base64
import pybase64

__all__ = ['JSONEncoder', 'UJSONEncoder', 'Base64Encoder', 'PyBase64Encoder']


class _JSONEncoder(Encoder):
    def encode(self, data: Any, **kwargs) -> str:
        ensure_ascii = kwargs.pop('ensure_ascii', False)

        return json.dumps(data, ensure_ascii=ensure_ascii, **kwargs)

    def decode(self, data: AnyStr, **kwargs) -> Any:
        return json.loads(data, **kwargs)


class _UJSONEncoder(Encoder):
    def encode(self, data: Any, **kwargs) -> str:
        ensure_ascii = kwargs.pop('ensure_ascii', False)
        escape_forward_slashes = kwargs.pop('escape_forward_slashes', False)

        return ujson.dumps(
            data,
            ensure_ascii=ensure_ascii,
            escape_forward_slashes=escape_forward_slashes,
            **kwargs,
        )

    def decode(self, data: AnyStr, **kwargs) -> Any:
        return ujson.loads(data, **kwargs)


class _Base64Encoder(Encoder):
    def encode(self, data: Any, **kwargs) -> bytes:
        return base64.b64encode(data, **kwargs)

    def decode(self, data: Any, **kwargs) -> bytes:
        validate = kwargs.pop('validate', False)

        return base64.b64decode(data, validate=validate, **kwargs)


class _PyBase64Encoder(Encoder):
    def encode(self, data: Any, **kwargs) -> bytes:
        return pybase64.b64encode(data, **kwargs)

    def decode(self, data: Any, **kwargs) -> bytes:
        validate = kwargs.pop('validate', False)

        return pybase64.b64decode(data, validate=validate, **kwargs)


JSONEncoder = _JSONEncoder()
UJSONEncoder = _UJSONEncoder()
Base64Encoder = _Base64Encoder()
PyBase64Encoder = _PyBase64Encoder()
