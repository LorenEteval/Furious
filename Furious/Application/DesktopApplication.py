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

from Furious.Frozenlib import (
    APPLICATION_FLATPAK_ID,
    APPLICATION_NAME,
    APPLICATION_VERSION,
    DATA_DIR,
    LOCAL_SERVER_NAME,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
    OS_CPU_COUNT,
    PLATFORM,
    PLATFORM_MACHINE,
    PLATFORM_PYTHON_VERSION,
    PLATFORM_RELEASE,
    PYSIDE6_VERSION,
    SYSTEM_LANGUAGE,
    AppBuiltinCommand,
    AppBuiltinProxyMode,
    AppConnectionController,
    AppSettings,
    ApplicationTheme,
    Mixins,
    SystemProxy,
    SystemRuntime,
    Win32Session,
    callRateLimited,
)
from Furious.Interface import ApplicationRunner
from Furious.Core import Tun2socks
from Furious.Backends import OFFICIAL_PLUGIN_TYPES
from Furious.Controllers import (
    APPLICATION_THEME_SETTING,
    LOG_AUTO_CLEAR_SETTING,
    ConnectionController,
    RoutingController,
    SettingsController,
)
from Furious.Extensions import BUNDLED_EXTENSION_TYPES
from Furious.Plugins import initializePluginRegistry
from Furious.Qt import AppStyleSheet
from Furious.Qt.TextEditorTheme import configureEditorLogMetadata
from Furious.Qt import gettext as _
from Furious.Repository import Storage
from Furious.Service import ApplicationLogHandler, LogManager
from Furious.Application.TrayIcon import TrayIcon
from Furious.Window.LogPage import LogPage
from Furious.Window.MainWindow import MainWindow

from PySide6 import QtCore
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

import os
import sys
import logging
import platform
import traceback
import darkdetect

logger = logging.getLogger(__name__)


class _ApplicationCleanupStack:
    """Run acquired application-resource cleanup in reverse order exactly once."""

    def __init__(self):
        self._callbacks = []
        self._closed = False

    def register(self, stage: str, callback):
        """Record cleanup after *stage* has completed successfully."""
        if self._closed:
            raise RuntimeError('application cleanup has already completed')

        self._callbacks.append((stage, callback))

    def close(self):
        """Release every acquired stage in reverse order, continuing on errors."""
        if self._closed:
            return False

        self._closed = True

        while self._callbacks:
            stage, callback = self._callbacks.pop()

            try:
                callback()
            except Exception:
                # Any non-exit exceptions

                logger.exception(f'application cleanup failed for stage {stage}')

        return True


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

    def shouldExitForExistingInstance(self) -> bool:
        """Claim the single-instance endpoint or notify the running instance."""
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


class DesktopApplication(ApplicationRunner, SingletonApplication):
    """Represent application."""

    _sessionShutdownRequested = QtCore.Signal()
    ThreadPoolShutdownTimeout = 5000

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
        self.threadPool = QtCore.QThreadPool(self)
        self.threadPool.setMaxThreadCount(max(OS_CPU_COUNT // 2, 1))

        self._cleanupStack = _ApplicationCleanupStack()
        self._cleanupStack.register('thread pool', self._cleanupThreadPool)

        self._exitRequested = False
        self._exitCode = ApplicationRunner.ExitCode.ExitSuccess.value

        # win32session invokes its callback on the native listener thread.
        # Queue the request so every Qt-owned cleanup stage stays on the GUI thread.
        self._sessionShutdownRequested.connect(
            self.exit,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

    @callRateLimited(maxCallPerSecond=2)
    @QtCore.Slot()
    def handleNewConnection(self):
        """Handle new connection."""
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()

            if socket is None:
                continue

            # QLocalServer owns pending sockets until they are explicitly
            # released.  Use sender() instead of a partial that retains each
            # socket and dispose it after the one-command protocol completes.
            socket.readyRead.connect(self.handleNewData)
            socket.disconnected.connect(socket.deleteLater)

    @QtCore.Slot()
    def handleNewData(self):
        """Handle new data."""
        socket = self.sender()

        if not isinstance(socket, QLocalSocket):
            return

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

        # The singleton IPC channel carries exactly one command.  Closing it
        # here both wakes RunAs clients and prevents completed QLocalSocket
        # children from accumulating under the application-wide server.
        socket.disconnectFromServer()

        if socket.state() == QLocalSocket.LocalSocketState.UnconnectedState:
            socket.deleteLater()

    def configureLogging(self):
        """Configure logging."""
        self.logManager = LogManager(
            parent=self,
            autoClearEnabled=AppSettings.isStateON_(LOG_AUTO_CLEAR_SETTING),
        )

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

        try:
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
        except Exception:
            # Any non-exit exceptions

            pluginRegistry.shutdown()

            raise

        return pluginRegistry

    def addStorage(self):
        # Protected storage access
        """Add storage."""
        self._userActivatedItemIndex = Storage.UserActivatedItemIndex()
        self._userServers = Storage.UserServers()
        self._userSubs = Storage.UserSubs()
        self._userTUNSettings = Storage.UserTUNSettings()

    def _initializeControllers(self):
        """Create the process-lifetime application state authorities."""
        try:
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
        except Exception:
            # Any non-exit exceptions

            self._cleanupControllers()

            raise

    def _cleanupControllers(self):
        """Shut down and release each controller acquired during startup."""
        if self.connectionController is not None:
            try:
                self.connectionController.shutdown()
            except Exception:
                # Any non-exit exceptions

                logger.exception('connection controller shutdown failed')

        for controllerName in ('routingController', 'connectionController'):
            controller = getattr(self, controllerName)

            if isinstance(controller, QtCore.QObject):
                controller.deleteLater()

            setattr(self, controllerName, None)

        self.settingsController = None

    def _initializeThemeDetection(self):
        """Start the one application-owned theme observer."""
        logger.info('theme detect method uses timer implementation')

        @QtCore.Slot()
        def handleTimeout():
            """Apply a changed system theme."""
            currentTheme = self.systemTheme()

            if self.currentTheme != currentTheme:
                self.currentTheme = currentTheme
                self.handleSystemThemeChanged(currentTheme)

        self.currentTheme = self.systemTheme()
        self.themeDetectTimer = QtCore.QTimer(self)
        self.themeDetectTimer.timeout.connect(handleTimeout)
        self.themeDetectTimer.start(1000)

    def _stopThemeDetection(self):
        """Stop Qt-owned theme polling during rollback or final cleanup."""
        if isinstance(self.themeDetectTimer, QtCore.QTimer):
            self.themeDetectTimer.stop()

    def _cleanupThreadPool(self):
        """Cancel queued work and boundedly finish already-running Qt work."""
        self.threadPool.clear()

        if not self.threadPool.waitForDone(self.ThreadPoolShutdownTimeout):
            logger.error('application thread pool did not stop before timeout')

    def _initializeSystemIntegration(self):
        """Install operating-system session and automatic proxy integration."""
        self.setQuitOnLastWindowClosed(False)

        if Win32Session.set(self._sessionShutdownRequested.emit):
            self._cleanupStack.register('Windows session listener', Win32Session.off)

            if not Win32Session.run():
                logger.error('failed to start Windows session listener')

        if AppSettings.get('SystemProxyMode') == AppBuiltinProxyMode.Auto.value:
            SystemProxy.off()

            # sysproxy's change-notification daemon is a Windows-only resource.
            # ConnectionController owns the configured OS proxy and turns it
            # off during disconnection/shutdown on every platform.
            if PLATFORM == 'Windows':
                SystemProxy.daemonOn_()

                self._cleanupStack.register(
                    'Windows system proxy daemon', SystemProxy.daemonOff
                )

    def _initializeUI(self):
        """Create and bootstrap the application-owned main window and tray."""
        try:
            self.applyThemePreference()
            self.mainWindow = MainWindow()
            self.systemTray = TrayIcon(parent=self)

            if PLATFORM == 'Darwin':
                if AppSettings.isStateON_('HideDockIcon'):
                    self.installDockIconVisibilityFeature()

                def onApplicationStateChange(state):
                    """Show the main window when the macOS dock activates the app."""
                    if QtCore.Qt.ApplicationState(state) != (
                        QtCore.Qt.ApplicationState.ApplicationActive
                    ):
                        return

                    controller = AppConnectionController()

                    if (
                        not self.mainWindow.isVisible()
                        and controller is not None
                        and not controller.isConnecting()
                    ):
                        self.mainWindow.show()

                self.applicationStateChanged.connect(onApplicationStateChange)

            self.systemTray.show()
            self.systemTray.setCustomToolTip()
            self.systemTray.bootstrap()
        except Exception:
            # Any non-exit exceptions

            self._cleanupUI()

            raise

    def _cleanupUI(self):
        """Hide and release application-owned top-level UI objects."""
        if self.systemTray is not None:
            self.systemTray.hide()
            self.systemTray.deleteLater()
            self.systemTray = None

        if self.mainWindow is not None:
            self.mainWindow.hide()
            self.mainWindow.deleteLater()
            self.mainWindow = None

    def _logRuntimeInformation(self):
        """Log the initialized runtime environment without acquiring resources."""
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
            logger.info(f'running from Linux AppImage: {appImagePath}')
        else:
            logger.info(f'not running from Linux AppImage')

        flatpakId = SystemRuntime.flatpakID()

        if flatpakId:
            logger.info(f'running from Linux flatpak: {flatpakId}')
        else:
            logger.info(f'not running from Linux flatpak')

        logger.info(f'python version: {PLATFORM_PYTHON_VERSION}')
        logger.info(f'system version: {sys.version}')
        logger.info(f'sys.executable: {sys.executable}')
        logger.info(f'sys.argv: {sys.argv}')
        logger.info(f'appFilePath: {self.applicationFilePath()}')
        logger.info(f'isPythonw: {SystemRuntime.isPythonw()}')
        logger.info(f'system language is {SYSTEM_LANGUAGE}')
        logger.info(self.customFontLoadMsg)
        logger.info(f'current theme is {self.theme()}')

    def isSystemDarkMode(self):
        """Return whether the current system palette appears dark."""
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

        return AppStyleSheet.Dark if self.isSystemDarkMode() else AppStyleSheet.Light

    def themePreference(self) -> ApplicationTheme:
        """Return the authoritative persisted application theme preference."""
        return ApplicationTheme(AppSettings.get(APPLICATION_THEME_SETTING))

    def followsSystemAppearance(self) -> bool:
        """Return whether system appearance controls the application theme."""
        return self.themePreference() == ApplicationTheme.System

    def usesForcedDarkTheme(self) -> bool:
        """Return whether the application explicitly forces its dark theme."""
        return self.themePreference() == ApplicationTheme.Dark

    def theme(self):
        """Resolve the effective light or dark application theme."""
        preference = self.themePreference()

        if preference != ApplicationTheme.System:
            return preference.value

        return self.systemTheme()

    def applyStyleSheetForTheme(self, theme):
        """Handle apply style sheet for theme for the application."""
        self.setStyleSheet(AppStyleSheet.forTheme(theme))

    def applyThemePreference(self):
        """Apply the resolved preference and refresh every theme-aware object."""
        theme = self.theme()

        self.applyStyleSheetForTheme(theme)

        Mixins.ThemeAware.callThemeChangedCallbackUnchecked(theme)

    @QtCore.Slot(str)
    def handleSystemThemeChanged(self, theme):
        """Handle system theme changed."""
        if not self.followsSystemAppearance():
            logger.info(
                f'ignore system theme \'{theme}\' change while application theme '
                f'is forced to \'{self.themePreference().value}\''
            )

            return

        if theme not in [AppStyleSheet.Dark, AppStyleSheet.Light]:
            theme = self.systemTheme()

        self.applyStyleSheetForTheme(theme)

        Mixins.ThemeAware.callThemeChangedCallback(theme)

    @QtCore.Slot()
    def cleanup(self):
        """Release every successfully acquired application stage exactly once."""
        if self._cleanupStack.close():
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
        """Request normal event-loop termination; ``aboutToQuit`` owns cleanup."""
        if self._exitRequested:
            return

        self._exitRequested = True
        self._exitCode = int(exitcode)
        self.setExitingFlag(True)

        QtCore.QCoreApplication.exit(self._exitCode)

    def run(self):
        """Run the application task."""
        try:
            if self.shouldExitForExistingInstance():
                # See: https://github.com/python/cpython/issues/79908
                # sys.exit(None) in multiprocessing will produce
                # exitcode 1 in some Python version, which is
                # not what we want.
                return ApplicationRunner.ExitCode.ExitSuccess.value

            if not TrayIcon.isSystemTrayAvailable():
                raise SystemTrayUnavailable(
                    'TrayIcon is not available on this platform'
                )

            pluginRegistry = self.addEnviron()

            self._cleanupStack.register('plugins', pluginRegistry.shutdown)

            try:
                self.addStorage()
            except Exception:
                Mixins.CleanupOnExit.cleanupAll()

                raise

            self._cleanupStack.register(
                'mixin-owned resources', Mixins.CleanupOnExit.cleanupAll
            )
            self._initializeControllers()
            self._cleanupStack.register('controllers', self._cleanupControllers)

            self.addCustomFont()
            # self.configureApplicationFont()
            self.configureLogging()
            self._logRuntimeInformation()

            self._initializeThemeDetection()
            self._cleanupStack.register('theme detection', self._stopThemeDetection)

            self.aboutToQuit.connect(self.cleanup)
            self._initializeSystemIntegration()

            self._initializeUI()
            self._cleanupStack.register('application UI', self._cleanupUI)
            self.connectionController.restoreStartupState()

            if self._exitRequested:
                return self._exitCode

            return self.exec()
        except SystemTrayUnavailable:
            return ApplicationRunner.ExitCode.PlatformNotSupported.value
        except Exception:
            # Any non-exit exceptions

            traceback.print_exc()

            return ApplicationRunner.ExitCode.UnknownException.value
        finally:
            self.cleanup()
