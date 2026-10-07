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

"""Coordinate proxy cores, TUN mode, DNS, and platform routing."""

from __future__ import annotations

from Furious.Frozenlib import (
    APPLICATION_TUN2SOCKS_DEVICE_NAME,
    APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
    APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS,
    APPLICATION_TUN2SOCKS_IP_ADDRESS,
    APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME,
    APPLICATION_TUN_BACKEND,
    AppSettings,
    Mixins,
    PLATFORM,
    PySide6Legacy,
    SystemRoutingTable,
    SystemRuntime,
    isValidIPAddress,
    parseHostPort,
)
from Furious.Interface import CoreRuntime, RuntimeExit, RuntimeStartError
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Repository import Storage
from Furious.Plugins import (
    CoreRuntimeStartup,
    PreparedRuntime,
    TUNPreparationError,
    getPluginRegistry,
)
from Furious.Qt.Signals import connectWeakly, singleShotWeakly
from Furious.Service.DnsResolver import DnsResolver
from Furious.Core.Tun2socks import Tun2socks
from Furious.Core.SingTUN import SingTUN
from Furious.Models.SingTUN import SingTUNHostSettingsCallers, prepareSingTUNSettings
from Furious.Frozenlib.SocksProxy import socksURL
from Furious.Service.SingTUNHost import SingTUNHostPlan
from Furious.Service.RuntimeLease import RuntimeEventRouter, RuntimeLease

from PySide6 import QtCore, QtNetwork

from shiboken6 import isValid

from typing import Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

import os
import logging
import tempfile
import functools
import copy
import time
import ipaddress
import weakref

__all__ = ['ConnectionManager', 'ConnectionStartOperation', 'ConnectionStartStage']

logger = logging.getLogger(__name__)


@dataclass
class _ConnectionStartAttempt:
    """Track resources acquired by one connection startup attempt."""

    manager: 'ConnectionManager'
    runtimeConfiguration: CoreConfiguration | ServerProfile
    leases: list[RuntimeLease] = field(default_factory=list)
    nativeTUNHandled: bool = False
    applicationTun2socks: bool = False
    committed: bool = False
    tunBackend: str = field(
        default_factory=lambda: AppSettings.get(APPLICATION_TUN_BACKEND)
    )
    singSettings: dict = field(default_factory=dict)
    tun2socksSettings: dict = field(default_factory=dict)
    singHostSettingsCallers: SingTUNHostSettingsCallers | None = field(
        default=None, init=False, repr=False
    )
    tun2socksSettingsCallers: _Tun2socksSettingsCallers | None = field(
        default=None, init=False, repr=False
    )

    def applicationTUNLogCallback(self, callback):
        """Bind the engine captured by this attempt, preserving plain callbacks."""
        copyWithSource = getattr(callback, 'copyWithSource', None)

        return copyWithSource(self.tunBackend) if callable(copyWithSource) else callback

    def snapshotApplicationTUN(self):
        """Read engine settings only when the plugin requires application TUN."""
        if self.applicationTun2socks:
            if self.tunBackend == 'sing-tun':
                self.singSettings = copy.deepcopy(Storage.UserSingTUNSettings())
                self.singHostSettingsCallers = SingTUNHostSettingsCallers(
                    self.singSettings.get('host_options', {})
                )
            else:
                self.tun2socksSettings = copy.deepcopy(Storage.UserTUNSettings())
                self.tun2socksSettingsCallers = _Tun2socksSettingsCallers(
                    self.tun2socksSettings
                )

    @property
    def runtimes(self):
        """Return an ordered execution-resource snapshot for this attempt."""
        return [lease.runtime for lease in self.leases]

    def ownRuntime(
        self, runtime: CoreRuntime | None, router=None, *, applicationTUN=False
    ):
        """Retain one exact runtime lease until the attempt commits."""
        if runtime is None:
            return None

        router = router or RuntimeEventRouter()
        lease = RuntimeLease(runtime, router, applicationTUN=applicationTUN)

        self.leases.append(lease)

        return lease

    def rollback(self, message: str = '') -> bool:
        """Release this attempt's resources in reverse acquisition order."""
        if message:
            logger.error(message)

        if self.committed:
            return False

        for lease in reversed(self.leases):
            if not lease.release():
                self.manager._pendingReleases.append(lease)

        self.leases.clear()

        return False

    def commit(self, exitCallback=None):
        """Atomically transfer acquired runtimes to the manager lifecycle."""
        if self.committed:
            return

        for lease in self.leases:
            lease.commit(exitCallback)

        self.manager._leases.extend(self.leases)
        self.leases.clear()

        self.committed = True


class _Tun2socksSettingsCallers:
    """Bind named tun2socks settings callers to one attempt's captured document."""

    def __init__(self, settings):
        (
            self.userPrimaryAdapterInterfaceName,
            self.userPrimaryAdapterInterfaceIP,
            self.userDefaultPrimaryGatewayIP,
            self.userTunAdapterInterfaceDNS,
            self.userBypassTUNAdapterInterfaceIP,
            self.userDisablePrimaryAdapterInterfaceDNS,
            self.userTcpSendBufferSize,
            self.userTcpReceiveBufferSize,
            self.userTcpAutoTuning,
        ) = (
            functools.partial(settings.get, 'primaryAdapterInterfaceName', ''),
            functools.partial(settings.get, 'primaryAdapterInterfaceIP', ''),
            functools.partial(settings.get, 'defaultPrimaryGatewayIP', ''),
            functools.partial(settings.get, 'tunAdapterInterfaceDNS', ''),
            functools.partial(settings.get, 'bypassTUNAdapterInterfaceIP', ''),
            functools.partial(
                settings.get, 'disablePrimaryAdapterInterfaceDNS', 'True'
            ),
            functools.partial(settings.get, 'tcpSendBufferSize', 1),
            functools.partial(settings.get, 'tcpReceiveBufferSize', 1),
            functools.partial(settings.get, 'tcpAutoTuning', 'False'),
        )


class ConnectionStartStage(Enum):
    """Describe the active stage of one connection startup transaction."""

    Pending = 'pending'
    Preparing = 'preparing'
    StartingPrimary = 'starting-primary'
    WaitingPrimary = 'waiting-primary'
    PreparingTUN = 'preparing-tun'
    ResolvingTUNAddress = 'resolving-tun-address'
    WaitingTUNDevice = 'waiting-tun-device'
    StartingTUNRuntime = 'starting-tun-runtime'
    WaitingTUNRuntime = 'waiting-tun-runtime'
    ApplyingHostNetwork = 'applying-host-network'
    Committing = 'committing'
    Succeeded = 'succeeded'
    Failed = 'failed'
    Cancelled = 'cancelled'


class _RuntimeReadinessProbe(QtCore.QObject):
    """Observe an optional local endpoint without competing with runtime exits."""

    ready = QtCore.Signal()
    failed = QtCore.Signal(str)

    def __init__(self, runtime, startup, parent=None):
        """Initialize a bounded readiness observer."""
        super().__init__(parent)

        self._runtime = runtime
        self._startup = startup
        self._terminal = False
        self._host = ''
        self._port = 0

        self._elapsed = QtCore.QElapsedTimer()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(max(int(startup.retryInterval), 1))

        connectWeakly(self._timer.timeout, self, '_poll')

        self._socket = QtNetwork.QTcpSocket(self)

        connectWeakly(self._socket.connected, self, '_connected')

    def start(self):
        """Begin observing without blocking or nesting the Qt event loop."""
        if self._terminal or self._timer.isActive():
            return

        if self._startup.endpoint:
            try:
                self._host, port = parseHostPort(self._startup.endpoint)
                self._port = int(port)
            except Exception:
                # Any non-exit exceptions

                self._finishFailed(
                    f'invalid runtime readiness endpoint: '
                    f'{self._startup.endpoint!r}'
                )

                return

        self._elapsed.start()
        self._timer.start()
        self._poll()

    def _poll(self):
        """Retry endpoint connection and enforce the startup deadline."""
        if self._terminal:
            return

        if isinstance(self._runtime, SingTUN):
            if self._runtime.startupError:
                self._finishFailed(self._runtime.startupError)

                return

            if self._runtime.ready:
                self._finishReady()

                return

        timeout = max(int(self._startup.timeout), 1)

        if self._elapsed.isValid() and self._elapsed.elapsed() >= timeout:
            if self._startup.endpoint or isinstance(self._runtime, SingTUN):
                self._finishFailed('core readiness check timed out')
            else:
                self._finishReady()

            return

        if (
            self._startup.endpoint
            and self._socket.state()
            is QtNetwork.QAbstractSocket.SocketState.UnconnectedState
        ):
            self._socket.connectToHost(self._host, self._port)

    def _connected(self):
        """Accept the first successful local endpoint connection."""
        self._finishReady()

    def _finishReady(self):
        """Publish readiness exactly once."""
        if self._terminal:
            return

        self._terminal = True
        self._timer.stop()
        self._socket.abort()

        self.ready.emit()

    def _finishFailed(self, message):
        """Publish startup failure exactly once."""
        if self._terminal:
            return

        self._terminal = True
        self._timer.stop()
        self._socket.abort()

        self.failed.emit(str(message))

    def cancel(self):
        """Stop all probe resources without publishing a stale result."""
        if self._terminal:
            return

        self._terminal = True
        self._timer.stop()
        self._socket.abort()


class _ConditionProbe(QtCore.QObject):
    """Poll one host condition through a bounded parent-owned Qt timer."""

    finished = QtCore.Signal(bool)

    def __init__(self, predicate, description, timeout=10000, parent=None):
        """Initialize an idle condition observer."""
        super().__init__(parent)

        self._predicate = predicate
        self._description = description
        self._timeout = max(int(timeout), 1)
        self._terminal = False

        self._elapsed = QtCore.QElapsedTimer()
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(100)

        connectWeakly(self._timer.timeout, self, '_poll')

    def start(self):
        """Begin polling the condition."""
        if self._terminal or self._timer.isActive():
            return

        self._elapsed.start()
        self._timer.start()
        self._poll()

    def _poll(self):
        """Publish the first successful observation or one timeout."""
        if self._terminal:
            return

        try:
            ready = bool(self._predicate())
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'failed to inspect {self._description}: {ex}')

            ready = False

        if not isValid(self) or self._terminal:
            return

        if ready:
            logger.info(f'find {self._description} success')

            self._finish(True)
        elif self._elapsed.isValid() and self._elapsed.elapsed() >= self._timeout:
            logger.error(f'find {self._description} failed')

            self._finish(False)

    def _finish(self, success):
        """Publish exactly one terminal condition result."""
        if self._terminal:
            return

        self._terminal = True
        self._timer.stop()

        self.finished.emit(bool(success))

    def cancel(self):
        """Stop polling without publishing a stale result."""
        if self._terminal:
            return

        self._terminal = True
        self._timer.stop()


def _cleanupDestroyedStartOperation(reference, *_args):
    """Release an unfinished attempt before native child observers are deleted."""
    operation = reference()

    if operation is None:
        return

    if not operation._terminal:
        operation.stage = ConnectionStartStage.Cancelled

    operation._terminal = True

    try:
        operation._cancelObservers()
    finally:
        try:
            operation.attempt.rollback()
        finally:
            if operation.manager._activeStartOperation is operation:
                operation.manager._finishStartOperation(operation)


class ConnectionStartOperation(QtCore.QObject):
    """Own one cancellable, staged connection startup transaction."""

    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(object, str, str)
    cancelled = QtCore.Signal(object)
    stageChanged = QtCore.Signal(object)

    def __init__(
        self,
        manager,
        generation,
        config,
        routing,
        *,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        options=None,
        parent=None,
    ):
        """Initialize an operation without starting any resource."""
        super().__init__(parent)

        self.manager = manager
        self.generation = generation
        self.routing = routing
        self.exitCallback = exitCallback
        self.msgCallbackCore = msgCallbackCore
        self.proxyModeOnly = proxyModeOnly
        self.log = log
        self.options = dict(options or {})

        self.attempt = _ConnectionStartAttempt(
            manager, manager._runtimeConfiguration(config, deepcopy)
        )
        self.msgCallbackTUN_ = self.attempt.applicationTUNLogCallback(msgCallbackTUN_)

        self.stage = ConnectionStartStage.Pending

        self._terminal = False
        self._readinessProbe = None
        self._conditionProbe = None
        self._conditionContinuation = ''
        self._conditionFailureMessage = 'TUN device did not become ready'
        self._dnsOperation = None
        self._tun = None
        self._startTUN = None
        self._gateway = None
        self._interface = None

        self.destroyed.connect(
            functools.partial(_cleanupDestroyedStartOperation, weakref.ref(self))
        )

    def _isCurrent(self):
        """Return whether this generation still owns manager startup."""
        return (
            isValid(self)
            and not self._terminal
            and self.manager._activeStartOperation is self
            and self.manager._startGeneration == self.generation
        )

    def _setStage(self, stage):
        """Publish one observable startup stage."""
        if self.stage is stage:
            return

        self.stage = stage
        self.stageChanged.emit(stage)

    def _resume(self, methodName):
        """Run one named continuation and translate exceptions into rollback."""
        if not self._isCurrent():
            return

        try:
            getattr(self, methodName)()
        except Exception as ex:
            # Any non-exit exceptions

            self._fail('', str(ex))

    def start(self):
        """Start the semantic transaction after observers are connected."""
        if not self._isCurrent() or self.stage is not ConnectionStartStage.Pending:
            return

        self._setStage(ConnectionStartStage.Preparing)

        if not self._isCurrent():
            return

        configcopy = self.attempt.runtimeConfiguration

        try:
            (
                self.attempt.nativeTUNHandled,
                self.attempt.applicationTun2socks,
            ) = self.manager._prepareTUNPolicy(configcopy, self.proxyModeOnly)

            self.attempt.snapshotApplicationTUN()
        except TUNPreparationError as ex:
            self.manager._lastStartError = str(ex)

            self._fail(str(ex), 'native TUN preparation failed')

            return
        except Exception as ex:
            # Any non-exit exceptions

            self._fail('', str(ex))

            return

        self._resume('_startPrimary')

    def _startPrimary(self):
        """Construct and launch the primary runtime under attempt ownership."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.StartingPrimary)

        if not self._isCurrent():
            return

        router = RuntimeEventRouter()

        try:
            launch = getPluginRegistry().createCoreRuntime(
                self.attempt.runtimeConfiguration,
                self.routing,
                exitCallback=router.publish,
                messageCallback=self.msgCallbackCore,
                proxyModeOnly=self.proxyModeOnly,
                log=self.log,
                **self.options,
            )
        except Exception as ex:
            # Any non-exit exceptions

            self._fail('', str(ex))

            return

        if not isinstance(launch, PreparedRuntime):
            self._fail('', 'no core runtime is available for this configuration')

            return

        runtime = launch.runtime

        router.attach(runtime, self)

        self.attempt.ownRuntime(runtime, router)

        if not self._isCurrent():
            self.attempt.rollback()

            return

        try:
            launch.start()
        except RuntimeStartError as ex:
            self._fail(ex.message, ex.details)

            return
        except Exception as ex:
            # Any non-exit exceptions

            self._fail(self._runtimeStartMessage(runtime), str(ex))

            return

        if launch.readiness is None:
            self._resume('_afterPrimaryReady')
        else:
            self._observeRuntime(
                runtime,
                launch.readiness,
                '_afterPrimaryReady',
                ConnectionStartStage.WaitingPrimary,
            )

    def _observeRuntime(self, runtime, startup, continuation, stage):
        """Observe runtime readiness and resume through a named method."""
        if not self._isCurrent():
            return

        self._setStage(stage)

        if not self._isCurrent():
            return

        self._conditionContinuation = continuation

        probe = _RuntimeReadinessProbe(runtime, startup, parent=self)

        self._readinessProbe = probe

        connectWeakly(probe.ready, self, '_runtimeReady')
        connectWeakly(probe.failed, self, '_runtimeReadinessFailed')

        probe.start()

    def _runtimeReady(self):
        """Confirm the observed runtime and resume its continuation."""
        if not self._isCurrent() or self._readinessProbe is None:
            return

        probe = self._readinessProbe
        runtime = probe._runtime
        continuation = self._conditionContinuation

        self._readinessProbe = None
        self._conditionContinuation = ''

        probe.deleteLater()

        self._resume(continuation)

    def _runtimeReadinessFailed(self, message):
        """Fail the transaction when a readiness observer reaches terminal."""
        if not self._isCurrent() or self._readinessProbe is None:
            return

        probe = self._readinessProbe
        runtime = probe._runtime

        if not runtime.isRunning():
            # The runtime owns process-exit interpretation. Its typed event may
            # already be queued behind this direct readiness signal, so never
            # replace that semantic failure with a generic endpoint timeout.
            return

        self._readinessProbe = None
        self._conditionContinuation = ''

        self._fail('Failed to start core', message)

    def _afterPrimaryReady(self):
        """Continue into application TUN or commit a proxy-only startup."""
        if not self._isCurrent():
            return

        if self.attempt.applicationTun2socks:
            self._beginApplicationTun()
        else:
            self._commit()

    def runtimeExited(self, runtime, event: RuntimeExit):
        """Abort on one typed exit while this attempt owns the runtime."""
        if not self._isCurrent():
            return

        self._fail(
            event.message,
            f'{runtime.name()} exited during {self.stage.value} with code '
            f'{event.code}; reason={event.reason.value}',
        )

    def _beginApplicationTun(self):
        """Acquire tun2socks and preserve the platform's startup ordering."""
        if not self._isCurrent():
            return

        if self.attempt.tunBackend == 'sing-tun':
            self._resume('_beginSingTUN')

            return

        self._setStage(ConnectionStartStage.PreparingTUN)

        if not self._isCurrent():
            return

        configcopy = self.attempt.runtimeConfiguration

        if PLATFORM == 'Windows':
            SystemRoutingTable.delete(
                '0.0.0.0',
                APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
            )

        settings = self.attempt.tun2socksSettingsCallers
        userGateway = settings.userDefaultPrimaryGatewayIP()
        userInterfaceIP = settings.userPrimaryAdapterInterfaceIP()

        if userGateway and userInterfaceIP:
            logger.info(
                f'got user defined TUN settings. '
                f'\'DefaultPrimaryGatewayIP\': {userGateway}. '
                f'\'PrimaryAdapterInterfaceIP\': {userInterfaceIP}'
            )

            self._gateway, self._interface = userGateway, userInterfaceIP
        else:
            logger.info(
                'automatically fetching TUN settings: '
                '\'DefaultPrimaryGatewayIP\' and '
                '\'PrimaryAdapterInterfaceIP\''
            )

            defaultGateway = SystemRoutingTable.getDefaultGateway()

            if PLATFORM == 'Darwin':
                defaultGateway = list(
                    filter(
                        lambda item: (item != APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS),
                        defaultGateway,
                    )
                )

            if len(defaultGateway) != 1:
                self._fail('', f'bad default gateway: {defaultGateway}')

                return

            if PLATFORM in ('Windows', 'Linux'):
                self._gateway, self._interface = defaultGateway[0]
            elif PLATFORM == 'Darwin':
                self._gateway, self._interface = defaultGateway[0], None
            else:
                self._fail('', f'unrecognized platform: {PLATFORM}')

                return

        tcpSendBufferSize = settings.userTcpSendBufferSize()
        tcpReceiveBufferSize = settings.userTcpReceiveBufferSize()
        tcpAutoTuning = settings.userTcpAutoTuning() == 'True'
        interfaceArg = (
            APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME
            if PLATFORM != 'Linux'
            else self._interface
        )

        router = RuntimeEventRouter()
        tun = Tun2socks(
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            interfaceArg,
            'error',
            f'socks5://{configcopy.socksProxy()}',
            '',
            f'{tcpSendBufferSize}MB',
            f'{tcpReceiveBufferSize}MB',
            tcpAutoTuning,
            exitCallback=router.publish,
            msgCallback=self.msgCallbackTUN_,
        )

        router.attach(tun, self)

        self._tun = tun
        self.attempt.ownRuntime(tun, router, applicationTUN=True)
        self._startTUN = tun.start

        if PLATFORM != 'Linux':
            self._setStage(ConnectionStartStage.StartingTUNRuntime)

            if not self._isCurrent():
                return

            try:
                self._startTUN()
            except RuntimeStartError as ex:
                self._fail(ex.message, ex.details)

                return

        if PLATFORM == 'Darwin':
            self._observeRuntime(
                tun,
                CoreRuntimeStartup(),
                '_prepareTunBypass',
                ConnectionStartStage.WaitingTUNRuntime,
            )
        else:
            self._resume('_prepareTunBypass')

    def _beginSingTUN(self):
        """Validate before activation, then resolve remote exclusions via the core."""
        self._setStage(ConnectionStartStage.PreparingTUN)

        if not self._isCurrent():
            return

        router = RuntimeEventRouter()

        try:
            self._tun = self.manager._createSingTUN(
                self.attempt, router.publish, self.msgCallbackTUN_
            )
        except BaseException:
            router.finishRelease()
            router.deleteLater()

            raise

        router.attach(self._tun, self)

        self.attempt.ownRuntime(self._tun, router, applicationTUN=True)

        address = self.attempt.runtimeConfiguration.remoteAddress()

        if isValidIPAddress(address):
            self._singAddressesResolved(False, [address])

            return

        if not address:
            raise ValueError('A remote destination is required for sing-tun bypass')

        resolver = self.manager._connectionDnsResolver()

        self.manager._configureTunResolver(resolver, self.attempt.runtimeConfiguration)

        self._setStage(ConnectionStartStage.ResolvingTUNAddress)

        if not self._isCurrent():
            return

        operation = resolver.resolveAsync(address, parent=self)

        self._dnsOperation = operation

        connectWeakly(operation.finished, self, '_singAddressesResolved')

        operation.start()

    def _singAddressesResolved(self, error, addresses):
        if not self._isCurrent():
            return

        operation, self._dnsOperation = self._dnsOperation, None

        if operation is not None:
            operation.deleteLater()

        if error or not addresses:
            self._fail(
                'Failed to prepare sing-tun', 'Remote bypass DNS resolution failed'
            )

            return

        try:
            addresses = self.manager._singBypassAddresses(self.attempt, addresses)

            self._tun._hostPlan.begin('prepare', addresses)

            self._waitSingHost('_startSingTUN')
        except Exception as ex:
            # Any non-exit exceptions

            self._fail('Failed to prepare sing-tun', str(ex))

    def _waitSingHost(self, continuation):
        if not self._isCurrent():
            return

        self._observeCondition(
            self._tun._hostPlan.workCompleted,
            'sing-tun host preparation',
            continuation,
            self.stage,
            'sing-tun host preparation timed out',
        )

    def _startSingTUN(self):
        if self._tun._hostPlan.error:
            raise RuntimeStartError(self._tun._hostPlan.error)

        self._setStage(ConnectionStartStage.StartingTUNRuntime)

        if not self._isCurrent():
            return

        self._tun.start()

        self._observeRuntime(
            self._tun,
            CoreRuntimeStartup(timeout=15000),
            '_applySingDNS',
            ConnectionStartStage.WaitingTUNRuntime,
        )

    def _applySingDNS(self):
        self._setStage(ConnectionStartStage.ApplyingHostNetwork)

        if not self._isCurrent():
            return

        self._tun._hostPlan.begin('applyDNS', self._tun.deviceName)

        self._waitSingHost('_singHostReady')

    def _singHostReady(self):
        if self._tun._hostPlan.error:
            raise RuntimeStartError(self._tun._hostPlan.error)

        self._commit()

    def _prepareTunBypass(self):
        """Prepare remote-server bypass routes without blocking for DNS."""
        if not self._isCurrent():
            return

        bypassTUN = (
            self.attempt.tun2socksSettingsCallers.userBypassTUNAdapterInterfaceIP()
        )

        if bypassTUN:
            for bypass in bypassTUN.split(','):
                bypass = bypass.strip()

                if not isValidIPAddress(bypass):
                    SystemRoutingTable.managedRoutes.clear()

                    self._fail(
                        '',
                        f'invalid IP address when processing user TUN '
                        f'bypass settings: {bypass}',
                    )

                    return

                logger.info(f'processing user TUN bypass IP: {bypass}')

                SystemRoutingTable.managedRoutes.append([bypass, self._gateway])

            self._resume('_continueTunPlatform')

            return

        address = self.attempt.runtimeConfiguration.remoteAddress()

        if isValidIPAddress(address):
            SystemRoutingTable.managedRoutes.append([address, self._gateway])

            self._resume('_continueTunPlatform')

            return

        self._setStage(ConnectionStartStage.ResolvingTUNAddress)

        resolver = self.manager._connectionDnsResolver()
        resolver.configureHttpProxy(self.attempt.runtimeConfiguration.httpProxy())

        operation = resolver.resolveAsync(address, parent=self)

        self._dnsOperation = operation

        connectWeakly(operation.finished, self, '_tunAddressResolved')

        operation.start()

    def _tunAddressResolved(self, error, resolved):
        """Resume TUN setup after event-driven remote-address resolution."""
        if not self._isCurrent():
            return

        operation = self._dnsOperation

        self._dnsOperation = None

        if operation is not None:
            operation.deleteLater()

        if error:
            SystemRoutingTable.managedRoutes.clear()

            self._fail(
                '',
                f'DNS resolution failed: '
                f'{self.attempt.runtimeConfiguration.remoteAddress()}',
            )

            return

        for address in resolved:
            SystemRoutingTable.managedRoutes.append([address, self._gateway])

        self._resume('_continueTunPlatform')

    def _continueTunPlatform(self):
        """Continue with the platform-specific TUN stage."""
        if PLATFORM == 'Windows':
            self._waitForTunDevice(
                functools.partial(
                    SystemRoutingTable.WIN32IpconfigFindContent,
                    APPLICATION_TUN2SOCKS_DEVICE_NAME,
                ),
                '_applyWindowsTun',
            )
        elif PLATFORM == 'Darwin':
            self._applyDarwinTun()
        elif PLATFORM == 'Linux':
            self._prepareLinuxTun()
        else:
            self._fail('', f'unrecognized platform: {PLATFORM}')

    def _waitForTunDevice(self, predicate, continuation):
        """Wait for one platform TUN device through a Qt timer."""
        self._observeCondition(
            predicate,
            f'TUN device {APPLICATION_TUN2SOCKS_DEVICE_NAME!r}',
            continuation,
            ConnectionStartStage.WaitingTUNDevice,
            'TUN device did not become ready',
        )

    def _observeCondition(
        self, predicate, description, continuation, stage, failureMessage
    ):
        """Observe an owned worker or device without inventing device readiness."""
        if not self._isCurrent():
            return

        self._setStage(stage)

        if not self._isCurrent():
            return

        self._conditionContinuation = continuation
        self._conditionFailureMessage = failureMessage

        probe = _ConditionProbe(
            predicate,
            description,
            parent=self,
        )

        self._conditionProbe = probe

        connectWeakly(probe.finished, self, '_tunDeviceObserved')

        probe.start()

    def _tunDeviceObserved(self, success):
        """Resume after one device observation reaches terminal."""
        if not self._isCurrent() or self._conditionProbe is None:
            return

        probe = self._conditionProbe
        continuation = self._conditionContinuation

        self._conditionProbe = None
        self._conditionContinuation = ''

        probe.deleteLater()

        if not success:
            self._fail('', self._conditionFailureMessage)

            return

        self._resume(continuation)

    def _applyWindowsTun(self):
        """Apply Windows DNS, gateway, and route mutations after readiness."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.ApplyingHostNetwork)

        settings = self.attempt.tun2socksSettingsCallers
        userInterfaceName = settings.userPrimaryAdapterInterfaceName()
        alias = (
            userInterfaceName
            if userInterfaceName
            else SystemRoutingTable.WIN32GetInterfaceAliasByIP(self._interface)
        )

        if alias:

            def _windowsCleanup(_alias):
                SystemRoutingTable.WIN32SetInterfaceDNS(_alias)
                SystemRoutingTable.WIN32FlushDNSCache()

            self._tun.cleanup = functools.partial(_windowsCleanup, alias)

            if settings.userDisablePrimaryAdapterInterfaceDNS() != 'False':
                SystemRoutingTable.WIN32SetInterfaceDNS(
                    alias,
                    '127.0.0.1',
                    False,
                )

        interfaceDNS = (
            settings.userTunAdapterInterfaceDNS()
            or APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
        )

        SystemRoutingTable.addRelations()
        SystemRoutingTable.WIN32SetInterfaceDNS(
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            interfaceDNS,
            False,
        )
        SystemRoutingTable.setDeviceGateway(
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            APPLICATION_TUN2SOCKS_IP_ADDRESS,
            APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
        )
        SystemRoutingTable.WIN32FlushDNSCache()

        self._commit()

    def _applyDarwinTun(self):
        """Apply macOS DNS, gateway, and route mutations after startup."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.ApplyingHostNetwork)

        for address in [
            *list(f'{2 ** (8 - index)}.0.0.0/{index}' for index in range(8, 0, -1)),
            '198.18.0.0/15',
        ]:
            SystemRoutingTable.managedRoutes.append(
                [address, APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS]
            )

        servers = SystemRoutingTable.DarwinGetDNSServers()

        def _darwinCleanup(_servers):
            for service, dnsserver in _servers:
                SystemRoutingTable.DarwinSetDNSServers(service, dnsserver)

        self._tun.cleanup = functools.partial(_darwinCleanup, servers)

        interfaceDNS = (
            self.attempt.tun2socksSettingsCallers.userTunAdapterInterfaceDNS()
            or APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
        )

        for service, _dnsserver in servers:
            SystemRoutingTable.DarwinSetDNSServers(service, interfaceDNS)

        SystemRoutingTable.setDeviceGateway(
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            APPLICATION_TUN2SOCKS_IP_ADDRESS,
            APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
        )
        SystemRoutingTable.addRelations()

        self._commit()

    def _prepareLinuxTun(self):
        """Create Linux TUN and routes before starting tun2socks."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.ApplyingHostNetwork)

        def _linuxCleanup():
            SystemRoutingTable.LinuxDeleteTUNDevice(APPLICATION_TUN2SOCKS_DEVICE_NAME)

        self._tun.cleanup = _linuxCleanup

        commandBringUpTUN = ''

        if not SystemRoutingTable.LinuxFindTUNDevice(APPLICATION_TUN2SOCKS_DEVICE_NAME):
            commandBringUpTUN = (
                f'ip tuntap add mode tun dev '
                f'{APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                f'ip addr add 10.10.10.10/24 dev '
                f'{APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                f'ip link set dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} up'
            )

        commandAddDefaultRoute = (
            f'ip route add default dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} ' 'metric 5'
        )

        def route(source, destination):
            return f'{source} via {destination} dev {self._interface}'

        iproute = SystemRoutingTable.LinuxGetIpRoute()
        commandBypass = '\n'.join(
            f'ip route add {route(sourceIP, destinationIP)}'
            for sourceIP, destinationIP in SystemRoutingTable.managedRoutes
            if iproute.find(route(sourceIP, destinationIP)) == -1
        )

        tempdir = os.environ.get('TMPDIR') if SystemRuntime.flatpakID() else None

        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            suffix='.sh',
            dir=tempdir,
            delete=True,
        ) as file:
            file.write(
                '\n'.join(
                    filter(
                        bool,
                        [
                            commandBringUpTUN,
                            commandAddDefaultRoute,
                            commandBypass,
                        ],
                    )
                )
            )
            file.flush()

            if not SystemRoutingTable.LinuxExecutePrivilegedScript(
                file.name,
                shell='bash',
            ):
                self._fail('', 'failed to configure Linux TUN routes')

                return

        self._waitForTunDevice(
            functools.partial(
                SystemRoutingTable.LinuxFindTUNDevice,
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
            ),
            '_startLinuxTun',
        )

    def _startLinuxTun(self):
        """Start Linux tun2socks after the host device exists."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.StartingTUNRuntime)

        if not self._isCurrent():
            return

        try:
            self._startTUN()
        except RuntimeStartError as ex:
            self._fail(ex.message, ex.details)

            return

        self._observeRuntime(
            self._tun,
            CoreRuntimeStartup(),
            '_commit',
            ConnectionStartStage.WaitingTUNRuntime,
        )

    def _commit(self):
        """Transfer exact runtime ownership only after every stage succeeds."""
        if not self._isCurrent():
            return

        self._setStage(ConnectionStartStage.Committing)

        if not self._isCurrent():
            return

        self.attempt.commit(self.exitCallback)
        self._terminal = True

        self._publishTerminal(ConnectionStartStage.Succeeded, 'succeeded', self)

    def _publishTerminal(self, stage, signalName, *args):
        """Publish once and retire ownership across reentrant native destruction."""
        try:
            if isValid(self):
                self._setStage(stage)

            if isValid(self):
                getattr(self, signalName).emit(*args)
        finally:
            if self.manager._activeStartOperation is self:
                self.manager._finishStartOperation(self)

            if isValid(self):
                self.deleteLater()

    def _cancelObservers(self):
        """Cancel every child observer owned by this operation."""
        for attribute in ('_readinessProbe', '_conditionProbe', '_dnsOperation'):
            observer = getattr(self, attribute)

            setattr(self, attribute, None)

            if observer is not None and isValid(observer):
                observer.cancel()

        self._conditionContinuation = ''

    def _fail(self, message='', details=''):
        """Roll back and publish one terminal failure."""
        if self._terminal:
            return

        self._terminal = True

        self._cancelObservers()

        concise = str(message or '')

        if concise:
            self.manager._lastStartError = concise

        self.attempt.rollback(f'connection startup failed: {details or concise}')

        self._publishTerminal(
            ConnectionStartStage.Failed, 'failed', self, concise, str(details or '')
        )

    def cancel(self):
        """Cancel this generation and roll back only its acquired resources."""
        if self._terminal:
            return False

        self._terminal = True

        self._cancelObservers()

        self.attempt.rollback('connection startup cancelled')

        self._publishTerminal(ConnectionStartStage.Cancelled, 'cancelled', self)

        return True


class ConnectionManager(Mixins.CleanupOnExit):
    """Coordinate proxy cores, TUN setup, DNS changes, and routing cleanup."""

    def __init__(self, *args, **kwargs):
        """Initialize the connection manager."""
        self._dnsResolver = kwargs.pop('dnsResolver', None)

        super().__init__(*args, **kwargs)

        self.uniqueCleanup = False
        self._leases = list()
        self._pendingReleases = []
        self._lastStartError = ''
        self._startGeneration = 0
        self._activeStartOperation = None

    @property
    def runtimes(self):
        """Return committed runtimes without exposing the mutable owner list."""
        return [lease.runtime for lease in self._leases]

    def usesApplicationTUN(self) -> bool:
        """Return whether the committed connection owns an application TUN engine."""
        return any(lease.applicationTUN for lease in self._leases)

    def _connectionDnsResolver(self) -> DnsResolver:
        """Return the resolver owned by this connection-manager lifecycle."""
        if self._dnsResolver is None:
            # Creating QNetworkAccessManager during module import is invalid:
            # QApplication does not exist yet.  DNS is needed only for the
            # application-managed TUN path, so acquire it at that boundary.
            self._dnsResolver = DnsResolver()

        return self._dnsResolver

    @property
    def lastStartError(self) -> str:
        """Return the concise failure reported by the latest runtime start."""
        return self._lastStartError

    def _startCoreRuntime(
        self,
        config,
        routing,
        exitCallback=None,
        msgCallback=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> Tuple[Union[CoreRuntime, None], bool]:
        """Construct and start the core runtime selected for a configuration."""
        return getPluginRegistry().startCoreRuntime(
            config,
            routing,
            exitCallback=exitCallback,
            messageCallback=msgCallback,
            proxyModeOnly=proxyModeOnly,
            log=log,
            **kwargs,
        )

    @staticmethod
    def _runtimeConfiguration(config, deepcopy: bool):
        """Return the attempt-scoped configuration used for runtime preparation."""
        return config.deepcopy() if deepcopy else config

    def _prepareTUNPolicy(self, config, proxyModeOnly: bool) -> tuple[bool, bool]:
        """Prepare plugin-native TUN and decide whether tun2socks is required."""
        tunModeRequested = not proxyModeOnly and SystemRuntime.isTUNMode()

        if not tunModeRequested:
            return False, False

        registry = getPluginRegistry()
        pluginTUN = registry.prepareTUN(config)

        if pluginTUN:
            return True, False

        useAppTun2socks = registry.usesApplicationTun2socks(config)

        if useAppTun2socks:
            logger.info(
                f'application-managed TUN selected. Remote '
                f'address: {config.remoteAddress()!r}'
            )
        else:
            logger.info(
                'application-managed TUN skipped by the active '
                'core runtime configuration'
            )

        return False, useAppTun2socks

    def _startPrimaryRuntime(
        self,
        attempt: _ConnectionStartAttempt,
        routing,
        exitCallback,
        msgCallbackCore,
        proxyModeOnly,
        log,
        **kwargs,
    ) -> bool:
        """Start and track the plugin-selected primary runtime."""
        runtime, success = self._startCoreRuntime(
            attempt.runtimeConfiguration,
            routing,
            exitCallback,
            msgCallbackCore,
            proxyModeOnly,
            log,
            **kwargs,
        )

        attempt.ownRuntime(runtime)

        if success:
            return True

        self._lastStartError = 'Failed to start core'

        if isinstance(runtime, CoreRuntime):
            logger.error(f'core {runtime.name()} start failed')

        return False

    @staticmethod
    def waitForTUNDeviceBroughtUp(func: Callable[[str], bool], deviceName: str) -> bool:
        """Wait for the platform to expose the configured TUN device."""
        for counter in range(0, 10000, 100):
            if func(deviceName):
                logger.info(
                    f'find TUN device \'{deviceName}\' success. Counter: {counter}'
                )

                return True

            PySide6Legacy.eventLoopWait(100)

        logger.error(f'find TUN device \'{deviceName}\' failed')

        return False

    def start(
        self,
        config: CoreConfiguration | ServerProfile,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        """Run the legacy synchronous startup compatibility path.

        Normal GUI connections use :meth:`startAsync`. This path remains for
        third-party plugins and non-interactive callers that rely on historical
        synchronous launch semantics.
        """
        self._retryPendingReleases()

        self._lastStartError = ''

        attempt = _ConnectionStartAttempt(
            self, self._runtimeConfiguration(config, deepcopy)
        )

        try:
            return self._startAttempt(
                attempt,
                routing,
                exitCallback=exitCallback,
                msgCallbackCore=msgCallbackCore,
                msgCallbackTUN_=msgCallbackTUN_,
                proxyModeOnly=proxyModeOnly,
                log=log,
                **kwargs,
            )
        except Exception:
            # Any non-exit exceptions

            attempt.rollback('unexpected error during connection startup')

            raise

    def startAsync(
        self,
        config: CoreConfiguration | ServerProfile,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        deepcopy=True,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ):
        """Create and schedule one manager-owned startup transaction."""
        if self._activeStartOperation is not None:
            self._activeStartOperation.cancel()

        self._retryPendingReleases()

        self._lastStartError = ''
        self._startGeneration += 1

        operation = ConnectionStartOperation(
            self,
            self._startGeneration,
            config,
            routing,
            exitCallback=exitCallback,
            msgCallbackCore=msgCallbackCore,
            msgCallbackTUN_=msgCallbackTUN_,
            deepcopy=deepcopy,
            proxyModeOnly=proxyModeOnly,
            log=log,
            options=kwargs,
        )

        self._activeStartOperation = operation

        singleShotWeakly(0, operation, 'start')

        return operation

    def _finishStartOperation(self, operation):
        """Release manager ownership of one exact terminal generation."""
        if self._activeStartOperation is operation:
            self._activeStartOperation = None

    def cancelStart(self, operation=None):
        """Cancel the current startup generation when it matches *operation*."""
        current = self._activeStartOperation

        if current is None or (operation is not None and current is not operation):
            return False

        return current.cancel()

    def _startAttempt(
        self,
        attempt: _ConnectionStartAttempt,
        routing: str,
        exitCallback=None,
        msgCallbackCore=None,
        msgCallbackTUN_=None,
        proxyModeOnly=False,
        log=True,
        **kwargs,
    ) -> bool:
        """Execute the semantic stages for one prepared connection attempt."""
        configcopy = attempt.runtimeConfiguration

        def abortStart(message: str = ''):
            """Roll back only resources acquired by this startup attempt."""
            return attempt.rollback(message)

        try:
            (
                attempt.nativeTUNHandled,
                attempt.applicationTun2socks,
            ) = self._prepareTUNPolicy(configcopy, proxyModeOnly)
        except TUNPreparationError as ex:
            self._lastStartError = str(ex)

            return abortStart(f'native TUN preparation failed: {self._lastStartError}')

        tunModeRequested = not proxyModeOnly and SystemRuntime.isTUNMode()

        attempt.snapshotApplicationTUN()

        msgCallbackTUN_ = attempt.applicationTUNLogCallback(msgCallbackTUN_)

        if not self._startPrimaryRuntime(
            attempt,
            routing,
            exitCallback,
            msgCallbackCore,
            proxyModeOnly,
            log,
            **kwargs,
        ):
            return abortStart()

        if tunModeRequested and attempt.applicationTun2socks:
            startApplicationTUN = (
                self._startApplicationSingTUN
                if attempt.tunBackend == 'sing-tun'
                else self._startApplicationTun2socks
            )

            if not startApplicationTUN(attempt, exitCallback, msgCallbackTUN_):
                return False

        attempt.commit()

        return True

    @staticmethod
    def _singBypassAddresses(attempt, addresses):
        result = list(addresses)
        manual = attempt.singHostSettingsCallers.userBypassTUNAdapterInterfaceIP()

        if manual:
            result.extend(value.strip() for value in manual.split(','))

        try:
            return list(
                dict.fromkeys(str(ipaddress.ip_address(value)) for value in result)
            )
        except ValueError:
            raise ValueError('Invalid application TUN bypass IP address') from None

    @staticmethod
    def _configureTunResolver(resolver, configuration):
        # SOCKS transit carries the prepared listener's authentication policy.
        # Never require HTTP or fall back to a direct bootstrap request.
        getter = getattr(configuration, 'applicationTUNProxy', None)

        resolver.configureSocksProxy(
            getter() if callable(getter) else socksURL(configuration.socksProxy())
        )

    @staticmethod
    def _createSingTUN(attempt, exitCallback, messageCallback):
        configuration = prepareSingTUNSettings(attempt.singSettings, platform=PLATFORM)
        getter = getattr(attempt.runtimeConfiguration, 'applicationTUNProxy', None)

        configuration['proxy'] = socksURL(
            getter() if callable(getter) else attempt.runtimeConfiguration.socksProxy()
        )

        plan = SingTUNHostPlan(configuration)

        return SingTUN(
            plan.configuration,
            hostPlan=plan,
            exitCallback=exitCallback,
            msgCallback=messageCallback,
        )

    def _startApplicationSingTUN(self, attempt, exitCallback, messageCallback):
        """Compatibility startup shares configuration, bypass and host ownership."""
        try:
            runtime = self._createSingTUN(attempt, exitCallback, messageCallback)

            attempt.ownRuntime(runtime, applicationTUN=True)

            address = attempt.runtimeConfiguration.remoteAddress()

            if isValidIPAddress(address):
                addresses = [address]
            else:
                resolver = self._connectionDnsResolver()

                self._configureTunResolver(resolver, attempt.runtimeConfiguration)

                error, addresses = resolver.resolve(address)

                if error or not addresses:
                    raise ValueError('Remote bypass DNS resolution failed')

            plan = runtime._hostPlan
            plan.prepare(self._singBypassAddresses(attempt, addresses))

            runtime.start()

            deadline = time.monotonic() + 15

            while not runtime.ready:
                if (
                    runtime.startupError
                    or not runtime.isRunning()
                    or time.monotonic() >= deadline
                ):
                    raise RuntimeStartError(
                        runtime.startupError or 'sing-tun readiness timed out'
                    )

                time.sleep(0.02)

            plan.applyDNS(runtime.deviceName)

            return True
        except Exception as ex:
            # Any non-exit exceptions

            self._lastStartError = str(ex)

            return attempt.rollback('sing-tun startup failed: ' + self._lastStartError)

    def _startApplicationTun2socks(
        self,
        attempt: _ConnectionStartAttempt,
        exitCallback,
        msgCallbackTUN_,
    ) -> bool:
        """Acquire the application-managed tun2socks and host-network stage."""
        configcopy = attempt.runtimeConfiguration

        def abortStart(message: str = ""):
            return attempt.rollback(message)

        if PLATFORM == 'Windows':
            # cleanup first
            SystemRoutingTable.delete('0.0.0.0', APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS)

        # Handle user defined settings
        settings = attempt.tun2socksSettingsCallers
        userGateway, userInterfaceIP = (
            settings.userDefaultPrimaryGatewayIP(),
            settings.userPrimaryAdapterInterfaceIP(),
        )

        if userGateway and userInterfaceIP:
            logger.info(
                f'got user defined TUN settings. '
                f'\'DefaultPrimaryGatewayIP\': {userGateway}. '
                f'\'PrimaryAdapterInterfaceIP\': {userInterfaceIP}'
            )

            gateway, interface = userGateway, userInterfaceIP
        else:
            logger.info(
                f'automatically fetching TUN settings: '
                f'\'DefaultPrimaryGatewayIP\' and \'PrimaryAdapterInterfaceIP\''
            )

            defaultGateway = SystemRoutingTable.getDefaultGateway()

            if PLATFORM == 'Darwin':
                # Need this?
                defaultGateway = list(
                    # Filter TUN Gateway
                    filter(
                        lambda x: x != APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
                        defaultGateway,
                    )
                )

            if len(defaultGateway) != 1:
                return abortStart(f'bad default gateway: {defaultGateway}')

            if PLATFORM == 'Windows' or PLATFORM == 'Linux':
                # On Linux the 'interface' is a name
                gateway, interface = defaultGateway[0]
            elif PLATFORM == 'Darwin':
                gateway, interface = defaultGateway[0], None
            else:
                return abortStart(f'unrecognized platform: {PLATFORM}')

        tcpSendBufferSize, tcpReceiveBufferSize, tcpAutoTuning = (
            settings.userTcpSendBufferSize(),
            settings.userTcpReceiveBufferSize(),
            settings.userTcpAutoTuning(),
        )

        if tcpSendBufferSize != 1:
            logger.info(
                f'got user defined TUN settings. TcpSendBufferSize: {tcpSendBufferSize}'
            )

        if tcpReceiveBufferSize != 1:
            logger.info(
                f'got user defined TUN settings. TCPReceiveBufferSize: {tcpReceiveBufferSize}'
            )

        if tcpAutoTuning == 'False':
            tcpAutoTuning = False
        elif tcpAutoTuning == 'True':
            tcpAutoTuning = True

            logger.info(
                f'got user defined TUN settings. TcpAutoTuning: {tcpAutoTuning}'
            )
        else:
            tcpAutoTuning = False

        if PLATFORM != 'Linux':
            interfaceArg = APPLICATION_TUN2SOCKS_NETWORK_INTERFACE_NAME
        else:
            interfaceArg = interface

        tun = Tun2socks(
            APPLICATION_TUN2SOCKS_DEVICE_NAME,
            interfaceArg,
            'error',
            f'socks5://{configcopy.socksProxy()}',
            '',
            f'{tcpSendBufferSize}MB',
            f'{tcpReceiveBufferSize}MB',
            tcpAutoTuning,
            exitCallback=exitCallback,
            msgCallback=msgCallbackTUN_,
        )

        attempt.ownRuntime(tun, applicationTUN=True)

        startTUN = tun.start

        if PLATFORM != 'Linux':
            # Windows & macOS: bring up TUN first
            try:
                startTUN()
            except RuntimeStartError:
                return abortStart(f'core {Tun2socks.name()} start failed')

        # Handle user defined settings
        bypassTUN = settings.userBypassTUNAdapterInterfaceIP()

        if bypassTUN:
            try:
                bypassSplit = bypassTUN.split(',')
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'error when processing user TUN bypass settings: {ex}')

                SystemRoutingTable.managedRoutes.clear()

                return abortStart()
            else:
                for bypass in bypassSplit:
                    bypass = bypass.strip()

                    if isValidIPAddress(bypass):
                        logger.info(f'processing user TUN bypass IP: {bypass}')

                        SystemRoutingTable.managedRoutes.append([bypass, gateway])
                    else:
                        logger.error(
                            f'invalid IP address when processing '
                            f'user TUN bypass settings: {bypass}'
                        )

                        SystemRoutingTable.managedRoutes.clear()

                        return abortStart()
        else:
            logger.info(
                f'automatically fetching TUN settings: '
                f'\'BypassTUNAdapterInterfaceIP\''
            )

            address = configcopy.remoteAddress()

            if not isValidIPAddress(address):
                dnsResolver = self._connectionDnsResolver()
                dnsResolver.configureHttpProxy(configcopy.httpProxy())

                error, resolved = dnsResolver.resolve(address)

                if error:
                    SystemRoutingTable.managedRoutes.clear()

                    return abortStart(f'DNS resolution failed: {address}')
                else:
                    for address in resolved:
                        SystemRoutingTable.managedRoutes.append([address, gateway])
            else:
                SystemRoutingTable.managedRoutes.append([address, gateway])

        # Platform specific implementation
        if PLATFORM == 'Windows':
            if not self.waitForTUNDeviceBroughtUp(
                SystemRoutingTable.WIN32IpconfigFindContent,
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
            ):
                return abortStart()

            # Handle user defined settings
            userInterfaceName = settings.userPrimaryAdapterInterfaceName()

            if userInterfaceName:
                logger.info(
                    f'got user defined TUN settings. '
                    f'\'PrimaryAdapterInterfaceName\': {userInterfaceName}'
                )

                alias = userInterfaceName
            else:
                logger.info(
                    f'automatically fetching TUN settings: '
                    f'\'PrimaryAdapterInterfaceName\''
                )

                alias = SystemRoutingTable.WIN32GetInterfaceAliasByIP(interface)

            if alias:

                def _windowsCleanup(_alias):
                    """Handle windows cleanup for the core manager."""
                    SystemRoutingTable.WIN32SetInterfaceDNS(_alias)
                    SystemRoutingTable.WIN32FlushDNSCache()

                tun.cleanup = functools.partial(_windowsCleanup, alias)

                # Handle user defined settings
                userDisableInterfaceDNS = (
                    settings.userDisablePrimaryAdapterInterfaceDNS()
                )

                logger.info(f'DisablePrimaryInterfaceDNS: {userDisableInterfaceDNS}')

                if userDisableInterfaceDNS != 'False':
                    SystemRoutingTable.WIN32SetInterfaceDNS(alias, '127.0.0.1', False)

            # Handle user defined settings
            userTunInterfaceDNS = settings.userTunAdapterInterfaceDNS()

            if userTunInterfaceDNS == '':
                userTunInterfaceDNS = APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
            else:
                logger.info(
                    f'got user defined TUN settings. '
                    f'TunAdapterInterfaceDNS: {userTunInterfaceDNS}'
                )

            SystemRoutingTable.addRelations()
            SystemRoutingTable.WIN32SetInterfaceDNS(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                userTunInterfaceDNS,
                False,
            )
            SystemRoutingTable.setDeviceGateway(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                APPLICATION_TUN2SOCKS_IP_ADDRESS,
                APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
            )
            SystemRoutingTable.WIN32FlushDNSCache()

        # Platform specific implementation
        if PLATFORM == 'Darwin':
            for address in [
                *list(f'{2 ** (8 - x)}.0.0.0/{x}' for x in range(8, 0, -1)),
                '198.18.0.0/15',
            ]:
                SystemRoutingTable.managedRoutes.append(
                    [address, APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS]
                )

            servers = SystemRoutingTable.DarwinGetDNSServers()

            def _darwinCleanup(_servers):
                """Handle darwin cleanup for the core manager."""
                for _service, _dnsserver in _servers:
                    SystemRoutingTable.DarwinSetDNSServers(_service, _dnsserver)

            tun.cleanup = functools.partial(_darwinCleanup, servers)

            # Handle user defined settings
            userTunInterfaceDNS = settings.userTunAdapterInterfaceDNS()

            if userTunInterfaceDNS == '':
                userTunInterfaceDNS = APPLICATION_TUN2SOCKS_INTERFACE_DNS_ADDRESS
            else:
                logger.info(
                    f'got user defined TUN settings. '
                    f'TunAdapterInterfaceDNS: {userTunInterfaceDNS}'
                )

            for service, dnsserver in servers:
                SystemRoutingTable.DarwinSetDNSServers(
                    service,
                    userTunInterfaceDNS,
                )

            SystemRoutingTable.setDeviceGateway(
                APPLICATION_TUN2SOCKS_DEVICE_NAME,
                APPLICATION_TUN2SOCKS_IP_ADDRESS,
                APPLICATION_TUN2SOCKS_GATEWAY_ADDRESS,
            )
            SystemRoutingTable.addRelations()

        # Platform specific implementation
        if PLATFORM == 'Linux':

            def _linuxCleanup():
                """Handle linux cleanup for the core manager."""
                SystemRoutingTable.LinuxDeleteTUNDevice(
                    APPLICATION_TUN2SOCKS_DEVICE_NAME
                )

            tun.cleanup = functools.partial(_linuxCleanup)

            if SystemRoutingTable.LinuxFindTUNDevice(APPLICATION_TUN2SOCKS_DEVICE_NAME):
                logger.info(
                    f'find TUN device {APPLICATION_TUN2SOCKS_DEVICE_NAME} success. '
                    f'Will not try to bring up TUN device again'
                )

                commandBringUpTUN = ''
            else:
                logger.info(
                    f'find TUN device {APPLICATION_TUN2SOCKS_DEVICE_NAME} failed. '
                    f'Will try to bring up TUN device'
                )

                commandBringUpTUN = (
                    f'ip tuntap add mode tun dev {APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                    f'ip addr add 10.10.10.10/24 dev {APPLICATION_TUN2SOCKS_DEVICE_NAME}\n'
                    f'ip link set dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} up'
                )

            commandAddDefaultRoute = (
                f'ip route add default dev {APPLICATION_TUN2SOCKS_DEVICE_NAME} '
                'metric 5'
            )

            def route(source, destination) -> str:
                """Configure platform routing for the active proxy connection."""
                return f'{source} via {destination} dev {interface}'

            iproute = SystemRoutingTable.LinuxGetIpRoute()

            commandBypass = '\n'.join(
                list(
                    f'ip route add {route(sourceIP, destinationIP)}'
                    for sourceIP, destinationIP in SystemRoutingTable.managedRoutes
                    if iproute.find(route(sourceIP, destinationIP)) == -1
                )
            )

            if SystemRuntime.flatpakID():
                tempdir = os.environ.get('TMPDIR')
            else:
                tempdir = None

            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.sh', dir=tempdir, delete=True
            ) as file:
                content = '\n'.join(
                    filter(
                        lambda x: x != '',
                        [commandBringUpTUN, commandAddDefaultRoute, commandBypass],
                    )
                )

                file.write(content)
                file.flush()

                if not SystemRoutingTable.LinuxExecutePrivilegedScript(
                    file.name, shell='bash'
                ):
                    return abortStart()

                if not self.waitForTUNDeviceBroughtUp(
                    SystemRoutingTable.LinuxFindTUNDevice,
                    APPLICATION_TUN2SOCKS_DEVICE_NAME,
                ):
                    return abortStart()

            # Now bring up TUN
            try:
                startTUN()
            except RuntimeStartError:
                return abortStart(f'core {Tun2socks.name()} start failed')

        return True

    def allRunning(self) -> bool:
        """Return whether every managed core runtime is running."""
        return all(runtime.isRunning() for runtime in self.runtimes)

    def anyRunning(self) -> bool:
        """Return whether any managed core runtime is running."""
        return any(runtime.isRunning() for runtime in self.runtimes)

    def _releaseRuntime(self, runtime):
        """Stop, dispose, and forget one exact runtime owned by this manager."""
        lease = next(
            (lease for lease in self._leases if lease.runtime is runtime),
            None,
        )

        if lease is None:
            return

        if not lease.release():
            self._pendingReleases.append(lease)

        self._leases.remove(lease)

    def stopAll(self):
        """Stop every managed proxy-core and TUN runtime."""
        self.cancelStart()

        self._pendingReleases.extend(reversed(self._leases))
        self._leases.clear()

        self._retryPendingReleases()

    def _retryPendingReleases(self):
        """Keep exact failed resources and refuse replacement until release succeeds."""
        self._pendingReleases[:] = [
            lease for lease in self._pendingReleases if not lease.release()
        ]

        if self._pendingReleases:
            raise RuntimeError('Connection runtime cleanup is incomplete')

    def cleanup(self):
        """Release resources owned by the core manager."""
        try:
            self.stopAll()
        finally:
            # A failed runtime release must not strand independent DNS replies.
            if self._dnsResolver is not None:
                dispose = getattr(self._dnsResolver, 'dispose', None)

                if callable(dispose):
                    dispose()

                self._dnsResolver = None
