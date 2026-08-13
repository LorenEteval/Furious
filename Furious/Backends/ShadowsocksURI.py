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

"""Parse and serialize Shadowsocks share links according to SIP002."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote_to_bytes, urlsplit

import re
import base64
import binascii
import ipaddress

__all__ = [
    'SHADOWSOCKS_PLUGIN_METADATA_KEY',
    'ShadowsocksURIData',
    'ShadowsocksURIError',
    'parseShadowsocksURI',
    'serializeShadowsocksURI',
]

SHADOWSOCKS_PLUGIN_METADATA_KEY = 'shadowsocksPlugin'

# Methods implemented by common Shadowsocks clients, including the legacy
# stream ciphers used by existing share links.  Keeping validation here
# prevents malformed method names from becoming runtime configurations.
SUPPORTED_SHADOWSOCKS_METHODS = frozenset(
    {
        'none',
        'plain',
        'table',
        'rc4',
        'rc4-md5',
        'aes-128-cfb',
        'aes-192-cfb',
        'aes-256-cfb',
        'aes-128-ctr',
        'aes-192-ctr',
        'aes-256-ctr',
        'bf-cfb',
        'camellia-128-cfb',
        'camellia-192-cfb',
        'camellia-256-cfb',
        'cast5-cfb',
        'des-cfb',
        'idea-cfb',
        'rc2-cfb',
        'salsa20',
        'chacha20',
        'chacha20-ietf',
        'aes-128-gcm',
        'aes-192-gcm',
        'aes-256-gcm',
        'chacha20-poly1305',
        'chacha20-ietf-poly1305',
        'xchacha20-poly1305',
        'xchacha20-ietf-poly1305',
        '2022-blake3-aes-128-gcm',
        '2022-blake3-aes-256-gcm',
        '2022-blake3-chacha20-poly1305',
    }
)

_BASE64URL_PATTERN = re.compile(r'^[A-Za-z0-9_-]+={0,2}$')
_HEX_DIGITS = frozenset('0123456789abcdefABCDEF')
_PLUGIN_ESCAPED_CHARACTERS = frozenset('\\:;=')


class ShadowsocksURIError(ValueError):
    """Report a malformed or unsupported Shadowsocks share link."""


@dataclass(frozen=True)
class ShadowsocksURIData:
    """Store the meaningful fields of one SIP002 URI."""

    method: str
    password: str
    host: str
    port: int
    plugin: str = ''
    tag: str = ''


def _validatePercentEncoding(value: str, label: str):
    """Reject incomplete percent escapes before decoding *value*."""
    index = 0

    while index < len(value):
        if value[index] != '%':
            index += 1
            continue

        if (
            index + 2 >= len(value)
            or value[index + 1] not in _HEX_DIGITS
            or value[index + 2] not in _HEX_DIGITS
        ):
            raise ShadowsocksURIError(f'{label} contains invalid percent encoding')

        index += 3


def _percentDecode(value: str, label: str) -> str:
    """Decode one RFC3986 component as strict UTF-8 without ``+`` semantics."""
    _validatePercentEncoding(value, label)

    try:
        return unquote_to_bytes(value).decode('utf-8')
    except UnicodeDecodeError as ex:
        raise ShadowsocksURIError(f'{label} is not valid UTF-8') from ex


def _validateMethodAndPassword(method: str, password: str):
    """Validate fields before constructing a configuration."""
    if method not in SUPPORTED_SHADOWSOCKS_METHODS:
        raise ShadowsocksURIError(f'unsupported Shadowsocks method {method!r}')

    if not password:
        raise ShadowsocksURIError('Shadowsocks password cannot be empty')


def _decodeBase64URL(value: str) -> str:
    """Decode padded or unpadded Base64URL using strict alphabet validation."""
    if not value or not _BASE64URL_PATTERN.fullmatch(value):
        raise ShadowsocksURIError('userinfo is not valid Base64URL')

    unpadded = value.rstrip('=')
    suppliedPadding = len(value) - len(unpadded)
    requiredPadding = -len(unpadded) % 4

    if (
        '=' in unpadded
        or len(unpadded) % 4 == 1
        or (suppliedPadding and suppliedPadding != requiredPadding)
    ):
        raise ShadowsocksURIError('userinfo has invalid Base64URL padding')

    padded = unpadded + '=' * requiredPadding

    try:
        decoded = base64.b64decode(
            padded.encode('ascii'), altchars=b'-_', validate=True
        )

        return decoded.decode('utf-8')
    except (binascii.Error, UnicodeDecodeError) as ex:
        raise ShadowsocksURIError('userinfo is not valid Base64URL UTF-8') from ex


def _decodeLegacyBase64(value: str) -> str:
    """Decode a pre-SIP002 whole-authority payload for import compatibility."""
    value = _percentDecode(value, 'legacy payload').rstrip('=')

    if not value or len(value) % 4 == 1:
        raise ShadowsocksURIError('legacy payload has invalid Base64 padding')

    padded = value + '=' * (-len(value) % 4)

    try:
        decoded = base64.b64decode(
            padded.encode('ascii'), altchars=b'-_', validate=True
        )

        return decoded.decode('utf-8')
    except (ValueError, binascii.Error, UnicodeDecodeError) as ex:
        raise ShadowsocksURIError('legacy payload is not valid Base64 UTF-8') from ex


def _parseEndpoint(value: str) -> tuple[str, int]:
    """Parse a normal URI host/port authority, including bracketed IPv6."""
    try:
        result = urlsplit(f'//{value}')
        host = result.hostname or ''
        port = result.port
    except ValueError as ex:
        raise ShadowsocksURIError('server endpoint has an invalid port') from ex

    if not host or port is None:
        raise ShadowsocksURIError('server endpoint must contain a host and port')

    if not 1 <= port <= 65535:
        raise ShadowsocksURIError('server port must be between 1 and 65535')

    if result.username is not None or result.password is not None or result.path:
        raise ShadowsocksURIError('server endpoint is malformed')

    if any(character.isspace() or ord(character) < 32 for character in host):
        raise ShadowsocksURIError('server host contains invalid characters')

    return host, port


def _parsePlainUserinfo(value: str) -> tuple[str, str]:
    """Decode SIP002 plain method/password fields."""
    if ':' not in value:
        raise ShadowsocksURIError('plain userinfo is missing the method separator')

    encodedMethod, encodedPassword = value.split(':', 1)
    method = _percentDecode(encodedMethod, 'method')
    password = _percentDecode(encodedPassword, 'password')

    _validateMethodAndPassword(method, password)

    return method, password


def _parseUserinfo(value: str) -> tuple[str, str]:
    """Parse SIP002 userinfo and one widespread encoded-separator variant."""
    if not value or '@' in value:
        raise ShadowsocksURIError('userinfo is malformed')

    if ':' in value:
        return _parsePlainUserinfo(value)

    try:
        decoded = _decodeBase64URL(value)
    except ShadowsocksURIError as base64Error:
        # Some producers percent-encode the entire ``method:password`` value,
        # including the separator.  It is not canonical SIP002, but accepting
        # it preserves established import compatibility; export normalizes it.
        decoded = _percentDecode(value, 'userinfo')

        if ':' not in decoded:
            raise base64Error

        method, password = decoded.split(':', 1)

        _validateMethodAndPassword(method, password)

        if method.startswith('2022-'):
            raise ShadowsocksURIError(
                'AEAD-2022 userinfo must use a literal method separator'
            )

        return method, password

    if ':' not in decoded:
        raise ShadowsocksURIError('Base64URL userinfo is missing the method separator')

    method, password = decoded.split(':', 1)

    _validateMethodAndPassword(method, password)

    if method.startswith('2022-'):
        raise ShadowsocksURIError('AEAD-2022 userinfo must not be Base64URL encoded')

    return method, password


def _splitEscaped(value: str, separator: str) -> list[str]:
    """Split a SIP003 plugin argument on an unescaped separator."""
    result = []
    current = []
    escaped = False

    for character in value:
        if escaped:
            if character not in _PLUGIN_ESCAPED_CHARACTERS:
                raise ShadowsocksURIError(
                    f'plugin argument contains invalid escape \\{character}'
                )

            if character == separator:
                current.append(character)
            else:
                # Preserve escapes that belong to a later parsing layer.  In
                # particular, an escaped equals sign must not become the
                # option's key/value delimiter after splitting semicolons.
                current.extend(('\\', character))
            escaped = False
        elif character == '\\':
            escaped = True
        elif character == separator:
            result.append(''.join(current))
            current = []
        else:
            current.append(character)

    if escaped:
        raise ShadowsocksURIError('plugin argument ends with an incomplete escape')

    result.append(''.join(current))

    return result


def _splitPluginOption(value: str) -> tuple[str, str | None]:
    """Split and unescape one plugin option at its first unescaped equals."""
    parts = _splitEscaped(value, '=')

    if len(parts) > 2:
        parts[1:] = ['='.join(parts[1:])]

    return (
        _unescapePluginComponent(parts[0]),
        _unescapePluginComponent(parts[1]) if len(parts) == 2 else None,
    )


def _unescapePluginComponent(value: str) -> str:
    """Remove validated SIP003 escapes from one component."""
    result = []
    escaped = False

    for character in value:
        if escaped:
            if character not in _PLUGIN_ESCAPED_CHARACTERS:
                raise ShadowsocksURIError(
                    f'plugin argument contains invalid escape \\{character}'
                )

            result.append(character)
            escaped = False
        elif character == '\\':
            escaped = True
        else:
            result.append(character)

    if escaped:
        raise ShadowsocksURIError('plugin argument ends with an incomplete escape')

    return ''.join(result)


def escapePluginComponent(value: str) -> str:
    """Escape one SIP003 plugin name, option name, or option value."""
    return ''.join(
        f'\\{character}' if character in _PLUGIN_ESCAPED_CHARACTERS else character
        for character in str(value)
    )


def parsePluginArgument(value: str) -> tuple[str, tuple[tuple[str, str | None], ...]]:
    """Parse one decoded SIP002 plugin argument into semantic components."""
    fields = _splitEscaped(value, ';')
    name = _unescapePluginComponent(fields[0])

    if not name:
        raise ShadowsocksURIError('plugin name cannot be empty')

    options = []

    for field in fields[1:]:
        if not field:
            raise ShadowsocksURIError('plugin option cannot be empty')

        key, optionValue = _splitPluginOption(field)

        if not key:
            raise ShadowsocksURIError('plugin option name cannot be empty')

        options.append((key, optionValue))

    return name, tuple(options)


def formatPluginArgument(
    name: str, options: tuple[tuple[str, str | None], ...] = tuple()
) -> str:
    """Serialize semantic plugin components with SIP003 escaping."""
    if not name:
        raise ShadowsocksURIError('plugin name cannot be empty')

    fields = [escapePluginComponent(name)]

    for key, value in options:
        if not key:
            raise ShadowsocksURIError('plugin option name cannot be empty')

        field = escapePluginComponent(key)

        if value is not None:
            field += f'={escapePluginComponent(value)}'

        fields.append(field)

    return ';'.join(fields)


def _normalizePluginArgument(value: str) -> str:
    """Validate and canonically re-escape one decoded plugin argument."""
    name, options = parsePluginArgument(value)

    return formatPluginArgument(name, options)


def _parseQuery(value: str) -> str:
    """Return the first plugin query value and ignore unsupported parameters."""
    for field in value.split('&') if value else tuple():
        encodedKey, separator, encodedValue = field.partition('=')

        try:
            key = _percentDecode(encodedKey, 'query parameter name')
        except ShadowsocksURIError:
            # An unsupported malformed parameter must not invalidate a valid
            # Shadowsocks URI.
            continue

        if key != 'plugin':
            continue

        if not separator:
            raise ShadowsocksURIError('plugin query parameter has no value')

        return _normalizePluginArgument(
            _percentDecode(encodedValue, 'plugin query parameter')
        )

    return ''


def _parseLegacyURI(result) -> ShadowsocksURIData:
    """Parse the pre-SIP002 ``base64(method:password@host:port)`` form."""
    # A standard Base64 payload may itself contain ``/``.  ``urlsplit`` moves
    # that suffix into ``path``, so joining the two components reconstructs the
    # original payload without treating any Base64 character as URI structure.
    payload = f'{result.netloc}{result.path}'
    decoded = _decodeLegacyBase64(payload)

    userinfo, separator, endpoint = decoded.rpartition('@')

    if not separator:
        raise ShadowsocksURIError('legacy payload has no server separator')

    method, password = _parsePlainUserinfo(userinfo)
    host, port = _parseEndpoint(endpoint)
    tag = _percentDecode(result.fragment, 'tag')

    return ShadowsocksURIData(method, password, host, port, tag=tag)


def parseShadowsocksURI(uri: str) -> ShadowsocksURIData:
    """Parse a SIP002 URI, with isolated pre-SIP002 import compatibility."""
    if not isinstance(uri, str) or not uri.strip():
        raise ShadowsocksURIError('Shadowsocks URI cannot be empty')

    uri = uri.strip()

    try:
        result = urlsplit(uri)
    except ValueError as ex:
        raise ShadowsocksURIError('Shadowsocks URI is malformed') from ex

    if result.scheme.casefold() != 'ss':
        raise ShadowsocksURIError('URI scheme must be ss')

    if '@' not in result.netloc:
        return _parseLegacyURI(result)

    if result.path not in ('', '/'):
        raise ShadowsocksURIError('SIP002 URI path must be empty or /')

    userinfo, separator, endpoint = result.netloc.rpartition('@')

    if not separator:
        raise ShadowsocksURIError('SIP002 URI is missing userinfo')

    method, password = _parseUserinfo(userinfo)
    host, port = _parseEndpoint(endpoint)
    plugin = _parseQuery(result.query)
    tag = _percentDecode(result.fragment, 'tag')

    return ShadowsocksURIData(method, password, host, port, plugin, tag)


def _formatHost(host: str) -> str:
    """Return a canonical URI host, bracketing IPv6 literals."""
    host = str(host).strip()

    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]

    if not host:
        raise ShadowsocksURIError('server host cannot be empty')

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if ':' in host or any(
            character.isspace() or ord(character) < 32 for character in host
        ):
            raise ShadowsocksURIError('server host is malformed')

        try:
            return host.encode('idna').decode('ascii')
        except UnicodeError as ex:
            raise ShadowsocksURIError('server host is malformed') from ex

    return f'[{address.compressed}]' if address.version == 6 else address.compressed


def serializeShadowsocksURI(value: ShadowsocksURIData) -> str:
    """Serialize one configuration into canonical SIP002 form."""
    if not isinstance(value, ShadowsocksURIData):
        raise TypeError('value must be a ShadowsocksURIData instance')

    _validateMethodAndPassword(value.method, value.password)

    try:
        port = int(value.port)
    except (TypeError, ValueError) as ex:
        raise ShadowsocksURIError('server port must be an integer') from ex

    if not 1 <= port <= 65535:
        raise ShadowsocksURIError('server port must be between 1 and 65535')

    if value.method.startswith('2022-'):
        userinfo = f'{quote(value.method, safe="")}:{quote(value.password, safe="")}'
    else:
        encoded = base64.urlsafe_b64encode(
            f'{value.method}:{value.password}'.encode('utf-8')
        ).decode('ascii')

        userinfo = encoded.rstrip('=')

    endpoint = f'{_formatHost(value.host)}:{port}'
    path, query = '', ''

    if value.plugin:
        plugin = _normalizePluginArgument(value.plugin)
        path, query = '/', f'plugin={quote(plugin, safe="")}'

    fragment = quote(value.tag, safe='')

    return f'ss://{userinfo}@{endpoint}{path}{"?" + query if query else ""}{"#" + fragment if fragment else ""}'
