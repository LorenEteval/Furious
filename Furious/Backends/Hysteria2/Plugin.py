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

"""Integrate Hysteria 2 configuration, editor, and process startup."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Plugins.API import *
from Furious.Backends.Configuration import *

from .Process import Hysteria2
from .ProtocolEditors import HYSTERIA2_PROTOCOL_EDITORS
from .Protocols import HYSTERIA2_PROTOCOL_HANDLERS
from .Stats import (
    HYSTERIA2_STATS_CLIENT_ID_SETTING,
    HYSTERIA2_STATS_SECRET_SETTING,
    HYSTERIA2_STATS_URL_SETTING,
    Hysteria2StatsProvider,
    configuredHysteria2StatsTarget,
)
from .TUN import *

import logging

__all__ = ['Hysteria2Plugin']

logger = logging.getLogger(__name__)


def _placeholder(x):
    return x


_ = _placeholder

# Register host-owned descriptor text with the static translation extractor
# without making the headless plugin module import Qt presentation code.
_TRANSLATABLE_SETTINGS = (
    _('Hysteria2 Traffic Statistics'),
    _('Traffic Stats API URL'),
    _('Hysteria2 server API address; /traffic is appended automatically.'),
    _('Traffic Stats Client ID'),
    _('Authentication ID reported by the Hysteria2 server.'),
    _('Traffic Stats API Secret'),
    _('Authorization value configured by the Hysteria2 server.'),
)


class Hysteria2SettingsProvider(PluginSettingsProvider):
    """Declare Hysteria 2 traffic-API preferences for the host UI."""

    providerId = 'official.hysteria2.settings'

    def createSections(self, parent=None, **kwargs):
        """Return host-rendered Hysteria 2 settings descriptors."""
        del parent, kwargs

        return (
            PluginSettingsSection(
                'traffic-statistics',
                'Hysteria2 Traffic Statistics',
                (
                    PluginSettingDescriptor(
                        'stats-url',
                        'Traffic Stats API URL',
                        'Hysteria2 server API address; /traffic is appended automatically.',
                        'activity.svg',
                        PluginSettingControl.Text,
                        HYSTERIA2_STATS_URL_SETTING,
                        placeholder='http://server:9999',
                        translatable=True,
                    ),
                    PluginSettingDescriptor(
                        'stats-client-id',
                        'Traffic Stats Client ID',
                        'Authentication ID reported by the Hysteria2 server.',
                        'person-badge.svg',
                        PluginSettingControl.Text,
                        HYSTERIA2_STATS_CLIENT_ID_SETTING,
                        translatable=True,
                    ),
                    PluginSettingDescriptor(
                        'stats-secret',
                        'Traffic Stats API Secret',
                        'Authorization value configured by the Hysteria2 server.',
                        'key.svg',
                        PluginSettingControl.Password,
                        HYSTERIA2_STATS_SECRET_SETTING,
                        translatable=True,
                        strip=False,
                    ),
                ),
                translatable=True,
            ),
        )


class Hysteria2ActionProvider(ActionProvider):
    """Provide optional Hysteria 2 management UI independently of its runtime."""

    providerId = 'official.hysteria2.management'
    category = 'core'

    def createActions(self, parent=None, **kwargs):
        """Create Hysteria 2 native TUN management actions."""
        isCoreActive = kwargs.pop('isCoreActive', lambda coreType: False)

        # These modules require a fully initialized Furious.Qt package.
        from Furious.Qt import AppQAction, showMBoxNewChangesNextTime
        from Furious.Qt import gettext as _

        from .TunSettingsDialog import Hysteria2TunSettingsDialog

        useHysteria2TUNAction = AppQAction(
            _('Use Hysteria2 TUN'),
            checkable=True,
            checked=isHysteria2TUNEnabled(),
        )

        def updateUseHysteria2TUN():
            """Persist the native Hysteria 2 TUN action state."""
            setHysteria2TUNEnabled(useHysteria2TUNAction.isChecked())

            if SystemRuntime.isTUNMode() and isCoreActive(Hysteria2):
                showMBoxNewChangesNextTime()

        useHysteria2TUNAction.callback = updateUseHysteria2TUN

        return (
            useHysteria2TUNAction,
            AppQAction(
                _('Customize Hysteria2 TUN Settings...'),
                callback=lambda: Hysteria2TunSettingsDialog(
                    parent=parent,
                    isConnectionActive=lambda: isCoreActive(Hysteria2),
                ).open(),
            ),
        )


class Hysteria2CoreRuntimeFactory(CoreRuntimeFactory):
    """Construct Hysteria 2 core runtimes independently of protocol handling."""

    factoryId = 'official.hysteria2'
    configurationTypes = (ConfigHysteria2,)
    runtimeTypes = (Hysteria2,)

    def prepareTUN(self, config) -> bool:
        """Preserve user TUN or replace it with Furious-managed native TUN."""
        if not isHysteria2TUNEnabled():
            # Presence is authoritative even when the block is malformed: the
            # core must report that error instead of Furious silently changing
            # the connection to application tun2socks.
            return hasHysteria2TUNConfig(config)

        if PLATFORM == 'Linux' and not SystemRuntime.isAdmin():
            # Native Hysteria 2 creates the interface and routing table in its
            # own process, so it cannot use ConnectionManager's privileged helper.
            raise TUNPreparationError(
                'Hysteria 2 native TUN requires Linux superuser privileges'
            )

        settings = getHysteria2TUNSettings()
        serverAddresses = resolveHysteria2ServerAddresses(config)
        route = settings.get('route', {})
        hasManualExclusions = bool(route.get('ipv4Exclude') or route.get('ipv6Exclude'))

        if not serverAddresses and not hasManualExclusions:
            raise TUNPreparationError(
                'Hysteria 2 native TUN cannot start because '
                'the server address could not be resolved and no manual route '
                'exclusion is configured'
            )

        config['tun'] = buildHysteria2TUNConfig(settings, serverAddresses)

        return True

    def usesApplicationTun2socks(self, config) -> bool:
        """Use host tun2socks only when the runtime has no native TUN block."""
        return not hasHysteria2TUNConfig(config)

    def create(self, request: CoreRuntimeRequest):
        """Create a prepared Hysteria 2 core-runtime launch."""
        if request.log:
            logger.info(f'core {Hysteria2.name()} configured')

        runtime = Hysteria2(
            exitCallback=request.exitCallback,
            msgCallback=request.messageCallback,
        )

        setattr(runtime, 'hysteria2StatsTarget', configuredHysteria2StatsTarget())

        return CoreRuntimeLaunch(
            runtime,
            request.configuration,
            options=request.options,
        )

    def prepareDownloadTest(self, config, port: int):
        """Create a Hysteria 2 configuration with one local HTTP proxy."""
        configcopy = config.deepcopy()
        configcopy['http'] = {
            'listen': f'127.0.0.1:{port}',
            'timeout': 300,
            'disable_udp': False,
        }
        configcopy.pop('socks5', '')
        configcopy.pop('tun', None)

        return configcopy

    def coreVersions(self):
        """Return the bundled Hysteria 2 version."""
        return (Hysteria2.version(),)

    def logTimestampPatterns(self):
        """Return the timestamp format emitted by Hysteria 2."""
        return (r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})',)


def _placeholder(x):
    return x


_ = _placeholder

_TRANSLATABLE = [
    _('Official Hysteria 2 protocol, editor, and runtime support.'),
]


class Hysteria2Plugin(FuriousPlugin):
    """Bundle official Hysteria 2 protocol and runtime capabilities."""

    metadata = PluginMetadata(
        'official.hysteria2',
        'Hysteria2',
        description='Official Hysteria 2 protocol, editor, and runtime support.',
        provider='Furious',
    )

    def __init__(self):
        """Create an isolated Hysteria 2 runtime factory."""
        self.capabilities = (
            *HYSTERIA2_PROTOCOL_HANDLERS,
            *HYSTERIA2_PROTOCOL_EDITORS,
            Hysteria2CoreRuntimeFactory(),
            Hysteria2StatsProvider(),
            Hysteria2SettingsProvider(),
            Hysteria2ActionProvider(),
        )
