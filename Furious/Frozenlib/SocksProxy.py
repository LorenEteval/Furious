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

"""Provide local SOCKS endpoint validation and normalization helpers."""

from __future__ import annotations

import ipaddress
import urllib.parse


def socksURL(endpoint):
    """Normalize a local listener without permitting direct DNS or logging secrets."""
    if (
        not isinstance(endpoint, str)
        or not endpoint
        or any(c in endpoint for c in '\x00\r\n')
    ):
        raise ValueError('A local SOCKS endpoint is required')

    # Xray's legacy accessor can produce an unbracketed IPv6 host:port.
    if (
        '://' not in endpoint
        and not endpoint.startswith('[')
        and endpoint.count(':') > 1
    ):
        host, port = endpoint.rsplit(':', 1)

        endpoint = '[' + host + ']:' + port

    try:
        parsed = urllib.parse.urlsplit(
            endpoint if '://' in endpoint else 'socks5://' + endpoint
        )

        if parsed.scheme != 'socks5' or parsed.path or parsed.query or parsed.fragment:
            raise ValueError()

        host = parsed.hostname

        if host == 'localhost':
            host = '127.0.0.1'

        address = ipaddress.ip_address(host)

        if address.is_unspecified:
            address = ipaddress.ip_address(
                '::1' if address.version == 6 else '127.0.0.1'
            )

        port = parsed.port

        if port is None or not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(
            'Invalid local SOCKS endpoint (IP address and port required)'
        ) from None

    host = '[' + str(address) + ']' if address.version == 6 else str(address)
    credentials = ''

    if parsed.username is not None:
        username = urllib.parse.unquote(parsed.username)
        password = urllib.parse.unquote(parsed.password or '')

        if (
            not username
            or not password
            or max(len(username.encode()), len(password.encode())) > 255
        ):
            raise ValueError('Invalid SOCKS authentication credentials')

        credentials = (
            urllib.parse.quote(username, safe='')
            + ':'
            + urllib.parse.quote(password, safe='')
            + '@'
        )

    return 'socks5://' + credentials + host + ':' + str(port)
