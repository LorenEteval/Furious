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

from Furious.Interface import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Storage import *
from Furious.Widget.SystemTrayIcon import *
from Furious.Window.AppMainWindow import *
from Furious.Window.LogViewerWindow import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtNetwork import *
from PySide6.QtWidgets import *

import os
import sys
import time
import logging
import platform
import threading
import traceback
import functools
import qdarkstyle
import darkdetect

logger = logging.getLogger(__name__)

registerAppSettings('AppLogViewerWidgetPointSize')
registerAppSettings('CoreLogViewerWidgetPointSize')
registerAppSettings('TunLogViewerWidgetPointSize')


def rateLimited(maxCallPerSecond):
    """
    Decorator function that limits the rate at which a function can be called.
    """
    interval = 1.0 / float(maxCallPerSecond)
    called = time.monotonic()

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Previously called
            nonlocal called

            elapsed = time.monotonic() - called
            waitsec = interval - elapsed

            if waitsec > 0:
                time.sleep(waitsec)

            result = func(*args, **kwargs)
            called = time.monotonic()

            return result

        return wrapper

    return decorator


class SystemTrayUnavailable(Exception):
    pass


class AppLogHandler(logging.Handler):
    def __init__(self, emitCallback):
        super().__init__()

        self.emitCallback = emitCallback

    def emit(self, record):
        if callable(self.emitCallback):
            self.emitCallback(self.format(record))


class ApplicationExitHelper(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        # Exiting flag
        self._exiting = False

    def setExitingFlag(self, value: bool):
        self._exiting = value

    def isExiting(self) -> bool:
        return self._exiting is True


class SingletonApplication(ApplicationExitHelper):
    def __init__(self, argv):
        super().__init__(argv)

        self.serverName = LOCAL_SERVER_NAME

        self.socket = QLocalSocket(self)
        self.server = QLocalServer(self)

    def hasRunningApp(self) -> bool:
        self.socket.connectToServer(self.serverName)

        if self.socket.waitForConnected(1000):
            # Show tray message in the started instance
            self.socket.close()

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
            self.server.newConnection.connect(self.showExistingApp)

            if not self.server.listen(self.serverName):
                # Do not start
                logger.error(f'unable to listen on server: {self.serverName}')

                return True

            # Start
            return False

    @QtCore.Slot()
    def showExistingApp(self):
        raise NotImplementedError


class ApplicationThemeDetector(QtCore.QObject):
    themeChanged = QtCore.Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Application(ApplicationFactory, SingletonApplication):
    def __init__(self, argv):
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

        # Initialize storage
        self.userServers = UserServers()
        self.userSubs = UserSubs()
        self.userTUNSettings = UserTUNSettings()

        self.mainWindow = None
        self.systemTray = None

        # ThreadPool
        self.threadPool = QtCore.QThreadPool()
        self.threadPool.setMaxThreadCount(max(OS_CPU_COUNT // 2, 1))

    @rateLimited(maxCallPerSecond=2)
    @QtCore.Slot()
    def showExistingApp(self):
        if isinstance(self.systemTray, SystemTrayIcon):
            logger.info('attempting to start multiple instance. Show tray message')

            self.systemTray.showMessage(_('Already started'))
        else:
            # The tray hasn't been initialized. Do nothing
            pass

    def configureLogging(self):
        self.logViewerWindowApp_ = LogViewerWindow(
            tabTitle=_('Furious Log'),
            fontFamily=self.customFontName,
            pointSizeSettingsName='AppLogViewerWidgetPointSize',
        )
        self.logViewerWindowCore = LogViewerWindow(
            tabTitle=_('Core Log'),
            fontFamily=self.customFontName,
            pointSizeSettingsName='CoreLogViewerWidgetPointSize',
        )
        self.logViewerWindowTun_ = LogViewerWindow(
            tabTitle=_('Tun2socks Log'),
            fontFamily=self.customFontName,
            pointSizeSettingsName='TunLogViewerWidgetPointSize',
        )

        logging.basicConfig(
            format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            level=logging.INFO,
            handlers=(
                AppLogHandler(
                    lambda record: self.logViewerWindowApp_.appendLine(record)
                ),
                logging.StreamHandler(),
            ),
        )
        logging.raiseExceptions = False

    def log(self):
        return self.logViewerWindowApp_.plainText()

    def addCustomFont(self):
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

    @staticmethod
    def addEnviron():
        # Xray environment variables
        os.environ['XRAY_LOCATION_ASSET'] = str(XRAY_ASSET_DIR)

    def isSystemTrayConnected(self):
        if isinstance(self.systemTray, SystemTrayIcon):
            return self.systemTray.ConnectAction.isConnected()
        else:
            return False

    def isDarkMode(self):
        backgroudColor = self.palette().color(QPalette.ColorRole.Window)

        return backgroudColor.lightness() < 128

    @staticmethod
    def isDarkModeEnabled():
        return AppSettings.isStateON_('DarkMode')

    def switchToDarkMode(self):
        self.setStyleSheet(qdarkstyle.load_stylesheet_pyside6())

        SupportThemeChangedCallback.callThemeChangedCallbackUnchecked('Dark')

    def switchToAutoMode(self):
        self.setStyleSheet('')

        SupportThemeChangedCallback.callThemeChangedCallbackUnchecked(
            darkdetect.theme()
        )

    @staticmethod
    @callOnceOnly
    @QtCore.Slot()
    def cleanup():
        SupportExitCleanup.cleanupAll()

        if AppSettings.get('SystemProxyMode') == 'Auto':
            # Automatically configure
            SystemProxy.off()
            SystemProxy.daemonOff()

        if PLATFORM == 'Darwin':
            AppThreadPool().clear()

            for timeout in [1000, 2000, 3000]:
                QtCore.QTimer.singleShot(timeout, APP().exit)

        logger.info('final cleanup done')

    @staticmethod
    def setDockIconVisible(visible: bool):
        if PLATFORM != 'Darwin':
            return

        from AppKit import NSApplication

        policy = 0 if visible else 1
        NSApplication.sharedApplication().setActivationPolicy_(policy)

    def eventFilter(self, watched, event):
        # Show Dock icon on macOS when window is shown
        # and hide only when window is closed (not minimized)
        if PLATFORM == 'Darwin' and watched is self.mainWindow:
            if event.type() == QtCore.QEvent.Type.Show:
                self.setDockIconVisible(True)
            if event.type() == QtCore.QEvent.Type.Hide:
                # Hide Dock icon when window is closed (not minimized)
                if not self.mainWindow.isMinimized():
                    self.setDockIconVisible(False)

        return super().eventFilter(watched, event)

    def installDockIconVisibilityFeature(self, remove=False):
        if remove:
            self.mainWindow.removeEventFilter(self)
            self.setDockIconVisible(True)
        else:
            # Install event filter for main window to track show/hide
            self.mainWindow.installEventFilter(self)

            if not self.mainWindow.isVisible() and not self.mainWindow.isMinimized():
                self.setDockIconVisible(False)

    def exit(self, exitcode=0):
        self.setExitingFlag(True)

        self.threadPool.clear()

        super().exit(exitcode)

    def run(self):
        try:
            if self.hasRunningApp():
                # See: https://github.com/python/cpython/issues/79908
                # sys.exit(None) in multiprocessing will produce
                # exitcode 1 in some Python version, which is
                # not what we want.
                return ApplicationFactory.ExitCode.ExitSuccess

            if not SystemTrayIcon.isSystemTrayAvailable():
                raise SystemTrayUnavailable(
                    'SystemTrayIcon is not available on this platform'
                )

            self.addEnviron()
            self.addCustomFont()
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

            appImagePath = getAppImagePath()

            if appImagePath:
                logger.info(f'running from Linux AppImage: \'{appImagePath}\'')
            else:
                logger.info('not running from Linux AppImage')

            logger.info(f'python version: {getPythonVersion()}')
            logger.info(f'system version: {sys.version}')
            logger.info(f'sys.executable: \'{sys.executable}\'')
            logger.info(f'sys.argv: {sys.argv}')
            logger.info(f'appFilePath: \'{self.applicationFilePath()}\'')
            logger.info(f'isPythonw: {isPythonw()}')
            logger.info(f'system language is {SYSTEM_LANGUAGE}')
            logger.info(self.customFontLoadMsg)
            logger.info(f'current theme is {darkdetect.theme()}')

            if PLATFORM != 'Windows' and not isScriptMode():
                logger.info('theme detect method uses timer implementation')

                @QtCore.Slot()
                def handleTimeout():
                    currentTheme = darkdetect.theme()

                    if self.currentTheme != currentTheme:
                        self.currentTheme = currentTheme

                        SupportThemeChangedCallback.callThemeChangedCallback(
                            currentTheme
                        )

                self.currentTheme = darkdetect.theme()
                self.themeDetectTimer = QtCore.QTimer()
                self.themeDetectTimer.timeout.connect(handleTimeout)
                self.themeDetectTimer.start(1000)
            else:
                logger.info('theme detect method uses listener implementation')

                def listener(*args, **kwargs):
                    try:
                        darkdetect.listener(*args, **kwargs)
                    except NotImplementedError:
                        # Not supported by darkdetect. Ignore

                        logger.error(
                            'darkdetect listener is not implemented on this platform'
                        )

                self.themeDetector = ApplicationThemeDetector()
                self.themeDetector.themeChanged.connect(
                    SupportThemeChangedCallback.callThemeChangedCallback
                )

                self.themeListenerThread = threading.Thread(
                    target=listener,
                    args=(self.themeDetector.themeChanged.emit,),
                    daemon=True,
                )
                self.themeListenerThread.start()

            # Mandatory
            self.setQuitOnLastWindowClosed(False)

            self.aboutToQuit.connect(Application.cleanup)

            Win32Session.set(Application.cleanup)
            Win32Session.run()

            if AppSettings.get('SystemProxyMode') == 'Auto':
                # Automatically configure
                SystemProxy.off()
                SystemProxy.daemonOn_()

            self.mainWindow = AppMainWindow()
            self.systemTray = SystemTrayIcon()

            if PLATFORM == 'Darwin':
                if AppSettings.isStateON_('HideDockIcon'):
                    # Hide Dock icon initially, keeping only the tray icon visible
                    self.installDockIconVisibilityFeature()

                def onApplicationStateChange(state):
                    if state == QtCore.Qt.ApplicationState.ApplicationActive:
                        if (
                            not self.mainWindow.isVisible()
                            and not self.systemTray.ConnectAction.isConnecting()
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

            return self.exec()
        except SystemTrayUnavailable:
            return ApplicationFactory.ExitCode.PlatformNotSupported
        except Exception:
            # Any non-exit exceptions

            traceback.print_exc()

            return ApplicationFactory.ExitCode.UnknownException
