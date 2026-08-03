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

"""Provide the application window for app main window."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Plugins import getPluginRegistry
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Widget.UserServersQTableView import *
from Furious.Widget.GuiCustomizeNetworkTest import *
from Furious.Widget.GuiCustomizeProxyBypass import *
from Furious.Widget.GuiTUNSettings import *
from Furious.Window.UserSubsWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from typing import Union

import os
import logging
import functools

__all__ = ['AppMainWindow']

logger = logging.getLogger(__name__)

# Migrate legacy settings
registerAppSettings('ServerWidgetWindowSize')
registerAppSettings('AppMainWindowGeometry')
registerAppSettings('AppMainWindowState')


class AppNetworkConnectivityManager(NetworkConnectivityManager):
    """Coordinate app network connectivity operations."""

    def __init__(self, parent=None):
        """Initialize the AppNetworkConnectivityManager."""
        super().__init__(parent)

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(True)

        super().successCallback(networkReply, **kwargs)

    def failureCallback(self, networkReply, **kwargs):
        """Handle a failed network operation."""
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(False, errorString=networkReply.errorString())

        super().failureCallback(networkReply, **kwargs)

    def startSingleTest(self):
        """Start single test."""
        if not APP().isSystemTrayConnected():
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()

            self.stopTest()

        connectedHttpProxy = Storage.Extras.UserHttpProxy()

        if connectedHttpProxy is None:
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()
        else:
            self.configureHttpProxy(connectedHttpProxy)

            super().startSingleTest()

    def disconnectedCallback(self):
        """Update the app network connectivity manager for a disconnected state."""
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
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


class SearchButton(AppQPushButton):
    """Represent search button."""

    def __init__(self, *args, **kwargs):
        """Initialize the SearchButton."""
        super().__init__(*args, **kwargs)

        self.setText(self.customText())
        self.setIcon(bootstrapIcon('search.svg'))

    @staticmethod
    def customText():
        """Return the user-facing message text for the search button."""
        return ' ' * 2 + _('Search')

    def retranslate(self):
        """Refresh translated text for the search button."""
        self.setText(self.customText())


class AppMainWindow(AppQMainWindow):
    """Present the app main window."""

    DEFAULT_WINDOW_SIZE_DARWIN = QtCore.QSize(1500, 780)
    DEFAULT_WINDOW_SIZE = (
        QtCore.QSize(1800, 960) if PLATFORM != 'Darwin' else DEFAULT_WINDOW_SIZE_DARWIN
    )

    def __init__(self, *args, **kwargs):
        """Initialize the AppMainWindow."""
        super().__init__(*args, **kwargs)

        if SystemRuntime.isAdmin():
            self.setWindowTitle(f'{_(APPLICATION_NAME)} ({_(ADMINISTRATOR_NAME)})')
        else:
            self.setWindowTitle(f'{_(APPLICATION_NAME)}')

        # TODO: Need this?
        # self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.updatesManager = UpdatesManager(parent=self)
        self.networkConnectivityManager = AppNetworkConnectivityManager(parent=self)

        self.userServersQTableWidget = UserServersQTableView(parent=self)
        self.userSubsWindow = UserSubsWindow(
            parent=self,
            deleteUniqueCallback=lambda unique: self.userServersQTableWidget.deleteItemByIndex(
                list(
                    index
                    for index, server in enumerate(Storage.UserServers())
                    if server.getExtras('subsId') == unique
                ),
                showProgress=False,
            ),
        )
        pluginRegistry = getPluginRegistry()
        self.customizeProxyBypassDialog = GuiCustomizeProxyBypassDialog(parent=self)
        self.customizeNetworkTestDialog = GuiCustomizeNetworkTestDialog(parent=self)

        self.mainTab = AppQTabWidget()
        self.mainTab.addTab(self.userServersQTableWidget, _('Server'))

        logActions = [
            AppQAction(
                _('Show Furious Log...'),
                callback=lambda: AppLoggerWindow.Self().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_F,
                ),
            ),
            AppQAction(
                _('Show Core Log...'),
                callback=lambda: AppLoggerWindow.Core().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Show Tun2socks Log...'),
                callback=lambda: AppLoggerWindow.TUN_().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_T,
                ),
            ),
        ]

        serverActions = []
        for descriptor in pluginRegistry.protocolDescriptors():
            if descriptor.separatorBefore and serverActions:
                serverActions.append(AppQSeperator())

            actionText = _(descriptor.addActionText)
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
        for plugin in pluginRegistry.plugins():
            managementActions = pluginRegistry.managementActions(
                plugin,
                parent=self,
            )
            if managementActions:
                corePluginActions.append(
                    AppQAction(
                        _(plugin.displayName),
                        menu=AppQMenu(*managementActions),
                        useActionGroup=False,
                        checkable=False,
                    )
                )
            else:
                corePluginActions.append(
                    AppQAction(
                        _(plugin.displayName),
                        checkable=False,
                    )
                )

        pluginActions = [
            AppQAction(
                _('Core'),
                menu=AppQMenu(*corePluginActions),
                useActionGroup=False,
                checkable=False,
            )
        ]
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
                    _('Log'),
                    icon=bootstrapIcon('pin-angle.svg'),
                    menu=AppQMenu(*logActions),
                    useSetMenu=False,
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
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
            self.toolbar.setObjectName('AppMainWindow_AppQToolBar')
            self.toolbar.setIconSize(QtCore.QSize(64, 32))
            self.toolbar.setToolButtonStyle(
                QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            self.addToolBar(self.toolbar)
        else:
            # Menu actions
            logMenu = {
                'name': 'Log',
                'actions': [*logActions],
            }

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
                _('Log'),
                _('Server'),
                _('Subscription'),
                _('Plugins'),
                _('Tools'),
                _('Help'),
            ]

            # Menus
            for menuDict in (
                logMenu,
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

        self.networkState = NetworkStateBadge(parent=self)

        self.statusBar().addPermanentWidget(self.networkState)

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
        self._layout.addWidget(self.mainTab)

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

    def appendNewItemByFactory(self, factory: ConfigFactory):
        """Append new item by factory."""
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ConfigFactory):
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
            """Return the cached GUI TUN settings value used by the app main window."""
            parent = kwargs.pop('parent', self)

            return GuiTUNSettings(parent=parent, **kwargs)

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
        """Handle restart as admin for the app main window."""
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

    def setWidthAndHeight(self):
        """Apply the default size for the app main window."""
        if AppSettings.get('AppMainWindowGeometry') is None:
            # Migrate legacy settings
            try:
                windowSize = AppSettings.get('ServerWidgetWindowSize').split(',')

                width, height = tuple(int(size) for size in windowSize)

                if (width, height) == (640, 480):
                    self.resize(AppMainWindow.DEFAULT_WINDOW_SIZE)
                else:
                    self.resize(width, height)
            except Exception:
                # Any non-exit exceptions

                self.resize(AppMainWindow.DEFAULT_WINDOW_SIZE)
        else:
            try:
                self.restoreGeometry(AppSettings.get('AppMainWindowGeometry'))
            except Exception:
                # Any non-exit exceptions

                self.resize(AppMainWindow.DEFAULT_WINDOW_SIZE)

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
                        f'detected unresolve Qt bug on macOS. '
                        f'Resizing main window to default '
                        f'{AppMainWindow.DEFAULT_WINDOW_SIZE.toTuple()}'
                    )
                    self.resize(AppMainWindow.DEFAULT_WINDOW_SIZE)
                else:
                    logger.info(
                        f'restore main window size on macOS success: '
                        f'{size.toTuple()}'
                    )

    def retranslate(self):
        """Refresh translated text for the app main window."""
        if SystemRuntime.isAdmin():
            self.setWindowTitle(f'{_(APPLICATION_NAME)} ({_(ADMINISTRATOR_NAME)})')
        else:
            self.setWindowTitle(f'{_(APPLICATION_NAME)}')

    def cleanup(self):
        """Release resources owned by the app main window."""
        AppSettings.set('AppMainWindowGeometry', self.saveGeometry())
        AppSettings.set('AppMainWindowState', self.saveState())
