# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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
from Furious.Window.UserSubsWindow import *
from Furious.Window.LogViewerWindow import *
from Furious.Window.XrayAssetViewerWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtNetwork import *

from typing import Union

import logging
import functools

__all__ = ['AppMainWindow']

logger = logging.getLogger(__name__)

registerAppSettings('ServerWidgetWindowSize')

needTrans = functools.partial(needTransFn, source=__name__)


def connectedHttpProxyEndpoint() -> Union[str, None]:
    try:
        if APP().isSystemTrayConnected():
            index = AS_UserActivatedItemIndex()

            if index >= 0:
                return AS_UserServers()[index].httpProxyEndpoint()
            else:
                # Should not reach here
                return None
        else:
            return None
    except Exception:
        # Any non-exit exceptions

        return None


def connectedRemark() -> str:
    try:
        if APP().isSystemTrayConnected():
            index = AS_UserActivatedItemIndex()

            if index >= 0:
                return f'{index + 1} - ' + AS_UserServers()[index].getExtras('remark')
            else:
                # Should not reach here
                return ''
        else:
            return ''
    except Exception:
        # Any non-exit exceptions

        return ''


class AppNetworkStateManager(NetworkStateManager):
    def __init__(self, parent=None):
        super().__init__(parent)

    def successCallback(self):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(True)

    def errorCallback(self, errorString: str):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.setNetworkState(False, errorString=errorString)

    def startSingleTest(self):
        if not APP().isSystemTrayConnected():
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()

            self.stopTest()

        httpProxyEndpoint = connectedHttpProxyEndpoint()

        if httpProxyEndpoint is None:
            parent = self.parent()

            if isinstance(parent, AppMainWindow):
                parent.resetNetworkState()
        else:
            self.configureHttpProxy(httpProxyEndpoint)

            super().startSingleTest()

    def disconnectedCallback(self):
        parent = self.parent()

        if isinstance(parent, AppMainWindow):
            parent.resetNetworkState()

        self.stopTest()


needTrans(
    'Server',
    'Add VMess Server...',
    'Add VLESS Server...',
    'Add Shadowsocks Server...',
    'Add Trojan Server...',
    'Add Hysteria1 Server...',
    'Add Hysteria2 Server...',
    'Subscription',
    'Update Subscription (Use Current Proxy)',
    'Update Subscription (Force Proxy)',
    'Update Subscription (No Proxy)',
    'Edit Subscription...',
    'Log',
    'Show Furious Log',
    'Show Core Log',
    'Show Tun2socks Log',
    'Tools',
    'Manage Xray-core Asset File...',
    'Check For Updates',
    'About',
    'Help',
)


class AppMainWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))

        self.updatesManager = UpdatesManager()
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
        self.xrayAssetViewerWindow = XrayAssetViewerWindow()

        self.mainTab = AppQTabWidget()
        self.mainTab.addTab(self.userServersQTableWidget, _('Server'))

        logActions = [
            AppQAction(
                _('Show Furious Log'),
                callback=lambda: APP().logViewerWindowApp_.showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_F,
                ),
            ),
            AppQAction(
                _('Show Core Log'),
                callback=lambda: APP().logViewerWindowCore.showMaximized(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Show Tun2socks Log'),
                callback=lambda: APP().logViewerWindowTun_.showMaximized(),
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
        ]

        subsActions = [
            AppQAction(
                _('Update Subscription (Use Current Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    connectedHttpProxyEndpoint()
                ),
            ),
            AppQAction(
                _('Update Subscription (Force Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(
                    '127.0.0.1:10809'
                ),
            ),
            AppQAction(
                _('Update Subscription (No Proxy)'),
                callback=lambda: self.userServersQTableWidget.updateSubs(None),
            ),
            AppQSeperator(),
            AppQAction(
                _('Edit Subscription...'),
                icon=bootstrapIcon('star.svg'),
                callback=lambda: self.userSubsWindow.show(),
            ),
        ]

        toolsActions = [
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
                    callback=lambda: self.checkForUpdates(),
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
                        callback=lambda: self.checkForUpdates(),
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

    def appendNewItemByFactory(self, factory: ConfigurationFactory):
        self.userServersQTableWidget.appendNewItemByFactory(factory)

    def flushRow(self, row: int, item: ConfigurationFactory):
        self.userServersQTableWidget.flushRow(row, item)

    def showTabAndSpaces(self):
        self.userServersQTableWidget.showTabAndSpaces()

    def hideTabAndSpaces(self):
        self.userServersQTableWidget.hideTabAndSpaces()

    def checkForUpdates(self):
        self.updatesManager.configureHttpProxy(connectedHttpProxyEndpoint())
        self.updatesManager.checkForUpdates()

    def resetNetworkState(self):
        self.networkState.setText('')

    def setNetworkState(self, success: bool, **kwargs):
        remark = connectedRemark()

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
    def openAboutPage():
        if QDesktopServices.openUrl(QtCore.QUrl(APPLICATION_ABOUT_PAGE)):
            logger.info('open about page success')
        else:
            logger.error('open about page failed')

    def setWidthAndHeight(self):
        try:
            windowSize = AppSettings.get('ServerWidgetWindowSize').split(',')

            self.setGeometry(100, 100, *list(int(size) for size in windowSize))
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 1800, 960)

    def cleanup(self):
        AppSettings.set(
            'ServerWidgetWindowSize',
            f'{self.geometry().width()},{self.geometry().height()}',
        )
