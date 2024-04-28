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
from Furious.Utility import *
from Furious.Library.Configuration import *

__all__ = ['getEmptyFactory']

RAY_TEMPLATE = constructFromDict(
    {
        'log': {
            'access': '',
            'error': '',
            'loglevel': 'warning',
        },
        'inbounds': [
            {
                'tag': 'socks',
                'port': 10808,
                'listen': '127.0.0.1',
                'protocol': 'socks',
                'sniffing': {
                    'enabled': True,
                    'destOverride': [
                        'http',
                        'tls',
                    ],
                },
                'settings': {
                    'auth': 'noauth',
                    'udp': True,
                    'allowTransparent': False,
                },
            },
            {
                'tag': 'http',
                'port': 10809,
                'listen': '127.0.0.1',
                'protocol': 'http',
                'sniffing': {
                    'enabled': True,
                    'destOverride': [
                        'http',
                        'tls',
                    ],
                },
                'settings': {
                    'auth': 'noauth',
                    'udp': True,
                    'allowTransparent': False,
                },
            },
        ],
        'outbounds': [
            {
                'tag': 'proxy',
                'protocol': '',
                'settings': {},
                'streamSettings': {
                    'network': 'tcp',
                },
                'mux': {
                    'enabled': False,
                    'concurrency': -1,
                },
            },
            {
                'tag': 'direct',
                'protocol': 'freedom',
                'settings': {},
            },
            {
                'tag': 'block',
                'protocol': 'blackhole',
                'settings': {
                    'response': {
                        'type': 'http',
                    }
                },
            },
        ],
        'routing': {},
    }
)

HY1_TEMPLATE = constructFromDict(
    {
        'server': '',
        'protocol': 'udp',
        'socks5': {
            'listen': '127.0.0.1:10808',
        },
        'http': {
            'listen': '127.0.0.1:10809',
        },
    }
)

HY2_TEMPLATE = constructFromDict(
    {
        'server': '',
        'tls': {
            'insecure': False,
        },
        'socks5': {
            'listen': '127.0.0.1:10808',
        },
        'http': {
            'listen': '127.0.0.1:10809',
        },
    }
)


def getEmptyFactory(protocol: str) -> ConfigurationFactory:
    if (
        protocolRepr(protocol) == Protocol.VMess
        or protocolRepr(protocol) == Protocol.VLESS
    ):
        factory = RAY_TEMPLATE.deepcopy()
        factory['outbounds'][0]['protocol'] = protocol.lower()
        factory['outbounds'][0]['settings']['vnext'] = [
            {
                'address': '',
                'port': 0,
                'users': [{'email': PROXY_OUTBOUND_USER_EMAIL}],
            },
        ]

        return factory

    if (
        protocolRepr(protocol) == Protocol.Shadowsocks
        or protocolRepr(protocol) == Protocol.Trojan
    ):
        factory = RAY_TEMPLATE.deepcopy()
        factory['outbounds'][0]['protocol'] = protocol.lower()
        factory['outbounds'][0]['settings']['servers'] = [
            {
                'address': '',
                'port': 0,
                'email': PROXY_OUTBOUND_USER_EMAIL,
            },
        ]

        return factory

    if protocolRepr(protocol) == Protocol.Hysteria1:
        factory = HY1_TEMPLATE.deepcopy()

        return factory
    if protocolRepr(protocol) == Protocol.Hysteria2:
        factory = HY2_TEMPLATE.deepcopy()

        return factory

    return ConfigurationFactory()
