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

"""Exercise server-table editor ownership in source or compiled form."""

from __future__ import annotations

from Furious.Backends import OFFICIAL_PLUGIN_TYPES
from Furious.Backends.Xray.RoutingWindow import RoutingRulesDialog
from Furious.Backends.Xray.AssetListView import XrayAssetListView
import Furious.Backends.Xray.AssetListView as assetModule
import Furious.Actions.Import as importModule
from Furious.Actions.Routing import RoutingAction
from Furious.Actions.Connection import ConnectionErrorMessageBox
from Furious.Application.TrayIcon import TrayIcon
from Furious.Application.DesktopApplication import DesktopApplication
from Furious.Controllers import ConnectionController, RoutingController
from Furious.Controllers.ConnectionController import ConnectionError
from Furious.Plugins import RoutingOption
from Furious.Plugins import blankProfile, initializePluginRegistry
from Furious.Qt import (
    AppQAction,
    AppQMenu,
    AppQMenuPushButton,
    AppQDialog,
    AppQMessageBox,
    AppQMainWindow,
    ThemeTransition,
    connectWeakly,
)
from Furious.Qt.HttpGetManager import HttpGetManager
from Furious.Service.EndpointInfoService import (
    EndpointInfoService,
    EndpointInfoState,
    ProxyEndpointHttpClient,
)
from Furious.Service.SubscriptionManager import SubscriptionManager
from Furious.Service.ProfileTesting import _LatencyScheduler
from Furious.Service.DnsResolver import DnsResolutionOperation, DnsResolver
from Furious.Service.TrafficStatsManager import TrafficStatsManager
from Furious.Frozenlib import Mixins
from Furious.Plugins import TrafficCounters
from Furious.Service.ConnectionManager import (
    ConnectionManager,
    ConnectionStartOperation,
)
from Furious.Models import CoreConfiguration
from Furious.Controllers.SettingsController import SettingsController
from Furious.Repository import Storage
from Furious.Window.SettingsPage import _TUNBackendSettingsCard
from Furious.Widget.ServerTableView import ServerTableView

import PySide6

from PySide6 import QtCore
from PySide6.QtNetwork import QLocalSocket, QNetworkReply
from PySide6.QtWidgets import QPushButton, QWidget

from shiboken6 import isValid, delete as deleteQObject

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    waitFor,
)

from collections import Counter
from types import SimpleNamespace
from unittest import mock

import argparse
import json
import sys
import weakref
from pathlib import Path
import tempfile

PROTOCOL_PATTERNS = {
    'alternating': ('hysteria2', 'vless'),
    'reverse': ('vless', 'hysteria2'),
    'hysteria2': ('hysteria2',),
    'vless': ('vless',),
    'representative': (
        'hysteria2',
        'vless',
        'vmess',
        'trojan',
        'socks',
        'hysteria1',
        'external-core',
    ),
}
CLOSE_METHODS = ('accept', 'close', 'reject')


def runNotificationAndDnsProbe(iterations=100):
    """Exercise native destruction during pool, DNS, and statistics callbacks."""
    application()

    cases = (
        (Mixins.ConnectionAware, 'callConnectedCallback', ()),
        (Mixins.ConnectionAware, 'callDisconnectedCallback', ()),
        (Mixins.ThemeAware, 'callThemeChangedCallbackUnchecked', ('Dark',)),
        (Mixins.QTranslatable, 'retranslateAll', ()),
        (Mixins.CleanupOnExit, 'cleanupAll', ()),
    )
    poolNotifications = 0

    for mixin, methodName, arguments in cases:

        class Participant(mixin, QtCore.QObject):
            def __init__(self, name):
                kwargs = (
                    {'uniqueCleanup': False} if mixin is Mixins.CleanupOnExit else {}
                )
                super().__init__(**kwargs)

                self.setObjectName(name)
                self.victim = None

            def notify(self, *_args):
                calls.append(self.objectName())

                if self.victim is not None:
                    deleteQObject(self.victim)

            connectedCallback = notify
            disconnectedCallback = notify
            themeChangedCallback = notify
            retranslate = notify
            cleanup = notify

        for _ in range(iterations):
            calls = []
            pool = type(mixin.ObjectsPool)()

            with mock.patch.object(mixin, 'ObjectsPool', pool):
                first, victim, last = (
                    Participant('first'),
                    Participant('victim'),
                    Participant('last'),
                )
                first.victim = victim

                getattr(mixin, methodName)(*arguments)

                assert calls == ['first', 'last']
                assert not isValid(victim)

                deleteQObject(first)
                deleteQObject(last)

                assert not len(pool)

            poolNotifications += 1

    class PendingReply(QNetworkReply):
        def abort(self):
            self.setFinished(True)

            self.finished.emit()

        def readData(self, _maximumLength):
            return bytes()

    for boundary in ('cancel-start', 'destroy-start', 'destroy-timeout'):
        for _ in range(iterations):
            resolver = SimpleNamespace(_newResultMap=DnsResolver._newResultMap)
            operation = DnsResolutionOperation(resolver, 'example.test')
            results = []

            operation.finished.connect(lambda *_args: results.append(True))

            def beginResolve(resultMap):
                resultMap['depth'] = 1

                if boundary == 'cancel-start':
                    operation.cancel()
                elif boundary == 'destroy-start':
                    deleteQObject(operation)

            resolver._beginResolve = beginResolve

            operation.start()

            if boundary == 'cancel-start':
                assert not operation._timer.isActive()
                deleteQObject(operation)
            elif boundary == 'destroy-timeout':
                reply = PendingReply()
                operation._resultMap['reference'].append(reply)
                reply.finished.connect(lambda: deleteQObject(operation))
                operation._timeout = 0

                operation._poll()

                assert reply.isFinished()

                deleteQObject(reply)

            assert not results
            assert not isValid(operation)
            assert not isValid(operation._timer)

    # These managers are process-lifetime receivers in the application. Probe
    # each emission boundary once, rather than treating their persistent direct
    # slots as transient callback-retention candidates.
    for signalName in ('usageHistoryReset', 'usageChanged', 'speedChanged'):
        manager = TrafficStatsManager()

        with mock.patch.object(
            manager, '_clearUsageOnReconnectEnabled', return_value=True
        ):
            manager._consumeResult(manager._generation, TrafficCounters(100, 100), 1.0)

            getattr(manager, signalName).connect(lambda *_args: deleteQObject(manager))

            manager._sampleReady.emit(manager._generation, TrafficCounters(10, 10), 2.0)

        assert not isValid(manager)
        assert not isValid(manager._sampleTimer)

    class EndpointClient(QtCore.QObject):
        completed = QtCore.Signal(object, object, str)

        def __init__(self):
            super().__init__()

            self.requests = []

        def configureHttpProxy(self, _proxy):
            return True

        def cancelAll(self):
            pass

        def request(self, url, context):
            self.requests.append((url, context))

    for boundary in ('loading', 'refresh-result', 'ip-result'):
        for action in ('destroy', 'disable'):
            client = EndpointClient()
            service = EndpointInfoService(
                controller=SimpleNamespace(isConnected=lambda: True),
                httpClient=client,
                proxyResolver=lambda: '127.0.0.1:10809',
                enabled=True,
            )

            if boundary == 'ip-result':
                service.setPageVisible(True)
            else:
                service._setState(EndpointInfoState.Ready)

            requestCount = len(client.requests)
            interrupted = []

            def interruptLookup(*_args):
                if interrupted:
                    return

                interrupted.append(True)

                if action == 'destroy':
                    deleteQObject(service)
                else:
                    service.setEnabled(False)

            signal = (
                service.stateChanged if boundary == 'loading' else service.resultChanged
            )
            signal.connect(interruptLookup)

            if boundary == 'ip-result':
                client.completed.emit(
                    client.requests[-1][1], b'ip=192.0.2.10\nloc=US\n', ''
                )
            else:
                service.refresh()

            assert interrupted == [True]
            assert len(client.requests) == requestCount

            if isValid(service):
                assert service.state is EndpointInfoState.Disabled
                assert not service._requestInFlight

                deleteQObject(service)

            deleteQObject(client)

    processQtEvents()

    return {
        'poolNotificationCycles': poolNotifications,
        'dnsReentrantCycles': iterations * 3,
        'statsDestructionBoundaries': 3,
        'endpointInterruptionBoundaries': 6,
    }


def runConnectionRecoveryProbe(iterations=100):
    """Check compiled diagnostic-button dispatch and transient destruction."""
    app = application()
    hadWindow = hasattr(app, 'mainWindow')
    previousWindow = getattr(app, 'mainWindow', None)
    previousClipboard = app.clipboard().text()

    window = AppQMainWindow()
    logPageOpens = []
    window.showLogPage = lambda: logPageOpens.append(True)
    app.mainWindow = window

    references = []
    destroyed = []
    protectedMethods = getattr(
        sys.modules.get('PySide6-postLoad', PySide6), '_protected', None
    )
    protectedBefore = len(protectedMethods) if protectedMethods is not None else None

    try:
        for _ in range(iterations):
            box = ConnectionErrorMessageBox(
                ConnectionError('Unable to connect', 'Fixture failure', 'Native detail')
            )
            references.append(weakref.ref(box))
            box.destroyed.connect(lambda *_args: destroyed.append(True))

            box.open()
            processQtEvents()

            box.copyErrorButton.click()
            assert box.isVisible()
            assert (
                app.clipboard().text()
                == 'Unable to connect\n\nFixture failure\n\nNative detail'
            )

            box.openLogsButton.click()
            processQtEvents()

            assert not isValid(box)
            del box

        assert len(logPageOpens) == iterations
        assert len(destroyed) == iterations
        assert all(reference() is None for reference in references)
        assert not AppQDialog._openDialogs

        growth = (
            len(protectedMethods) - protectedBefore
            if protectedBefore is not None
            else None
        )

        assert growth in (None, 0), growth

        return {
            'connectionRecoveryDialogs': iterations,
            'protectedMethodGrowth': growth,
        }
    finally:
        app.clipboard().setText(previousClipboard)

        if hadWindow:
            app.mainWindow = previousWindow
        else:
            del app.mainWindow

        deleteQObject(window)
        processQtEvents()


class _ReentrantAction(AppQAction):
    """Make stale activation visible as a forbidden native operation."""

    def triggeredCallback(self, checked):
        self.setChecked(checked)
        self.hookCalls += 1


def runReentrantLifetimeProbe(iterations=100):
    """Exercise callback deletion and borrowed menu retirement under compilation."""
    application()

    references = []
    protectedMethods = getattr(
        sys.modules.get('PySide6-postLoad', PySide6), '_protected', None
    )
    protectedBefore = len(protectedMethods) if protectedMethods is not None else None

    for _ in range(iterations):
        owner = QtCore.QObject()
        action = _ReentrantAction('Callback', parent=owner)
        action.hookCalls = 0
        action.callback = lambda: deleteQObject(owner)
        references.append(weakref.ref(action))

        action.trigger()

        assert not isValid(action) and action.hookCalls == 0

        del action, owner

        owner = QWidget()
        menu = AppQMenu(parent=owner)
        action = AppQAction('Borrower', menu=menu)
        button = AppQMenuPushButton('Popup', popupMenu=menu)
        references.append(weakref.ref(menu))

        deleteQObject(owner)

        assert action._menu is None and button.popupMenu() is None
        assert not button._popupMenuConnections

        del menu

        button.showPopupMenu()

        deleteQObject(action)
        deleteQObject(button)

        menu = AppQMenu()
        reference = weakref.ref(menu)
        button = AppQMenuPushButton('Release', popupMenu=menu)

        del menu
        deleteQObject(button)

        assert button.popupMenu() is None and reference() is None

    owner = QWidget()
    menus = [AppQMenu(parent=owner), AppQMenu(parent=owner)]
    button = AppQMenuPushButton('Replace')

    signal = QtCore.SIGNAL('destroyed(QObject*)')
    counts = [menu.receivers(signal) for menu in menus]
    buttonCount = button.receivers(signal)

    for index in range(iterations):
        active = index % 2

        button.setPopupMenu(menus[active])

        assert button.receivers(signal) == buttonCount + 1
        assert all(
            menu.receivers(signal) == counts[number] + (2 if number == active else 0)
            for number, menu in enumerate(menus)
        )

    deleteQObject(button)

    assert all(
        menu.receivers(signal) == counts[number] for number, menu in enumerate(menus)
    )

    deleteQObject(owner)

    for boundary in ('theme', 'started', 'finished'):
        for _ in range(iterations):
            window = QWidget()
            window.resize(160, 100)
            window.show()
            processQtEvents()

            transition = ThemeTransition(
                duration=100000,
                windowProvider=lambda: (window,),
                animationsEnabled=lambda: True,
            )
            references.append(weakref.ref(transition))

            if boundary == 'theme':
                transition.apply(lambda: deleteQObject(transition))
            elif boundary == 'started':
                transition.transitionStarted.connect(lambda: deleteQObject(transition))

                transition.apply(lambda: None)
            else:
                transition.apply(lambda: None)
                transition.transitionFinished.connect(lambda: deleteQObject(transition))

                window.resize(170, 110)

            processQtEvents()

            assert not isValid(transition)
            assert not transition._animations and not transition._animationsByWindow
            assert not window.findChildren(QWidget, ThemeTransition.OverlayObjectName)

            del transition
            deleteQObject(window)

    with isolatedSettings():
        for method, signalName in (
            ('cancel', 'cancelled'),
            ('_fail', 'failed'),
            ('_commit', 'succeeded'),
        ):
            for _ in range(iterations):
                manager = SimpleNamespace(
                    _runtimeConfiguration=lambda config, copied: config,
                    _leases=[],
                    _pendingReleases=[],
                    _startGeneration=1,
                    _activeStartOperation=None,
                )
                manager._finishStartOperation = (
                    lambda operation: ConnectionManager._finishStartOperation(
                        manager, operation
                    )
                )

                owner = QtCore.QObject()
                operation = ConnectionStartOperation(
                    manager, 1, CoreConfiguration({}), '', parent=owner
                )
                manager._activeStartOperation = operation
                references.append(weakref.ref(operation))

                getattr(operation, signalName).connect(
                    lambda *_args: deleteQObject(owner)
                )

                getattr(operation, method)()

                assert not isValid(operation) and manager._activeStartOperation is None

                del operation, owner

    assert all(reference() is None for reference in references)

    growth = (
        len(protectedMethods) - protectedBefore if protectedBefore is not None else None
    )

    assert growth in (None, 0), growth

    return {
        'reentrantActions': iterations,
        'borrowedMenus': iterations,
        'menuReplacements': iterations,
        'reentrantTransitions': iterations * 3,
        'reentrantStartOperations': iterations * 3,
        'protectedMethodGrowth': growth,
    }


class _SingletonReceiver(QtCore.QObject):
    """Exercise the real IPC methods without application startup or endpoints."""

    handleNewData = DesktopApplication.handleNewData

    def __init__(self):
        super().__init__()

        self.pending = []
        self.systemTray = None
        self.server = SimpleNamespace(
            hasPendingConnections=lambda _pending=self.pending: bool(_pending),
            nextPendingConnection=lambda _pending=self.pending: _pending.pop(0),
        )


def runSingletonIPCProbe(iterations: int = 100) -> dict[str, object]:
    """Destroy completed IPC sockets and bound compiled callback growth."""
    application()

    protectedMethods = getattr(
        sys.modules.get('PySide6-postLoad', PySide6), '_protected', None
    )
    directGrowth = None

    if protectedMethods is not None:
        # Positive control: native sender destruction does not retire this
        # toolchain's protected compiled bound method. Keep the diagnostic bounded.
        control = _SingletonReceiver()
        socket = QLocalSocket(control)
        before = len(protectedMethods)

        socket.readyRead.connect(control.handleNewData)
        deleteQObject(control)

        directGrowth = len(protectedMethods) - before
        assert directGrowth == 1, directGrowth

        del socket, control

    receiver = _SingletonReceiver()
    receiverReference = weakref.ref(receiver)
    before = len(protectedMethods) if protectedMethods is not None else None
    references = []
    destroyed = []

    for _ in range(iterations):
        socket = QLocalSocket(receiver)
        references.append(weakref.ref(socket))
        socket.destroyed.connect(lambda *_args: destroyed.append(True))
        receiver.pending.append(socket)

        # Bypass the launch rate limit, preserving the actual connection logic.
        DesktopApplication.handleNewConnection.__wrapped__(receiver)
        socket.readyRead.emit()
        processQtEvents()

        assert not isValid(socket)
        del socket

    growth = len(protectedMethods) - before if before is not None else None

    assert growth in (None, 0), growth
    assert len(destroyed) == iterations
    assert all(reference() is None for reference in references)

    deleteQObject(receiver)
    del receiver

    assert receiverReference() is None

    return {
        'singletonSocketsDestroyed': len(destroyed),
        'singletonProtectedMethodGrowth': growth,
        'directConnectionControlGrowth': directGrowth,
    }


def runProbe(
    iterations: int = 100,
    *,
    pattern: str = 'alternating',
    closeMethod: str = 'reject',
) -> dict[str, object]:
    """Open real server-table editors and prove deterministic destruction."""
    application()

    if pattern not in PROTOCOL_PATTERNS:
        raise ValueError(f'unsupported editor pattern: {pattern!r}')

    if closeMethod not in CLOSE_METHODS:
        raise ValueError(f'unsupported close method: {closeMethod!r}')

    protocols = PROTOCOL_PATTERNS[pattern]
    references = []
    destroyed = []
    finishedBeforeDestroyed = []
    operationContextsReleased = []
    invalidWrappersAfterClose = 0
    protocolCounts = Counter()

    with isolatedSettings():
        registry = initializePluginRegistry(OFFICIAL_PLUGIN_TYPES)
        table = ServerTableView(
            configurationEditorFactory=QWidget,
            qrCodeWindowFactory=QWidget,
            importActionsFactory=tuple,
        )

        # Nuitka 4.2.1 keeps this private list in its synthetic post-load module.
        # Other toolchains may expose it on PySide6 or not expose it at all.
        protectedMethods = getattr(
            sys.modules.get('PySide6-postLoad', PySide6), '_protected', None
        )
        protectedMethodsBefore = (
            len(protectedMethods) if isinstance(protectedMethods, list) else None
        )

        try:
            for index in range(iterations):
                protocol = protocols[index % len(protocols)]
                protocolCounts[protocol] += 1

                profile = blankProfile(protocol, registry=registry)
                editor = table.getGuiEditorByFactory(profile, translatable=False)

                if editor is None:
                    raise RuntimeError(f'no editor is registered for {protocol!r}')

                editor.factoryToInput(profile)

                key = editor._lifetimeKey
                reference = weakref.ref(editor)

                editor._modContext = (index, profile)

                connectWeakly(
                    editor.accepted,
                    table,
                    'handleGuiEditorAccepted',
                    sender=editor,
                    forwardSender=True,
                )
                connectWeakly(
                    editor.rejected,
                    table,
                    'handleGuiEditorRejected',
                    sender=editor,
                    forwardSender=True,
                )

                editor.finished.connect(
                    lambda _result, _key=key: finishedBeforeDestroyed.append(
                        _key in AppQDialog._openDialogs
                    )
                )
                editor.finished.connect(
                    lambda _result, _reference=reference: (
                        operationContextsReleased.append(
                            _reference() is not None
                            and not hasattr(_reference(), '_modContext')
                        )
                    )
                )
                editor.destroyed.connect(
                    lambda *_args, _destroyed=destroyed: _destroyed.append(True)
                )

                references.append(reference)

                editor.open()
                del editor

                processQtEvents(1)

                activeEditor = reference()

                if activeEditor is None or not isValid(activeEditor):
                    raise RuntimeError(f'{protocol} editor died while still open')

                getattr(activeEditor, closeMethod)()
                del activeEditor

                processQtEvents(2)

                if reference() is not None and not isValid(reference()):
                    invalidWrappersAfterClose += 1

            collectAtBoundary()

            result = {
                'iterations': iterations,
                'pattern': pattern,
                'closeMethod': closeMethod,
                'protocolCounts': dict(sorted(protocolCounts.items())),
                'destroyed': len(destroyed),
                'liveWrappers': sum(
                    reference() is not None for reference in references
                ),
                'openDialogs': len(AppQDialog._openDialogs),
                'registryHeldAtFinished': sum(finishedBeforeDestroyed),
                'operationContextsReleased': sum(operationContextsReleased),
                'invalidWrappersAfterClose': invalidWrappersAfterClose,
                'nuitkaProtectedGrowth': (
                    len(protectedMethods) - protectedMethodsBefore
                    if protectedMethodsBefore is not None
                    else None
                ),
            }

            expectedCounts = Counter(
                protocols[index % len(protocols)] for index in range(iterations)
            )

            expected = {
                'iterations': iterations,
                'pattern': pattern,
                'closeMethod': closeMethod,
                'protocolCounts': dict(sorted(expectedCounts.items())),
                'destroyed': iterations,
                'liveWrappers': 0,
                'openDialogs': 0,
                'registryHeldAtFinished': iterations,
                'operationContextsReleased': iterations,
                'invalidWrappersAfterClose': 0,
                'nuitkaProtectedGrowth': (
                    0 if protectedMethodsBefore is not None else None
                ),
            }

            if result != expected:
                raise RuntimeError(f'editor lifetime probe failed: {result!r}')

            return result
        finally:
            table.close()
            table.deleteLater()
            processQtEvents()

            registry.shutdown()


class _SignalEndpoint(QtCore.QObject):
    """Exercise compiled methods with independently destroyed Qt endpoints."""

    emitted = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.calls = 0

    def record(self):
        self.calls += 1


class _PendingReply(QNetworkReply):
    """Exercise request destruction without external network traffic."""

    def __init__(self, parent):
        super().__init__(parent)
        self.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)

    def abort(self):
        self.setFinished(True)
        self.finished.emit()

    def readData(self, maximumLength):
        return b''


class _RequestPayload:
    """Expose whether pending request context still owns plain operation data."""


def runNetworkProbe(iterations=100):
    """Verify native teardown releases both reply registries under compilation."""
    application()

    result = {}

    for managerType, contextAttribute in (
        (HttpGetManager, '_replyContexts'),
        (ProxyEndpointHttpClient, '_pendingRequests'),
    ):
        for terminal in (
            'finished',
            'replyDestroyed',
            'managerDestroyed',
            'callbackReplyDestroyed',
            'callbackManagerDestroyed',
        ):
            references = []
            destroyed = []

            for _ in range(iterations):
                manager = managerType()
                payload = _RequestPayload()
                reply = _PendingReply(manager)

                references.extend((weakref.ref(payload), weakref.ref(reply)))
                reply.destroyed.connect(lambda *_args: destroyed.append(True))

                manager.get = lambda _request: reply

                if isinstance(manager, HttpGetManager):
                    manager.webGET('https://invalid.test', payload=payload)
                else:
                    manager.request('https://invalid.test', payload)

                del manager.get
                del payload

                if terminal.startswith('callback'):

                    def destroyFromCallback(*_args, **_kwargs):
                        deleteQObject(
                            manager if terminal == 'callbackManagerDestroyed' else reply
                        )

                    if isinstance(manager, HttpGetManager):
                        manager.successCallback = destroyFromCallback
                    else:
                        manager.completed.connect(destroyFromCallback)

                    reply.finished.emit()
                elif terminal == 'finished':
                    reply.finished.emit()
                elif terminal == 'replyDestroyed':
                    reply.deleteLater()
                else:
                    manager.deleteLater()

                processQtEvents()

                assert not isValid(reply)
                assert not getattr(manager, contextAttribute)

                if isValid(manager):
                    manager.deleteLater()
                    processQtEvents()

                del reply, manager

            assert len(destroyed) == iterations
            assert all(reference() is None for reference in references)

            result[managerType.__name__ + ':' + terminal] = iterations

    return result


def runSettingsAndSubscriptionProbe(iterations=100):
    """Verify independent controller edges and early subscription reply deletion."""
    app = application()
    previousController = app.settingsController
    controller = SettingsController()
    app.settingsController = controller

    references = []
    signal = QtCore.SIGNAL('tunBackendChanged(QString)')
    baseline = controller.receivers(signal)

    subsGetter = Storage.UserSubs
    Storage.UserSubs = staticmethod(dict)
    manager = SubscriptionManager()

    try:
        with isolatedSettings():
            for index in range(iterations):
                card = _TUNBackendSettingsCard()
                references.append(weakref.ref(card))

                controller.tunBackendChanged.emit('tun2socks')

                assert card.comboBox.currentData() == 'tun2socks'
                assert controller.receivers(signal) == baseline + 1

                deleteQObject(card)
                del card

                assert controller.receivers(signal) == baseline

                controller.tunBackendChanged.emit('sing-tun')

                reply = _PendingReply(manager)
                references.append(weakref.ref(reply))
                manager.get = lambda _request: reply

                manager.updateSubsByWebGET(
                    webURL='https://invalid.test', unique=str(index)
                )
                del manager.get

                deleteQObject(reply)
                del reply

                assert not manager._replyContexts
                assert not manager._activeReplies
                assert not manager._replySubscriptions

                manager.cancelUpdates()

            replies = [_PendingReply(manager), _PendingReply(manager)]

            for index, reply in enumerate(replies):
                manager.get = lambda _request: reply
                manager.updateSubsByWebGET(
                    webURL='https://invalid.test', unique=str(index)
                )
                del manager.get

            replies[0].abort = lambda: deleteQObject(manager)
            manager.cancelUpdates()

            assert not isValid(manager)
            assert all(not isValid(reply) for reply in replies)
            assert not manager._activeReplies and not manager._replySubscriptions

            deleteQObject(controller)
            collectAtBoundary()

            assert all(reference() is None for reference in references)
    finally:
        app.settingsController = previousController
        Storage.UserSubs = staticmethod(subsGetter)

        if isValid(controller):
            deleteQObject(controller)

        if isValid(manager):
            manager.shutdown()
            deleteQObject(manager)

    return {'selectorCycles': iterations, 'subscriptionReplyCycles': iterations}


class _CaptureHandle:
    """Stand in for desktop capture without acquiring a host handle."""

    def __init__(self):
        self.closeCount = 0

    def close(self):
        self.closeCount += 1


def runTrayOwnershipProbe(iterations=100):
    """Prove native teardown even if compiled callbacks retain Python wrappers."""
    app = application()
    previousConnection, previousRouting = (
        app.connectionController,
        app.routingController,
    )

    captureFactory = importModule.mss.mss
    importModule.mss.mss = _CaptureHandle

    connection, routing = ConnectionController(), RoutingController()
    app.connectionController, app.routingController = connection, routing
    options = (RoutingOption('one', 'One'), RoutingOption('two', 'Two'))

    try:
        for _ in range(iterations):
            tray = TrayIcon()
            action = tray.ConnectAction
            progress = action.progressWidget
            captureAction = next(
                child
                for child in tray.ImportAction._menu._actions
                if isinstance(child, importModule.ImportQRCodeOnTheScreenAction)
            )
            capture = captureAction.sct

            progress.start(50)

            tray.RoutingAction._applyState(options, 'one')
            retired = tuple(tray.RoutingAction._menu.actions())
            tray.RoutingAction._applyState(options, 'two')
            processQtEvents()

            assert all(not isValid(child) for child in retired)

            current = tuple(tray.RoutingAction._menu.actions())
            resources = (
                tray._menu,
                action,
                tray.ImportAction,
                tray.ImportAction._menu,
                captureAction,
                progress,
                progress._widget.timer,
                *current,
            )

            deleteQObject(tray)
            processQtEvents()

            assert all(not isValid(ob) for ob in resources)
            assert capture.closeCount == 1 and captureAction.sct is None

    finally:
        app.connectionController, app.routingController = (
            previousConnection,
            previousRouting,
        )
        importModule.mss.mss = captureFactory

        connection.shutdown()
        deleteQObject(connection)
        deleteQObject(routing)

    return {'trayOwnershipCycles': iterations, 'routingRebuildCycles': iterations}


def runThreadOwnershipProbe(iterations=100):
    """Stop the native thread before Qt deletes a scheduler or its parent."""
    application()

    destroyed = []
    references = []

    for parentFirst in (False, True):
        for _ in range(iterations):
            owner = QtCore.QObject()
            scheduler = _LatencyScheduler(
                lambda target: None,
                lambda target, result: False,
                pingConcurrency=1,
                tcpingConcurrency=1,
                parent=owner,
            )

            engine = scheduler.ensureTcpingEngine()
            thread = scheduler.tcpingThread
            references.extend((weakref.ref(engine), weakref.ref(thread)))
            engine.destroyed.connect(
                lambda *_args: destroyed.append(
                    QtCore.QThread.currentThread() is thread
                ),
                QtCore.Qt.ConnectionType.DirectConnection,
            )

            assert waitFor(thread.isRunning)

            deleteQObject(owner if parentFirst else scheduler)

            assert all(not isValid(ob) for ob in (scheduler, thread, engine))

            if isValid(owner):
                deleteQObject(owner)

            del engine, thread, scheduler, owner
            processQtEvents()

    assert len(destroyed) == iterations * 2 and all(destroyed)
    assert all(reference() is None for reference in references)

    return {
        'threadOwnerFirstCycles': iterations * 2,
        'destroyedInWorkerThread': len(destroyed),
    }


def runButtonOwnershipProbe(iterations=100):
    """Exercise button detach/reuse, native removal, and owner-first callbacks."""
    application()

    references = []
    destroyed = []

    for _ in range(iterations):
        box = AppQMessageBox()
        button = QPushButton('Fixture')
        results = []
        box.finished.connect(results.append)

        for item in (box, button):
            references.append(weakref.ref(item))
            item.destroyed.connect(lambda *_args: destroyed.append(True))

        del item

        for _detach in range(3):
            box.addButton(button, box.ButtonRole.AcceptRole)
            box.setDefaultButton(button)
            box.setEscapeButton(button)

            box.removeButton(button)
            button.click()

            assert not results
            assert box.defaultButton() is None and box.escapeButton() is None
            assert button.receivers(QtCore.SIGNAL('clicked()')) == 0

        box.addButton(button, box.ButtonRole.AcceptRole)
        box.addButton(button, box.ButtonRole.AcceptRole)

        box.open()
        button.click()
        processQtEvents()

        assert results == [int(AppQDialog.DialogCode.Accepted)]
        assert not isValid(box) and not isValid(button)

        del box, button

        box = AppQMessageBox()
        button = box.addButton(box.StandardButton.Yes)
        box.setDefaultButton(button)
        box.setEscapeButton(button)

        deleteQObject(button)

        assert not box.buttons()
        assert box.defaultButton() is None and box.escapeButton() is None

        deleteQObject(box)
        del box, button

        owner = QWidget()
        box = AppQMessageBox(parent=owner)
        button = box.addButton(box.StandardButton.Yes)
        box.buttonClicked.connect(lambda *_args: deleteQObject(owner))

        button.click()

        assert not isValid(box) and not isValid(button)

        del box, button, owner

    processQtEvents()

    assert len(destroyed) == iterations * 2
    assert all(reference() is None for reference in references)
    assert not AppQDialog._openDialogs

    return {
        'buttonDetachReuse': iterations,
        'nativeButtonRemoval': iterations,
        'buttonCallbackOwnerDestruction': iterations,
        'destroyed': len(destroyed),
        'liveWrappers': 0,
    }


def runInfrastructureProbe(iterations=100):
    """Check signal, mask, and animation ownership under real Qt destruction."""
    application()

    result = {}

    for closeMethod in CLOSE_METHODS:
        destroyed = []

        for _ in range(iterations):
            dialog = AppQDialog()
            dialog.destroyed.connect(lambda *_args: destroyed.append(True))
            reference = weakref.ref(dialog)
            key = dialog._lifetimeKey

            dialog.open()
            getattr(dialog, closeMethod)()
            dialog.open()

            del dialog
            processQtEvents()

            assert reference() is not None and isValid(reference())
            assert reference().isVisible()
            assert AppQDialog._openDialogs.get(key) is reference()

            getattr(reference(), closeMethod)()
            processQtEvents()

            assert reference() is None
            assert key not in AppQDialog._openDialogs

        assert len(destroyed) == iterations

        result['reopenAfter' + closeMethod.title()] = iterations

    routingReferences = []
    routingDestroyed = []

    for _ in range(iterations):
        dialog = RoutingRulesDialog({'rules': [{'ruleTag': 'keep'}]})
        dialog.open()
        dialog.listView.setCurrentIndex(dialog.listView.rulesModel.index(0, 0))

        dialog.deleteRule()

        confirmation = next(
            item
            for item in AppQDialog._openDialogs.values()
            if isinstance(item, AppQMessageBox)
        )

        for item in (dialog, confirmation):
            routingReferences.append(weakref.ref(item))
            item.destroyed.connect(lambda *_args: routingDestroyed.append(True))

        del item

        dialog.deleteLater()
        processQtEvents()

        assert not isValid(dialog) and not isValid(confirmation)

        del dialog, confirmation

    collectAtBoundary()

    assert len(routingDestroyed) == iterations * 2
    assert all(reference() is None for reference in routingReferences)
    assert not AppQDialog._openDialogs

    result['routingOwnerFirst'] = iterations

    for senderFirst in (True, False):
        survivor = _SignalEndpoint()
        counts = []

        for _ in range(iterations):
            transient = _SignalEndpoint()
            sender, receiver = (
                (transient, survivor) if senderFirst else (survivor, transient)
            )

            connectWeakly(sender.emitted, receiver, 'record', sender=sender)
            sender.emitted.emit()

            assert receiver.calls > 0

            transient.deleteLater()
            processQtEvents()

            assert not isValid(transient)

            survivor.emitted.emit()
            counts.append(survivor.receivers(QtCore.SIGNAL('destroyed(QObject*)')))

        assert counts == [counts[0]] * iterations, counts

        result['senderFirst' if senderFirst else 'receiverFirst'] = iterations

        survivor.deleteLater()
        processQtEvents()

    for windowFirst in (True, False):
        for _ in range(iterations):
            window = QWidget()
            window.show()
            processQtEvents()

            transition = ThemeTransition(
                duration=100000,
                windowProvider=lambda: (window,),
                animationsEnabled=lambda: True,
            )

            transition.apply(lambda: None)

            animation = next(iter(transition._animations))
            overlay = window.findChild(QWidget, transition.OverlayObjectName)

            if windowFirst:
                window.deleteLater()
                processQtEvents()

                assert not transition._animations
                assert not transition._animationsByWindow

                transition.deleteLater()
            else:
                transition.deleteLater()
                processQtEvents()

                window.deleteLater()

            processQtEvents()

            assert not isValid(animation)
            assert not isValid(overlay)

        result['themeWindowFirst' if windowFirst else 'themeCoordinatorFirst'] = (
            iterations
        )

    owner = QWidget()
    owner.show()
    processQtEvents()

    try:
        for _ in range(iterations):
            dialog = AppQMessageBox(parent=owner, text='Lifetime probe')
            dialog.open()
            mask = dialog._windowMask

            dialog.deleteLater()
            processQtEvents()

            assert not isValid(dialog)
            assert not isValid(mask)

        assert not AppQDialog._openDialogs

        result['messageBoxDeleted'] = iterations
    finally:
        owner.deleteLater()
        processQtEvents()

    return result


def runConfirmationProbe(iterations=100):
    """Check native menu ownership and representative view-owned prompts."""
    application()

    result = {}

    for explicitOwner in (False, True):
        references = []
        destroyed = []

        for _ in range(iterations):
            owner = QWidget()
            menu = AppQMenu(parent=owner if explicitOwner else None)
            action = AppQAction('Menu fixture', menu=menu, parent=owner)

            references.append(weakref.ref(menu))
            menu.destroyed.connect(lambda *_args: destroyed.append(True))

            action.deleteLater()
            processQtEvents()

            assert not isValid(action)
            assert isValid(menu) == explicitOwner

            owner.deleteLater()
            processQtEvents()

            del action, menu, owner

        assert len(destroyed) == iterations
        assert all(reference() is None for reference in references)

        result['widgetOwnedMenu' if explicitOwner else 'actionOwnedMenu'] = iterations

    originalAssetDirectory = assetModule.XRAY_ASSET_DIR

    try:
        with tempfile.TemporaryDirectory() as directory:
            assetModule.XRAY_ASSET_DIR = Path(directory)
            asset = Path(directory) / 'fixture.dat'
            asset.write_bytes(b'keep')

            for overwrite in (False, True):
                references = []
                destroyed = []

                for _ in range(iterations):
                    owner = QWidget()
                    view = XrayAssetListView(parent=owner)
                    view.setCurrentIndex(view.model().index(0, 0))

                    if overwrite:
                        view.appendNewItem(str(asset))
                    else:
                        view.deleteSelectedItem()

                    confirmation = next(iter(AppQDialog._openDialogs.values()))
                    references.append(weakref.ref(confirmation))
                    confirmation.destroyed.connect(
                        lambda *_args: destroyed.append(True)
                    )

                    view.deleteLater()
                    processQtEvents()

                    assert not isValid(view) and not isValid(confirmation)
                    assert isValid(owner)
                    assert asset.read_bytes() == b'keep'

                    owner.deleteLater()
                    processQtEvents()

                    del confirmation, view, owner

                assert len(destroyed) == iterations
                assert all(reference() is None for reference in references)
                assert not AppQDialog._openDialogs

                result[
                    'assetOverwriteOwnerFirst' if overwrite else 'assetDeleteOwnerFirst'
                ] = iterations
    finally:
        assetModule.XRAY_ASSET_DIR = originalAssetDirectory

    return result


def main():
    """Run the probe as a standalone source or Nuitka executable."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=100)
    parser.add_argument(
        '--pattern', choices=tuple(PROTOCOL_PATTERNS), default='alternating'
    )
    parser.add_argument('--close-method', choices=CLOSE_METHODS, default='reject')

    arguments = parser.parse_args()

    callbackErrors = []
    previousExceptionHook = sys.excepthook
    sys.excepthook = lambda kind, value, traceback: callbackErrors.append(
        (kind.__name__, str(value))
    )

    try:
        print(json.dumps(runNotificationAndDnsProbe(arguments.iterations)))
        print(json.dumps(runConnectionRecoveryProbe(arguments.iterations)))
        print(json.dumps(runReentrantLifetimeProbe(arguments.iterations)))
        print(json.dumps(runSingletonIPCProbe(arguments.iterations)))
        print(json.dumps(runThreadOwnershipProbe(arguments.iterations)))
        print(json.dumps(runTrayOwnershipProbe(arguments.iterations)))
        print(json.dumps(runSettingsAndSubscriptionProbe(arguments.iterations)))
        print(json.dumps(runButtonOwnershipProbe(arguments.iterations), sort_keys=True))
        print(json.dumps(runConfirmationProbe(arguments.iterations), sort_keys=True))
        print(json.dumps(runNetworkProbe(arguments.iterations), sort_keys=True))
        print(json.dumps(runInfrastructureProbe(arguments.iterations), sort_keys=True))

        print(
            json.dumps(
                runProbe(
                    arguments.iterations,
                    pattern=arguments.pattern,
                    closeMethod=arguments.close_method,
                ),
                sort_keys=True,
            )
        )
    finally:
        sys.excepthook = previousExceptionHook

    assert not callbackErrors, callbackErrors


if __name__ == '__main__':
    main()
