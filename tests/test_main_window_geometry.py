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

"""Protect AppQMainWindow lifecycle and persisted geometry semantics."""

from __future__ import annotations

from Furious.Backends.Xray.AssetWindow import XrayAssetWindow
from Furious.Backends.Xray.RoutingWindow import XrayRoutingWindow
from Furious.Controllers.ConnectionController import ConnectionController
from Furious.Controllers.RoutingController import RoutingController
from Furious.Controllers.SettingsController import SettingsController
from Furious.Frozenlib import AppSettings
from Furious.Service import LogManager, PluginNavigationManager
from Furious.Qt import AppQMainWindow
from Furious.Widget.NavigationView import NavigationView
from Furious.Window.HomePage import HomePage
from Furious.Window.LogPage import LogPage
from Furious.Window.MainWindow import MainWindow
from Furious.Window.QRCodeWindow import QRCodeWindow
from Furious.Window.TextEditorWindow import TextEditorWindow

from PySide6 import QtCore
from PySide6.QtWidgets import QMainWindow, QWidget

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
)

from contextlib import contextmanager

import unittest
from unittest.mock import patch


class _LifecycleWindow(AppQMainWindow):
    """Record the shared first-show lifecycle without application pages."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(731, 517)

    def __init__(self):
        """Finish composition after the base constructor returns."""
        self.composed = False
        self.prepareCalls = 0
        self.preparedAfterComposition = False

        super().__init__()

        self.setCentralWidget(QWidget(parent=self))
        self.composed = True

    def prepareInitialGeometry(self):
        """Record preparation order before applying the declarative default."""
        self.prepareCalls += 1
        self.preparedAfterComposition = self.composed

        super().prepareInitialGeometry()


class _NeverCenterWindow(_LifecycleWindow):
    """Exercise the explicit initial-centering opt-out."""

    CENTER_ON_INITIAL_SHOW = False


class _GeometryWindow(AppQMainWindow):
    """Exercise MainWindow's geometry policy without constructing app pages."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(700, 500)

    QT_FALLBACK_WINDOW_SIZE = MainWindow.QT_FALLBACK_WINDOW_SIZE
    _applyDefaultWindowSize = MainWindow._applyDefaultWindowSize
    _restoreLegacyWindowSize = MainWindow._restoreLegacyWindowSize
    _restoreMainWindowState = MainWindow._restoreMainWindowState
    cleanup = MainWindow.cleanup
    prepareInitialGeometry = MainWindow.prepareInitialGeometry

    def __init__(self):
        """Compose the minimal child hierarchy used by restoreState()."""
        super().__init__()

        self.setCentralWidget(QWidget(parent=self))


class _InertManager:
    """Expose only the idle runtime collection used by controllers in UI tests."""

    runtimes = ()


@contextmanager
def _realMainWindow():
    """Own one fully composed MainWindow and its isolated application services."""
    app = application()
    oldServices = (
        app.connectionController,
        app.routingController,
        app.settingsController,
        app.logManager,
        app.logPage,
    )
    connectionController = ConnectionController(
        parent=app,
        coreManager=_InertManager(),
        updatesManager=_InertManager(),
    )
    logManager = LogManager(parent=app)
    routingController = None
    window = None

    try:
        app.connectionController = connectionController
        routingController = RoutingController(parent=app)
        app.routingController = routingController
        app.settingsController = SettingsController()
        app.logManager = logManager
        app.logPage = LogPage(manager=logManager)

        with patch.object(HomePage, 'serverImportActions', return_value=()):
            window = MainWindow()

        yield window
    finally:
        if window is not None:
            window.close()
            window.deleteLater()
            collectAtBoundary()

        (
            app.connectionController,
            app.routingController,
            app.settingsController,
            app.logManager,
            app.logPage,
        ) = oldServices

        if routingController is not None:
            routingController.deleteLater()

        connectionController.deleteLater()
        logManager.deleteLater()
        collectAtBoundary()


class AppQMainWindowLifecycleTest(unittest.TestCase):
    """Keep shared first-show mechanics deterministic and subclass-safe."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Destroy windows and drain deferred deletion between tests."""
        for window in list(AppQMainWindow._openWindows.values()):
            window.close()
            window.deleteLater()

        collectAtBoundary()

    def testPreparationRunsAfterCompositionAndOnlyOnce(self):
        """Never call subclass lifecycle hooks from the base constructor."""
        window = _LifecycleWindow()

        self.assertEqual(window.prepareCalls, 0)
        self.assertFalse(window.hasPreparedInitialGeometry())

        with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
            window.show()

            self.assertEqual(window.prepareCalls, 1)
            self.assertTrue(window.hasPreparedInitialGeometry())
            self.assertTrue(window.preparedAfterComposition)
            self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
            moveToCenter.assert_called_once_with(window)

            window.move(37, 41)
            movedPosition = QtCore.QPoint(window.pos())
            window.hide()
            window.show()

            self.assertEqual(window.prepareCalls, 1)
            self.assertEqual(window.pos(), movedPosition)
            moveToCenter.assert_called_once_with(window)

        window.close()
        window.deleteLater()

    def testRestoredGeometryOwnsItsInitialPosition(self):
        """Do not center over a position supplied by valid saved geometry."""
        source = _LifecycleWindow()
        source.setGeometry(45, 55, 640, 480)
        savedGeometry = source.saveGeometry()
        source.close()
        source.deleteLater()

        window = _LifecycleWindow()
        self.assertTrue(window.restoreInitialGeometry(savedGeometry))

        with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
            window.show()

            moveToCenter.assert_not_called()

        window.close()
        window.deleteLater()

    def testSubclassCanOptOutOfInitialCentering(self):
        """Honor the declarative centering policy without platform checks."""
        window = _NeverCenterWindow()

        with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
            window.show()

            moveToCenter.assert_not_called()

        window.close()
        window.deleteLater()

    def testConcreteSubclassDefaultsAndRepeatedShows(self):
        """Apply every non-persistent subclass default once and preserve moves."""
        cases = (
            (QRCodeWindow, QRCodeWindow.DEFAULT_WINDOW_SIZE),
            (TextEditorWindow, TextEditorWindow.DEFAULT_WINDOW_SIZE),
            (XrayAssetWindow, XrayAssetWindow.DEFAULT_WINDOW_SIZE),
        )

        with isolatedSettings():
            for windowType, expectedSize in cases:
                with self.subTest(windowType=windowType.__name__):
                    window = windowType()

                    with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                        window.show()

                        self.assertEqual(window.size(), expectedSize)
                        moveToCenter.assert_called_once_with(window)

                        window.move(61, 73)
                        movedPosition = QtCore.QPoint(window.pos())
                        window.hide()
                        window.show()

                        self.assertEqual(window.pos(), movedPosition)
                        moveToCenter.assert_called_once_with(window)

                    window.close()
                    window.deleteLater()
                    collectAtBoundary()


class MainWindowNavigationSessionTest(unittest.TestCase):
    """Keep page and expansion state live in one window, not in settings."""

    FormerPageKey = 'AppMainWindowSelectedPage'
    FormerExpansionKey = 'AppMainWindowNavigationExpanded'

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Destroy windows and drain deferred deletion between tests."""
        for window in list(AppQMainWindow._openWindows.values()):
            window.close()
            window.deleteLater()

        collectAtBoundary()

    def assertCanonicalPage(self, window: MainWindow):
        """Assert the navigation selection and stack both point to Home."""
        self.assertEqual(window.navigationView.currentPageId(), 'home')
        self.assertIs(window.navigationView.page('home'), window.homePage)
        self.assertIs(
            window.navigationView.pageStack.currentWidget(),
            window.homePage,
        )

    def testNewSessionUsesCanonicalPageAndIgnoresFormerValues(self):
        """Ignore every representative value stored by the retired setting."""
        self.assertNotIn(self.FormerPageKey, AppSettings.SettingsPool)
        self.assertNotIn(self.FormerExpansionKey, AppSettings.SettingsPool)

        formerValues = (
            None,
            'settings',
            'log',
            'metrics',
            'plugin:example:status',
            'removed-page',
        )

        for formerValue in formerValues:
            with self.subTest(formerValue=formerValue), isolatedSettings() as settings:
                if formerValue is not None:
                    settings.setValue(self.FormerPageKey, formerValue)

                with _realMainWindow() as window:
                    self.assertCanonicalPage(window)
                    self.assertFalse(window.navigationView.isExpanded())

    def testNavigationDoesNotCreateOrUpdateFormerSetting(self):
        """Keep both absent and stale obsolete keys untouched by navigation."""
        with isolatedSettings() as settings, _realMainWindow() as window:
            window.showPage('settings')
            window.navigationView.setExpanded(True, animated=False)
            window.cleanup()

            self.assertFalse(settings.contains(self.FormerPageKey))
            self.assertFalse(settings.contains(self.FormerExpansionKey))

        with isolatedSettings() as settings:
            settings.setValue(self.FormerPageKey, 'log')
            settings.setValue(self.FormerExpansionKey, '1')

            with _realMainWindow() as window:
                self.assertCanonicalPage(window)
                self.assertFalse(window.navigationView.isExpanded())
                window.showPage('settings')
                window.navigationView.setExpanded(True, animated=False)
                window.cleanup()

            self.assertEqual(settings.value(self.FormerPageKey), 'log')
            self.assertEqual(settings.value(self.FormerExpansionKey), '1')

    def testNewWindowResetsSessionStateButRestoresGeometry(self):
        """Reset page and expansion while retaining persistent geometry."""
        expectedSize = QtCore.QSize(760, 600)

        with isolatedSettings() as settings:
            with _realMainWindow() as firstWindow:
                firstWindow.show()
                firstWindow.resize(expectedSize)
                firstWindow.navigationView.setExpanded(True, animated=False)
                firstWindow.showPage('settings')
                firstWindow.cleanup()

                self.assertEqual(
                    firstWindow.navigationView.currentPageId(),
                    'settings',
                )
                self.assertTrue(firstWindow.navigationView.isExpanded())

            self.assertFalse(settings.contains(self.FormerPageKey))
            self.assertFalse(settings.contains(self.FormerExpansionKey))

            with _realMainWindow() as secondWindow:
                secondWindow.show()

                self.assertCanonicalPage(secondWindow)
                self.assertFalse(secondWindow.navigationView.isExpanded())
                self.assertEqual(secondWindow.size(), expectedSize)

    def testHideAndShowPreservesLivePage(self):
        """Do not reset the page while reusing the same MainWindow instance."""
        with isolatedSettings(), _realMainWindow() as window:
            window.show()
            window.showPage('settings')
            window.hide()
            window.show()
            processQtEvents()

            self.assertEqual(window.navigationView.currentPageId(), 'settings')
            self.assertIs(
                window.navigationView.pageStack.currentWidget(),
                window.settingsPage,
            )

    def testPluginRegistrationCannotReplaceCanonicalPage(self):
        """Keep Home selected even when a stale plugin page is registered."""

        def registerPluginPage(_manager, navigationView):
            pluginPage = QWidget(parent=navigationView)
            navigationView.addPage(
                'plugin:example:status',
                pluginPage,
                'Plugin',
                'house-door.svg',
            )

        with isolatedSettings() as settings:
            settings.setValue(self.FormerPageKey, 'plugin:example:status')

            with patch.object(
                PluginNavigationManager,
                'registerPages',
                autospec=True,
                side_effect=registerPluginPage,
            ), _realMainWindow() as window:
                self.assertCanonicalPage(window)
                self.assertIsNotNone(
                    window.navigationView.page('plugin:example:status')
                )


class MainWindowGeometryTest(unittest.TestCase):
    """Keep restoration driven by persisted-state validity, not dimensions."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Destroy windows and drain deferred deletion between tests."""
        for window in list(AppQMainWindow._openWindows.values()):
            window.close()
            window.deleteLater()

        collectAtBoundary()

    @staticmethod
    def _saveGeometry(rect: QtCore.QRect) -> QtCore.QByteArray:
        """Return valid Qt geometry for one deterministic client rectangle."""
        source = _GeometryWindow()
        source.setGeometry(rect)
        savedGeometry = source.saveGeometry()
        source.close()
        source.deleteLater()

        return savedGeometry

    def testRealMainWindowUsesSharedLifecycleAfterComposition(self):
        """Construct the complete page hierarchy before first-show preparation."""
        app = application()
        with isolatedSettings(), _realMainWindow() as window:
            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                window.show()

                self.assertEqual(
                    sum(
                        isinstance(widget, MainWindow)
                        for widget in app.topLevelWidgets()
                    ),
                    1,
                )
                self.assertEqual(len(window.findChildren(NavigationView)), 1)
                self.assertIs(window.centralWidget(), window.navigationView)

                self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                moveToCenter.assert_called_once_with(window)

                window.move(83, 97)
                movedPosition = QtCore.QPoint(window.pos())
                window.hide()
                window.show()

                self.assertEqual(window.pos(), movedPosition)
                moveToCenter.assert_called_once_with(window)

            expectedPages = {
                'home': window.homePage,
                'log': window.logPage,
                'subscription': window.subscriptionPage,
                'metrics': window.metricsPage,
                'settings': window.settingsPage,
            }

            for pageId, page in expectedPages.items():
                with self.subTest(pageId=pageId):
                    window.showPage(pageId)
                    processQtEvents()

                    self.assertEqual(
                        window.navigationView.currentPageId(),
                        pageId,
                    )
                    self.assertIs(window.navigationView.page(pageId), page)
                    self.assertIs(
                        window.navigationView.pageStack.currentWidget(),
                        page,
                    )

    def testFirstLaunchUsesCanonicalDefault(self):
        """Use the product default when modern and legacy settings are absent."""
        with isolatedSettings(), patch(
            'Furious.Qt.QtWidgets.moveToCenter'
        ) as moveToCenter:
            window = _GeometryWindow()
            window.show()

            self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
            moveToCenter.assert_called_once_with(window)

            window.close()
            window.deleteLater()

    def testInvalidModernGeometryUsesCanonicalDefault(self):
        """Honor restoreGeometry's false result rather than inspecting size."""
        for savedGeometry in (
            QtCore.QByteArray(),
            QtCore.QByteArray(b'broken'),
        ):
            with self.subTest(savedGeometry=bytes(savedGeometry)), isolatedSettings():
                AppSettings.set('AppMainWindowGeometry', savedGeometry)

                window = _GeometryWindow()

                with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                    window.show()

                    self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                    moveToCenter.assert_called_once_with(window)

                window.close()
                window.deleteLater()

    def testDarwinRestoredQtFallbackSizeUsesCanonicalDefault(self):
        """Replace macOS Qt fallback dimensions with the product default."""
        with isolatedSettings():
            expected = QtCore.QRect(40, 50, 640, 480)
            AppSettings.set(
                'AppMainWindowGeometry',
                self._saveGeometry(expected),
            )

            window = _GeometryWindow()

            with patch('Furious.Window.MainWindow.PLATFORM', 'Darwin'), patch(
                'Furious.Qt.QtWidgets.moveToCenter'
            ) as moveToCenter:
                window.show()

                self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testNonDarwinRestoredQtFallbackSizeUsesCanonicalDefault(self):
        """Replace the Qt fallback dimensions with the product default."""
        with isolatedSettings():
            expected = QtCore.QRect(40, 50, 640, 480)
            AppSettings.set(
                'AppMainWindowGeometry',
                self._saveGeometry(expected),
            )

            window = _GeometryWindow()

            with patch('Furious.Window.MainWindow.PLATFORM', 'Windows'), patch(
                'Furious.Qt.QtWidgets.moveToCenter'
            ) as moveToCenter:
                window.show()

                self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testValidGeometrySurvivesInvalidQMainWindowState(self):
        """Keep geometry and QMainWindow layout-state validity independent."""
        with isolatedSettings():
            expected = QtCore.QRect(30, 35, 720, 520)
            AppSettings.set(
                'AppMainWindowGeometry',
                self._saveGeometry(expected),
            )
            AppSettings.set('AppMainWindowState', QtCore.QByteArray(b'broken'))

            window = _GeometryWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                window.show()

                self.assertEqual(window.size(), expected.size())
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testLegacyCustomAndHistoricallySuspiciousSizesRemainUserData(self):
        """Migrate every positive legacy size without dimension heuristics."""
        for legacySize, expected in (
            ('1111,700', QtCore.QSize(1111, 700)),
            ('640,480', QtCore.QSize(640, 480)),
            ('702,480', QtCore.QSize(702, 480)),
        ):
            with self.subTest(legacySize=legacySize), isolatedSettings():
                AppSettings.set('ServerWidgetWindowSize', legacySize)

                window = _GeometryWindow()
                window.show()

                self.assertEqual(window.size(), expected)

                window.close()
                window.deleteLater()

    def testInvalidLegacySizeUsesCanonicalDefault(self):
        """Reject malformed and non-positive legacy values deterministically."""
        for legacySize in ('', '640', 'wide,high', '0,480', '-1,480'):
            with self.subTest(legacySize=legacySize), isolatedSettings():
                AppSettings.set('ServerWidgetWindowSize', legacySize)

                window = _GeometryWindow()
                window.show()

                self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)

                window.close()
                window.deleteLater()

    def testFallbackSavedAtCleanupRestoresOnNextLaunch(self):
        """Persist the product fallback instead of a transient Qt initial size."""
        with isolatedSettings():
            AppSettings.set('AppMainWindowGeometry', QtCore.QByteArray(b'broken'))

            firstWindow = _GeometryWindow()
            firstWindow.show()
            firstWindow.cleanup()

            secondWindow = _GeometryWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                secondWindow.show()

                self.assertEqual(secondWindow.size(), firstWindow.DEFAULT_WINDOW_SIZE)
                moveToCenter.assert_not_called()

            firstWindow.close()
            firstWindow.deleteLater()
            secondWindow.close()
            secondWindow.deleteLater()

    def testMaximizedGeometryRestoresWithoutDefaultFallback(self):
        """Preserve Qt's maximized state encoded in valid saved geometry."""
        with isolatedSettings():
            source = _GeometryWindow()
            source.showMaximized()
            processQtEvents()
            savedGeometry = source.saveGeometry()
            source.close()
            source.deleteLater()

            AppSettings.set('AppMainWindowGeometry', savedGeometry)

            window = _GeometryWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                window.show()

                self.assertTrue(window.isMaximized())
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testRoutingWindowRestoresCrossPlatformAndPreservesMove(self):
        """Give the routing editor the same restoration semantics everywhere."""
        with isolatedSettings():
            expected = QtCore.QRect(50, 60, 820, 540)
            AppSettings.set(
                'UserRoutingWindowGeometry',
                self._saveGeometry(expected),
            )

            window = XrayRoutingWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                window.show()

                # Qt may clamp restored geometry to the available screen; the
                # successful restore is authoritative even when dimensions shift.
                self.assertNotEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                moveToCenter.assert_not_called()

                window.move(77, 89)
                movedPosition = QtCore.QPoint(window.pos())
                window.hide()
                window.show()

                self.assertEqual(window.pos(), movedPosition)
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testRoutingWindowUsesDefaultForMissingAndInvalidGeometry(self):
        """Center the routing default only when no valid position was restored."""
        savedValues = (
            None,
            QtCore.QByteArray(),
            QtCore.QByteArray(b'broken'),
            self._saveGeometry(QtCore.QRect(1, 22, 100, 30)),
        )

        for savedGeometry in savedValues:
            with self.subTest(savedGeometry=savedGeometry), isolatedSettings():
                if savedGeometry is not None:
                    AppSettings.set('UserRoutingWindowGeometry', savedGeometry)

                window = XrayRoutingWindow()

                with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                    window.show()

                    self.assertEqual(window.size(), window.DEFAULT_WINDOW_SIZE)
                    moveToCenter.assert_called_once_with(window)

                window.close()
                window.deleteLater()

    def testRoutingWindowKeepsValidSmallGeometryAndIgnoresInvalidState(self):
        """Preserve intentional compact geometry independently from layout state."""
        with isolatedSettings():
            expected = QtCore.QRect(35, 45, 420, 260)
            AppSettings.set(
                'UserRoutingWindowGeometry',
                self._saveGeometry(expected),
            )
            AppSettings.set(
                'UserRoutingWindowState',
                QtCore.QByteArray(b'broken'),
            )

            window = XrayRoutingWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                window.show()

                self.assertEqual(window.size(), expected.size())
                moveToCenter.assert_not_called()

            window.close()
            window.deleteLater()

    def testRoutingWindowCloseAndReopenPreservesLiveGeometry(self):
        """Reuse one routing editor without rerunning first-show preparation."""
        with isolatedSettings():
            window = XrayRoutingWindow()

            with patch.object(
                window,
                'prepareInitialGeometry',
                wraps=window.prepareInitialGeometry,
            ) as prepareInitialGeometry:
                window.show()
                window.setGeometry(73, 91, 760, 510)
                expectedGeometry = QtCore.QRect(window.geometry())
                window.close()
                window.show()

                self.assertEqual(window.geometry(), expectedGeometry)
                prepareInitialGeometry.assert_called_once_with()

            window.close()
            window.deleteLater()

    def testRoutingWindowFallbackSavesAndRestoresOnNextInstance(self):
        """Replace failed restoration with a stable default for the next launch."""
        with isolatedSettings():
            AppSettings.set(
                'UserRoutingWindowGeometry',
                QtCore.QByteArray(b'broken'),
            )

            firstWindow = XrayRoutingWindow()
            firstWindow.show()
            firstWindow.cleanup()

            restoredGeometry = AppSettings.get('UserRoutingWindowGeometry')
            restoreProbe = QMainWindow()
            self.assertTrue(restoreProbe.restoreGeometry(restoredGeometry))
            expectedSize = QtCore.QSize(restoreProbe.size())

            secondWindow = XrayRoutingWindow()

            with patch('Furious.Qt.QtWidgets.moveToCenter') as moveToCenter:
                secondWindow.show()

                self.assertEqual(secondWindow.size(), expectedSize)
                moveToCenter.assert_not_called()

            restoreProbe.deleteLater()
            firstWindow.close()
            firstWindow.deleteLater()
            secondWindow.close()
            secondWindow.deleteLater()

    def testNeverShownPersistentWindowsDoNotOverwriteSavedGeometry(self):
        """Keep eager hidden windows from persisting native pre-show defaults."""
        cases = (
            (
                _GeometryWindow,
                'AppMainWindowGeometry',
                'AppMainWindowState',
            ),
            (
                XrayRoutingWindow,
                'UserRoutingWindowGeometry',
                'UserRoutingWindowState',
            ),
        )

        for windowType, geometryKey, stateKey in cases:
            with self.subTest(windowType=windowType.__name__), isolatedSettings():
                geometry = self._saveGeometry(QtCore.QRect(50, 60, 820, 540))
                state = QtCore.QByteArray(b'preserve-existing-state')
                AppSettings.set(geometryKey, geometry)
                AppSettings.set(stateKey, state)

                parent = QWidget()
                window = (
                    windowType(parent=parent)
                    if windowType is XrayRoutingWindow
                    else windowType()
                )

                self.assertFalse(window.hasPreparedInitialGeometry())

                window.cleanup()

                self.assertEqual(AppSettings.get(geometryKey), geometry)
                self.assertEqual(AppSettings.get(stateKey), state)

                window.close()
                window.deleteLater()
                parent.deleteLater()


if __name__ == '__main__':
    unittest.main()
