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

"""Provide bundled tcping."""

from __future__ import annotations

from typing import Tuple

import time
import socket

__all__ = ['tcping']


def tcping(
    address: str,
    port: int,
    timeout: float,
    count: int,
    interval: float,
) -> Tuple[int, list]:
    """Return the tcping value used by the application."""
    candidates = []
    seen = set()

    for (
        family,
        socketType,
        protocol,
        _canonicalName,
        socketAddress,
    ) in socket.getaddrinfo(
        address,
        port,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    ):
        candidate = (family, socketType, protocol, socketAddress)

        if candidate not in seen:
            seen.add(candidate)

            candidates.append(candidate)

    if not candidates:
        raise OSError(f'no TCP address found for {address!r}')

    sent = 0
    rtts = []

    for sequence in range(count):
        if sequence > 0:
            time.sleep(interval)

        counter = time.perf_counter()

        for family, socketType, protocol, socketAddress in candidates:
            with socket.socket(family, socketType, protocol) as sock:
                sock.settimeout(timeout)

                try:
                    sock.connect(socketAddress)
                except OSError:
                    continue

                sent += 1
                rtts.append(time.perf_counter() - counter)

                break

    return sent, rtts
