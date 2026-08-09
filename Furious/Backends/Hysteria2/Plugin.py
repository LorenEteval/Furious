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
from .Protocols import HYSTERIA2_PROTOCOL_HANDLERS
from .TUN import *

import logging

__all__ = ['Hysteria2Plugin']

logger = logging.getLogger(__name__)


class Hysteria2Backend(CoreBackend):
    """Run Hysteria 2 independently of profile parsing and editor creation."""

    backendId = 'official.hysteria2'
    configurationTypes = (ConfigHysteria2,)
    coreTypes = (Hysteria2,)

    def createManagementActions(self, parent=None, **kwargs):
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

    def prepareTUN(self, config) -> bool:
        """Add Hysteria 2 native TUN mode when enabled and safe to route."""
        if not isHysteria2TUNEnabled():
            # Work on ConnectionManager's copy so a stored native TUN block
            # cannot run alongside the external tun2socks implementation.
            config.pop('tun', None)

            return False

        if PLATFORM == 'Linux' and not SystemRuntime.isAdmin():
            # Native Hysteria 2 creates the interface and routing table in its
            # own process, so it cannot use ConnectionManager's privileged helper.
            # Keep the existing external tun2socks path available instead.
            config.pop('tun', None)

            logger.warning(
                'Hysteria 2 native TUN requires superuser privileges on '
                'Linux; falling back to external tun2socks'
            )

            return False

        settings = getHysteria2TUNSettings()
        serverAddresses = resolveHysteria2ServerAddresses(config)
        route = settings.get('route', {})
        hasManualExclusions = bool(route.get('ipv4Exclude') or route.get('ipv6Exclude'))

        if not serverAddresses and not hasManualExclusions:
            config.pop('tun', None)

            logger.error(
                'Hysteria 2 native TUN disabled for this connection because '
                'the server address could not be resolved and no manual route '
                'exclusion is configured'
            )

            return False

        config['tun'] = buildHysteria2TUNConfig(settings, serverAddresses)

        return True

    def startCore(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        """Start the Hysteria 2 core."""
        if log:
            logger.info(f'core {Hysteria2.name()} configured')

        process = Hysteria2(exitCallback=exitCallback, msgCallback=msgCallback)

        return process, process.start(config, **kwargs)

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


class Hysteria2Plugin(FuriousPlugin):
    """Bundle official Hysteria 2 protocol and runtime capabilities."""

    pluginId = 'official.hysteria2'
    displayName = 'Hysteria2'
    protocolHandlers = HYSTERIA2_PROTOCOL_HANDLERS

    def __init__(self):
        """Create an isolated Hysteria 2 backend instance for this plugin."""
        self.coreBackends = (Hysteria2Backend(),)
