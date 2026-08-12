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

"""Expose the self-contained foundation API used by higher layers."""

from __future__ import annotations

from . import AppResources
from .AppSettings import AppBinarySettings, AppSettings, registerAppSettings
from .Constants import (
    ADMINISTRATOR_NAME,
    APPLICATION_ABOUT_PAGE,
    APPLICATION_AUTHOR_EMAIL,
    APPLICATION_AUTHOR_NAME,
    APPLICATION_DESCRIPTION,
    APPLICATION_FLATPAK_ID,
    APPLICATION_MACOS_SIGNATURE,
    APPLICATION_NAME,
    APPLICATION_REPO_NAME,
    APPLICATION_REPO_OWNER_NAME,
    APPLICATION_TUN2SOCKS_DEVICE_NAME,
    APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
    APPLICATION_TUN2SOCKS_IP_ADDRESS,
    APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS,
    APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME,
    APPLICATION_VERSION,
    CORE_CHECK_ALIVE_INTERVAL,
    CRASH_LOG_DIR,
    DATA_DIR,
    GEN_TRANSLATION_FILE,
    GOLDEN_RATIO,
    LOCAL_SERVER_NAME,
    NETWORK_CONNECTIVITY_TEST_URL,
    NETWORK_SPEED_TEST_URL,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
    OS_CPU_COUNT,
    PACKAGE_DIR,
    PLATFORM,
    PLATFORM_MACHINE,
    PLATFORM_PYTHON_VERSION,
    PLATFORM_RELEASE,
    PROXY_SERVER_BYPASS,
    PYSIDE6_VERSION,
    ROOT_DIR,
    SYSTEM_LANGUAGE,
    URL_GEOIP,
    URL_GEOIP_SHA256,
    URL_GEOSITE,
    URL_GEOSITE_SHA256,
    XRAY_ASSET_DIR,
    XRAY_ASSET_PATH_GEOIP,
    XRAY_ASSET_PATH_GEOSITE,
)
from .Enum import AppBuiltinCommand, AppBuiltinProxyMode, AppBuiltinRouting
from .Globals import (
    APP,
    AppConnectionController,
    AppFontName,
    AppLogManager,
    AppLogPage,
    AppRoutingController,
    AppSettingsController,
    AppThreadPool,
)
from .Mixins import Mixins
from .PySide6Legacy import PySide6Legacy
from .StartupOnBoot import StartupOnBoot
from .SystemProxy import SystemProxy
from .SystemRoutingTable import SystemRoutingTable
from .SystemRuntime import SystemRuntime
from .Tcping import tcping
from .Utility import (
    absolutePath,
    callOnceOnly,
    callRateLimited,
    classname,
    forceToLocalhostIfPossible,
    isValidIPAddress,
    parseHostPort,
    runExternalCommand,
    versionToValue,
)
from .Win32Session import Win32Session

__all__ = [
    'ADMINISTRATOR_NAME',
    'APP',
    'APPLICATION_ABOUT_PAGE',
    'APPLICATION_AUTHOR_EMAIL',
    'APPLICATION_AUTHOR_NAME',
    'APPLICATION_DESCRIPTION',
    'APPLICATION_FLATPAK_ID',
    'APPLICATION_MACOS_SIGNATURE',
    'APPLICATION_NAME',
    'APPLICATION_REPO_NAME',
    'APPLICATION_REPO_OWNER_NAME',
    'APPLICATION_TUN2SOCKS_DEVICE_NAME',
    'APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS',
    'APPLICATION_TUN2SOCKS_IP_ADDRESS',
    'APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS',
    'APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME',
    'APPLICATION_VERSION',
    'AppBinarySettings',
    'AppBuiltinCommand',
    'AppBuiltinProxyMode',
    'AppBuiltinRouting',
    'AppConnectionController',
    'AppFontName',
    'AppLogManager',
    'AppLogPage',
    'AppResources',
    'AppSettings',
    'AppRoutingController',
    'AppSettingsController',
    'AppThreadPool',
    'CORE_CHECK_ALIVE_INTERVAL',
    'CRASH_LOG_DIR',
    'DATA_DIR',
    'GEN_TRANSLATION_FILE',
    'GOLDEN_RATIO',
    'LOCAL_SERVER_NAME',
    'Mixins',
    'NETWORK_CONNECTIVITY_TEST_URL',
    'NETWORK_SPEED_TEST_URL',
    'ORGANIZATION_DOMAIN',
    'ORGANIZATION_NAME',
    'OS_CPU_COUNT',
    'PACKAGE_DIR',
    'PLATFORM',
    'PLATFORM_MACHINE',
    'PLATFORM_PYTHON_VERSION',
    'PLATFORM_RELEASE',
    'PROXY_SERVER_BYPASS',
    'PYSIDE6_VERSION',
    'PySide6Legacy',
    'ROOT_DIR',
    'SYSTEM_LANGUAGE',
    'StartupOnBoot',
    'SystemProxy',
    'SystemRoutingTable',
    'SystemRuntime',
    'URL_GEOIP',
    'URL_GEOIP_SHA256',
    'URL_GEOSITE',
    'URL_GEOSITE_SHA256',
    'Win32Session',
    'XRAY_ASSET_DIR',
    'XRAY_ASSET_PATH_GEOIP',
    'XRAY_ASSET_PATH_GEOSITE',
    'absolutePath',
    'callOnceOnly',
    'callRateLimited',
    'classname',
    'forceToLocalhostIfPossible',
    'isValidIPAddress',
    'parseHostPort',
    'registerAppSettings',
    'runExternalCommand',
    'tcping',
    'versionToValue',
]
