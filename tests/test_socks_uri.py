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

"""Verify interoperable and centralized SOCKS share-link handling."""

from __future__ import annotations

from Furious.Backends.Configuration import ConfigXray
from Furious.Backends.SocksURI import (
    SocksURIData,
    SocksURIError,
    parseSocksURI,
    serializeSocksURI,
)
from Furious.Backends.Xray.Protocols import XRAY_PROTOCOL_HANDLERS
from Furious.Extensions.StandardSubscriptions import StandardSubscriptionPlugin
from Furious.Plugins.API import FuriousPlugin, PluginMetadata
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)

from urllib.parse import quote

import base64
import unittest


class SocksURICodecTest(unittest.TestCase):
    """Exercise canonical export and compatibility import forms."""

    def testBasicHostnameAndIPv4Imports(self):
        """Parse unauthenticated hostnames and IPv4 endpoints."""
        self.assertEqual(
            parseSocksURI('socks://example.com:1080'),
            SocksURIData('example.com', 1080),
        )
        self.assertEqual(
            parseSocksURI('socks5://127.0.0.1:1081#Local'),
            SocksURIData('127.0.0.1', 1081, tag='Local'),
        )

    def testDirectCredentialsUseStrictPercentDecoding(self):
        """Preserve reserved characters without form-style plus decoding."""
        uri = (
            'socks://user%40name:'
            'p%3Aa%23ss%25word%2Fwith%20space%2Bplus@example.com:1080'
            '#My%20SOCKS%20%23%25%20服务器'
        )

        self.assertEqual(
            parseSocksURI(uri),
            SocksURIData(
                'example.com',
                1080,
                'user@name',
                'p:a#ss%word/with space+plus',
                'My SOCKS #% 服务器',
            ),
        )

    def testV2rayNBase64UserinfoCompatibility(self):
        """Accept v2rayN's standard and URL-safe Base64 userinfo."""
        value = SocksURIData('example.com', 1080, 'user', 'pass', 'Remark')

        self.assertEqual(
            parseSocksURI('socks://dXNlcjpwYXNz@example.com:1080#Remark'),
            value,
        )

        credentials = base64.urlsafe_b64encode('用户:密码/@'.encode('utf-8')).decode(
            'ascii'
        )
        uri = f'socks5://{quote(credentials, safe="")}@example.com:1080'

        self.assertEqual(
            parseSocksURI(uri),
            SocksURIData('example.com', 1080, '用户', '密码/@'),
        )

    def testLegacyWholePayloadCompatibility(self):
        """Accept the historical Base64 credentials-and-endpoint payload."""
        payload = base64.b64encode(b'user:pass@example.com:1080').decode('ascii')

        self.assertEqual(
            parseSocksURI(f'socks://{payload}#Legacy%20Node'),
            SocksURIData('example.com', 1080, 'user', 'pass', 'Legacy Node'),
        )

        ipv6Payload = base64.b64encode(b'user:pass@2001:db8::1:1080').decode('ascii')

        self.assertEqual(
            parseSocksURI(f'socks://{ipv6Payload}'),
            SocksURIData('2001:db8::1', 1080, 'user', 'pass'),
        )

    def testIPv6RoundTripUsesBrackets(self):
        """Keep IPv6 colons separate from the URI port delimiter."""
        value = SocksURIData('2001:0db8::1', 1080, 'user', 'pass', 'IPv6')
        uri = serializeSocksURI(value)

        self.assertEqual(
            uri,
            'socks://user:pass@[2001:db8::1]:1080#IPv6',
        )
        self.assertEqual(
            parseSocksURI(uri),
            SocksURIData('2001:db8::1', 1080, 'user', 'pass', 'IPv6'),
        )

    def testCanonicalExportUsesInteroperableSocksAuthority(self):
        """Export one socks scheme with unambiguous percent-encoded userinfo."""
        self.assertEqual(
            serializeSocksURI(
                SocksURIData('example.com', 1080, 'user', 'pass', 'My SOCKS')
            ),
            'socks://user:pass@example.com:1080#My%20SOCKS',
        )
        self.assertEqual(
            serializeSocksURI(SocksURIData('example.com', 1080)),
            'socks://example.com:1080',
        )

    def testUnicodeCredentialsAndTagRoundTrip(self):
        """Round-trip Unicode through UTF-8 Base64 and percent encoding."""
        value = SocksURIData(
            'xn--fsqu00a.xn--0zwm56d',
            1080,
            '用户',
            '密码:@#% /',
            '测试 SOCKS #%',
        )

        self.assertEqual(parseSocksURI(serializeSocksURI(value)), value)

    def testCompatibilitySchemeAliasesAreCaseInsensitive(self):
        """Accept existing Furious aliases and v2rayN's SOCKS4 alias."""
        for scheme in ('SOCKS', 'socks5', 'socks5h', 'socks4'):
            with self.subTest(scheme=scheme):
                self.assertEqual(
                    parseSocksURI(f'{scheme}://example.com:1080'),
                    SocksURIData('example.com', 1080),
                )

    def testMalformedLinksFailCleanly(self):
        """Reject corrupt authority, credentials, and URI components."""
        invalid = (
            '',
            'http://example.com:1080',
            'socks://:1080',
            'socks://example.com',
            'socks://example.com:0',
            'socks://example.com:65536',
            'socks://example.com:not-a-port',
            'socks://[2001:db8::1:1080',
            'socks://not-base64@example.com:1080',
            'socks://user%ZZ:pass@example.com:1080',
            'socks://example.com:1080/path',
            'socks://example.com:1080?unsupported=1',
            'socks://example.com:1080#bad%',
        )

        for uri in invalid:
            with self.subTest(uri=uri):
                with self.assertRaises(SocksURIError):
                    parseSocksURI(uri)


class SocksURIIntegrationTest(unittest.TestCase):
    """Verify the codec at Xray configuration and plugin boundaries."""

    def testConfigImportPreservesRuntimeFieldsAndRemark(self):
        """Pass imported credentials into Xray's SOCKS outbound settings."""
        handler = next(
            item for item in XRAY_PROTOCOL_HANDLERS if item.descriptor.id == 'SOCKS'
        )
        result = handler.parse(
            'socks://user%40name:p%3Aass@[2001:db8::1]:1080#My%20Node'
        )
        config = result.configuration

        self.assertEqual(config.proxyProtocol, 'socks')
        self.assertEqual(
            config.proxyServerObject,
            {
                'address': '2001:db8::1',
                'port': 1080,
                'user': 'user@name',
                'pass': 'p:ass',
            },
        )
        self.assertEqual(result.metadata['displayName'], 'My Node')

    def testConfigExportAndReimportPreserveSemantics(self):
        """Share a persisted SOCKS outbound through the centralized codec."""
        original = ConfigXray(
            {
                'outbounds': [
                    {
                        'tag': 'proxy',
                        'protocol': 'socks',
                        'settings': {
                            'address': 'example.com',
                            'port': 1080,
                            'user': 'user:@',
                            'pass': 'password #%',
                        },
                    }
                ]
            }
        )
        uri = original.toURI('共享 SOCKS')
        handler = next(
            item for item in XRAY_PROTOCOL_HANDLERS if item.descriptor.id == 'SOCKS'
        )
        result = handler.parse(uri)
        reparsed = result.configuration

        self.assertTrue(uri.startswith('socks://'))
        self.assertEqual(reparsed.proxyServerObject, original.proxyServerObject)
        self.assertEqual(result.metadata['displayName'], '共享 SOCKS')

    def testProtocolCapabilityOwnsAllAliasesAndValidatesEndpoint(self):
        """Keep URI dispatch and semantic validation inside the SOCKS handler."""
        handler = next(
            item for item in XRAY_PROTOCOL_HANDLERS if item.descriptor.id == 'SOCKS'
        )

        self.assertEqual(
            set(handler.schemes),
            {'socks', 'socks5', 'socks5h', 'socks4'},
        )

        parsed = handler.parse('socks5://dXNlcjpwYXNz@example.com:1080#Node')

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata['displayName'], 'Node')
        self.assertEqual(handler.validate(parsed.configuration), tuple())

        parsed.configuration.proxyServerObject['port'] = 0

        self.assertIn(
            'server port must be between 1 and 65535',
            handler.validate(parsed.configuration),
        )

    def testLineSubscriptionUsesTheRegisteredSocksCodec(self):
        """Route subscription links through the same protocol capability."""
        handler = next(
            item for item in XRAY_PROTOCOL_HANDLERS if item.descriptor.id == 'SOCKS'
        )

        class SocksOnlyPlugin(FuriousPlugin):
            """Register only the SOCKS capability needed by this fixture."""

            metadata = PluginMetadata('test.socks', 'Test SOCKS')
            capabilities = (handler,)

        registry = PluginRegistry()
        registry.register(SocksOnlyPlugin())
        registry.register(StandardSubscriptionPlugin())

        try:
            result = SubscriptionImportService(registry).importPayload(
                b'socks://dXNlcjpwYXNz@example.com:1080#Subscribed%20SOCKS',
                SubscriptionSource('fixture'),
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.rejectedItems, 0)
            self.assertEqual(len(result.profiles), 1)
            self.assertEqual(result.profiles[0].itemRemark, 'Subscribed SOCKS')
            self.assertEqual(
                result.profiles[0].connection.proxyServerObject,
                {
                    'address': 'example.com',
                    'port': 1080,
                    'user': 'user',
                    'pass': 'pass',
                },
            )
            self.assertEqual(
                registry.exportConfig(result.profiles[0]),
                'socks://user:pass@example.com:1080#Subscribed%20SOCKS',
            )
        finally:
            registry.shutdown()


if __name__ == '__main__':
    unittest.main()
