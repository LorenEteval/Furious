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

"""Provide the page-based application main window."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Models import ConfigFactory, ServerProfile
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import MetricsDataManager, PluginNavigationManager
from Furious.Widget.NavigationView import NavigationView
from Furious.Window.HomePage import HomePage
from Furious.Window.LogPage import LogPage
from Furious.Window.MetricsPage import MetricsPage
from Furious.Window.SettingsPage import SettingsPage
from Furious.Window.SubscriptionPage import SubscriptionPage

from PySide6 import QtCore

from typing import Union

import logging

__all__ = ['MainWindow']

logger = logging.getLogger(__name__)

# Migrate legacy settings.
registerAppSettings('ServerWidgetWindowSize')
registerAppSettings('AppMainWindowGeometry')
registerAppSettings('AppMainWindowState')
registerAppSettings('AppMainWindowSelectedPage', default='home')
registerAppSettings('AppMainWindowNavigationExpanded', isBinary=True)

_TRANSLATABLE_NAVIGATION_LABELS = (
    _('Home'),
    _('Log'),
    _('Subscription'),
    _('Metrics'),
    _('Settings'),
)


class MainWindow(AppQMainWindow):
    """Manage application pages, navigation, and global window state."""

    DEFAULT_WINDOW_SIZE_DARWIN = QtCore.QSize(1500, 780)
    DEFAULT_WINDOW_SIZE = (
        QtCore.QSize(1800, 960) if PLATFORM != 'Darwin' else DEFAULT_WINDOW_SIZE_DARWIN
    )

    def __init__(self, *args, **kwargs):
        """Create and register the built-in application pages."""
        super().__init__(*args, **kwargs)

        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.menuBar().hide()

        self.navigationView = NavigationView(parent=self)
        self.homePage = HomePage(parent=self.navigationView)
        self.subscriptionPage = SubscriptionPage(
            self.homePage.userServersQTableWidget,
            parent=self.navigationView,
        )
        self.metricsDataManager = MetricsDataManager(parent=self)
        self.homePage.trafficStatsManager.sampleChanged.connect(
            self.metricsDataManager.recordTrafficSample
        )
        self.homePage.trafficStatsManager.usageHistoryReset.connect(
            self.metricsDataManager.clearTrafficUsageHistory
        )
        self.metricsPage = MetricsPage(
            self.metricsDataManager,
            parent=self.navigationView,
        )
        self.logPage = AppLogPage()
        self.settingsPage = SettingsPage(
            tunSettingsDialogFactory=self.homePage.getGuiTUNSettings,
            proxyBypassDialog=self.homePage.customizeProxyBypassDialog,
            networkTestDialog=self.homePage.customizeNetworkTestDialog,
            checkForUpdates=self.homePage.checkForUpdates,
            openAboutPage=self.homePage.openAboutPage,
            restartAsAdmin=self.homePage.restartAsAdmin,
            openApplicationFolder=self.homePage.openApplicationFolder,
            parent=self.navigationView,
        )

        if not isinstance(self.logPage, LogPage):
            raise TypeError('application log page must be a LogPage')

        self.navigationView.addPage(
            'home',
            self.homePage,
            'Home',
            'house-door.svg',
        )
        self.navigationView.addPage(
            'log',
            self.logPage,
            'Log',
            'pin-angle.svg',
        )
        self.navigationView.addPage(
            'subscription',
            self.subscriptionPage,
            'Subscription',
            'collection.svg',
        )
        self.pluginNavigationManager = PluginNavigationManager()
        self.pluginNavigationManager.registerPages(self.navigationView)
        self.navigationView.addPage(
            'metrics',
            self.metricsPage,
            'Metrics',
            'speedometer2.svg',
        )
        self.navigationView.addPage(
            'settings',
            self.settingsPage,
            'Settings',
            'gear-wide-connected.svg',
            placement='bottom',
        )
        self.navigationView.pageChanged.connect(self._pageChanged)
        self.navigationView.expandedChanged.connect(self._navigationExpandedChanged)

        self.navigationView.setExpanded(
            AppSettings.isStateON_('AppMainWindowNavigationExpanded'),
            animated=False,
        )
        self.navigationView.setCurrentPage(
            str(AppSettings.get('AppMainWindowSelectedPage'))
        )
        self.setCentralWidget(self.navigationView)

        # Preserve the established application-facing server-management API.
        self.userServersQTableWidget = self.homePage.userServersQTableWidget
        self.userSubsWindow = self.subscriptionPage
        self.networkConnectivityManager = self.homePage.networkConnectivityManager
        self.networkState = self.homePage.networkState
        self.trafficStats = self.homePage.trafficStats
        self.trafficStatsManager = self.homePage.trafficStatsManager

        self.retranslate()

    @QtCore.Slot(str)
    def _pageChanged(self, pageId: str):
        """Persist the current page selected through navigation."""
        AppSettings.set('AppMainWindowSelectedPage', pageId)

    @QtCore.Slot(bool)
    def _navigationExpandedChanged(self, expanded: bool):
        """Persist the navigation menu expansion state."""
        if expanded:
            AppSettings.turnON_('AppMainWindowNavigationExpanded')
        else:
            AppSettings.turnOFF('AppMainWindowNavigationExpanded')

    def showPage(self, pageId: str):
        """Navigate to a registered application page."""
        self.navigationView.setCurrentPage(pageId)

    def showLogPage(self):
        """Navigate directly to the unified logging page."""
        self.showPage('log')

    def showSettingsPage(self):
        """Navigate directly to application settings."""
        self.show()
        self.showPage('settings')

    def showSubscriptionPage(self):
        """Navigate directly to subscription management."""
        self.show()
        self.showPage('subscription')

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        """Forward a subscription update to the dedicated page controller."""
        self.subscriptionPage.updateSubsByUnique(unique, httpProxy, **kwargs)

    def appendNewItemByFactory(self, factory: ConfigFactory | ServerProfile):
        """Forward a new server profile to the home page."""
        self.homePage.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ServerProfile):
        """Forward a server-row refresh to the home page."""
        self.homePage.flushRow(row, item)

    def showTabAndSpaces(self):
        """Enable whitespace markers in home-page editors."""
        self.homePage.showTabAndSpaces()

    def hideTabAndSpaces(self):
        """Disable whitespace markers in home-page editors."""
        self.homePage.hideTabAndSpaces()

    def getGuiTUNSettings(self, **kwargs):
        """Return the home page's TUN settings editor."""
        return self.homePage.getGuiTUNSettings(**kwargs)

    def checkForUpdates(self, **kwargs):
        """Forward update checks to the home page."""
        self.homePage.checkForUpdates(**kwargs)

    def resetNetworkState(self):
        """Clear the home page network state."""
        self.homePage.resetNetworkState()

    def setNetworkState(self, success: bool, **kwargs):
        """Update the home page network state."""
        self.homePage.setNetworkState(success, **kwargs)

    def setWidthAndHeight(self):
        """Restore the saved application window geometry and state."""
        if AppSettings.get('AppMainWindowGeometry') is None:
            try:
                windowSize = AppSettings.get('ServerWidgetWindowSize').split(',')
                width, height = tuple(int(size) for size in windowSize)

                if (width, height) == (640, 480):
                    self.resize(self.DEFAULT_WINDOW_SIZE)
                else:
                    self.resize(width, height)
            except Exception:
                # Any non-exit exceptions

                self.resize(self.DEFAULT_WINDOW_SIZE)
        else:
            try:
                self.restoreGeometry(AppSettings.get('AppMainWindowGeometry'))
            except Exception:
                # Any non-exit exceptions

                self.resize(self.DEFAULT_WINDOW_SIZE)

            try:
                self.restoreState(AppSettings.get('AppMainWindowState'))
            except Exception:
                # Any non-exit exceptions

                pass

            if PLATFORM == 'Darwin':
                APP().processEvents()

                size = self.size()

                if size == QtCore.QSize(640, 480):
                    logger.error(
                        f'detected unresolved Qt bug on macOS. '
                        f'Resizing main window to default '
                        f'{self.DEFAULT_WINDOW_SIZE.toTuple()}'
                    )

                    self.resize(self.DEFAULT_WINDOW_SIZE)
                else:
                    logger.info(
                        f'restore main window size on macOS success: '
                        f'{size.toTuple()}'
                    )

    def showEvent(self, event):
        """Focus the window itself instead of an untouched child control."""
        super().showEvent(event)

        self.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)

    def retranslate(self):
        """Refresh the application window title."""
        if SystemRuntime.isAdmin():
            self.setWindowTitle(f'{_(APPLICATION_NAME)} ({_(ADMINISTRATOR_NAME)})')
        else:
            self.setWindowTitle(_(APPLICATION_NAME))

    def cleanup(self):
        """Persist application-level window state."""
        AppSettings.set('AppMainWindowGeometry', self.saveGeometry())
        AppSettings.set('AppMainWindowState', self.saveState())
