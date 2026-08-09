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

"""Integrate Xray configuration, editors, routing, and process startup."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Core import *
from Furious.Repository import *
from Furious.Plugins.API import *
from Furious.Backends.Configuration import *

from .Process import *
from .ProtocolEditors import XRAY_PROTOCOL_EDITORS
from .Protocols import XRAY_PROTOCOL_HANDLERS
from .Routing import *
from .TUN import *

import os
import uuid
import logging

__all__ = ['XrayPlugin']

logger = logging.getLogger(__name__)


def fixLogObjectPath(config, attr: str, value: str, log=True):
    """Resolve and normalize one log-file path in an Xray configuration."""
    try:
        path = config['log'][attr]
    except Exception:
        config['log'][attr] = path = ''

    if not isinstance(path, (str, bytes)):
        config['log'][attr] = path = ''

    if path == '':
        if SystemRuntime.isPythonw() and ProcessOutputRedirector.TemporaryDir.isValid():
            config['log'][attr] = ProcessOutputRedirector.TemporaryDir.filePath(value)
    else:
        config['log'][attr] = absolutePath(path)

    result = config['log'][attr]
    if result:
        try:
            with open(result, 'x', encoding='utf-8'):
                pass
        except FileExistsError:
            pass
        except Exception:
            pass

    if log:
        logger.info(
            f'{XrayCore.name()}: {attr} log is specified as \'{path}\'. '
            f'Fixed to \'{result}\''
        )


class XrayActionProvider(ActionProvider):
    """Provide optional Xray management UI independently of its runtime."""

    providerId = 'official.xray.management'
    category = 'core'

    def createActions(self, parent=None, **kwargs):
        """Create Xray routing, TUN, and asset-management actions."""
        isCoreActive = kwargs.pop('isCoreActive', lambda coreType: False)

        # These modules require a fully initialized Furious.Qt package.
        from Furious.Qt import (
            AppQAction,
            AppQSeperator,
            bootstrapIcon,
            showMBoxNewChangesNextTime,
        )
        from Furious.Qt import gettext as _

        from .AssetWindow import XrayAssetWindow
        from .RoutingWindow import XrayRoutingWindow
        from .TunSettingsDialog import XrayTunSettingsDialog

        routingEditor = XrayRoutingWindow(parent=parent, **kwargs)
        assetViewer = XrayAssetWindow(parent=parent)

        def showRoutingDialog():
            """Restore and foreground the persistent routing editor window."""
            if routingEditor.isMinimized():
                routingEditor.showNormal()
            else:
                routingEditor.show()

            routingEditor.raise_()
            routingEditor.activateWindow()

        useXrayTUNAction = AppQAction(
            _('Use Xray-core TUN'),
            checkable=True,
            checked=isXrayTUNEnabled(),
        )

        def updateUseXrayTUN():
            """Persist the native Xray TUN action state."""
            setXrayTUNEnabled(useXrayTUNAction.isChecked())

            if SystemRuntime.isTUNMode() and isCoreActive(XrayCore):
                showMBoxNewChangesNextTime()

        useXrayTUNAction.callback = updateUseXrayTUN

        return (
            AppQAction(
                _('Edit Routing...'),
                icon=bootstrapIcon('signpost.svg'),
                callback=showRoutingDialog,
            ),
            AppQSeperator(),
            useXrayTUNAction,
            AppQAction(
                _('Customize Xray-core TUN Settings...'),
                callback=lambda: XrayTunSettingsDialog(
                    parent=parent,
                    isConnectionActive=lambda: isCoreActive(XrayCore),
                ).open(),
            ),
            AppQSeperator(),
            AppQAction(
                _('Manage Xray-core Asset File...'),
                callback=assetViewer.show,
            ),
        )


class XrayKernelFactory(KernelFactory):
    """Construct Xray kernels independently of protocols and editors."""

    factoryId = 'official.xray'
    configurationTypes = (ConfigXray,)
    kernelTypes = (XrayCore,)

    def fromMapping(self, configuration, **kwargs):
        """Recognize a complete Xray configuration without a proxy profile."""
        if (
            configuration.get('inbounds') is not None
            or configuration.get('outbounds') is not None
        ):
            return ConfigXray(configuration)

        return None

    def prepareTUN(self, config) -> bool:
        """Add the configured Xray native TUN inbound when enabled."""
        if not isXrayTUNEnabled():
            return False

        inbounds = config.get('inbounds')

        if not isinstance(inbounds, list):
            inbounds = []

        config['inbounds'] = [
            inbound
            for inbound in inbounds
            if not (
                isinstance(inbound, dict)
                and str(inbound.get('protocol', '')).casefold() == 'tun'
            )
        ]
        config['inbounds'].append(buildXrayTUNInbound())

        return True

    def routingOptions(self, config=None):
        """Return built-in and named routing modes supported by Xray."""
        options = [
            RoutingOption(
                AppBuiltinRouting.BypassMainlandChina.value,
                AppBuiltinRouting.BypassMainlandChina.value,
                translatable=True,
            ),
            RoutingOption(
                AppBuiltinRouting.Global.value,
                AppBuiltinRouting.Global.value,
                translatable=True,
            ),
            RoutingOption(
                AppBuiltinRouting.Custom.value,
                AppBuiltinRouting.Custom.value,
                translatable=True,
            ),
        ]
        enabledProfiles = tuple(
            (unique, routing)
            for unique, routing in Storage.UserRoutings().items()
            if routing.get('enabled', True)
        )
        options.extend(
            RoutingOption(
                f'Custom:{unique}',
                routing.get('remark', ''),
                separatorBefore=index == 0,
            )
            for index, (unique, routing) in enumerate(enabledProfiles)
        )

        return tuple(options)

    def configureEnvironment(self):
        """Point Xray-core at Furious's bundled geo-asset directory."""
        os.environ['XRAY_LOCATION_ASSET'] = str(XRAY_ASSET_DIR)

    def create(self, request: KernelRequest):
        """Configure routing and create an Xray-core launch."""
        config, routing, proxyModeOnly, log = (
            request.configuration,
            request.routing,
            request.proxyModeOnly,
            request.log,
        )

        if config.get('log') is None or not isinstance(config['log'], dict):
            config['log'] = {'access': '', 'error': '', 'loglevel': 'warning'}

        logRedirectValue = str(uuid.uuid4())

        for attr in ['access', 'error']:
            fixLogObjectPath(config, attr, logRedirectValue, log)

        if routing == AppBuiltinRouting.BypassMainlandChina.value:
            if (
                not proxyModeOnly
                and SystemRuntime.isTUNMode()
                and not hasXrayTUNInbound(config)
            ):
                # Defer Qt access until the application has finished importing it.
                from Furious.Qt.QtWidgets import showMBoxDirectRulesNotAllowed

                showMBoxDirectRulesNotAllowed()

                return None

            routingObject = {
                'domainStrategy': 'IPIfNonMatch',
                'domainMatcher': 'hybrid',
                'rules': [
                    {
                        'type': 'field',
                        'domain': ['geosite:category-ads-all'],
                        'outboundTag': 'block',
                    },
                    {
                        'type': 'field',
                        'domain': ['geosite:cn'],
                        'outboundTag': 'direct',
                    },
                    {
                        'type': 'field',
                        'ip': ['geoip:private', 'geoip:cn'],
                        'outboundTag': 'direct',
                    },
                    {
                        'type': 'field',
                        'port': '0-65535',
                        'outboundTag': 'proxy',
                    },
                ],
            }
        elif routing == AppBuiltinRouting.Global.value:
            routingObject = {}
        elif customRoutingObjectFromSettings(routing) is not None:
            routingObject = customRoutingObjectFromSettings(routing)
        elif routing == AppBuiltinRouting.Custom.value:
            routingObject = config.get('routing', {})
        else:
            routingObject = {}

        if log:
            logger.info(f'core {XrayCore.name()} configured')
            logger.info(f'routing is {routing}')
            logger.info(f'RoutingObject: {routingObject}')

        config['routing'] = routingObject

        process = XrayCore(
            exitCallback=request.exitCallback,
            msgCallback=request.messageCallback,
        )

        return KernelLaunch(process, config, options=request.options)

    def prepareDownloadTest(self, config, port: int):
        """Create an Xray configuration with one local HTTP test inbound."""
        configcopy = config.deepcopy()
        configcopy['inbounds'] = [
            {
                'tag': 'http',
                'port': port,
                'listen': '127.0.0.1',
                'protocol': 'http',
                'sniffing': {
                    'enabled': True,
                    'destOverride': ['http', 'tls'],
                },
                'settings': {
                    'auth': 'noauth',
                    'udp': True,
                    'allowTransparent': False,
                },
            },
        ]

        try:
            for outboundObject in configcopy['outbounds']:
                if outboundObject['tag'] == 'proxy':
                    outboundObject['tag'] = f'proxy{port}'
        except Exception:
            pass

        return configcopy

    def coreVersions(self):
        """Return the bundled Xray-core version."""
        return (XrayCore.version(),)

    def logTimestampPatterns(self):
        """Return the timestamp format emitted by Xray-core."""
        return (r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}.\d{6}',)

    def afterConnected(self, httpProxy=None):
        """Update Xray geo assets after connecting when enabled."""
        if not SystemRuntime.isAssetsFolderWritable():
            logger.info(
                f'skipped auto assets update due to assets folder '
                f'\'{XRAY_ASSET_DIR}\' not writable'
            )

            return

        logger.info(f'assets folder \'{XRAY_ASSET_DIR}\' is writable. Continue')

        if not AppSettings.isStateON_('AutoUpdateAssetFiles'):
            logger.info('skipped auto assets update due to settings')

            return

        # The download manager is Qt-based and is not needed until this hook runs.
        from .AssetDownloadManager import XrayAssetDownloadManager

        try:
            assetDownloadManager = self._assetDownloadManager
        except AttributeError:
            self._assetDownloadManager = assetDownloadManager = (
                XrayAssetDownloadManager()
            )

        assetDownloadManager.configureHttpProxy(httpProxy)
        assetDownloadManager.download()


class XrayPlugin(FuriousPlugin):
    """Bundle official Xray protocol handlers and its runtime backend."""

    metadata = PluginMetadata(
        'official.xray',
        'Xray-core',
        description='Official Xray protocol, editor, and runtime support.',
        provider='Furious',
    )

    def __init__(self):
        """Create an isolated Xray runtime factory for this plugin."""
        self.capabilities = (
            *XRAY_PROTOCOL_HANDLERS,
            *XRAY_PROTOCOL_EDITORS,
            XrayKernelFactory(),
            XrayActionProvider(),
        )
