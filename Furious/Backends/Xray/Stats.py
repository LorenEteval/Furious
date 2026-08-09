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

"""Configure and query Xray outbound traffic statistics."""

from __future__ import annotations

from Furious.Plugins.API import (
    TrafficCounters,
    TrafficStatsMonitor,
    TrafficStatsProvider,
)

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional

import json
import socket

try:
    import xray
except Exception:
    # Any non-exit exceptions

    xray = None

from .Process import XrayCore

__all__ = [
    'XRAY_STATS_QUERY_TIMEOUT',
    'XrayStatsProvider',
    'XrayStatsTarget',
    'buildXrayStats',
    'configureXrayStats',
    'queryXrayOutboundStats',
    'queryXrayStats',
]

XRAY_STATS_API_HOST = '127.0.0.1'
XRAY_STATS_QUERY_TIMEOUT = 1


@dataclass(frozen=True)
class XrayStatsTarget:
    """Describe the active local Xray statistics API and outbound tag."""

    apiServer: str
    outboundTag: str
    timeout: int = XRAY_STATS_QUERY_TIMEOUT
    reset: bool = False


def _proxyOutboundTag(config: Mapping) -> Optional[str]:
    """Return the tag of the configured Xray proxy outbound."""
    if not isinstance(config, Mapping):
        return None

    outbounds = config.get('outbounds', [])

    if not isinstance(outbounds, list):
        return None

    for outbound in outbounds:
        if not isinstance(outbound, Mapping):
            continue

        tag = outbound.get('tag')

        if isinstance(tag, str) and tag.casefold() == 'proxy':
            return tag

    return None


def _availableXrayStatsApiServer() -> str:
    """Select an available loopback endpoint for the next Xray launch."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((XRAY_STATS_API_HOST, 0))

        return f'{XRAY_STATS_API_HOST}:{listener.getsockname()[1]}'


def buildXrayStats(
    apiServer: Optional[str] = None,
) -> dict:
    """Build the Xray API, stats, and outbound policy configuration."""
    apiServer = apiServer or _availableXrayStatsApiServer()

    return {
        'api': {
            'tag': 'api',
            'listen': apiServer,
            'services': ['StatsService'],
        },
        'stats': {},
        'policy': {
            'system': {
                'statsOutboundUplink': True,
                'statsOutboundDownlink': True,
            },
        },
    }


def configureXrayStats(
    config: dict, apiServer: Optional[str] = None
) -> Optional[XrayStatsTarget]:
    """Enable statistics in *config* for its active proxy outbound."""
    outboundTag = _proxyOutboundTag(config)

    if outboundTag is None:
        return None

    currentApi = config.get('api')

    if not isinstance(currentApi, dict):
        currentApi = {}
        config['api'] = currentApi

    configuredServer = currentApi.get('listen')
    if not isinstance(configuredServer, str) or not configuredServer.strip():
        configuredServer = None

    apiServer = apiServer or configuredServer or _availableXrayStatsApiServer()
    generated = buildXrayStats(apiServer)

    currentApi.setdefault('tag', generated['api']['tag'])
    currentApi['listen'] = apiServer

    services = currentApi.get('services', [])
    if not isinstance(services, list):
        services = []

    currentApi['services'] = list(
        dict.fromkeys(
            [
                *(service for service in services if isinstance(service, str)),
                'StatsService',
            ]
        )
    )

    if not isinstance(config.get('stats'), dict):
        config['stats'] = generated['stats']

    policy = config.get('policy')
    if not isinstance(policy, dict):
        policy = {}
        config['policy'] = policy

    systemPolicy = policy.get('system')
    if not isinstance(systemPolicy, dict):
        systemPolicy = {}
        policy['system'] = systemPolicy

    systemPolicy.update(generated['policy']['system'])

    return XrayStatsTarget(apiServer, outboundTag)


def queryXrayStats(
    apiServer: str,
    timeout: int,
    myPattern: str,
    reset: bool,
) -> Optional[str]:
    """Query the Xray binding and return its raw response when available."""
    if (
        xray is None
        or not isinstance(apiServer, str)
        or not apiServer.strip()
        or not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or timeout <= 0
        or not isinstance(myPattern, str)
        or not isinstance(reset, bool)
    ):
        return None

    try:
        response = xray.queryStats(apiServer, timeout, myPattern, reset)
    except Exception:
        # Any non-exit exceptions

        return None

    if isinstance(response, bytes):
        return response.decode('utf-8', 'replace')

    return response if isinstance(response, str) else None


def queryXrayOutboundStats(target: XrayStatsTarget) -> Optional[TrafficCounters]:
    """Return cumulative traffic counters for one configured Xray outbound."""
    if not isinstance(target, XrayStatsTarget) or not target.outboundTag:
        return None

    prefix = f'outbound>>>{target.outboundTag}>>>traffic>>>'
    response = queryXrayStats(
        target.apiServer,
        target.timeout,
        prefix,
        target.reset,
    )

    try:
        payload = json.loads(response)
    except (AttributeError, TypeError, ValueError):
        return None

    if not isinstance(payload, Mapping):
        return None

    statistics = payload.get('stat', [])

    if not isinstance(statistics, list):
        return None

    if not statistics:
        return TrafficCounters(uplink=0, downlink=0)

    values = {}

    for statistic in statistics:
        if not isinstance(statistic, Mapping):
            continue

        name = statistic.get('name')

        if name not in (f'{prefix}uplink', f'{prefix}downlink'):
            continue

        try:
            rawValue = statistic.get('value', 0)

            if isinstance(rawValue, bool):
                continue

            value = int(rawValue)
        except (TypeError, ValueError):
            continue

        if value >= 0:
            values[name.rsplit('>>>', 1)[-1]] = value

    if not values:
        return None

    return TrafficCounters(
        uplink=values.get('uplink', 0),
        downlink=values.get('downlink', 0),
    )


class XrayStatsProvider(TrafficStatsProvider):
    """Expose active Xray outbound traffic through the plugin capability API."""

    providerId = 'official.xray.stats'
    kernelTypes = (XrayCore,)

    def monitorForKernel(self, kernel) -> Optional[TrafficStatsMonitor]:
        """Return a monitor when the active core has a valid outbound target."""
        target = getattr(kernel, 'xrayStatsTarget', None)

        if not isinstance(target, XrayStatsTarget):
            return None

        return TrafficStatsMonitor(queryXrayOutboundStats, target)
