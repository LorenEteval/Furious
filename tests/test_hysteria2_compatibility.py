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

"""Protect Hysteria 2.12 client configuration and editor compatibility."""

from __future__ import annotations

from Furious.Backends.Configuration import ConfigHysteria2
from Furious.Backends.Hysteria2.Editor import (
    HY2_OBFS_TYPES,
    GuiHy2GroupBoxAdvanced,
    GuiHy2GroupBoxBasic,
    GuiHy2GroupBoxProxyBandwidth,
    GuiHy2GroupBoxTLS,
    Hysteria2Editor,
)
from Furious.Backends.Hysteria2.Process import Hysteria2
from Furious.Backends.Hysteria2.Protocols import Hysteria2ProtocolHandler
from Furious.Frozenlib import AppSettings, Mixins
from Furious.Models.Profile import ServerProfile

from tests.support import (
    application,
    closeTransient,
    collectAtBoundary,
    isolatedSettings,
)

import copy
import json
import unittest
import weakref


class Hysteria2CompatibilityTest(unittest.TestCase):
    """Verify model, URI, editor, runtime, and lifetime boundaries."""

    def setUp(self):
        """Create the isolated Qt application used by real editor widgets."""
        application()

    @staticmethod
    def profile(configuration: dict) -> ServerProfile:
        """Return one independent Hysteria 2 profile."""
        return ServerProfile.fromConfiguration(ConfigHysteria2(configuration))

    @staticmethod
    def binding(editor: Hysteria2Editor, path: tuple[str, ...]):
        """Return the structured editor binding for one upstream field path."""

        def descendants(binding):
            yield binding

            for child in getattr(binding, 'bindings', tuple()):
                yield from descendants(child)

        for group in editor.groupBoxSequence():
            for binding in getattr(group, '_containers', tuple()):
                for descendant in descendants(binding):
                    if getattr(descendant, 'path', None) == path:
                        return descendant

        raise AssertionError(f'no editor binding for {path!r}')

    @staticmethod
    def fullConfiguration() -> dict:
        """Return representative target-version client configuration."""
        return {
            'server': 'example.com:443',
            'auth': 'secret',
            'tls': {
                'sni': 'tls.example.com',
                'insecure': False,
                'pinSHA256': 'sha256-value',
                'ca': '/certificates/ca.pem',
                'clientCertificate': '/certificates/client.pem',
                'clientKey': '/certificates/client.key',
                'ech': 'AEz+example/config==',
                'futureTLSField': {'preserve': True},
            },
            'bandwidth': {
                'up': '20 mbps',
                'down': '100 mbps',
                'disableLossCompensation': True,
                'futureBandwidthField': 7,
            },
            'quic': {
                'initStreamReceiveWindow': 8388608,
                'maxStreamReceiveWindow': 16777216,
                'initConnReceiveWindow': 20971520,
                'maxConnReceiveWindow': 33554432,
                'maxIdleTimeout': '30s',
                'keepAlivePeriod': '10s',
                'disablePathMTUDiscovery': True,
                'disableChromeParrot': False,
                'sockopts': {
                    'bindInterface': 'eth0',
                    'fwmark': 1234,
                    'fdControlUnixSocket': '/run/fd-control.sock',
                    'futureSocketOption': 'preserved',
                },
            },
            'realm': {
                'stunServers': ['stun.example.com:3478', 'stun2.example.com:3478'],
                'stunTimeout': '5s',
                'punchTimeout': '6s',
                'insecure': False,
                'ipMode': 'v6',
                'portMapping': {
                    'enabled': True,
                    'timeout': '10s',
                    'lifetime': '10m',
                    'futureMappingField': 'preserved',
                },
            },
            'mimic': {
                'enabled': True,
                'interface': 'eth0',
                'xdpMode': 'native',
                'path': '/usr/local/bin/mimic',
                'extraArgs': ['--alpha', 'value with spaces'],
                'futureMimicField': {'preserve': True},
            },
            'fastOpen': True,
            'lazy': True,
            'unknownFutureGroup': {'enabled': True},
            'socks5': {'listen': '127.0.0.1:10808'},
            'http': {'listen': '127.0.0.1:10809'},
        }

    def testBlankEditorDoesNotMaterializeOptionalGroups(self):
        """Keep all optional upstream groups absent after an untouched save."""
        profile = self.profile(
            {
                'server': '',
                'socks5': {'listen': '127.0.0.1:10808'},
                'http': {'listen': '127.0.0.1:10809'},
            }
        )
        editor = Hysteria2Editor()

        editor.factoryToInput(profile)

        self.assertFalse(editor.inputToFactory(profile))

        for key in ('tls', 'bandwidth', 'quic', 'realm', 'mimic'):
            self.assertNotIn(key, profile.connection)

        self.assertNotIn('fastOpen', profile.connection)
        self.assertNotIn('lazy', profile.connection)

        editor.close()

    def testStructuredEditorPreservesCompleteAndUnknownConfiguration(self):
        """Round-trip target fields and benign future fields without churn."""
        original = self.fullConfiguration()
        profile = self.profile(original)
        editor = Hysteria2Editor()

        editor.factoryToInput(profile)

        self.assertFalse(editor.inputToFactory(profile))
        self.assertEqual(profile.connection, original)
        self.assertEqual(
            [type(group) for group in editor.groupBoxSequence()],
            [
                GuiHy2GroupBoxBasic,
                GuiHy2GroupBoxProxyBandwidth,
                GuiHy2GroupBoxAdvanced,
                GuiHy2GroupBoxTLS,
            ],
        )
        self.assertIs(editor.tabWidget.widget(0), editor.tabCentralWidget)

        positions = []

        for group in editor.groupBoxSequence():
            index = editor.tabCentralWidgetLayout.indexOf(group)
            row, column, _rowSpan, _columnSpan = (
                editor.tabCentralWidgetLayout.getItemPosition(index)
            )
            positions.append((row, column))

        self.assertEqual(positions, [(0, 0), (0, 1), (1, 0), (1, 1)])

        basic, proxyBandwidth, advanced, _tls = editor.groupBoxSequence()
        self.assertEqual(
            tuple(binding._title.text() for binding in basic._containers[-1].bindings),
            ('congestion-type', 'congestion-profile'),
        )
        self.assertEqual(
            tuple(
                binding._title.text() for binding in proxyBandwidth.proxyFields.bindings
            ),
            ('http', 'socks'),
        )
        self.assertEqual(
            tuple(
                binding._title.text()
                for binding in proxyBandwidth.bandwidthFields.bindings
            ),
            ('bandwidth.up', 'bandwidth.down'),
        )
        self.assertEqual(
            tuple(binding._title.text() for binding in advanced.optionsRow.bindings),
            ('ipMode', 'quic.disableChromeParrot', 'mimic.enabled'),
        )
        self.assertEqual(
            proxyBandwidth.bandwidthFields._widget.layout().contentsMargins().top(),
            20,
        )

        editor.show()
        application().processEvents()

        proxyInputPositions = tuple(
            binding._input.mapTo(proxyBandwidth, binding._input.rect().topLeft()).x()
            for binding in proxyBandwidth.proxyFields.bindings
        )
        bandwidthInputPositions = tuple(
            binding._input.mapTo(proxyBandwidth, binding._input.rect().topLeft()).x()
            for binding in proxyBandwidth.bandwidthFields.bindings
        )
        lossCompensationPosition = proxyBandwidth.lossCompensationItem._input.mapTo(
            proxyBandwidth,
            proxyBandwidth.lossCompensationItem._input.rect().topLeft(),
        ).x()

        self.assertEqual(len(set(proxyInputPositions)), 1)
        self.assertEqual(len(set(bandwidthInputPositions)), 1)
        self.assertNotEqual(proxyInputPositions[0], bandwidthInputPositions[0])
        self.assertNotEqual(proxyInputPositions[0], lossCompensationPosition)

        geckoPage = advanced.obfsItem.page(HY2_OBFS_TYPES.index('gecko'))
        advanced.obfsItem.setCurrentIndex(HY2_OBFS_TYPES.index('gecko'))
        application().processEvents()
        self.assertEqual(
            geckoPage.packetSizeRow.bindings,
            (
                geckoPage.minPacketSizeItem,
                geckoPage.maxPacketSizeItem,
            ),
        )
        self.assertIs(geckoPage._containers[-1], geckoPage.packetSizeRow)
        self.assertIs(advanced._containers[-1], advanced.optionsRow)
        self.assertEqual(len(advanced._containers), 2)

        for row in (
            basic._containers[-1],
            geckoPage.packetSizeRow,
            advanced.optionsRow,
        ):
            rowLayout = row._widget.layout()

            self.assertTrue(
                all(rowLayout.stretch(index) == 0 for index in range(rowLayout.count()))
            )

        editor.close()

    def testEditorWritesSemanticEnumsAndPositiveChromeToggle(self):
        """Persist upstream values rather than translated display labels."""
        profile = self.profile({'server': 'example.com:443', 'auth': 'secret'})
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        ipMode = self.binding(editor, ('realm', 'ipMode'))
        self.assertEqual(
            tuple(
                ipMode._input.itemText(index) for index in range(ipMode._input.count())
            ),
            ('dual', 'v4', 'v6'),
        )
        ipMode.setText('v4')
        chromeParrot = self.binding(editor, ('quic', 'disableChromeParrot'))
        chromeParrot.setChecked(True)
        mimicEnabled = self.binding(editor, ('mimic', 'enabled'))
        mimicEnabled.setChecked(True)

        self.assertTrue(editor.inputToFactory(profile))
        self.assertEqual(profile.connection['realm']['ipMode'], 'v4')
        self.assertTrue(profile.connection['mimic']['enabled'])
        self.assertTrue(profile.connection['quic']['disableChromeParrot'])

        editor.close()

    def testNestedSwitchPersistsFalseAfterDoubleToggle(self):
        """Keep an existing false value when a double toggle returns to it."""
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'mimic': {'enabled': False},
            }
        )
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        mimicEnabled = self.binding(editor, ('mimic', 'enabled'))
        mimicEnabled.setChecked(True)
        mimicEnabled.setChecked(False)

        self.assertFalse(editor.inputToFactory(profile))
        self.assertIs(profile.connection['mimic']['enabled'], False)

        editor.close()

    def testVisibleEditsPreserveRepresentativeJSONOnlyFields(self):
        """Modify compact controls without deleting advanced sibling settings."""
        original = self.fullConfiguration()
        profile = self.profile(original)
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        self.binding(editor, ('tls', 'sni')).setText('changed.example.com')
        self.binding(editor, ('bandwidth', 'up')).setText('30 mbps')
        self.binding(editor, ('quic', 'disableChromeParrot')).setChecked(True)

        ipMode = self.binding(editor, ('realm', 'ipMode'))
        ipMode.setText('v4')
        self.binding(editor, ('mimic', 'enabled')).setChecked(False)

        self.assertTrue(editor.inputToFactory(profile))

        connection = profile.connection

        self.assertEqual(
            connection['tls']['clientCertificate'], '/certificates/client.pem'
        )
        self.assertEqual(connection['tls']['clientKey'], '/certificates/client.key')
        self.assertEqual(connection['tls']['futureTLSField'], {'preserve': True})
        self.assertEqual(connection['bandwidth']['futureBandwidthField'], 7)
        self.assertEqual(connection['quic']['maxIdleTimeout'], '30s')
        self.assertEqual(connection['quic']['sockopts'], original['quic']['sockopts'])
        self.assertEqual(
            connection['realm']['stunServers'], original['realm']['stunServers']
        )
        self.assertEqual(
            connection['realm']['portMapping'], original['realm']['portMapping']
        )
        self.assertFalse(connection['mimic']['enabled'])
        self.assertEqual(connection['mimic']['interface'], 'eth0')
        self.assertEqual(connection['mimic']['xdpMode'], 'native')
        self.assertEqual(
            connection['mimic']['futureMimicField'],
            {'preserve': True},
        )

        editor.close()

    def testCompactEditorUsesUpstreamTechnicalFieldLabels(self):
        """Keep schema-oriented field names stable across UI languages."""
        expected = {
            ('tls', 'sni'): 'sni',
            ('tls', 'pinSHA256'): 'pinSHA256',
            ('tls', 'ca'): 'ca',
            ('tls', 'ech'): 'ech',
            ('tls', 'insecure'): 'insecure',
            ('bandwidth', 'up'): 'bandwidth.up',
            ('bandwidth', 'down'): 'bandwidth.down',
            (
                'bandwidth',
                'disableLossCompensation',
            ): 'bandwidth.disableLossCompensation',
            ('quic', 'disableChromeParrot'): 'quic.disableChromeParrot',
            ('realm', 'ipMode'): 'ipMode',
            ('mimic', 'enabled'): 'mimic.enabled',
        }

        with isolatedSettings():
            AppSettings.set('Language', 'ZH')
            editor = Hysteria2Editor()

            self.assertEqual(editor.groupBoxSequence()[1].title(), '代理 && 带宽')
            self.assertEqual(editor.groupBoxSequence()[2].title(), '高级')

            for language, proxyTitle, advancedTitle in (
                ('RU', 'Прокси и пропускная способность', 'Дополнительно'),
                ('EN', 'Proxy & Bandwidth', 'Advanced'),
            ):
                AppSettings.set('Language', language)
                Mixins.QTranslatable.retranslateAll()

                with self.subTest(language=language):
                    self.assertEqual(
                        editor.groupBoxSequence()[1].title().replace('&&', '&'),
                        proxyTitle,
                    )
                    self.assertEqual(
                        editor.groupBoxSequence()[2].title(), advancedTitle
                    )

                    for path, label in expected.items():
                        self.assertEqual(
                            self.binding(editor, path)._title.text(), label
                        )

            editor.close()

    def testUnknownEnumAndObfsValuesCanBeReplacedDirectly(self):
        """Replace represented future values without interaction shadow state."""
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'realm': {'ipMode': 'future-mode'},
                'obfs': {
                    'type': 'future-obfs',
                    'future-obfs': {'token': 'discard'},
                },
            }
        )
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        ipMode = self.binding(editor, ('realm', 'ipMode'))
        ipMode.setText('v6')
        editor.advancedGroup.obfsItem.handleActivated(
            HY2_OBFS_TYPES.index('salamander')
        )

        self.assertTrue(editor.inputToFactory(profile))
        self.assertEqual(profile.connection['realm']['ipMode'], 'v6')
        self.assertEqual(profile.connection['obfs']['type'], 'salamander')
        self.assertNotIn('future-obfs', profile.connection['obfs'])

        editor.close()

    def testUnknownCompactEditorValuesNormalizeToKnownDefaults(self):
        """Normalize unsupported represented values while preserving other data."""
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'realm': {
                    'ipMode': 'future-mode',
                    'futureRealmField': {'preserve': True},
                },
                'congestion': {
                    'type': 'future-congestion',
                    'bbrProfile': 'future-profile',
                    'futureCongestionField': 7,
                },
                'obfs': {
                    'type': 'future-obfs',
                    'future-obfs': {
                        'token': 'preserve',
                        'futureOption': True,
                    },
                },
            }
        )
        original = copy.deepcopy(profile.connection)
        editor = Hysteria2Editor()

        editor.factoryToInput(profile)

        self.assertEqual(profile.connection, original)
        self.assertEqual(
            self.binding(editor, ('realm', 'ipMode')).text(),
            'dual',
        )
        self.assertEqual(
            editor.basicGroup._containers[3].bindings[0].text(),
            '',
        )
        self.assertEqual(
            editor.basicGroup._containers[3].bindings[1].text(),
            '',
        )
        self.assertEqual(
            editor.advancedGroup.obfsItem.page(
                editor.advancedGroup.obfsItem.currentIndex()
            ).obfsTypeText(),
            '',
        )
        self.assertTrue(editor.inputToFactory(profile))
        self.assertEqual(
            profile.connection['realm'],
            {
                'ipMode': 'dual',
                'futureRealmField': {'preserve': True},
            },
        )
        self.assertEqual(
            profile.connection['congestion'],
            {'futureCongestionField': 7},
        )
        self.assertNotIn('obfs', profile.connection)

        editor.close()

    def testSavingCongestionNormalizesUnknownRepresentedSiblings(self):
        """Clear unsupported represented values while preserving JSON-only data."""
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'congestion': {
                    'type': 'bbr',
                    'bbrProfile': 'fast',
                    'futureCongestionField': {'preserve': True},
                },
            }
        )
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        editor.basicGroup._containers[3].bindings[0].setText('')

        self.assertTrue(editor.inputToFactory(profile))
        self.assertNotIn('type', profile.connection['congestion'])
        self.assertNotIn('bbrProfile', profile.connection['congestion'])
        self.assertEqual(
            profile.connection['congestion']['futureCongestionField'],
            {'preserve': True},
        )

        editor.close()

    def testImplicitGeckoPacketDefaultsRemainAbsent(self):
        """Do not materialize effective Gecko defaults during an untouched save."""
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'obfs': {
                    'type': 'gecko',
                    'gecko': {
                        'password': 'secret',
                        'futureGeckoField': {'preserve': True},
                    },
                },
            }
        )
        original = copy.deepcopy(profile.connection)
        editor = Hysteria2Editor()

        editor.factoryToInput(profile)

        self.assertFalse(editor.inputToFactory(profile))
        self.assertEqual(profile.connection, original)

        editor.close()

    def testStandardURIUsesPercentEncodingAndRoundTripsECHAndGecko(self):
        """Follow upstream URI escaping without form-style plus semantics."""
        original = ConfigHysteria2(
            {
                'server': '[2001:db8::1]:443',
                'auth': 'name:p+a ss/@%',
                'tls': {
                    'sni': 'example.com',
                    'insecure': True,
                    'pinSHA256': 'pin+/=',
                    'ech': 'AEz+config/list==',
                },
                'obfs': {
                    'type': 'gecko',
                    'gecko': {'password': 'p+a ss&%'},
                },
            }
        )

        uri = original.toURI('Unicode tag 名')
        parsed = ConfigHysteria2(uri)

        self.assertNotIn(' ', uri)
        self.assertIn('p%2Ba%20ss', uri)
        self.assertIn('%2F', uri)
        self.assertEqual(parsed['server'], original['server'])
        self.assertEqual(parsed['auth'], original['auth'])
        self.assertEqual(parsed['tls'], original['tls'])
        self.assertEqual(parsed['obfs'], original['obfs'])

    def testRealmURIPreservesRepeatedSTUNAndLiteralPlus(self):
        """Keep Realm discovery items and query authentication losslessly."""
        original = ConfigHysteria2(
            {
                'server': (
                    'realm://rendezvous.example:443/room?'
                    'stun=one%2Btwo&stun=two.example%3A3478&lport=3456'
                ),
                'auth': 'p+a ss',
                'tls': {'ech': 'AEz+realm=='},
            }
        )

        uri = original.toURI('Realm')
        parsed = ConfigHysteria2(uri)

        self.assertEqual(parsed['auth'], original['auth'])
        self.assertEqual(parsed['server'], original['server'])
        self.assertEqual(parsed['tls']['ech'], original['tls']['ech'])
        self.assertEqual(parsed['server'].count('stun='), 2)

    def testECHEncodedAndFileFormsSurviveStructuredEditor(self):
        """Treat ECH content as an opaque encoded value or file path."""
        for ech in ('AEz+encoded/config==', '/etc/hysteria/ech.pem'):
            with self.subTest(ech=ech):
                profile = self.profile(
                    {
                        'server': 'example.com:443',
                        'auth': 'secret',
                        'tls': {'ech': ech},
                    }
                )
                editor = Hysteria2Editor()

                editor.factoryToInput(profile)

                self.assertFalse(editor.inputToFactory(profile))
                self.assertEqual(profile.connection['tls']['ech'], ech)

                editor.close()

    def testOldProfileEditPreservesEstablishedConfiguration(self):
        """Edit one old-era field without changing established client options."""
        original = {
            'server': 'old.example.com:443',
            'auth': 'old-secret',
            'tls': {
                'sni': 'old.example.com',
                'insecure': False,
            },
            'obfs': {
                'type': 'salamander',
                'salamander': {'password': 'old-obfs-secret'},
            },
            'socks5': {'listen': '127.0.0.1:10808'},
            'http': {'listen': '127.0.0.1:10809'},
        }
        profile = self.profile(original)
        editor = Hysteria2Editor()
        editor.factoryToInput(profile)

        editor.basicGroup._containers[2].setText('new-secret')

        self.assertTrue(editor.inputToFactory(profile))
        self.assertEqual(profile.connection['auth'], 'new-secret')
        self.assertEqual(
            {key: value for key, value in profile.connection.items() if key != 'auth'},
            {key: value for key, value in original.items() if key != 'auth'},
        )

        editor.close()

    def testMimicConfigurationIsPreservedIndependentOfHostPlatform(self):
        """Keep portable Linux-only Mimic data on every editor host platform."""
        mimic = {
            'enabled': True,
            'interface': 'eth0',
            'xdpMode': 'skb',
            'path': '/opt/mimic/mimic',
            'extraArgs': ['--queue', '4', 'argument with spaces'],
            'futureOption': {'keep': True},
        }
        profile = self.profile(
            {
                'server': 'example.com:443',
                'auth': 'secret',
                'mimic': copy.deepcopy(mimic),
            }
        )
        editor = Hysteria2Editor()

        editor.factoryToInput(profile)

        self.assertFalse(editor.inputToFactory(profile))
        self.assertEqual(profile.connection['mimic'], mimic)

        editor.close()

    def testProtocolValidationRejectsInvalidEnumsAndMimicPortHopping(self):
        """Catch editor-level enum errors and the documented Mimic conflict."""
        handler = Hysteria2ProtocolHandler()
        configuration = ConfigHysteria2(
            {
                'server': 'example.com:443,8443',
                'auth': 'secret',
                'realm': {'ipMode': 'invalid'},
                'mimic': {'enabled': True, 'xdpMode': 'invalid'},
            }
        )

        errors = handler.validate(configuration)

        self.assertIn('Invalid Realm IP mode', errors)
        self.assertIn('Invalid Mimic XDP mode', errors)
        self.assertIn('Mimic cannot be used with port hopping', errors)

    def testRuntimeLaunchReceivesAuthoritativeFullJSON(self):
        """Submit target-version fields directly to startFromJSON's boundary."""
        configuration = ConfigHysteria2(self.fullConfiguration())
        runtime = Hysteria2()

        try:
            launchSpec = runtime.launchSpec(configuration)
            submitted = json.loads(launchSpec.args[0])

            self.assertEqual(submitted, configuration)
            self.assertEqual(submitted['realm']['ipMode'], 'v6')
            self.assertEqual(submitted['tls']['ech'], 'AEz+example/config==')
            self.assertTrue(submitted['bandwidth']['disableLossCompensation'])
            self.assertFalse(submitted['quic']['disableChromeParrot'])
            self.assertEqual(submitted['mimic'], configuration['mimic'])
        finally:
            runtime.dispose()

    def testEditorIsDestroyedAcrossRepeatedOpenCloseCycles(self):
        """Release the compact persistent group tree with each transient dialog."""
        references = []

        for _index in range(20):
            editor = Hysteria2Editor()
            editor.show()
            references.append(
                (
                    weakref.ref(editor),
                    tuple(weakref.ref(group) for group in editor.groupBoxSequence()),
                )
            )
            closeTransient(editor)

        del editor

        collectAtBoundary()

        self.assertTrue(
            all(
                editorReference() is None
                and all(groupReference() is None for groupReference in groupReferences)
                for editorReference, groupReferences in references
            )
        )


if __name__ == '__main__':
    unittest.main()
