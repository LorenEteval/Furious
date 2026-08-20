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

"""Protect native-TUN ownership for normal and proxy-only operations."""

from __future__ import annotations

from unittest import mock

import copy
import unittest

from Furious.Backends.Configuration import ConfigHysteria2, ConfigXray
from Furious.Backends.Hysteria2 import Plugin as Hysteria2PluginModule
from Furious.Backends.Hysteria2.Plugin import Hysteria2CoreRuntimeFactory
from Furious.Backends.Xray import Plugin as XrayPluginModule
from Furious.Backends.Xray.Plugin import XrayCoreRuntimeFactory
from Furious.Plugins.API import TUNPreparationError
from Furious.Plugins.Registry import PluginRegistry
from Furious.Service.ConnectionManager import ConnectionManager


class _RecordingConnectionManager(ConnectionManager):
    """Capture the runtime document without starting a core process."""

    def _startCoreRuntime(self, config, *_args, **_kwargs):
        """Record the prepared runtime configuration as a successful launch."""
        self.runtimeConfiguration = config

        return None, True


class XrayNativeTUNTest(unittest.TestCase):
    """Verify Xray runtime copies preserve or replace native TUN intentionally."""

    customTUN = {
        'tag': 'user-tun',
        'protocol': 'tun',
        'settings': {'gateway': ['192.0.2.1/24']},
    }
    generatedTUN = {
        'tag': 'tun',
        'protocol': 'tun',
        'settings': {'gateway': ['10.0.0.1/16']},
    }
    httpInbound = {'tag': 'http', 'protocol': 'http'}

    def setUp(self):
        """Create one stateless Xray core-runtime capability."""
        self.factory = XrayCoreRuntimeFactory()

    def configuration(self, *, nativeTUN: bool) -> ConfigXray:
        """Return one minimal Xray document with optional custom native TUN."""
        inbounds = [copy.deepcopy(self.httpInbound)]

        if nativeTUN:
            inbounds.append(copy.deepcopy(self.customTUN))

        return ConfigXray({'inbounds': inbounds, 'outbounds': []})

    def prepare(self, original, enabled):
        """Prepare an independent runtime copy under one toggle state."""
        runtime = original.deepcopy()

        with (
            mock.patch.object(
                XrayPluginModule,
                'isXrayTUNEnabled',
                return_value=enabled,
            ),
            mock.patch.object(
                XrayPluginModule,
                'buildXrayTUNInbound',
                return_value=copy.deepcopy(self.generatedTUN),
            ),
        ):
            handled = self.factory.prepareTUN(runtime)

        return runtime, handled

    def testExistingTUNIsReplacedWhenManagedTUNIsEnabled(self):
        """Replace every runtime TUN inbound without changing persisted JSON."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, True)

        self.assertTrue(handled)
        self.assertEqual(original, snapshot)
        self.assertEqual(runtime['inbounds'], [self.httpInbound, self.generatedTUN])
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testExistingTUNIsPreservedWhenManagedTUNIsDisabled(self):
        """Treat a user TUN inbound as authoritative for normal connection."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, False)

        self.assertTrue(handled)
        self.assertEqual(runtime, original)
        self.assertEqual(original, snapshot)
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testGeneratedTUNIsInjectedWhenEnabledAndMissing(self):
        """Inject Furious-managed Xray TUN into only the runtime copy."""
        original = self.configuration(nativeTUN=False)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, True)

        self.assertTrue(handled)
        self.assertEqual(original, snapshot)
        self.assertEqual(runtime['inbounds'], [self.httpInbound, self.generatedTUN])
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testMissingTUNLeavesApplicationFallbackAvailableWhenDisabled(self):
        """Report no native owner so global TUN may use application tun2socks."""
        original = self.configuration(nativeTUN=False)

        runtime, handled = self.prepare(original, False)

        self.assertFalse(handled)
        self.assertEqual(runtime, original)
        self.assertTrue(self.factory.usesApplicationTun2socks(runtime))

    def testDownloadTestExplicitlyStripsNativeTUN(self):
        """Keep normal custom TUN while deriving a TUN-free speed-test copy."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, False)
        speedTest = self.factory.prepareDownloadTest(original, 18080)

        self.assertTrue(handled)
        self.assertEqual(runtime, original)
        self.assertEqual(original, snapshot)
        self.assertFalse(
            any(inbound.get('protocol') == 'tun' for inbound in speedTest['inbounds'])
        )

    def testConnectionManagerDoesNotPairCustomTUNWithTun2socks(self):
        """Stop host tun2socks selection once Xray reports custom native TUN."""
        original = self.configuration(nativeTUN=True)
        registry = mock.Mock()
        registry.prepareTUN.side_effect = self.factory.prepareTUN
        registry.usesApplicationTun2socks.side_effect = (
            self.factory.usesApplicationTun2socks
        )
        manager = _RecordingConnectionManager()

        with (
            mock.patch.object(
                XrayPluginModule,
                'isXrayTUNEnabled',
                return_value=False,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=True,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.getPluginRegistry',
                return_value=registry,
            ),
            mock.patch('Furious.Service.ConnectionManager.Tun2socks') as tun2socks,
        ):
            self.assertTrue(manager.start(original, 'Global'))

        registry.usesApplicationTun2socks.assert_not_called()
        tun2socks.assert_not_called()

        self.assertEqual(manager.runtimeConfiguration, original)

        manager.cleanup()

    def testManagedTUNPreparationFailureDoesNotFallBackToTun2socks(self):
        """Fail an unavailable managed TUN instead of changing networking mode."""
        original = self.configuration(nativeTUN=True)
        registry = mock.Mock()
        registry.prepareTUN.side_effect = TUNPreparationError('managed TUN failed')
        manager = _RecordingConnectionManager()

        with (
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=True,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.getPluginRegistry',
                return_value=registry,
            ),
            mock.patch('Furious.Service.ConnectionManager.Tun2socks') as tun2socks,
        ):
            self.assertFalse(manager.start(original, 'Global'))

        self.assertEqual(manager.lastStartError, 'managed TUN failed')

        registry.usesApplicationTun2socks.assert_not_called()
        tun2socks.assert_not_called()

        self.assertFalse(hasattr(manager, 'runtimeConfiguration'))

    def testRegistryPropagatesIntentionalTUNPreparationFailure(self):
        """Keep the explicit failure distinct from an unsupported capability."""
        registry = PluginRegistry()

        factory = mock.Mock(factoryId='managed-tun-factory')
        factory.prepareTUN.side_effect = TUNPreparationError('managed TUN failed')

        registry.factoryForConfig = mock.Mock(return_value=factory)

        with self.assertRaisesRegex(TUNPreparationError, 'managed TUN failed'):
            registry.prepareTUN(self.configuration(nativeTUN=False))


class Hysteria2NativeTUNTest(unittest.TestCase):
    """Verify Hysteria 2 runtime copies preserve or replace native TUN."""

    customTUN = {
        'name': 'user-tun',
        'address': {'ipv4': '192.0.2.1/30'},
    }
    generatedTUN = {
        'name': 'hytun',
        'address': {'ipv4': '100.100.100.101/30'},
    }

    def setUp(self):
        """Create one stateless Hysteria 2 core-runtime capability."""
        self.factory = Hysteria2CoreRuntimeFactory()

    def configuration(self, *, nativeTUN: bool) -> ConfigHysteria2:
        """Return one minimal Hysteria 2 document with optional custom TUN."""
        config = ConfigHysteria2(
            {
                'server': '203.0.113.10:443',
                'http': {'listen': '127.0.0.1:10809'},
            }
        )

        if nativeTUN:
            config['tun'] = copy.deepcopy(self.customTUN)

        return config

    def prepare(self, original, enabled):
        """Prepare an independent runtime copy under one toggle state."""
        runtime = original.deepcopy()

        with (
            mock.patch.object(
                Hysteria2PluginModule,
                'isHysteria2TUNEnabled',
                return_value=enabled,
            ),
            mock.patch.object(Hysteria2PluginModule, 'PLATFORM', 'Windows'),
            mock.patch.object(
                Hysteria2PluginModule,
                'getHysteria2TUNSettings',
                return_value={},
            ),
            mock.patch.object(
                Hysteria2PluginModule,
                'resolveHysteria2ServerAddresses',
                return_value=['203.0.113.10'],
            ),
            mock.patch.object(
                Hysteria2PluginModule,
                'buildHysteria2TUNConfig',
                return_value=copy.deepcopy(self.generatedTUN),
            ),
        ):
            handled = self.factory.prepareTUN(runtime)

        return runtime, handled

    def testExistingTUNIsReplacedWhenManagedTUNIsEnabled(self):
        """Replace the runtime block without changing the persisted document."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, True)

        self.assertTrue(handled)
        self.assertEqual(runtime['tun'], self.generatedTUN)
        self.assertEqual(original, snapshot)
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testExistingTUNIsPreservedWhenManagedTUNIsDisabled(self):
        """Treat a user TUN block as authoritative for normal connection."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, False)

        self.assertTrue(handled)
        self.assertEqual(runtime, original)
        self.assertEqual(original, snapshot)
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testMalformedExplicitTUNStillPreventsSilentFallback(self):
        """Leave validation of an explicit malformed block to Hysteria 2."""
        original = self.configuration(nativeTUN=False)
        original['tun'] = 'malformed-user-value'

        runtime, handled = self.prepare(original, False)

        self.assertTrue(handled)
        self.assertEqual(runtime['tun'], 'malformed-user-value')
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testGeneratedTUNIsInjectedWhenEnabledAndMissing(self):
        """Inject Furious-managed Hysteria 2 TUN into only the runtime copy."""
        original = self.configuration(nativeTUN=False)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, True)

        self.assertTrue(handled)
        self.assertEqual(runtime['tun'], self.generatedTUN)
        self.assertEqual(original, snapshot)
        self.assertFalse(self.factory.usesApplicationTun2socks(runtime))

    def testMissingTUNLeavesApplicationFallbackAvailableWhenDisabled(self):
        """Report no native owner so global TUN may use application tun2socks."""
        original = self.configuration(nativeTUN=False)

        runtime, handled = self.prepare(original, False)

        self.assertFalse(handled)
        self.assertEqual(runtime, original)
        self.assertTrue(self.factory.usesApplicationTun2socks(runtime))

    def testUnavailableManagedTUNFailsWithoutRemovingUserTUN(self):
        """Do not replace a requested native TUN with application tun2socks."""
        original = self.configuration(nativeTUN=True)
        runtime = original.deepcopy()

        with (
            mock.patch.object(
                Hysteria2PluginModule,
                'isHysteria2TUNEnabled',
                return_value=True,
            ),
            mock.patch.object(Hysteria2PluginModule, 'PLATFORM', 'Linux'),
            mock.patch.object(
                Hysteria2PluginModule.SystemRuntime,
                'isAdmin',
                return_value=False,
            ),
        ):
            with self.assertRaisesRegex(TUNPreparationError, 'superuser privileges'):
                self.factory.prepareTUN(runtime)

        self.assertEqual(runtime, original)

    def testDownloadTestExplicitlyStripsNativeTUN(self):
        """Keep normal custom TUN while deriving a TUN-free speed-test copy."""
        original = self.configuration(nativeTUN=True)
        snapshot = copy.deepcopy(original)

        runtime, handled = self.prepare(original, False)
        speedTest = self.factory.prepareDownloadTest(original, 18080)

        self.assertTrue(handled)
        self.assertEqual(runtime, original)
        self.assertEqual(original, snapshot)
        self.assertNotIn('tun', speedTest)

    def testConnectionManagerDoesNotPairCustomTUNWithTun2socks(self):
        """Stop host tun2socks selection once Hysteria 2 owns native TUN."""
        original = self.configuration(nativeTUN=True)
        registry = mock.Mock()
        registry.prepareTUN.side_effect = self.factory.prepareTUN
        registry.usesApplicationTun2socks.side_effect = (
            self.factory.usesApplicationTun2socks
        )
        manager = _RecordingConnectionManager()

        with (
            mock.patch.object(
                Hysteria2PluginModule,
                'isHysteria2TUNEnabled',
                return_value=False,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.SystemRuntime.isTUNMode',
                return_value=True,
            ),
            mock.patch(
                'Furious.Service.ConnectionManager.getPluginRegistry',
                return_value=registry,
            ),
            mock.patch('Furious.Service.ConnectionManager.Tun2socks') as tun2socks,
        ):
            self.assertTrue(manager.start(original, 'Global'))

        registry.usesApplicationTun2socks.assert_not_called()
        tun2socks.assert_not_called()

        self.assertEqual(manager.runtimeConfiguration, original)

        manager.cleanup()


if __name__ == '__main__':
    unittest.main()
