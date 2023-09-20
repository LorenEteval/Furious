# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Widget.SystemTrayIcon import SystemTrayIcon
from Furious.Widget.EditConfiguration import EditConfigurationWidget
from Furious.Widget.EditRouting import EditRoutingWidget
from Furious.Widget.EditSubscription import EditSubscriptionWidget
from Furious.Widget.LogViewer import LogViewerWidget, TorViewerWidget
from Furious.Widget.TorRelaySettings import TorRelaySettingsWidget
from Furious.Utility.Constants import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    ORGANIZATION_NAME,
    ORGANIZATION_DOMAIN,
    PLATFORM,
    LOCAL_SERVER_NAME,
    SYSTEM_LANGUAGE,
    DATA_DIR,
)
from Furious.Utility.Utility import (
    ServerStorage,
    SupportThemeChangedCallback,
    NeedSyncSettings,
)
from Furious.Utility.Proxy import Proxy
from Furious.Utility.Settings import Settings
from Furious.Utility.Translator import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

import os
import sys
import time
import logging
import traceback
import threading
import darkdetect

logger = logging.getLogger(__name__)


def getPythonVersion():
    return '.'.join(str(info) for info in sys.version_info)


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


class LogViewerHandle(logging.Handler):
    def __init__(self, textBrowser):
        super().__init__()

        self.textBrowser = textBrowser

    def emit(self, record):
        self.textBrowser.append(self.format(record))


class SingletonApplication(QApplication):
    def __init__(self, argv):
        super().__init__(argv)

        # Exiting flag
        self.exiting = False
        self.serverName = LOCAL_SERVER_NAME

        self.socket = QLocalSocket(self)
        self.server = QLocalServer(self)

    def checkForExistingApp(self):
        self.socket.connectToServer(self.serverName)

        if self.socket.waitForConnected(1000):
            # Show tray message in the started instance
            self.socket.close()

            # Do not start
            return True
        else:
            # New instance
            self.server.newConnection.connect(self.showExistingApp)

            if not self.server.listen(self.serverName):
                # Do not start
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


class Application(SingletonApplication):
    class ErrorCode:
        ExitSuccess = 0
        UnknownException = 1
        PlatformNotSupported = 2
        AssertionError = 3

    def __init__(self, argv):
        super().__init__(argv)

        self.setApplicationName(APPLICATION_NAME)
        self.setApplicationVersion(APPLICATION_VERSION)
        self.setOrganizationName(ORGANIZATION_NAME)
        self.setOrganizationDomain(ORGANIZATION_DOMAIN)

        self.tray = None

        # Whether server test has been performed
        self.testPerformed = False

        # Font
        self.customFontLoadMsg = ''
        self.customFontEnabled = False
        self.customFontName = ''

        # Log Viewer Widget
        self.logViewerWidget = None
        self.torViewerWidget = None

        # Log Handle
        self.logViewerHandle = None
        self.logStreamHandle = None

        # Theme Detect
        self.themeDetector = None
        self.themeListenerThread = None

        # Main Widget
        self.SubscriptionWidget = None
        self.ServerWidget = None
        self.RoutesWidget = None
        self.TorRelayWidget = None

    def __getattr__(self, key):
        try:
            return Settings.get(key)
        except AttributeError:
            raise

    def __setattr__(self, key, value):
        try:
            Settings.set(key, value)
        except AttributeError:
            pass

        super().__setattr__(key, value)

    @rateLimited(maxCallPerSecond=2)
    @QtCore.Slot()
    def showExistingApp(self):
        if isinstance(self.tray, SystemTrayIcon):
            logger.info('attempting to start multiple instance. Show tray message')

            self.tray.showMessage(_('Already started'))
        else:
            # The tray hasn't been initialized. Do nothing
            pass

    def configureLogging(self):
        self.logViewerWidget = LogViewerWidget()
        self.torViewerWidget = TorViewerWidget()

        self.logViewerHandle = LogViewerHandle(self.logViewerWidget.textBrowser)
        self.logStreamHandle = logging.StreamHandler()

        logging.basicConfig(
            format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            level=logging.INFO,
            handlers=(self.logViewerHandle, self.logStreamHandle),
        )
        logging.raiseExceptions = False

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
        os.environ['XRAY_LOCATION_ASSET'] = str(DATA_DIR / 'xray')

    def initTray(self):
        if not SystemTrayIcon.isSystemTrayAvailable():
            raise SystemTrayUnavailable(
                'SystemTrayIcon is not available on this platform'
            )

        self.addEnviron()
        self.addCustomFont()
        self.configureLogging()

        self.themeDetector = ApplicationThemeDetector()
        self.themeDetector.themeChanged.connect(
            SupportThemeChangedCallback.callThemeChangedCallback
        )

        self.themeListenerThread = threading.Thread(
            target=darkdetect.listener,
            args=(self.themeDetector.themeChanged.emit,),
            daemon=True,
        )
        self.themeListenerThread.start()

        import PySide6

        logger.info(f'application version: {APPLICATION_VERSION}')
        logger.info(
            f'Qt version: {QtCore.qVersion()}. PySide6 version: {PySide6.__version__}'
        )
        logger.info(f'python version: {getPythonVersion()}. Platform: {PLATFORM}')
        logger.info(f'system version: {sys.version}')
        logger.info(f'sys.executable: {sys.executable}')
        logger.info(f'sys.argv: {sys.argv}')
        logger.info(f'appFilePath: {self.applicationFilePath()}')
        logger.info(f'system language is {SYSTEM_LANGUAGE}')
        logger.info(self.customFontLoadMsg)

        # Mandatory
        self.setQuitOnLastWindowClosed(False)

        # Reset proxy
        Proxy.off()
        Proxy.daemonOn_()

        self.aboutToQuit.connect(self.cleanup)

        self.SubscriptionWidget = EditSubscriptionWidget()
        self.ServerWidget = EditConfigurationWidget()
        self.RoutesWidget = EditRoutingWidget()
        self.TorRelayWidget = TorRelaySettingsWidget()

        self.tray = SystemTrayIcon()
        self.tray.show()
        self.tray.setApplicationToolTip()
        self.tray.bootstrap()

        return self

    @QtCore.Slot()
    def cleanup(self):
        Proxy.off()
        Proxy.daemonOff()

        # Try to avoid unnecessary storage sync.
        # Better way to do this?
        if self.testPerformed:
            ServerStorage.sync()

        NeedSyncSettings.syncAll()

        if self.tray is not None:
            self.tray.ConnectAction.stopCore()

    def exit(self, exitcode=0):
        if self.ServerWidget is not None:
            if self.ServerWidget.questionSave():
                # Changes handled. Exit
                self.ServerWidget.pingThreadPool.clear()
                self.exiting = True

                super().exit(exitcode)
        else:
            self.exiting = True

            super().exit(exitcode)

    def log(self):
        if self.logViewerWidget is not None:
            return self.logViewerWidget.log()
        else:
            return ''

    def run(self):
        try:
            if not self.checkForExistingApp():
                return self.initTray().exec()

            # See: https://github.com/python/cpython/issues/79908
            # sys.exit(None) in multiprocessing will produce
            # exitcode 1 in some Python version, which is
            # not what we want.
            return Application.ErrorCode.ExitSuccess
        except SystemTrayUnavailable:
            return Application.ErrorCode.PlatformNotSupported
        except Exception:
            # Any non-exit exceptions

            traceback.print_exc()

            return Application.ErrorCode.UnknownException
