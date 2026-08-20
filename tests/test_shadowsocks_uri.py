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

"""Exercise SIP002 canonical and generated Shadowsocks URI boundaries."""

from __future__ import annotations

from Furious.Backends.ShadowsocksURI import (
    ShadowsocksURIData,
    ShadowsocksURIError,
    formatPluginArgument,
    parseShadowsocksURI,
    serializeShadowsocksURI,
)
from Furious.Backends.Xray.Plugin import XrayPlugin
from Furious.Plugins import PluginRegistry, exportConfiguration, profileFromAny

import random
import string
import unittest


class ShadowsocksURITest(unittest.TestCase):
    """Protect round trips, encoding rules, IPv6, plugins, and rejection."""

    def testCanonicalRoundTripsReservedUnicodeAndIPv6Fields(self):
        """Preserve meaningful fields while canonicalizing SIP002 syntax."""
        plugin = formatPluginArgument(
            'simple-obfs',
            (
                ('obfs', 'http'),
                ('obfs-host', '例子.example'),
                ('escaped', r'a:b;c=d\e'),
            ),
        )
        cases = (
            ShadowsocksURIData(
                'aes-128-gcm',
                ' +/=: @% 密码 ',
                'example.com',
                443,
                '',
                'Tag with spaces 测试',
            ),
            ShadowsocksURIData(
                'chacha20-ietf-poly1305',
                'secret',
                '192.0.2.1',
                8388,
                plugin,
                'Plugin profile',
            ),
            ShadowsocksURIData(
                '2022-blake3-aes-128-gcm',
                'plain+/=:password',
                '2001:db8::42',
                8443,
                '',
                'IPv6',
            ),
        )

        for value in cases:
            with self.subTest(value=value):
                uri = serializeShadowsocksURI(value)

                self.assertNotIn(' ', uri)
                self.assertEqual(parseShadowsocksURI(uri), value)

                if ':' in value.host:
                    self.assertIn(f'@[{value.host}]:{value.port}', uri)

    def testPluginProfileExportPreservesShadowsocksMetadata(self):
        """Keep profile-only plugin arguments in the protocol capability."""
        value = ShadowsocksURIData(
            'aes-256-gcm',
            'secret',
            'example.com',
            443,
            formatPluginArgument(
                'simple-obfs',
                (('obfs', 'http'), ('obfs-host', 'cdn.example.com')),
            ),
            'Profile',
        )

        registry = PluginRegistry()
        registry.register(XrayPlugin())

        try:
            profile = profileFromAny(serializeShadowsocksURI(value), registry=registry)
            exported = exportConfiguration(profile, registry=registry)
        finally:
            registry.shutdown()

        self.assertEqual(parseShadowsocksURI(exported), value)

    def testUnknownQueryParametersAreIgnored(self):
        """Accept future SIP002 query keys without changing known meaning."""
        base = serializeShadowsocksURI(
            ShadowsocksURIData('aes-256-gcm', 'secret', 'example.com', 443)
        )
        parsed = parseShadowsocksURI(f'{base}/?future=value&another=1')

        self.assertEqual(parsed.method, 'aes-256-gcm')
        self.assertEqual(parsed.password, 'secret')
        self.assertEqual(parsed.plugin, '')

    def testDeterministicGeneratedRoundTrips(self):
        """Explore many safe strings without an optional property-test package."""
        randomizer = random.Random(20260817)
        alphabet = string.ascii_letters + string.digits + '+/=: @%_-'

        for index in range(75):
            password = ''.join(
                randomizer.choice(alphabet) for _character in range(1 + index % 19)
            )
            value = ShadowsocksURIData(
                ('2022-blake3-aes-256-gcm' if index % 5 == 0 else 'aes-256-gcm'),
                password,
                f'node-{index}.example',
                1024 + index,
                '',
                f'Generated {index}',
            )

            self.assertEqual(
                parseShadowsocksURI(serializeShadowsocksURI(value)),
                value,
            )

    def testMalformedUrisFailWithoutPartialResult(self):
        """Reject corrupt authority, encoding, cipher, credentials, and ports."""
        malformed = (
            'http://example.com',
            'ss://not-base64@example.com:443',
            'ss://YWVzLTEyOC1nY206@example.com:443',
            'ss://YWVzLTEyOC1nY206c2VjcmV0@example.com',
            'ss://YWVzLTEyOC1nY206c2VjcmV0@example.com:0',
            'ss://YWVzLTEyOC1nY206c2VjcmV0@example.com:70000',
            'ss://unsupported%3Asecret@example.com:443',
            'ss://2022-blake3-aes-128-gcm:bad%ZZ@example.com:443',
        )

        for uri in malformed:
            with self.subTest(uri=uri), self.assertRaises(ShadowsocksURIError):
                parseShadowsocksURI(uri)


if __name__ == '__main__':
    unittest.main()
