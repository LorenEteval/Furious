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

from Furious.Utility.Constants import *

from typing import AnyStr, Tuple

import os
import ujson
import operator
import functools
import ipaddress
import subprocess
import urllib.parse

__all__ = [
    'Protocol',
    'BinarySettings',
    'protocolRepr',
    'isValidIPAddress',
    'parseHostPort',
    'runExternalCommand',
    'getAbsolutePath',
    'versionToValue',
    'getXrayProxyOutboundObject',
    'getXrayProxyOutboundStream',
]


class Protocol:
    VMess = 'VMess'
    VLESS = 'VLESS'
    Shadowsocks = 'Shadowsocks'
    Trojan = 'Trojan'
    Hysteria1 = 'hysteria1'
    Hysteria2 = 'hysteria2'


class BinarySettings:
    OFF = '0'
    ON_ = '1'

    RANGE = [OFF, ON_]


@functools.lru_cache(None)
def protocolRepr(protocol: str) -> str:
    if not isinstance(protocol, str):
        return ''

    if protocol.lower() == 'vmess':
        return Protocol.VMess

    if protocol.lower() == 'vless':
        return Protocol.VLESS

    if protocol.lower() == 'shadowsocks':
        return Protocol.Shadowsocks

    if protocol.lower() == 'trojan':
        return Protocol.Trojan

    return protocol


@functools.lru_cache(None)
def isValidIPAddress(address) -> bool:
    try:
        ipaddress.ip_address(address)
    except Exception:
        # Any non-exita exceptions

        return False
    else:
        return True


# Can throw exceptions
def parseHostPort(address) -> Tuple[AnyStr | None, str]:
    if address.count('//') == 0:
        result = urllib.parse.urlsplit('//' + address)
    else:
        result = urllib.parse.urlsplit(address)

    return result.hostname, str(result.port)


def runExternalCommand(*args, **kwargs):
    if PLATFORM == 'Windows':
        creationflags = kwargs.pop('creationflags', subprocess.CREATE_NO_WINDOW)

        return subprocess.run(*args, creationflags=creationflags, **kwargs)
    else:
        return subprocess.run(*args, **kwargs)


def getAbsolutePath(path):
    return path if os.path.isabs(path) else str(ROOT_DIR / path)


def versionToValue(version: str) -> int:
    def _split():
        # x.y.z or x.y.z.u
        result = version.split('.')

        if len(result) == 3:
            result.append('0')

        return result

    x_weight = 10**9
    y_weight = 10**6
    z_weight = 10**3
    u_weight = 1

    try:
        x, y, z, u = _split()

        return functools.reduce(
            operator.add,
            list(
                int(val) * weight
                for val, weight in zip(
                    [x, y, z, u], [x_weight, y_weight, z_weight, u_weight]
                )
            ),
        )
    except Exception:
        # Any non-exit exceptions

        return 0


def getXrayProxyOutboundObject(config: dict) -> dict:
    if not isinstance(config.get('outbounds'), list):
        config['outbounds'] = []

    for outbound in config['outbounds']:
        if isinstance(outbound, dict):
            tag = outbound.get('tag')

            if isinstance(tag, str) and tag == 'proxy':
                return outbound

    return {}


def getXrayProxyOutboundStream(config: dict) -> dict:
    proxyOutboundObject = getXrayProxyOutboundObject(config)

    if not isinstance(proxyOutboundObject.get('streamSettings'), dict):
        proxyOutboundObject['streamSettings'] = {}

    return proxyOutboundObject['streamSettings']
