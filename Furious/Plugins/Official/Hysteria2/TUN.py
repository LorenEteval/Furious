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

"""Store and apply Hysteria 2 native TUN settings."""

from __future__ import annotations

from Furious.Frozenlib import *

import copy
import ipaddress
import json
import logging
import socket

__all__ = [
    'DEFAULT_HYSTERIA2_TUN_SETTINGS',
    'buildHysteria2TUNConfig',
    'getHysteria2TUNSettings',
    'hasHysteria2TUNConfig',
    'isHysteria2TUNEnabled',
    'resolveHysteria2ServerAddresses',
    'saveHysteria2TUNSettings',
    'setHysteria2TUNEnabled',
]

logger = logging.getLogger(__name__)

DEFAULT_HYSTERIA2_TUN_SETTINGS = {
    'name': 'utun777' if PLATFORM == 'Darwin' else 'hytun',
    'mtu': 1500,
    'timeout': '5m',
    'address': {
        'ipv4': '100.100.100.101/30',
        'ipv6': '2001::ffff:ffff:ffff:fff1/126',
    },
    'route': {
        'ipv4': ['0.0.0.0/0'],
        'ipv6': ['2000::/3'],
        'ipv4Exclude': [],
        'ipv6Exclude': [],
    },
}

registerAppSettings('useHysteria2TUN', isBinary=True, default=AppBinarySettings.ON_)
registerAppSettings('Hysteria2TUNSettings')


def isHysteria2TUNEnabled() -> bool:
    """Return whether Hysteria 2 should provide TUN mode."""
    return AppSettings.isStateON_('useHysteria2TUN')


def setHysteria2TUNEnabled(enabled: bool):
    """Persist whether Hysteria 2 should provide TUN mode."""
    AppSettings.set(
        'useHysteria2TUN',
        AppBinarySettings.ON_ if enabled else AppBinarySettings.OFF,
    )


def _normalizedStringList(value) -> list[str]:
    """Return stripped, non-empty strings from a list-like value."""
    if not isinstance(value, (list, tuple)):
        return []

    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _normalizedHysteria2TUNSettings(settings) -> dict:
    """Return validated Hysteria 2 TUN settings with safe defaults."""
    result = copy.deepcopy(DEFAULT_HYSTERIA2_TUN_SETTINGS)
    if not isinstance(settings, dict):
        return result

    for key in ('name', 'timeout'):
        value = settings.get(key)
        if isinstance(value, str):
            result[key] = value.strip()

    mtu = settings.get('mtu')
    if isinstance(mtu, int) and not isinstance(mtu, bool) and 1 <= mtu <= 65535:
        result['mtu'] = mtu

    address = settings.get('address')
    if isinstance(address, dict):
        for key in ('ipv4', 'ipv6'):
            value = address.get(key)
            if isinstance(value, str):
                result['address'][key] = value.strip()

    route = settings.get('route')
    if isinstance(route, dict):
        for key in ('ipv4', 'ipv6', 'ipv4Exclude', 'ipv6Exclude'):
            value = route.get(key)
            if isinstance(value, (list, tuple)):
                result['route'][key] = _normalizedStringList(value)

    return result


def getHysteria2TUNSettings() -> dict:
    """Return a validated copy of the persisted Hysteria 2 TUN settings."""
    try:
        settings = json.loads(AppSettings.get('Hysteria2TUNSettings'))
    except Exception:
        settings = None

    return _normalizedHysteria2TUNSettings(settings)


def saveHysteria2TUNSettings(settings: dict):
    """Validate and persist Hysteria 2 TUN settings."""
    AppSettings.set(
        'Hysteria2TUNSettings',
        json.dumps(_normalizedHysteria2TUNSettings(settings), ensure_ascii=False),
    )


def _serverHost(config) -> str:
    """Return the Hysteria server host from a config or share-style server URI."""
    server = config.get('server', '')
    if not isinstance(server, str) or not server.strip():
        return ''

    try:
        host, _port = parseHostPort(server.strip())
    except Exception:
        host = None

    if not host:
        try:
            host = config.itemAddress
        except Exception:
            host = server.rsplit(':', 1)[0]

    if not isinstance(host, str):
        return ''

    return host.strip().strip('[]')


def resolveHysteria2ServerAddresses(config) -> list[str]:
    """Resolve addresses that must bypass native TUN to prevent a route loop."""
    host = _serverHost(config)
    if not host:
        return []

    unscopedHost = host.split('%', 1)[0]
    try:
        return [str(ipaddress.ip_address(unscopedHost))]
    except ValueError:
        pass

    addresses = []
    try:
        results = socket.getaddrinfo(
            host,
            0,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_DGRAM,
        )
    except OSError as ex:
        logger.error(f'failed to resolve Hysteria 2 server {host!r}: {ex}')

        return []

    for family, _socketType, _protocol, _canonicalName, socketAddress in results:
        if family not in (socket.AF_INET, socket.AF_INET6) or not socketAddress:
            continue

        address = str(socketAddress[0]).split('%', 1)[0]
        try:
            address = str(ipaddress.ip_address(address))
        except ValueError:
            continue

        if address not in addresses:
            addresses.append(address)

    return addresses


def _hostPrefix(address: str):
    """Return a host CIDR for one IPv4 or IPv6 address."""
    try:
        addressObject = ipaddress.ip_address(address.split('%', 1)[0])
    except ValueError:
        return None, None

    key = 'ipv4Exclude' if addressObject.version == 4 else 'ipv6Exclude'

    return key, f'{addressObject}/{addressObject.max_prefixlen}'


def buildHysteria2TUNConfig(settings=None, serverAddresses=()) -> dict:
    """Build a native TUN config and merge server route-loop exclusions."""
    settings = _normalizedHysteria2TUNSettings(
        getHysteria2TUNSettings() if settings is None else settings
    )

    for address in serverAddresses:
        if not isinstance(address, str):
            continue

        key, prefix = _hostPrefix(address)
        if key is not None and prefix not in settings['route'][key]:
            settings['route'][key].append(prefix)

    result = {
        key: value
        for key, value in {
            'name': settings['name'],
            'mtu': settings['mtu'],
            'timeout': settings['timeout'],
        }.items()
        if value != ''
    }
    address = {key: value for key, value in settings['address'].items() if value != ''}
    route = {key: value for key, value in settings['route'].items() if value != []}

    if address:
        result['address'] = address
    if route:
        result['route'] = route

    return result


def hasHysteria2TUNConfig(config) -> bool:
    """Return whether a Hysteria 2 configuration contains native TUN mode."""
    return isinstance(config.get('tun'), dict)
