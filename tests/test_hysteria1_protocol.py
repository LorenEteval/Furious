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

"""Cover the complete Hysteria 1 protocol capability boundary."""

from __future__ import annotations

from Furious.Backends.Configuration import ConfigHysteria1
from Furious.Backends.Hysteria1.Plugin import (
    Hysteria1CoreRuntimeFactory,
    Hysteria1Plugin,
)
from Furious.Backends.Hysteria1.Protocols import HYSTERIA1_PROTOCOL_HANDLERS
from Furious.Plugins.API import CapabilityKind
from Furious.Plugins.Registry import PluginRegistry

from tests.support import application, collectAtBoundary, waitFor

from urllib.parse import quote

import copy
import unittest
import weakref


class Hysteria1ProtocolTest(unittest.TestCase):
    """Protect URI, mapping, editor, and runtime-copy compatibility."""

    @classmethod
    def setUpClass(cls):
        """Create Qt before asking the plugin for a transient editor."""
        application()

    def testCanonicalUriRoundTripPreservesAllSupportedFields(self):
        """Round-trip legacy flat fields, port hopping, and a Unicode remark."""
        remark = 'Hysteria 1 + 测试'
        uri = (
            'hysteria://example.com:443'
            '?mport=20000-30000'
            '&protocol=faketcp'
            '&auth=secret%3Avalue'
            '&peer=sni.example'
            '&insecure=1'
            '&upmbps=55'
            '&downmbps=120'
            '&alpn=h3'
            '&obfsParam=obfs%2Bvalue'
            f'#{quote(remark, safe="")}'
        )
        handler = HYSTERIA1_PROTOCOL_HANDLERS[0]
        parsed = handler.parse(uri)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata['displayName'], remark)

        configuration = parsed.configuration

        self.assertEqual(configuration['server'], 'example.com:443,20000-30000')
        self.assertEqual(configuration['protocol'], 'faketcp')
        self.assertEqual(configuration['auth_str'], 'secret:value')
        self.assertEqual(configuration['server_name'], 'sni.example')
        self.assertTrue(configuration['insecure'])
        self.assertEqual(configuration['up_mbps'], 55)
        self.assertEqual(configuration['down_mbps'], 120)
        self.assertEqual(configuration['alpn'], 'h3')
        self.assertEqual(configuration['obfs'], 'obfs+value')

        reparsed = handler.parse(handler.export(configuration, remark))

        self.assertIsNotNone(reparsed)
        self.assertEqual(reparsed.metadata['displayName'], remark)
        self.assertEqual(dict(reparsed.configuration), dict(configuration))

    def testMalformedUrisFailWithoutPartialConfiguration(self):
        """Reject wrong schemes and non-numeric bandwidth through one codec."""
        handler = HYSTERIA1_PROTOCOL_HANDLERS[0]

        for uri in (
            'hysteria2://example.com:443?upmbps=10&downmbps=20',
            'hysteria://example.com:443?upmbps=bad&downmbps=20',
            'hysteria://example.com:443?upmbps=10&downmbps=bad',
        ):
            with self.subTest(uri=uri):
                self.assertIsNone(handler.parse(uri))

    def testMappingRecognitionAvoidsAmbiguousServerOnlyDocuments(self):
        """Recognize Hysteria 1 fields without claiming another core's mapping."""
        handler = HYSTERIA1_PROTOCOL_HANDLERS[0]

        self.assertIsNone(handler.fromMapping({'server': 'example.com:443'}))

        configuration = handler.fromMapping(
            {
                'server': 'example.com:443',
                'protocol': 'udp',
                'futureField': {'preserved': True},
            }
        )

        self.assertIsInstance(configuration, ConfigHysteria1)
        self.assertEqual(
            configuration['futureField'],
            {'preserved': True},
        )

    def testDownloadPreparationUsesAnIndependentFullDocument(self):
        """Strip only SOCKS from the derived probe configuration."""
        original = ConfigHysteria1(
            {
                'server': 'example.com:443',
                'protocol': 'udp',
                'up_mbps': 20,
                'down_mbps': 80,
                'http': {'listen': '127.0.0.1:10809'},
                'socks5': {'listen': '127.0.0.1:10808'},
                'futureField': {'preserved': True},
            }
        )
        before = copy.deepcopy(dict(original))
        prepared = Hysteria1CoreRuntimeFactory().prepareDownloadTest(original, 19090)

        self.assertEqual(dict(original), before)
        self.assertIsNot(prepared, original)
        self.assertEqual(prepared['http']['listen'], '127.0.0.1:19090')
        self.assertNotIn('socks5', prepared)
        self.assertEqual(prepared['futureField'], {'preserved': True})

    def testPluginDiscoversProtocolEditorAndRuntimeCapabilities(self):
        """Keep Hysteria 1 entirely behind the generic plugin registry."""
        registry = PluginRegistry()
        plugin = Hysteria1Plugin()
        registry.register(plugin)

        try:
            self.assertIs(
                registry.plugin('official.hysteria1'),
                plugin,
            )
            self.assertEqual(
                len(
                    registry.capabilities(
                        CapabilityKind.Protocol,
                        plugin=plugin,
                    )
                ),
                1,
            )
            self.assertEqual(
                len(
                    registry.capabilities(
                        CapabilityKind.ProtocolEditor,
                        plugin=plugin,
                    )
                ),
                1,
            )
            self.assertEqual(
                len(
                    registry.capabilities(
                        CapabilityKind.CoreRuntimeFactory,
                        plugin=plugin,
                    )
                ),
                1,
            )

            configuration = ConfigHysteria1(
                {
                    'server': 'example.com:443',
                    'protocol': 'udp',
                    'up_mbps': 20,
                    'down_mbps': 80,
                }
            )
            editor = registry.createEditorForConfig(configuration)
            reference = weakref.ref(editor)

            editor.show()
            editor.close()
            editor = None

            self.assertTrue(waitFor(lambda: reference() is None))
        finally:
            registry.shutdown()
            collectAtBoundary()


if __name__ == '__main__':
    unittest.main()
