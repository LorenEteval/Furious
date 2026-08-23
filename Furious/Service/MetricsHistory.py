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

"""Store and aggregate timestamped application metrics independently of UI."""

from __future__ import annotations

from Furious.Service.TrafficStatsManager import TrafficStatsSample

from PySide6 import QtCore

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import math
import time

__all__ = [
    'DOWNLOAD_SPEED_METRIC',
    'DOWNLOAD_USAGE_METRIC',
    'MetricSeriesPoint',
    'MetricSample',
    'MetricsHistory',
    'UPLOAD_SPEED_METRIC',
    'UPLOAD_USAGE_METRIC',
]

DOWNLOAD_SPEED_METRIC = 'network.download.speed'
DOWNLOAD_USAGE_METRIC = 'network.download.usage'
UPLOAD_SPEED_METRIC = 'network.upload.speed'
UPLOAD_USAGE_METRIC = 'network.upload.usage'

MEAN_AGGREGATION = 'mean'
LAST_AGGREGATION = 'last'
SUPPORTED_AGGREGATIONS = (MEAN_AGGREGATION, LAST_AGGREGATION)


@dataclass(frozen=True)
class MetricSample:
    """Store one timestamp and a generic set of metric values."""

    sampledAt: float
    values: Mapping[str, float]


@dataclass(frozen=True)
class MetricSeriesPoint:
    """Represent one graph-ready raw or aggregated metric value."""

    sampledAt: float
    value: float
    firstSampledAt: float | None = None
    lastSampledAt: float | None = None
    sampleCount: int = 1

    @property
    def isAggregated(self) -> bool:
        """Return whether this point summarizes multiple raw samples."""
        return self.sampleCount > 1


class MetricsHistory(QtCore.QObject):
    """Maintain bounded metric history and aggregate it for consumers."""

    historyChanged = QtCore.Signal()

    MaximumHistorySeconds = 24 * 60 * 60
    AutoBucketTarget = 120
    MaximumSampleCount = 50_000
    AutoGranularities = (
        1,
        2,
        5,
        10,
        15,
        30,
        60,
        2 * 60,
        5 * 60,
        10 * 60,
        15 * 60,
        30 * 60,
        60 * 60,
    )

    def __init__(
        self,
        parent=None,
        *,
        maximumHistorySeconds=None,
        maximumSampleCount=None,
    ):
        """Initialize generic metric definitions and bounded sample storage."""
        super().__init__(parent)

        self._maximumHistorySeconds = max(
            float(maximumHistorySeconds or self.MaximumHistorySeconds),
            1.0,
        )
        self._samples = deque()
        self._maximumSampleCount = max(
            int(maximumSampleCount or self.MaximumSampleCount), 1
        )
        self._aggregations = {}

        self.registerMetric(DOWNLOAD_SPEED_METRIC, MEAN_AGGREGATION)
        self.registerMetric(DOWNLOAD_USAGE_METRIC, LAST_AGGREGATION)
        self.registerMetric(UPLOAD_SPEED_METRIC, MEAN_AGGREGATION)
        self.registerMetric(UPLOAD_USAGE_METRIC, LAST_AGGREGATION)

    def registerMetric(self, metricKey: str, aggregation=MEAN_AGGREGATION):
        """Register a metric and its bucket aggregation strategy."""
        if not isinstance(metricKey, str) or not metricKey:
            raise ValueError('metricKey must be a non-empty string')

        if aggregation not in SUPPORTED_AGGREGATIONS:
            raise ValueError(f'unsupported metric aggregation: {aggregation}')

        self._aggregations[metricKey] = aggregation

    def metricKeys(self) -> tuple[str, ...]:
        """Return all metrics currently understood by the manager."""
        return tuple(self._aggregations)

    def sampleCount(self) -> int:
        """Return the number of raw samples retained in memory."""
        return len(self._samples)

    def rawSamples(self) -> tuple[MetricSample, ...]:
        """Return an immutable snapshot of the original recorded samples."""
        return tuple(self._samples)

    def clearHistory(self):
        """Discard all retained metrics and notify interested consumers."""
        if not self._samples:
            return

        self._samples.clear()
        self.historyChanged.emit()

    def clearMetrics(self, metricKeys):
        """Remove selected metric values while preserving other history."""
        keys = frozenset(metricKeys)

        if not keys or not self._samples:
            return

        retainedSamples = deque()
        changed = False

        for sample in self._samples:
            retainedValues = {
                key: value for key, value in sample.values.items() if key not in keys
            }

            if len(retainedValues) != len(sample.values):
                changed = True

            if retainedValues:
                retainedSamples.append(
                    MetricSample(
                        sample.sampledAt,
                        MappingProxyType(retainedValues),
                    )
                )

        if changed:
            self._samples = retainedSamples
            self.historyChanged.emit()

    @QtCore.Slot()
    def clearTrafficUsageHistory(self):
        """Clear usage graphs without discarding upload/download speed history."""
        self.clearMetrics((DOWNLOAD_USAGE_METRIC, UPLOAD_USAGE_METRIC))

    @QtCore.Slot(object)
    def recordTrafficSample(self, sample):
        """Convert one session-normalized traffic sample into generic metrics.

        Raw proxy-core counter lifetimes are reconciled upstream by
        ``TrafficStatsManager`` so this class remains provider-independent.
        """
        if not isinstance(sample, TrafficStatsSample):
            return

        self.recordSample(
            {
                DOWNLOAD_SPEED_METRIC: sample.downloadSpeed,
                DOWNLOAD_USAGE_METRIC: sample.downloadUsage,
                UPLOAD_SPEED_METRIC: sample.uploadSpeed,
                UPLOAD_USAGE_METRIC: sample.uploadUsage,
            },
            sample.sampledAt,
        )

    def recordSample(self, values: Mapping[str, float], sampledAt=None):
        """Record finite values for registered metrics at one timestamp."""
        if not isinstance(values, Mapping):
            raise TypeError('values must be a mapping')

        timestamp = time.monotonic() if sampledAt is None else float(sampledAt)

        if not math.isfinite(timestamp):
            raise ValueError('sampledAt must be finite')

        normalizedValues = {}

        for metricKey, value in values.items():
            if metricKey not in self._aggregations:
                continue

            try:
                normalizedValue = float(value)
            except (TypeError, ValueError, OverflowError):
                continue

            if math.isfinite(normalizedValue):
                normalizedValues[metricKey] = max(normalizedValue, 0.0)

        if not normalizedValues:
            return

        if self._samples and timestamp < self._samples[-1].sampledAt:
            timestamp = self._samples[-1].sampledAt

        self._samples.append(
            MetricSample(
                timestamp,
                MappingProxyType(normalizedValues),
            )
        )
        self._pruneHistory(timestamp)
        self.historyChanged.emit()

    def _pruneHistory(self, now: float):
        """Remove samples older than the configured in-memory history."""
        oldestAllowed = now - self._maximumHistorySeconds

        while self._samples and (
            self._samples[0].sampledAt < oldestAllowed
            or len(self._samples) > self._maximumSampleCount
        ):
            self._samples.popleft()

    def effectiveGranularity(self, rangeSeconds, granularitySeconds=0) -> float:
        """Return an explicit or automatically selected bucket duration."""
        rangeSeconds = max(float(rangeSeconds), 1.0)
        granularitySeconds = float(granularitySeconds or 0)

        if granularitySeconds > 0:
            return min(granularitySeconds, rangeSeconds)

        target = max(rangeSeconds / self.AutoBucketTarget, 1.0)

        return min(
            next(
                (float(value) for value in self.AutoGranularities if value >= target),
                rangeSeconds,
            ),
            rangeSeconds,
        )

    def series(
        self,
        metricKey: str,
        rangeSeconds: float,
        granularitySeconds=0,
        *,
        now=None,
    ) -> tuple[MetricSeriesPoint, ...]:
        """Return graph-ready values aggregated into time buckets."""
        aggregation = self._aggregations.get(metricKey)

        if aggregation is None:
            raise KeyError(f'unknown metric: {metricKey}')

        if not self._samples:
            return tuple()

        rangeSeconds = max(float(rangeSeconds), 1.0)
        currentTime = time.monotonic() if now is None else float(now)
        granularity = self.effectiveGranularity(
            rangeSeconds,
            granularitySeconds,
        )
        startTime = currentTime - rangeSeconds
        firstBucketIndex = math.floor(startTime / granularity)
        firstBucketStart = firstBucketIndex * granularity
        buckets = {}

        for sample in self._samples:
            if sample.sampledAt < firstBucketStart:
                continue

            if sample.sampledAt > currentTime:
                continue

            if metricKey not in sample.values:
                continue

            # Align every bucket to the process's absolute monotonic clock.
            # Moving ``now`` therefore changes only the visible window; it
            # never shifts boundaries and re-groups historical samples.
            bucketIndex = math.floor(sample.sampledAt / granularity)
            bucket = buckets.setdefault(bucketIndex, [])
            bucket.append((sample.sampledAt, float(sample.values[metricKey])))

        points = []

        for _bucketIndex, samples in sorted(buckets.items()):
            sampleTimes = tuple(sample[0] for sample in samples)
            values = tuple(sample[1] for sample in samples)

            if aggregation == LAST_AGGREGATION:
                value = values[-1]
            else:
                value = sum(values) / len(values)

            sampledAt = sampleTimes[-1]

            if sampledAt < startTime:
                continue

            points.append(
                MetricSeriesPoint(
                    sampledAt,
                    value,
                    sampleTimes[0],
                    sampleTimes[-1],
                    len(samples),
                )
            )

        return tuple(points)
