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

"""Verify proxy-only endpoint discovery, cache invalidation, and presentation."""

from __future__ import annotations

from Furious.Controllers import ConnectionState, SettingsController
from Furious.Frozenlib import AppSettings
from Furious.Qt import AppQSwitch, AppStyleSheet
from Furious.Qt import gettext as _
from Furious.Service.EndpointInfoService import (
    PROXY_ENDPOINT_INFO_SETTING,
    EndpointInfo,
    EndpointInfoService,
    EndpointInfoState,
    EndpointLocation,
    ProxyEndpointHttpClient,
)
from Furious.Widget.EndpointInfoWidget import EndpointInfoWidget
from Furious.Window.SettingsPage import (
    _EndpointInfoSettingsCard,
    _endpointPrivacyMessageBox,
    _endpointPrivacyParagraphs,
)

from PySide6 import QtCore, QtGui
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFrame, QWidget

from shiboken6 import isValid

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
)

import json
from pathlib import Path
import unittest
from unittest.mock import patch
import weakref


class _Controller(QtCore.QObject):
    """Expose the connection signals consumed by the endpoint service."""

    stateChanged = QtCore.Signal(object)
    activeProfileChanged = QtCore.Signal(object)

    def __init__(self, state=ConnectionState.Connected):
        """Initialize a deterministic state-only controller."""
        super().__init__()

        self.state = state

    def isConnected(self):
        """Return whether the fixture represents an active connection."""
        return self.state is ConnectionState.Connected

    def setState(self, state):
        """Publish one connection transition."""
        self.state = state
        self.stateChanged.emit(state)


class _HttpClient(QtCore.QObject):
    """Record requests and allow tests to complete them without network I/O."""

    completed = QtCore.Signal(object, object, str)

    def __init__(self, proxyAccepted=True):
        """Initialize request and proxy observations."""
        super().__init__()

        self.proxyAccepted = proxyAccepted
        self.configuredProxies = []
        self.requests = []
        self.cancelCount = 0

    def configureHttpProxy(self, proxy):
        """Record the only permitted transport path."""
        self.configuredProxies.append(proxy)

        return self.proxyAccepted

    def request(self, url, context):
        """Record one provider request and its completion context."""
        self.requests.append((url, context))

    def completeLatest(self, data=None, error=''):
        """Complete the newest recorded request synchronously."""
        _url, context = self.requests[-1]

        self.completed.emit(context, data, error)

    def cancelAll(self):
        """Record connection-scope cancellation."""
        self.cancelCount += 1


class _PendingReply(QNetworkReply):
    """Provide a controllable reply for HTTP-client cancellation tests."""

    def __init__(self, parent=None):
        """Initialize an unfinished readable reply."""
        super().__init__(parent)

        self.abortCount = 0
        self.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)

    def abort(self):
        """Record cancellation and emit the normal Qt completion signal."""
        self.abortCount += 1
        self.setError(
            QNetworkReply.NetworkError.OperationCanceledError,
            'cancelled by test',
        )
        self.setFinished(True)
        self.finished.emit()

    def finishSuccessfully(self):
        """Complete normally without publishing response bytes."""
        self.setFinished(True)
        self.finished.emit()

    def readData(self, maximumLength):
        """Return EOF because the fixture never publishes response data."""
        return bytes()


class _EventRecorder(QtCore.QObject):
    """Record one event type without consuming the watched object's event."""

    def __init__(self, eventType, parent=None):
        """Initialize an empty event observation list."""
        super().__init__(parent)

        self.eventType = eventType
        self.events = []

    def eventFilter(self, watched, event):
        """Record matching events and preserve normal delivery."""
        if event.type() is self.eventType:
            self.events.append(watched)

        return False


class _PresentationService(QtCore.QObject):
    """Provide the minimal immutable API used by EndpointInfoWidget."""

    stateChanged, resultChanged, enabledChanged = (
        QtCore.Signal(object),
        QtCore.Signal(object),
        QtCore.Signal(bool),
    )

    def __init__(self):
        """Initialize one ready presentation snapshot."""
        super().__init__()

        self.state = EndpointInfoState.Ready
        self.enabled = True
        self.result = EndpointInfo(
            ipv4='192.0.2.1',
            ipv4Resolved=True,
            ipv6Resolved=True,
            locationResolved=True,
            location=EndpointLocation(
                countryCode='US',
                countryName='United States',
                city='Los Angeles',
                region='California',
                latitude=34.05,
                longitude=-118.24,
                organization='Example Network',
            ),
        )
        self.refreshCount = 0

    @QtCore.Slot()
    def refresh(self):
        """Record an explicit UI refresh request."""
        self.refreshCount += 1
        self.state = EndpointInfoState.Loading
        self.result = EndpointInfo()
        self.stateChanged.emit(self.state)
        self.resultChanged.emit(self.result)

    def completeRefresh(self):
        """Publish a deterministic refreshed endpoint at the same coordinate."""
        self.state = EndpointInfoState.Ready
        self.result = EndpointInfo(
            ipv4='192.0.2.1',
            ipv4Resolved=True,
            ipv6Resolved=True,
            locationResolved=True,
            location=EndpointLocation(
                countryCode='US',
                countryName='United States',
                city='Los Angeles',
                region='California',
                latitude=34.05,
                longitude=-118.24,
                organization='Example Network',
            ),
        )
        self.resultChanged.emit(self.result)
        self.stateChanged.emit(self.state)


class EndpointInfoServiceTest(unittest.TestCase):
    """Exercise provider fallback and per-connection caching deterministically."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Drain deferred QObject destruction after each case."""
        collectAtBoundary()

    def testHttpCancellationDropsReplyContextWithoutCompletion(self):
        """Cancel deterministically without object-ID bookkeeping or late data."""
        client = ProxyEndpointHttpClient()
        reply = _PendingReply(client)
        completions = []

        client.completed.connect(lambda *values: completions.append(values))

        with patch.object(client, 'get', return_value=reply):
            client.request('https://example.invalid', {'generation': 7})

        self.assertEqual(
            client._pendingRequests,
            {reply: {'generation': 7}},
        )

        client.cancelAll()

        self.assertEqual(reply.abortCount, 1)
        self.assertEqual(client._pendingRequests, {})
        self.assertEqual(completions, [])

        client.deleteLater()

    def testHttpCompletionReleasesPendingRequestEntry(self):
        """Release the explicit reply/context pair on normal completion."""
        client = ProxyEndpointHttpClient()
        reply = _PendingReply(client)
        completions = []

        client.completed.connect(lambda *values: completions.append(values))

        with patch.object(client, 'get', return_value=reply):
            client.request('https://example.invalid', {'generation': 9})

        reply.finishSuccessfully()

        self.assertEqual(client._pendingRequests, {})
        self.assertEqual(completions, [({'generation': 9}, b'', '')])

        client.deleteLater()

    @staticmethod
    def _service(
        proxy='127.0.0.1:10809',
        *,
        proxyAccepted=True,
        enabled=True,
    ):
        controller = _Controller()
        client = _HttpClient(proxyAccepted=proxyAccepted)
        service = EndpointInfoService(
            controller=controller,
            httpClient=client,
            proxyResolver=lambda: proxy,
            enabled=enabled,
        )

        return service, controller, client

    def testInspectionDefaultsOffAndNeverIssuesProviderRequests(self):
        """Require an explicit opt-in before any endpoint provider is contacted."""
        settings = QtCore.QSettings()
        settings.remove(PROXY_ENDPOINT_INFO_SETTING)

        controller = _Controller()

        client = _HttpClient()

        service = EndpointInfoService(
            controller=controller,
            httpClient=client,
            proxyResolver=lambda: '127.0.0.1:10809',
        )
        service.setPageVisible(True)
        service.refresh()

        self.assertFalse(service.enabled)
        self.assertEqual(service.state, EndpointInfoState.Disabled)
        self.assertEqual(client.requests, [])
        self.assertEqual(client.configuredProxies, [])

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testEnableDisableInvalidatesPendingLookupAndRejectsLateResults(self):
        """Apply opt-in immediately and prevent disabled replies repopulating data."""
        service, controller, client = self._service(enabled=False)
        service.setPageVisible(True)

        self.assertEqual(client.requests, [])

        service.setEnabled(True)

        self.assertEqual(len(client.requests), 1)

        _url, context = client.requests[-1]

        service.setEnabled(False)
        service.refresh()

        client.completed.emit(context, b'ip=192.0.2.20\nloc=US\n', '')

        self.assertEqual(service.state, EndpointInfoState.Disabled)
        self.assertEqual(service.result, EndpointInfo())
        self.assertEqual(len(client.requests), 1)
        self.assertGreaterEqual(client.cancelCount, 1)

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testRefreshPublishesLoadingBeforeClearingThePreviousResult(self):
        """Keep observer snapshots internally consistent during refresh startup."""
        service, controller, client = self._service()
        previousResult = EndpointInfo(ipv4='192.0.2.1', ipv4Resolved=True)
        observations = []

        service.state = EndpointInfoState.Ready
        service.result = previousResult
        service.stateChanged.connect(
            lambda state: observations.append(('state', state, service.result))
        )
        service.resultChanged.connect(
            lambda result: observations.append(('result', service.state, result))
        )

        service.refresh()

        self.assertEqual(
            observations[:2],
            [
                ('state', EndpointInfoState.Loading, previousResult),
                ('result', EndpointInfoState.Loading, EndpointInfo()),
            ],
        )

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testSettingsCardDefaultsOffPersistsAndExposesInAppPrivacyAction(self):
        """Bind one Fluent switch and one local privacy action to the preference."""
        privacyRequests = []

        with isolatedSettings():
            card = _EndpointInfoSettingsCard(
                SettingsController.setProxyEndpointInfoEnabled,
                lambda: privacyRequests.append(True),
            )

            self.assertIsInstance(card.checkBox, AppQSwitch)
            self.assertFalse(card.checkBox.isChecked())
            self.assertEqual(card.privacyButton.objectName(), 'SettingsLinkButton')
            self.assertEqual(card.privacyButton.text(), _('Data usage'))

            with patch('Furious.Window.SettingsPage._', side_effect=lambda text: text):
                privacyParagraphs = _endpointPrivacyParagraphs()
                privacyText = '\n'.join(privacyParagraphs)

            for paragraph in privacyParagraphs:
                self.assertGreaterEqual(paragraph.count('<br>\n'), 3)

            for provider in (
                'Cloudflare',
                'ipify',
                'ipapi.co',
                'OpenFreeMap',
                'OpenStreetMap',
            ):
                self.assertIn(provider, privacyText)
                self.assertNotIn(f'<i>{provider}</i>', privacyText)

            self.assertNotIn('<a ', privacyText)
            self.assertNotIn('href=', privacyText)
            self.assertNotIn('<i>', privacyText)
            self.assertIn('\n', privacyText)
            self.assertNotIn('<b>Privacy</b>', privacyText)
            self.assertNotIn('proxy credentials', privacyText)
            self.assertNotIn('subscription URLs', privacyText)
            self.assertNotIn('Furious', privacyText)
            self.assertNotIn('Qt Location', privacyText)
            self.assertNotIn('first time Network Statistics', privacyText)

            card.checkBox.setChecked(True)
            self.assertTrue(AppSettings.isStateON_(PROXY_ENDPOINT_INFO_SETTING))

            card.privacyButton.click()
            self.assertEqual(privacyRequests, [True])

            card.checkBox.setChecked(False)
            self.assertFalse(AppSettings.isStateON_(PROXY_ENDPOINT_INFO_SETTING))

            card.close()
            card.deleteLater()

    def testLookupIsLazyProxyOnlyAndCachedForConnection(self):
        """Never issue a direct request and reuse one completed session result."""
        service, controller, client = self._service()

        self.assertEqual(service.state, EndpointInfoState.Loading)
        self.assertEqual(client.requests, [])

        service.setPageVisible(True)

        self.assertEqual(client.configuredProxies, ['127.0.0.1:10809'])
        self.assertIn('1.1.1.1', client.requests[-1][0])

        client.completeLatest(b'ip=192.0.2.10\nloc=US\n')
        self.assertEqual(service.result.ipv4, '192.0.2.10')
        self.assertTrue(service.result.ipv4Resolved)
        self.assertFalse(service.result.ipv6Resolved)
        self.assertIn('2606:4700:4700::1111', client.requests[-1][0])

        client.completeLatest(error='IPv6 unavailable')
        self.assertEqual(client.requests[-1][0], 'https://api6.ipify.org')
        client.completeLatest(b'2001:db8::10')

        self.assertEqual(service.result.ipv6, '2001:db8::10')
        self.assertTrue(service.result.ipv6Resolved)
        self.assertFalse(service.result.locationResolved)
        self.assertIn('192.0.2.10', client.requests[-1][0])

        location = {
            'ip': '192.0.2.10',
            'country_code': 'US',
            'country_name': 'United States',
            'region': 'California',
            'city': 'Los Angeles',
            'latitude': 34.05,
            'longitude': -118.24,
            'org': 'Example Network',
        }
        client.completeLatest(json.dumps(location).encode())

        self.assertEqual(service.state, EndpointInfoState.Ready)
        self.assertEqual(service.result.location.city, 'Los Angeles')
        self.assertTrue(service.result.locationResolved)

        requestCount = len(client.requests)
        service.setPageVisible(False)
        service.setPageVisible(True)
        service.requestIfNeeded()

        self.assertEqual(len(client.requests), requestCount)

        controller.activeProfileChanged.emit(object())

        self.assertEqual(service.state, EndpointInfoState.Loading)
        self.assertEqual(service.result, EndpointInfo())
        self.assertEqual(len(client.requests), requestCount + 1)

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testMissingOrRejectedProxyNeverFallsBackToDirectAccess(self):
        """Fail closed when the active local HTTP proxy cannot be configured."""
        for proxy, proxyAccepted in ((None, True), ('127.0.0.1:10809', False)):
            with self.subTest(proxy=proxy, proxyAccepted=proxyAccepted):
                service, controller, client = self._service(
                    proxy,
                    proxyAccepted=proxyAccepted,
                )
                service.setPageVisible(True)

                self.assertEqual(service.state, EndpointInfoState.Failed)
                self.assertEqual(client.requests, [])

                controller.deleteLater()
                client.deleteLater()
                service.deleteLater()

    def testInvalidResponsesFallbackAndLateOldSessionDataIsIgnored(self):
        """Validate addresses and reject results from a disconnected session."""
        service, controller, client = self._service()
        service.setPageVisible(True)
        staleRequest = client.requests[-1]

        client.completeLatest(b'ip=not-an-address\nloc=US\n')
        self.assertEqual(client.requests[-1][0], 'https://api4.ipify.org')

        controller.setState(ConnectionState.Disconnected)
        _url, context = staleRequest
        client.completed.emit(context, b'ip=192.0.2.20\nloc=US\n', '')

        self.assertEqual(service.state, EndpointInfoState.Disconnected)
        self.assertEqual(service.result, EndpointInfo())
        self.assertGreaterEqual(client.cancelCount, 1)

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testIPv6FailureKeepsIPv4AndCompletesLocation(self):
        """Treat IPv6 absence as a partial result rather than total failure."""
        service, controller, client = self._service()
        service.setPageVisible(True)
        client.completeLatest(b'ip=8.8.8.8\nloc=US\n')

        client.completeLatest(error='no IPv6 route')
        client.completeLatest(error='no IPv6 fallback')

        self.assertEqual(service.result.ipv4, '8.8.8.8')
        self.assertEqual(service.result.ipv6, '')
        self.assertTrue(service.result.ipv4Resolved)
        self.assertTrue(service.result.ipv6Resolved)
        self.assertFalse(service.result.locationResolved)
        self.assertIn('8.8.8.8', client.requests[-1][0])

        location = {
            'ip': '8.8.8.8',
            'country_code': 'US',
            'country_name': 'United States',
            'region': 'California',
            'city': 'Mountain View',
            'latitude': 37.4,
            'longitude': -122.1,
        }
        client.completeLatest(json.dumps(location).encode())

        self.assertEqual(service.state, EndpointInfoState.Ready)
        self.assertEqual(service.result.location.countryCode, 'US')
        self.assertTrue(service.result.locationResolved)

        controller.deleteLater()
        client.deleteLater()
        service.deleteLater()

    def testCountryIsPlainTextAndFlagResourcesAreAbsent(self):
        """Keep country presentation while removing the complete flag subsystem."""
        repositoryRoot = Path(__file__).resolve().parents[1]
        resourceManifest = (repositoryRoot / 'Resources.qrc').read_text(
            encoding='utf-8'
        )

        self.assertNotIn('Icons/flags', resourceManifest)
        self.assertNotIn('flag-icons', resourceManifest)
        self.assertFalse((repositoryRoot / 'Icons' / 'flags').exists())

        service = _PresentationService()
        widget = EndpointInfoWidget(service)

        self.assertIs(type(widget.infoCard), QFrame)
        self.assertEqual(widget.countryRow.valueLabel.text(), 'United States (US)')
        self.assertFalse(hasattr(widget.countryRow, 'flagLabel'))

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testDataUsageDialogHasStaticProviderTextAndTransientLifetime(self):
        """Render provider names without links and destroy each closed disclosure."""
        parent = QWidget()
        references = []

        for _index in range(5):
            with patch('Furious.Window.SettingsPage._', side_effect=lambda text: text):
                messageBox = _endpointPrivacyMessageBox(parent)

            body = messageBox.informativeText()
            references.append(weakref.ref(messageBox))

            self.assertIn('Cloudflare', body)
            self.assertIn('OpenFreeMap', body)
            self.assertIn('OpenStreetMap', body)
            self.assertNotIn('CARTO', body)
            self.assertNotIn('<a ', body)
            self.assertNotIn('href=', body)
            self.assertIn('<br><br>\n', body)
            self.assertNotIn('<br><br><b>', body)
            self.assertNotIn('<b>Privacy</b>', body)
            self.assertNotIn('proxy configuration', body)
            self.assertNotIn('Furious', body)
            self.assertNotIn('Qt Location', body)
            self.assertEqual(len(messageBox.buttons()), 1)

            messageBox.show()
            processQtEvents()
            messageBox.close()
            processQtEvents()
            del messageBox

        collectAtBoundary()
        self.assertTrue(all(reference() is None for reference in references))

        parent.close()
        parent.deleteLater()

    def testFieldAndMapSpinnersTrackPartialCompletionIndependently(self):
        """Keep each unresolved field animated while preserving partial results."""
        service = _PresentationService()

        widget = EndpointInfoWidget(service)
        widget.mapWidget._sourceLoaded = True
        widget.mapWidget._documentLoaded = True
        widget.mapWidget._runJavaScript = lambda _script: None
        widget.show()

        processQtEvents()
        service.refresh()
        processQtEvents()

        self.assertFalse(hasattr(widget, 'statusLabel'))

        rows = (
            widget.ipv4Row,
            widget.ipv6Row,
            widget.countryRow,
            widget.locationRow,
            widget.organizationRow,
        )

        self.assertTrue(all(row.loadingSpinner.is_spinning for row in rows))
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertTrue(widget.mapWidget._lastWebState['loading'])
        self.assertFalse(widget.mapWidget._lastWebState['markerVisible'])

        service.result = EndpointInfo(ipv4='192.0.2.1', ipv4Resolved=True)
        service.resultChanged.emit(service.result)

        processQtEvents()

        self.assertEqual(widget.ipv4Row.valueLabel.text(), '192.0.2.1')
        self.assertFalse(widget.ipv4Row.loadingSpinner.is_spinning)
        self.assertTrue(widget.ipv6Row.loadingSpinner.is_spinning)
        self.assertTrue(widget.countryRow.loadingSpinner.is_spinning)
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)

        service.result = EndpointInfo(
            ipv4='192.0.2.1',
            ipv4Resolved=True,
            ipv6Resolved=True,
        )
        service.resultChanged.emit(service.result)

        processQtEvents()

        self.assertEqual(widget.ipv6Row.valueLabel.text(), _('Not available'))
        self.assertFalse(widget.ipv6Row.loadingSpinner.is_spinning)
        self.assertTrue(widget.locationRow.loadingSpinner.is_spinning)

        service.state = EndpointInfoState.Ready
        service.result = EndpointInfo(
            ipv4='192.0.2.1',
            ipv4Resolved=True,
            ipv6Resolved=True,
            locationResolved=True,
            location=EndpointLocation(
                countryCode='US',
                countryName='United States',
                city='Los Angeles',
                region='California',
                latitude=34.05,
                longitude=-118.24,
                organization='Example Network',
            ),
        )
        service.resultChanged.emit(service.result)
        service.stateChanged.emit(service.state)

        widget.mapWidget._mapBecameReady()

        processQtEvents()

        self.assertTrue(all(not row.loadingSpinner.is_spinning for row in rows))
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testPresentationShowsValidatedValuesAndApproximateLocation(self):
        """Render selectable IP data and expose one reusable refresh action."""
        service = _PresentationService()

        widget = EndpointInfoWidget(service)
        widget.resize(900, 320)

        scripts = []

        widget.mapWidget._sourceLoaded = True
        widget.mapWidget._documentLoaded = True
        widget.mapWidget._runJavaScript = scripts.append
        widget.mapWidget._syncWebState()

        self.assertEqual(widget.ipv4Row.valueLabel.text(), '192.0.2.1')
        self.assertEqual(widget.refreshButton.toolTip(), _('Refresh'))
        self.assertEqual(widget.ipv4Row.copyButton.toolTip(), _('Copy'))
        self.assertEqual(widget.countryRow.valueLabel.text(), 'United States (US)')
        self.assertEqual(
            widget.locationRow.valueLabel.text(),
            'Los Angeles, California, United States',
        )
        self.assertFalse(hasattr(widget.countryRow, 'flagLabel'))
        self.assertFalse(hasattr(widget, 'statusLabel'))
        self.assertEqual(widget.bodyLayout.stretch(0), 1)
        self.assertEqual(widget.bodyLayout.stretch(1), 2)
        self.assertGreaterEqual(widget.minimumHeight(), 360)
        self.assertIsInstance(widget.mapWidget.webView, QWebEngineView)
        self.assertEqual(widget.mapWidget.webProfile.httpUserAgent(), 'Mozilla/5.0')
        self.assertNotIn('Furious', widget.mapWidget.webProfile.httpUserAgent())
        self.assertTrue(widget.mapWidget._lastWebState['markerVisible'])
        self.assertEqual(
            widget.mapWidget._lastWebState['fontFamily'],
            QtGui.QFontInfo(widget.mapWidget.font()).family(),
        )
        self.assertEqual(
            widget.mapWidget._lastWebState['fontPointSize'],
            QtGui.QFontInfo(widget.mapWidget.font()).pointSizeF(),
        )
        self.assertAlmostEqual(widget.mapWidget._lastWebState['markerLatitude'], 34.05)
        self.assertAlmostEqual(
            widget.mapWidget._lastWebState['markerLongitude'], -118.24
        )
        self.assertTrue(scripts)
        self.assertEqual(
            widget.ipv4Row.valueContainer.objectName(),
            'EndpointFieldValueContainer',
        )
        self.assertFalse(hasattr(widget, 'statusWidget'))
        self.assertFalse(hasattr(widget, 'spinner'))
        self.assertIn(
            'QWidget#EndpointFieldValueContainer',
            AppStyleSheet.forTheme(AppStyleSheet.Light),
        )

        wheelEvent = QtGui.QWheelEvent(
            QtCore.QPointF(20, 20),
            QtCore.QPointF(20, 20),
            QtCore.QPoint(),
            QtCore.QPoint(0, 60),
            QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            QtCore.Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QtCore.QCoreApplication.sendEvent(widget.mapWidget.webView, wheelEvent)

        self.assertTrue(wheelEvent.isAccepted())

        html = widget.mapWidget.HtmlPath.read_text(encoding='utf-8')
        mapScriptPath = widget.mapWidget.HtmlPath.with_name('EndpointMap.js')
        mapScript = mapScriptPath.read_text(encoding='utf-8')

        self.assertIn('EndpointMap.js', html)
        self.assertIn('window.endpointMap', mapScript)
        self.assertIn('map.setStyle(nextStyle)', mapScript)
        self.assertIn("document.documentElement.dataset.theme", mapScript)
        self.assertIn('--endpoint-attribution-background', html)
        self.assertIn('--endpoint-attribution-foreground', html)
        self.assertIn('endpoint-loading-overlay', html)
        self.assertIn('endpoint-loading-spinner', html)
        self.assertIn('width: 16px', html)
        self.assertIn('height: 16px', html)
        self.assertIn('0.8s linear infinite', html)
        self.assertIn('border-right-color: transparent', html)
        self.assertIn('--endpoint-font-family', html)
        self.assertIn("JSON.stringify(state.fontFamily", mapScript)
        self.assertIn('applyLoadingState()', mapScript)
        self.assertIn('!state.markerVisible', mapScript)
        self.assertIn('.maplibregl-canvas:focus', html)
        self.assertIn('outline: none', html)
        self.assertNotIn('color-mix(', html)
        self.assertEqual(
            {style.name: style.value for style in widget.mapWidget.Style},
            {
                'Bright': 'https://tiles.openfreemap.org/styles/bright',
                'Liberty': 'https://tiles.openfreemap.org/styles/liberty',
                'Positron': 'https://tiles.openfreemap.org/styles/positron',
                'Dark': 'https://tiles.openfreemap.org/styles/dark',
                'Fiord': 'https://tiles.openfreemap.org/styles/fiord',
            },
        )
        self.assertEqual(
            widget.mapWidget._lastWebState['lightStyleUrl'],
            widget.mapWidget.LightStyle.value,
        )
        self.assertIs(widget.mapWidget.LightStyle, widget.mapWidget.Style.Liberty)
        self.assertEqual(
            widget.mapWidget._lastWebState['darkStyleUrl'],
            widget.mapWidget.DarkStyle.value,
        )
        self.assertIs(widget.mapWidget.DarkStyle, widget.mapWidget.Style.Fiord)
        self.assertNotIn('tile.openstreetmap.org', html)
        self.assertNotIn('opacity: 0.60', html)
        self.assertNotIn('opacity: 0.60', mapScript)
        self.assertTrue(mapScriptPath.is_file())
        self.assertTrue((widget.mapWidget.HtmlPath.parent / 'maplibre-gl.js').is_file())
        self.assertTrue(
            (widget.mapWidget.HtmlPath.parent / 'maplibre-gl.css').is_file()
        )
        self.assertTrue((widget.mapWidget.HtmlPath.parent / 'LICENSE').is_file())

        widget.mapWidget.setActive(True)

        self.assertFalse(widget.mapWidget.webView.isHidden())
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)
        self.assertTrue(widget.mapWidget._lastWebState['loading'])

        hideRecorder = _EventRecorder(QtCore.QEvent.Type.Hide, widget)

        widget.mapWidget.webView.installEventFilter(hideRecorder)
        widget.mapWidget._mapBecameReady()

        processQtEvents()

        self.assertEqual(hideRecorder.events, [])
        self.assertFalse(widget.mapWidget.webView.isHidden())
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget._lastWebState['loading'])

        service.state = EndpointInfoState.Loading
        service.stateChanged.emit(service.state)

        self.assertEqual(widget.mapWidget.statusLabel.text(), _('Detecting...'))
        self.assertFalse(widget.mapWidget.webView.isHidden())
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)
        self.assertTrue(widget.mapWidget._lastWebState['loading'])

        service.state = EndpointInfoState.Ready
        service.stateChanged.emit(service.state)

        self.assertFalse(widget.mapWidget.webView.isHidden())
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())

        widget.refreshButton.click()

        self.assertEqual(service.refreshCount, 1)
        self.assertEqual(widget.mapWidget.statusLabel.text(), _('Detecting...'))
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)
        self.assertTrue(widget.mapWidget._lastWebState['loading'])
        self.assertEqual(
            widget.mapWidget._lastWebState['loadingText'],
            _('Detecting...'),
        )

        previousRevision = widget.mapWidget._viewRevision
        service.completeRefresh()

        processQtEvents()

        self.assertGreater(widget.mapWidget._viewRevision, previousRevision)
        self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget._lastWebState['loading'])
        self.assertAlmostEqual(widget.mapWidget._lastWebState['markerLatitude'], 34.05)
        self.assertAlmostEqual(
            widget.mapWidget._lastWebState['markerLongitude'], -118.24
        )

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testUnavailableLocationReplacesHtmlLoadingWithSingleLineFallback(self):
        """Hide web loading before presenting the terminal map fallback."""
        service = _PresentationService()
        service.state = EndpointInfoState.Ready
        service.result = EndpointInfo(
            ipv4='192.0.2.1',
            ipv4Resolved=True,
            ipv6Resolved=True,
            locationResolved=True,
        )

        widget = EndpointInfoWidget(service)
        widget.mapWidget._sourceLoaded = True
        widget.mapWidget._documentLoaded = True
        widget.mapWidget._runJavaScript = lambda _script: None
        widget.show()

        processQtEvents()
        widget._updatePresentation()

        self.assertFalse(widget.mapWidget._lastWebState['loading'])
        self.assertFalse(widget.mapWidget._lastWebState['markerVisible'])
        self.assertFalse(widget.mapWidget.statusOverlay.isHidden())
        self.assertFalse(widget.mapWidget.statusLabel.wordWrap())
        self.assertEqual(
            widget.mapWidget.statusLabel.text(),
            _('Approximate location unavailable'),
        )
        self.assertFalse(widget.mapWidget.loadingSpinner.is_spinning)

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testMapUsesForcedApplicationThemeFromItsFirstState(self):
        """Initialize map styling from the app preference, not the host palette."""
        service = _PresentationService()
        app = application()

        with patch.object(type(app), 'theme', return_value=AppStyleSheet.Light):
            widget = EndpointInfoWidget(service)

        scripts = []

        widget.mapWidget._documentLoaded = True
        widget.mapWidget._runJavaScript = scripts.append
        widget.mapWidget._syncWebState()

        self.assertEqual(widget.mapWidget._theme, AppStyleSheet.Light)
        self.assertFalse(widget.mapWidget._lastWebState['darkMode'])
        self.assertEqual(
            widget.mapWidget._lastWebState['lightStyleUrl'],
            widget.mapWidget.LightStyle.value,
        )
        self.assertTrue(scripts)

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testMapReadyAndRefreshDoNotToggleWebViewVisibility(self):
        """Overlay map status without recreating the native Chromium surface."""
        service = _PresentationService()

        widget = EndpointInfoWidget(service)
        widget.mapWidget._sourceLoaded = True
        widget.mapWidget._documentLoaded = True

        with patch.object(widget.mapWidget, '_ensureSourceLoaded'):
            widget.show()
            processQtEvents()

        windowHideRecorder = _EventRecorder(QtCore.QEvent.Type.Hide, widget)
        mapHideRecorder = _EventRecorder(QtCore.QEvent.Type.Hide, widget)
        mapShowRecorder = _EventRecorder(QtCore.QEvent.Type.Show, widget)

        widget.installEventFilter(windowHideRecorder)
        widget.mapWidget.webView.installEventFilter(mapHideRecorder)
        widget.mapWidget.webView.installEventFilter(mapShowRecorder)

        widget.mapWidget._mapBecameReady()
        processQtEvents()

        persistentObjects = (
            widget.mapWidget.webView,
            widget.mapWidget.webView.page(),
            widget.mapWidget.webProfile,
            widget.mapWidget.webChannel,
            widget.mapWidget.webBridge,
            widget.mapWidget.statusOverlay,
            widget.mapWidget.loadingSpinner,
        )

        for _index in range(40):
            widget.refreshButton.click()
            processQtEvents()

            self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
            self.assertTrue(widget.mapWidget._lastWebState['loading'])

            service.completeRefresh()
            processQtEvents()

            self.assertTrue(widget.mapWidget.statusOverlay.isHidden())
            self.assertFalse(widget.mapWidget._lastWebState['loading'])

        self.assertEqual(windowHideRecorder.events, [])
        self.assertEqual(mapHideRecorder.events, [])
        self.assertEqual(mapShowRecorder.events, [])
        self.assertEqual(
            persistentObjects,
            (
                widget.mapWidget.webView,
                widget.mapWidget.webView.page(),
                widget.mapWidget.webProfile,
                widget.mapWidget.webChannel,
                widget.mapWidget.webBridge,
                widget.mapWidget.statusOverlay,
                widget.mapWidget.loadingSpinner,
            ),
        )

        widget.close()
        widget.deleteLater()
        service.deleteLater()

    def testMapThemeSwitchPreservesViewMarkerAndPersistentScene(self):
        """Switch real map styles without recreating the persistent renderer."""
        service = _PresentationService()
        scripts = []

        widget = EndpointInfoWidget(service)
        widget.mapWidget._documentLoaded = True
        widget.mapWidget._runJavaScript = scripts.append
        widget.mapWidget._syncWebState()

        webView = widget.mapWidget.webView
        webPage = webView.page()
        webProfile = widget.mapWidget.webProfile
        webBridge = widget.mapWidget.webBridge
        initialRevision = widget.mapWidget._viewRevision
        marker = (
            widget.mapWidget._lastWebState['markerLatitude'],
            widget.mapWidget._lastWebState['markerLongitude'],
        )

        for index in range(40):
            theme = AppStyleSheet.Dark if index % 2 == 0 else AppStyleSheet.Light
            widget.themeChangedCallback(theme)

            processQtEvents()

            self.assertIs(widget.mapWidget.webView, webView)
            self.assertIs(widget.mapWidget.webView.page(), webPage)
            self.assertIs(widget.mapWidget.webProfile, webProfile)
            self.assertIs(widget.mapWidget.webBridge, webBridge)
            self.assertEqual(widget.mapWidget._viewRevision, initialRevision)
            self.assertEqual(
                widget.mapWidget._lastWebState['darkMode'],
                theme == AppStyleSheet.Dark,
            )
            self.assertEqual(
                (
                    widget.mapWidget._lastWebState['markerLatitude'],
                    widget.mapWidget._lastWebState['markerLongitude'],
                ),
                marker,
            )

        self.assertEqual(len(widget.findChildren(QWebEngineView)), 1)
        self.assertEqual(len(scripts), 41)

        widgetReference = weakref.ref(widget)
        webViewReference = weakref.ref(webView)
        webPageReference = weakref.ref(webPage)
        webProfileReference = weakref.ref(webProfile)
        webBridgeReference = weakref.ref(webBridge)

        widget.close()
        widget.deleteLater()
        service.deleteLater()

        del webBridge
        del webProfile
        del webPage
        del webView
        del widget

        collectAtBoundary()

        self.assertIsNone(widgetReference())

        for reference in (
            webViewReference,
            webPageReference,
            webProfileReference,
            webBridgeReference,
        ):
            wrapper = reference()
            self.assertTrue(wrapper is None or not isValid(wrapper))


if __name__ == '__main__':
    unittest.main()
