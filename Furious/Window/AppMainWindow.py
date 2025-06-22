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

from __future__ import annotations

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Library import *
from Furious.Utility import *
from Furious.Widget.UserServersQTableWidget import *
from Furious.Widget.GuiTUNSettings import *
from Furious.Window.UserSubsWindow import *
from Furious.Window.LogViewerWindow import *
from Furious.Window.XrayAssetViewerWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

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


class AppNetworkStateManager(NetworkStateManager):
    def __init__(self, parent=None):
        super().__init__(parent)

    def successCallback(self, networkReply, **kwargs):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(True)

        super().successCallback(networkReply, **kwargs)

    def failureCallback(self, networkReply, **kwargs):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(False, errorString=networkReply.errorString())

        super().failureCallback(networkReply, **kwargs)

    def startSingleTest(self):
        if not APP().isSystemTrayConnected():
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()

            self.stopTest()

        connectedHttpProxy = connectedHttpProxyEndpoint()

        if connectedHttpProxy is None:
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()
        else:
            self.configureHttpProxy(connectedHttpProxy)

            super().startSingleTest()

    def disconnectedCallback(self):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.resetNetworkState()

        super().disconnectedCallback()


class AppMainWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        # TODO: Need this?
        # self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.updatesManager = UpdatesManager(parent=self)
        self.networkStateManager = AppNetworkStateManager(parent=self)

        self.userServersQTableWidget = UserServersQTableWidget(parent=self)
        self.userSubsWindow = UserSubsWindow(
            parent=self,
            deleteUniqueCallback=lambda unique: self.userServersQTableWidget.deleteItemByIndex(
                list(
                    index
                    for index, server in enumerate(AS_UserServers())
                    if server.getExtras('subsId') == unique
                )
            ),
        )
        self.xrayAssetViewerWindow = XrayAssetViewerWindow(parent=self)

        self.mainTab = AppQTabWidget()
        self.mainTab.addTab(self.userServersQTableWidget, _('Server'))

        logActions = [
            AppQAction(
                _('Show Furious Log'),
                callback=lambda: loggerApp_().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_F,
                ),
            ),
            AppQAction(
                _('Show Core Log'),
                callback=lambda: loggerCore().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Show Tun2socks Log'),
                callback=lambda: loggerTun_().showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_T,
                ),
            ),
        ]

        serverActions = [
            AppQAction(
                _('Add VMess Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.VMess, _('Add VMess Server...')
                ),
            ),
            AppQAction(
                _('Add VLESS Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.VLESS, _('Add VLESS Server...')
                ),
            ),
            AppQAction(
                _('Add Shadowsocks Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.Shadowsocks, _('Add Shadowsocks Server...')
                ),
            ),
            AppQAction(
                _('Add Trojan Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.Trojan, _('Add Trojan Server...')
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Add Hysteria1 Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.Hysteria1, _('Add Hysteria1 Server...')
                ),
            ),
            AppQAction(
                _('Add Hysteria2 Server...'),
                callback=lambda: self.userServersQTableWidget.addServerViaGui(
                    Protocol.Hysteria2, _('Add Hysteria2 Server...')
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('New Empty Configuration'),
                callback=lambda: self.userServersQTableWidget.newEmptyItem(),
            ),
        ]

        subsActions = [
            AppQAction(
                _('Update Subscription (Use Current Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    connectedHttpProxyEndpoint(),
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

        if PLATFORM == 'Darwin':
            openAppFolderAction = [None]
        else:
            openAppFolderAction = [
                AppQSeperator(),
                AppQAction(
                    _('Open Application Folder'),
                    callback=lambda: self.openApplicationFolder(),
                ),
            ]

        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            customizeTUNSettingsAction = [
                AppQAction(
                    _('Customize TUN Settings...'),
                    icon=bootstrapIcon('diagram-3.svg'),
                    checkable=False,
                    callback=lambda: self.getGuiTUNSettings().open(),
                ),
                AppQSeperator(),
            ]
        else:
            customizeTUNSettingsAction = []

        toolsActions = [
            *customizeTUNSettingsAction,
            AppQAction(
                _('Manage Xray-core Asset File...'),
                callback=lambda: self.xrayAssetViewerWindow.show(),
            ),
            *openAppFolderAction,
        ]

        if hasattr(AppQAction, 'setMenu'):
            self.toolbar = AppQToolBar(
                AppQAction(
                    _('Log'),
                    icon=bootstrapIcon('pin-angle.svg'),
                    menu=AppQMenu(*logActions),
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
                AppQAction(
                    _('Server'),
                    icon=bootstrapIcon('database.svg'),
                    menu=AppQMenu(*serverActions),
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
                AppQAction(
                    _('Subscription'),
                    icon=bootstrapIcon('collection.svg'),
                    menu=AppQMenu(*subsActions),
                    useActionGroup=False,
                    checkable=False,
                ),
                AppQSeperator(),
                AppQAction(
                    _('Tools'),
                    icon=bootstrapIcon('tools.svg'),
                    menu=AppQMenu(*toolsActions),
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
            TRANSLATABLE_MENU_NAME = [
                _('Log'),
                _('Server'),
                _('Subscription'),
                _('Tools'),
                _('Help'),
            ]

            # Menus
            for menuDict in (logMenu, serverMenu, subsMenu, toolsMenu, helpMenu):
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

        self.networkState = AppQLabel(translatable=False)

        self.statusBar().addPermanentWidget(self.networkState)

        self._widget = QWidget()
        self._layout = QVBoxLayout(self._widget)
        self._layout.addWidget(self.mainTab)

        self.setCentralWidget(self._widget)

    def updateSubsByUnique(self, unique: str, httpProxy: Union[str, None], **kwargs):
        self.userServersQTableWidget.updateSubsByUnique(unique, httpProxy, **kwargs)

    def appendNewItemByFactory(self, factory: ConfigurationFactory):
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ConfigurationFactory):
        self.userServersQTableWidget.flushRow(row, item)

    def showTabAndSpaces(self):
        self.userServersQTableWidget.showTabAndSpaces()

    def hideTabAndSpaces(self):
        self.userServersQTableWidget.hideTabAndSpaces()

    def getGuiTUNSettings(self, **kwargs):
        @functools.lru_cache(None)
        def cachedGuiTUNSettings():
            parent = kwargs.pop('parent', self)

            return GuiTUNSettings(parent=parent, **kwargs)

        guiTUNSettings = cachedGuiTUNSettings()
        guiTUNSettings.factoryToInput(AS_UserTUNSettings())

        return guiTUNSettings

    def checkForUpdates(self, **kwargs):
        self.updatesManager.configureHttpProxy(connectedHttpProxyEndpoint())
        self.updatesManager.checkForUpdates(**kwargs)

    def resetNetworkState(self):
        self.networkState.setText('')

    def setNetworkState(self, success: bool, **kwargs):
        remark = connectedServerRemark()

        if success:
            if remark:
                self.networkState.setText(f'{remark} {UNICODE_LARGE_GREEN_CIRCLE}')
            else:
                self.resetNetworkState()
        else:
            errorString = kwargs.pop('errorString', '')

            if remark:
                self.networkState.setText(
                    f'{remark} - {errorString} {UNICODE_LARGE_RED_CIRCLE}'
                )
            else:
                self.resetNetworkState()

    @staticmethod
    def openApplicationFolder():
        appFolder = os.path.dirname(APP().applicationFilePath())

        if QDesktopServices.openUrl(QtCore.QUrl(appFolder)):
            logger.info(f'open application folder \'{appFolder}\' success')
        else:
            logger.error(f'open application folder \'{appFolder}\' failed')

    @staticmethod
    def openAboutPage():
        if QDesktopServices.openUrl(QtCore.QUrl(APPLICATION_ABOUT_PAGE)):
            logger.info('open about page success')
        else:
            logger.error('open about page failed')

    def setWidthAndHeight(self):
        if AppSettings.get('AppMainWindowGeometry') is None:
            # Migrate legacy settings
            try:
                windowSize = AppSettings.get('ServerWidgetWindowSize').split(',')

                self.resize(*list(int(size) for size in windowSize))
            except Exception:
                # Any non-exit exceptions

                self.resize(1800, 960)
        else:
            try:
                self.restoreGeometry(AppSettings.get('AppMainWindowGeometry'))
            except Exception:
                # Any non-exit exceptions

                pass

            try:
                self.restoreState(AppSettings.get('AppMainWindowState'))
            except Exception:
                # Any non-exit exceptions

                pass

    def cleanup(self):
        AppSettings.set('AppMainWindowGeometry', self.saveGeometry())
        AppSettings.set('AppMainWindowState', self.saveState())
