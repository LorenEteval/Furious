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

"""Exercise bounded service work, validation, and plugin UI ownership."""

from __future__ import annotations

from Furious.Plugins import (
    CapabilityKind,
    NavigationPageDescriptor,
    TrafficCounters,
    TrafficStatsMonitor,
)
from Furious.Service.ConnectivityManager import ConnectivityManager
from Furious.Service.EndpointInfoService import ProxyEndpointHttpClient
from Furious.Qt.HttpGetManager import HttpGetManager
from Furious.Service.PluginUIManager import PluginNavigationManager
from Furious.Service.TrafficStatsManager import TrafficStatsManager
from Furious.Service.UpdateManager import UpdateManager

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid, delete as deleteQObject

from tests.support import processQtEvents, application, collectAtBoundary, waitFor

from types import SimpleNamespace
from unittest.mock import patch

import json
import unittest
import weakref
import threading


class _ResponseBody:
    """Provide the QByteArray-compatible API consumed by UpdateManager."""

    def __init__(self, data):
        """Store one deterministic response body."""
        self._data = data

    def data(self):
        """Return the stored response bytes."""
        return self._data


class _Response:
    """Expose one complete fake network response."""

    def __init__(self, payload):
        """Encode *payload* as one JSON response."""
        self._data = json.dumps(payload).encode('utf-8')

    def readAll(self):
        """Return a QByteArray-compatible response wrapper."""
        return _ResponseBody(self._data)


class UpdateManagerTest(unittest.TestCase):
    """Verify update data is validated before it reaches UI callbacks."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def testMalformedSuccessfulResponseUsesControlledFailurePath(self):
        """Reject missing and untrusted release fields without raw exceptions."""
        manager = UpdateManager()
        parent = QWidget()
        versions = []

        with patch.object(manager, 'showErrorMessageBox') as showError:
            manager.successCallback(
                _Response(
                    {
                        'tag_name': '999.0.0',
                        'html_url': 'javascript:alert(1)',
                    }
                ),
                parent=parent,
                hasNewVersionCallback=versions.append,
            )

        showError.assert_called_once_with(parent)

        self.assertEqual(versions, [])

        manager.deleteLater()
        parent.deleteLater()

    def testFailureForwardsDialogParent(self):
        """Keep update failures modal to the initiating window when supplied."""
        manager = UpdateManager()
        parent = QWidget()

        with patch.object(manager, 'showErrorMessageBox') as showError:
            manager.failureCallback(None, parent=parent)

        showError.assert_called_once_with(parent)

        manager.deleteLater()
        parent.deleteLater()


class _ManagedReply(QNetworkReply):
    """Provide a hermetic reply object with real Qt lifecycle signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)

    def abort(self):
        self.setFinished(True)

    def readData(self, maximumLength):
        return bytes()


class _CapturingHttpGetManager(HttpGetManager):
    """Capture normalized requests without performing network I/O."""

    def __init__(self):
        super().__init__()
        self.reply = _ManagedReply(self)
        self.request = None

    def get(self, request):
        self.request = request
        return self.reply


class HttpGetManagerLifetimeTest(unittest.TestCase):
    """Verify every request receives a timeout and releases exact context."""

    @classmethod
    def setUpClass(cls):
        application()

    def testCompletionMayDestroyReplyOrManager(self):
        """Real finished delivery tolerates native deletion from user callbacks."""
        for managerType, contextAttribute in (
            (HttpGetManager, '_replyContexts'),
            (ProxyEndpointHttpClient, '_pendingRequests'),
        ):
            for deleteManager in (False, True):
                with self.subTest(manager=managerType.__name__, owner=deleteManager):
                    for _ in range(20):
                        manager = managerType()
                        reply = _ManagedReply(manager)
                        destroyed = []
                        reply.destroyed.connect(lambda *_a: destroyed.append(True))
                        completion = []

                        def destroyFromCallback(*_args, **_kwargs):
                            deleteQObject(manager if deleteManager else reply)

                        try:
                            with patch.object(manager, 'get', lambda _request: reply):
                                if isinstance(manager, HttpGetManager):
                                    manager.webGET(
                                        'https://invalid.test', logActionMessage=False
                                    )
                                    manager.successCallback = destroyFromCallback
                                    manager.completionCallback = (
                                        lambda **_k: completion.append(True)
                                    )
                                else:
                                    manager.request('https://invalid.test', 'fixture')
                                    manager.completed.connect(destroyFromCallback)

                            with patch('sys.excepthook') as exceptionHook:
                                reply.finished.emit()
                                processQtEvents()
                            exceptionHook.assert_not_called()
                            self.assertEqual(destroyed, [True])
                            self.assertFalse(isValid(reply))
                            self.assertFalse(getattr(manager, contextAttribute))
                            if isinstance(manager, HttpGetManager):
                                self.assertEqual(
                                    completion, [] if deleteManager else [True]
                                )
                        finally:
                            if isValid(manager):
                                deleteQObject(manager)
                            processQtEvents()

    def testEndpointCancellationToleratesOwnerDestructionDuringAbort(self):
        """An abort listener may delete the manager and its other pending replies."""
        manager = ProxyEndpointHttpClient()
        replies = [_ManagedReply(manager), _ManagedReply(manager)]
        for index, reply in enumerate(replies):
            with patch.object(manager, 'get', lambda _request: reply):
                manager.request('https://invalid.test', index)
        replies[0].abort = lambda: deleteQObject(manager)
        manager.cancelAll()
        self.assertFalse(isValid(manager))
        self.assertTrue(all(not isValid(reply) for reply in replies))
        self.assertEqual(manager._pendingRequests, {})

    def testRequestHasFiniteTimeoutAndTerminalPathDropsContext(self):
        manager = _CapturingHttpGetManager()

        reply = manager.webGET('https://invalid.test/resource', marker='fixture')

        self.assertIs(reply, manager.reply)
        self.assertEqual(manager.request.transferTimeout(), 60_000)
        self.assertEqual(manager._replyContexts[reply], {'marker': 'fixture'})

        with patch.object(manager, 'handleFinishedByNetworkReply') as finished:
            reply.finished.emit()

        self.assertEqual(manager._replyContexts, {})
        finished.assert_called_once_with(reply, marker='fixture')

        manager.deleteLater()

    def testEarlyReplyDestructionReleasesContextAcrossRepeatedRequests(self):
        """Native deletion without finished releases payloads and reply wrappers."""
        for managerType, contextAttribute in (
            (HttpGetManager, '_replyContexts'),
            (ProxyEndpointHttpClient, '_pendingRequests'),
        ):
            with self.subTest(manager=managerType.__name__):
                manager = managerType()
                references = []
                destroyed = []
                self.addCleanup(manager.deleteLater)

                for _ in range(30):
                    payload = _ResponseBody(b'fixture')
                    references.append(weakref.ref(payload))

                    reply = _ManagedReply(manager)
                    references.append(weakref.ref(reply))
                    reply.destroyed.connect(lambda *_args: destroyed.append(True))

                    with patch.object(manager, 'get', lambda _request: reply):
                        if isinstance(manager, HttpGetManager):
                            manager.webGET('https://invalid.test', payload=payload)
                        else:
                            manager.request('https://invalid.test', payload)

                    del payload
                    reply.deleteLater()
                    processQtEvents()

                    self.assertFalse(isValid(reply))
                    self.assertFalse(getattr(manager, contextAttribute))

                    del reply

                self.assertEqual(len(destroyed), 30)
                self.assertTrue(all(reference() is None for reference in references))

    def testManagerDestructionReleasesPendingContextWithRetainedWrappers(self):
        """Surviving invalid wrappers cannot keep operation payloads alive."""
        for managerType, contextAttribute in (
            (HttpGetManager, '_replyContexts'),
            (ProxyEndpointHttpClient, '_pendingRequests'),
        ):
            with self.subTest(manager=managerType.__name__):
                manager = managerType()
                payload = _ResponseBody(b'fixture')
                reference = weakref.ref(payload)
                reply = _ManagedReply(manager)

                with patch.object(manager, 'get', lambda _request: reply):
                    if isinstance(manager, HttpGetManager):
                        manager.webGET('https://invalid.test', payload=payload)
                    else:
                        manager.request('https://invalid.test', payload)

                del payload
                manager.deleteLater()
                processQtEvents()

                self.assertFalse(isValid(manager))
                self.assertFalse(isValid(reply))
                self.assertFalse(getattr(manager, contextAttribute))
                self.assertIsNone(reference())

    def testRepeatedFinishedSignalPublishesOnlyOnce(self):
        """A completed reply cannot invoke hooks again before deferred deletion."""
        manager = _CapturingHttpGetManager()
        self.addCleanup(manager.deleteLater)

        reply = manager.webGET('https://invalid.test', marker='fixture')

        with patch.object(manager, 'successCallback') as completed:
            reply.finished.emit()
            reply.finished.emit()

        completed.assert_called_once_with(reply, marker='fixture')

        processQtEvents()

        self.assertFalse(isValid(reply))

    capabilityId = 'fixture.navigation'


class _NavigationProvider:
    """Return one valid page and one invalid parented QObject."""

    def __init__(self):
        """Initialize construction counters used by idempotence assertions."""
        self.validCalls = 0
        self.invalidCalls = 0
        self.invalidPage = None

    def _validPage(self, parent=None):
        """Return one host-owned QWidget."""
        self.validCalls += 1

        return QWidget(parent)

    def _invalidPage(self, parent=None):
        """Return one parented QObject that must be rejected and destroyed."""
        self.invalidCalls += 1
        self.invalidPage = QtCore.QObject(parent)

        return self.invalidPage

    def pageDescriptors(self):
        """Return deterministic page descriptors."""
        return (
            NavigationPageDescriptor(
                'valid',
                'Valid',
                'valid.svg',
                self._validPage,
            ),
            NavigationPageDescriptor(
                'invalid',
                'Invalid',
                'invalid.svg',
                self._invalidPage,
            ),
        )


class _NavigationRegistry:
    """Expose the registry subset consumed by PluginNavigationManager."""

    def __init__(self, provider):
        """Store the only provider returned by this fixture."""
        self.provider = provider
        self.plugin = object()

    def plugins(self):
        """Return one deterministic plugin token."""
        return (self.plugin,)

    def metadataFor(self, plugin):
        """Return stable plugin metadata."""
        return SimpleNamespace(id='fixture')

    def capabilities(self, kind, plugin):
        """Return navigation capability only for the requested plugin."""
        if kind is CapabilityKind.NavigationPage and plugin is self.plugin:
            return (self.provider,)

        return tuple()


class _NavigationHost(QWidget):
    """Record pages registered through the host navigation API."""

    def __init__(self):
        """Initialize an empty registration list."""
        super().__init__()

        self.registrations = []

    def addPage(self, *args, **kwargs):
        """Record one page registration."""
        self.registrations.append((args, kwargs))


class PluginNavigationManagerTest(unittest.TestCase):
    """Protect startup idempotence and invalid QObject cleanup."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def testDestroyedFactoryResultsAreRejectedBeforeRegistration(self):
        """A retained Python wrapper is not proof of a valid plugin page."""
        for pageType in (QtCore.QObject, QWidget):
            with self.subTest(pageType=pageType):
                page = pageType()
                page.deleteLater()
                processQtEvents()

                provider = _NavigationProvider()
                provider._invalidPage = lambda parent=None: page
                host = _NavigationHost()
                manager = PluginNavigationManager(_NavigationRegistry(provider))

                try:
                    with self.assertLogs(
                        'Furious.Service.PluginUIManager', level='ERROR'
                    ):
                        pages = manager.registerPages(host)

                    self.assertEqual(len(pages), 1)
                    self.assertEqual(len(host.registrations), 1)
                finally:
                    host.deleteLater()
                    processQtEvents()

    def testRegistrationIsIdempotentAndDeletesInvalidQObject(self):
        """Construct each descriptor once and destroy rejected Qt objects."""
        provider = _NavigationProvider()
        host = _NavigationHost()
        manager = PluginNavigationManager(_NavigationRegistry(provider))

        first, second = (
            manager.registerPages(host),
            manager.registerPages(host),
        )

        self.assertEqual(first, second)
        self.assertEqual(provider.validCalls, 1)
        self.assertEqual(provider.invalidCalls, 1)
        self.assertEqual(len(host.registrations), 1)

        collectAtBoundary()

        self.assertFalse(isValid(provider.invalidPage))

        host.deleteLater()


class ConnectivityManagerTest(unittest.TestCase):
    """Verify one bounded request is active at a time without live networking."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def testRapidStartsReuseOneActiveRequest(self):
        """Do not accumulate probes or timeout timers during rapid calls."""
        manager = ConnectivityManager()
        reply = object()
        manager._testingEnabled = True

        with (
            patch.object(manager, 'webGET', return_value=reply) as webGet,
            patch(
                'Furious.Service.ConnectivityManager.AppSettings.get', return_value=None
            ),
        ):
            manager.startSingleTest()
            manager.startSingleTest()

        webGet.assert_called_once()

        self.assertIs(manager._activeReply, reply)
        self.assertTrue(manager.jobTimeoutTimer.isActive())

        manager.successCallback(reply)

        self.assertIsNone(manager._activeReply)
        self.assertFalse(manager.jobTimeoutTimer.isActive())
        self.assertTrue(manager.jobArrangeTimer.isActive())

        manager.stopTest()
        manager.deleteLater()


class TrafficStatsManagerTest(unittest.TestCase):
    """Verify a blocked provider cannot retain its Qt manager on cleanup."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def testBlockedQueryCompletionCallbackDoesNotRetainManager(self):
        """Keep a running plugin call detached from the manager's lifetime."""
        started = threading.Event()
        release = threading.Event()

        def query(_target):
            """Block until the test has checked the manager weak reference."""
            started.set()
            release.wait(2)

            return TrafficCounters(uplink=1, downlink=2)

        manager = TrafficStatsManager()
        manager._activateMonitor(TrafficStatsMonitor(query=query, target=None))

        self.assertTrue(started.wait(1))

        reference = weakref.ref(manager)

        manager.cleanup()
        manager.deleteLater()

        del manager

        collectAtBoundary()

        try:
            self.assertTrue(waitFor(lambda: reference() is None))
        finally:
            release.set()


if __name__ == '__main__':
    unittest.main()
