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

from Furious.Models import ConfigFactory
from Furious.Plugins.API import (
    CapabilityKind,
    FuriousPlugin,
    KernelFactory,
    KernelLaunch,
    KernelRequest,
    PluginMetadata,
    ProtocolDescriptor,
    ProtocolEditorProvider,
    ProtocolHandler,
    ProtocolParseResult,
    SubscriptionDecoder,
    SubscriptionItem,
    SubscriptionResult,
)
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)

import unittest


class FixtureConfiguration(ConfigFactory):
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


class FixtureKernel:
    """Record start calls made through KernelLaunch."""

    def __init__(self):
        """Initialize an empty call history."""
        self.calls = []

    def start(self, configuration, *args, **kwargs):
        """Record prepared launch values and report success."""
        self.calls.append((configuration, args, kwargs))

        return True


class FixtureKernelFactory(KernelFactory):
    """Create a deterministic in-process runtime kernel."""

    factoryId = 'fixture.kernel'
    configurationTypes = (FixtureConfiguration,)
    kernelTypes = (FixtureKernel,)

    def create(self, request: KernelRequest):
        """Build one prepared launch for a fixture configuration."""
        if not isinstance(request.configuration, FixtureConfiguration):
            return None

        return KernelLaunch(
            FixtureKernel(),
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
        FixtureKernelFactory(),
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
            self.registry.pluginsWithCapability(CapabilityKind.KernelFactory),
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

    def testConfigurationAndKernelFactories(self):
        """Build normalized configurations and start one prepared runtime."""
        config = self.registry.configFromDict({'type': 'fixture', 'value': 'node'})
        launch = self.registry.createKernel(config, 'direct')

        self.assertIsInstance(config, FixtureConfiguration)
        self.assertIsInstance(launch.kernel, FixtureKernel)
        self.assertTrue(launch.start())
        self.assertEqual(
            launch.kernel.calls,
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

                descriptor = ProtocolDescriptor('OTHER', 'Other', 'Add Other')

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


if __name__ == '__main__':
    unittest.main()
