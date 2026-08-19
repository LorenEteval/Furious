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

"""Expose application services that coordinate lower-level subsystems."""

from __future__ import annotations

from .ConnectionManager import ConnectionManager
from .ConnectivityManager import ConnectivityManager
from .DnsResolver import DnsResolver
from .EndpointInfoService import (
    PROXY_ENDPOINT_INFO_SETTING,
    EndpointInfo,
    EndpointInfoService,
    EndpointInfoState,
    EndpointLocation,
    ProxyEndpointHttpClient,
)
from .LogManager import (
    ALL_LOGS_FILTER,
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    ApplicationLogHandler,
    LogManager,
    coreLogCallback,
    formatLogEntry,
)
from .MetricsHistory import (
    DOWNLOAD_SPEED_METRIC,
    DOWNLOAD_USAGE_METRIC,
    UPLOAD_SPEED_METRIC,
    UPLOAD_USAGE_METRIC,
    MetricSeriesPoint,
    MetricSample,
    MetricsHistory,
)
from .PluginUIManager import PluginNavigationManager, isCoreActive
from .SubscriptionImporter import (
    SubscriptionImportResult,
    SubscriptionImportService,
    SubscriptionSource,
)
from .SubscriptionSync import SubscriptionSyncResult, SubscriptionSynchronizer
from .TrafficStatsManager import (
    TrafficStatsSample,
    TrafficStatsManager,
    formatTrafficSpeed,
    formatTrafficUsage,
)
from .UpdateManager import UpdateManager

__all__ = [
    'ConnectionManager',
    'ConnectivityManager',
    'DnsResolver',
    'EndpointInfo',
    'EndpointInfoService',
    'EndpointInfoState',
    'PROXY_ENDPOINT_INFO_SETTING',
    'EndpointLocation',
    'ProxyEndpointHttpClient',
    'ALL_LOGS_FILTER',
    'APPLICATION_LOG_CATEGORY',
    'CORE_LOG_CATEGORY',
    'TUN2SOCKS_LOG_CATEGORY',
    'ApplicationLogHandler',
    'LogManager',
    'DOWNLOAD_SPEED_METRIC',
    'DOWNLOAD_USAGE_METRIC',
    'UPLOAD_SPEED_METRIC',
    'UPLOAD_USAGE_METRIC',
    'MetricSeriesPoint',
    'MetricSample',
    'MetricsHistory',
    'PluginNavigationManager',
    'coreLogCallback',
    'SubscriptionImportResult',
    'SubscriptionImportService',
    'SubscriptionSource',
    'SubscriptionSyncResult',
    'SubscriptionSynchronizer',
    'TrafficStatsSample',
    'TrafficStatsManager',
    'UpdateManager',
    'formatTrafficSpeed',
    'formatTrafficUsage',
    'formatLogEntry',
    'isCoreActive',
]
