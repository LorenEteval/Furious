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

"""Protect data-only log benchmark reports and standalone CLI comparison."""

from __future__ import annotations

from tests.benchmarks import benchmark_log_manager as benchmark
from tests.support import assertChildSucceeded, runPythonChild

from pathlib import Path
from unittest import mock

import copy
import io
import json
import tempfile
import unittest


class LogManagerBenchmarkTest(unittest.TestCase):
    """Keep saved measurements comparable without importing historical code."""

    @staticmethod
    def report():
        return {
            'schema': 1,
            'entries': 50,
            'measurements': {
                name: float(index + 1)
                for index, name in enumerate(benchmark.MEASUREMENTS)
            },
        }

    def testComparisonUsesMeasuredRatiosWithoutChangingReports(self):
        baseline = self.report()
        current = copy.deepcopy(baseline)
        current['measurements'] = {
            name: value * 2 for name, value in baseline['measurements'].items()
        }
        before = copy.deepcopy((current, baseline))

        self.assertEqual(
            benchmark.compareReports(current, baseline),
            {name: 2.0 for name in benchmark.MEASUREMENTS},
        )
        self.assertEqual((current, baseline), before)

    def testInvalidOrIncompatibleReportsAreRejected(self):
        for value in (None, [], {}, {'schema': True}, {'schema': 2}):
            with self.subTest(report=value), self.assertRaises(ValueError):
                benchmark.validateReport(value)

        for field, value in (
            ('entries', True),
            ('entries', 9),
            ('entries', 50.0),
            ('measurements', {}),
            ('measurements', []),
        ):
            report = self.report()
            report[field] = value

            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                benchmark.validateReport(report)

        current = self.report()
        baseline = self.report()
        baseline['entries'] = 100

        with self.assertRaisesRegex(ValueError, 'entries must match'):
            benchmark.compareReports(current, baseline)

    def testInvalidTimingsCannotProduceMisleadingRatios(self):
        for value in (0, -1, True, '1.0', None, float('nan'), float('inf')):
            report = self.report()
            report['measurements']['steady_append_ms'] = value

            with self.subTest(value=value), self.assertRaises(ValueError):
                benchmark.validateReport(report)

    def testCommandLineMeasuresAndComparesSavedJsonInFreshProcesses(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / 'baseline.json'
            current = Path(directory) / 'current.json'

            for output, extra in (
                (baseline, []),
                (current, ['--baseline', str(baseline)]),
            ):
                arguments = ['--entries', '50', '--output', str(output), *extra]

                result = runPythonChild(
                    'from tests.benchmarks.benchmark_log_manager import main\n'
                    f'main({arguments!r})'
                )

                assertChildSucceeded(self, result, 'log benchmark CLI')
                self.assertEqual(
                    json.loads(result.stdout),
                    json.loads(output.read_text(encoding='utf-8')),
                )

            baselineReport = json.loads(baseline.read_text(encoding='utf-8'))
            currentReport = json.loads(current.read_text(encoding='utf-8'))

            self.assertNotIn('comparison', baselineReport)
            self.assertEqual(currentReport['comparison']['baseline'], baselineReport)
            self.assertEqual(
                currentReport['comparison']['ratios'],
                benchmark.compareReports(currentReport, baselineReport),
            )
            self.assertIn('qt', currentReport['environment'])

    def testInvalidBaselineFailsBeforeWorkOrOutput(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / 'baseline.json'
            output = Path(directory) / 'current.json'

            for contents in ('not JSON', '{"schema": 99}', json.dumps(self.report())):
                baseline.write_text(contents, encoding='utf-8')

                with self.subTest(contents=contents), mock.patch.object(
                    benchmark, 'run'
                ) as run, mock.patch(
                    'sys.stderr', new_callable=io.StringIO
                ), self.assertRaises(
                    SystemExit
                ) as exited:
                    benchmark.main(
                        [
                            '--entries',
                            '100',
                            '--baseline',
                            str(baseline),
                            '--output',
                            str(output),
                        ]
                    )

                self.assertEqual(exited.exception.code, 2)
                run.assert_not_called()
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
