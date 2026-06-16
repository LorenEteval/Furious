"""
The MIT License (MIT)

Copyright (c) 2012-2014 Alexander Turkin
Copyright (c) 2014 William Hallatt
Copyright (c) 2015 Jacob Dawid
Copyright (c) 2016 Luca Weiss
Copyright (c) 2017 fbjorn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

import math

__all__ = ['WaitingSpinner']


# pylint: disable=too-many-instance-attributes,too-many-arguments
class WaitingSpinner(QWidget):
    """WaitingSpinner is a highly configurable, custom spinner widget."""

    def __init__(
        self,
        parent: QWidget,
        center_on_parent: bool = True,
        disable_parent_when_spinning: bool = False,
        modality: Qt.WindowModality = Qt.WindowModality.NonModal,
        roundness: float = 100.0,
        fade: float = 80.0,
        lines: int = 20,
        line_length: int = 10,
        line_width: int = 2,
        radius: int = 10,
        speed: float = math.pi / 2,
        color: QColor = QColor(0, 0, 0),
    ) -> None:
        super().__init__(parent)

        self._center_on_parent: bool = center_on_parent
        self._disable_parent_when_spinning: bool = disable_parent_when_spinning

        self._color: QColor = color
        self._roundness: float = roundness
        self._minimum_trail_opacity: float = math.pi
        self._trail_fade_percentage: float = fade
        self._revolutions_per_second: float = speed
        self._number_of_lines: int = lines
        self._line_length: int = line_length
        self._line_width: int = line_width
        self._inner_radius: int = radius
        self._current_counter: int = 0
        self._is_spinning: bool = False

        self._timer: QTimer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._update_size()
        self._update_timer()
        self.hide()

        self.setWindowModality(modality)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _: QPaintEvent) -> None:  # pylint: disable=invalid-name
        """Paint the WaitingSpinner."""
        self._update_position()

        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self._current_counter >= self._number_of_lines:
            self._current_counter = 0

        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(self._number_of_lines):
            painter.save()
            painter.translate(
                self._inner_radius + self._line_length,
                self._inner_radius + self._line_length,
            )

            rotate_angle = 360 * i / self._number_of_lines

            painter.rotate(rotate_angle)
            painter.translate(self._inner_radius, 0)

            distance = self._line_count_distance_from_primary(
                i, self._current_counter, self._number_of_lines
            )
            color = self._current_line_color(
                distance,
                self._number_of_lines,
                self._trail_fade_percentage,
                self._minimum_trail_opacity,
                self._color,
            )

            painter.setBrush(color)
            painter.drawRoundedRect(
                QRect(
                    0,
                    -self._line_width // 2,
                    self._line_length,
                    self._line_width,
                ),
                self._roundness,
                self._roundness,
                Qt.SizeMode.RelativeSize,
            )
            painter.restore()

    def start(self) -> None:
        """Show and start spinning the WaitingSpinner."""
        self._update_position()
        self._is_spinning = True
        self.show()

        if self.parentWidget and self._disable_parent_when_spinning:
            self.parentWidget().setEnabled(False)

        if not self._timer.isActive():
            self._timer.start()
            self._current_counter = 0

    def stop(self) -> None:
        """Hide and stop spinning the WaitingSpinner."""
        self._is_spinning = False
        self.hide()

        if self.parentWidget() and self._disable_parent_when_spinning:
            self.parentWidget().setEnabled(True)

        if self._timer.isActive():
            self._timer.stop()
            self._current_counter = 0

    @property
    def color(self) -> QColor:
        """Return color of WaitingSpinner."""
        return self._color

    @color.setter
    def color(self, color: Qt.GlobalColor = Qt.GlobalColor.black) -> None:
        """Set color of WaitingSpinner."""
        self._color = QColor(color)

    @property
    def roundness(self) -> float:
        """Return roundness of WaitingSpinner."""
        return self._roundness

    @roundness.setter
    def roundness(self, roundness: float) -> None:
        """Set color of WaitingSpinner."""
        self._roundness = max(0.0, min(100.0, roundness))

    @property
    def minimum_trail_opacity(self) -> float:
        """Return minimum trail opacity of WaitingSpinner."""
        return self._minimum_trail_opacity

    @minimum_trail_opacity.setter
    def minimum_trail_opacity(self, minimum_trail_opacity: float) -> None:
        """Set minimum trail opacity of WaitingSpinner."""
        self._minimum_trail_opacity = minimum_trail_opacity

    @property
    def trail_fade_percentage(self) -> float:
        """Return trail fade percentage of WaitingSpinner."""
        return self._trail_fade_percentage

    @trail_fade_percentage.setter
    def trail_fade_percentage(self, trail: float) -> None:
        """Set trail fade percentage of WaitingSpinner."""
        self._trail_fade_percentage = trail

    @property
    def revolutions_per_second(self) -> float:
        """Return revolutions per second of WaitingSpinner."""
        return self._revolutions_per_second

    @revolutions_per_second.setter
    def revolutions_per_second(self, revolutions_per_second: float) -> None:
        """Set revolutions per second of WaitingSpinner."""
        self._revolutions_per_second = revolutions_per_second
        self._update_timer()

    @property
    def number_of_lines(self) -> int:
        """Return number of lines of WaitingSpinner."""
        return self._number_of_lines

    @number_of_lines.setter
    def number_of_lines(self, lines: int) -> None:
        """Set number of lines of WaitingSpinner."""
        self._number_of_lines = lines
        self._current_counter = 0
        self._update_timer()

    @property
    def line_length(self) -> int:
        """Return line length of WaitingSpinner."""
        return self._line_length

    @line_length.setter
    def line_length(self, length: int) -> None:
        """Set line length of WaitingSpinner."""
        self._line_length = length
        self._update_size()

    @property
    def line_width(self) -> int:
        """Return line width of WaitingSpinner."""
        return self._line_width

    @line_width.setter
    def line_width(self, width: int) -> None:
        """Set line width of WaitingSpinner."""
        self._line_width = width
        self._update_size()

    @property
    def inner_radius(self) -> int:
        """Return inner radius size of WaitingSpinner."""
        return self._inner_radius

    @inner_radius.setter
    def inner_radius(self, radius: int) -> None:
        """Set inner radius size of WaitingSpinner."""
        self._inner_radius = radius
        self._update_size()

    @property
    def is_spinning(self) -> bool:
        """Return actual spinning status of WaitingSpinner."""
        return self._is_spinning

    def _rotate(self) -> None:
        """Rotate the WaitingSpinner."""
        self._current_counter += 1
        if self._current_counter >= self._number_of_lines:
            self._current_counter = 0
        self.update()

    def _update_size(self) -> None:
        """Update the size of the WaitingSpinner."""
        size = (self._inner_radius + self._line_length) * 2
        self.setFixedSize(size, size)

    def _update_timer(self) -> None:
        """Update the spinning speed of the WaitingSpinner."""
        self._timer.setInterval(
            int(1000 / (self._number_of_lines * self._revolutions_per_second))
        )

    def _update_position(self) -> None:
        """Center WaitingSpinner on parent widget."""
        if self.parentWidget() and self._center_on_parent:
            self.move(
                (self.parentWidget().width() - self.width()) // 2,
                (self.parentWidget().height() - self.height()) // 2,
            )

    @staticmethod
    def _line_count_distance_from_primary(
        current: int, primary: int, total_nr_of_lines: int
    ) -> int:
        """Return the amount of lines from _current_counter."""
        distance = primary - current
        if distance < 0:
            distance += total_nr_of_lines
        return distance

    @staticmethod
    def _current_line_color(
        count_distance: int,
        total_nr_of_lines: int,
        trail_fade_perc: float,
        min_opacity: float,
        color_input: QColor,
    ) -> QColor:
        """Returns the current color for the WaitingSpinner."""
        color = QColor(color_input)
        if count_distance == 0:
            return color
        min_alpha_f = min_opacity / 100.0
        distance_threshold = int(
            math.ceil((total_nr_of_lines - 1) * trail_fade_perc / 100.0)
        )
        if count_distance > distance_threshold:
            color.setAlphaF(min_alpha_f)
        else:
            alpha_diff = color.alphaF() - min_alpha_f
            gradient = alpha_diff / float(distance_threshold + 1)
            result_alpha = color.alphaF() - gradient * count_distance
            # If alpha is out of bounds, clip it.
            result_alpha = min(1.0, max(0.0, result_alpha))
            color.setAlphaF(result_alpha)
        return color
