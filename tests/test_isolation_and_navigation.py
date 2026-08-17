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

"""Verify test-process isolation and Fluent navigation behavior."""

from __future__ import annotations

from Furious.Widget.NavigationView import NavigationView

from PySide6 import QtCore
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from pathlib import Path

from tests.support import (
    application,
    assertIsolatedSettings,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    settingsSandboxPath,
)

import unittest


class TestHarnessIsolationTest(unittest.TestCase):
    """Prove QSettings never resolves to a production Furious namespace."""

    @classmethod
    def setUpClass(cls):
        """Create the suite-owned QApplication and settings root."""
        application()

    def testNestedSettingsNamespacesRestoreProcessMetadata(self):
        """Keep nested tests independent and restore their caller's namespace."""
        app = application()
        originalIdentity = (app.organizationName(), app.applicationName())

        with isolatedSettings() as outer:
            outerIdentity = (app.organizationName(), app.applicationName())
            outer.setValue('fixture', 'outer')

            assertIsolatedSettings(outer)

            self.assertIn(settingsSandboxPath(), Path(outer.fileName()).parents)

            with isolatedSettings() as inner:
                innerIdentity = (app.organizationName(), app.applicationName())

                assertIsolatedSettings(inner)

                self.assertNotEqual(innerIdentity, outerIdentity)
                self.assertIsNone(inner.value('fixture'))

                inner.setValue('fixture', 'inner')

            self.assertEqual(
                (app.organizationName(), app.applicationName()),
                outerIdentity,
            )
            self.assertEqual(outer.value('fixture'), 'outer')

        self.assertEqual(
            (app.organizationName(), app.applicationName()),
            originalIdentity,
        )

    def testDefaultSettingsObjectRemainsInsideSuiteSandbox(self):
        """Keep unscoped test helpers away from the user's real settings file."""
        settings = QtCore.QSettings()

        assertIsolatedSettings(settings)

        self.assertIn(settingsSandboxPath(), Path(settings.fileName()).parents)


class NavigationBehaviorTest(unittest.TestCase):
    """Protect overlay geometry, outside-click dismissal, and page persistence."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def setUp(self):
        """Build one isolated navigation view with top and bottom pages."""
        self.navigation = NavigationView()
        self.navigation.resize(900, 600)

        self.homePage = QWidget()

        homeLayout = QVBoxLayout(self.homePage)

        self.outsideButton = QPushButton('Outside target', self.homePage)

        homeLayout.addWidget(self.outsideButton)

        self.settingsPage = QWidget()

        self.navigation.addPage('home', self.homePage, 'Home', 'house-door.svg')
        self.navigation.addPage(
            'settings',
            self.settingsPage,
            'Settings',
            'gear-wide-connected.svg',
            placement='bottom',
        )
        self.navigation.show()

        processQtEvents()

    def tearDown(self):
        """Destroy the complete page tree between tests."""
        self.navigation.close()
        self.navigation.deleteLater()

        collectAtBoundary()

    def testExpandedPanelOverlaysWithoutMovingContent(self):
        """Expand only the panel geometry while the page stack remains fixed."""
        collapsedGeometry = QtCore.QRect(self.navigation.pageStack.geometry())

        self.navigation.setExpanded(True, animated=False)

        processQtEvents()

        self.assertTrue(self.navigation.isExpanded())
        self.assertEqual(
            self.navigation.navigationPanel.width(),
            self.navigation.ExpandedWidth,
        )
        self.assertEqual(self.navigation.pageStack.geometry(), collapsedGeometry)
        self.assertEqual(
            self.navigation.navigationRail.width(),
            self.navigation.CollapsedWidth,
        )

    def testOutsideClickCollapsesAndStillReachesTarget(self):
        """Dismiss the temporary overlay without consuming the original click."""
        clicks = []

        self.outsideButton.clicked.connect(lambda: clicks.append(True))
        self.navigation.setExpanded(True, animated=False)

        QTest.mouseClick(
            self.outsideButton,
            QtCore.Qt.MouseButton.LeftButton,
        )

        processQtEvents()

        self.assertEqual(clicks, [True])
        self.assertFalse(self.navigation.isExpanded())
        self.assertFalse(self.navigation._outsideClickFilterInstalled)

    def testInsideNavigationClickKeepsOverlayExpandedAndSwitchesPage(self):
        """Allow normal navigation interaction without flyout dismissal."""
        self.navigation.setExpanded(True, animated=False)

        settingsButton = self.navigation._pages['settings'].button

        QTest.mouseClick(
            settingsButton,
            QtCore.Qt.MouseButton.LeftButton,
        )

        processQtEvents()

        self.assertTrue(self.navigation.isExpanded())
        self.assertEqual(self.navigation.currentPageId(), 'settings')
        self.assertIs(self.navigation.pageStack.currentWidget(), self.settingsPage)

    def testRepeatedExpansionAndPageSwitchingReuseOwnedObjects(self):
        """Avoid duplicate pages, animations, buttons, or event-filter state."""
        animation = self.navigation._widthAnimation
        pages = tuple(page.widget for page in self.navigation._pages.values())
        buttons = tuple(page.button for page in self.navigation._pages.values())

        for index in range(75):
            self.navigation.setExpanded(True, animated=False)
            self.navigation.setCurrentPage('settings' if index % 2 else 'home')
            self.navigation.setExpanded(False, animated=False)

        processQtEvents()

        self.assertIs(self.navigation._widthAnimation, animation)
        self.assertEqual(
            tuple(page.widget for page in self.navigation._pages.values()),
            pages,
        )
        self.assertEqual(
            tuple(page.button for page in self.navigation._pages.values()),
            buttons,
        )
        self.assertEqual(self.navigation.pageStack.count(), 2)
        self.assertFalse(self.navigation._outsideClickFilterInstalled)


if __name__ == '__main__':
    unittest.main()
