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

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Utility import *
from Furious.Widget.UserServersQTableWidget import *
from Furious.Widget.GuiTUNSettings import *
from Furious.Window.UserSubsWindow import *
from Furious.Window.XrayAssetViewerWindow import *

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

        connectedHttpProxy = Storage.Extras.UserHttpProxy()

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
    DEFAULT_WINDOW_SIZE_DARWIN = QtCore.QSize(1500, 780)
    DEFAULT_WINDOW_SIZE = (
        QtCore.QSize(1800, 960) if PLATFORM != 'Darwin' else DEFAULT_WINDOW_SIZE_DARWIN
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if SystemRuntime.isAdmin():
            self.setWindowTitle(f'{_(APPLICATION_NAME)} ({_(ADMINISTRATOR_NAME)})')
        else:
            self.setWindowTitle(f'{_(APPLICATION_NAME)}')
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
                    for index, server in enumerate(Storage.UserServers())
                    if server.getExtras('subsId') == unique
                )
            ),
        )
        self.xrayAssetViewerWindow = XrayAssetViewerWindow(parent=self)

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

        customizeTUNSettingsAction = [
            AppQAction(
                _('Customize TUN Settings...'),
                icon=bootstrapIcon('diagram-3.svg'),
                checkable=False,
                callback=lambda: self.getGuiTUNSettings().open(),
            ),
            AppQSeperator(),
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

        if PLATFORM == 'Darwin':
            openAppFolderAction = [
                AppQSeperator(),
            ]
        else:
            openAppFolderAction = [
                AppQAction(
                    _('Open Application Folder'),
                    icon=bootstrapIcon('folder2.svg'),
                    checkable=False,
                    callback=lambda: self.openApplicationFolder(),
                ),
                AppQSeperator(),
            ]

        toolsActions = [
            *customizeTUNSettingsAction,
            *restartAsAdminAction,
            *openAppFolderAction,
            AppQAction(
                _('Manage Xray-core Asset File...'),
                callback=lambda: self.xrayAssetViewerWindow.show(),
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
                    icon=bootstrapIcon('database.svg'),
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

    def appendNewItemByFactory(self, factory: ConfigFactory):
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ConfigFactory):
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
        guiTUNSettings.factoryToInput(Storage.UserTUNSettings())

        return guiTUNSettings

    def checkForUpdates(self, **kwargs):
        self.updatesManager.configureHttpProxy(Storage.Extras.UserHttpProxy())
        self.updatesManager.checkForUpdates(**kwargs)

    def resetNetworkState(self):
        self.networkState.setText('')

    def setNetworkState(self, success: bool, **kwargs):
        remark = Storage.Extras.UserServerRemark()

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
    def restartAsAdmin():
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
        if QDesktopServices.openUrl(QtCore.QUrl(APPLICATION_ABOUT_PAGE)):
            logger.info('open about page success')
        else:
            logger.error('open about page failed')

    def setWidthAndHeight(self):
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

    def cleanup(self):
        AppSettings.set('AppMainWindowGeometry', self.saveGeometry())
        AppSettings.set('AppMainWindowState', self.saveState())
