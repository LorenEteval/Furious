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

"""Provide one application-wide, interruption-safe theme cross-fade."""

from __future__ import annotations

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QApplication, QStyle, QWidget

from .Signals import connectWeakly

from shiboken6 import isValid

from collections.abc import Callable, Iterable

__all__ = ['ThemeTransition']


class _ThemeSnapshotOverlay(QWidget):
    """Paint one old-theme window snapshot without intercepting input."""

    def __init__(self, snapshot: QtGui.QPixmap, parent: QWidget):
        """Initialize an overlay owned by its source top-level window."""
        super().__init__(parent)

        self._snapshot = snapshot
        self._opacity = 1.0

        self.setObjectName(ThemeTransition.OverlayObjectName)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.setGeometry(parent.rect())

    def opacity(self) -> float:
        """Return the currently painted snapshot opacity."""
        return self._opacity

    def setOpacity(self, opacity: float):
        """Set the snapshot opacity and schedule a repaint."""
        opacity = min(max(float(opacity), 0.0), 1.0)

        if self._opacity == opacity:
            return

        self._opacity = opacity
        self.update()

    opacityValue = QtCore.Property(float, opacity, setOpacity)

    def paintEvent(self, _event):
        """Paint the device-pixel-ratio-aware snapshot."""
        painter = QtGui.QPainter(self)
        painter.setOpacity(self._opacity)
        painter.drawPixmap(QtCore.QPoint(0, 0), self._snapshot)


class ThemeTransition(QtCore.QObject):
    """Cross-fade visible top-level widgets after an immediate theme change."""

    DefaultDuration = 500
    OverlayObjectName = 'FuriousThemeTransitionOverlay'

    transitionStarted = QtCore.Signal()
    transitionFinished = QtCore.Signal()

    def __init__(
        self,
        parent=None,
        *,
        duration: int = DefaultDuration,
        windowProvider: Callable[[], Iterable[QWidget]] | None = None,
        animationsEnabled: Callable[[], bool] | None = None,
    ):
        """Initialize the process-lifetime transition coordinator."""
        super().__init__(parent)

        self._duration = max(int(duration), 1)
        self._windowProvider = windowProvider or QApplication.topLevelWidgets
        self._animationsEnabled = animationsEnabled
        self._animations = {}
        self._animationsByWindow = {}

    def isRunning(self) -> bool:
        """Return whether any window snapshot is currently fading."""
        return bool(self._animations)

    def activeOverlayCount(self) -> int:
        """Return the number of active per-window snapshot overlays."""
        return len(self._animations)

    def _styleAllowsAnimations(self) -> bool:
        """Honor Qt's platform/style animation preference when available."""
        if self._animationsEnabled is not None:
            return bool(self._animationsEnabled())

        application = QApplication.instance()

        if application is None or application.closingDown():
            return False

        style = application.style()

        if style is None:
            return True

        duration = style.styleHint(QStyle.StyleHint.SH_Widget_Animation_Duration)

        return duration != 0

    @staticmethod
    def _canCapture(window) -> bool:
        """Return whether *window* is a visible application top-level widget."""
        return (
            isinstance(window, QWidget)
            and isValid(window)
            and window.isWindow()
            and window.isVisible()
            and not window.size().isEmpty()
            and window.windowType() != QtCore.Qt.WindowType.Desktop
        )

    def _captureWindows(self):
        """Capture each currently visible window, including an interrupted fade."""
        captures = []
        seen = set()

        for window in self._windowProvider():
            if not self._canCapture(window) or id(window) in seen:
                continue

            seen.add(id(window))
            snapshot = window.grab()

            if not snapshot.isNull():
                captures.append((window, snapshot))

        return captures

    def apply(self, applyTheme: Callable[[], None], *, animate: bool = True):
        """Apply a theme immediately and fade from the previously visible state."""
        if not callable(applyTheme):
            raise TypeError('theme application callback must be callable')

        captures = []

        if animate and self._styleAllowsAnimations():
            captures = self._captureWindows()

        # Capturing first preserves the user's current composite appearance when a
        # rapid second switch interrupts an in-progress transition.
        self.stop()

        applyTheme()

        for window, snapshot in captures:
            if not self._canCapture(window):
                continue

            overlay = _ThemeSnapshotOverlay(snapshot, window)

            animation = QtCore.QPropertyAnimation(
                overlay,
                b'opacityValue',
                self,
            )
            animation.setDuration(self._duration)
            animation.setStartValue(1.0)
            animation.setEndValue(0.0)
            animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

            self._animations[animation] = (window, overlay)
            self._animationsByWindow[window] = animation

            window.installEventFilter(self)

            connectWeakly(
                animation.finished,
                self,
                '_handleAnimationFinished',
                sender=animation,
                forwardSender=True,
            )

            overlay.show()
            overlay.raise_()

        if not self._animations:
            return

        self.transitionStarted.emit()

        for animation in tuple(self._animations):
            animation.start()

    def _releaseAnimation(self, animation, *, notify=True):
        """Release one animation and its transient overlay exactly once."""
        transition = self._animations.pop(animation, None)

        if transition is None:
            return

        window, overlay = transition

        self._animationsByWindow.pop(window, None)

        try:
            if isValid(window):
                window.removeEventFilter(self)
        except RuntimeError:
            pass

        if isValid(animation):
            animation.stop()
            animation.deleteLater()

        if isValid(overlay):
            overlay.hide()
            overlay.deleteLater()

        if notify and not self._animations:
            self.transitionFinished.emit()

    @QtCore.Slot(QtCore.QObject)
    def _handleAnimationFinished(self, animation):
        """Release the overlay belonging to a completed animation."""
        self._releaseAnimation(animation)

    def eventFilter(self, watched, event):
        """Drop stale snapshots when a transitioning window changes geometry."""
        if watched in self._animationsByWindow and event.type() in (
            QtCore.QEvent.Type.Resize,
            QtCore.QEvent.Type.WindowStateChange,
            QtCore.QEvent.Type.Hide,
            QtCore.QEvent.Type.Close,
            QtCore.QEvent.Type.Destroy,
        ):
            self._releaseAnimation(self._animationsByWindow.get(watched))

        return super().eventFilter(watched, event)

    def stop(self):
        """Stop and dispose every active transition without leaving an overlay."""
        wasRunning = self.isRunning()

        for animation in tuple(self._animations):
            self._releaseAnimation(animation, notify=False)

        if wasRunning:
            self.transitionFinished.emit()
