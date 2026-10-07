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

from Furious.Qt import ThemeTransition

from PySide6 import QtCore
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid, delete as deleteQObject

from tests.support import (
    application,
    assertChildSucceeded,
    processQtEvents,
    runPythonChild,
    waitFor,
)

from unittest import mock

import unittest
import weakref


class ThemeTransitionTest(unittest.TestCase):
    """Exercise cross-fades through the real Qt event loop."""

    def testCompletionCanDestroyTheWatchedWindowDuringResizeDelivery(self):
        """Notify deletion-capable observers after the native resize returns."""
        # Unsafe native event delivery can crash rather than raise a Python error.
        # Keep that failure inside an exact, bounded offscreen child process.
        result = runPythonChild(
            '''
from tests.support import application, processQtEvents
from Furious.Qt import ThemeTransition
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid, delete as deleteQObject
from unittest import mock
import weakref

application()

for _ in range(30):
    window = QWidget()
    window.resize(160, 100)
    window.show()
    processQtEvents()
    transition = ThemeTransition(
        duration=100000,
        windowProvider=lambda: (window,),
        animationsEnabled=lambda: True,
    )
    transition.apply(lambda: None)
    animation = next(iter(transition._animations))
    overlay = transition._animations[animation][1]
    references = [weakref.ref(item) for item in (window, animation, overlay)]
    destroyed = QSignalSpy(window.destroyed)
    finished = QSignalSpy(transition.transitionFinished)
    transition.transitionFinished.connect(lambda: deleteQObject(window))

    with mock.patch('sys.excepthook') as exceptionHook:
        window.resize(170, 110)
        assert isValid(window)
        assert destroyed.count() == 0
        assert finished.count() == 0
        assert not transition.isRunning()
        processQtEvents()
        exceptionHook.assert_not_called()

    assert destroyed.count() == 1
    assert finished.count() == 1
    assert not isValid(window)
    assert not isValid(animation)
    assert not isValid(overlay)
    assert isValid(transition)
    assert not transition._animations
    assert not transition._animationsByWindow

    del destroyed, finished, window, animation, overlay
    assert all(reference() is None for reference in references)
    deleteQObject(transition)
    del transition
    processQtEvents()
''',
            timeout=30,
        )

        assertChildSucceeded(self, result, 'window deletion during resize delivery')

    def testDeferredGeometryCompletionIsFlushedBeforeReplacementOrStop(self):
        """Retire one pending completion without finishing the replacement."""
        for replace in (False, True):
            with self.subTest(replace=replace):
                window = self.createWindow()
                transition = self.createTransition([window], duration=100000)
                finished = QSignalSpy(transition.transitionFinished)

                transition.apply(lambda: None)

                window.resize(330, 190)

                self.assertFalse(transition.isRunning())
                self.assertEqual(finished.count(), 0)

                if replace:
                    transition.apply(lambda: None)

                    self.assertTrue(transition.isRunning())
                    self.assertEqual(finished.count(), 1)

                    processQtEvents()

                    self.assertTrue(transition.isRunning())
                    self.assertEqual(finished.count(), 1)

                transition.stop()
                processQtEvents()

                self.assertFalse(transition.isRunning())
                self.assertEqual(finished.count(), 2 if replace else 1)

    def testCoordinatorDestructionCancelsDeferredGeometryCompletion(self):
        """A queued notification cannot outlive its coordinator or timer."""
        window = self.createWindow()
        owner = QtCore.QObject()
        transition = ThemeTransition(
            parent=owner,
            duration=100000,
            windowProvider=lambda: (window,),
            animationsEnabled=lambda: True,
        )
        finished = QSignalSpy(transition.transitionFinished)
        timer = transition._completionTimer

        transition.apply(lambda: None)

        window.resize(330, 190)

        self.assertEqual(finished.count(), 0)
        self.assertTrue(timer.isActive())

        deleteQObject(owner)
        processQtEvents()

        self.assertFalse(isValid(transition))
        self.assertFalse(isValid(timer))
        self.assertEqual(finished.count(), 0)
        self.assertEqual(self.overlays(window), [])

    def testReentrantCoordinatorDestructionClearsStateAndCancelsContinuation(self):
        """Callbacks may delete the coordinator before animation acquisition/start."""
        application()

        for boundary in ('theme', 'started', 'finished'):
            for _ in range(20):
                window = QWidget()
                window.resize(160, 100)
                window.show()
                processQtEvents()

                transition = ThemeTransition(
                    duration=100000,
                    windowProvider=lambda: (window,),
                    animationsEnabled=lambda: True,
                )
                reference = weakref.ref(transition)

                with mock.patch('sys.excepthook') as exceptionHook:
                    if boundary == 'theme':
                        transition.apply(lambda: deleteQObject(transition))
                    elif boundary == 'started':
                        transition.transitionStarted.connect(
                            lambda: deleteQObject(transition)
                        )

                        transition.apply(lambda: None)
                    else:
                        transition.apply(lambda: None)
                        transition.transitionFinished.connect(
                            lambda: deleteQObject(transition)
                        )

                        window.resize(170, 110)

                    processQtEvents()

                    exceptionHook.assert_not_called()

                self.assertFalse(isValid(transition))
                self.assertFalse(transition._animations)
                self.assertFalse(transition._animationsByWindow)
                self.assertFalse(self.overlays(window))

                del transition

                self.assertIsNone(reference())

                deleteQObject(window)
                processQtEvents()

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

    def testWindowDestructionReleasesCoordinatorAnimationState(self):
        """Deleting a target must not leave its stopped animation registered."""
        windows = []
        transition = self.createTransition(windows, duration=100000)

        for _ in range(30):
            window = QWidget()
            window.show()
            processQtEvents()

            windows[:] = [window]

            transition.apply(lambda: None)
            animation = next(iter(transition._animations))

            window.deleteLater()
            processQtEvents()

            self.assertFalse(isValid(animation))
            self.assertEqual(transition._animations, {})
            self.assertEqual(transition._animationsByWindow, {})

    def testCoordinatorDestructionReleasesWindowOwnedOverlays(self):
        """Destroying the animation owner must also remove its snapshots."""
        window = self.createWindow()

        for _ in range(30):
            owner = QtCore.QObject()
            transition = ThemeTransition(
                owner,
                duration=100000,
                windowProvider=lambda: (window,),
                animationsEnabled=lambda: True,
            )

            transition.apply(lambda: None)
            overlays = self.overlays(window)

            self.assertEqual(len(overlays), 1)

            owner.deleteLater()
            processQtEvents()

            self.assertFalse(isValid(transition))
            self.assertFalse(isValid(overlays[0]))
            self.assertEqual(self.overlays(window), [])

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
