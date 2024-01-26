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
