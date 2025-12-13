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

from __future__ import annotations

from Furious.Frozenlib.Constants import *

from enum import Enum
from typing import AnyStr, Tuple

import os
import time
import pathlib
import operator
import functools
import ipaddress
import subprocess
import urllib.parse

__all__ = [
    'Protocol',
    'callRateLimited',
    'callOnceOnly',
    'classname',
    'isValidIPAddress',
    'parseHostPort',
    'runExternalCommand',
    'absolutePath',
    'versionToValue',
]


class Protocol(Enum):
    Unknown = 'Unknown'
    VMess = 'VMess'
    VLESS = 'VLESS'
    Shadowsocks = 'Shadowsocks'
    Trojan = 'Trojan'
    Hysteria1 = 'hysteria1'
    Hysteria2 = 'hysteria2'

    @staticmethod
    @functools.lru_cache(None)
    def toEnum(protocol: str):
        if not isinstance(protocol, str):
            return Protocol.Unknown

        if protocol.lower() == 'vmess':
            return Protocol.VMess

        if protocol.lower() == 'vless':
            return Protocol.VLESS

        if protocol.lower() == 'shadowsocks':
            return Protocol.Shadowsocks

        if protocol.lower() == 'trojan':
            return Protocol.Trojan

        return Protocol.Unknown


def callRateLimited(maxCallPerSecond):
    """
    Decorator function that limits the rate at which a function can be called.
    """
    interval = 1.0 / float(maxCallPerSecond)
    called = time.monotonic()

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Previously called
            nonlocal called

            elapsed = time.monotonic() - called
            waitsec = interval - elapsed

            if waitsec > 0:
                time.sleep(waitsec)

            result = func(*args, **kwargs)
            called = time.monotonic()

            return result

        return wrapper

    return decorator


def callOnceOnly(func):
    """
    Decorator that ensures a function is only called once.
    Later calls return the cached result from the first invocation.
    """
    result = None
    called = False

    def wrapper(*args, **kwargs):
        nonlocal result, called

        if not called:
            result = func(*args, **kwargs)
            called = True

        return result

    return wrapper


def classname(ob) -> str:
    return ob.__class__.__name__


@functools.lru_cache(None)
def isValidIPAddress(address) -> bool:
    try:
        ipaddress.ip_address(address)
    except Exception:
        # Any non-exit exceptions

        return False
    else:
        return True


# Can throw exceptions
@functools.lru_cache(None)
def parseHostPort(address: str) -> Tuple[AnyStr | None, str | None]:
    if address.find('//') == -1:
        result = urllib.parse.urlsplit('//' + address)
    else:
        result = urllib.parse.urlsplit(address)

    if result.hostname is None:
        hostname = None
    else:
        hostname = result.hostname

    if result.port is None:
        port = None
    else:
        port = str(result.port)

    return hostname, port


def runExternalCommand(*args, **kwargs):
    if PLATFORM == 'Windows':
        creationflags = kwargs.pop('creationflags', subprocess.CREATE_NO_WINDOW)

        return subprocess.run(*args, creationflags=creationflags, **kwargs)
    else:
        return subprocess.run(*args, **kwargs)


@functools.lru_cache(None)
def absolutePath(path) -> pathlib.Path:
    return pathlib.Path(path) if os.path.isabs(path) else ROOT_DIR / path


@functools.lru_cache(None)
def versionToValue(version: str) -> int:
    def split():
        # x or x.y or x.y.z or x.y.z.u
        result = version.split('.')

        while len(result) < 4:
            result.append('0')

        return result

    x_weight = 10**9
    y_weight = 10**6
    z_weight = 10**3
    u_weight = 1

    try:
        x, y, z, u = split()

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
