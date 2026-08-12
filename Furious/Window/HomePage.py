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
from Furious.Plugins import getPluginRegistry
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
from Furious.Widget.ConnectionButton import ConnectionButton
from Furious.Widget.RoutingSelector import RoutingSelector
from Furious.Widget.ServerTableView import *
from Furious.Window.NetworkTestDialog import *
from Furious.Window.ProxyBypassDialog import *
from Furious.Window.QRCodeWindow import QRCodeWindow
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
        if not APP().connectionController.isConnected():
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
    """Display compact Fluent direction groups for live network statistics."""

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

        self.downloadTextLabel.setObjectName('TrafficSpeedLabel')
        self.uploadTextLabel.setObjectName('TrafficSpeedLabel')
        self.uploadUsageLabel.setObjectName('TrafficUsageLabel')
        self.downloadUsageLabel.setObjectName('TrafficUsageLabel')

        self.downloadBadge = QFrame(parent=self)
        self.downloadBadge.setObjectName('TrafficDirectionBadge')
        self.downloadBadge.setProperty('direction', 'download')

        self.uploadBadge = QFrame(parent=self)
        self.uploadBadge.setObjectName('TrafficDirectionBadge')
        self.uploadBadge.setProperty('direction', 'upload')

        downloadLayout = QHBoxLayout(self.downloadBadge)
        downloadLayout.setContentsMargins(8, 2, 8, 2)
        downloadLayout.setSpacing(5)
        downloadLayout.addWidget(self.downloadIconLabel)
        downloadLayout.addWidget(self.downloadTextLabel)
        downloadLayout.addWidget(self.downloadUsageLabel)

        uploadLayout = QHBoxLayout(self.uploadBadge)
        uploadLayout.setContentsMargins(8, 2, 8, 2)
        uploadLayout.setSpacing(5)
        uploadLayout.addWidget(self.uploadIconLabel)
        uploadLayout.addWidget(self.uploadTextLabel)
        uploadLayout.addWidget(self.uploadUsageLabel)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 1, 0, 1)
        self._layout.setSpacing(5)
        self._layout.addWidget(self.downloadBadge)
        self._layout.addWidget(self.uploadBadge)

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
        self.uploadUsageLabel.setText(f'• {formatTrafficUsage(upload)}')
        self.downloadUsageLabel.setText(f'• {formatTrafficUsage(download)}')
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

        self.serverMenu = AppQMenu(*serverActions, parent=self)
        self.serverButton = AppQPushButton(
            _('Server'),
            icon=bootstrapIcon('server.svg'),
        )
        # Keep the protocol/profile creation menu without presenting this as a
        # split or drop-down button. The regular button opens the menu itself.
        self.serverButton.clicked.connect(self.showServerMenu)

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
        self._widget.setObjectName('HomePageContent')
        self._layout = QVBoxLayout(self._widget)
        self._layout.setContentsMargins(20, 18, 20, 20)
        self._layout.setSpacing(12)

        self.pageTitleLabel = AppQLabel(_('Server'))
        self.pageTitleLabel.setObjectName('HomePageTitle')

        self.connectButton = ConnectionButton(
            APP().connectionController,
            self.activateSelectedServerForConnection,
            parent=self,
        )
        self.routingController = APP().routingController
        self.routingSelector = RoutingSelector(self.routingController, parent=self)

        self.searchLineEdit = AppQLineEdit()
        self.searchLineEdit.setPlaceholderText(
            _(
                'Search servers with text or regex, e.g. trojan, hk|jp, ^vmess, (us|sg).*tls'
            )
        )
        self.searchLineEdit.setMinimumWidth(280)
        self.searchLineEdit.setMaximumWidth(700)
        self.searchLineEdit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.searchButton = SearchButton()
        self.subscriptionFilterComboBox = AppQComboBox()
        self.subscriptionFilterComboBox.setMinimumWidth(190)
        self.subscriptionFilterComboBox.setMaximumWidth(300)
        self.subscriptionFilterComboBox.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )

        self.headerLayout = QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 0)
        self.headerLayout.setSpacing(8)
        self.headerLayout.addWidget(self.pageTitleLabel)
        self.headerLayout.addStretch(1)
        self.headerLayout.addWidget(self.searchLineEdit, 4)
        self.headerLayout.addWidget(self.searchButton)

        self.actionLayout = QHBoxLayout()
        self.actionLayout.setContentsMargins(0, 0, 0, 0)
        self.actionLayout.setSpacing(8)
        self.actionLayout.addWidget(self.connectButton)
        self.actionLayout.addWidget(self.routingSelector)
        self.actionLayout.addWidget(self.serverButton)
        self.actionLayout.addStretch(1)
        self.actionLayout.addWidget(self.subscriptionFilterComboBox)

        self._layout.addLayout(self.headerLayout)
        self._layout.addLayout(self.actionLayout)
        self._layout.addWidget(self.userServersQTableWidget, 1)

        self.searchButton.clicked.connect(
            lambda: self.userServersQTableWidget.search(self.searchLineEdit.text())
        )

        self.searchLineEdit.returnPressed.connect(
            lambda: self.userServersQTableWidget.search(self.searchLineEdit.text())
        )
        self.searchLineEdit.textChanged.connect(self.handleUserServersSearchTextChanged)

        self.subscriptionFilterComboBox.currentIndexChanged.connect(
            self.handleSubscriptionFilterChanged
        )

        self.userServersQTableWidget.subsManager.subscriptionsChanged.connect(
            self.refreshSubscriptionFilter
        )
        self.userServersQTableWidget.selectionModel().selectionChanged.connect(
            self.handleServerSelectionChanged
        )
        self.userServersQTableWidget.activeServerChanged.connect(
            self.routingController.refresh
        )

        self.refreshSubscriptionFilter()
        self.handleServerSelectionChanged()

        self.setCentralWidget(self._widget)

    @QtCore.Slot()
    def showServerMenu(self):
        """Open server creation actions below the regular Server button."""
        position = self.serverButton.mapToGlobal(
            QtCore.QPoint(0, self.serverButton.height() + 2)
        )

        self.serverMenu.popup(position)

    @QtCore.Slot()
    def handleServerSelectionChanged(self, *_args):
        """Apply Home's selection policy to the shared connection control."""
        self.connectButton.setSelectionCount(
            len(self.userServersQTableWidget.selectedIndex)
        )

    def activateSelectedServerForConnection(self) -> bool:
        """Activate exactly one selected server before requesting connection."""
        indexes = self.userServersQTableWidget.selectedIndex

        if len(indexes) != 1:
            return False

        self.userServersQTableWidget.activateSelectedServer()
        self.routingController.refresh()

        return Storage.UserActivatedItemIndex() == indexes[0]

    @QtCore.Slot(str)
    def handleUserServersSearchTextChanged(self, text: str):
        """Handle user servers search text changed."""
        if not text:
            self.userServersQTableWidget.clearSearch()

    @QtCore.Slot()
    def refreshSubscriptionFilter(self):
        """Refresh the stable group selector without losing its selection."""
        selected = self.subscriptionFilterComboBox.currentData()

        with Mixins.QBlockSignalContext(self.subscriptionFilterComboBox):
            self.subscriptionFilterComboBox.clear()
            self.subscriptionFilterComboBox.addItem(_('All Profiles'), None)
            self.subscriptionFilterComboBox.addItem(_('Manual Profiles'), '')

            for group in Storage.SubscriptionGroups():
                self.subscriptionFilterComboBox.addItem(
                    group.remark or group.webURL or group.id,
                    group.id,
                )

            index = self.subscriptionFilterComboBox.findData(selected)

            self.subscriptionFilterComboBox.setCurrentIndex(max(0, index))

        self.handleSubscriptionFilterChanged()

    @QtCore.Slot()
    def handleSubscriptionFilterChanged(self):
        """Apply the selected ownership group to the server table."""
        self.userServersQTableWidget.filterBySubscription(
            self.subscriptionFilterComboBox.currentData()
        )

    def showSubscriptionGroup(self, unique: str):
        """Select one group in the Home profile filter."""
        index = self.subscriptionFilterComboBox.findData(unique)

        if index >= 0:
            self.subscriptionFilterComboBox.setCurrentIndex(index)

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
