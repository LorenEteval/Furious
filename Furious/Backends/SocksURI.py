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

"""Parse compatible SOCKS share links and emit one canonical form."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote_to_bytes, urlsplit

import base64
import binascii
import ipaddress
import re

__all__ = [
    'SOCKS_URI_SCHEMES',
    'SocksURIData',
    'SocksURIError',
    'parseSocksURI',
    'serializeSocksURI',
]

# Xray's outbound speaks SOCKS5.  The remaining schemes are import aliases
# retained for existing Furious links and v2rayN interoperability; canonical
# export normalizes every accepted alias to ``socks://``.
SOCKS_URI_SCHEMES = ('socks', 'socks5', 'socks5h', 'socks4')

_BASE64_PATTERN = re.compile(r'^[A-Za-z0-9+/_-]+={0,2}$')
_HEX_DIGITS = frozenset('0123456789abcdefABCDEF')


class SocksURIError(ValueError):
    """Report a malformed or unsupported SOCKS share link."""


@dataclass(frozen=True)
class SocksURIData:
    """Store the meaningful fields of one SOCKS share link."""

    host: str
    port: int
    username: str = ''
    password: str = ''
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
            raise SocksURIError(f'{label} contains invalid percent encoding')

        index += 3


def _percentDecode(value: str, label: str) -> str:
    """Decode one RFC3986 component as strict UTF-8 without ``+`` semantics."""
    _validatePercentEncoding(value, label)

    try:
        return unquote_to_bytes(value).decode('utf-8')
    except UnicodeDecodeError as ex:
        raise SocksURIError(f'{label} is not valid UTF-8') from ex


def _decodeBase64(value: str, label: str) -> str:
    """Decode standard or URL-safe Base64 with strict alphabet validation."""
    value = _percentDecode(value, label)

    if not value or not _BASE64_PATTERN.fullmatch(value):
        raise SocksURIError(f'{label} is not valid Base64')

    unpadded = value.rstrip('=')
    suppliedPadding = len(value) - len(unpadded)
    requiredPadding = -len(unpadded) % 4

    if (
        '=' in unpadded
        or len(unpadded) % 4 == 1
        or (suppliedPadding and suppliedPadding != requiredPadding)
    ):
        raise SocksURIError(f'{label} has invalid Base64 padding')

    try:
        decoded = base64.b64decode(
            (unpadded + '=' * requiredPadding).encode('ascii'),
            altchars=b'-_',
            validate=True,
        )

        return decoded.decode('utf-8')
    except (ValueError, binascii.Error, UnicodeDecodeError) as ex:
        raise SocksURIError(f'{label} is not valid Base64 UTF-8') from ex


def _normalizeHost(host: str) -> str:
    """Validate and normalize a hostname or IP address for storage."""
    host = str(host).strip()

    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]

    if not host:
        raise SocksURIError('server host cannot be empty')

    if any(
        character.isspace() or ord(character) < 32 or character in '/?#@%'
        for character in host
    ):
        raise SocksURIError('server host contains invalid characters')

    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        if ':' in host:
            raise SocksURIError('server host is malformed')

        try:
            normalized = host.encode('idna').decode('ascii')
        except UnicodeError as ex:
            raise SocksURIError('server host is malformed') from ex

        if not normalized or len(normalized) > 253:
            raise SocksURIError('server host is malformed')

        labels = normalized.rstrip('.').split('.')

        if any(
            not label
            or len(label) > 63
            or label.startswith('-')
            or label.endswith('-')
            or not all(character.isalnum() or character == '-' for character in label)
            for label in labels
        ):
            raise SocksURIError('server host is malformed')

        return normalized


def _parsePort(value) -> int:
    """Return a validated TCP port number."""
    try:
        port = int(value)
    except (TypeError, ValueError) as ex:
        raise SocksURIError('server port must be an integer') from ex

    if not 1 <= port <= 65535:
        raise SocksURIError('server port must be between 1 and 65535')

    return port


def _parseEndpoint(value: str) -> tuple[str, int]:
    """Parse a URI authority endpoint, including bracketed IPv6."""
    try:
        result = urlsplit(f'//{value}')
        host = result.hostname or ''
        port = result.port
    except ValueError as ex:
        # v2rayN's legacy parser split the port at the final colon, so old
        # whole-payload links may contain an unbracketed IPv6 literal.  Keep
        # that compatibility isolated here; canonical export adds brackets.
        host, separator, port = value.rpartition(':')

        if separator and ':' in host:
            return _normalizeHost(host), _parsePort(port)

        raise SocksURIError('server endpoint is malformed') from ex

    if not host or port is None:
        raise SocksURIError('server endpoint must contain a host and port')

    if result.username is not None or result.password is not None or result.path:
        raise SocksURIError('server endpoint is malformed')

    return _normalizeHost(host), _parsePort(port)


def _parseUserinfo(value: str) -> tuple[str, str]:
    """Parse direct RFC userinfo or v2rayN-compatible Base64 userinfo."""
    if ':' in value:
        username, password = value.split(':', 1)

        return (
            _percentDecode(username, 'username'),
            _percentDecode(password, 'password'),
        )

    decoded = _percentDecode(value, 'userinfo')

    if ':' in decoded:
        # Accept producers that percent-encode the complete userinfo value,
        # including its credential separator.  Canonical export always keeps
        # the separator literal so encoded colons inside either field remain
        # unambiguous.
        username, password = decoded.split(':', 1)

        return username, password

    decoded = _decodeBase64(value, 'userinfo')

    if ':' not in decoded:
        raise SocksURIError('userinfo is missing the credential separator')

    username, password = decoded.split(':', 1)

    return username, password


def _parseLegacyURI(result) -> SocksURIData:
    """Parse the historical ``base64(user:pass@host:port)`` form."""
    if result.query:
        raise SocksURIError('legacy SOCKS URI cannot contain a query')

    payload = f'{result.netloc}{result.path}'
    decoded = _decodeBase64(payload, 'legacy payload')

    userinfo, separator, endpoint = decoded.rpartition('@')

    if not separator:
        raise SocksURIError('legacy payload has no server separator')

    if ':' not in userinfo:
        raise SocksURIError('legacy userinfo has no credential separator')

    username, password = userinfo.split(':', 1)
    host, port = _parseEndpoint(endpoint)
    tag = _percentDecode(result.fragment, 'tag')

    return SocksURIData(host, port, username, password, tag)


def parseSocksURI(uri: str) -> SocksURIData:
    """Parse standard and v2rayN-compatible SOCKS share-link forms."""
    if not isinstance(uri, str) or not uri.strip():
        raise SocksURIError('SOCKS URI cannot be empty')

    try:
        result = urlsplit(uri.strip())
    except ValueError as ex:
        raise SocksURIError('SOCKS URI is malformed') from ex

    if result.scheme.casefold() not in SOCKS_URI_SCHEMES:
        raise SocksURIError('URI scheme must identify SOCKS')

    if result.query:
        raise SocksURIError('SOCKS URI cannot contain a query')

    if '@' not in result.netloc:
        try:
            host, port = _parseEndpoint(result.netloc)
        except SocksURIError as endpointError:
            try:
                return _parseLegacyURI(result)
            except SocksURIError:
                raise endpointError

        if result.path not in ('', '/'):
            raise SocksURIError('SOCKS URI path must be empty or /')

        return SocksURIData(
            host,
            port,
            tag=_percentDecode(result.fragment, 'tag'),
        )

    if result.path not in ('', '/'):
        raise SocksURIError('SOCKS URI path must be empty or /')

    userinfo, separator, endpoint = result.netloc.rpartition('@')

    if not separator or not userinfo:
        raise SocksURIError('SOCKS URI userinfo is malformed')

    username, password = _parseUserinfo(userinfo)
    host, port = _parseEndpoint(endpoint)
    tag = _percentDecode(result.fragment, 'tag')

    return SocksURIData(host, port, username, password, tag)


def _formatHost(host: str) -> str:
    """Return a canonical URI host, bracketing IPv6 literals."""
    normalized = _normalizeHost(host)

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return normalized

    return f'[{address.compressed}]' if address.version == 6 else address.compressed


def serializeSocksURI(value: SocksURIData) -> str:
    """Serialize a SOCKS profile using unambiguous RFC3986 userinfo."""
    if not isinstance(value, SocksURIData):
        raise TypeError('value must be a SocksURIData instance')

    port = _parsePort(value.port)
    endpoint = f'{_formatHost(value.host)}:{port}'
    fragment = quote(value.tag, safe='')
    authority = endpoint

    if value.username or value.password:
        authority = (
            f'{quote(value.username, safe="")}:'
            f'{quote(value.password, safe="")}@{endpoint}'
        )

    return f'socks://{authority}{"#" + fragment if fragment else ""}'
