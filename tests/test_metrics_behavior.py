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

"""Protect rolling metrics history, aggregation, lazy rendering, and hover."""

from __future__ import annotations

from Furious.Qt import gettext as _
from Furious.Service.MetricsHistory import (
    DOWNLOAD_SPEED_METRIC,
    DOWNLOAD_USAGE_METRIC,
    UPLOAD_SPEED_METRIC,
    MetricSeriesPoint,
    MetricsHistory,
)
from Furious.Service.TrafficStatsManager import formatTrafficSpeed
from Furious.Widget.MetricsGraph import MetricsGraphWidget
from Furious.Window.MetricsPage import MetricsPage

from PySide6 import QtCore

from tests.support import application, collectAtBoundary, processQtEvents, waitFor

import math
import time
import unittest


class MetricsTimeSeriesBehaviorTest(unittest.TestCase):
    """Verify raw history and display buckets remain distinct and deterministic."""

    def testRawSamplesRemainImmutableAsVisibleWindowMoves(self):
        """Advance now without rewriting timestamps or historical metric values."""
        manager = MetricsHistory(maximumHistorySeconds=1000)
        manager.recordSample({DOWNLOAD_SPEED_METRIC: 10}, sampledAt=100)
        manager.recordSample({DOWNLOAD_SPEED_METRIC: 30}, sampledAt=104)
        manager.recordSample({DOWNLOAD_SPEED_METRIC: 50}, sampledAt=111)

        rawBefore = manager.rawSamples()
        valuesBefore = tuple(
            sample.values[DOWNLOAD_SPEED_METRIC] for sample in rawBefore
        )
        firstWindow = manager.series(
            DOWNLOAD_SPEED_METRIC,
            20,
            granularitySeconds=10,
            now=115,
        )
        secondWindow = manager.series(
            DOWNLOAD_SPEED_METRIC,
            20,
            granularitySeconds=10,
            now=118,
        )

        self.assertEqual(manager.rawSamples(), rawBefore)
        self.assertEqual(
            tuple(
                sample.values[DOWNLOAD_SPEED_METRIC] for sample in manager.rawSamples()
            ),
            valuesBefore,
        )
        self.assertEqual(firstWindow, secondWindow)
        self.assertEqual(
            tuple((point.sampledAt, point.value) for point in firstWindow),
            ((104.0, 20.0), (111.0, 50.0)),
        )
        self.assertGreater(
            MetricsGraphWidget._normalizedTimePosition(104, 20, 115),
            MetricsGraphWidget._normalizedTimePosition(104, 20, 118),
        )

    def testWindowEntryExitAndTimestampAlignedBuckets(self):
        """Drop old points naturally while stable absolute buckets retain values."""
        manager = MetricsHistory(maximumHistorySeconds=1000)

        for sampledAt, value in ((1, 10), (9, 30), (10, 50), (19, 70), (20, 90)):
            manager.recordSample(
                {
                    DOWNLOAD_SPEED_METRIC: value,
                    DOWNLOAD_USAGE_METRIC: value * 100,
                },
                sampledAt=sampledAt,
            )

        speedAt20 = manager.series(
            DOWNLOAD_SPEED_METRIC,
            20,
            granularitySeconds=10,
            now=20,
        )
        usageAt20 = manager.series(
            DOWNLOAD_USAGE_METRIC,
            20,
            granularitySeconds=10,
            now=20,
        )
        speedAt21 = manager.series(
            DOWNLOAD_SPEED_METRIC,
            20,
            granularitySeconds=10,
            now=21,
        )

        self.assertEqual(
            tuple((point.sampledAt, point.value) for point in speedAt20),
            ((9.0, 20.0), (19.0, 60.0), (20.0, 90.0)),
        )
        self.assertEqual(
            tuple((point.sampledAt, point.value) for point in usageAt20),
            ((9.0, 3000.0), (19.0, 7000.0), (20.0, 9000.0)),
        )
        self.assertEqual(
            tuple((point.sampledAt, point.value) for point in speedAt21),
            ((9.0, 20.0), (19.0, 60.0), (20.0, 90.0)),
        )

    def testAutoGranularityAndNonMonotonicInputArePredictable(self):
        """Select documented buckets and normalize backward timestamps safely."""
        manager = MetricsHistory(maximumHistorySeconds=24 * 60 * 60)

        self.assertEqual(manager.effectiveGranularity(5 * 60), 5)
        self.assertEqual(manager.effectiveGranularity(15 * 60), 10)
        self.assertEqual(manager.effectiveGranularity(60 * 60), 30)
        self.assertEqual(manager.effectiveGranularity(24 * 60 * 60), 15 * 60)
        self.assertEqual(manager.effectiveGranularity(60, 120), 60)

        manager.recordSample({UPLOAD_SPEED_METRIC: 10}, sampledAt=50)
        manager.recordSample({UPLOAD_SPEED_METRIC: 20}, sampledAt=40)

        self.assertEqual(
            tuple(sample.sampledAt for sample in manager.rawSamples()),
            (50.0, 50.0),
        )
        self.assertEqual(
            tuple(
                point.value
                for point in manager.series(
                    UPLOAD_SPEED_METRIC,
                    60,
                    granularitySeconds=10,
                    now=50,
                )
            ),
            (15.0,),
        )

    def testUsageHistoryCanClearWithoutMutatingSpeedHistory(self):
        """Reset cumulative graphs while retaining immutable speed samples."""
        manager = MetricsHistory()
        manager.recordSample(
            {
                DOWNLOAD_SPEED_METRIC: 25,
                DOWNLOAD_USAGE_METRIC: 100,
            },
            sampledAt=10,
        )
        manager.clearTrafficUsageHistory()

        samples = manager.rawSamples()

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].values[DOWNLOAD_SPEED_METRIC], 25.0)
        self.assertNotIn(DOWNLOAD_USAGE_METRIC, samples[0].values)


class MetricsPageAndGraphTest(unittest.TestCase):
    """Exercise hidden-page rendering and graph lookup with real widgets."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Drain deferred widget destruction after every UI case."""
        collectAtBoundary()

    def testTrafficGraphsAndSelectorsShareOneCard(self):
        """Keep the page title separate while grouping all metrics controls."""
        manager = MetricsHistory()
        page = MetricsPage(manager)
        contentLayout = page.scrollArea.widget().layout()
        cardLayout = page.metricsCard.layout()
        headerLayout = cardLayout.itemAt(0).layout()

        self.assertIs(contentLayout.itemAt(0).widget(), page.pageTitleLabel)
        self.assertIs(contentLayout.itemAt(1).widget(), page.metricsCard)
        self.assertIs(contentLayout.itemAt(2).widget(), page.endpointInfoWidget)
        self.assertEqual(page.metricsCard.objectName(), 'TrafficMetricsCard')
        self.assertIs(headerLayout.itemAt(0).widget(), page.metricsCard.titleLabel)
        self.assertEqual(page.metricsCard.titleLabel.text(), _('Traffic Statistics'))
        self.assertEqual(headerLayout.stretch(1), 1)
        self.assertIs(headerLayout.itemAt(2).widget(), page.timeRangeLabel)
        self.assertIs(headerLayout.itemAt(3).widget(), page.timeRangeComboBox)
        self.assertIs(headerLayout.itemAt(5).widget(), page.granularityLabel)
        self.assertIs(headerLayout.itemAt(6).widget(), page.granularityComboBox)

        for control in (
            page.timeRangeLabel,
            page.timeRangeComboBox,
            page.granularityLabel,
            page.granularityComboBox,
        ):
            self.assertIs(control.parentWidget(), page.metricsCard)

        self.assertIs(
            page.downloadSpeedGraph.parentWidget(),
            page.metricsCard.downloadSpeedCard,
        )
        self.assertIs(
            page.downloadUsageGraph.parentWidget(),
            page.metricsCard.downloadUsageCard,
        )
        self.assertIs(
            page.uploadSpeedGraph.parentWidget(),
            page.metricsCard.uploadSpeedCard,
        )
        self.assertIs(
            page.uploadUsageGraph.parentWidget(),
            page.metricsCard.uploadUsageCard,
        )

        page.close()
        page.deleteLater()
        manager.deleteLater()

    def testHiddenPageStoresHistoryWithoutRenderingThenCatchesUp(self):
        """Keep collection eager and graph submission strictly visibility-bound."""
        manager = MetricsHistory()
        page = MetricsPage(manager)
        sampledAt = math.floor((time.monotonic() - 20) / 10) * 10 + 1
        manager.recordSample({DOWNLOAD_SPEED_METRIC: 32}, sampledAt=sampledAt)

        processQtEvents()

        self.assertEqual(page._renderRevision, 0)
        self.assertEqual(page.downloadSpeedGraph._points, tuple())
        self.assertFalse(page._renderTimer.isActive())
        self.assertFalse(page._timelineTimer.isActive())

        page.show()

        self.assertTrue(waitFor(lambda: page._renderRevision == 1))
        self.assertEqual(
            tuple(point.value for point in page.downloadSpeedGraph._points),
            (32.0,),
        )
        self.assertTrue(page._timelineTimer.isActive())

        page.hide()

        processQtEvents()

        hiddenRevision = page._renderRevision

        manager.recordSample({DOWNLOAD_SPEED_METRIC: 64}, sampledAt=sampledAt + 1)
        page._renderLatest()

        processQtEvents()

        self.assertEqual(page._renderRevision, hiddenRevision)
        self.assertFalse(page._renderTimer.isActive())
        self.assertFalse(page._timelineTimer.isActive())

        page.show()

        self.assertTrue(waitFor(lambda: page._renderRevision > hiddenRevision))
        self.assertEqual(
            tuple(point.value for point in page.downloadSpeedGraph._points),
            (48.0,),
        )

        page.close()
        page.deleteLater()
        manager.deleteLater()

    def testHoverLookupMatchesDisplayedPointAndTimestampRange(self):
        """Report the exact prepared point rather than recomputing raw history."""
        graph = MetricsGraphWidget(
            MetricsGraphWidget.Download,
            formatTrafficSpeed,
        )
        graph.resize(640, 360)
        graph.setMetricLabel('Download Speed')
        point = MetricSeriesPoint(95, 2048, 91, 95, 3)
        graph.setSeries((point,), 20, 100, currentWallTime=1000)
        graph.show()

        processQtEvents()

        position = graph._pointPosition(
            point,
            graph._chartRect(),
            graph._maximumValue(),
        ).toPoint()

        self.assertIs(graph._nearestPoint(position), point)

        tooltip = graph._tooltipText(point)

        self.assertIn('Download Speed: 2 KiB/s', tooltip)
        self.assertIn(' – ', tooltip)
        self.assertNotIn('×3', tooltip)

        graph.close()
        graph.deleteLater()


if __name__ == '__main__':
    unittest.main()
