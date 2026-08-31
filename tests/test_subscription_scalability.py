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

"""Exercise deterministic large subscription preparation without network I/O."""

from __future__ import annotations

from tests.benchmarks.benchmark_subscription_updates import generatedPayload, run

import unittest


class SubscriptionScalabilityTest(unittest.TestCase):
    """Protect the representative 1/3/8-group data-volume path."""

    def testOneThreeAndEightLargeGroups(self):
        """Prepare and commit 1,500 profiles per group with bounded workers."""
        payload = generatedPayload(1_500)

        for groupCount in (1, 3, 8):
            with self.subTest(groupCount=groupCount):
                result = run(payload, groupCount)

                self.assertEqual(result['groups'], groupCount)
                self.assertEqual(result['profiles'], 1_500 * groupCount)
                self.assertGreaterEqual(result['workers'], 1)
                self.assertLessEqual(result['workers'], 4)


if __name__ == '__main__':
    unittest.main()
