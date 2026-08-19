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

"""Discover proxy egress IP and approximate location without direct fallback."""

from __future__ import annotations

from Furious.Frozenlib import (
    AppBinarySettings,
    AppConnectionController,
    AppSettings,
    registerAppSettings,
)
from Furious.Qt.QtNetwork import AppQNetworkAccessManager
from Furious.Repository import Storage

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest

from enum import Enum
from dataclasses import dataclass, replace
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Callable
from urllib.parse import quote

import json
import logging

__all__ = [
    'PROXY_ENDPOINT_INFO_SETTING',
    'EndpointInfo',
    'EndpointInfoService',
    'EndpointInfoState',
    'EndpointLocation',
    'ProxyEndpointHttpClient',
]

logger = logging.getLogger(__name__)

PROXY_ENDPOINT_INFO_SETTING = 'ProxyEndpointInformationEnabled'

registerAppSettings(
    PROXY_ENDPOINT_INFO_SETTING,
    isBinary=True,
    default=AppBinarySettings.OFF,
)


class EndpointInfoState(Enum):
    """Describe the connection-aware endpoint lookup state."""

    Disabled = 'disabled'
    Disconnected = 'disconnected'
    Connecting = 'connecting'
    Loading = 'loading'
    Ready = 'ready'
    Failed = 'failed'


@dataclass(frozen=True)
class EndpointLocation:
    """Describe approximate public-IP geolocation returned by a provider."""

    countryCode: str = ''
    countryName: str = ''
    region: str = ''
    city: str = ''
    latitude: float | None = None
    longitude: float | None = None
    organization: str = ''

    @property
    def displayName(self) -> str:
        """Return the compact city/region/country presentation."""
        values = []

        for value in (self.city, self.region, self.countryName):
            value = str(value or '').strip()

            if value and value not in values:
                values.append(value)

        return ', '.join(values)


@dataclass(frozen=True)
class EndpointInfo:
    """Store one active connection's observed egress information."""

    ipv4: str = ''
    ipv6: str = ''
    location: EndpointLocation = EndpointLocation()
    ipv4Resolved: bool = False
    ipv6Resolved: bool = False
    locationResolved: bool = False

    @property
    def primaryAddress(self) -> str:
        """Return the preferred address used for geolocation."""
        return self.ipv4 or self.ipv6


class ProxyEndpointHttpClient(AppQNetworkAccessManager):
    """Issue bounded HTTPS GET requests through one explicitly configured proxy."""

    completed = QtCore.Signal(object, object, str)

    TimeoutMilliseconds = 5000

    def __init__(self, parent=None):
        """Initialize reply tracking under the service-owned network manager."""
        super().__init__(parent)

        self._pendingRequests = {}

    def request(self, url: str, context):
        """Start one bounded request associated with *context*."""
        request = QNetworkRequest(QtCore.QUrl(url))
        request.setTransferTimeout(self.TimeoutMilliseconds)
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        request.setRawHeader(b'Accept', b'text/plain, application/json')
        request.setRawHeader(b'User-Agent', b'Furious endpoint information')

        reply = self.get(request)

        self._pendingRequests[reply] = context

        reply.finished.connect(self._replyFinished)

    @QtCore.Slot()
    def _replyFinished(self):
        """Consume, publish, and release one completed reply."""
        reply = self.sender()

        if not isinstance(reply, QNetworkReply):
            return

        context = self._pendingRequests.pop(reply, None)

        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data, error = bytes(reply.readAll()), ''
            else:
                data, error = None, reply.errorString()

            self.completed.emit(context, data, error)
        finally:
            reply.deleteLater()

    def cancelAll(self):
        """Abort all connection-specific requests without retaining replies."""
        pendingReplies = tuple(self._pendingRequests)

        self._pendingRequests.clear()

        for reply in pendingReplies:
            try:
                reply.finished.disconnect(self._replyFinished)
            except (RuntimeError, TypeError):
                pass

            reply.abort()
            reply.deleteLater()


@dataclass(frozen=True)
class _IPProvider:
    name: str
    url: str
    parser: Callable[[bytes, int], tuple[str, str]]


def _validatedAddress(value, version: int) -> str:
    """Return a canonical address of *version* or raise ``ValueError``."""
    address = ip_address(str(value).strip())

    if address.version != version:
        raise ValueError(f'expected IPv{version}, got IPv{address.version}')

    return str(address)


def _parseCloudflareTrace(data: bytes, version: int) -> tuple[str, str]:
    """Parse Cloudflare's documented key/value trace response."""
    values = {}

    for line in data.decode('utf-8', 'replace').splitlines():
        key, separator, value = line.partition('=')

        if separator:
            values[key.strip()] = value.strip()

    return (
        _validatedAddress(values.get('ip', ''), version),
        str(values.get('loc', '')).upper(),
    )


def _parsePlainAddress(data: bytes, version: int) -> tuple[str, str]:
    """Parse a provider response containing only one public address."""
    return _validatedAddress(data.decode('ascii', 'strict').strip(), version), ''


IPV4_PROVIDERS = (
    _IPProvider(
        'Cloudflare',
        'https://1.1.1.1/cdn-cgi/trace',
        _parseCloudflareTrace,
    ),
    _IPProvider('ipify', 'https://api4.ipify.org', _parsePlainAddress),
)
IPV6_PROVIDERS = (
    _IPProvider(
        'Cloudflare',
        'https://[2606:4700:4700::1111]/cdn-cgi/trace',
        _parseCloudflareTrace,
    ),
    _IPProvider('ipify', 'https://api6.ipify.org', _parsePlainAddress),
)


class EndpointInfoService(QtCore.QObject):
    """Own lazy, per-connection endpoint discovery independently from the page."""

    stateChanged, resultChanged, enabledChanged = (
        QtCore.Signal(object),
        QtCore.Signal(object),
        QtCore.Signal(bool),
    )

    def __init__(
        self,
        parent=None,
        *,
        controller=None,
        httpClient=None,
        proxyResolver=None,
        enabled=None,
    ):
        """Initialize the connection observer and injectable HTTP transport."""
        super().__init__(parent)

        self.controller = controller or AppConnectionController()
        self.httpClient = httpClient or ProxyEndpointHttpClient(self)
        self.proxyResolver = proxyResolver or Storage.Extras.UserHttpProxy
        self._enabled = (
            AppSettings.isStateON_(PROXY_ENDPOINT_INFO_SETTING)
            if enabled is None
            else bool(enabled)
        )
        self.state = EndpointInfoState.Disabled
        self.result = EndpointInfo()
        self._generation = 0
        self._pageVisible = False
        self._cached = False
        self._requestInFlight = False
        self._family = 4
        self._providerIndex = 0
        self._countryHint = ''

        self.httpClient.completed.connect(self._requestCompleted)

        stateChanged = getattr(self.controller, 'stateChanged', None)
        activeProfileChanged = getattr(self.controller, 'activeProfileChanged', None)

        if stateChanged is not None:
            stateChanged.connect(self._connectionStateChanged)

        if activeProfileChanged is not None:
            activeProfileChanged.connect(self._activeProfileChanged)

        self._syncConnectionState()

    @property
    def enabled(self) -> bool:
        """Return whether privacy-sensitive endpoint inspection is allowed."""
        return self._enabled

    @QtCore.Slot(bool)
    def setEnabled(self, enabled: bool):
        """Apply endpoint inspection immediately and invalidate disabled work."""
        enabled = bool(enabled)

        if enabled == self._enabled:
            return

        self._enabled = enabled
        self.enabledChanged.emit(enabled)

        if not enabled:
            self._invalidate()
            self._setState(EndpointInfoState.Disabled)

            return

        self._syncConnectionState()

    def _setState(self, state: EndpointInfoState):
        """Publish state only when it changes."""
        if state is self.state:
            return

        self.state = state
        self.stateChanged.emit(state)

    def _publishResult(self, result: EndpointInfo):
        """Publish immutable endpoint data."""
        self.result = result
        self.resultChanged.emit(result)

    def _invalidate(self):
        """Invalidate the old connection's cache and pending work."""
        self._generation += 1
        self._cached = False
        self._requestInFlight = False
        self._countryHint = ''
        self.httpClient.cancelAll()
        self._publishResult(EndpointInfo())

    def _syncConnectionState(self):
        """Reflect the controller and begin lazy work only while visible."""
        if not self._enabled:
            self._setState(EndpointInfoState.Disabled)

            return

        if self.controller.isConnected():
            self._setState(EndpointInfoState.Loading)

            if self._pageVisible:
                self.requestIfNeeded()
        elif (
            getattr(getattr(self.controller, 'state', None), 'name', '') == 'Connecting'
        ):
            self._setState(EndpointInfoState.Connecting)
        else:
            self._setState(EndpointInfoState.Disconnected)

    @QtCore.Slot(object)
    def _connectionStateChanged(self, _state):
        """Invalidate results whenever the runtime connection changes state."""
        self._invalidate()
        self._syncConnectionState()

    @QtCore.Slot(object)
    def _activeProfileChanged(self, _profile):
        """Reject late data when the active profile identity changes."""
        self._invalidate()
        self._syncConnectionState()

    def setPageVisible(self, visible: bool):
        """Enable network work only while the owning page can present it."""
        self._pageVisible = bool(visible)

        if self._pageVisible:
            self.requestIfNeeded()

    @QtCore.Slot()
    def refresh(self):
        """Explicitly replace the current connection's cached observation."""
        if not self._enabled or not self.controller.isConnected():
            return

        self._generation += 1
        self._cached = False
        self._requestInFlight = False
        self._countryHint = ''
        self.httpClient.cancelAll()
        self._publishResult(EndpointInfo())
        self._setState(EndpointInfoState.Loading)
        self._startLookup()

    def requestIfNeeded(self):
        """Start a lookup only for an uncached visible connection session."""
        if (
            not self._pageVisible
            or not self._enabled
            or not self.controller.isConnected()
            or self._cached
            or self._requestInFlight
        ):
            return

        self._startLookup()

    def _startLookup(self):
        """Configure the active local HTTP proxy before issuing any request."""
        proxy = self.proxyResolver()

        if not proxy or not self.httpClient.configureHttpProxy(proxy):
            logger.error('endpoint lookup refused because no active HTTP proxy exists')
            self._setState(EndpointInfoState.Failed)

            return

        self._requestInFlight = True
        self._family = 4
        self._providerIndex = 0
        self._countryHint = ''
        self._setState(EndpointInfoState.Loading)
        self._requestIPProvider()

    def _providers(self):
        """Return the provider chain for the current address family."""
        return IPV4_PROVIDERS if self._family == 4 else IPV6_PROVIDERS

    def _requestIPProvider(self):
        """Request the current provider in the sequential fallback chain."""
        providers = self._providers()

        if self._providerIndex >= len(providers):
            self._finishFamily()

            return

        provider = providers[self._providerIndex]

        self.httpClient.request(
            provider.url,
            {
                'generation': self._generation,
                'kind': 'ip',
                'family': self._family,
                'providerIndex': self._providerIndex,
            },
        )

    @QtCore.Slot(object, object, str)
    def _requestCompleted(self, context, data, error):
        """Apply only the response that belongs to the current connection."""
        if (
            not self._enabled
            or not isinstance(context, dict)
            or context.get('generation') != self._generation
        ):
            return

        if context.get('kind') == 'location':
            self._locationCompleted(data, error)
        else:
            self._ipCompleted(context, data, error)

    def _ipCompleted(self, context, data, error):
        """Validate one IP provider response or advance to its fallback."""
        family = int(context.get('family', 0))
        providerIndex = int(context.get('providerIndex', 0))
        providers = IPV4_PROVIDERS if family == 4 else IPV6_PROVIDERS

        if family != self._family or providerIndex != self._providerIndex:
            return

        provider = providers[providerIndex]

        try:
            if error or not isinstance(data, bytes):
                raise ValueError(error or 'empty response')

            address, countryCode = provider.parser(data, family)
        except Exception as ex:
            # Any non-exit exceptions

            logger.debug(f'{provider.name} IPv{family} endpoint lookup failed: {ex}')

            self._providerIndex += 1
            self._requestIPProvider()

            return

        if countryCode and not self._countryHint:
            self._countryHint = countryCode

        if family == 4:
            self._publishResult(replace(self.result, ipv4=address, ipv4Resolved=True))
        else:
            self._publishResult(replace(self.result, ipv6=address, ipv6Resolved=True))

        self._finishFamily()

    def _finishFamily(self):
        """Advance from IPv4 to IPv6, then enrich the observed result."""
        if self._family == 4:
            if not self.result.ipv4Resolved:
                self._publishResult(replace(self.result, ipv4Resolved=True))

            self._family = 6
            self._providerIndex = 0
            self._requestIPProvider()

            return

        if not self.result.ipv6Resolved:
            self._publishResult(replace(self.result, ipv6Resolved=True))

        address = self.result.primaryAddress

        if not address:
            self._finishLookup(EndpointInfoState.Failed)

            return

        encodedAddress = quote(address, safe='')

        self.httpClient.request(
            f'https://ipapi.co/{encodedAddress}/json/',
            {
                'generation': self._generation,
                'kind': 'location',
                'address': address,
            },
        )

    def _locationCompleted(self, data, error):
        """Validate approximate geolocation without discarding valid IP data."""
        location = EndpointLocation(countryCode=self._countryHint)

        try:
            if error or not isinstance(data, bytes):
                raise ValueError(error or 'empty response')

            payload = json.loads(data.decode('utf-8'))

            if payload.get('error'):
                raise ValueError(payload.get('reason') or 'provider error')

            observedAddress = _validatedAddress(
                payload.get('ip', ''), ip_address(self.result.primaryAddress).version
            )

            if observedAddress != self.result.primaryAddress:
                raise ValueError('geolocation response address does not match request')

            latitude, longitude = (
                float(payload['latitude']),
                float(payload['longitude']),
            )

            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError('geolocation coordinates out of range')

            countryCode = (
                str(payload.get('country_code') or payload.get('country') or '')
                .strip()
                .upper()
            )

            location = EndpointLocation(
                countryCode=countryCode or self._countryHint,
                countryName=str(payload.get('country_name') or '').strip(),
                region=str(payload.get('region') or '').strip(),
                city=str(payload.get('city') or '').strip(),
                latitude=latitude,
                longitude=longitude,
                organization=str(payload.get('org') or '').strip(),
            )
        except Exception as ex:
            logger.warning(f'approximate endpoint geolocation failed: {ex}')

        self._publishResult(
            replace(self.result, location=location, locationResolved=True)
        )
        self._finishLookup(EndpointInfoState.Ready)

    def _finishLookup(self, state: EndpointInfoState):
        """Cache the completed connection result and publish final state."""
        if not self.result.locationResolved:
            self._publishResult(replace(self.result, locationResolved=True))

        self._requestInFlight = False
        self._cached = True
        self._setState(state)
