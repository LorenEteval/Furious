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
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import MetricsHistory, PluginNavigationManager
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

    QT_FALLBACK_WINDOW_SIZE = QtCore.QSize(640, 480)

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
        self.metricsHistory = MetricsHistory(parent=self)
        self.homePage.trafficStatsManager.sampleChanged.connect(
            self.metricsHistory.recordTrafficSample
        )
        self.homePage.trafficStatsManager.usageHistoryReset.connect(
            self.metricsHistory.clearTrafficUsageHistory
        )
        self.metricsPage = MetricsPage(
            self.metricsHistory,
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

        AppConnectionController().interactionEnabledChanged.connect(
            self.settingsPage.setConnectionControlsEnabled
        )

        self.settingsPage.setConnectionControlsEnabled(
            AppConnectionController().interactionEnabled
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

    def appendNewItemByFactory(self, factory: CoreConfiguration | ServerProfile):
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

    def prepareInitialGeometry(self):
        """Restore persisted geometry after composition and before first show."""
        savedGeometry = AppSettings.get('AppMainWindowGeometry')

        if savedGeometry is None:
            if not self._restoreLegacyWindowSize():
                self._applyDefaultWindowSize('no saved main-window geometry')
        else:
            try:
                restored = self.restoreInitialGeometry(savedGeometry)
            except Exception:
                # Any non-exit exceptions

                logger.exception('unexpected main-window geometry restore failure')

                restored = False

            if restored and self.size() == self.QT_FALLBACK_WINDOW_SIZE:
                self._applyDefaultWindowSize(
                    'saved main-window geometry restored to the Qt fallback size'
                )
            elif restored:
                logger.info(
                    f'restored main-window geometry: {self.geometry().getRect()}'
                )
            else:
                self._applyDefaultWindowSize('saved main-window geometry was invalid')

        self._restoreMainWindowState()

    def _applyDefaultWindowSize(self, reason: str):
        """Apply the canonical first-launch/recovery size and center it."""
        self.resize(self.DEFAULT_WINDOW_SIZE)

        logger.info(
            f'{reason}; using default main-window size '
            f'{self.DEFAULT_WINDOW_SIZE.toTuple()}'
        )

    def _restoreLegacyWindowSize(self) -> bool:
        """Restore one valid legacy client size without guessing its origin."""
        legacySize = AppSettings.get('ServerWidgetWindowSize')

        if legacySize is None:
            return False

        try:
            widthText, heightText = legacySize.split(',')
            width, height = int(widthText), int(heightText)

            if width <= 0 or height <= 0:
                raise ValueError('window dimensions must be positive')
        except (AttributeError, TypeError, ValueError):
            logger.warning(f'ignored invalid legacy main-window size: {legacySize!r}')

            return False

        self.resize(width, height)

        logger.info(f'migrated legacy main-window size: {(width, height)}')

        return True

    def _restoreMainWindowState(self):
        """Restore QMainWindow layout state independently from its geometry."""
        savedState = AppSettings.get('AppMainWindowState')

        if savedState is None:
            return

        try:
            restored = self.restoreState(savedState)
        except Exception:
            # Any non-exit exceptions

            logger.exception('unexpected main-window state restore failure')

            return

        if not restored:
            logger.warning('saved main-window state was invalid and was ignored')

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
