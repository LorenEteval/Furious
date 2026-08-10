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

"""Provide the server-management home page."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import *
from Furious.Repository import *
from Furious.Plugins import CapabilityKind, getPluginRegistry
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import (
    ConnectivityManager,
    TrafficStatsManager,
    UpdateManager,
    formatTrafficSpeed,
    formatTrafficUsage,
)
from Furious.Actions.Import import (
    ImportFromFileAction,
    ImportJSONFromClipboardAction,
    ImportQRCodeOnTheScreenAction,
    ImportURIFromClipboardAction,
)
from Furious.Widget.ServerTableView import *
from Furious.Window.NetworkTestDialog import *
from Furious.Window.ProxyBypassDialog import *
from Furious.Window.QRCodeWindow import QRCodeWindow
from Furious.Window.SubscriptionWindow import *
from Furious.Window.TextEditorWindow import TextEditorWindow
from Furious.Window.TunSettingsDialog import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union

import os
import logging
import functools

__all__ = ['HomePage']

logger = logging.getLogger(__name__)


def _isCoreActive(coreType) -> bool:
    """Return whether the tray's active connection owns *coreType*."""
    try:
        connectAction = APP().systemTray.ConnectAction

        return connectAction.isConnected() and any(
            isinstance(process, coreType)
            for process in connectAction.coreManager.processesPool
        )
    except (AttributeError, RuntimeError):
        # The home page is built before the system tray is attached.
        return False


class AppConnectivityManager(ConnectivityManager):
    """Coordinate app network connectivity operations."""

    def __init__(self, parent=None):
        """Initialize the application connectivity manager."""
        super().__init__(parent)

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        parent = self.parent()

        if isinstance(parent, HomePage):
            parent.setNetworkState(True)

        super().successCallback(networkReply, **kwargs)

    def failureCallback(self, networkReply, **kwargs):
        """Handle a failed network operation."""
        parent = self.parent()

        if isinstance(parent, HomePage):
            parent.setNetworkState(False, errorString=networkReply.errorString())

        super().failureCallback(networkReply, **kwargs)

    def startSingleTest(self):
        """Start single test."""
        if not APP().isSystemTrayConnected():
            parent = self.parent()

            if isinstance(parent, HomePage):
                parent.resetNetworkState()

            self.stopTest()

        connectedHttpProxy = Storage.Extras.UserHttpProxy()

        if connectedHttpProxy is None:
            parent = self.parent()

            if isinstance(parent, HomePage):
                parent.resetNetworkState()
        else:
            self.configureHttpProxy(connectedHttpProxy)

            super().startSingleTest()

    def disconnectedCallback(self):
        """Update the app network connectivity manager for a disconnected state."""
        parent = self.parent()

        if isinstance(parent, HomePage):
            parent.resetNetworkState()

        super().disconnectedCallback()


class NetworkStateBadge(Mixins.QTranslatable, Mixins.ThemeAware, QWidget):
    """Provide the network state badge widget."""

    DefaultIconFileName = 'reception-4.svg'
    StateIconFileName = {
        'success': 'reception-4.svg',
        'failure': 'reception-0.svg',
    }
    IconSize = QtCore.QSize(16, 16)

    def __init__(self, parent=None):
        """Initialize the NetworkStateBadge."""
        super().__init__(parent)

        self.currentIconFileName = self.DefaultIconFileName
        self.currentState = ''
        self.currentRemark = ''
        self.currentErrorString = ''

        self.setObjectName('NetworkStateBadge')
        self.setProperty('networkState', '')
        self.setVisible(False)

        self.iconLabel = QLabel(parent=self)
        self.textLabel = AppQLabel(translatable=False, parent=self)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 3, 10, 3)
        self._layout.setSpacing(7)
        self._layout.addWidget(self.iconLabel)
        self._layout.addWidget(self.textLabel)

        self.setIconByTheme(APP().theme())

    def setIconByTheme(self, theme: str, iconFileName: Union[str, None] = None):
        """Set icon by theme."""
        iconFileName = iconFileName or self.currentIconFileName

        if theme == AppStyleSheet.Dark:
            icon = bootstrapIconWhite(iconFileName)
        else:
            icon = bootstrapIcon(iconFileName)

        self.iconLabel.setPixmap(icon.pixmap(self.IconSize))

    def statusText(self):
        """Return the status text value used by the network state badge."""
        if self.currentState == 'success':
            return f'{_("Network OK")} - {self.currentRemark}'

        if self.currentState == 'failure':
            return f'{_("Network error")} - {self.currentRemark}'

        return ''

    def statusToolTip(self):
        """Return the status tool tip value used by the network state badge."""
        if self.currentState == 'success':
            return self.currentRemark

        if self.currentState == 'failure':
            return f'{self.currentRemark}\n{self.currentErrorString}'.strip()

        return ''

    def updateStatusText(self):
        """Update status text."""
        text = self.statusText()
        tooltip = self.statusToolTip()

        self.textLabel.setText(text)
        self.setToolTip(tooltip)
        self.iconLabel.setToolTip(tooltip)
        self.textLabel.setToolTip(tooltip)

    def setStatus(self, state: str, remark: str, errorString: str = ''):
        """Set status."""
        self.currentState = state
        self.currentRemark = remark
        self.currentErrorString = errorString

        self.updateStatusText()
        self.setProperty('networkState', state)
        self.currentIconFileName = self.StateIconFileName.get(
            state, self.DefaultIconFileName
        )
        self.setIconByTheme(APP().theme())
        self.refreshStyle()

    def clearStatus(self):
        """Clear status."""
        self.currentState = ''
        self.currentRemark = ''
        self.currentErrorString = ''

        self.updateStatusText()
        self.setProperty('networkState', '')
        self.currentIconFileName = self.DefaultIconFileName
        self.setIconByTheme(APP().theme())
        self.setVisible(False)
        self.refreshStyle()

    def refreshStyle(self):
        """Refresh style."""
        for widget in [self, self.iconLabel, self.textLabel]:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        self.setVisible(bool(self.textLabel.text()))

    def themeChangedCallback(self, theme: str):
        """Update the network state badge for a theme change."""
        self.setIconByTheme(theme)

    def retranslate(self):
        """Refresh translated text for the network state badge."""
        self.updateStatusText()


class TrafficStatsBadge(Mixins.QTranslatable, Mixins.ThemeAware, QWidget):
    """Display independently updated traffic speeds and usage."""

    UploadIconFileName = 'cloud-upload.svg'
    DownloadIconFileName = 'cloud-download.svg'
    IconSize = QtCore.QSize(16, 16)

    def __init__(self, parent=None):
        """Initialize dedicated traffic-direction icons and labels."""
        super().__init__(parent)

        self.setObjectName('TrafficStatsBadge')
        self.setVisible(False)

        self.downloadIconLabel = QLabel(parent=self)
        self.downloadTextLabel = AppQLabel(translatable=False, parent=self)
        self.downloadUsageLabel = AppQLabel(translatable=False, parent=self)
        self.uploadIconLabel = QLabel(parent=self)
        self.uploadTextLabel = AppQLabel(translatable=False, parent=self)
        self.uploadUsageLabel = AppQLabel(translatable=False, parent=self)

        self.uploadUsageLabel.setObjectName('TrafficUsageLabel')
        self.downloadUsageLabel.setObjectName('TrafficUsageLabel')

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 3, 8, 3)
        self._layout.setSpacing(6)
        self._layout.addWidget(self.downloadIconLabel)
        self._layout.addWidget(self.downloadTextLabel)
        self._layout.addWidget(self.downloadUsageLabel)
        self._layout.addSpacing(4)
        self._layout.addWidget(self.uploadIconLabel)
        self._layout.addWidget(self.uploadTextLabel)
        self._layout.addWidget(self.uploadUsageLabel)

        self.setIconByTheme(APP().theme())
        self.updateToolTips()

    def updateToolTips(self):
        """Apply translated descriptions to each traffic statistic."""
        uploadSpeed, downloadSpeed, uploadUsage, downloadUsage = (
            _('Upload Speed'),
            _('Download Speed'),
            _('Upload Traffic Usage'),
            _('Download Traffic Usage'),
        )

        self.uploadIconLabel.setToolTip(uploadSpeed)
        self.uploadTextLabel.setToolTip(uploadSpeed)
        self.uploadUsageLabel.setToolTip(uploadUsage)
        self.downloadIconLabel.setToolTip(downloadSpeed)
        self.downloadTextLabel.setToolTip(downloadSpeed)
        self.downloadUsageLabel.setToolTip(downloadUsage)

    def setIconByTheme(self, theme: str):
        """Apply theme-appropriate upload and download icons."""
        iconFactory = (
            bootstrapIconWhite if theme == AppStyleSheet.Dark else bootstrapIcon
        )

        self.uploadIconLabel.setPixmap(
            iconFactory(self.UploadIconFileName).pixmap(self.IconSize)
        )
        self.downloadIconLabel.setPixmap(
            iconFactory(self.DownloadIconFileName).pixmap(self.IconSize)
        )

    @QtCore.Slot(float, float)
    def setSpeeds(self, upload: float, download: float):
        """Display formatted upload and download byte rates."""
        self.uploadTextLabel.setText(formatTrafficSpeed(upload))
        self.downloadTextLabel.setText(formatTrafficSpeed(download))
        self.setVisible(True)

    @QtCore.Slot(object, object)
    def setUsage(self, upload: int, download: int):
        """Display formatted cumulative upload and download usage."""
        self.uploadUsageLabel.setText(f'({formatTrafficUsage(upload)})')
        self.downloadUsageLabel.setText(f'({formatTrafficUsage(download)})')
        self.setVisible(True)

    @QtCore.Slot()
    def clearStatistics(self):
        """Hide stale speed and usage values when statistics are unavailable."""
        self.uploadTextLabel.clear()
        self.uploadUsageLabel.clear()
        self.downloadTextLabel.clear()
        self.downloadUsageLabel.clear()
        self.setVisible(False)

    def themeChangedCallback(self, theme: str):
        """Refresh traffic-direction icons after a theme change."""
        self.setIconByTheme(theme)

    def retranslate(self):
        """Refresh translated traffic-statistic tooltips."""
        self.updateToolTips()


class ConnectionStatusWidget(QWidget):
    """Compose network state and traffic speed as one permanent status item."""

    def __init__(self, parent=None):
        """Initialize separate network-state and traffic-speed components."""
        super().__init__(parent)

        self.setObjectName('ConnectionStatusWidget')
        self.networkState = NetworkStateBadge(parent=self)
        self.trafficStats = TrafficStatsBadge(parent=self)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addWidget(self.trafficStats)
        self._layout.addWidget(self.networkState)


class SearchButton(AppQIconTextPushButton):
    """Represent search button."""

    def __init__(self, *args, **kwargs):
        """Initialize the SearchButton."""
        super().__init__(*args, **kwargs)

        self.setObjectName('SearchButton')
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.setText(_('Search'))
        self.setIcon(bootstrapIcon('search.svg'))

    def retranslate(self):
        """Refresh translated text for the search button."""
        self.setText(_('Search'))


class HomePage(Mixins.QTranslatable, QMainWindow):
    """Own server management, its actions, and connection presentation."""

    @staticmethod
    def serverImportActions():
        """Build import actions contributed to the server table context menu."""
        return (
            ImportFromFileAction(),
            ImportURIFromClipboardAction(
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_V,
                ),
            ),
            ImportJSONFromClipboardAction(
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_J,
                ),
            ),
            ImportQRCodeOnTheScreenAction(),
        )

    def __init__(self, *args, **kwargs):
        """Initialize the server-management page."""
        super().__init__(*args, **kwargs)

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self.updatesManager = UpdateManager(parent=self)
        self.networkConnectivityManager = AppConnectivityManager(parent=self)

        self.userServersQTableWidget = ServerTableView(
            parent=self,
            configurationEditorFactory=lambda: TextEditorWindow(parent=self),
            qrCodeWindowFactory=QRCodeWindow,
            importActionsFactory=self.serverImportActions,
        )
        self.userSubsWindow = SubscriptionWindow(
            parent=self,
            deleteUniqueCallback=lambda unique: self.userServersQTableWidget.deleteItemByIndex(
                list(
                    index
                    for index, server in enumerate(Storage.UserServers())
                    if server.itemSubscription == unique
                ),
                showProgress=False,
            ),
        )
        pluginRegistry = getPluginRegistry()
        self.customizeProxyBypassDialog = ProxyBypassDialog(parent=self)
        self.customizeNetworkTestDialog = NetworkTestDialog(parent=self)

        serverActions = []

        for descriptor in pluginRegistry.protocolDescriptors():
            if (
                not descriptor.addActionText
                or pluginRegistry.editorForProtocol(descriptor.id) is None
            ):
                continue

            if descriptor.separatorBefore and serverActions:
                serverActions.append(AppQSeperator())

            actionText = (
                _(descriptor.addActionText)
                if descriptor.translatable
                else descriptor.addActionText
            )
            serverActions.append(
                AppQAction(
                    actionText,
                    callback=functools.partial(
                        self.userServersQTableWidget.addServerViaGui,
                        descriptor.id,
                        actionText,
                    ),
                )
            )

        if serverActions:
            serverActions.append(AppQSeperator())
        serverActions.append(
            AppQAction(
                _('New Empty Configuration'),
                callback=lambda: self.userServersQTableWidget.newEmptyItem(),
            )
        )

        subsActions = [
            AppQAction(
                _('Update Subscription (Use Current Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    Storage.Extras.UserHttpProxy(),
                    parent=self,
                ),
            ),
            AppQAction(
                _('Update Subscription (Force Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    '127.0.0.1:10809',
                    parent=self,
                ),
            ),
            AppQAction(
                _('Update Subscription (No Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    None,
                    parent=self,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Edit Subscription...'),
                icon=bootstrapIcon('star.svg'),
                callback=lambda: self.userSubsWindow.show(),
            ),
        ]

        if SystemRuntime.flatpakID():
            customizeTUNSettingsAction = []
        else:
            customizeTUNSettingsAction = [
                AppQAction(
                    _('Customize Tun2socks Settings...'),
                    icon=bootstrapIcon('diagram-3.svg'),
                    checkable=False,
                    callback=lambda: self.getGuiTUNSettings().open(),
                ),
            ]

        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            _TRANSLATABLE_RESTART_AS_ADMIN = [
                _('Restart The Application As Administrator'),
                _('Restart The Application As Superuser'),
            ]

            restartAsAdminAction = [
                AppQAction(
                    _(f'Restart The Application As {ADMINISTRATOR_NAME}'),
                    icon=bootstrapIcon('arrow-clockwise.svg'),
                    checkable=False,
                    callback=lambda: self.restartAsAdmin(),
                ),
            ]
        else:
            restartAsAdminAction = []

        if PLATFORM == 'Darwin' or SystemRuntime.flatpakID():
            openAppFolderAction = []
        else:
            openAppFolderAction = [
                AppQAction(
                    _('Open Application Folder'),
                    icon=bootstrapIcon('folder2-open.svg'),
                    checkable=False,
                    callback=lambda: self.openApplicationFolder(),
                ),
            ]

        toolsActions = [
            *customizeTUNSettingsAction,
            AppQAction(
                _('Customize System Proxy Bypass Address...'),
                checkable=False,
                callback=lambda: self.customizeProxyBypassDialog.open(),
            ),
            AppQAction(
                _('Customize Network Test URL...'),
                icon=bootstrapIcon('speedometer2.svg'),
                checkable=False,
                callback=lambda: self.customizeNetworkTestDialog.open(),
            ),
        ]
        systemTools = [*restartAsAdminAction, *openAppFolderAction]

        if systemTools:
            toolsActions.extend([AppQSeperator(), *systemTools])

        corePluginActions = []

        for plugin in pluginRegistry.pluginsWithCapability(
            CapabilityKind.KernelFactory
        ):
            pluginMetadata = pluginRegistry.metadataFor(plugin)
            managementActions = pluginRegistry.managementActions(
                plugin,
                parent=self,
                isCoreActive=_isCoreActive,
            )
            if managementActions:
                corePluginActions.append(
                    AppQAction(
                        pluginMetadata.displayName,
                        menu=AppQMenu(*managementActions),
                        useActionGroup=False,
                        checkable=False,
                    )
                )
            else:
                corePluginActions.append(
                    AppQAction(
                        pluginMetadata.displayName,
                        checkable=False,
                    )
                )

        extensionPluginActions = []

        corePlugins = set(
            pluginRegistry.pluginsWithCapability(CapabilityKind.KernelFactory)
        )

        for plugin in pluginRegistry.pluginsWithCapability(
            CapabilityKind.ActionProvider
        ):
            if plugin in corePlugins:
                continue

            managementActions = pluginRegistry.managementActions(
                plugin,
                parent=self,
                isCoreActive=_isCoreActive,
            )

            if managementActions:
                pluginMetadata = pluginRegistry.metadataFor(plugin)
                extensionPluginActions.append(
                    AppQAction(
                        pluginMetadata.displayName,
                        menu=AppQMenu(*managementActions),
                        useActionGroup=False,
                        checkable=False,
                    )
                )

        pluginActions = [
            AppQAction(
                _('Core'),
                menu=AppQMenu(*corePluginActions),
                useActionGroup=False,
                checkable=False,
            ),
        ]

        if extensionPluginActions:
            pluginActions.append(
                AppQAction(
                    _('Extensions'),
                    menu=AppQMenu(*extensionPluginActions),
                    useActionGroup=False,
                    checkable=False,
                )
            )

        pluginsToolbarActions = [
            AppQSeperator(),
            AppQAction(
                _('Plugins'),
                icon=bootstrapIcon('plugin.svg'),
                menu=AppQMenu(*pluginActions),
                useSetMenu=False,
                useActionGroup=False,
                checkable=False,
            ),
        ]

        if hasattr(AppQAction, 'setMenu'):
            self.toolbar = AppQToolBar(
                AppQAction(
                    _('Server'),
                    icon=bootstrapIcon('server.svg'),
                    menu=AppQMenu(*serverActions),
                    useSetMenu=False,
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
                AppQAction(
                    _('Subscription'),
                    icon=bootstrapIcon('collection.svg'),
                    menu=AppQMenu(*subsActions),
                    useSetMenu=False,
                    useActionGroup=False,
                    checkable=False,
                ),
                *pluginsToolbarActions,
                AppQSeperator(),
                AppQAction(
                    _('Tools'),
                    icon=bootstrapIcon('tools.svg'),
                    menu=AppQMenu(*toolsActions),
                    useSetMenu=False,
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
                AppQAction(
                    _('Check For Updates'),
                    icon=bootstrapIcon('download.svg'),
                    checkable=False,
                    callback=lambda: self.checkForUpdates(parent=self),
                ),
                AppQSeperator(),
                AppQAction(
                    _('About'),
                    icon=bootstrapIcon('info-circle.svg'),
                    checkable=False,
                    callback=lambda: self.openAboutPage(),
                ),
            )
            self.toolbar.setObjectName('HomePageToolBar')
            self.toolbar.setMovable(False)
            self.toolbar.setFloatable(False)
            self.toolbar.setIconSize(QtCore.QSize(64, 32))
            self.toolbar.setToolButtonStyle(
                QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            self.addToolBar(self.toolbar)
        else:
            # Menu actions
            serverMenu = {
                'name': 'Server',
                'actions': [*serverActions],
            }

            subsMenu = {
                'name': 'Subscription',
                'actions': [*subsActions],
            }

            pluginsMenu = {
                'name': 'Plugins',
                'actions': [*pluginActions],
            }

            toolsMenu = {
                'name': 'Tools',
                'actions': [*toolsActions],
            }

            helpMenu = {
                'name': 'Help',
                'actions': [
                    AppQAction(
                        _('Check For Updates'),
                        icon=bootstrapIcon('download.svg'),
                        checkable=False,
                        callback=lambda: self.checkForUpdates(parent=self),
                    ),
                    AppQSeperator(),
                    AppQAction(
                        _('About'),
                        icon=bootstrapIcon('info-circle.svg'),
                        checkable=False,
                        callback=lambda: self.openAboutPage(),
                    ),
                ],
            }

            # Corresponds to menus defined above
            _TRANSLATABLE_MENU_NAME = [
                _('Server'),
                _('Subscription'),
                _('Plugins'),
                _('Tools'),
                _('Help'),
            ]

            # Menus
            for menuDict in (
                serverMenu,
                subsMenu,
                pluginsMenu,
                toolsMenu,
                helpMenu,
            ):
                menuName = menuDict['name']
                menuObjName = f'_{menuName}Menu'
                menu = AppQMenu(
                    *menuDict['actions'], title=_(menuName), parent=self.menuBar()
                )

                # Set reference
                setattr(self, menuObjName, menu)

                self.menuBar().addMenu(menu)

        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)

        # TODO: Custom status tip
        # self.setStatusBar(QStatusBar(self))

        self.connectionStatus = ConnectionStatusWidget(parent=self)
        self.networkState = self.connectionStatus.networkState
        self.trafficStats = self.connectionStatus.trafficStats
        self.trafficStatsManager = TrafficStatsManager(parent=self)
        self.trafficStatsManager.speedChanged.connect(self.trafficStats.setSpeeds)
        self.trafficStatsManager.usageChanged.connect(self.trafficStats.setUsage)
        self.trafficStatsManager.statisticsUnavailable.connect(
            self.trafficStats.clearStatistics
        )

        self.statusBar().addPermanentWidget(self.connectionStatus)

        self._widget = QWidget()
        self._layout = QVBoxLayout(self._widget)

        self.searchLayout = QHBoxLayout()

        self.searchLineEdit = AppQLineEdit()
        self.searchLineEdit.setPlaceholderText(
            _(
                'Search servers with text or regex, e.g. trojan, hk|jp, ^vmess, (us|sg).*tls'
            )
        )

        self.searchButton = SearchButton()

        self.searchLayout.addWidget(self.searchLineEdit)
        self.searchLayout.addWidget(self.searchButton)

        self._layout.addLayout(self.searchLayout)
        self._layout.addWidget(self.userServersQTableWidget)

        self.searchButton.clicked.connect(
            lambda: self.userServersQTableWidget.search(self.searchLineEdit.text())
        )
        self.searchLineEdit.returnPressed.connect(
            lambda: self.userServersQTableWidget.search(self.searchLineEdit.text())
        )
        self.searchLineEdit.textChanged.connect(self.handleUserServersSearchTextChanged)

        self.setCentralWidget(self._widget)

    @QtCore.Slot(str)
    def handleUserServersSearchTextChanged(self, text: str):
        """Handle user servers search text changed."""
        if not text:
            self.userServersQTableWidget.clearSearch()

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        """Update subs by unique."""
        self.userServersQTableWidget.updateSubsByUnique(unique, httpProxy, **kwargs)

    def appendNewItemByFactory(self, factory: ConfigFactory | ServerProfile):
        """Append new item by factory."""
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ServerProfile):
        """Refresh row."""
        self.userServersQTableWidget.flushRow(row, item)

    def showTabAndSpaces(self):
        """Show tab and spaces."""
        self.userServersQTableWidget.showTabAndSpaces()

    def hideTabAndSpaces(self):
        """Hide tab and spaces."""
        self.userServersQTableWidget.hideTabAndSpaces()

    def getGuiTUNSettings(self, **kwargs):
        """Return GUI TUN settings."""

        @functools.lru_cache(None)
        def cachedGuiTUNSettings():
            """Return the TUN settings editor owned by the home page."""
            parent = kwargs.pop('parent', self)

            return TunSettingsDialog(parent=parent, **kwargs)

        guiTUNSettings = cachedGuiTUNSettings()
        guiTUNSettings.factoryToInput(Storage.UserTUNSettings())

        return guiTUNSettings

    def checkForUpdates(self, **kwargs):
        """Check for updates."""
        self.updatesManager.configureHttpProxy(Storage.Extras.UserHttpProxy())
        self.updatesManager.checkForUpdates(**kwargs)

    def resetNetworkState(self):
        """Reset network state."""
        self.networkState.clearStatus()

    def setNetworkState(self, success: bool, **kwargs):
        """Set network state."""
        remark = Storage.Extras.UserServerRemark()

        if not remark:
            self.resetNetworkState()

            return

        if success:
            self.networkState.setStatus(
                'success',
                remark,
            )

            return

        errorString = kwargs.pop('errorString', '')

        self.networkState.setStatus(
            'failure',
            remark,
            errorString,
        )

    @staticmethod
    def openApplicationFolder():
        """Open application folder."""
        appFolder = os.path.dirname(APP().applicationFilePath())

        if QDesktopServices.openUrl(QtCore.QUrl(appFolder)):
            logger.info(f'open application folder \'{appFolder}\' success')
        else:
            logger.error(f'open application folder \'{appFolder}\' failed')

    @staticmethod
    def restartAsAdmin():
        """Handle the home-page request to restart with elevated privileges."""
        if not SystemRuntime.isScriptMode():
            if not SystemRuntime.isAdmin():
                process = QtCore.QProcess()

                if PLATFORM == 'Windows':
                    process.startDetached(
                        'powershell',
                        arguments=[
                            '-Command',
                            f'Start-Process \'{APP().applicationFilePath()}\' '
                            f'\'{AppBuiltinCommand.RunAs.value}\' -Verb runAs',
                        ],
                    )
                elif PLATFORM == 'Darwin':
                    process.startDetached(
                        'osascript',
                        arguments=[
                            '-e',
                            f'do shell script \"{APP().applicationFilePath()} '
                            f'{AppBuiltinCommand.RunAs.value}\" with administrator privileges',
                        ],
                    )
            else:
                mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Information)
                mbox.setWindowTitle(_(APPLICATION_NAME))
                mbox.setText(_('I am the supreme authority 👑'))

                # Show the MessageBox asynchronously
                mbox.open()

                logger.info('ignored request to restart as admin as already is')
        else:
            logger.info(f'ignored request to restart as admin in script mode')

    @staticmethod
    def openAboutPage():
        """Open about page."""
        if QDesktopServices.openUrl(QtCore.QUrl(APPLICATION_ABOUT_PAGE)):
            logger.info('open about page success')
        else:
            logger.error('open about page failed')

    def retranslate(self):
        """Refresh text owned directly by the home page."""
        pass
