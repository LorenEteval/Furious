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

"""Benchmark copied subscription preparation and GUI-thread commits."""

from __future__ import annotations

from Furious.Backends import OFFICIAL_PLUGIN_TYPES
from Furious.Extensions import BUNDLED_EXTENSION_TYPES
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)
from Furious.Service.SubscriptionSync import SubscriptionSynchronizer

from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import argparse
import base64
import os
import time


def generatedPayload(profileCount: int) -> bytes:
    """Create a deterministic Base64 share-link payload without network access."""
    links = '\n'.join(
        f'socks://node-{index}.example:1080#Node-{index}'
        for index in range(profileCount)
    )

    return base64.b64encode(links.encode())


def timed(callableObject):
    """Return one value and elapsed duration."""
    started = time.perf_counter()
    value = callableObject()

    return value, time.perf_counter() - started


def run(payload: bytes, groupCount: int):
    """Measure worker-eligible parsing/preparation and short sequential commits."""
    registry = PluginRegistry()

    for pluginType in (*OFFICIAL_PLUGIN_TYPES, *BUNDLED_EXTENSION_TYPES):
        registry.register(pluginType())

    try:
        importer = SubscriptionImportService(registry)
        synchronizer = SubscriptionSynchronizer()
        workerCount = max(1, min((os.cpu_count() or 1) // 2, 4))

        def prepare(index):
            source = SubscriptionSource(f'group-{index}', decoderId=None)
            imported, decodeDuration = timed(
                lambda: importer.importPayload(
                    payload,
                    source,
                    requireWorkerSafe=True,
                )
            )
            snapshot = synchronizer.snapshot((), source.id)
            plan, reconcileDuration = timed(
                lambda: synchronizer.prepare(snapshot, imported.profiles)
            )

            return plan, decodeDuration, reconcileDuration

        started = time.perf_counter()

        with ThreadPoolExecutor(max_workers=workerCount) as executor:
            prepared = tuple(executor.map(prepare, range(groupCount)))

        workerWall = time.perf_counter() - started
        repository = []
        commitStarted = time.perf_counter()

        for plan, _decodeDuration, _reconcileDuration in prepared:
            synchronizer.commit(repository, plan)

        commitDuration = time.perf_counter() - commitStarted

        return {
            'groups': groupCount,
            'profiles': len(repository),
            'workers': workerCount,
            'decode_cpu_s': sum(item[1] for item in prepared),
            'reconcile_cpu_s': sum(item[2] for item in prepared),
            'worker_wall_s': workerWall,
            'gui_commit_s': commitDuration,
        }
    finally:
        registry.shutdown()


def main():
    """Run deterministic 1/3/8-group measurements or an explicit live payload."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--profiles', type=int, default=1_500)
    parser.add_argument('--groups', default='1,3,8')
    parser.add_argument('--url', default='')
    arguments = parser.parse_args()

    if arguments.url:
        with urlopen(arguments.url, timeout=30) as response:
            payload = response.read()
    else:
        payload = generatedPayload(max(arguments.profiles, 1))

    for groupCount in (int(value) for value in arguments.groups.split(',')):
        result = run(payload, groupCount)
        print(' '.join(f'{key}={value}' for key, value in result.items()))


if __name__ == '__main__':
    main()
