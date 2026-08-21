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

"""Protect observational loading and lossless backend editor round trips."""

from __future__ import annotations

from Furious.Backends.Configuration import ConfigXray
from Furious.Backends.Hysteria1.Editor import GuiHy1ItemBasicProtocol
from Furious.Backends.Xray.TlsEditor import GuiVTLSQGroupBox
from Furious.Backends.Xray.TransportEditor import GuiVTransportQGroupBox

from tests.support import application, collectAtBoundary

import copy
import unittest


class BackendEditorContractTest(unittest.TestCase):
    """Verify mature editors preserve values they do not yet understand."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide Qt application used by real editor widgets."""
        application()

    def tearDown(self):
        """Process deferred Qt deletion between real-widget tests."""
        collectAtBoundary()

    @staticmethod
    def xrayConfiguration(streamSettings: dict) -> ConfigXray:
        """Return a minimal Xray document with one tagged proxy outbound."""
        return ConfigXray(
            {
                'outbounds': [
                    {
                        'tag': 'proxy',
                        'protocol': 'vless',
                        'streamSettings': copy.deepcopy(streamSettings),
                    }
                ]
            }
        )

    def testHysteria1UnknownProtocolIsVisibleAndPreserved(self):
        """Round-trip a future Hysteria 1 protocol through the shared combo."""
        binding = GuiHy1ItemBasicProtocol(title='Protocol', translatable=False)
        configuration = {'protocol': 'future-protocol'}
        original = copy.deepcopy(configuration)
        optionCount = binding._input.count()

        binding.factoryToInput(configuration)

        self.assertEqual(binding.text(), 'future-protocol')
        self.assertEqual(binding._input.count(), optionCount)
        self.assertEqual(binding._input.findText('future-protocol'), -1)
        self.assertEqual(configuration, original)
        self.assertFalse(binding.inputToFactory(configuration))
        self.assertEqual(configuration, original)

        for widget in binding.widgets():
            widget.deleteLater()

    def testXrayUnknownTransportIsVisibleAndPreserved(self):
        """Keep an unsupported transport and its settings untouched."""
        configuration = self.xrayConfiguration(
            {
                'network': 'future-transport',
                'futureTransportSettings': {
                    'token': 'preserve',
                    'futureField': 7,
                },
            }
        )
        original = copy.deepcopy(configuration)
        group = GuiVTransportQGroupBox()

        group.factoryToInput(configuration)

        self.assertEqual(configuration, original)
        self.assertEqual(
            group.page(group.currentIndex()).networkText(), 'future-transport'
        )
        self.assertFalse(group.inputToFactory(configuration))
        self.assertEqual(configuration, original)

        group.deleteLater()

    def testXrayTransportAliasIsNormalizedWhileLoading(self):
        """Normalize legacy upstream aliases while preserving their settings."""
        configuration = self.xrayConfiguration(
            {
                'network': 'http',
                'httpSettings': {
                    'host': ['example.com'],
                    'path': '/future-safe',
                    'futureField': {'preserve': True},
                },
            }
        )
        group = GuiVTransportQGroupBox()

        group.factoryToInput(configuration)

        self.assertEqual(
            configuration.proxyStreamSettingsObject['network'],
            'h2',
        )
        self.assertEqual(
            configuration.proxyStreamSettingsObject['httpSettings'],
            {
                'host': ['example.com'],
                'path': '/future-safe',
                'futureField': {'preserve': True},
            },
        )
        self.assertEqual(group.page(group.currentIndex()).networkText(), 'h2')
        self.assertFalse(group.inputToFactory(configuration))

        group.deleteLater()

    def testXrayUnknownSecurityIsVisibleAndPreserved(self):
        """Keep unsupported TLS modes and sibling settings untouched."""
        configuration = self.xrayConfiguration(
            {
                'network': 'tcp',
                'security': 'future-security',
                'future-securitySettings': {
                    'certificate': 'preserve',
                    'futureField': True,
                },
            }
        )
        original = copy.deepcopy(configuration)
        group = GuiVTLSQGroupBox()

        group.factoryToInput(configuration)

        self.assertEqual(configuration, original)
        self.assertEqual(
            group.page(group.currentIndex())._containers[0].text(),
            'future-security',
        )
        self.assertFalse(group.inputToFactory(configuration))
        self.assertEqual(configuration, original)

        group.deleteLater()


if __name__ == '__main__':
    unittest.main()
