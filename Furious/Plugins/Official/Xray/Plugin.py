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

from Furious.Core.CoreProcessWorker import ProcessOutputRedirector
from Furious.Frozenlib import *
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Library.Storage import Storage
from Furious.Plugins.API import FuriousPlugin, PluginProtocol, PluginRouting
from Furious.Plugins.Official.Configuration import (
    BLANK_CONFIG_XRAY,
    ConfigXray,
    configXrayEmptyProxyOutboundObject,
)

import copy
import logging
import os
import uuid

from .Core import XrayCore
from .Routing import customRoutingObjectFromSettings
from .TUN import (
    buildXrayTUNInbound,
    hasXrayTUNInbound,
    isXrayTUNEnabled,
    setXrayTUNEnabled,
)

__all__ = ['XrayPlugin', 'isXrayConnectionActive']

logger = logging.getLogger(__name__)


def _protocolId(protocol) -> str:
    """Return a normalized protocol identifier."""
    return str(getattr(protocol, 'value', protocol)).strip().casefold()


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


_TRANSLATABLE_ACTION_TEXT = [
    _('Add VMess Server...'),
    _('Add VLESS Server...'),
    _('Add Shadowsocks Server...'),
    _('Add Trojan Server...'),
    _('Add SOCKS Server...'),
]


def isXrayConnectionActive() -> bool:
    """Return whether the connected core process belongs to Xray-core."""
    try:
        connectAction = APP().systemTray.ConnectAction
        if not connectAction.isConnected():
            return False

        return any(
            isinstance(process, XrayCore)
            for process in connectAction.coreManager.processesPool
        )
    except Exception:
        # Plugin actions can be created before the tray is fully initialized.
        return False


class XrayPlugin(FuriousPlugin):
    """Provide official Xray-core support."""

    pluginId = 'official.xray'
    displayName = 'Xray-core'
    protocols = (
        PluginProtocol('VMess', 'VMess', 'Add VMess Server...', 10),
        PluginProtocol('VLESS', 'VLESS', 'Add VLESS Server...', 20),
        PluginProtocol('Shadowsocks', 'Shadowsocks', 'Add Shadowsocks Server...', 30),
        PluginProtocol('Trojan', 'Trojan', 'Add Trojan Server...', 40),
        PluginProtocol('SOCKS', 'SOCKS', 'Add SOCKS Server...', 70, True),
    )
    configurationTypes = (ConfigXray,)
    coreTypes = (XrayCore,)

    def configFromString(self, config: str, **kwargs):
        """Parse an Xray share URI when its scheme is supported."""
        if config.startswith(
            (
                'vmess://',
                'vless://',
                'ss://',
                'trojan://',
                'socks://',
                'socks5://',
                'socks5h://',
            )
        ):
            return ConfigXray(config, **kwargs)

        return None

    def configFromDict(self, config: dict, **kwargs):
        """Recognize Xray configuration mappings by their inbound/outbound fields."""
        if config.get('inbounds') is not None or config.get('outbounds') is not None:
            return ConfigXray(config, **kwargs)

        return None

    def blankConfig(self, protocol, **kwargs):
        """Construct a blank Xray configuration for one supported protocol."""
        protocolId = _protocolId(protocol)
        factory = ConfigXray(copy.deepcopy(BLANK_CONFIG_XRAY), **kwargs)
        outbound = factory['outbounds'][0]

        if protocolId in ('vmess', 'vless'):
            outbound['protocol'] = protocolId
            outbound['settings']['vnext'] = [
                {
                    'address': '',
                    'port': 0,
                    'users': [{'email': PROXY_OUTBOUND_USER_EMAIL}],
                },
            ]
        elif protocolId == 'socks':
            outbound['protocol'] = protocolId
            outbound['settings'] = {'address': '', 'port': 0}
        elif protocolId in ('shadowsocks', 'trojan'):
            outbound['protocol'] = protocolId
            outbound['settings']['servers'] = [
                {
                    'address': '',
                    'port': 0,
                    'email': PROXY_OUTBOUND_USER_EMAIL,
                },
            ]
        else:
            return None

        return factory

    def createEditorForProtocol(self, protocol, parent=None, **kwargs):
        """Create the Xray editor matching a protocol identifier."""
        # Plugin discovery can occur while the Furious.Qt package is initializing.
        from .GuiShadowsocks import GuiShadowsocks
        from .GuiSocks import GuiSocks
        from .GuiTrojan import GuiTrojan
        from .GuiVLESS import GuiVLESS
        from .GuiVMess import GuiVMess

        editors = {
            'vmess': GuiVMess,
            'vless': GuiVLESS,
            'shadowsocks': GuiShadowsocks,
            'socks': GuiSocks,
            'trojan': GuiTrojan,
        }
        editorType = editors.get(_protocolId(protocol))

        return editorType(parent=parent, **kwargs) if editorType is not None else None

    def createEditorForConfig(self, config, parent=None, **kwargs):
        """Create the editor matching an Xray outbound protocol."""
        return self.createEditorForProtocol(config.proxyProtocol, parent, **kwargs)

    def createManagementActions(self, parent=None, **kwargs):
        """Create Xray routing, TUN, and asset-management actions."""
        # These modules require a fully initialized Furious.Qt package.
        from Furious.Qt import (
            AppQAction,
            AppQSeperator,
            bootstrapIcon,
            showMBoxNewChangesNextTime,
        )
        from Furious.Qt import gettext as _

        from .GuiTUNSettings import GuiXrayTUNSettings
        from .UserRoutingWindow import UserRoutingWindow
        from .XrayAssetViewerWindow import XrayAssetViewerWindow

        routingEditor = UserRoutingWindow(parent=parent, **kwargs)
        assetViewer = XrayAssetViewerWindow(parent=parent)

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

            if SystemRuntime.isTUNMode() and isXrayConnectionActive():
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
                callback=lambda: GuiXrayTUNSettings(parent=parent).open(),
            ),
            AppQSeperator(),
            AppQAction(
                _('Manage Xray-core Asset File...'),
                callback=assetViewer.show,
            ),
        )

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
            PluginRouting(
                AppBuiltinRouting.BypassMainlandChina.value,
                AppBuiltinRouting.BypassMainlandChina.value,
                translatable=True,
            ),
            PluginRouting(
                AppBuiltinRouting.Global.value,
                AppBuiltinRouting.Global.value,
                translatable=True,
            ),
            PluginRouting(
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
            PluginRouting(
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
        """Configure routing and start Xray-core."""
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

                return None, False

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
        process = XrayCore(exitCallback=exitCallback, msgCallback=msgCallback)

        return process, process.start(config, **kwargs)

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
        from .XrayAssetDownloadManager import XrayAssetDownloadManager

        try:
            assetDownloadManager = self._assetDownloadManager
        except AttributeError:
            self._assetDownloadManager = assetDownloadManager = (
                XrayAssetDownloadManager()
            )

        assetDownloadManager.configureHttpProxy(httpProxy)
        assetDownloadManager.download()
