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

"""Query Hysteria 2 server traffic statistics through its HTTP API."""

from __future__ import annotations

from Furious.Frozenlib import AppSettings, registerAppSettings
from Furious.Plugins.API import (
    TrafficCounters,
    TrafficStatsMonitor,
    TrafficStatsProvider,
)

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import json

from .Process import Hysteria2

__all__ = [
    'HYSTERIA2_STATS_CLIENT_ID_SETTING',
    'HYSTERIA2_STATS_SECRET_SETTING',
    'HYSTERIA2_STATS_URL_SETTING',
    'Hysteria2StatsProvider',
    'Hysteria2StatsTarget',
    'configuredHysteria2StatsTarget',
    'normalizeHysteria2StatsURL',
    'queryHysteria2TrafficStats',
]

HYSTERIA2_STATS_URL_SETTING = 'Hysteria2TrafficStatsURL'
HYSTERIA2_STATS_CLIENT_ID_SETTING = 'Hysteria2TrafficStatsClientID'
HYSTERIA2_STATS_SECRET_SETTING = 'Hysteria2TrafficStatsSecret'
HYSTERIA2_STATS_QUERY_TIMEOUT = 2
HYSTERIA2_STATS_RESPONSE_LIMIT = 2 * 1024 * 1024

registerAppSettings(HYSTERIA2_STATS_URL_SETTING)
registerAppSettings(HYSTERIA2_STATS_CLIENT_ID_SETTING)
registerAppSettings(HYSTERIA2_STATS_SECRET_SETTING)


@dataclass(frozen=True)
class Hysteria2StatsTarget:
    """Describe one authenticated Hysteria 2 server statistics endpoint."""

    trafficURL: str
    clientId: str
    secret: str = ''
    timeout: int = HYSTERIA2_STATS_QUERY_TIMEOUT


def normalizeHysteria2StatsURL(value: str) -> Optional[str]:
    """Return an HTTP(S) URL ending at the documented ``/traffic`` endpoint."""
    if not isinstance(value, str) or not value.strip():
        return None

    candidate = value.strip()

    if '://' not in candidate:
        candidate = f'http://{candidate}'

    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None

    try:
        hostname, port = (
            parsed.hostname,
            parsed.port,
        )
    except ValueError:
        return None

    if parsed.scheme.casefold() not in ('http', 'https') or not hostname:
        return None

    path = parsed.path.rstrip('/')

    if not path.casefold().endswith('/traffic'):
        path = f'{path}/traffic'

    # The shared manager requires cumulative counters, so never preserve the
    # API's ``clear`` query option supplied in a pasted URL.
    return urlunsplit((parsed.scheme, parsed.netloc, path, '', ''))


def configuredHysteria2StatsTarget() -> Optional[Hysteria2StatsTarget]:
    """Build a target from the explicitly configured server API settings."""
    trafficURL = normalizeHysteria2StatsURL(
        str(AppSettings.get(HYSTERIA2_STATS_URL_SETTING) or '')
    )

    if trafficURL is None:
        return None

    clientId = str(AppSettings.get(HYSTERIA2_STATS_CLIENT_ID_SETTING) or '').strip()

    if not clientId:
        return None

    secret = str(AppSettings.get(HYSTERIA2_STATS_SECRET_SETTING) or '')

    return Hysteria2StatsTarget(trafficURL, clientId, secret)


def _nonNegativeInteger(value) -> Optional[int]:
    """Return one valid byte counter without accepting booleans or negatives."""
    if isinstance(value, bool):
        return None

    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None

    return result if result >= 0 else None


def queryHysteria2TrafficStats(
    target: Hysteria2StatsTarget,
) -> Optional[TrafficCounters]:
    """Return cumulative counters for the configured Hysteria authentication ID."""
    if not isinstance(target, Hysteria2StatsTarget):
        return None

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Furious-GUI',
    }

    if target.secret:
        headers['Authorization'] = target.secret

    request = Request(target.trafficURL, headers=headers, method='GET')

    try:
        with urlopen(request, timeout=target.timeout) as response:
            content = response.read(HYSTERIA2_STATS_RESPONSE_LIMIT + 1)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError):
        return None

    if len(content) > HYSTERIA2_STATS_RESPONSE_LIMIT:
        return None

    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return None

    if not isinstance(payload, Mapping):
        return None

    counters = payload.get(target.clientId)

    if counters is None:
        return TrafficCounters(uplink=0, downlink=0)

    if not isinstance(counters, Mapping):
        return None

    uplink, downlink = (
        _nonNegativeInteger(counters.get('tx')),
        _nonNegativeInteger(counters.get('rx')),
    )

    if uplink is None or downlink is None:
        return None

    # The server traffic logger records client-to-remote bytes as tx and
    # remote-to-client bytes as rx.
    return TrafficCounters(uplink=uplink, downlink=downlink)


class Hysteria2StatsProvider(TrafficStatsProvider):
    """Expose Hysteria server counters through the shared metrics capability."""

    providerId = 'official.hysteria2.stats'
    kernelTypes = (Hysteria2,)

    def monitorForKernel(self, kernel) -> Optional[TrafficStatsMonitor]:
        """Return a monitor when the active kernel has a configured API target."""
        target = getattr(kernel, 'hysteria2StatsTarget', None)

        if not isinstance(target, Hysteria2StatsTarget):
            return None

        return TrafficStatsMonitor(queryHysteria2TrafficStats, target)
