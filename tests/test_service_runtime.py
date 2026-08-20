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
from Furious.Service.PluginUIManager import PluginNavigationManager
from Furious.Service.TrafficStatsManager import TrafficStatsManager
from Furious.Service.UpdateManager import UpdateManager

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget

from shiboken6 import isValid

from tests.support import application, collectAtBoundary, waitFor

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


class _NavigationProvider:
    """Return one valid page and one invalid parented QObject."""

    capabilityId = 'fixture.navigation'

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

        with patch.object(manager, 'webGET', return_value=reply) as webGet:
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
