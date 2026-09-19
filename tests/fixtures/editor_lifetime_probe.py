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
from Furious.Plugins import blankProfile, initializePluginRegistry
from Furious.Qt import (
    AppQAction,
    AppQMenu,
    AppQDialog,
    AppQMessageBox,
    ThemeTransition,
    connectWeakly,
)
from Furious.Qt.HttpGetManager import HttpGetManager
from Furious.Service.EndpointInfoService import ProxyEndpointHttpClient
from Furious.Widget.ServerTableView import ServerTableView

import PySide6

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QPushButton, QWidget

from shiboken6 import isValid, delete as deleteQObject

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
)

from collections import Counter

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

        protectedMethods = getattr(PySide6, '_protected', None)
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
