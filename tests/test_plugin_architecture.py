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

"""Verify plugin capability discovery, factories, rollback, and shutdown."""

from __future__ import annotations

import Furious.Plugins.Registry as PluginRegistryModule
from Furious.Models import CoreConfiguration
from Furious.Plugins.API import (
    CapabilityKind,
    CoreRuntimeFactory,
    CoreRuntimeLaunch,
    CoreRuntimeRequest,
    FuriousPlugin,
    PluginMetadata,
    ProtocolDescriptor,
    ProtocolEditorProvider,
    ProtocolHandler,
    ProtocolParseResult,
    SubscriptionDecoder,
    SubscriptionItem,
    SubscriptionResult,
    TrafficCounters,
    TrafficStatsMonitor,
    TrafficStatsProvider,
)
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)

from PySide6 import QtCore, QtWidgets

from tests.support import application, collectAtBoundary, waitFor

import unittest
from unittest import mock
import weakref


class FixtureConfiguration(CoreConfiguration):
    """Represent one deterministic plugin-owned connection document."""

    @property
    def itemProtocol(self):
        """Return the protocol ID used by display and dispatch code."""
        return 'FIXTURE'

    def httpProxy(self) -> str:
        """Return the local HTTP endpoint used by controller fixtures."""
        return '127.0.0.1:18080'


class FixtureProtocolHandler(ProtocolHandler):
    """Parse and export a minimal fixture:// URI."""

    descriptor = ProtocolDescriptor(
        'FIXTURE',
        'Fixture',
        'Add Fixture...',
        'Add Fixture',
        subscriptionImportable=True,
    )
    schemes = ('fixture',)

    def supports(self, configuration) -> bool:
        """Return whether this handler owns *configuration*."""
        return isinstance(
            getattr(configuration, 'connection', configuration),
            FixtureConfiguration,
        )

    def parse(self, uri: str, **kwargs):
        """Parse one fixture endpoint or decline another scheme."""
        if not uri.casefold().startswith('fixture://'):
            return None

        value = uri.split('://', 1)[1]

        if not value:
            return None

        return ProtocolParseResult(
            FixtureConfiguration({'type': 'fixture', 'value': value}),
            {'displayName': value},
        )

    def fromMapping(self, configuration, **kwargs):
        """Recognize normalized fixture mappings."""
        if configuration.get('type') == 'fixture':
            return FixtureConfiguration(dict(configuration))

        return None

    def blank(self, **kwargs):
        """Create one valid blank fixture configuration."""
        return FixtureConfiguration({'type': 'fixture', 'value': 'blank'})

    def export(self, configuration, remark: str = '') -> str:
        """Export a fixture URI."""
        connection = getattr(configuration, 'connection', configuration)

        return f"fixture://{connection.get('value', '')}"

    def validate(self, configuration):
        """Require a non-empty fixture value."""
        connection = getattr(configuration, 'connection', configuration)

        return tuple() if connection.get('value') else ('missing fixture value',)


class FixtureEditorProvider(ProtocolEditorProvider):
    """Create a sentinel editor without retaining it in the registry."""

    editorId = 'fixture.editor'
    protocolIds = ('FIXTURE',)

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Return a fresh sentinel editor for the exact protocol."""
        return {'protocol': protocolId, 'parent': parent, **kwargs}


class FixtureCoreRuntime:
    """Record start calls made through CoreRuntimeLaunch."""

    def __init__(self):
        """Initialize an empty call history."""
        self.calls = []

    def start(self, configuration, *args, **kwargs):
        """Record prepared launch values and report success."""
        self.calls.append((configuration, args, kwargs))

        return True


class FixtureCoreRuntimeFactory(CoreRuntimeFactory):
    """Create a deterministic in-process core runtime."""

    factoryId = 'fixture.runtime'
    configurationTypes = (FixtureConfiguration,)
    runtimeTypes = (FixtureCoreRuntime,)

    def create(self, request: CoreRuntimeRequest):
        """Build one prepared launch for a fixture configuration."""
        if not isinstance(request.configuration, FixtureConfiguration):
            return None

        return CoreRuntimeLaunch(
            FixtureCoreRuntime(),
            request.configuration,
            ('prepared',),
            {'routing': request.routing},
        )


class FixtureDecoder(SubscriptionDecoder):
    """Decode a deterministic fixture payload."""

    decoderId = 'fixture-decoder'
    displayName = 'Fixture Decoder'
    priority = 100

    def decode(self, data: bytes):
        """Decode the exact fixture marker."""
        if data != b'fixture':
            return None

        return SubscriptionResult(
            self.decoderId,
            (
                SubscriptionItem(uri='fixture://one', upstreamId='one'),
                SubscriptionItem(uri='fixture://two', upstreamId='two'),
            ),
        )


class FixturePlugin(FuriousPlugin):
    """Bundle representative capabilities for registry tests."""

    metadata = PluginMetadata('tests.fixture', 'Fixture Plugin')
    capabilities = (
        FixtureProtocolHandler(),
        FixtureEditorProvider(),
        FixtureCoreRuntimeFactory(),
        FixtureDecoder(),
    )

    def __init__(self):
        """Initialize lifecycle counters."""
        self.initialized = 0
        self.stopped = 0
        self.context = None

    def initialize(self, context):
        """Record one successful initialization."""
        self.initialized += 1
        self.context = context

    def shutdown(self):
        """Record one registry-owned shutdown."""
        self.stopped += 1


class PluginRegistryManagerTest(unittest.TestCase):
    """Verify process-registry creation and host-plugin reconciliation."""

    def setUp(self):
        """Replace process state with one isolated registry owner."""
        manager = PluginRegistryModule._PluginRegistryManager()
        patcher = mock.patch.object(PluginRegistryModule, '_registryManager', manager)
        patcher.start()
        self.addCleanup(patcher.stop)

    def testInitializationDiscoversOnceAndReusesRegistry(self):
        """Create one registry and accept the same host type repeatedly."""
        with mock.patch.object(PluginRegistry, 'discover') as discover:
            registry = PluginRegistryModule.initializePluginRegistry((FixturePlugin,))
            self.addCleanup(registry.shutdown)
            current = PluginRegistryModule.initializePluginRegistry((FixturePlugin,))

            self.assertIs(registry, current)

        discover.assert_called_once_with()
        self.assertIsInstance(registry.plugin('tests.fixture'), FixturePlugin)

    def testAdditionalHostPluginTypeIsRegistered(self):
        """Register a newly supplied host plugin in the existing registry."""

        class AdditionalPlugin(FuriousPlugin):
            metadata = PluginMetadata('tests.additional', 'Additional Plugin')

        with mock.patch.object(PluginRegistry, 'discover'):
            registry = PluginRegistryModule.initializePluginRegistry()
            self.addCleanup(registry.shutdown)
            PluginRegistryModule.initializePluginRegistry((AdditionalPlugin,))

        self.assertIsInstance(registry.plugin('tests.additional'), AdditionalPlugin)

    def testConflictingHostPluginTypeIsRejected(self):
        """Reject a different host type claiming an existing plugin ID."""

        class ConflictingPlugin(FuriousPlugin):
            metadata = FixturePlugin.metadata

        with mock.patch.object(PluginRegistry, 'discover'):
            registry = PluginRegistryModule.initializePluginRegistry((FixturePlugin,))
            self.addCleanup(registry.shutdown)

            with self.assertRaisesRegex(ValueError, 'already registered'):
                PluginRegistryModule.initializePluginRegistry((ConflictingPlugin,))

    def testFailedInitialCreationShutsDownEarlierHostPlugins(self):
        """Release initialized plugins when a later host plugin fails."""
        initializedPlugin = FixturePlugin()

        class InitializedPluginType:
            """Return the observable plugin instance owned by this test."""

            def __new__(cls):
                return initializedPlugin

        class FailingPluginType:
            """Fail before the process registry can be published."""

            def __new__(cls):
                raise RuntimeError('host plugin construction failed')

        with mock.patch.object(PluginRegistry, 'discover') as discover:
            with self.assertRaisesRegex(
                RuntimeError,
                'host plugin construction failed',
            ):
                PluginRegistryModule.initializePluginRegistry(
                    (InitializedPluginType, FailingPluginType)
                )

        self.assertEqual(initializedPlugin.initialized, 1)
        self.assertEqual(initializedPlugin.stopped, 1)
        discover.assert_not_called()

        with mock.patch.object(PluginRegistry, 'discover') as discover:
            registry = PluginRegistryModule.initializePluginRegistry()
            self.addCleanup(registry.shutdown)

        discover.assert_called_once_with()


class PluginRegistryTest(unittest.TestCase):
    """Exercise capability dispatch without the process-wide registry."""

    def setUp(self):
        """Create one isolated registry and fixture plugin."""
        self.registry = PluginRegistry()
        self.plugin = FixturePlugin()
        self.registry.register(self.plugin)

    def tearDown(self):
        """Release only plugins owned by this test."""
        self.registry.shutdown()

    def testCapabilityDiscoveryAndMetadata(self):
        """Query capabilities without assuming every plugin is a core."""
        self.assertEqual(self.plugin.initialized, 1)
        self.assertIs(self.plugin.context.registry, self.registry)
        self.assertEqual(
            self.registry.metadataFor('tests.fixture'),
            self.plugin.metadata,
        )
        self.assertEqual(
            len(self.registry.capabilities(plugin=self.plugin)),
            4,
        )
        self.assertIs(
            self.registry.capability(CapabilityKind.Protocol, 'FIXTURE'),
            self.plugin.capabilities[0],
        )
        self.assertEqual(
            self.plugin.capabilities[0].descriptor.addActionText,
            'Add Fixture...',
        )
        self.assertEqual(
            self.plugin.capabilities[0].descriptor.editorWindowTitle,
            'Add Fixture',
        )
        self.assertEqual(
            self.registry.pluginsWithCapability(CapabilityKind.CoreRuntimeFactory),
            (self.plugin,),
        )

    def testProtocolParseExportValidationAndEditorFactory(self):
        """Dispatch URI and editor operations through registered capabilities."""
        parsed = self.registry.parseURI('FiXtUrE://server')

        self.assertIsInstance(parsed.configuration, FixtureConfiguration)
        self.assertEqual(parsed.metadata['displayName'], 'server')
        self.assertEqual(
            self.registry.exportConfig(parsed.configuration),
            'fixture://server',
        )
        self.assertEqual(self.registry.validateConfig(parsed.configuration), tuple())
        self.assertEqual(
            self.registry.createEditorForConfig(parsed.configuration, marker=7),
            {'protocol': 'fixture', 'parent': None, 'marker': 7},
        )

    def testConfigurationAndCoreRuntimeFactories(self):
        """Build normalized configurations and start one prepared runtime."""
        config = self.registry.configFromDict({'type': 'fixture', 'value': 'node'})
        launch = self.registry.createCoreRuntime(config, 'direct')

        self.assertIsInstance(config, FixtureConfiguration)
        self.assertIsInstance(launch.runtime, FixtureCoreRuntime)
        self.assertTrue(launch.start())
        self.assertEqual(
            launch.runtime.calls,
            [(config, ('prepared',), {'routing': 'direct'})],
        )

    def testSubscriptionImportSeparatesMetadataAndConnection(self):
        """Convert decoder items into managed profiles with stable identities."""
        result = SubscriptionImportService(self.registry).importPayload(
            b'fixture',
            SubscriptionSource('source-id', displayName='Fixture source'),
        )

        self.assertEqual(result.decoderId, 'fixture-decoder')
        self.assertEqual(result.rejectedItems, 0)
        self.assertEqual(len(result.profiles), 2)
        self.assertEqual(
            tuple(profile.itemRemark for profile in result.profiles),
            ('one', 'two'),
        )
        self.assertTrue(
            all(profile.metadata.subscriptionManaged for profile in result.profiles)
        )
        self.assertEqual(
            tuple(
                profile.metadata.subscriptionProfileKey for profile in result.profiles
            ),
            ('upstream:one', 'upstream:two'),
        )

    def testShutdownRunsOnceInReverseRegistryLifetime(self):
        """Make shutdown idempotent and reject use of a closed registry."""
        self.registry.shutdown()
        self.registry.shutdown()

        self.assertEqual(self.plugin.stopped, 1)

        with self.assertRaises(RuntimeError):
            self.registry.register(FixturePlugin())


class PluginRollbackTest(unittest.TestCase):
    """Verify failed plugins leave no capabilities or live lifecycle state."""

    def testInitializationFailureRollsBackEveryIndex(self):
        """Remove a failed plugin from all capability lookup structures."""

        class FailingPlugin(FixturePlugin):
            """Raise after capabilities have been indexed."""

            metadata = PluginMetadata('tests.failure', 'Failing Plugin')

            def initialize(self, context):
                """Simulate plugin initialization failure."""
                raise RuntimeError('fixture failure')

        registry = PluginRegistry()
        plugin = FailingPlugin()

        with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
            registry.register(plugin)

        self.assertEqual(plugin.stopped, 1)
        self.assertEqual(registry.plugins(), tuple())
        self.assertEqual(registry.capabilities(), tuple())
        self.assertIsNone(registry.parseURI('fixture://node'))

        registry.shutdown()

    def testDuplicateSchemeDoesNotPartiallyRegisterSecondPlugin(self):
        """Reject conflicting protocol ownership atomically."""

        class ConflictingPlugin(FuriousPlugin):
            """Claim an existing URI scheme under another protocol ID."""

            metadata = PluginMetadata('tests.conflict', 'Conflict')

            class Handler(FixtureProtocolHandler):
                """Use a distinct protocol ID with the same scheme."""

                descriptor = ProtocolDescriptor(
                    'OTHER',
                    'Other',
                    'Add Other...',
                    'Add Other',
                )

            capabilities = (Handler(),)

        first = FixturePlugin()

        registry = PluginRegistry()
        registry.register(first)

        try:
            with self.assertRaises(ValueError):
                registry.register(ConflictingPlugin())

            self.assertEqual(registry.plugins(), (first,))
            self.assertIsNotNone(registry.parseURI('fixture://node'))
        finally:
            registry.shutdown()


class PluginFailureIsolationTest(unittest.TestCase):
    """Keep optional plugin failures bounded to the owning capability."""

    @classmethod
    def setUpClass(cls):
        """Create Qt before exercising a plugin-provided editor widget."""
        application()

    def tearDown(self):
        """Drain deferred deletes after plugin UI tests."""
        collectAtBoundary()

    def testDecoderExceptionFallsThroughToNextCandidate(self):
        """Allow one broken decoder without blocking later valid decoders."""

        class RaisingDecoder(SubscriptionDecoder):
            decoderId = 'raising-decoder'
            displayName = 'Raising decoder'
            priority = 200

            def decode(self, data: bytes):
                raise RuntimeError('decoder fixture')

        class RaisingPlugin(FuriousPlugin):
            metadata = PluginMetadata('tests.raising-decoder', 'Raising decoder')
            capabilities = (RaisingDecoder(),)

        registry = PluginRegistry()
        registry.register(RaisingPlugin())
        registry.register(FixturePlugin())

        try:
            result = registry.decodeSubscription(b'fixture')

            self.assertIsNotNone(result)
            self.assertEqual(result.decoderId, 'fixture-decoder')
        finally:
            registry.shutdown()

    def testCoreRuntimeFactoryExceptionReturnsControlledStartFailure(self):
        """Translate construction failure into a false runtime result."""

        class RaisingFactory(CoreRuntimeFactory):
            factoryId = 'raising-factory'
            configurationTypes = (FixtureConfiguration,)
            runtimeTypes = (FixtureCoreRuntime,)

            def create(self, request: CoreRuntimeRequest):
                raise RuntimeError('factory fixture')

        class RaisingPlugin(FuriousPlugin):
            metadata = PluginMetadata('tests.raising-factory', 'Raising factory')
            capabilities = (RaisingFactory(),)

        registry = PluginRegistry()
        registry.register(RaisingPlugin())

        try:
            runtime, success = registry.startCoreRuntime(
                FixtureConfiguration({'type': 'fixture'}),
                'direct',
            )

            self.assertIsNone(runtime)
            self.assertFalse(success)
        finally:
            registry.shutdown()

    def testShutdownExceptionDoesNotBlockOtherPlugins(self):
        """Run every shutdown hook once even when one hook raises."""
        stopped = []

        class OrderedPlugin(FuriousPlugin):
            capabilities = tuple()

            def __init__(self, identifier: str, *, raises=False):
                self.metadata = PluginMetadata(identifier, identifier)
                self.raises = raises

            def shutdown(self):
                stopped.append(self.metadata.id)

                if self.raises:
                    raise RuntimeError('shutdown fixture')

        registry = PluginRegistry()
        registry.register(OrderedPlugin('tests.shutdown.first'))
        registry.register(OrderedPlugin('tests.shutdown.second', raises=True))
        registry.register(OrderedPlugin('tests.shutdown.third'))

        registry.shutdown()
        registry.shutdown()

        self.assertEqual(
            stopped,
            [
                'tests.shutdown.third',
                'tests.shutdown.second',
                'tests.shutdown.first',
            ],
        )

    def testRegistryStoresEditorFactoryButNotTransientEditorInstance(self):
        """Destroy a plugin editor while its provider remains registered."""

        class WidgetEditorProvider(ProtocolEditorProvider):
            editorId = 'fixture.widget-editor'
            protocolIds = ('FIXTURE',)

            def createEditor(self, protocolId: str, parent=None, **kwargs):
                editor = QtWidgets.QDialog(parent)
                editor.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

                return editor

        class WidgetPlugin(FuriousPlugin):
            metadata = PluginMetadata('tests.widget-editor', 'Widget editor')
            capabilities = (
                FixtureProtocolHandler(),
                WidgetEditorProvider(),
            )

        registry = PluginRegistry()
        registry.register(WidgetPlugin())

        try:
            editor = registry.createEditorForConfig(
                FixtureConfiguration({'type': 'fixture', 'value': 'node'})
            )
            editorReference = weakref.ref(editor)
            editor.show()
            editor.close()
            editor = None

            self.assertTrue(waitFor(lambda: editorReference() is None))
            self.assertIsNotNone(
                registry.capability(
                    CapabilityKind.ProtocolEditor,
                    'fixture.widget-editor',
                )
            )
        finally:
            registry.shutdown()


if __name__ == '__main__':
    unittest.main()
