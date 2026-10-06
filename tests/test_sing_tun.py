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

"""Isolated sing-tun policy, UI, native-child and host ownership contracts."""

from __future__ import annotations

from Furious.Core.SingTUN import SingTUN, _runEngine
from Furious.Core.MultiprocessingRuntime import (
    ProcessLaunchSpec,
    MultiprocessingRuntime,
)
from Furious.Interface import CoreRuntime, RuntimeState, RuntimeExitReason
from Furious.Frozenlib import AppSettings
from Furious.Models.SingTUN import prepareSingTUNSettings, addSingTUNExclusions
from Furious.Frozenlib.SocksProxy import socksURL
from Furious.Repository import Storage
from Furious.Repository.SingTUNSettings import UserSingTUNSettings
from Furious.Repository.TunSettings import UserTUNSettings
from Furious.Service.ConnectionManager import (
    ConnectionManager,
    ConnectionStartStage,
    _ConnectionStartAttempt,
)
from Furious.Service.SingTUNHost import (
    SingTUNHostPlan,
    _routeRanges,
    _linuxRuleDelete,
    _darwinRoutes,
)
from Furious.Plugins import PreparedRuntime, CoreRuntimeStartup, TUNPreparationError
from Furious.Window.SingTUNSettingsDialog import SingTUNSettingsDialog
from Furious.Window.TunSettingsDialog import TunSettingsDialog
from Furious.Backends.Configuration import ConfigXray, ConfigHysteria1, ConfigHysteria2
from Furious.Controllers.SettingsController import SettingsController
from Furious.Controllers.ConnectionController import (
    ConnectionController,
    ConnectionState,
)
from Furious.Qt import gettext as _
from Furious.Service.RuntimeLease import RuntimeEventRouter, RuntimeLeaseState
from Furious.Service.LogManager import LogManager, TUN_LOG_CATEGORY

from PySide6 import QtCore
from PySide6.QtWidgets import QLabel, QWidget
from shiboken6 import isValid

from tests.support import application, isolatedSettings, processQtEvents, waitFor
from tests.test_connection_startup_async import _Configuration, _Registry, _Runtime

from unittest import mock

import copy
import importlib
import json
import multiprocessing
import subprocess
import sys
import threading
import tempfile
import unittest
import ipaddress
import weakref


class _Engine:
    """Harmless native stand-in, never acquires an interface or route."""

    def __init__(self, configuration):
        if configuration.get('missing', False):
            raise ImportError('unavailable native library with sensitive loader data')
        if configuration.get('invalid', False):
            raise ValueError('binding configuration validation failed')

        self.ready = False
        self.status = {'error': ''}
        self.device_name = 'utun101'
        self.stopped = threading.Event()
        self.block = configuration.get('block', False)
        self.fail = configuration.get('fail', False)
        self.failWithoutStatus = configuration.get('fail_without_status', False)
        self.runtimeFail = configuration.get('runtime_fail', False)

    def start(self):
        if self.block:
            self.stopped.wait(2)
            raise RuntimeError('cancelled')
        if self.fail:
            self.status['error'] = 'new binding startup failure wording'
            raise RuntimeError('do not expose socks5://secret:password@127.0.0.1:1080')
        if self.failWithoutStatus:
            raise RuntimeError('binding initialization exception without status')

        self.ready = True

    def stop(self):
        self.stopped.set()

    def wait(self, timeout):
        if self.runtimeFail:
            self.status['error'] = 'new binding runtime failure wording'
            raise RuntimeError('do not expose runtime secrets')
        return self.stopped.wait(timeout)

    def close(self, _timeout):
        self.stop()


def _fakeChild(_output, configuration, control):
    _runEngine(configuration, control, _Engine)


class _ChildRuntime(SingTUN):
    """Use the actual spawn/IPC owner with a harmless child entry point."""

    def start(self):
        self._started = True
        self._launch = ProcessLaunchSpec(
            target=_fakeChild,
            args=(self._output, self._configuration, self._childControl),
        )
        try:
            MultiprocessingRuntime.start(self)
            self._monitor.setInterval(10)
        finally:
            self._childControl.close()


class _PreparedSing(SingTUN):
    """Drive service readiness without multiprocessing or host commands."""

    def __init__(self, configuration, *, hostPlan, exitCallback=None, **_kwargs):
        CoreRuntime.__init__(self, exitCallback)
        self._hostPlan = hostPlan
        self._configuration = copy.deepcopy(configuration)
        self.alive = False
        self.nativeReady = False
        self.released = False

    @property
    def startupError(self):
        return ''

    @property
    def deviceName(self):
        return 'utun101'

    @property
    def ready(self):
        return self.nativeReady and self.alive

    def start(self):
        self.alive = True
        self.setState(RuntimeState.Alive)

    def stop(self):
        self.alive = False
        self.released = True

    def dispose(self):
        self.stop()

    def isRunning(self):
        return self.alive


class _Plan:
    def __init__(self, configuration):
        self.configuration = copy.deepcopy(configuration)
        self.hostSettings = self.configuration.pop('host_options')
        self.error = ''
        self.deviceName = 'utun101'
        self.addresses = []
        self.applied = []

    def begin(self, method, *args):
        if method == 'prepare':
            self.addresses = args[0]
        elif method == 'applyDNS':
            self.applied.append(args[0])

    def workCompleted(self):
        return True

    def prepare(self, addresses):
        self.addresses = addresses

    def applyDNS(self, device):
        self.applied.append(device)


class SingTUNConfigurationTest(unittest.TestCase):
    def testHostOptionsHaveIndependentDefaultsAndNeverEnterNativeConfig(self):
        stored = {'host_options': {'tunAdapterInterfaceDNS': '9.9.9.9'}}
        prepared = prepareSingTUNSettings(stored)
        plan = SingTUNHostPlan(prepared)

        self.assertEqual(plan.hostSettings['tunAdapterInterfaceDNS'], '9.9.9.9')
        self.assertTrue(plan.hostSettings['disablePrimaryAdapterInterfaceDNS'])
        self.assertNotIn('host_options', plan.configuration)

        plan.hostSettings['tunAdapterInterfaceDNS'] = '1.0.0.1'

        self.assertEqual(
            stored, {'host_options': {'tunAdapterInterfaceDNS': '9.9.9.9'}}
        )
        self.assertEqual(
            prepareSingTUNSettings({})['host_options']['tunAdapterInterfaceDNS'], ''
        )

    def testMalformedHostOptionsAreRejectedBeforeActivation(self):
        for host in (
            None,
            [],
            {'tunAdapterInterfaceDNS': 'invalid'},
            {'disablePrimaryAdapterInterfaceDNS': 'False'},
            {'tcpSendBufferSize': 4},
            {'bypassTUNAdapterInterfaceIP': '192.0.2.1,invalid'},
        ):
            with self.subTest(host=host), self.assertRaises(ValueError):
                prepareSingTUNSettings({'host_options': host})

    def testDefaultsCopyAndOwnedFields(self):
        original = {'tun_options': {'MTU': 1400}}
        prepared = prepareSingTUNSettings(original)

        self.assertEqual(original, {'tun_options': {'MTU': 1400}})
        self.assertEqual(prepared['stack'], 'go')
        self.assertEqual(prepared['tun_options']['Inet4Address'], ['198.18.0.1/15'])

        for field, value in [
            ('AutoRoute', False),
            ('DNSMode', 'native'),
            ('EXP_ExternalConfiguration', True),
            ('EXP_DisableDNSHijack', False),
            ('FileDescriptor', 3),
            ('IPRoute2TableIndex', 99),
        ]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepareSingTUNSettings({'tun_options': {field: value}})

    def testValidationRejectsUnsupportedAndMalformedValues(self):
        for value in [
            {'stack': 'unsupported'},
            {'unknown': True},
            {'max_sessions': True},
            {'udp_timeout': float('nan')},
            {'tun_options': {'MTU': 0}},
            {'tun_options': {'Inet4Address': ['::1/128']}},
            {'stack_options': {'UDPTimeout': '0s'}},
            {'stack': 'system', 'stack_options': {'IncludeAllNetworks': True}},
            {'stack': '', 'stack_options': {'IncludeAllNetworks': True}},
            {'stack': 'go', 'stack_options': {'IncludeAllNetworks': True}},
            {'stack_options': {'ForwarderBindInterface': True}},
            {'stack_options': {'TCPCongestionControl': 'invalid'}},
            {'stack_options': {'TCPCongestionControl': True}},
            {'stack': 'gvisor', 'stack_options': {'TCPCongestionControl': 'bbr'}},
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepareSingTUNSettings(value)

    def testGoAndPreviousStacksPreserveExplicitChoicesAndCongestionControl(self):
        for stack in ('', 'go', 'gvisor', 'system', 'mixed'):
            original = {'stack': stack}
            self.assertEqual(prepareSingTUNSettings(original)['stack'], stack)
            self.assertEqual(original, {'stack': stack})

        for stack in ('', 'go'):
            for congestion in ('', 'cubic', 'reno', 'bbr'):
                original = {
                    'stack': stack,
                    'stack_options': {'TCPCongestionControl': congestion},
                }
                self.assertEqual(
                    prepareSingTUNSettings(original)['stack_options'][
                        'TCPCongestionControl'
                    ],
                    congestion,
                )

        self.assertTrue(
            prepareSingTUNSettings(
                {'stack': 'gvisor', 'stack_options': {'IncludeAllNetworks': True}}
            )['stack_options']['IncludeAllNetworks']
        )

    def testEndpointsIncludingAuthentication(self):
        expected = {
            '0.0.0.0:1080': 'socks5://127.0.0.1:1080',
            'localhost:1080': 'socks5://127.0.0.1:1080',
            ':::1080': 'socks5://[::1]:1080',
            '[::1]:1080': 'socks5://[::1]:1080',
            'socks5://u:p%40ss@[::1]:1080': 'socks5://u:p%40ss@[::1]:1080',
        }
        for value, normalized in expected.items():
            self.assertEqual(socksURL(value), normalized)

        for value in (
            '',
            'http://127.0.0.1:1080',
            'example.com:1080',
            '127.0.0.1:0',
            '127.0.0.1:65536',
            'socks5://u:@127.0.0.1:1080',
        ):
            with self.assertRaises(ValueError):
                socksURL(value)

    def testDualStackBypassesPreserveStoredExclusions(self):
        original = prepareSingTUNSettings(
            {'tun_options': {'Inet4RouteExcludeAddress': ['192.0.2.0/24']}}
        )
        prepared = addSingTUNExclusions(
            original, ['192.0.2.1', '2001:db8::1', '192.0.2.1']
        )

        self.assertEqual(
            original['tun_options']['Inet4RouteExcludeAddress'], ['192.0.2.0/24']
        )
        self.assertEqual(
            prepared['tun_options']['Inet6RouteExcludeAddress'], ['2001:db8::1/128']
        )
        self.assertEqual(len(prepared['tun_options']['Inet4RouteExcludeAddress']), 2)

    def testBackendAuthenticationAndUDPPolicy(self):
        xray = ConfigXray(
            {
                'inbounds': [
                    {
                        'listen': '::',
                        'port': 1080,
                        'protocol': 'socks',
                        'settings': {
                            'udp': True,
                            'auth': 'password',
                            'accounts': [{'user': 'u', 'pass': 'p@ss'}],
                        },
                    }
                ]
            }
        )
        self.assertEqual(xray.applicationTUNProxy(), 'socks5://u:p%40ss@[::1]:1080')

        xray['inbounds'][0]['settings']['accounts'][0]['pass'] = 'p/@ss'
        self.assertEqual(xray.applicationTUNProxy(), 'socks5://u:p%2F%40ss@[::1]:1080')

        xray['inbounds'][0]['settings']['udp'] = False
        with self.assertRaises(ValueError):
            xray.applicationTUNProxy()

        for cls, user, disable in (
            (ConfigHysteria1, 'user', 'disable_udp'),
            (ConfigHysteria2, 'username', 'disableUDP'),
        ):
            configuration = cls(
                {'socks5': {'listen': '127.0.0.1:1080', user: 'u', 'password': 'p'}}
            )
            self.assertEqual(
                configuration.applicationTUNProxy(), 'socks5://u:p@127.0.0.1:1080'
            )
            configuration['socks5'][disable] = True
            with self.assertRaises(ValueError):
                configuration.applicationTUNProxy()

    def testPublishedNativeAPIWithoutTUNAcquisition(self):
        for settings in (
            {},
            {'stack': 'gvisor'},
            {'stack': 'system'},
            {'stack': 'mixed'},
            {'stack': ''},
            {'stack_options': {'TCPCongestionControl': 'bbr'}},
            {
                'max_sessions': 512,
                'tun_options': {'MTU': 1450},
                'stack_options': {
                    'UDPTimeout': '15s',
                    'ICMPTimeout': 0,
                    'UDPNATMax': 64,
                },
            },
        ):
            configuration = prepareSingTUNSettings(settings)
            configuration['proxy'] = 'socks5://127.0.0.1:1080'
            configuration = SingTUNHostPlan(configuration).configuration

            with tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(
                    [
                        sys.executable,
                        '-c',
                        'import json,sys,importlib.metadata; '
                        'from sing_tun import Config, Engine, capabilities; '
                        'assert importlib.metadata.version("sing-tun") == "0.9.7.dev0"; '
                        'assert Config(proxy="socks5://127.0.0.1:1080").stack == "go"; '
                        'assert "go" in capabilities()["stacks"]; '
                        'e=Engine(Config(**json.load(sys.stdin))); assert not e.ready; e.close(5); '
                        'assert capabilities(); print("Installed API OK")',
                    ],
                    input=json.dumps(configuration).encode(),
                    capture_output=True,
                    cwd=directory,
                    timeout=20,
                )

            self.assertEqual(
                result.returncode, 0, result.stderr.decode(errors='replace')
            )


class SingTUNUIAndStorageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = application()

    def testSelectorDestructionDisconnectsTheIndependentController(self):
        """Repeated cards release dispatchers while the controller remains alive."""
        module = importlib.import_module('Furious.Window.SettingsPage')

        with isolatedSettings():
            controller = SettingsController()
            signal = QtCore.SIGNAL('tunBackendChanged(QString)')
            baseline = controller.receivers(signal)

            with mock.patch.object(
                module, 'AppSettingsController', return_value=controller
            ):
                for _ in range(20):
                    card = module._TUNBackendSettingsCard()
                    reference = weakref.ref(card)

                    controller.tunBackendChanged.emit('tun2socks')

                    self.assertEqual(card.comboBox.currentData(), 'tun2socks')
                    self.assertEqual(controller.receivers(signal), baseline + 1)

                    card.deleteLater()
                    processQtEvents()

                    self.assertFalse(isValid(card))
                    del card

                    self.assertIsNone(reference())
                    self.assertEqual(controller.receivers(signal), baseline)

                    controller.tunBackendChanged.emit('sing-tun')

                card = module._TUNBackendSettingsCard()
                controller.deleteLater()
                processQtEvents()

                self.assertTrue(isValid(card))

                card.deleteLater()
                processQtEvents()

                self.assertFalse(isValid(card))

    def testTwoChoiceSelectorRetranslatesWithoutChangingStablePreference(self):
        module = importlib.import_module('Furious.Window.SettingsPage')

        with isolatedSettings(), mock.patch(
            'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
        ):
            controller = SettingsController()

            with mock.patch.object(
                module, 'AppSettingsController', return_value=controller
            ):
                card = module._TUNBackendSettingsCard()

                self.assertEqual(
                    [
                        card.comboBox.itemData(index)
                        for index in range(card.comboBox.count())
                    ],
                    ['tun2socks', 'sing-tun'],
                )
                self.assertEqual(card.comboBox.currentData(), 'tun2socks')

                for backend in ('tun2socks', 'sing-tun', 'tun2socks'):
                    card.comboBox.setCurrentIndex(card.comboBox.findData(backend))
                    self.assertEqual(AppSettings.get('ApplicationTUNBackend'), backend)

                for language in ('ZH', 'RU', 'EN'):
                    AppSettings.set('Language', language)
                    card.titleLabel.retranslate()
                    card.descriptionLabel.retranslate()
                    card.comboBox.retranslate()

                    self.assertEqual(
                        card.titleLabel.text(), _('Application TUN Engine', language)
                    )
                    self.assertEqual(card.comboBox.currentData(), 'tun2socks')

                self.assertFalse(AppSettings.isStateON_('VPNMode'))

                card.deleteLater()
                processQtEvents()

    def testIndependentRoundTripAndMalformedPreservation(self):
        with isolatedSettings():
            AppSettings.set('CustomSingTUNSettings', 'malformed')

            with self.assertLogs('Furious.Repository.SingTUNSettings', level='ERROR'):
                repository = UserSingTUNSettings()

            repository.cleanup()

            self.assertEqual(AppSettings.get('CustomSingTUNSettings'), 'malformed')

            repository.data()['unknown'] = {'future': 1}
            repository.sync()
            self.assertEqual(UserSingTUNSettings().data(), {'unknown': {'future': 1}})

    def _dialog(self, sing):
        patches = (
            mock.patch.object(Storage, 'UserSingTUNSettings', return_value=sing),
            mock.patch.object(
                Storage,
                'UserTUNSettings',
                side_effect=AssertionError('tun2socks settings must not be read'),
            ),
        )
        with patches[0], patches[1]:
            return SingTUNSettingsDialog()

    def testGoDefaultAndCongestionControlRoundTripPreservePreviousStackChoices(self):
        for stack in (None, '', 'go', 'gvisor', 'system', 'mixed'):
            saved = {} if stack is None else {'stack': stack}
            baseline = copy.deepcopy(saved)
            dialog = self._dialog(saved)
            expected = 'go' if stack is None else stack

            self.assertEqual(dialog.fields['stack'].currentData(), expected)
            self.assertEqual(dialog.document()['stack'], expected)
            self.assertEqual(saved, baseline)

            dialog.reject()
            processQtEvents()

        saved = {'stack_options': {'TCPCongestionControl': 'bbr'}}
        dialog = self._dialog(saved)

        self.assertEqual(dialog.fields['TCPCongestionControl'].currentData(), 'bbr')
        self.assertEqual(
            dialog.document()['stack_options']['TCPCongestionControl'], 'bbr'
        )
        self.assertNotIn('TCPCongestionControl', dialog.advanced.toPlainText())

        for language in ('ZH', 'RU'):
            self.assertNotEqual(
                _('TCP Congestion Control (Go stack)', language),
                'TCP Congestion Control (Go stack)',
            )

        dialog.reject()
        processQtEvents()

    def testCancelAndInvalidAreObservational(self):
        sing = {'tun_options': {'MTU': 1450}}
        baseline = copy.deepcopy(sing)
        dialog = self._dialog(sing)
        dialog.open()

        dialog.fields['udp_timeout'].setText('invalid')
        with mock.patch.object(Storage, 'replaceSingTUNSettings') as commit:
            dialog.accept()
            commit.assert_not_called()

        self.assertEqual(sing, baseline)
        self.assertTrue(dialog.errorLabel.text())

        dialog.reject()
        processQtEvents()
        self.assertFalse(isValid(dialog))

    def testDialogPreparesNativeAndHostOptionsInOneIndependentDocument(self):
        sing = {'host_options': {'tunAdapterInterfaceDNS': '9.9.9.9'}}
        dialog = self._dialog(sing)
        dialog.fields['MTU'].setValue(1400)
        dialog.fields['bypassTUNAdapterInterfaceIP'].setText('192.0.2.4,2001:db8::4')

        document = dialog.document()

        self.assertEqual(document['tun_options']['MTU'], 1400)
        self.assertEqual(document['host_options']['tunAdapterInterfaceDNS'], '9.9.9.9')
        self.assertEqual(
            document['host_options']['bypassTUNAdapterInterfaceIP'],
            '192.0.2.4,2001:db8::4',
        )
        self.assertNotIn('defaultPrimaryGatewayIP', dialog.fields)

        dialog.fields['tunAdapterInterfaceDNS'].setText('invalid')
        with self.assertRaises(ValueError):
            dialog.document()
        self.assertEqual(sing, {'host_options': {'tunAdapterInterfaceDNS': '9.9.9.9'}})

        dialog.reject()
        processQtEvents()

    def testCommitStagesAliasedLiveViewAndRejectsInvalidSingFields(self):
        sing = {'max_sessions': 512}
        singRepository = mock.Mock()
        singRepository.data.return_value = sing

        with isolatedSettings(), mock.patch.object(
            Storage, '_UserSingTUNSettingsStorage', return_value=singRepository
        ), mock.patch.object(
            Storage,
            '_UserTUNSettingsStorage',
            side_effect=AssertionError('tun2socks storage must not be acquired'),
        ):
            Storage.replaceSingTUNSettings(sing)
            self.assertEqual(sing, {'max_sessions': 512})

            with self.assertRaises(ValueError):
                Storage.replaceSingTUNSettings(
                    {
                        'max_sessions': 256,
                        'host_options': {'tunAdapterInterfaceDNS': object()},
                    }
                )

            self.assertEqual(sing, {'max_sessions': 512})

    def testSingFlushFailureReportsItsCompletedCommitWithoutAcquiringTun2socks(self):
        sing = {'max_sessions': 512}
        repository = mock.Mock()
        repository.data.return_value = sing
        settings = mock.Mock()
        status = QtCore.QSettings.Status
        settings.status.return_value = status.AccessError

        with mock.patch.object(
            Storage, '_UserSingTUNSettingsStorage', return_value=repository
        ), mock.patch.object(
            Storage,
            '_UserTUNSettingsStorage',
            side_effect=AssertionError('inactive backend'),
        ), mock.patch.object(
            QtCore, 'QSettings', return_value=settings
        ) as factory:
            factory.Status = status

            with self.assertRaisesRegex(OSError, 'committed in memory'):
                Storage.replaceSingTUNSettings({'max_sessions': 256})

        self.assertEqual(sing, {'max_sessions': 256})
        repository.sync.assert_called_once_with()
        settings.sync.assert_called_once_with()

    def testOwnHostSettingsLabelsAreTranslatedInBothSupportedLocales(self):
        for language, title in (
            ('EN', 'Host Settings'),
            ('ZH', '主机设置'),
            ('RU', 'Настройки хоста'),
        ):
            with self.subTest(language=language), isolatedSettings():
                AppSettings.set('Language', language)

                dialog = self._dialog({})

                with mock.patch.object(Storage, 'UserTUNSettings', return_value={}):
                    legacy = TunSettingsDialog()

                self.assertEqual(_('Host Settings'), title)
                self.assertIn(
                    title,
                    [
                        dialog.tabs.tabText(index)
                        for index in range(dialog.tabs.count())
                    ],
                )

                form = dialog.disableDNS.parentWidget().layout()
                legacyLabels = {label.text() for label in legacy.findChildren(QLabel)}

                for key, source in (
                    ('primaryAdapterInterfaceName', 'Primary Adapter Interface Name'),
                    ('primaryAdapterInterfaceIP', 'Primary Adapter Interface IP'),
                    ('tunAdapterInterfaceDNS', 'TUN Adapter Interface DNS'),
                    (
                        'bypassTUNAdapterInterfaceIP',
                        'Bypass TUN Adapter Interface IP (separated by commas)',
                    ),
                ):
                    expected = _(source)
                    self.assertEqual(
                        form.labelForField(dialog.fields[key]).text(), expected
                    )
                    self.assertIn(expected, legacyLabels)
                    if language != 'EN':
                        self.assertNotEqual(expected, source)

                dnsLabel = _(
                    'Disable Primary Adapter Interface DNS (Mitigating DNS leaks on Windows)'
                )
                self.assertIn(
                    dnsLabel,
                    {
                        label.text()
                        for label in dialog.disableDNS.parentWidget().findChildren(
                            QLabel
                        )
                    },
                )
                self.assertIn(dnsLabel, legacyLabels)
                self.assertEqual(form.rowCount(), 5)

                legacy.reject()
                legacy.deleteLater()
                dialog.reject()
                processQtEvents()

    def testSavingEitherBackendPreservesTheOthersLiveAndPersistedSettings(self):
        with isolatedSettings():
            tun2socks = UserTUNSettings()
            tun2socks.data().update(
                {
                    'tunAdapterInterfaceDNS': '8.8.8.8',
                    'defaultPrimaryGatewayIP': '192.0.2.254',
                    'tcpSendBufferSize': 4,
                }
            )
            tun2socks.sync()
            legacyBefore = copy.deepcopy(tun2socks.data())
            legacyRaw = AppSettings.get('CustomTUNSettings')
            sing = UserSingTUNSettings()

            with mock.patch.object(
                Storage, '_UserSingTUNSettingsStorage', return_value=sing
            ), mock.patch.object(
                Storage,
                '_UserTUNSettingsStorage',
                side_effect=AssertionError('sing-tun must not touch tun2socks storage'),
            ):
                dialog = SingTUNSettingsDialog()
                dialog.open()

                self.assertEqual(dialog.fields['tunAdapterInterfaceDNS'].text(), '')

                dialog.fields['tunAdapterInterfaceDNS'].setText('9.9.9.9')
                dialog.fields['bypassTUNAdapterInterfaceIP'].setText('2001:db8::1')

                dialog.accept()
                processQtEvents()

                self.assertFalse(isValid(dialog))

            self.assertEqual(tun2socks.data(), legacyBefore)
            self.assertEqual(AppSettings.get('CustomTUNSettings'), legacyRaw)
            self.assertEqual(
                UserSingTUNSettings().data()['host_options']['tunAdapterInterfaceDNS'],
                '9.9.9.9',
            )

            singBefore = copy.deepcopy(sing.data())
            singRaw = AppSettings.get('CustomSingTUNSettings')

            tun2socks.data()['tunAdapterInterfaceDNS'] = '1.0.0.1'
            tun2socks.sync()

            self.assertEqual(sing.data(), singBefore)
            self.assertEqual(AppSettings.get('CustomSingTUNSettings'), singRaw)
            self.assertNotIsInstance(sing, UserTUNSettings)

    def testRepeatedOpenAndOwnerFirstDestruction(self):
        for _ in range(5):
            owner = QWidget()

            with mock.patch.object(
                Storage, 'UserSingTUNSettings', return_value={}
            ), mock.patch.object(
                Storage,
                'UserTUNSettings',
                side_effect=AssertionError('inactive backend'),
            ):
                dialog = SingTUNSettingsDialog(owner)

            dialog.open()
            owner.deleteLater()
            processQtEvents()

            self.assertFalse(isValid(dialog))

    def testNativeTUNBackendSelectionPersistsWithoutReconnectNotice(self):
        """Application-engine preferences do not affect an active native TUN."""
        module = importlib.import_module('Furious.Window.SettingsPage')
        configurations = (
            ConfigXray({'inbounds': []}),
            ConfigXray({'inbounds': [{'protocol': 'tun'}]}),
            ConfigHysteria2({}),
            ConfigHysteria2({'tun': {}}),
        )

        for configuration in configurations:
            with (
                self.subTest(configuration=dict(configuration)),
                isolatedSettings(),
                mock.patch(
                    'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
                ) as notice,
                mock.patch('sys.excepthook') as callbackExceptionHook,
            ):
                AppSettings.turnON_('VPNMode')
                AppSettings.set('ApplicationTUNBackend', 'tun2socks')

                manager = ConnectionManager()
                connection = ConnectionController(
                    coreManager=manager, updatesManager=mock.Mock()
                )
                settings = SettingsController()

                previousConnection = self.app.connectionController
                self.app.connectionController = connection
                card = None

                try:
                    primary = _Runtime()
                    primary.start()

                    attempt = _ConnectionStartAttempt(
                        manager, configuration, nativeTUNHandled=True
                    )
                    attempt.ownRuntime(primary)

                    attempt.commit()

                    connection._activeProfile = configuration
                    connection._state = ConnectionState.Connected

                    changes = []
                    settings.tunBackendChanged.connect(changes.append)

                    with mock.patch.object(
                        module, 'AppSettingsController', return_value=settings
                    ):
                        card = module._TUNBackendSettingsCard()

                        for backend in ('sing-tun', 'tun2socks'):
                            card.comboBox.setCurrentIndex(
                                card.comboBox.findData(backend)
                            )

                            self.assertEqual(
                                AppSettings.get('ApplicationTUNBackend'), backend
                            )
                            self.assertEqual(card.comboBox.currentData(), backend)
                            self.assertTrue(connection.isConnected())
                            self.assertTrue(primary.isRunning())
                            self.assertEqual(manager.runtimes, [primary])
                            notice.assert_not_called()

                    self.assertEqual(changes, ['sing-tun', 'tun2socks'])
                finally:
                    self.app.connectionController = previousConnection

                    if card is not None:
                        card.deleteLater()

                    manager.cleanup()

                    connection.deleteLater()
                    settings.deleteLater()

                    processQtEvents()

                callbackExceptionHook.assert_not_called()

    def testApplicationTUNBackendSelectionStillOffersReconnect(self):
        """Use committed engine ownership even if the profile is edited later."""
        for backend in ('tun2socks', 'sing-tun'):
            with (
                self.subTest(backend=backend),
                isolatedSettings(),
                mock.patch(
                    'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
                ) as notice,
            ):
                AppSettings.set('ApplicationTUNBackend', backend)

                manager = ConnectionManager()
                connection = ConnectionController(
                    coreManager=manager, updatesManager=mock.Mock()
                )
                settings = SettingsController()

                previousConnection = self.app.connectionController
                self.app.connectionController = connection

                configuration = ConfigXray({'inbounds': []})
                attempt = _ConnectionStartAttempt(
                    manager, configuration, applicationTun2socks=True
                )

                try:
                    primary, engine = _Runtime(), _Runtime()
                    primary.start()
                    engine.start()

                    attempt.ownRuntime(primary)
                    attempt.ownRuntime(engine, applicationTUN=True)

                    self.assertFalse(manager.usesApplicationTUN())

                    attempt.commit()

                    connection._activeProfile = configuration
                    connection._state = ConnectionState.Connected

                    configuration['inbounds'].append({'protocol': 'tun'})

                    self.assertTrue(connection.usesApplicationTUN())

                    other = 'sing-tun' if backend == 'tun2socks' else 'tun2socks'

                    settings.setTUNBackend(other)
                    settings.setTUNBackend(other)

                    notice.assert_called_once_with()
                    self.assertEqual(AppSettings.get('ApplicationTUNBackend'), other)
                    self.assertEqual(manager.runtimes, [primary, engine])
                    self.assertTrue(primary.isRunning())
                    self.assertTrue(engine.isRunning())

                    notice.reset_mock()
                    connection._state = ConnectionState.Disconnected

                    settings.setTUNBackend(backend)

                    notice.assert_not_called()
                finally:
                    self.app.connectionController = previousConnection

                    attempt.rollback()
                    manager.cleanup()

                    connection.deleteLater()
                    settings.deleteLater()

                    processQtEvents()

                self.assertFalse(manager.usesApplicationTUN())

    def testPreferenceDefaultInvalidAndSignal(self):
        with isolatedSettings(), mock.patch(
            'Furious.Controllers.SettingsController.showMBoxNewChangesNextTime'
        ):
            self.assertEqual(AppSettings.get('ApplicationTUNBackend'), 'tun2socks')
            QtCore.QSettings().setValue('ApplicationTUNBackend', 'invalid')
            self.assertEqual(AppSettings.get('ApplicationTUNBackend'), 'tun2socks')

            controller = SettingsController()
            changes = []
            controller.tunBackendChanged.connect(changes.append)

            controller.setTUNBackend('sing-tun')
            controller.setTUNBackend('sing-tun')

            with self.assertRaises(ValueError):
                controller.setTUNBackend('invalid')

            self.assertEqual(changes, ['sing-tun'])
            self.assertEqual(AppSettings.get('ApplicationTUNBackend'), 'sing-tun')
            self.assertFalse(AppSettings.isStateON_('VPNMode'))


class SingTUNChildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        application()

    def testSpawnReadyCooperativeStopAndFinalHandleDisposal(self):
        runtime = _ChildRuntime({})

        try:
            self.assertEqual(runtime._processContext.get_start_method(), 'spawn')

            runtime.start()

            self.assertTrue(waitFor(lambda: runtime.ready, timeout=10))
            self.assertEqual(runtime.deviceName, 'utun101')

            child = runtime.process
            runtime.stop()

            self.assertEqual(runtime._status['state'], 'stopped')
            self.assertIsNone(runtime.process)
            self.assertTrue(child._closed)

            runtime.dispose()

            self.assertTrue(runtime._control.closed)
        finally:
            runtime.dispose()

    def testInvalidAndOversizeStatusCannotSupplyReadiness(self):
        for payload in (
            b'{"state":"ready","device_name":false}',
            b'{"state":"failed"}',
            b'{"state":"failed","error":""}',
            b'{"state":"failed","error":null}',
            b'{"state":"failed","error":false}',
            b'{"state":"failed","error":["failure"]}',
            b'{"state":"failed","error":{"reason":"failure"}}',
            b'x' * 4097,
        ):
            with self.subTest(payloadSize=len(payload)):
                runtime = SingTUN({})
                try:
                    runtime._childControl.send_bytes(payload)
                    self.assertEqual(
                        runtime.startupError, 'Invalid sing-tun status message'
                    )
                    self.assertFalse(runtime.ready)
                    self.assertEqual(runtime.deviceName, '')
                finally:
                    runtime.dispose()

    def testStopDuringBlockedInitialization(self):
        runtime = _ChildRuntime({'block': True})
        try:
            runtime.start()
            runtime.stop()
            self.assertFalse(runtime.isRunning())
        finally:
            runtime.dispose()

    def testBindingStatusReasonIsForwardedWithoutLiteralMatching(self):
        runtime = _ChildRuntime({'fail': True})
        try:
            runtime.start()
            self.assertTrue(waitFor(lambda: bool(runtime.startupError), timeout=10))
            self.assertFalse(runtime.ready)
            self.assertEqual(
                runtime.startupError, 'sing-tun: new binding startup failure wording'
            )
            event = runtime.interpretExit(1)
            self.assertEqual(event.reason, RuntimeExitReason.StartFailure)
            self.assertEqual(event.message, runtime.startupError)
        finally:
            runtime.dispose()

    def testBindingExceptionsAreForwardedWhenStatusHasNoReason(self):
        for configuration, reason in (
            ({'invalid': True}, 'binding configuration validation failed'),
            (
                {'fail_without_status': True},
                'binding initialization exception without status',
            ),
        ):
            with self.subTest(configuration=configuration):
                runtime = _ChildRuntime(configuration)
                try:
                    runtime.start()
                    self.assertTrue(
                        waitFor(lambda: bool(runtime.startupError), timeout=10)
                    )
                    self.assertEqual(runtime.startupError, reason)
                    self.assertFalse(runtime.ready)
                finally:
                    runtime.dispose()

    def testUnavailableBindingFailsVisiblyWithoutFallback(self):
        runtime = _ChildRuntime({'missing': True})
        try:
            runtime.start()
            self.assertTrue(waitFor(lambda: bool(runtime.startupError), timeout=10))
            self.assertEqual(
                runtime.startupError, 'sing-tun package is unavailable or incompatible'
            )
            self.assertFalse(runtime.ready)
        finally:
            runtime.dispose()

    def testFailureAfterNativeReadinessKeepsRuntimeExitMeaning(self):
        runtime = _ChildRuntime({'runtime_fail': True})
        try:
            runtime.start()
            self.assertTrue(waitFor(lambda: bool(runtime.startupError), timeout=10))
            event = runtime.interpretExit(1)
            self.assertEqual(event.reason, RuntimeExitReason.Unexpected)
            self.assertEqual(
                event.message, 'sing-tun: new binding runtime failure wording'
            )
        finally:
            runtime.dispose()

    def testHostCleanupRefusalKeepsRuntimeRetryable(self):
        plan = mock.Mock()
        plan.finishCleanup.side_effect = [RuntimeError('retained'), None, None]
        runtime = SingTUN({}, hostPlan=plan)
        try:
            with self.assertRaisesRegex(RuntimeError, 'retained'):
                runtime.stop()

            self.assertFalse(runtime._control.closed)

            runtime.stop()
        finally:
            runtime.dispose()

    def testFailedHandleCloseStillRestoresHostAndRetainsRetryOwnership(self):
        runtime = _ChildRuntime({})
        plan = mock.Mock()
        runtime._hostPlan = plan

        try:
            runtime.start()
            self.assertTrue(waitFor(lambda: runtime.ready, timeout=10))

            child = runtime.process

            with mock.patch.object(
                child, 'close', side_effect=OSError('retained handle')
            ):
                with self.assertRaisesRegex(RuntimeError, 'handle could not be closed'):
                    runtime.stop()

            plan.finishCleanup.assert_called_once()
            self.assertIs(runtime.process, child)
            self.assertFalse(child.is_alive())
            self.assertFalse(runtime._control.closed)

            runtime.stop()

            self.assertTrue(child._closed)
        finally:
            runtime.dispose()

    def testFailedReapRestoresDNSWithoutRecoveringLiveNativeResources(self):
        runtime = SingTUN({})
        plan, child = mock.Mock(), mock.Mock()
        runtime._hostPlan, runtime._process = plan, child
        child.is_alive.return_value = True

        try:
            with mock.patch.object(
                MultiprocessingRuntime,
                'stop',
                side_effect=RuntimeError('retained child'),
            ):
                with self.assertRaisesRegex(RuntimeError, 'retained child'):
                    runtime.stop()

            plan.finishDNSCleanup.assert_called_once()
            plan.finishCleanup.assert_not_called()
            self.assertIs(runtime.process, child)
            self.assertFalse(runtime._control.closed)
        finally:
            runtime._process = None
            runtime.dispose()


class SingTUNHostTest(unittest.TestCase):
    def testLinuxResolverPrerequisiteFailsBeforeNativeActivation(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Linux')

        with mock.patch.object(
            module.os, 'geteuid', return_value=0, create=True
        ), mock.patch.object(
            module.SystemRuntime, 'flatpakID', return_value=''
        ), mock.patch.object(
            module.shutil, 'which', return_value=None
        ), mock.patch.object(
            module, '_command'
        ) as command:
            with self.assertRaisesRegex(RuntimeError, 'systemd-resolved'):
                plan.prepare([])

            command.assert_not_called()

        self.assertFalse(plan._activated)

    def testUnsupportedOwnershipCombinationsFailBeforeHostCommands(self):
        with self.assertRaisesRegex(ValueError, 'both address families'):
            prepareSingTUNSettings({'tun_options': {'StrictRoute': True}})
        with self.assertRaisesRegex(ValueError, 'scoped route cleanup'):
            prepareSingTUNSettings(
                {'tun_options': {'InterfaceScope': True}}, platform='Darwin'
            )
        with self.assertRaisesRegex(ValueError, 'Unsupported sing-tun host'):
            SingTUNHostPlan(
                {'host_options': {'defaultPrimaryGatewayIP': '192.0.2.254'}}
            )

    def testLinuxRecoveryMatchesSelectorsRatherThanDeletingPriorityAlone(self):
        rule = {
            'priority': 2002,
            'src': 'all',
            'table': 'main',
            'not': True,
            'dport': '53-53',
            'suppress_prefixlength': 0,
        }
        command = _linuxRuleDelete('-4', rule, 123456, 2000, 'utun101')
        self.assertIn('not', command)
        self.assertIn('dport', command)
        self.assertIn('suppress_prefixlength', command)
        self.assertIn('main', command)
        with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
            _linuxRuleDelete('-4', {**rule, 'dport': 443}, 123456, 2000, 'utun101')

    def testDevelopmentIPv6RuleOrderingKeepsExactCleanupSelectors(self):
        # The snapshot moves the TUN goto before the loopback source rules.
        rule = {
            'priority': 2001,
            'src': 'all',
            'iif': 'utun101',
            'goto': 2010,
        }
        self.assertEqual(
            _linuxRuleDelete('-6', rule, 123456, 2000, 'utun101'),
            [
                'ip',
                '-6',
                'rule',
                'del',
                'priority',
                '2001',
                'from',
                'all',
                'iif',
                'utun101',
                'goto',
                '2010',
            ],
        )
        sourceRule = {
            'priority': 2002,
            'src': 'fd00::/64',
            'iif': 'lo',
            'table': 123456,
        }
        command = _linuxRuleDelete('-6', sourceRule, 123456, 2000, 'utun101')
        self.assertIn('fd00::/64', command)
        self.assertEqual(command[-2:], ['table', '123456'])

    def testWindowsRegistersStaticDNSRestorationBeforeFailedWrite(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Windows')
        plan.deviceName = 'utun101'
        plan.egressIP = '192.0.2.10'
        snapshot = [
            {
                'Name': 'Ethernet',
                'IP': ['192.0.2.10'],
                'Static': '8.8.8.8',
                'DNS': ['2606:4700:4700::1111', '8.8.8.8'],
            }
        ]

        with mock.patch.object(
            module, '_powershell', return_value=json.dumps(snapshot)
        ), mock.patch.object(
            plan, '_windowsDNS', side_effect=RuntimeError('write failed')
        ):
            with self.assertRaisesRegex(RuntimeError, 'write failed'):
                plan.applyDNS('utun101')

        self.assertEqual(plan._dnsRestore[0][1]['DNS'], ['8.8.8.8'])

        with mock.patch.object(plan, '_windowsDNS') as restore:
            plan.cleanup(True)
            restore.assert_called_once_with('Ethernet', ['8.8.8.8'])

    def testDarwinAbbreviatedRouteDestinationsAreNormalized(self):
        rows = _darwinRoutes(
            'Destination Gateway Flags Netif\n1 198.18.0.1 UGSc utun101\n192.0.2 192.0.2.254 UGSc en0',
            4,
        )

        self.assertEqual(
            rows[0], (ipaddress.ip_network('1.0.0.0/8'), '198.18.0.1', 'utun101')
        )
        self.assertEqual(rows[1][0], ipaddress.ip_network('192.0.2.0/24'))

    def testLinuxPrivilegesFailBeforeCommands(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Linux')
        with mock.patch.object(
            module.os, 'geteuid', return_value=1000, create=True
        ), mock.patch.object(
            module.SystemRuntime, 'flatpakID', return_value=''
        ), mock.patch.object(
            module, '_command'
        ) as commands:
            with self.assertRaisesRegex(RuntimeError, 'requires root'):
                plan.prepare(['192.0.2.1'])
            commands.assert_not_called()

    def testLinuxAssignedIdentifiersAndDualStackExclusions(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Linux')

        with mock.patch.object(
            module.os, 'geteuid', return_value=0, create=True
        ), mock.patch.object(
            module.SystemRuntime, 'flatpakID', return_value=''
        ), mock.patch.object(
            module.shutil, 'which', return_value='resolvectl'
        ), mock.patch.object(
            module.socket, 'if_nameindex', return_value=[]
        ), mock.patch.object(
            module, '_command', return_value='[]'
        ):
            plan.prepare(['192.0.2.1', '2001:db8::1'])

        tun = plan.configuration['tun_options']

        self.assertGreater(tun['IPRoute2TableIndex'], 100000)
        self.assertGreater(tun['IPRoute2RuleIndex'], 999)
        self.assertEqual(tun['Inet6RouteExcludeAddress'], ['2001:db8::1/128'])

    def testDNSRestorationIndependentOfNativeRecoveryFailure(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Windows')
        snapshot = {
            'Name': 'Ethernet',
            'Static': '8.8.8.8',
            'DNS': ['8.8.8.8', '8.8.4.4'],
        }
        plan._dnsRestore = [('Windows', snapshot)]
        plan._activated = True

        with mock.patch.object(plan, '_windowsDNS') as restore, mock.patch.object(
            plan, '_recoverNative', side_effect=RuntimeError('retained')
        ):
            with self.assertRaisesRegex(RuntimeError, 'retained'):
                plan.cleanup(False)

            restore.assert_called_once_with('Ethernet', ['8.8.8.8', '8.8.4.4'])
            self.assertEqual(plan._dnsRestore, [])
            self.assertTrue(plan._activated)

    def testRecoveryRefusesConflictingPolicyRules(self):
        module = importlib.import_module('Furious.Service.SingTUNHost')
        plan = SingTUNHostPlan(prepareSingTUNSettings({}), platform='Linux')
        plan._table, plan._ruleStart = 123456, 2000
        with mock.patch.object(
            module.socket, 'if_nameindex', return_value=[]
        ), mock.patch.object(
            module, '_command', return_value='[{"priority":2000,"table":987}]'
        ) as commands:
            with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
                plan._recoverNative()
            self.assertEqual(commands.call_count, 1)

    def testDarwinRangesMirrorSubRangesAndExclusions(self):
        tun = prepareSingTUNSettings({})['tun_options']
        ranges = _routeRanges(tun)
        self.assertEqual(len(ranges), 8)
        self.assertNotIn(ipaddress.ip_address('0.0.0.1'), ranges[0])

        tun['Inet4RouteExcludeAddress'] = ['192.0.2.1/32']
        self.assertFalse(
            any(
                ipaddress.ip_address('192.0.2.1') in network
                for network in _routeRanges(tun)
            )
        )


class SingTUNStartupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        application()

    def testBothStartupPathsKeepCapturedTUNLogSourceAfterPreferenceChanges(self):
        """Changing the next engine cannot relabel a previously captured attempt."""
        module = importlib.import_module('Furious.Service.ConnectionManager')

        for backend in ('sing-tun', 'tun2socks'):
            other = 'tun2socks' if backend == 'sing-tun' else 'sing-tun'

            for asynchronous in (True, False):
                with self.subTest(backend=backend, asynchronous=asynchronous):
                    with isolatedSettings():
                        AppSettings.set('ApplicationTUNBackend', backend)
                        manager = ConnectionManager()
                        logs = LogManager()
                        route = logs.callback(TUN_LOG_CATEGORY)

                        def switchPreference(*_args, **_kwargs):
                            AppSettings.set('ApplicationTUNBackend', other)
                            return True

                        def emitTUN(_attempt, _exitCallback, callback):
                            callback.appendMany(('first', 'second'))
                            return True

                        try:
                            if asynchronous:
                                operation = manager.startAsync(
                                    _Configuration(),
                                    'Global',
                                    msgCallbackTUN_=route,
                                    deepcopy=False,
                                )
                                switchPreference()
                                operation.msgCallbackTUN_.appendMany(
                                    ('first', 'second')
                                )
                            else:
                                starter = (
                                    '_startApplicationSingTUN'
                                    if backend == 'sing-tun'
                                    else '_startApplicationTun2socks'
                                )
                                with mock.patch.object(
                                    manager,
                                    '_prepareTUNPolicy',
                                    return_value=(False, True),
                                ), mock.patch.object(
                                    module.SystemRuntime, 'isTUNMode', return_value=True
                                ), mock.patch.object(
                                    Storage, 'UserSingTUNSettings', return_value={}
                                ), mock.patch.object(
                                    Storage, 'UserTUNSettings', return_value={}
                                ), mock.patch.object(
                                    manager,
                                    '_startPrimaryRuntime',
                                    side_effect=switchPreference,
                                ), mock.patch.object(
                                    manager, starter, side_effect=emitTUN
                                ):
                                    self.assertTrue(
                                        manager.start(
                                            _Configuration(),
                                            'Global',
                                            msgCallbackTUN_=route,
                                            deepcopy=False,
                                        )
                                    )

                            self.assertEqual(
                                AppSettings.get('ApplicationTUNBackend'), other
                            )
                            self.assertEqual(route.source, '')
                            self.assertEqual(
                                [
                                    entry.source
                                    for entry in logs.entries(TUN_LOG_CATEGORY)
                                ],
                                [backend, backend],
                            )
                        finally:
                            manager.cleanup()
                            logs.deleteLater()
                            processQtEvents()

    def testSnapshotReadsOnlyTheSelectedBackendAndKeepsItsOwnCopy(self):
        for backend, getter, field in (
            ('sing-tun', 'UserSingTUNSettings', 'singSettings'),
            ('tun2socks', 'UserTUNSettings', 'tun2socksSettings'),
        ):
            with self.subTest(backend=backend):
                stored = (
                    {'host_options': {'tunAdapterInterfaceDNS': '9.9.9.9'}}
                    if backend == 'sing-tun'
                    else {'tunAdapterInterfaceDNS': '8.8.8.8'}
                )
                inactive = (
                    'UserTUNSettings'
                    if backend == 'sing-tun'
                    else 'UserSingTUNSettings'
                )
                attempt = _ConnectionStartAttempt(
                    mock.Mock(),
                    _Configuration(),
                    applicationTun2socks=True,
                    tunBackend=backend,
                )

                with mock.patch.object(
                    Storage, getter, return_value=stored
                ) as selected, mock.patch.object(
                    Storage,
                    inactive,
                    side_effect=AssertionError('inactive backend read'),
                ) as other:
                    attempt.snapshotApplicationTUN()

                selected.assert_called_once_with()
                other.assert_not_called()

                expected = copy.deepcopy(stored)
                stored.clear()

                self.assertEqual(getattr(attempt, field), expected)

                if backend == 'sing-tun':
                    callers = attempt.singHostSettingsCallers
                    self.assertIsNone(attempt.tun2socksSettingsCallers)
                    self.assertEqual(callers.userTunAdapterInterfaceDNS(), '9.9.9.9')
                    self.assertIs(callers.userDisablePrimaryAdapterInterfaceDNS(), True)
                else:
                    callers = attempt.tun2socksSettingsCallers
                    self.assertIsNone(attempt.singHostSettingsCallers)
                    self.assertEqual(callers.userTunAdapterInterfaceDNS(), '8.8.8.8')
                    self.assertEqual(
                        callers.userDisablePrimaryAdapterInterfaceDNS(), 'True'
                    )
                    self.assertEqual(callers.userTcpSendBufferSize(), 1)

                self.assertEqual(
                    getattr(
                        attempt,
                        (
                            'tun2socksSettings'
                            if backend == 'sing-tun'
                            else 'singSettings'
                        ),
                    ),
                    {},
                )

    def testBothStartupPathsUseNamedCallersBoundBeforePrimaryLaunch(self):
        """Settings edited during core launch only affect the next attempt."""
        module = importlib.import_module('Furious.Service.ConnectionManager')

        for backend in ('tun2socks', 'sing-tun'):
            for asynchronous in (True, False):
                with self.subTest(backend=backend, asynchronous=asynchronous):
                    with isolatedSettings():
                        AppSettings.set('ApplicationTUNBackend', backend)
                        host = {'tunAdapterInterfaceDNS': '9.9.9.9'}
                        stored = (
                            {'host_options': host} if backend == 'sing-tun' else host
                        )
                        getter = (
                            'UserSingTUNSettings'
                            if backend == 'sing-tun'
                            else 'UserTUNSettings'
                        )
                        inactive = (
                            'UserTUNSettings'
                            if backend == 'sing-tun'
                            else 'UserSingTUNSettings'
                        )
                        manager = ConnectionManager()
                        primary = _Runtime()
                        observed = []

                        def changeSettings(*_args, **_kwargs):
                            host['tunAdapterInterfaceDNS'] = '1.0.0.1'
                            return True

                        def observeSettings(attempt):
                            callers = (
                                attempt.singHostSettingsCallers
                                if backend == 'sing-tun'
                                else attempt.tun2socksSettingsCallers
                            )
                            observed.append(callers.userTunAdapterInterfaceDNS())

                        def finishAsync(operation):
                            observeSettings(operation.attempt)
                            operation._commit()

                        def finishSync(attempt, *_args):
                            observeSettings(attempt)
                            return True

                        try:
                            with mock.patch.object(
                                Storage, getter, return_value=stored
                            ) as selected, mock.patch.object(
                                Storage,
                                inactive,
                                side_effect=AssertionError('inactive backend read'),
                            ), mock.patch.object(
                                manager, '_prepareTUNPolicy', return_value=(False, True)
                            ), mock.patch.object(
                                module.SystemRuntime, 'isTUNMode', return_value=True
                            ):
                                if asynchronous:
                                    startPrimary = primary.start

                                    def launchPrimary():
                                        changeSettings()
                                        startPrimary()

                                    with mock.patch.object(
                                        module,
                                        'getPluginRegistry',
                                        return_value=_Registry(
                                            [PreparedRuntime(primary)]
                                        ),
                                    ), mock.patch.object(
                                        primary, 'start', side_effect=launchPrimary
                                    ), mock.patch.object(
                                        module.ConnectionStartOperation,
                                        '_beginApplicationTun',
                                        autospec=True,
                                        side_effect=finishAsync,
                                    ):
                                        operation = manager.startAsync(
                                            _Configuration(), 'Global', deepcopy=False
                                        )
                                        self.assertTrue(
                                            waitFor(lambda: operation._terminal)
                                        )
                                        self.assertTrue(operation.attempt.committed)
                                else:
                                    starter = (
                                        '_startApplicationSingTUN'
                                        if backend == 'sing-tun'
                                        else '_startApplicationTun2socks'
                                    )
                                    with mock.patch.object(
                                        manager,
                                        '_startPrimaryRuntime',
                                        side_effect=changeSettings,
                                    ), mock.patch.object(
                                        manager, starter, side_effect=finishSync
                                    ):
                                        self.assertTrue(
                                            manager.start(
                                                _Configuration(),
                                                'Global',
                                                deepcopy=False,
                                            )
                                        )

                                self.assertEqual(observed, ['9.9.9.9'])
                                self.assertEqual(
                                    host['tunAdapterInterfaceDNS'], '1.0.0.1'
                                )

                                nextAttempt = _ConnectionStartAttempt(
                                    manager,
                                    _Configuration(),
                                    applicationTun2socks=True,
                                    tunBackend=backend,
                                )
                                nextAttempt.snapshotApplicationTUN()
                                observeSettings(nextAttempt)

                                self.assertEqual(observed, ['9.9.9.9', '1.0.0.1'])
                                self.assertEqual(selected.call_count, 2)
                        finally:
                            manager.cleanup()
                            primary.dispose()
                            processQtEvents()

    def testBothPreferencesPreserveNativePriorityAndTypedFailure(self):
        module = importlib.import_module('Furious.Service.ConnectionManager')

        for backend in ('sing-tun', 'tun2socks'):
            for failure in (False, True):
                with self.subTest(backend=backend, failure=failure), isolatedSettings():
                    AppSettings.set('ApplicationTUNBackend', backend)
                    manager, primary = ConnectionManager(), _Runtime()
                    registry = _Registry([PreparedRuntime(primary)])
                    registry.prepareTUN = mock.Mock(
                        return_value=True,
                        side_effect=(
                            TUNPreparationError('native failed') if failure else None
                        ),
                    )
                    registry.usesApplicationTun2socks = mock.Mock()

                    with mock.patch.object(
                        module.SystemRuntime, 'isTUNMode', return_value=True
                    ), mock.patch.object(
                        module, 'getPluginRegistry', return_value=registry
                    ), mock.patch.object(
                        module, 'SingTUN'
                    ) as sing, mock.patch.object(
                        module, 'Tun2socks'
                    ) as tun2socks, mock.patch.object(
                        Storage, 'UserSingTUNSettings'
                    ) as stored:
                        operation = manager.startAsync(
                            _Configuration(), 'Global', deepcopy=False
                        )
                        self.assertTrue(waitFor(lambda: operation._terminal))

                        sing.assert_not_called()
                        tun2socks.assert_not_called()
                        stored.assert_not_called()
                        registry.usesApplicationTun2socks.assert_not_called()
                        self.assertEqual(primary.isRunning(), not failure)
                        self.assertFalse(manager.usesApplicationTUN())

                        manager.cleanup()

                processQtEvents()

    def testInvalidSettingsReleaseDetachedRouterAndPrimaryRuntime(self):
        module = importlib.import_module('Furious.Service.ConnectionManager')
        primaryRouter, router = RuntimeEventRouter(), RuntimeEventRouter()
        primary = _Runtime()
        manager = ConnectionManager()

        with isolatedSettings(), mock.patch.object(
            Storage,
            'UserTUNSettings',
            side_effect=AssertionError('inactive tun2socks backend'),
        ), mock.patch.object(
            Storage, 'UserSingTUNSettings', return_value={'stack': 'go'}
        ), mock.patch.object(
            manager, '_prepareTUNPolicy', return_value=(False, True)
        ), mock.patch.object(
            module,
            'getPluginRegistry',
            return_value=_Registry([PreparedRuntime(primary)]),
        ):
            AppSettings.set('ApplicationTUNBackend', 'sing-tun')

            operation = manager.startAsync(_Configuration(), 'Global', deepcopy=False)

            with mock.patch.object(
                module, 'RuntimeEventRouter', side_effect=[primaryRouter, router]
            ):
                self.assertTrue(waitFor(lambda: operation._terminal))
                self.assertEqual(router.state, RuntimeLeaseState.Released)
                self.assertFalse(primary.isRunning())
                self.assertEqual(manager.runtimes, [])

            manager.cleanup()

        processQtEvents()

        self.assertFalse(isValid(router))

    def testAliveDoesNotCommitUntilAuthoritativeNativeReadyAndDNSComplete(self):
        module = importlib.import_module('Furious.Service.ConnectionManager')
        manager = ConnectionManager()
        primary = _Runtime()
        registry = _Registry([PreparedRuntime(primary)])
        customized = {
            'tun_options': {'MTU': 1400},
            'host_options': {'bypassTUNAdapterInterfaceIP': '2001:db8::1'},
        }
        runtimes = []

        def create(*args, **kwargs):
            runtime = _PreparedSing(*args, **kwargs)
            runtimes.append(runtime)
            return runtime

        with isolatedSettings(), mock.patch.object(
            Storage,
            'UserTUNSettings',
            side_effect=AssertionError('inactive tun2socks backend'),
        ), mock.patch.object(
            Storage, 'UserSingTUNSettings', return_value=customized
        ), mock.patch.object(
            manager, '_prepareTUNPolicy', return_value=(False, True)
        ), mock.patch.object(
            module, 'getPluginRegistry', return_value=registry
        ), mock.patch.object(
            module, 'SingTUN', _PreparedSing
        ), mock.patch.object(
            module, 'SingTUNHostPlan', _Plan
        ), mock.patch.object(
            manager, '_createSingTUN', wraps=manager._createSingTUN
        ):
            AppSettings.set('ApplicationTUNBackend', 'sing-tun')

            succeeded = []
            operation = manager.startAsync(_Configuration(), 'Global', deepcopy=False)
            operation.succeeded.connect(succeeded.append)

            self.assertTrue(
                waitFor(lambda: operation._tun is not None and operation._tun.alive)
            )

            runtime = operation._tun
            self.assertFalse(succeeded)
            self.assertEqual(manager.runtimes, [])
            self.assertFalse(manager.usesApplicationTUN())

            AppSettings.set('ApplicationTUNBackend', 'tun2socks')
            customized['host_options']['bypassTUNAdapterInterfaceIP'] = '192.0.2.99'
            customized['tun_options']['MTU'] = 1300

            self.assertEqual(operation.attempt.tunBackend, 'sing-tun')
            self.assertEqual(runtime._configuration['tun_options']['MTU'], 1400)

            runtime.nativeReady = True

            self.assertTrue(waitFor(lambda: bool(succeeded)))
            self.assertTrue(manager.usesApplicationTUN())
            self.assertEqual(runtime._hostPlan.applied, ['utun101'])
            self.assertEqual(runtime._hostPlan.addresses, ['192.0.2.1', '2001:db8::1'])

            manager.cleanup()

            self.assertFalse(manager.usesApplicationTUN())

        processQtEvents()

    def testCancellationBeforeNativeReadyReleasesBothOwners(self):
        module = importlib.import_module('Furious.Service.ConnectionManager')
        manager = ConnectionManager()
        primary = _Runtime()

        with isolatedSettings(), mock.patch.object(
            Storage,
            'UserTUNSettings',
            side_effect=AssertionError('inactive tun2socks backend'),
        ), mock.patch.object(
            Storage, 'UserSingTUNSettings', return_value={}
        ), mock.patch.object(
            manager, '_prepareTUNPolicy', return_value=(False, True)
        ), mock.patch.object(
            module,
            'getPluginRegistry',
            return_value=_Registry([PreparedRuntime(primary)]),
        ), mock.patch.object(
            module, 'SingTUN', _PreparedSing
        ), mock.patch.object(
            module, 'SingTUNHostPlan', _Plan
        ):
            AppSettings.set('ApplicationTUNBackend', 'sing-tun')

            operation = manager.startAsync(_Configuration(), 'Global', deepcopy=False)
            self.assertTrue(
                waitFor(lambda: operation._tun is not None and operation._tun.alive)
            )
            runtime = operation._tun

            operation.cancel()

            self.assertTrue(runtime.released)
            self.assertFalse(primary.alive)
            self.assertEqual(manager.runtimes, [])

            manager.cleanup()

        processQtEvents()

    def testSynchronousCompatibilityPathSelectsSingAndCommitsAfterHostDNS(self):
        module = importlib.import_module('Furious.Service.ConnectionManager')
        manager = ConnectionManager()
        primary = _Runtime()
        primary.start()

        with isolatedSettings(), mock.patch.object(
            Storage,
            'UserTUNSettings',
            side_effect=AssertionError('inactive tun2socks backend'),
        ), mock.patch.object(
            Storage, 'UserSingTUNSettings', return_value={}
        ), mock.patch.object(
            manager, '_prepareTUNPolicy', return_value=(False, True)
        ), mock.patch.object(
            manager, '_startCoreRuntime', return_value=(primary, True)
        ), mock.patch.object(
            module.SystemRuntime, 'isTUNMode', return_value=True
        ), mock.patch.object(
            module, 'SingTUN', _PreparedSing
        ), mock.patch.object(
            module, 'SingTUNHostPlan', _Plan
        ), mock.patch.object(
            _PreparedSing, 'ready', new_callable=mock.PropertyMock, return_value=True
        ):
            AppSettings.set('ApplicationTUNBackend', 'sing-tun')

            self.assertTrue(manager.start(_Configuration(), 'Global', deepcopy=False))
            self.assertEqual(manager.runtimes[1]._hostPlan.applied, ['utun101'])
            self.assertTrue(manager.usesApplicationTUN())

            manager.cleanup()

            self.assertFalse(manager.usesApplicationTUN())

    def testSocksOnlyResolverHasNoHTTPOrDirectFallback(self):
        resolver = mock.Mock()
        configuration = _Configuration()
        configuration.httpProxy = lambda: ''

        ConnectionManager._configureTunResolver(resolver, configuration)

        resolver.configureSocksProxy.assert_called_once_with('socks5://127.0.0.1:18081')
        resolver.configureHttpProxy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
