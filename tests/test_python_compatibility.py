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

"""Exercise Python compatibility with real workers and legacy API shapes."""

from __future__ import annotations

from Furious.Core.SingTUN import SingTUN
from Furious.Frozenlib import PythonCompatibility
from Furious.Plugins import FuriousPlugin, PluginMetadata, PluginRegistry
from Furious.Service.TrafficStatsManager import TrafficStatsManager

from shiboken6 import delete as deleteQObject

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module, metadata
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import sys
import threading
import unittest

from tests.support import (
    application,
    assertChildSucceeded,
    isolatedSettings,
    runPythonChild,
)

RegistryModule = import_module('Furious.Plugins.Registry')
TrafficStatsManagerModule = import_module('Furious.Service.TrafficStatsManager')


class _LegacyExecutor:
    """Expose the Python 3.8 shutdown signature over a real worker pool."""

    def __init__(self, executor):
        self.executor = executor

    def shutdown(self, wait=True):
        self.executor.shutdown(wait=wait)


class _MetadataProvider:
    """Count capability probes while exposing a strict entry-point API."""

    PackageNotFoundError = metadata.PackageNotFoundError

    def __init__(self, selectable, entryPoints):
        self.selectable = selectable
        self.entry_points = entryPoints
        self.probes = 0

    @property
    def EntryPoints(self):
        self.probes += 1

        if not self.selectable:
            raise AttributeError('legacy metadata has no EntryPoints type')

        return object


class PythonCompatibilityTest(unittest.TestCase):
    """Preserve exact text, metadata selection, and queued-work cancellation."""

    @staticmethod
    def _loadCompatibility(version, metadataProvider=metadata):
        """Execute the checked-out module with isolated interpreter/API inputs."""
        path = (
            Path(__file__).resolve().parents[1]
            / 'Furious/Frozenlib/PythonCompatibility.py'
        )
        code = compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        namespace = {'__name__': '_compatibility_selection'}

        with mock.patch.dict(
            'sys.modules', {'sys': SimpleNamespace(version_info=version)}
        ):
            with mock.patch('importlib.metadata', metadataProvider):
                exec(code, namespace)

        return namespace

    def testExactAffixRemoval(self):
        """Remove one match without stripping characters or an empty suffix."""
        cases = (
            ('socks5://localhost:1080', 'socks5://', 'localhost:1080'),
            ('socks5://socks5://host', 'socks5://', 'socks5://host'),
            ('host', 'socks5://', 'host'),
            ('prefix', '', 'prefix'),
            ('', 'prefix', ''),
            ('prefix', 'prefix', ''),
            ('\u524d\u7f00value', '\u524d\u7f00', 'value'),
        )

        for value, prefix, expected in cases:
            with self.subTest(value=value, prefix=prefix):
                self.assertEqual(
                    PythonCompatibility.removePrefix(value, prefix), expected
                )

        for value, suffix, expected in (
            ('module.py', '.py', 'module'),
            ('module.py.py', '.py', 'module.py'),
            ('module', '.py', 'module'),
            ('module', '', 'module'),
            ('', '.py', ''),
            ('.py', '.py', ''),
            ('value\u540e\u7f00', '\u540e\u7f00', 'value'),
        ):
            with self.subTest(value=value, suffix=suffix):
                self.assertEqual(
                    PythonCompatibility.removeSuffix(value, suffix), expected
                )

        for method in (
            PythonCompatibility.removePrefix,
            PythonCompatibility.removeSuffix,
        ):
            with self.assertRaises(TypeError):
                method('value', ('value',))

    def testImplementationsAreSelectedOnceAtImport(self):
        """Repeated calls retain their selected APIs without new capability probes."""
        for modern in (False, True):
            with self.subTest(modern=modern):
                if modern and sys.version_info < (3, 9):
                    self.skipTest('native affix methods require Python 3.9')

                version = mock.MagicMock()
                version.__ge__.return_value = modern
                fetch = mock.Mock(return_value=() if modern else {})
                provider = _MetadataProvider(modern, fetch)

                namespace = self._loadCompatibility(version, provider)
                compatibility = namespace['PythonCompatibility']

                fetch.assert_not_called()
                self.assertEqual(provider.probes, 1)

                if modern:
                    self.assertIs(namespace['_removePrefix'], str.removeprefix)
                    self.assertIs(namespace['_removeSuffix'], str.removesuffix)

                namespace['_PYTHON_39_OR_NEWER'] = not modern

                for _ in range(10):
                    self.assertEqual(
                        compatibility.removePrefix('prefix-value', 'prefix-'), 'value'
                    )
                    self.assertEqual(
                        compatibility.removeSuffix('value-suffix', '-suffix'), 'value'
                    )
                    self.assertEqual(compatibility.removePrefix('value', ''), 'value')
                    self.assertEqual(compatibility.removeSuffix('value', ''), 'value')
                    self.assertEqual(compatibility.entryPoints('missing'), ())

                    executor, future = mock.Mock(), mock.Mock()

                    compatibility.shutdownExecutor(executor, (future,), wait=False)

                    if modern:
                        executor.shutdown.assert_called_once_with(
                            wait=False, cancel_futures=True
                        )
                        future.cancel.assert_not_called()
                    else:
                        executor.shutdown.assert_called_once_with(wait=False)
                        future.cancel.assert_called_once_with()

                version.__ge__.assert_called_once_with((3, 9))
                self.assertEqual(provider.probes, 1)
                self.assertEqual(fetch.call_count, 10)

                if modern:
                    fetch.assert_called_with(group='missing')
                else:
                    fetch.assert_called_with()

    def testEntryPointAPIShapesPreserveOrderAndDiscoverPlugins(self):
        """Discovery reaches the same registry through old and new metadata APIs."""

        class FixturePlugin(FuriousPlugin):
            metadata = PluginMetadata(
                'tests.python-compatibility', 'Compatibility fixture'
            )

        entry = SimpleNamespace(name='fixture', load=lambda: FixturePlugin)
        entries = (entry, SimpleNamespace(name='second', load=lambda: ()))

        for selectable in (False, True):
            with self.subTest(selectable=selectable):
                if selectable:

                    def fetch(*, group):
                        return entries if group == 'furious.plugins' else ()

                else:

                    def fetch():
                        return {'furious.plugins': entries, 'unrelated': ()}

                provider = _MetadataProvider(selectable, mock.Mock(side_effect=fetch))

                compatibility = self._loadCompatibility(sys.version_info, provider)[
                    'PythonCompatibility'
                ]

                self.assertEqual(compatibility.entryPoints('furious.plugins'), entries)
                self.assertEqual(compatibility.entryPoints('missing'), ())

                registry = PluginRegistry()

                try:
                    with mock.patch.object(
                        RegistryModule, 'PythonCompatibility', compatibility
                    ):
                        registry.discover()

                    self.assertEqual(
                        registry.metadataFor('tests.python-compatibility'),
                        FixturePlugin.metadata,
                    )
                finally:
                    registry.shutdown()

                if selectable:
                    provider.entry_points.assert_called_with(group='furious.plugins')
                else:
                    provider.entry_points.assert_called_with()

                self.assertEqual(provider.probes, 1)

    def testInstalledMetadataUsesTheActualInterpreterAPI(self):
        """Real metadata lookup works without opening any native TUN engine."""
        self.assertEqual(
            PythonCompatibility.entryPoints('furious.tests.nonexistent-entry-points'),
            (),
        )

        self.assertEqual(SingTUN.version(), metadata.version('sing-tun'))

    def testDistributionVersionKeepsMissingMetadataBehavior(self):
        """The engine reports unavailable only for missing distribution metadata."""
        with mock.patch.object(
            metadata, 'version', return_value='0.9.7.dev0'
        ) as version:
            self.assertEqual(SingTUN.version(), '0.9.7.dev0')
            version.assert_called_once_with('sing-tun')

        with mock.patch.object(
            metadata,
            'version',
            side_effect=PythonCompatibility.PackageNotFoundError('sing-tun'),
        ):
            self.assertEqual(SingTUN.version(), 'unavailable')

        with mock.patch.object(
            metadata, 'version', side_effect=ValueError('invalid metadata')
        ):
            with self.assertRaisesRegex(ValueError, 'invalid metadata'):
                SingTUN.version()

    @unittest.skipIf(sys.version_info < (3, 9), 'native shutdown requires Python 3.9')
    def testModernShutdownDoesNotRetryUnrelatedTypeErrors(self):
        """Native shutdown errors propagate without an unsafe fallback retry."""
        executor = mock.Mock()
        executor.shutdown.side_effect = TypeError('shutdown failed')
        future = mock.Mock()

        compatibility = self._loadCompatibility((3, 9))['PythonCompatibility']

        with self.assertRaisesRegex(TypeError, 'shutdown failed'):
            compatibility.shutdownExecutor(executor, (future,), wait=False)

        executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
        future.cancel.assert_not_called()

    def testShutdownCancelsQueuedWorkAndLeavesRunningWorkOwned(self):
        """Both APIs reject new work, cancel queued calls, and allow a real drain."""
        for version in ((3, 8), (3, 9)):
            with self.subTest(version=version):
                if version >= (3, 9) and sys.version_info < (3, 9):
                    self.skipTest('native shutdown requires Python 3.9')

                started, release, queuedRan = (
                    threading.Event(),
                    threading.Event(),
                    threading.Event(),
                )
                executor = ThreadPoolExecutor(max_workers=1)

                def blocked():
                    started.set()
                    return release.wait(5)

                running = executor.submit(blocked)
                queued = None

                try:
                    self.assertTrue(started.wait(2))

                    queued = executor.submit(queuedRan.set)
                    adapter = (
                        _LegacyExecutor(executor) if version == (3, 8) else executor
                    )

                    compatibility = self._loadCompatibility(version)[
                        'PythonCompatibility'
                    ]

                    compatibility.shutdownExecutor(adapter, (queued,), wait=False)

                    self.assertTrue(queued.cancelled())
                    self.assertFalse(running.done())
                    self.assertFalse(queuedRan.is_set())

                    with self.assertRaises(RuntimeError):
                        executor.submit(lambda: None)

                    release.set()
                    self.assertTrue(running.result(timeout=2))
                finally:
                    release.set()

                    if queued is not None:
                        queued.cancel()

                    executor.shutdown(wait=True)

                self.assertFalse(queuedRan.is_set())
                self.assertTrue(
                    all(not thread.is_alive() for thread in executor._threads)
                )

    def testStatisticsOwnerPassesItsPendingWorkToLegacyShutdown(self):
        """Manager shutdown cancels its queued query using the strict old API."""
        application()

        with isolatedSettings():
            manager = TrafficStatsManager()
            started, release = threading.Event(), threading.Event()
            executor = ThreadPoolExecutor(max_workers=1)

            def blocked():
                started.set()
                return release.wait(5)

            running = executor.submit(blocked)
            queued = None

            try:
                self.assertTrue(started.wait(2))

                queued = executor.submit(lambda: None)
                manager._executor = _LegacyExecutor(executor)
                manager._future = queued
                manager._queryInFlight = True

                compatibility = self._loadCompatibility((3, 8))['PythonCompatibility']

                with mock.patch.object(
                    TrafficStatsManagerModule, 'PythonCompatibility', compatibility
                ):
                    manager._closeExecutor()

                self.assertIsNone(manager._executor)
                self.assertIsNone(manager._future)
                self.assertFalse(manager._queryInFlight)
                self.assertTrue(queued.cancelled())
                self.assertFalse(running.done())
            finally:
                release.set()

                if queued is not None:
                    queued.cancel()

                executor.shutdown(wait=True)

                manager.cleanup()
                deleteQObject(manager)

    def testProfileColdImportWithAnUnsubscriptableABC(self):
        """A Python 3.8-style collections ABC cannot break the profile import."""
        script = """
from collections.abc import MutableMapping

def unavailable(cls, item):
    raise TypeError('collections ABC is not subscriptable')

MutableMapping.__class_getitem__ = classmethod(unavailable)

try:
    MutableMapping[str, object]
except TypeError:
    pass
else:
    raise AssertionError('legacy ABC fixture did not reject subscripting')

from Furious.Models import CoreConfiguration, ServerProfile

profile = ServerProfile.fromConfiguration(CoreConfiguration({'server': 'example'}))
assert isinstance(profile, MutableMapping)
assert profile['server'] == 'example'
profile['port'] = 443
assert profile['port'] == 443
"""
        assertChildSucceeded(
            self, runPythonChild(script), 'profile import with a Python 3.8-style ABC'
        )


if __name__ == '__main__':
    unittest.main()
