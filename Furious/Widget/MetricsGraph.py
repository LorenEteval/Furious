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

"""Render lightweight time-series metrics with Qt's painting primitives."""

from __future__ import annotations

from Furious.Frozenlib import APP
from Furious.Qt import AppStyleSheet
from Furious.Qt import gettext as _
from Furious.Service.MetricsDataManager import MetricPoint

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from typing import Callable, Iterable

import bisect
import time

__all__ = ['MetricsGraphWidget']


class MetricsGraphWidget(QWidget):
    """Paint one prepared metric series without owning collection logic."""

    Download = 'download'
    Upload = 'upload'
    Directions = (Download, Upload)

    LeftMargin = 82
    TopMargin = 16
    RightMargin = 16
    BottomMargin = 30
    HorizontalGridLines = 4
    VerticalGridLines = 4
    HoverDistance = 18

    def __init__(self, direction: str, valueFormatter: Callable, parent=None):
        """Initialize an empty graph for one traffic direction."""
        super().__init__(parent)

        if direction not in self.Directions:
            raise ValueError(f'unsupported metrics direction: {direction}')

        if not callable(valueFormatter):
            raise TypeError('valueFormatter must be callable')

        self._direction = direction
        self._valueFormatter = valueFormatter
        self._points = tuple()
        self._pointTimes = tuple()
        self._rangeSeconds = 300.0
        self._currentTime = 0.0
        self._currentWallTime = 0.0
        self._metricLabel = ''
        self._hoveredPoint = None

        self.setObjectName('MetricsGraphWidget')
        self.setMouseTracking(True)
        self.setMinimumSize(340, 220)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def setSeries(
        self,
        points: Iterable[MetricPoint],
        rangeSeconds: float,
        currentTime: float,
        currentWallTime=None,
    ):
        """Replace the prepared series and schedule one repaint."""
        self._points = tuple(
            point for point in points if isinstance(point, MetricPoint)
        )
        self._pointTimes = tuple(point.sampledAt for point in self._points)
        self._rangeSeconds = max(float(rangeSeconds), 1.0)
        self._currentTime = float(currentTime)
        self._currentWallTime = (
            time.time() if currentWallTime is None else float(currentWallTime)
        )

        if self.underMouse():
            self._updateHover(self.mapFromGlobal(QtGui.QCursor.pos()))
        else:
            self._clearHover()

        self.update()

    def setMetricLabel(self, label: str):
        """Set the translated metric name displayed in hover details."""
        self._metricLabel = str(label)

    def clear(self):
        """Discard displayed points and schedule one repaint."""
        if not self._points:
            return

        self._points = tuple()
        self._pointTimes = tuple()
        self._clearHover()
        self.update()

    def _palette(self):
        """Return the current application palette for custom painting."""
        return AppStyleSheet.paletteForTheme(APP().theme())

    def _lineColor(self, palette):
        """Return the semantic line color for this traffic direction."""
        return QtGui.QColor(palette[f'metrics_{self._direction}'])

    def _fillColor(self, palette):
        """Return the semantic area-fill color for this traffic direction."""
        return QtGui.QColor(palette[f'metrics_{self._direction}_fill'])

    @staticmethod
    def _relativeTimeLabel(seconds: float) -> str:
        """Return a compact negative offset label for the horizontal axis."""
        seconds = max(float(seconds), 0.0)

        if seconds >= 3600:
            hours = seconds / 3600
            value = f'{hours:.1f}'.rstrip('0').rstrip('.')

            return f'-{value}h'

        if seconds >= 60:
            minutes = seconds / 60
            value = f'{minutes:.1f}'.rstrip('0').rstrip('.')

            return f'-{value}m'

        return f'-{int(round(seconds))}s'

    def _chartRect(self) -> QtCore.QRectF:
        """Return the drawable plot rectangle inside axis-label margins."""
        return QtCore.QRectF(
            self.LeftMargin,
            self.TopMargin,
            max(self.width() - self.LeftMargin - self.RightMargin, 1),
            max(self.height() - self.TopMargin - self.BottomMargin, 1),
        )

    def _drawGrid(self, painter, chartRect, palette, maximumValue):
        """Draw subtle Fluent-style grid lines and compact axis labels."""
        gridPen = QtGui.QPen(QtGui.QColor(palette['metrics_grid']))
        gridPen.setWidthF(1.0)

        painter.setPen(gridPen)

        labelColor = QtGui.QColor(palette['metrics_axis'])

        labelFont = QtGui.QFont(self.font())
        labelFont.setPointSizeF(max(labelFont.pointSizeF() - 1, 7))

        painter.setFont(labelFont)

        for index in range(self.HorizontalGridLines + 1):
            ratio = index / self.HorizontalGridLines
            y = chartRect.bottom() - (ratio * chartRect.height())

            painter.drawLine(
                QtCore.QPointF(chartRect.left(), y),
                QtCore.QPointF(chartRect.right(), y),
            )

            value = maximumValue * ratio
            labelRect = QtCore.QRectF(
                0,
                y - 10,
                self.LeftMargin - 8,
                20,
            )

            painter.setPen(labelColor)
            painter.drawText(
                labelRect,
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter,
                self._valueFormatter(value),
            )
            painter.setPen(gridPen)

        for index in range(self.VerticalGridLines + 1):
            ratio = index / self.VerticalGridLines
            x = chartRect.left() + (ratio * chartRect.width())

            painter.drawLine(
                QtCore.QPointF(x, chartRect.top()),
                QtCore.QPointF(x, chartRect.bottom()),
            )

            if index == self.VerticalGridLines:
                label = _('Now')
            else:
                label = self._relativeTimeLabel(self._rangeSeconds * (1.0 - ratio))

            labelRect = QtCore.QRectF(
                x - 40,
                chartRect.bottom() + 5,
                80,
                self.BottomMargin - 5,
            )

            painter.setPen(labelColor)
            painter.drawText(
                labelRect,
                QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop,
                label,
            )
            painter.setPen(gridPen)

    def _drawEmptyState(self, painter, chartRect, palette):
        """Describe why a graph has no line without fabricating data."""
        painter.setPen(QtGui.QColor(palette['metrics_axis']))
        painter.drawText(
            chartRect,
            QtCore.Qt.AlignmentFlag.AlignCenter,
            _('Waiting for network statistics'),
        )

    def _pointPosition(self, point, chartRect, maximumValue):
        """Map one metric point into plot coordinates."""
        startTime = self._currentTime - self._rangeSeconds
        xRatio = min(
            max((point.sampledAt - startTime) / self._rangeSeconds, 0.0),
            1.0,
        )
        yRatio = min(max(point.value / maximumValue, 0.0), 1.0)

        return QtCore.QPointF(
            chartRect.left() + (xRatio * chartRect.width()),
            chartRect.bottom() - (yRatio * chartRect.height()),
        )

    def _graphPath(self, chartRect, maximumValue):
        """Convert prepared metric points into a painter path."""
        path = QtGui.QPainterPath()

        for index, point in enumerate(self._points):
            pointPosition = self._pointPosition(point, chartRect, maximumValue)

            if index == 0:
                path.moveTo(pointPosition)
            else:
                path.lineTo(pointPosition)

        return path

    def _maximumValue(self):
        """Return the padded vertical-axis maximum for current points."""
        maximumValue = max(
            (point.value for point in self._points),
            default=0.0,
        )

        return max(maximumValue * 1.1, 1.0)

    def _nearestPoint(self, position):
        """Return the point nearest the cursor's horizontal time position."""
        if not self._points:
            return None

        chartRect = self._chartRect()

        if not chartRect.contains(QtCore.QPointF(position)):
            return None

        ratio = (position.x() - chartRect.left()) / chartRect.width()
        targetTime = (
            self._currentTime - self._rangeSeconds
        ) + ratio * self._rangeSeconds
        insertionIndex = bisect.bisect_left(self._pointTimes, targetTime)
        candidates = []

        if insertionIndex < len(self._points):
            candidates.append(self._points[insertionIndex])

        if insertionIndex > 0:
            candidates.append(self._points[insertionIndex - 1])

        nearest = min(
            candidates,
            key=lambda point: abs(point.sampledAt - targetTime),
            default=None,
        )

        if nearest is None:
            return None

        pointPosition = self._pointPosition(
            nearest,
            chartRect,
            self._maximumValue(),
        )

        if abs(pointPosition.x() - position.x()) > self.HoverDistance:
            return None

        return nearest

    def _tooltipText(self, point) -> str:
        """Return timestamp and formatted metric details for one point."""
        recordedAt = self._currentWallTime - (self._currentTime - point.sampledAt)
        timestamp = QtCore.QDateTime.fromMSecsSinceEpoch(
            int(recordedAt * 1000)
        ).toString('yyyy-MM-dd HH:mm:ss')
        value = self._valueFormatter(point.value)

        if self._metricLabel:
            value = f'{self._metricLabel}: {value}'

        return f'{timestamp}\n{value}'

    def _clearHover(self):
        """Clear hover state and dismiss the native Qt tooltip."""
        changed = self._hoveredPoint is not None

        self._hoveredPoint = None

        if changed:
            QToolTip.hideText()

            self.update()

    def _updateHover(self, position):
        """Select the nearest graph point and show its native tooltip."""
        point = self._nearestPoint(position)

        if point is None:
            self._clearHover()

            return

        changed = point is not self._hoveredPoint

        self._hoveredPoint = point

        tooltipPosition = self.mapToGlobal(position) + QtCore.QPoint(14, 18)

        QToolTip.showText(
            tooltipPosition,
            self._tooltipText(point),
            self,
        )

        if changed:
            self.update()

    def _drawHover(self, painter, chartRect, maximumValue, palette):
        """Draw a crosshair and highlighted marker for the hovered point."""
        if self._hoveredPoint is None:
            return

        pointPosition = self._pointPosition(
            self._hoveredPoint,
            chartRect,
            maximumValue,
        )

        crosshairColor = QtGui.QColor(palette['metrics_axis'])
        crosshairColor.setAlpha(150)

        crosshairPen = QtGui.QPen(crosshairColor)
        crosshairPen.setStyle(QtCore.Qt.PenStyle.DashLine)

        painter.setPen(crosshairPen)
        painter.drawLine(
            QtCore.QPointF(pointPosition.x(), chartRect.top()),
            QtCore.QPointF(pointPosition.x(), chartRect.bottom()),
        )
        painter.setBrush(QtGui.QColor(palette['panel_alt']))

        markerPen = QtGui.QPen(self._lineColor(palette))
        markerPen.setWidthF(2.5)

        painter.setPen(markerPen)
        painter.drawEllipse(pointPosition, 5.0, 5.0)

    def mouseMoveEvent(self, event):
        """Inspect the graph point nearest the moving cursor."""
        self._updateHover(event.position().toPoint())

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Dismiss hover details when the cursor leaves the graph."""
        self._clearHover()

        super().leaveEvent(event)

    def hideEvent(self, event):
        """Dismiss hover details when lazy page rendering becomes hidden."""
        self._clearHover()

        super().hideEvent(event)

    def paintEvent(self, event):
        """Paint axes, an optional area fill, and the current metric line."""
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        palette = self._palette()
        chartRect = self._chartRect()
        maximumValue = self._maximumValue()

        self._drawGrid(painter, chartRect, palette, maximumValue)

        if not self._points:
            self._drawEmptyState(painter, chartRect, palette)
            painter.end()

            return

        path = self._graphPath(chartRect, maximumValue)

        fillPath = QtGui.QPainterPath(path)
        fillPath.lineTo(path.currentPosition().x(), chartRect.bottom())
        fillPath.lineTo(path.elementAt(0).x, chartRect.bottom())
        fillPath.closeSubpath()

        fillColor = self._fillColor(palette)

        transparentFill = QtGui.QColor(fillColor)
        transparentFill.setAlpha(0)
        gradient = QtGui.QLinearGradient(
            chartRect.topLeft(),
            chartRect.bottomLeft(),
        )

        gradient.setColorAt(0.0, fillColor)
        gradient.setColorAt(1.0, transparentFill)

        painter.fillPath(fillPath, gradient)

        linePen = QtGui.QPen(self._lineColor(palette))
        linePen.setWidthF(2.25)
        linePen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        linePen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)

        painter.setPen(linePen)
        painter.drawPath(path)

        painter.setBrush(self._lineColor(palette))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(path.currentPosition(), 3.5, 3.5)

        self._drawHover(painter, chartRect, maximumValue, palette)

        painter.end()
