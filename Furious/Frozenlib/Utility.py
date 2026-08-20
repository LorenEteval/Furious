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

"""Provide bundled utility."""

from __future__ import annotations

from Furious.Frozenlib.Constants import *
from Furious.Frozenlib.AppSettings import *

from typing import AnyStr, Tuple

import os
import time
import pathlib
import operator
import functools
import threading
import ipaddress
import subprocess
import urllib.parse

__all__ = [
    'callRateLimited',
    'forceToLocalhostIfPossible',
    'callOnceOnly',
    'classname',
    'isValidIPAddress',
    'parseHostPort',
    'runExternalCommand',
    'absolutePath',
    'versionToValue',
]


def callRateLimited(maxCallPerSecond):
    """
    Decorate a callable with a non-blocking leading-edge rate limit.

    Calls made before the interval elapses are skipped instead of sleeping the
    calling thread.  This keeps the helper safe for GUI-thread slots.
    """
    rate = float(maxCallPerSecond)

    if rate <= 0:
        raise ValueError('maxCallPerSecond must be greater than zero')

    interval = 1.0 / rate

    def decorator(func):
        """Decorate a callable with the enclosing behavior."""
        call = None
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Invoke the wrapped callable with the enclosing behavior."""
            nonlocal call

            now = time.monotonic()

            with lock:
                if call is not None and now - call < interval:
                    # Interval is not reached. Return immediately.
                    return None

                call = now

            return func(*args, **kwargs)

        return wrapper

    return decorator


def forceToLocalhostIfPossible():
    """Return the force to localhost if possible value used by the application."""

    def decorator(func):
        """Decorate a callable with the enclosing behavior."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Invoke the wrapped callable with the enclosing behavior."""
            result = func(*args, **kwargs)

            if (
                AppSettings.isStateOFF('ForceToLocalhostWhenSettingLocalProxy')
                or not isinstance(result, str)
                or result == ''
            ):
                return result

            # Force to localhost according to settings
            try:
                host, port = parseHostPort(result)

                return f'127.0.0.1:{port}'
            except Exception:
                # Any non-exit exceptions

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
        """Invoke the wrapped callable with the enclosing behavior."""
        nonlocal result, called

        if not called:
            result = func(*args, **kwargs)
            called = True

        return result

    return wrapper


def classname(ob) -> str:
    """Return the classname value used by the application."""
    return ob.__class__.__name__


@functools.lru_cache(None)
def isValidIPAddress(address) -> bool:
    """Return whether valid ip address."""
    try:
        ipaddress.ip_address(address)
    except Exception:
        # Any non-exit exceptions

        return False
    else:
        return True


# Can throw exceptions
@functools.lru_cache(256)
def parseHostPort(address: str) -> Tuple[AnyStr | None, str | None]:
    """Parse host port."""
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
    """Run a blocking external command using caller-supplied subprocess options.

    This low-level wrapper intentionally does not impose a timeout. Callers
    decide whether their command may wait indefinitely and remain responsible
    for keeping potentially slow host operations off the GUI thread.
    """
    if PLATFORM == 'Windows':
        creationflags = kwargs.pop('creationflags', subprocess.CREATE_NO_WINDOW)

        return subprocess.run(*args, creationflags=creationflags, **kwargs)
    else:
        return subprocess.run(*args, **kwargs)


@functools.lru_cache(None)
def absolutePath(path) -> pathlib.Path:
    """Return the absolute path value used by the application."""
    return pathlib.Path(path) if os.path.isabs(path) else ROOT_DIR / path


@functools.lru_cache(None)
def versionToValue(version: str) -> int:
    """Return the version to value value used by the application."""

    def split():
        # x or x.y or x.y.z or x.y.z.u
        """Split the application."""
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
