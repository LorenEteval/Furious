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

"""Verify real Qt animation and ownership for application theme transitions."""

from __future__ import annotations

import unittest

from PySide6 import QtCore
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid

from Furious.Qt import ThemeTransition

from tests.support import application, processQtEvents, waitFor


class ThemeTransitionTest(unittest.TestCase):
    """Exercise cross-fades through the real Qt event loop."""

    def setUp(self):
        """Create per-test windows while retaining one process-wide application."""
        application()

        self.windows = []
        self.transitions = []

    def tearDown(self):
        """Release every transient overlay, animation, coordinator, and window."""
        for transition in self.transitions:
            transition.stop()
            transition.deleteLater()

        for window in self.windows:
            window.close()
            window.deleteLater()

        processQtEvents()

    def createWindow(self):
        """Create and show one deterministic top-level transition target."""
        window = QWidget()
        window.resize(320, 180)
        window.show()

        self.windows.append(window)

        processQtEvents()

        return window

    def createTransition(self, windows, *, duration=60, enabled=True):
        """Create one coordinator with deterministic animation policy."""
        transition = ThemeTransition(
            duration=duration,
            windowProvider=lambda: tuple(windows),
            animationsEnabled=lambda: enabled,
        )

        self.transitions.append(transition)

        return transition

    @staticmethod
    def overlays(window):
        """Return the transition overlays currently owned by *window*."""
        return window.findChildren(
            QWidget,
            ThemeTransition.OverlayObjectName,
            QtCore.Qt.FindChildOption.FindDirectChildrenOnly,
        )

    def testThemeIsAppliedImmediatelyThenSnapshotCompletesAndIsRemoved(self):
        """Keep destination state live beneath one real fading snapshot."""
        window = self.createWindow()
        transition = self.createTransition([window])
        started = QSignalSpy(transition.transitionStarted)
        finished = QSignalSpy(transition.transitionFinished)

        def applyDarkTheme():
            """Represent the application's synchronous destination-theme commit."""
            window.setProperty('testTheme', 'Dark')
            window.setStyleSheet('background-color: #10151d;')

        transition.apply(applyDarkTheme)

        self.assertEqual(window.property('testTheme'), 'Dark')
        self.assertTrue(transition.isRunning())
        self.assertEqual(transition.activeOverlayCount(), 1)
        self.assertEqual(len(self.overlays(window)), 1)
        self.assertEqual(started.count(), 1)
        self.assertTrue(
            transition.findChildren(QtCore.QPropertyAnimation),
            'the transition must use a real QPropertyAnimation',
        )

        self.assertTrue(waitFor(lambda: not transition.isRunning()))
        processQtEvents()

        self.assertEqual(finished.count(), 1)
        self.assertEqual(transition.activeOverlayCount(), 0)
        self.assertEqual(self.overlays(window), [])
        self.assertEqual(
            transition.findChildren(QtCore.QPropertyAnimation),
            [],
        )

    def testRapidRepeatedSwitchReplacesRatherThanStacksTransitions(self):
        """Restart from the visible composite and retain only the newest target."""
        window = self.createWindow()
        transition = self.createTransition([window], duration=160)
        started = QSignalSpy(transition.transitionStarted)
        finished = QSignalSpy(transition.transitionFinished)

        transition.apply(lambda: window.setProperty('testTheme', 'Dark'))
        firstOverlay = self.overlays(window)[0]

        transition.apply(lambda: window.setProperty('testTheme', 'Light'))

        self.assertEqual(window.property('testTheme'), 'Light')
        self.assertEqual(transition.activeOverlayCount(), 1)
        self.assertEqual(started.count(), 2)
        self.assertEqual(finished.count(), 1)

        processQtEvents()

        self.assertFalse(isValid(firstOverlay))
        self.assertEqual(len(self.overlays(window)), 1)
        self.assertTrue(waitFor(lambda: not transition.isRunning()))
        processQtEvents()

        self.assertEqual(finished.count(), 2)
        self.assertEqual(self.overlays(window), [])

    def testMultipleWindowsTransitionAndResizeIndependently(self):
        """Cancel only a resized window's stale snapshot while peers continue."""
        firstWindow = self.createWindow()
        secondWindow = self.createWindow()
        transition = self.createTransition(
            [firstWindow, secondWindow],
            duration=120,
        )
        finished = QSignalSpy(transition.transitionFinished)

        def applyLightTheme():
            """Commit the same destination theme to both top-level windows."""
            firstWindow.setProperty('testTheme', 'Light')
            secondWindow.setProperty('testTheme', 'Light')

        transition.apply(applyLightTheme)

        self.assertEqual(transition.activeOverlayCount(), 2)
        firstWindow.resize(360, 200)
        processQtEvents()

        self.assertEqual(firstWindow.property('testTheme'), 'Light')
        self.assertEqual(secondWindow.property('testTheme'), 'Light')
        self.assertEqual(self.overlays(firstWindow), [])
        self.assertEqual(transition.activeOverlayCount(), 1)
        self.assertTrue(transition.isRunning())
        self.assertTrue(waitFor(lambda: not transition.isRunning()))
        processQtEvents()

        self.assertEqual(finished.count(), 1)
        self.assertEqual(self.overlays(secondWindow), [])

    def testDisabledAnimationsNeverDelayOrOverlayTheDestinationTheme(self):
        """Honor the animation policy while preserving immediate theme activation."""
        window = self.createWindow()
        transition = self.createTransition([window], enabled=False)
        started = QSignalSpy(transition.transitionStarted)

        transition.apply(lambda: window.setProperty('testTheme', 'Dark'))

        self.assertEqual(window.property('testTheme'), 'Dark')
        self.assertFalse(transition.isRunning())
        self.assertEqual(started.count(), 0)
        self.assertEqual(self.overlays(window), [])


if __name__ == '__main__':
    unittest.main()
