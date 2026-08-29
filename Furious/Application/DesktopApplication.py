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
    PySide6Legacy,
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
from Furious.Qt import AppQMessageBox, AppStyleSheet, ThemeTransition
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
from enum import Enum

import darkdetect

logger = logging.getLogger(__name__)


class _ExistingInstanceResult(Enum):
    """Describe the result of forwarding this launch to a primary instance."""

    Unreachable = 'unreachable'
    CommandForwarded = 'command-forwarded'
    CommandDeliveryUncertain = 'command-delivery-uncertain'
    RunAsHandoffAccepted = 'run-as-handoff-accepted'


class _SingletonStartupResult(Enum):
    """Describe whether this process may continue full application startup."""

    Primary = 'primary'
    ExistingInstance = 'existing-instance'
    RecoveryRequired = 'recovery-required'
    OwnershipUnresolved = 'ownership-unresolved'


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

    ExistingInstanceConnectTimeout = 1000
    RunAsHandoffTimeout = 3000
    ExistingEndpointProbeTimeout = 250
    SingletonElectionLockTimeout = 3000
    SingletonElectionLockStaleTime = 30000

    def __init__(self, argv):
        """Initialize the SingletonApplication."""
        super().__init__(argv)

        self.serverName = LOCAL_SERVER_NAME

        self.socket = QLocalSocket(self)
        self.server = QLocalServer(self)

    def _notifyExistingInstance(self) -> _ExistingInstanceResult:
        """Forward this launch command or report that no primary responded."""
        self.socket.abort()
        self.socket.connectToServer(self.serverName)

        if not self.socket.waitForConnected(self.ExistingInstanceConnectTimeout):
            return _ExistingInstanceResult.Unreachable

        command = AppBuiltinCommand.Empty.value if len(sys.argv) == 1 else sys.argv[1]

        encodedCommand = command.encode()

        if self.socket.write(encodedCommand) == -1:
            # A successful connection still proves that another process owns
            # the endpoint.  Do not compete for ownership merely because the
            # one-command delivery failed while that process was disconnecting.
            logger.warning(
                f'unable to forward startup command to existing instance: '
                f'{self.socket.errorString()}'
            )

            return _ExistingInstanceResult.CommandDeliveryUncertain

        self.socket.flush()

        if command == AppBuiltinCommand.RunAs.value:
            # A successful disconnect means the old instance accepted the
            # command and started exiting.  A later listen() still decides
            # whether this replacement actually owns the endpoint.
            if self.socket.waitForDisconnected(self.RunAsHandoffTimeout):
                logger.info('existing instance accepted the RunAs handoff')

                return _ExistingInstanceResult.RunAsHandoffAccepted

            logger.warning(
                'existing instance did not complete the RunAs handoff before '
                'the deadline'
            )

            return _ExistingInstanceResult.CommandForwarded

        # Empty and currently unsupported commands are handled by the running
        # instance; this process must not create another application window.
        logger.info('startup command forwarded to the existing instance')

        return _ExistingInstanceResult.CommandForwarded

    def _listenAsPrimaryInstance(self) -> bool:
        """Listen as primary after the caller has serialized election."""
        if not self.server.listen(self.serverName):
            return False

        self.server.newConnection.connect(self.handleNewConnection)

        return True

    def _existingEndpointIsReachable(self) -> bool:
        """Probe endpoint ownership without forwarding this launch command."""
        self.socket.abort()
        self.socket.connectToServer(self.serverName)

        if not self.socket.waitForConnected(self.ExistingEndpointProbeTimeout):
            return False

        self.socket.disconnectFromServer()

        if self.socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
            self.socket.waitForDisconnected(self.ExistingEndpointProbeTimeout)

        return True

    def _waitForRunAsEndpointRelease(self) -> bool:
        """Wait until the primary that accepted RunAs stops owning the endpoint."""
        deadline = QtCore.QDeadlineTimer(self.RunAsHandoffTimeout)

        while not deadline.hasExpired():
            if not self._existingEndpointIsReachable():
                return True

            QtCore.QThread.msleep(50)

        return False

    def _singletonElectionLock(self):
        """Return the short-lived lock that serializes candidate election."""
        lock = QtCore.QLockFile(
            os.path.join(
                QtCore.QStandardPaths.writableLocation(
                    QtCore.QStandardPaths.StandardLocation.TempLocation
                ),
                f'{self.serverName}.lock',
            )
        )
        # Election is bounded to a few seconds.  The longer stale interval
        # prevents age-based recovery from stealing a live election transaction,
        # while QLockFile can still clean up a lock left by a crashed process.
        lock.setStaleLockTime(self.SingletonElectionLockStaleTime)

        return lock

    @staticmethod
    def _logElectionLockFailure(electionLock):
        """Log the specific reason singleton election cannot be serialized."""
        error = electionLock.error()

        if error == QtCore.QLockFile.LockError.LockFailedError:
            logger.info('singleton election is already owned by another launcher')
        elif error == QtCore.QLockFile.LockError.PermissionError:
            logger.error(
                f'permission denied creating singleton election lock: '
                f'{electionLock.fileName()}'
            )
        else:
            logger.error(
                f'unable to acquire singleton election lock '
                f'{electionLock.fileName()}: {error}'
            )

    def _electPrimaryUnderLock(
        self,
        initialProbe: _ExistingInstanceResult,
    ) -> _SingletonStartupResult:
        """Recheck competitors, then claim or classify the endpoint under lock."""
        if initialProbe is _ExistingInstanceResult.RunAsHandoffAccepted:
            if not self._waitForRunAsEndpointRelease():
                logger.error(
                    'existing instance accepted RunAs but did not release the '
                    'singleton endpoint before the handoff deadline'
                )

                return _SingletonStartupResult.OwnershipUnresolved
        elif self._existingEndpointIsReachable():
            # A launcher won while this process was waiting for the election
            # lock.  A connectivity-only probe avoids forwarding RunAs twice.
            logger.info('another launcher completed singleton election first')

            return _SingletonStartupResult.ExistingInstance

        # On Unix this is the authoritative ownership claim.  Qt explicitly
        # permits multiple same-name local servers on Windows, so the election
        # lock and preceding reachability barrier provide exclusivity there.
        if self._listenAsPrimaryInstance():
            logger.info(f'primary instance endpoint claimed: {self.serverName}')

            return _SingletonStartupResult.Primary

        # A non-cooperating process may have appeared despite serialization.
        # Recheck before treating a failed Unix listen as a stale socket file.
        if self._existingEndpointIsReachable():
            logger.info('singleton endpoint became reachable before recovery')

            return _SingletonStartupResult.ExistingInstance

        logger.info(
            f'primary endpoint claim failed; evaluating stale recovery: '
            f'{self.server.errorString()}'
        )

        return _SingletonStartupResult.RecoveryRequired

    def _recoverStaleEndpointAndClaim(self) -> _SingletonStartupResult:
        """Recover a confirmed stale endpoint while holding the election lock."""
        logger.info(f'attempting stale endpoint recovery: {self.serverName}')

        if QLocalServer.removeServer(self.serverName):
            logger.info(f'stale singleton endpoint removed: {self.serverName}')
        else:
            logger.warning(
                f'singleton endpoint could not be removed or was already absent: '
                f'{self.serverName}'
            )

        if self._listenAsPrimaryInstance():
            logger.info(
                f'primary instance endpoint claimed after recovery: '
                f'{self.serverName}'
            )

            return _SingletonStartupResult.Primary

        logger.error(
            f'unable to claim singleton endpoint {self.serverName} after '
            f'recovery: {self.server.errorString()}'
        )

        return _SingletonStartupResult.OwnershipUnresolved

    def shouldExitForExistingInstance(self) -> bool:
        """Claim the single-instance endpoint or notify the running instance."""
        initialProbe = self._notifyExistingInstance()

        if initialProbe in (
            _ExistingInstanceResult.CommandForwarded,
            _ExistingInstanceResult.CommandDeliveryUncertain,
        ):
            return True

        electionLock = self._singletonElectionLock()

        if not electionLock.tryLock(self.SingletonElectionLockTimeout):
            self._logElectionLockFailure(electionLock)

            return True

        try:
            result = self._electPrimaryUnderLock(initialProbe)

            if result is _SingletonStartupResult.RecoveryRequired:
                result = self._recoverStaleEndpointAndClaim()

            # Fail closed whenever endpoint ownership remains uncertain.
            return result is not _SingletonStartupResult.Primary
        finally:
            electionLock.unlock()

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
        self._appliedTheme = None
        self.themeTransition = ThemeTransition(parent=self)

        self.mainWindow = None
        self.systemTray = None

        self._loggingHandlers = tuple()
        self._loggingRootLevel = None
        self._loggingRaiseExceptions = logging.raiseExceptions

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

        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
        )

        rootLogger = logging.getLogger()

        self._loggingRootLevel = rootLogger.level
        self._loggingHandlers = (
            ApplicationLogHandler(self.logManager),
            logging.StreamHandler(),
        )

        rootLogger.setLevel(logging.INFO)

        for handler in self._loggingHandlers:
            handler.setFormatter(formatter)

            rootLogger.addHandler(handler)

        logging.raiseExceptions = False

        self._cleanupStack.register('logging', self._cleanupLogging)

    def _cleanupLogging(self):
        """Remove and close exactly the handlers owned by this application."""
        rootLogger = logging.getLogger()

        for handler in self._loggingHandlers:
            rootLogger.removeHandler(handler)

            handler.close()

        self._loggingHandlers = tuple()

        if self._loggingRootLevel is not None:
            rootLogger.setLevel(self._loggingRootLevel)

            self._loggingRootLevel = None

        logging.raiseExceptions = self._loggingRaiseExceptions

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
                SettingsController(parent=self),
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

        for controllerName in (
            'settingsController',
            'routingController',
            'connectionController',
        ):
            controller = getattr(self, controllerName)

            if isinstance(controller, QtCore.QObject):
                controller.deleteLater()

            setattr(self, controllerName, None)

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

    def _handleMainWindowCloseEvent(self, event):
        """Confirm a main-window close before Qt accepts the event."""
        assert self.systemTray is None

        mbox = AppQMessageBox(
            icon=AppQMessageBox.Icon.Question,
            parent=self.mainWindow,
            text=_('Are you sure you want to exit the application?'),
            buttons=(
                AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
            ),
        )
        mbox.setDefaultButton(AppQMessageBox.StandardButton.No)

        if mbox.exec() == PySide6Legacy.enumValueWrapper(
            AppQMessageBox.StandardButton.Yes
        ):
            self.exit()

            # Preserve normal close-event delivery so AppQMainWindow can
            # release its shown-window lifetime entry.
            return False
        else:
            event.ignore()

            return True

    def _initializeUI(self):
        """Create and bootstrap the application-owned main window and tray."""
        try:
            self.setQuitOnLastWindowClosed(False)
            self.applyThemePreference()

            self.mainWindow = MainWindow()
            self.mainWindow.installEventFilter(self)

            if TrayIcon.isSystemTrayAvailable():
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

            if self.systemTray is None:
                logger.warning(
                    'system tray unavailable; showing the main window instead'
                )

                self.mainWindow.show()
            else:
                self.systemTray.show()
                self.systemTray.setCustomToolTip()
                self.systemTray.bootstrap()
        except Exception:
            # Any non-exit exceptions

            self._cleanupUI()

            raise

    def _cleanupUI(self):
        """Hide and release application-owned top-level UI objects."""
        self.themeTransition.stop()

        if self.systemTray is not None:
            self.systemTray.hide()
            self.systemTray.deleteLater()
            self.systemTray = None

        if self.mainWindow is not None:
            self.mainWindow.removeEventFilter(self)
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
        # Arguments may contain imported share links, subscription URLs, or
        # plugin-defined commands.  Their contents are not diagnostic metadata.
        logger.info(f'command-line arguments: {max(len(sys.argv) - 1, 0)} provided')
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

    def _applyResolvedTheme(self, theme, notifyThemeAware):
        """Apply one effective theme through the centralized transition path."""
        theme = AppStyleSheet.normalizeTheme(theme)
        animate = self._appliedTheme is not None and self._appliedTheme != theme

        def applyTheme():
            """Commit the destination style and refresh all derived visuals."""
            self.applyStyleSheetForTheme(theme)
            self._appliedTheme = theme
            notifyThemeAware(theme)

        self.themeTransition.apply(applyTheme, animate=animate)

    def applyThemePreference(self):
        """Apply the resolved preference and refresh every theme-aware object."""
        theme = self.theme()

        self._applyResolvedTheme(
            theme,
            Mixins.ThemeAware.callThemeChangedCallbackUnchecked,
        )

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

        self._applyResolvedTheme(theme, Mixins.ThemeAware.callThemeChangedCallback)

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

    def _filterMainWindowEvent(self, event) -> bool:
        """Apply application policy before the main window handles an event."""
        eventType = event.type()

        if (
            eventType == QtCore.QEvent.Type.Close
            and self.systemTray is None
            and self._handleMainWindowCloseEvent(event)
        ):
            return True

        if PLATFORM == 'Darwin' and AppSettings.isStateON_('HideDockIcon'):
            # Show the Dock icon while the main window is visible and hide it
            # only when the window closes rather than when minimized.
            if eventType == QtCore.QEvent.Type.Show:
                self.setDockIconVisible(True)
            elif eventType == QtCore.QEvent.Type.Hide:
                if not self.mainWindow.isMinimized():
                    self.setDockIconVisible(False)

        return False

    def eventFilter(self, watched, event):
        """Filter application-owned main-window events."""
        if watched is self.mainWindow and self._filterMainWindowEvent(event):
            return True

        return super().eventFilter(watched, event)

    def installDockIconVisibilityFeature(self, remove=False):
        """Handle install dock icon visibility feature for the application."""
        if remove:
            self.setDockIconVisible(True)
        else:
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

            pluginRegistry = self.addEnviron()

            self._cleanupStack.register('plugins', pluginRegistry.shutdown)

            try:
                self.addStorage()
            except Exception:
                # Any non-exit exceptions

                # Roll back resources acquired before storage.
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
        except Exception:
            # Any non-exit exceptions

            traceback.print_exc()

            return ApplicationRunner.ExitCode.UnknownException.value
        finally:
            self.cleanup()
