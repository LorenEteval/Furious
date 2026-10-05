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

"""Pure configuration preparation for the application sing-tun bridge."""

from __future__ import annotations

import copy
import functools
import ipaddress
import math
import re

SING_TUN_HOST_DEFAULTS = {
    'primaryAdapterInterfaceName': '',
    'primaryAdapterInterfaceIP': '',
    'tunAdapterInterfaceDNS': '',
    'bypassTUNAdapterInterfaceIP': '',
    'disablePrimaryAdapterInterfaceDNS': True,
}

SING_TUN_DEFAULTS = {
    'stack': 'go',
    'log_level': 'error',
    'network_interface': '',
    'max_sessions': 1024,
    'udp_timeout': 60,
    'connect_timeout': 10,
    'tcp_idle_timeout': 300,
    'tun_options': {
        'Name': '',
        'MTU': 1500,
        'Inet4Address': ['198.18.0.1/15'],
        'Inet6Address': [],
        'AutoRoute': True,
        'EXP_ExternalConfiguration': False,
        'DNSMode': 'disabled',
        'EXP_DisableDNSHijack': True,
    },
    'stack_options': {'UDPTimeout': '1m'},
    'host_options': SING_TUN_HOST_DEFAULTS,
}
_OWNED = {
    'AutoRoute': True,
    'EXP_ExternalConfiguration': False,
    'DNSMode': 'disabled',
    'EXP_DisableDNSHijack': True,
}
_PREFIXES = {
    'Inet4Address': 4,
    'Inet6Address': 6,
    'Inet4RouteAddress': 4,
    'Inet6RouteAddress': 6,
    'Inet4RouteExcludeAddress': 4,
    'Inet6RouteExcludeAddress': 6,
}
_TUN_FIELDS = {*_PREFIXES, *_OWNED, 'Name', 'MTU', 'StrictRoute', 'InterfaceScope'}
_STACK_FIELDS = {
    'UDPTimeout',
    'ICMPTimeout',
    'UDPNATMax',
    'UDPMapping',
    'UDPFiltering',
    'ForwarderBindInterface',
    'IncludeAllNetworks',
    'TCPCongestionControl',
}


class SingTUNHostSettingsCallers:
    """Bind sing-tun's named host settings callers to a captured host document."""

    def __init__(self, settings):
        if not isinstance(settings, dict):
            raise ValueError('host_options must be an object')

        (
            self.userPrimaryAdapterInterfaceName,
            self.userPrimaryAdapterInterfaceIP,
            self.userTunAdapterInterfaceDNS,
            self.userBypassTUNAdapterInterfaceIP,
            self.userDisablePrimaryAdapterInterfaceDNS,
        ) = (
            functools.partial(
                settings.get,
                'primaryAdapterInterfaceName',
                SING_TUN_HOST_DEFAULTS['primaryAdapterInterfaceName'],
            ),
            functools.partial(
                settings.get,
                'primaryAdapterInterfaceIP',
                SING_TUN_HOST_DEFAULTS['primaryAdapterInterfaceIP'],
            ),
            functools.partial(
                settings.get,
                'tunAdapterInterfaceDNS',
                SING_TUN_HOST_DEFAULTS['tunAdapterInterfaceDNS'],
            ),
            functools.partial(
                settings.get,
                'bypassTUNAdapterInterfaceIP',
                SING_TUN_HOST_DEFAULTS['bypassTUNAdapterInterfaceIP'],
            ),
            functools.partial(
                settings.get,
                'disablePrimaryAdapterInterfaceDNS',
                SING_TUN_HOST_DEFAULTS['disablePrimaryAdapterInterfaceDNS'],
            ),
        )


def durationSeconds(value):
    """Read Go duration strings (or integer nanoseconds), without native imports."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value / 1e9

    if not isinstance(value, str) or len(value) > 80:
        raise ValueError('Use a Go duration such as 1m or 30s')

    parts = re.findall(r'(\d+(?:\.\d+)?)(ns|us|µs|μs|ms|s|m|h)', value)

    if not parts or ''.join(number + unit for number, unit in parts) != value:
        raise ValueError('Use a Go duration such as 1m or 30s')

    units = {
        'ns': 1e-9,
        'us': 1e-6,
        'µs': 1e-6,
        'μs': 1e-6,
        'ms': 0.001,
        's': 1,
        'm': 60,
        'h': 3600,
    }

    return sum(float(number) * units[unit] for number, unit in parts)


def prepareSingTUNSettings(document, *, platform=None):
    """Validate copied settings; the stored document is never normalized in place."""
    if not isinstance(document, dict):
        raise ValueError('sing-tun settings must be an object')

    if set(document) - set(SING_TUN_DEFAULTS):
        raise ValueError('Unsupported sing-tun settings fields')

    result = copy.deepcopy(SING_TUN_DEFAULTS)

    for key, value in document.items():
        if key in ('tun_options', 'stack_options', 'host_options'):
            if not isinstance(value, dict):
                raise ValueError(key + ' must be an object')

            result[key].update(copy.deepcopy(value))
        else:
            result[key] = copy.deepcopy(value)

    if result['stack'] not in ('', 'go', 'gvisor', 'system', 'mixed'):
        raise ValueError('Unsupported sing-tun stack')

    if result['log_level'] not in ('trace', 'debug', 'info', 'warn', 'error', 'silent'):
        raise ValueError('Invalid sing-tun log level')

    for key in ('network_interface',):
        if (
            not isinstance(result[key], str)
            or len(result[key]) > 256
            or any(c in result[key] for c in '\x00\r\n')
        ):
            raise ValueError('Invalid ' + key)

    sessions = result['max_sessions']

    if type(sessions) is not int or not 1 <= sessions <= 16384:
        raise ValueError('max_sessions must be between 1 and 16384')

    for key in ('udp_timeout', 'connect_timeout', 'tcp_idle_timeout'):
        value = result[key]

        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0.05 <= value <= 86400
        ):
            raise ValueError(key + ' must be between 0.05 and 86400 seconds')

    tun, stack = result['tun_options'], result['stack_options']

    if set(tun) - _TUN_FIELDS or set(stack) - _STACK_FIELDS:
        raise ValueError('Unsupported or application-owned native option')

    for key, expected in _OWNED.items():
        if type(tun[key]) is not type(expected) or tun[key] != expected:
            raise ValueError(key + ' is managed by Furious')

    if not isinstance(tun['Name'], str) or not re.fullmatch(
        r'[a-zA-Z0-9_.-]{0,32}', tun['Name']
    ):
        raise ValueError('Invalid TUN device name')

    if type(tun['MTU']) is not int or not 68 <= tun['MTU'] <= 65535:
        raise ValueError('MTU must be between 68 and 65535')

    for key, family in _PREFIXES.items():
        if key not in tun:
            continue

        if not isinstance(tun[key], list) or len(tun[key]) > 256:
            raise ValueError(key + ' must be a bounded prefix list')

        for prefix in tun[key]:
            try:
                if (
                    not isinstance(prefix, str)
                    or ipaddress.ip_interface(prefix).version != family
                ):
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValueError('Invalid prefix in ' + key) from None

    if not tun['Inet4Address'] and not tun['Inet6Address']:
        raise ValueError('At least one TUN address prefix is required')

    if tun['Inet6Address'] and tun['MTU'] < 1280:
        raise ValueError('IPv6 requires an MTU of at least 1280 bytes')

    if tun.get('StrictRoute') and (not tun['Inet4Address'] or not tun['Inet6Address']):
        raise ValueError(
            'StrictRoute requires both address families to preserve remote bypasses'
        )

    if platform == 'Darwin' and tun.get('InterfaceScope'):
        raise ValueError(
            'Scoped macOS routes require binding support for scoped route cleanup'
        )

    for options, keys in (
        (tun, ('StrictRoute', 'InterfaceScope')),
        (stack, ('ForwarderBindInterface', 'IncludeAllNetworks')),
    ):
        for key in keys:
            if key in options and type(options[key]) is not bool:
                raise ValueError(key + ' must be a boolean')

    if stack.get('IncludeAllNetworks') and result['stack'] != 'gvisor':
        raise ValueError('IncludeAllNetworks requires an explicit gvisor stack')

    if stack.get('ForwarderBindInterface') and result['stack'] in ('', 'go'):
        raise ValueError('ForwarderBindInterface is not used by the go stack')

    congestion = stack.get('TCPCongestionControl', '')

    if type(congestion) is not str or congestion not in ('', 'cubic', 'reno', 'bbr'):
        raise ValueError('Invalid TCPCongestionControl')

    if congestion and result['stack'] not in ('', 'go'):
        raise ValueError('TCPCongestionControl requires go or automatic stack')

    for key in ('UDPTimeout', 'ICMPTimeout'):
        if key in stack:
            seconds = durationSeconds(stack[key])

            if (
                not math.isfinite(seconds)
                or seconds < 0
                or (key == 'UDPTimeout' and seconds == 0)
                or seconds > 86400
            ):
                raise ValueError('Invalid ' + key)

    for key, maximum in (
        ('UDPNATMax', 4294967295),
        ('UDPMapping', 2),
        ('UDPFiltering', 2),
    ):
        if key in stack and (
            type(stack[key]) is not int or not 0 <= stack[key] <= maximum
        ):
            raise ValueError('Invalid ' + key)

    result['host_options'] = prepareSingHostSettings(result['host_options'])

    return result


def prepareSingHostSettings(document):
    """Validate sing-tun's own DNS, physical adapter and bypass preferences."""
    if not isinstance(document, dict):
        raise ValueError('sing-tun host options must be an object')

    if set(document) - set(SING_TUN_HOST_DEFAULTS):
        raise ValueError('Unsupported sing-tun host options')

    result = copy.deepcopy(SING_TUN_HOST_DEFAULTS)
    result.update(copy.deepcopy(document))

    for key in (
        'primaryAdapterInterfaceName',
        'primaryAdapterInterfaceIP',
        'tunAdapterInterfaceDNS',
        'bypassTUNAdapterInterfaceIP',
    ):
        value = result[key]

        if (
            not isinstance(value, str)
            or len(value) > 8192
            or any(char in value for char in '\x00\r\n')
        ):
            raise ValueError('Invalid sing-tun host field: ' + key)

        if key.endswith('IP') or key == 'tunAdapterInterfaceDNS':
            try:
                addresses = (
                    value.split(',')
                    if key == 'bypassTUNAdapterInterfaceIP'
                    else [value]
                )

                for address in addresses if value else []:
                    ipaddress.ip_address(address.strip())
            except ValueError:
                raise ValueError(
                    'Invalid IP address in sing-tun host field: ' + key
                ) from None

    if type(result['disablePrimaryAdapterInterfaceDNS']) is not bool:
        raise ValueError('sing-tun primary adapter DNS mitigation must be a boolean')

    return result


def addSingTUNExclusions(settings, addresses):
    """Merge attempt-only outbound exclusions with explicit user ranges."""
    prepared = copy.deepcopy(settings)

    for text in addresses:
        address = ipaddress.ip_address(text)
        key = (
            'Inet4RouteExcludeAddress'
            if address.version == 4
            else 'Inet6RouteExcludeAddress'
        )
        entries = prepared['tun_options'].setdefault(key, [])
        prefix = str(address) + ('/32' if address.version == 4 else '/128')

        if prefix not in entries:
            entries.append(prefix)

    return prepared
