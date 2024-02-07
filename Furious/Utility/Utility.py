from __future__ import annotations

from Furious.Utility.Constants import *

from typing import AnyStr, Tuple

import os
import ujson
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
