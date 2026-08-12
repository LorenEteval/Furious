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

"""Provide widgets for application."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Core import Tun2socks
from Furious.Backends import OFFICIAL_PLUGIN_TYPES
from Furious.Controllers import (
    ConnectionController,
    RoutingController,
    SettingsController,
)
from Furious.Extensions import BUNDLED_EXTENSION_TYPES
from Furious.Plugins import getPluginRegistry, initializePluginRegistry
from Furious.Qt import AppStyleSheet
from Furious.Qt.TextEditorTheme import configureEditorLogMetadata
from Furious.Qt import gettext as _
from Furious.Repository import *
from Furious.Service import ApplicationLogHandler, LogManager
from Furious.Application.TrayIcon import *
from Furious.Window.LogPage import *
from Furious.Window.MainWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtNetwork import *
from PySide6.QtWidgets import *

import os
import sys
import logging
import platform
import threading
import functools
import traceback
import darkdetect

logger = logging.getLogger(__name__)


class SystemTrayUnavailable(Exception):
    """Represent system tray unavailable."""

    pass


class ApplicationExitHelper(QApplication):
    """Represent application exit helper."""

    def __init__(self, argv):
        """Initialize the ApplicationExitHelper."""
        super().__init__(argv)

        # Exiting flag
        self._exiting = False

    def setExitingFlag(self, value: bool):
        """Set exiting flag."""
        self._exiting = value

    def isExiting(self) -> bool:
        """Return whether exiting."""
        return self._exiting is True


class SingletonApplication(ApplicationExitHelper):
    """Represent singleton application."""

    def __init__(self, argv):
        """Initialize the SingletonApplication."""
        super().__init__(argv)

        self.serverName = LOCAL_SERVER_NAME

        self.socket = QLocalSocket(self)
        self.server = QLocalServer(self)

    def hasRunningApp(self) -> bool:
        """Return whether running app."""
        self.socket.connectToServer(self.serverName)

        if self.socket.waitForConnected(1000):
            if len(sys.argv) == 1:
                command = AppBuiltinCommand.Empty.value
            else:
                command = sys.argv[1]

            self.socket.write(command.encode())
            self.socket.flush()

            if command == AppBuiltinCommand.Empty.value:
                # Show tray message in the started instance. Do not start
                return True
            elif command == AppBuiltinCommand.RunAs.value:
                if self.socket.waitForDisconnected(3000):
                    # The other instance have been exited. Start
                    return False
                else:
                    # Do not start
                    return True
            else:
                # TODO: Not implemented
                # Do not start
                return True
        else:
            # Remove the old socket file if it exists
            socket_path = QLocalServer.removeServer(self.serverName)

            if socket_path:
                logger.info(f'old socket file removed: {self.serverName}')
            else:
                logger.info(f'no existing socket file found for: {self.serverName}')

            # New instance
            self.server.newConnection.connect(self.handleNewConnection)

            if not self.server.listen(self.serverName):
                # Do not start
                logger.error(f'unable to listen on server: {self.serverName}')

                return True

            # Start
            return False

    @QtCore.Slot()
    def handleNewConnection(self):
        """Handle new connection."""
        raise NotImplementedError


class ApplicationThemeDetector(QtCore.QObject):
    """Represent application theme detector."""

    themeChanged = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        """Initialize the ApplicationThemeDetector."""
        super().__init__(*args, **kwargs)


class DesktopApplication(ApplicationRunner, SingletonApplication):
    """Represent application."""

    def __init__(self, argv):
        """Initialize the desktop application."""
        super().__init__(argv)

        self.setApplicationName(APPLICATION_NAME)
        self.setApplicationVersion(APPLICATION_VERSION)
        self.setOrganizationName(ORGANIZATION_NAME)
        self.setOrganizationDomain(ORGANIZATION_DOMAIN)

        self.systemTray = None

        # Font
        self.customFontLoadMsg = ''
        self.customFontEnabled = False
        self.customFontName = ''

        # Theme Detect
        self.currentTheme = None
        self.themeDetectTimer = None
        self.themeDetector = None
        self.themeListenerThread = None

        self.mainWindow = None
        self.systemTray = None
        self.connectionController = None
        self.routingController = None
        self.settingsController = None

        # Unified logging service and presentation
        self.logManager = None
        self.logPage = None

        # Protected storage access
        self._userActivatedItemIndex = None
        self._userServers = None
        self._userSubs = None
        self._userTUNSettings = None

        # ThreadPool
        self.threadPool = QtCore.QThreadPool()
        self.threadPool.setMaxThreadCount(max(OS_CPU_COUNT // 2, 1))

    @callRateLimited(maxCallPerSecond=2)
    @QtCore.Slot()
    def handleNewConnection(self):
        """Handle new connection."""
        socket = self.server.nextPendingConnection()
        socket.readyRead.connect(functools.partial(self.handleNewData, socket))

    @QtCore.Slot(QLocalSocket)
    def handleNewData(self, socket: QLocalSocket):
        """Handle new data."""
        data = socket.readAll().data()

        if isinstance(data, bytes):
            datastr = data.decode('utf-8', 'replace')
        else:
            datastr = str(data)

        if datastr == AppBuiltinCommand.Empty.value:
            if isinstance(self.systemTray, TrayIcon):
                logger.info('attempting to start multiple instance. Show tray message')

                self.systemTray.showMessage(_('Already started'))
            else:
                # The tray hasn't been initialized. Do nothing
                pass
        elif datastr == AppBuiltinCommand.RunAs.value:
            logger.info('detected requests to start as admin in new instance. Exiting')

            self.exit()
        else:
            # TODO: Not implemented
            pass

    def configureLogging(self):
        """Configure logging."""
        self.logManager = LogManager(parent=self)

        self.logPage = LogPage(
            manager=self.logManager,
            fontFamily=self.customFontName,
        )

        logging.basicConfig(
            format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            level=logging.INFO,
            handlers=(
                ApplicationLogHandler(self.logManager),
                logging.StreamHandler(),
            ),
        )
        logging.raiseExceptions = False

    def addCustomFont(self):
        """Add custom font."""
        fontFile = str(DATA_DIR / 'font' / 'CascadiaMono')
        fontName = 'Cascadia Mono'

        if QFontDatabase.addApplicationFont(fontFile) != -1:
            # Delayed
            self.customFontLoadMsg = f'custom font {fontName} load success'
            self.customFontEnabled = True
            self.customFontName = fontName
        else:
            # Delayed
            self.customFontLoadMsg = f'custom font {fontName} load failed'

    def configureApplicationFont(self):
        """Configure application font."""
        font = self.font()
        font.setPointSize(AppStyleSheet.FontPointSize)

        self.setFont(font)

    @staticmethod
    def addEnviron():
        """Add environ."""
        pluginRegistry = initializePluginRegistry(
            (*OFFICIAL_PLUGIN_TYPES, *BUNDLED_EXTENSION_TYPES)
        )
        configureEditorLogMetadata(
            lambda: (*pluginRegistry.coreVersions(), Tun2socks.version()),
            pluginRegistry.logTimestampPatterns,
        )
        pluginRegistry.configureEnvironment()

        if SystemRuntime.flatpakID():
            # https://github.com/flatpak/flatpak/issues/3438
            os.environ['TMPDIR'] = os.path.join(
                os.environ.get('XDG_RUNTIME_DIR'), 'app', APPLICATION_FLATPAK_ID
            )

    def addStorage(self):
        # Protected storage access
        """Add storage."""
        self._userActivatedItemIndex = Storage.UserActivatedItemIndex()
        self._userServers = Storage.UserServers()
        self._userSubs = Storage.UserSubs()
        self._userTUNSettings = Storage.UserTUNSettings()

    def isDarkMode(self):
        """Return whether dark mode."""
        backgroudColor = self.palette().color(QPalette.ColorRole.Window)

        return backgroudColor.lightness() < 128

    def systemTheme(self) -> str:
        """Return the system theme value used by the application."""
        try:
            theme = darkdetect.theme()

            if theme in [AppStyleSheet.Dark, AppStyleSheet.Light]:
                return theme
        except Exception:
            # Any non-exit exceptions

            logger.error('darkdetect.theme() is not implemented on this platform')

        return AppStyleSheet.Dark if self.isDarkMode() else AppStyleSheet.Light

    def isDarkModeEnabled(self):
        # if SystemRuntime.flatpakID():
        #     return self.isDarkMode()
        #
        # if not SystemRuntime.isAdmin():
        #     return AppSettings.isStateON_('DarkMode')
        # else:
        #     return self.isDarkMode()

        """Return whether dark mode enabled."""
        return AppSettings.isStateON_('DarkMode')

    def theme(self):
        """Return the theme value used by the application."""
        if self.isDarkModeEnabled():
            return AppStyleSheet.Dark

        return self.systemTheme()

    def applyStyleSheetForTheme(self, theme):
        """Handle apply style sheet for theme for the application."""
        self.setStyleSheet(AppStyleSheet.forTheme(theme))

    def switchToDarkMode(self):
        """Handle switch to dark mode for the application."""
        self.applyStyleSheetForTheme(AppStyleSheet.Dark)

        Mixins.ThemeAware.callThemeChangedCallbackUnchecked(AppStyleSheet.Dark)

    def switchToAutoMode(self):
        """Handle switch to auto mode for the application."""
        theme = self.systemTheme()

        self.applyStyleSheetForTheme(theme)

        Mixins.ThemeAware.callThemeChangedCallbackUnchecked(theme)

    @QtCore.Slot(str)
    def handleSystemThemeChanged(self, theme):
        """Handle system theme changed."""
        if theme not in [AppStyleSheet.Dark, AppStyleSheet.Light]:
            theme = self.systemTheme()

        if not self.isDarkModeEnabled():
            self.applyStyleSheetForTheme(theme)

        Mixins.ThemeAware.callThemeChangedCallback(theme)

    @staticmethod
    @callOnceOnly
    @QtCore.Slot()
    def cleanup():
        """Release resources owned by the application."""
        controller = AppConnectionController()

        if controller is not None:
            controller.shutdown()

        getPluginRegistry().shutdown()
        Mixins.CleanupOnExit.cleanupAll()

        if AppSettings.get('SystemProxyMode') == AppBuiltinProxyMode.Auto.value:
            # Automatically configure
            SystemProxy.off()
            SystemProxy.daemonOff()

        AppThreadPool().clear()

        logger.info('final cleanup done')

    @staticmethod
    def setDockIconVisible(visible: bool):
        """Set dock icon visible."""
        if PLATFORM != 'Darwin':
            return

        from AppKit import NSApplication

        policy = 0 if visible else 1
        NSApplication.sharedApplication().setActivationPolicy_(policy)

    def eventFilter(self, watched, event):
        # Show Dock icon on macOS when window is shown
        # and hide only when window is closed (not minimized)
        """Return the event filter value used by the application."""
        if PLATFORM == 'Darwin' and watched is self.mainWindow:
            if event.type() == QtCore.QEvent.Type.Show:
                self.setDockIconVisible(True)
            if event.type() == QtCore.QEvent.Type.Hide:
                # Hide Dock icon when window is closed (not minimized)
                if not self.mainWindow.isMinimized():
                    self.setDockIconVisible(False)

        return super().eventFilter(watched, event)

    def installDockIconVisibilityFeature(self, remove=False):
        """Handle install dock icon visibility feature for the application."""
        if remove:
            self.mainWindow.removeEventFilter(self)
            self.setDockIconVisible(True)
        else:
            # Install event filter for main window to track show/hide
            self.mainWindow.installEventFilter(self)

            if not self.mainWindow.isVisible() and not self.mainWindow.isMinimized():
                self.setDockIconVisible(False)

    def exit(self, exitcode=0):
        """Shut down and exit the application."""
        self.setExitingFlag(True)

        self.threadPool.clear()

        # Dirty exit
        for timeout in [1000, 2000, 3000]:
            QtCore.QTimer.singleShot(timeout, APP().exit)

        super().exit(exitcode)

    def run(self):
        """Run the application task."""
        try:
            if self.hasRunningApp():
                # See: https://github.com/python/cpython/issues/79908
                # sys.exit(None) in multiprocessing will produce
                # exitcode 1 in some Python version, which is
                # not what we want.
                return ApplicationRunner.ExitCode.ExitSuccess.value

            if not TrayIcon.isSystemTrayAvailable():
                raise SystemTrayUnavailable(
                    'TrayIcon is not available on this platform'
                )

            self.addEnviron()
            self.addStorage()

            # The application owns these lifetime-scoped services; Frozenlib
            # exposes them through App*Controller accessors.
            (
                self.connectionController,
                self.routingController,
                self.settingsController,
            ) = (
                ConnectionController(parent=self),
                RoutingController(parent=self),
                SettingsController(),
            )

            self.connectionController.interactionEnabledChanged.connect(
                self.routingController.setInteractionEnabled
            )

            self.addCustomFont()
            # self.configureApplicationFont()
            self.configureLogging()

            logger.info(f'application version: {APPLICATION_VERSION}')
            logger.info(
                f'Qt version: {QtCore.qVersion()}. PySide6 version: {PYSIDE6_VERSION}'
            )
            logger.info(f'Qt build info: {QtCore.QLibraryInfo.build()}')
            logger.info(f'platform: {PLATFORM}')
            logger.info(f'platform release: {PLATFORM_RELEASE}')
            logger.info(f'platform machine: {PLATFORM_MACHINE}')

            if PLATFORM == 'Darwin':
                logger.info(f'mac_ver: {platform.mac_ver()}')

            appImagePath = SystemRuntime.appImagePath()

            if appImagePath:
                logger.info(f'running from Linux AppImage: \'{appImagePath}\'')
            else:
                logger.info('not running from Linux AppImage')

            flatpakId = SystemRuntime.flatpakID()

            if flatpakId:
                logger.info(f'running from Linux flatpak: \'{flatpakId}\'')
            else:
                logger.info('not running from Linux flatpak')

            logger.info(f'python version: {PLATFORM_PYTHON_VERSION}')
            logger.info(f'system version: {sys.version}')
            logger.info(f'sys.executable: \'{sys.executable}\'')
            logger.info(f'sys.argv: {sys.argv}')
            logger.info(f'appFilePath: \'{self.applicationFilePath()}\'')
            logger.info(f'isPythonw: {SystemRuntime.isPythonw()}')
            logger.info(f'system language is {SYSTEM_LANGUAGE}')
            logger.info(self.customFontLoadMsg)
            logger.info(f'current theme is {self.theme()}')

            if PLATFORM != 'Windows' and not SystemRuntime.isScriptMode():
                logger.info('theme detect method uses timer implementation')

                @QtCore.Slot()
                def handleTimeout():
                    """Handle timeout."""
                    currentTheme = self.systemTheme()

                    if self.currentTheme != currentTheme:
                        self.currentTheme = currentTheme

                        self.handleSystemThemeChanged(currentTheme)

                self.currentTheme = self.systemTheme()
                self.themeDetectTimer = QtCore.QTimer()
                self.themeDetectTimer.timeout.connect(handleTimeout)
                self.themeDetectTimer.start(1000)
            else:
                logger.info('theme detect method uses listener implementation')

                def listener(*args, **kwargs):
                    """Handle listener for the application."""
                    try:
                        darkdetect.listener(*args, **kwargs)
                    except NotImplementedError:
                        # Not supported by darkdetect. Ignore

                        logger.error(
                            'darkdetect listener is not implemented on this platform'
                        )

                self.themeDetector = ApplicationThemeDetector()
                self.themeDetector.themeChanged.connect(self.handleSystemThemeChanged)

                self.themeListenerThread = threading.Thread(
                    target=listener,
                    args=(self.themeDetector.themeChanged.emit,),
                    daemon=True,
                )
                self.themeListenerThread.start()

            # Mandatory
            self.setQuitOnLastWindowClosed(False)

            self.aboutToQuit.connect(DesktopApplication.cleanup)

            Win32Session.set(DesktopApplication.cleanup)
            Win32Session.run()

            if AppSettings.get('SystemProxyMode') == AppBuiltinProxyMode.Auto.value:
                # Automatically configure
                SystemProxy.off()
                SystemProxy.daemonOn_()

            self.mainWindow = MainWindow()
            self.systemTray = TrayIcon()

            if PLATFORM == 'Darwin':
                if AppSettings.isStateON_('HideDockIcon'):
                    # Hide Dock icon initially, keeping only the tray icon visible
                    self.installDockIconVisibilityFeature()

                def onApplicationStateChange(state):
                    """Handle on application state change for the application."""
                    if state == QtCore.Qt.ApplicationState.ApplicationActive:
                        if (
                            not self.mainWindow.isVisible()
                            and not AppConnectionController().isConnecting()
                        ):
                            self.mainWindow.show()

                # Ensure the main window is shown when the dock icon is clicked
                self.applicationStateChanged.connect(onApplicationStateChange)

            if AppSettings.isStateON_('DarkMode'):
                self.switchToDarkMode()
            else:
                self.switchToAutoMode()

            self.systemTray.show()
            self.systemTray.setCustomToolTip()
            self.systemTray.bootstrap()

            AppConnectionController().restoreStartupState()

            return self.exec()
        except SystemTrayUnavailable:
            return ApplicationRunner.ExitCode.PlatformNotSupported.value
        except Exception:
            # Any non-exit exceptions

            traceback.print_exc()

            return ApplicationRunner.ExitCode.UnknownException.value
