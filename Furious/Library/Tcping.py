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

from typing import Tuple

import time
import socket
import ipaddress
import functools

__all__ = ['tcping']


def tcping(
    address: str,
    port: int,
    timeout: float,
    count: int,
    interval: float,
) -> Tuple[int, list]:
    host = socket.gethostbyname(address)
    addressobject = ipaddress.ip_address(host)

    if isinstance(addressobject, ipaddress.IPv4Address):
        socketFn = functools.partial(
            socket.socket,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    elif isinstance(addressobject, ipaddress.IPv6Address):
        socketFn = functools.partial(
            socket.socket,
            family=socket.AF_INET6,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    else:
        raise ValueError('Invalid address')

    sent = 0
    rtts = []

    for sequence in range(count):
        if sequence > 0:
            time.sleep(interval)

        with socketFn() as sock:
            sock.settimeout(timeout)

            counter = time.perf_counter()

            try:
                sock.connect((address, port))
            except Exception:
                # Any non-exit exceptions

                pass
            else:
                sent += 1

                rtts.append(time.perf_counter() - counter)

    return sent, rtts
