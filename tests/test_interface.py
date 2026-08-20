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

"""Verify the low-level application, runtime, editor, and storage contracts."""

from __future__ import annotations

from Furious.Frozenlib.Constants import PLATFORM
from Furious.Interface import (
    ApplicationRunner,
    CoreRuntime,
    EditorBinding,
    EditorWidgetBinding,
    StorageBackend,
)
from Furious.Models import CoreConfiguration
from Furious.Models.Encoding import UJSONEncoder

import json
import unittest

from unittest import mock


class RuntimeFixture(CoreRuntime):
    """Provide a side-effect-free runtime implementation for contract tests."""

    @staticmethod
    def name() -> str:
        """Return the fixture runtime name."""
        return 'Test runtime'

    @staticmethod
    def version() -> str:
        """Return the fixture runtime version."""
        return '1.0'

    def start(self, *args, **kwargs) -> bool:
        """Report a successful fixture start."""
        return True

    def stop(self):
        """Stop the fixture runtime."""


class EditorFixture(EditorWidgetBinding):
    """Provide a minimal editor binding with stable widget ownership."""

    def __init__(self):
        """Initialize the fixture editor."""
        super().__init__()

        self.value = None
        self._widgets = (object(), object())

    def inputToFactory(self):
        """Return the current fixture input."""
        return self.value

    def factoryToInput(self, value):
        """Load a fixture value into the editor."""
        self.value = value

    def widgets(self):
        """Return the stable fixture widgets."""
        return self._widgets


class StorageFixture(StorageBackend):
    """Provide a mutable in-memory repository for contract tests."""

    def __init__(self):
        """Initialize the fixture repository."""
        self.collection = []
        self.persisted = None

    def sync(self):
        """Record a snapshot of the live collection."""
        self.persisted = list(self.collection)

    def data(self):
        """Return the intentionally live mutable collection."""
        return self.collection


class InterfaceContractTest(unittest.TestCase):
    """Exercise stable behavior at the low-level interface boundary."""

    def testApplicationAndRuntimeExitCodesRemainStable(self):
        """Protect process exit values consumed by callers and host runtimes."""
        self.assertEqual(ApplicationRunner.ExitCode.ExitSuccess.value, 0)
        self.assertEqual(ApplicationRunner.ExitCode.UnknownException.value, 61)
        self.assertEqual(CoreRuntime.ExitCode.ConfigurationError.value, 23)
        self.assertEqual(
            CoreRuntime.ExitCode.ServerStartFailure.value,
            4294967295 if PLATFORM == 'Windows' else 255,
        )

    def testCoreRuntimeExitCallback(self):
        """Keep the runtime callback argument order stable."""
        observed = []
        runtime = RuntimeFixture(
            exitCallback=lambda runtime, exitcode: observed.append((runtime, exitcode))
        )

        runtime.callExitCallback(7)

        self.assertEqual(observed, [(runtime, 7)])

    def testPlainDictionarySerializationUsesSharedUJSONEncoder(self):
        """Reuse the shared high-performance encoder for plain dictionaries."""
        runtime = RuntimeFixture()
        document = {'name': '节点', 'url': 'https://example.com/path'}

        with mock.patch(
            'Furious.Interface.Runtime.UJSONEncoder.encode',
            wraps=UJSONEncoder.encode,
        ) as encode:
            encoded = runtime.toJSONString(document)

        encode.assert_called_once_with(document)

        self.assertEqual(json.loads(encoded), document)
        self.assertEqual(runtime.startError(), '')

    def testForwardSlashEscapingRemainsCompatible(self):
        """Preserve the existing optional forward-slash escaping convention."""
        runtime = RuntimeFixture()

        encoded = runtime.toJSONString(
            {'url': 'https://example.com'}, escape_forward_slashes=True
        )

        self.assertIn(r'https:\/\/example.com', encoded)
        self.assertEqual(json.loads(encoded), {'url': 'https://example.com'})

    def testDictionarySubclassSerializerRemainsAuthoritative(self):
        """Allow CoreConfiguration-style dictionary subclasses to serialize themselves."""

        class Configuration(dict):
            def __init__(self):
                super().__init__()

                self.kwargs = None

            def toJSONString(self, **kwargs):
                self.kwargs = kwargs

                return '{"custom": true}'

        runtime = RuntimeFixture()
        configuration = Configuration()

        encoded = runtime.toJSONString(configuration, indent=2)

        self.assertEqual(encoded, '{"custom": true}')
        self.assertEqual(configuration.kwargs, {'indent': 2})
        self.assertEqual(runtime.startError(), '')

    def testSerializationFailuresPopulateStartErrorAndLogDetails(self):
        """Keep the legacy empty return while making failures diagnosable."""
        runtime = RuntimeFixture()

        with self.assertLogs('Furious.Interface.Runtime', level='ERROR'):
            encoded = runtime.toJSONString({'value': object()})

        self.assertEqual(encoded, '')
        self.assertEqual(runtime.startError(), 'Invalid server configuration')

        with self.assertLogs('Furious.Interface.Runtime', level='ERROR'):
            encoded = runtime.toJSONString(object())

        self.assertEqual(encoded, '')
        self.assertEqual(runtime.startError(), 'Invalid server configuration')

    def testCoreConfigurationSerializationDiagnosticReachesRuntime(self):
        """Forward the model serializer's concrete failure to startup callers."""
        runtime = RuntimeFixture()
        configuration = CoreConfiguration({'value': object()})

        with self.assertLogs('Furious.Interface.Runtime', level='ERROR'):
            encoded = runtime.toJSONString(configuration)

        self.assertEqual(encoded, '')
        self.assertEqual(runtime.startError(), configuration.serializationError())

    def testSuccessfulSerializationClearsPreviousStartError(self):
        """Expose only the failure from the current launch preparation attempt."""
        runtime = RuntimeFixture()
        runtime.setStartError('old failure')

        self.assertEqual(runtime.toJSONString('{}'), '{}')
        self.assertEqual(runtime.startError(), '')

    def testEmbeddedRuntimeLaunchSpecsExposeSerializationFailures(self):
        """Give the connection layer a useful error for every embedded runtime."""
        from Furious.Backends.Hysteria1.Process import Hysteria1
        from Furious.Backends.Hysteria2.Process import Hysteria2
        from Furious.Backends.Xray.Process import XrayCore

        launchAttempts = (
            (XrayCore, lambda runtime: runtime.launchSpec(object())),
            (Hysteria1, lambda runtime: runtime.launchSpec(object(), '', '')),
            (Hysteria2, lambda runtime: runtime.launchSpec(object())),
        )

        for runtimeType, launch in launchAttempts:
            with self.subTest(runtime=runtimeType.__name__):
                runtime = object.__new__(runtimeType)
                CoreRuntime.__init__(runtime)

                with self.assertLogs('Furious.Interface.Runtime', level='ERROR'):
                    launchSpec = launch(runtime)

                self.assertIsNone(launchSpec)
                self.assertEqual(runtime.startError(), 'Invalid server configuration')

    def testRepresentativeImplementationsShareCoreRuntimeContract(self):
        """Cover subprocess and multiprocessing-backed runtime implementations."""
        from Furious.Backends.ExternalCore import ExternalCoreProcess
        from Furious.Backends.Hysteria1.Process import Hysteria1
        from Furious.Backends.Hysteria2.Process import Hysteria2
        from Furious.Backends.Xray.Process import XrayCore
        from Furious.Core import CoreProcessWorker, Tun2socks

        for runtimeType in (
            ExternalCoreProcess,
            Hysteria1,
            Hysteria2,
            XrayCore,
            Tun2socks,
        ):
            with self.subTest(runtime=runtimeType.__name__):
                self.assertTrue(issubclass(runtimeType, CoreRuntime))

        for runtimeType in (Hysteria1, Hysteria2, XrayCore, Tun2socks):
            with self.subTest(processBacked=runtimeType.__name__):
                self.assertTrue(issubclass(runtimeType, CoreProcessWorker))

        self.assertFalse(issubclass(ExternalCoreProcess, CoreProcessWorker))

    def testEditorBindingDirectionAndWidgetIdentity(self):
        """Keep editor data flow explicit and widget references stable."""
        editor = EditorFixture()
        widgets = editor.widgets()

        editor.factoryToInput('value')

        self.assertIsInstance(editor, EditorBinding)
        self.assertEqual(editor.inputToFactory(), 'value')
        self.assertIs(editor.widgets(), widgets)

    def testStorageDataIsTheLiveManagedCollection(self):
        """Document intentional mutation-before-sync repository behavior."""
        storage = StorageFixture()
        data = storage.data()

        data.append('value')
        storage.sync()

        self.assertIs(data, storage.data())
        self.assertEqual(storage.persisted, ['value'])


if __name__ == '__main__':
    unittest.main()
