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

"""Present connection-scoped proxy endpoint information on the metrics page."""

from __future__ import annotations

from Furious.Frozenlib import APP, DATA_DIR, PLATFORM, Mixins
from Furious.Qt import AppQLabel, AppQPushButton, AppStyleSheet, bootstrapIcon
from Furious.Qt import gettext as _
from Furious.Service import EndpointInfo, EndpointInfoState
from Furious.Widget.WaitingSpinner import WaitingSpinner

from PySide6 import QtCore, QtGui
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import *

import enum
import json
import logging

__all__ = ['EndpointInfoWidget']

logger = logging.getLogger(__name__)


class _EndpointWebView(QWebEngineView):
    """Keep map wheel gestures from bubbling into the Metrics scroll area."""

    def wheelEvent(self, event):
        """Let the map process the gesture, then consume it at this boundary."""
        super().wheelEvent(event)

        event.accept()


class _EndpointMapBridge(QtCore.QObject):
    """Expose the narrow, trusted callback surface used by the local map page."""

    mapReady, mapFailed, externalLinkRequested = (
        QtCore.Signal(),
        QtCore.Signal(str),
        QtCore.Signal(str),
    )

    @QtCore.Slot()
    def ready(self):
        """Publish that the initial vector style is ready for presentation."""
        self.mapReady.emit()

    @QtCore.Slot(str)
    def failed(self, message):
        """Publish an error reported by the embedded map renderer."""
        self.mapFailed.emit(str(message or ''))

    @QtCore.Slot(str)
    def openExternal(self, link):
        """Request external navigation without allowing in-view navigation."""
        self.externalLinkRequested.emit(str(link or ''))


class _EndpointMapWidget(QWidget):
    """Host one lazily loaded MapLibre vector map for the page lifetime."""

    class Style(enum.StrEnum):
        """OpenFreeMap styles available to the embedded endpoint map."""

        Bright, Liberty, Positron, Dark, Fiord = (
            'https://tiles.openfreemap.org/styles/bright',
            'https://tiles.openfreemap.org/styles/liberty',
            'https://tiles.openfreemap.org/styles/positron',
            'https://tiles.openfreemap.org/styles/dark',
            'https://tiles.openfreemap.org/styles/fiord',
        )

    HtmlPath = DATA_DIR / 'maplibre' / 'EndpointMap.html'
    LightStyle = Style.Liberty
    DarkStyle = Style.Fiord
    TrustedAttributionHosts = frozenset(
        {
            'openfreemap.org',
            'www.openfreemap.org',
            'openmaptiles.org',
            'www.openmaptiles.org',
            'openstreetmap.org',
            'www.openstreetmap.org',
        }
    )
    DefaultGeographicZoom = 6.0
    UserAgent = 'Mozilla/5.0'

    def __init__(self, parent=None):
        """Initialize an inert map whose lifetime follows its containing card."""
        super().__init__(parent)

        self._location = None
        self._message = ''
        self._unavailableText = ''
        self._loadingText = ''
        self._loading = False
        self._active = False
        self._sourceLoaded = False
        self._documentLoaded = False
        self._mapReady = False
        self._mapError = ''
        self._viewRevision = 0
        self._lastWebState = {}
        self._retainMapDuringRefresh = False

        self._theme = self._resolvedTheme()

        self.setObjectName('EndpointMapWidget')
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.statusOverlay = QWidget(self)
        self.statusOverlay.setAutoFillBackground(True)

        self.statusLabel = AppQLabel(
            translatable=False,
            parent=self.statusOverlay,
        )
        self.statusLabel.setObjectName('EndpointMapPlaceholder')
        self.statusLabel.setWordWrap(False)

        self.loadingSpinner = WaitingSpinner(
            self.statusOverlay,
            center_on_parent=False,
            line_length=5,
            line_width=2,
            radius=4,
            lines=12,
        )
        self.loadingSpinner.setFixedSize(22, 22)

        statusLayout = QHBoxLayout(self.statusOverlay)
        statusLayout.setContentsMargins(12, 12, 12, 12)
        statusLayout.setSpacing(8)
        statusLayout.addStretch(1)
        statusLayout.addWidget(self.loadingSpinner)
        statusLayout.addWidget(self.statusLabel)
        statusLayout.addStretch(1)

        # The off-the-record profile, page, channel, bridge, and WebEngine view
        # are all persistent children of this page-lifetime map widget. This
        # keeps vector-tile caching in memory and gives Chromium one bounded,
        # explicit teardown path with the containing Metrics page.
        self.webProfile = QWebEngineProfile(self)
        self.webProfile.setHttpCacheType(
            QWebEngineProfile.HttpCacheType.MemoryHttpCache
        )
        self.webProfile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )
        self.webProfile.setHttpUserAgent(self.UserAgent)

        self.webView = _EndpointWebView(self.webProfile, self)
        self.webView.setObjectName('EndpointLocationMap')
        self.webView.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        self.webView.page().setBackgroundColor(QtCore.Qt.GlobalColor.transparent)

        webSettings = self.webView.settings()
        webSettings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        webSettings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            False,
        )
        webSettings.setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled,
            True,
        )

        self.webChannel = QWebChannel(self.webView.page())
        self.webBridge = _EndpointMapBridge(self.webChannel)
        self.webChannel.registerObject('endpointMapBridge', self.webBridge)
        self.webView.page().setWebChannel(self.webChannel)

        self.webBridge.mapReady.connect(self._mapBecameReady)
        self.webBridge.mapFailed.connect(self._mapFailed)
        self.webBridge.externalLinkRequested.connect(self._openExternalLink)

        self.webView.loadFinished.connect(self._loadFinished)
        self.webView.page().renderProcessTerminated.connect(
            self._renderProcessTerminated
        )

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.webView, 0, 0)
        layout.addWidget(self.statusOverlay, 0, 0)

        if (
            PLATFORM == 'Windows'
            and QApplication.platformName().casefold() != 'offscreen'
        ):
            # Qt WebEngine embeds a native surface. When that surface first
            # appears inside the Metrics QScrollArea, Qt otherwise promotes
            # the visible parent chain to native windows, remapping and
            # visibly flashing the main window. Create the same hierarchy
            # now, while the application window is still hidden. This does
            # not load the map document or contact its provider.
            self.webView.winId()

    def _resolvedTheme(self, theme=None):
        """Resolve the map theme from the authoritative application setting."""
        if theme is not None:
            return AppStyleSheet.normalizeTheme(theme)

        app = APP()

        if app is not None and hasattr(app, 'theme'):
            return AppStyleSheet.normalizeTheme(app.theme())
        else:
            base = self.palette().color(QtGui.QPalette.ColorRole.Base)

            return AppStyleSheet.Dark if base.lightness() < 128 else AppStyleSheet.Light

    def setLocation(self, location, message='', *, loading=False):
        """Replace the displayed coordinate and status message."""
        refreshCompleted = self._retainMapDuringRefresh and not loading
        previousLocation = self._location
        previousCoordinate = (
            (
                previousLocation.latitude,
                previousLocation.longitude,
            )
            if previousLocation is not None
            and previousLocation.latitude is not None
            and previousLocation.longitude is not None
            else None
        )

        self._message = str(message or '')
        self._loading = bool(loading)

        nextCoordinate = (
            (location.latitude, location.longitude)
            if location is not None
            and location.latitude is not None
            and location.longitude is not None
            else None
        )

        if not (
            self._loading and self._retainMapDuringRefresh and nextCoordinate is None
        ):
            self._location = location

        if not self._loading:
            self._retainMapDuringRefresh = False

        coordinate = (
            (self._location.latitude, self._location.longitude)
            if self._hasLocation()
            else None
        )

        # A newly observed endpoint is a data transition, not a repaint. Only
        # that transition resets user pan/zoom to the canonical location view.
        if coordinate is not None and (
            coordinate != previousCoordinate or refreshCompleted
        ):
            self._viewRevision += 1

        if self._active:
            self._ensureSourceLoaded()

        self._syncWebState()
        self._updateOverlay()

    def beginRefresh(self):
        """Overlay progress on the current map during an explicit refresh."""
        self._retainMapDuringRefresh = self._hasLocation() and self._mapReady
        self._loading = True
        self._message = self._loadingText
        self._syncWebState()
        self._updateOverlay()

    def setActive(self, active):
        """Allow map initialization and rendering only while its page is visible."""
        self._active = bool(active)

        if self._active:
            self._ensureSourceLoaded()

        self._syncWebState()
        self._updateOverlay()

    def updateTheme(self, theme=None):
        """Switch vector styles without replacing the persistent map page."""
        self._theme = self._resolvedTheme(theme)
        self._syncWebState()

    def setUnavailableText(self, text):
        """Set the translated fallback shown if the map provider fails."""
        self._unavailableText = str(text or '')
        self._updateOverlay()

    def setLoadingText(self, text):
        """Set the translated message used while map data or HTML is pending."""
        self._loadingText = str(text or '')
        self._updateOverlay()

    def _hasLocation(self):
        """Return whether the current result has a usable coordinate."""
        return (
            self._location is not None
            and self._location.latitude is not None
            and self._location.longitude is not None
        )

    def _ensureSourceLoaded(self):
        """Load the inert local map document once, when its panel becomes active."""
        if self._sourceLoaded:
            return

        self._sourceLoaded = True
        self.webView.setUrl(QtCore.QUrl.fromLocalFile(str(self.HtmlPath)))

    @QtCore.Slot(bool)
    def _loadFinished(self, successful):
        """Publish local-document failures and send the first map state."""
        self._documentLoaded = bool(successful)

        if not successful:
            self._mapError = self._unavailableText or 'Endpoint map unavailable'

            logger.error('failed to load the local endpoint map document')

        self._syncWebState()
        self._updateOverlay()

    @QtCore.Slot()
    def _mapBecameReady(self):
        """Show the persistent map after its initial vector style is ready."""
        self._mapReady = True
        self._mapError = ''
        self._syncWebState()
        self._updateOverlay()

    @QtCore.Slot(str)
    def _mapFailed(self, message):
        """Show a fallback if the initial vector map cannot become ready."""
        logger.error(f'endpoint map provider error: {message}')

        if not self._mapReady:
            self._mapError = message or self._unavailableText
            self._updateOverlay()

    @QtCore.Slot(QWebEnginePage.RenderProcessTerminationStatus, int)
    def _renderProcessTerminated(self, status, exitCode):
        """Convert an unexpected Chromium exit into the normal map fallback."""
        self._mapReady = False
        self._mapError = self._unavailableText or 'Endpoint map unavailable'

        logger.error(
            f'endpoint map render process terminated '
            f'({status}, exit code {exitCode})',
        )

        self._updateOverlay()

    @QtCore.Slot(str)
    def _openExternalLink(self, link):
        """Open only the static attribution providers used by the map style."""
        url = QtCore.QUrl(link)

        if (
            url.scheme().casefold() == 'https'
            and url.host().casefold() in self.TrustedAttributionHosts
        ):
            QtGui.QDesktopServices.openUrl(url)

    def _syncWebState(self):
        """Synchronize endpoint and theme state with the persistent web map."""
        if not self._documentLoaded:
            return

        hasLocation = self._hasLocation()
        location = self._location if hasLocation else None
        accentColor = self.palette().color(QtGui.QPalette.ColorRole.Highlight).name()
        font = QtGui.QFontInfo(self.font())

        state = {
            'markerVisible': hasLocation,
            'markerLatitude': float(location.latitude) if hasLocation else None,
            'markerLongitude': float(location.longitude) if hasLocation else None,
            'defaultGeographicZoom': self.DefaultGeographicZoom,
            'viewRevision': self._viewRevision,
            'darkMode': self._theme == AppStyleSheet.Dark,
            'lightStyleUrl': self.LightStyle.value,
            'darkStyleUrl': self.DarkStyle.value,
            'accentColor': accentColor,
            'loading': self._loading
            or (
                self._active
                and hasLocation
                and not self._mapReady
                and not self._mapError
            ),
            'loadingText': self._loadingText or self._message,
            'fontFamily': font.family(),
            'fontPointSize': font.pointSizeF(),
        }

        self._lastWebState = state

        script = (
            f'window.endpointMap && '
            f'window.endpointMap.setState({json.dumps(state)});'
        )

        self._runJavaScript(script)

    def _runJavaScript(self, script):
        """Run a state update on the one persistent local map document."""
        self.webView.page().runJavaScript(script)

    def _updateOverlay(self):
        """Present loading and fallback state without re-stacking the web view."""
        initializingMap = (
            self._active
            and self._hasLocation()
            and not self._mapReady
            and not self._mapError
        )
        loading = self._loading or initializingMap

        htmlLoadingAvailable = (
            self._active and self._sourceLoaded and not self._mapError and loading
        )
        mapAvailable = (
            self._active
            and self._hasLocation()
            and self._sourceLoaded
            and not self._mapError
        )

        showOverlay = not (htmlLoadingAvailable or mapAvailable)

        if loading:
            self.statusLabel.setText(self._loadingText or self._message)
        elif self._hasLocation() and self._mapError:
            self.statusLabel.setText(self._unavailableText)
        else:
            self.statusLabel.setText(self._message)

        self.statusOverlay.setVisible(showOverlay)

        self.loadingSpinner.color = self.palette().color(QtGui.QPalette.ColorRole.Text)

        if self._active and loading and showOverlay:
            self.loadingSpinner.start()
        else:
            self.loadingSpinner.stop()


class _ValueRow(QtCore.QObject):
    """Align one endpoint label, selectable value, and optional copy action."""

    copied = QtCore.Signal(str)

    def __init__(self, name, parent=None, *, copyable=False):
        """Initialize one compact information row."""
        super().__init__(parent)

        self.nameLabel = AppQLabel(name, parent=parent)
        self.nameLabel.setObjectName('EndpointFieldName')

        self.valueLabel = AppQLabel(translatable=False, parent=parent)
        self.valueLabel.setObjectName('EndpointFieldValue')
        self.valueLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.valueLabel.setWordWrap(True)
        self.valueLabel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.copyButton = None
        self._loading = False
        self._animationsEnabled = False

        self.valueContainer = QWidget(parent)
        self.valueContainer.setObjectName('EndpointFieldValueContainer')

        self.loadingSpinner = WaitingSpinner(
            self.valueContainer,
            center_on_parent=False,
            line_length=3,
            line_width=2,
            radius=3,
            lines=10,
        )
        self.loadingSpinner.setFixedSize(16, 16)

        valueLayout = QHBoxLayout(self.valueContainer)
        valueLayout.setContentsMargins(0, 0, 0, 0)
        valueLayout.setSpacing(6)
        valueLayout.addWidget(
            self.loadingSpinner,
            0,
            QtCore.Qt.AlignmentFlag.AlignVCenter,
        )
        valueLayout.addWidget(self.valueLabel, 1)

        if copyable:
            self.copyButton = AppQPushButton(
                icon=bootstrapIcon('files.svg'),
                toolTip=_('Copy'),
                parent=parent,
            )
            self.copyButton.setObjectName('EndpointCopyButton')
            self.copyButton.setFixedSize(34, 30)
            self.copyButton.clicked.connect(self._copy)

    def addToLayout(self, layout: QGridLayout, row: int):
        """Insert this row into the card's shared label/value grid."""
        if self.copyButton is not None:
            nameAlignment = QtCore.Qt.AlignmentFlag.AlignVCenter
        else:
            nameAlignment = QtCore.Qt.AlignmentFlag.AlignTop

        layout.addWidget(
            self.nameLabel,
            row,
            0,
            nameAlignment,
        )
        layout.addWidget(self.valueContainer, row, 1)

        if self.copyButton is not None:
            layout.addWidget(
                self.copyButton,
                row,
                2,
                QtCore.Qt.AlignmentFlag.AlignTop,
            )

    @QtCore.Slot()
    def _copy(self):
        """Copy the currently displayed value through the application clipboard."""
        value = self.valueLabel.text().strip()

        if value and value != '—':
            QApplication.clipboard().setText(value)

            self.copied.emit(value)

    def setValue(self, value, emptyText='—', *, loading=False):
        """Set the row value and copy availability."""
        available = bool(value)

        self._loading = bool(loading)
        self.valueLabel.setText(str(value or emptyText))
        self._syncLoadingAnimation()

        if self.copyButton is not None:
            self.copyButton.setEnabled(available and not self._loading)

    def setAnimationsEnabled(self, enabled):
        """Run the persistent row spinner only while its page is visible."""
        self._animationsEnabled = bool(enabled)
        self._syncLoadingAnimation()

    def _syncLoadingAnimation(self):
        """Apply the current loading and page-visibility state."""
        self.loadingSpinner.color = self.valueContainer.palette().color(
            QtGui.QPalette.ColorRole.Text
        )

        if self._loading and self._animationsEnabled:
            self.loadingSpinner.start()
        else:
            self.loadingSpinner.stop()


class EndpointInfoWidget(Mixins.ThemeAware, Mixins.QTranslatable, QFrame):
    """Display observed public addresses and approximate egress location."""

    def __init__(self, service, parent=None):
        """Build a long-lived view over one independently owned lookup service."""
        super().__init__(parent)

        self.service = service
        self.setObjectName('MetricsSection')
        self.setMinimumHeight(360)

        self.titleLabel = AppQLabel(_('Proxy Endpoint Information'), parent=self)
        self.titleLabel.setObjectName('MetricsSectionTitle')

        self.refreshButton = AppQPushButton(
            _('Refresh'),
            icon=bootstrapIcon('arrow-clockwise.svg'),
            toolTip=_('Refresh'),
            parent=self,
        )
        self.refreshButton.clicked.connect(self._refresh)

        titleLayout = QHBoxLayout()
        titleLayout.setContentsMargins(0, 0, 0, 0)
        titleLayout.setSpacing(8)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch(1)
        titleLayout.addWidget(self.refreshButton)

        self.infoCard = QFrame(self)
        self.infoCard.setObjectName('MetricCard')

        self._unboundedInfoCardMaximumWidth = self.infoCard.maximumWidth()

        self.infoCard.setMinimumWidth(380)
        self.infoCard.setMaximumWidth(560)
        self.infoCard.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )

        self.ipv4Row = _ValueRow('IPv4', self.infoCard, copyable=True)
        self.ipv6Row = _ValueRow('IPv6', self.infoCard, copyable=True)
        self.countryRow = _ValueRow(_('Country'), self.infoCard)
        self.locationRow = _ValueRow(_('Approximate Location'), self.infoCard)
        self.organizationRow = _ValueRow(_('Organization'), self.infoCard)

        self.noteLabel = AppQLabel(
            _('Location is estimated from the public IP and may be inaccurate.'),
            parent=self.infoCard,
        )
        self.noteLabel.setObjectName('EndpointNoteLabel')
        self.noteLabel.setWordWrap(True)

        informationLayout = QGridLayout()
        informationLayout.setContentsMargins(0, 0, 0, 0)
        informationLayout.setHorizontalSpacing(14)
        informationLayout.setVerticalSpacing(10)
        informationLayout.setColumnStretch(1, 1)

        for rowIndex, row in enumerate(
            (
                self.ipv4Row,
                self.ipv6Row,
                self.countryRow,
                self.locationRow,
                self.organizationRow,
            )
        ):
            row.addToLayout(informationLayout, rowIndex)

        infoLayout = QVBoxLayout(self.infoCard)
        infoLayout.setContentsMargins(16, 14, 16, 14)
        infoLayout.setSpacing(14)
        infoLayout.addLayout(informationLayout)
        infoLayout.addStretch(1)
        infoLayout.addWidget(self.noteLabel)

        self.mapCard = QFrame(self)
        self.mapCard.setObjectName('MetricCard')

        self.mapTitleLabel = AppQLabel(_('Approximate Location'), parent=self.mapCard)
        self.mapTitleLabel.setObjectName('MetricCardTitle')

        self.mapWidget = _EndpointMapWidget(self.mapCard)

        mapLayout = QVBoxLayout(self.mapCard)
        mapLayout.setContentsMargins(14, 12, 14, 12)
        mapLayout.setSpacing(8)
        mapLayout.addWidget(self.mapTitleLabel)
        mapLayout.addWidget(self.mapWidget, 1)

        self.bodyLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(12)
        self.bodyLayout.addWidget(self.infoCard, 1)
        self.bodyLayout.addWidget(self.mapCard, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addLayout(titleLayout)
        layout.addLayout(self.bodyLayout)

        self.service.stateChanged.connect(self._updatePresentation)
        self.service.resultChanged.connect(self._updatePresentation)

        self.retranslate()

    @QtCore.Slot()
    def _refresh(self):
        """Refresh endpoint data while retaining a completed map underneath."""
        self.mapWidget.beginRefresh()
        self.service.refresh()

        if self.service.state is not EndpointInfoState.Loading:
            self._updatePresentation()

    @QtCore.Slot()
    @QtCore.Slot(object)
    def _updatePresentation(self, _value=None):
        """Render one immutable service snapshot without starting network work."""
        state = self.service.state
        result: EndpointInfo = self.service.result
        location = result.location

        self.refreshButton.setEnabled(
            state in (EndpointInfoState.Ready, EndpointInfoState.Failed)
        )

        ipv4Loading, ipv6Loading, mapLoading = (
            state is EndpointInfoState.Loading and not result.ipv4Resolved,
            state is EndpointInfoState.Loading and not result.ipv6Resolved,
            state is EndpointInfoState.Loading,
        )

        locationLoading = mapLoading and not result.locationResolved

        self.ipv4Row.setValue(
            result.ipv4,
            _('Detecting...') if ipv4Loading else _('Not available'),
            loading=ipv4Loading,
        )
        self.ipv6Row.setValue(
            result.ipv6,
            _('Detecting...') if ipv6Loading else _('Not available'),
            loading=ipv6Loading,
        )

        country = location.countryName

        if country and location.countryCode:
            country = f'{country} ({location.countryCode})'
        elif location.countryCode:
            country = location.countryCode

        self.countryRow.setValue(
            country,
            _('Detecting...') if locationLoading else _('Unknown'),
            loading=locationLoading,
        )
        self.locationRow.setValue(
            location.displayName,
            _('Detecting...') if locationLoading else _('Not available'),
            loading=locationLoading,
        )
        self.organizationRow.setValue(
            location.organization,
            _('Detecting...') if locationLoading else _('Not available'),
            loading=locationLoading,
        )

        if mapLoading:
            mapMessage = _('Detecting...')
        elif location.latitude is None or location.longitude is None:
            mapMessage = _('Approximate location unavailable')
        else:
            mapMessage = ''

        self.mapWidget.setLocation(location, mapMessage, loading=mapLoading)
        self._setLoadingAnimationsEnabled(self.isVisible())

    def _setLoadingAnimationsEnabled(self, enabled):
        """Start only the persistent loading indicators currently on screen."""
        for row in (
            self.ipv4Row,
            self.ipv6Row,
            self.countryRow,
            self.locationRow,
            self.organizationRow,
        ):
            row.setAnimationsEnabled(enabled)

    def themeChangedCallback(self, theme=None):
        """Switch the embedded map to the resolved application theme."""
        self.mapWidget.updateTheme(theme)

    def resizeEvent(self, event):
        """Stack cards only when side-by-side fields would become unreadable."""
        direction = (
            QBoxLayout.Direction.TopToBottom
            if event.size().width() < 760
            else QBoxLayout.Direction.LeftToRight
        )

        if self.bodyLayout.direction() is not direction:
            self.bodyLayout.setDirection(direction)

        self.infoCard.setMaximumWidth(
            self._unboundedInfoCardMaximumWidth
            if direction is QBoxLayout.Direction.TopToBottom
            else 560
        )

        super().resizeEvent(event)

    def showEvent(self, event):
        """Resume the lightweight activity indicator only while visible."""
        super().showEvent(event)

        self.mapWidget.setActive(True)
        self._setLoadingAnimationsEnabled(True)

    def hideEvent(self, event):
        """Avoid animating a spinner on a hidden Metrics page."""
        self.mapWidget.setActive(False)
        self._setLoadingAnimationsEnabled(False)

        super().hideEvent(event)

    def retranslate(self):
        """Refresh state-dependent endpoint presentation copy."""
        self.mapWidget.setLoadingText(_('Detecting...'))
        self.mapWidget.setUnavailableText(_('Approximate location unavailable'))

        self._updatePresentation()
