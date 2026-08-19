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

"""Present lazily rendered historical network metrics as an application page."""

from __future__ import annotations

from Furious.Frozenlib import Mixins
from Furious.Qt import AppQLabel
from Furious.Qt import gettext as _
from Furious.Service import (
    DOWNLOAD_SPEED_METRIC,
    DOWNLOAD_USAGE_METRIC,
    UPLOAD_SPEED_METRIC,
    UPLOAD_USAGE_METRIC,
    EndpointInfoService,
    MetricsDataManager,
    formatTrafficSpeed,
    formatTrafficUsage,
)
from Furious.Widget.EndpointInfoWidget import EndpointInfoWidget
from Furious.Widget.MetricsGraph import MetricsGraphWidget

from PySide6 import QtCore
from PySide6.QtWidgets import *

import time

__all__ = ['MetricsPage']


class _MetricCard(QFrame):
    """Frame one graph with a concise metric title."""

    def __init__(self, graph: MetricsGraphWidget, parent=None):
        """Initialize one graph card."""
        super().__init__(parent)

        self.setObjectName('MetricCard')
        self.titleLabel = AppQLabel(translatable=False, parent=self)
        self.titleLabel.setObjectName('MetricCardTitle')
        self.graph = graph
        self.graph.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.graph, 1)

    def setTitle(self, title: str):
        """Set the already translated metric title."""
        self.titleLabel.setText(title)
        self.graph.setMetricLabel(title)


class _MetricsSection(QFrame):
    """Group speed and traffic-usage graphs for one direction."""

    def __init__(self, speedGraph, usageGraph, parent=None):
        """Initialize a two-card metrics section."""
        super().__init__(parent)

        self.setObjectName('MetricsSection')
        self.titleLabel = AppQLabel(translatable=False, parent=self)
        self.titleLabel.setObjectName('MetricsSectionTitle')
        self.speedCard = _MetricCard(speedGraph, parent=self)
        self.usageCard = _MetricCard(usageGraph, parent=self)

        graphLayout = QHBoxLayout()
        graphLayout.setContentsMargins(0, 0, 0, 0)
        graphLayout.setSpacing(12)
        graphLayout.addWidget(self.speedCard, 1)
        graphLayout.addWidget(self.usageCard, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.titleLabel)
        layout.addLayout(graphLayout, 1)

    def setTitles(self, sectionTitle, speedTitle, usageTitle):
        """Set translated section and graph-card titles."""
        self.titleLabel.setText(sectionTitle)
        self.speedCard.setTitle(speedTitle)
        self.usageCard.setTitle(usageTitle)


class MetricsPage(Mixins.QTranslatable, Mixins.ThemeAware, QMainWindow):
    """Coordinate time controls and visible-only graph rendering."""

    RenderDelay = 100
    TimelineRefreshInterval = 1000
    DefaultTimeRange = 15 * 60
    DefaultGranularity = 0

    def __init__(
        self,
        manager: MetricsDataManager,
        parent=None,
        *,
        endpointInfoService=None,
    ):
        """Initialize the network metrics page around a data-only manager."""
        super().__init__(parent)

        if not isinstance(manager, MetricsDataManager):
            raise TypeError('manager must be a MetricsDataManager')

        self.setObjectName('MetricsPage')
        self.manager = manager

        if endpointInfoService is None:
            self.endpointInfoService = EndpointInfoService(parent=self)
        else:
            self.endpointInfoService = endpointInfoService

        self._dirty = True
        self._renderRevision = 0

        self.pageTitleLabel = AppQLabel(translatable=False)
        self.pageTitleLabel.setObjectName('MetricsPageTitle')
        self.timeRangeLabel = AppQLabel(translatable=False)
        self.granularityLabel = AppQLabel(translatable=False)
        self.timeRangeComboBox = QComboBox()
        self.granularityComboBox = QComboBox()
        self.timeRangeComboBox.setMinimumWidth(160)
        self.granularityComboBox.setMinimumWidth(130)

        self.downloadSpeedGraph = MetricsGraphWidget(
            MetricsGraphWidget.Download,
            formatTrafficSpeed,
        )
        self.downloadUsageGraph = MetricsGraphWidget(
            MetricsGraphWidget.Download,
            formatTrafficUsage,
        )
        self.uploadSpeedGraph = MetricsGraphWidget(
            MetricsGraphWidget.Upload,
            formatTrafficSpeed,
        )
        self.uploadUsageGraph = MetricsGraphWidget(
            MetricsGraphWidget.Upload,
            formatTrafficUsage,
        )

        self.downloadSection = _MetricsSection(
            self.downloadSpeedGraph,
            self.downloadUsageGraph,
        )
        self.uploadSection = _MetricsSection(
            self.uploadSpeedGraph,
            self.uploadUsageGraph,
        )

        self.endpointInfoWidget = EndpointInfoWidget(
            self.endpointInfoService,
            parent=self,
        )
        self.endpointInfoWidget.setVisible(self.endpointInfoService.enabled)

        self.endpointInfoService.enabledChanged.connect(
            self._endpointInfoEnabledChanged
        )

        controlsLayout = QHBoxLayout()
        controlsLayout.setContentsMargins(0, 0, 0, 0)
        controlsLayout.setSpacing(8)
        controlsLayout.addWidget(self.pageTitleLabel)
        controlsLayout.addStretch(1)
        controlsLayout.addWidget(self.timeRangeLabel)
        controlsLayout.addWidget(self.timeRangeComboBox)
        controlsLayout.addSpacing(8)
        controlsLayout.addWidget(self.granularityLabel)
        controlsLayout.addWidget(self.granularityComboBox)

        contentWidget = QWidget()
        contentWidget.setObjectName('MetricsPageContent')
        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(20, 18, 20, 20)
        contentLayout.setSpacing(14)
        contentLayout.addLayout(controlsLayout)
        contentLayout.addWidget(self.downloadSection, 1)
        contentLayout.addWidget(self.uploadSection, 1)
        contentLayout.addWidget(self.endpointInfoWidget)

        self.scrollArea = QScrollArea()
        self.scrollArea.setObjectName('MetricsScrollArea')
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setWidget(contentWidget)
        self.setCentralWidget(self.scrollArea)

        self._renderTimer = QtCore.QTimer(self)
        self._renderTimer.setSingleShot(True)
        self._renderTimer.setInterval(self.RenderDelay)
        self._renderTimer.timeout.connect(self._renderLatest)

        # This timer advances only the visible rolling window. Statistics
        # collection remains independent, and hidden pages do no graph work.
        self._timelineTimer = QtCore.QTimer(self)
        self._timelineTimer.setInterval(self.TimelineRefreshInterval)
        self._timelineTimer.timeout.connect(self._timelineAdvanced)

        self.manager.historyChanged.connect(self._historyChanged)
        self.timeRangeComboBox.currentIndexChanged.connect(self._selectionChanged)
        self.granularityComboBox.currentIndexChanged.connect(self._selectionChanged)

        self.retranslate()

    @staticmethod
    def _timeRangeOptions():
        """Return selectable ranges in short-to-long order."""
        return (
            (5 * 60, _('Last 5 minutes')),
            (15 * 60, _('Last 15 minutes')),
            (60 * 60, _('Last hour')),
            (6 * 60 * 60, _('Last 6 hours')),
            (24 * 60 * 60, _('Last 24 hours')),
        )

    @staticmethod
    def _granularityOptions():
        """Return selectable aggregation granularities."""
        return (
            (0, _('Auto')),
            (2, _('2 seconds')),
            (10, _('10 seconds')),
            (60, _('1 minute')),
            (5 * 60, _('5 minutes')),
        )

    @staticmethod
    def _populateComboBox(comboBox, options, selectedValue):
        """Rebuild translated choices while preserving semantic data."""
        blocker = QtCore.QSignalBlocker(comboBox)

        comboBox.clear()

        for value, text in options:
            comboBox.addItem(text, value)

        selectedIndex = comboBox.findData(selectedValue)

        comboBox.setCurrentIndex(max(selectedIndex, 0))

        del blocker

    def _pageCanRender(self) -> bool:
        """Return whether painting work can currently reach the screen."""
        window = self.window()

        return self.isVisible() and not (
            hasattr(window, 'isMinimized') and window.isMinimized()
        )

    def _scheduleRender(self):
        """Coalesce visible history updates into one graph refresh."""
        if self._pageCanRender() and not self._renderTimer.isActive():
            self._renderTimer.start()

    @QtCore.Slot()
    def _historyChanged(self):
        """Mark graph data stale without touching hidden graph widgets."""
        self._dirty = True
        self._scheduleRender()

    @QtCore.Slot(bool)
    def setEndpointInfoEnabled(self, enabled: bool):
        """Apply the persisted endpoint-inspection preference to the page service."""
        self.endpointInfoService.setEnabled(enabled)

    @QtCore.Slot(bool)
    def _endpointInfoEnabledChanged(self, enabled: bool):
        """Remove the privacy-sensitive section entirely while it is disabled."""
        self.endpointInfoWidget.setVisible(enabled)

    @QtCore.Slot()
    def _selectionChanged(self):
        """Refresh visible graphs after range or granularity selection."""
        self._dirty = True
        self._scheduleRender()

    @QtCore.Slot()
    def _timelineAdvanced(self):
        """Move the visible time window without altering stored samples."""
        if not self._pageCanRender():
            return

        self._dirty = True
        self._scheduleRender()

    @QtCore.Slot()
    def _renderLatest(self):
        """Prepare and submit graph series only while the page is visible."""
        if not self._dirty or not self._pageCanRender():
            return

        rangeSeconds = float(
            self.timeRangeComboBox.currentData() or self.DefaultTimeRange
        )
        granularity = float(
            self.granularityComboBox.currentData() or self.DefaultGranularity
        )
        currentTime = time.monotonic()
        currentWallTime = time.time()
        graphMetrics = (
            (self.downloadSpeedGraph, DOWNLOAD_SPEED_METRIC),
            (self.downloadUsageGraph, DOWNLOAD_USAGE_METRIC),
            (self.uploadSpeedGraph, UPLOAD_SPEED_METRIC),
            (self.uploadUsageGraph, UPLOAD_USAGE_METRIC),
        )

        for graph, metricKey in graphMetrics:
            graph.setSeries(
                self.manager.series(
                    metricKey,
                    rangeSeconds,
                    granularity,
                    now=currentTime,
                ),
                rangeSeconds,
                currentTime,
                currentWallTime,
            )

        self._dirty = False
        self._renderRevision += 1

    def showEvent(self, event):
        """Render the latest retained history when the page becomes visible."""
        super().showEvent(event)

        self._dirty = True
        self._timelineTimer.start()
        self.endpointInfoService.setPageVisible(True)
        self._scheduleRender()

    def hideEvent(self, event):
        """Stop pending rendering while leaving data collection untouched."""
        self._renderTimer.stop()
        self._timelineTimer.stop()
        self._dirty = True
        self.endpointInfoService.setPageVisible(False)

        super().hideEvent(event)

    def themeChangedCallback(self, theme: str):
        """Repaint custom graphs for a theme change only when visible."""
        self._dirty = True
        self.endpointInfoWidget.themeChangedCallback(theme)
        self._scheduleRender()

    def retranslate(self):
        """Refresh page, section, graph, and selector text."""
        selectedRange = self.timeRangeComboBox.currentData() or self.DefaultTimeRange
        selectedGranularity = (
            self.granularityComboBox.currentData()
            if self.granularityComboBox.count()
            else self.DefaultGranularity
        )

        self.pageTitleLabel.setText(_('Network Metrics'))
        self.timeRangeLabel.setText(_('Time Range'))
        self.granularityLabel.setText(_('Granularity'))
        self.downloadSection.setTitles(
            _('Download'),
            _('Download Speed'),
            _('Download Traffic Usage'),
        )
        self.uploadSection.setTitles(
            _('Upload'),
            _('Upload Speed'),
            _('Upload Traffic Usage'),
        )
        self.endpointInfoWidget.retranslate()

        self._populateComboBox(
            self.timeRangeComboBox,
            self._timeRangeOptions(),
            selectedRange,
        )
        self._populateComboBox(
            self.granularityComboBox,
            self._granularityOptions(),
            selectedGranularity,
        )

        self._dirty = True
        self._scheduleRender()
