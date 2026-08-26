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

"""Exercise high-value Qt presentation and editor integration boundaries."""

from __future__ import annotations

from Furious.Backends.Configuration import (
    ConfigXray,
    configXrayEmptyProxyOutboundObject,
)
from Furious.Backends.ExternalCore.Configuration import (
    BLANK_CONFIG_EXTERNAL_CORE,
    ConfigExternalCore,
)
from Furious.Backends.ExternalCore.Editor import (
    ExternalCoreApplicationTun2socksInput,
    ExternalCoreArgumentsInput,
    ExternalCoreConfigurationGroup,
    ExternalCoreEditor,
    ExternalCoreEnvironmentInput,
    ExternalCoreOtherGroup,
    ExternalCoreTunRemoteAddressInput,
)
from Furious.Backends.Hysteria1.Editor import Hysteria1Editor
from Furious.Backends.Hysteria2.Editor import Hysteria2Editor
from Furious.Backends.Xray.AssetListView import XrayAssetListView
from Furious.Backends.Xray.RoutingWindow import (
    RoutingRuleEditDialog,
    RoutingRulesDialog,
    RoutingTextEdit,
    RoutingTextEditDialog,
)
from Furious.Backends.Xray.ShadowsocksEditor import ShadowsocksEditor
from Furious.Backends.Xray.SocksEditor import SocksEditor
from Furious.Backends.Xray.TrojanEditor import TrojanEditor
from Furious.Backends.Xray.TransportEditor import (
    GuiVTransportPageXHttp,
    GuiVTransportQGroupBox,
    STREAM_NETWORK,
)
from Furious.Backends.Xray.VlessEditor import (
    GuiVLESSGroupBoxBasic,
    VlessEditor,
)
from Furious.Backends.Xray.VmessEditor import (
    GuiVMessGroupBoxBasic,
    VmessEditor,
)
from Furious.Actions.Connection import ConnectAction
from Furious.Controllers.ConnectionController import (
    ConnectionError,
    ConnectionController,
    ConnectionState,
)
from Furious.Controllers.SettingsController import (
    APPLICATION_THEME_SETTING,
    LOG_AUTO_CLEAR_SETTING,
    LOG_AUTO_SCROLL_DOWN_SETTING,
)
from Furious.Frozenlib import (
    APPLICATION_NAME,
    AppBuiltinProxyMode,
    ApplicationTheme,
    AppSettings,
    Mixins,
)
from Furious.Models import ProfileMetadata, Protocol, ServerProfile
from Furious.Plugins.API import RoutingOption
from Furious.Qt import (
    AppHue,
    AppQComboBox,
    AppQDialog,
    AppQMessageBox,
    AppQSwitch,
    AppStyleSheet,
    gettext as _,
)
from Furious.Service import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)
from Furious.Window.LogPage import LogPage
from Furious.Window.QRCodeWindow import (
    QRCodeWindow,
    _QRCodePage,
    createQRCodeImage,
)
from Furious.Window.SettingsPage import (
    _ApplicationThemeSettingsCard,
    _SystemProxySettingsCard,
    SettingsPage,
)
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog
from Furious.Widget.ConnectionButton import ConnectionButton
from Furious.Widget.RoutingSelector import RoutingSelector

from PySide6 import QtCore
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QVBoxLayout,
    QWidget,
)

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
    waitFor,
)

import copy
import pathlib
import tempfile
import unittest
import weakref

from unittest import mock
import segno
import zxingcpp


class RoutingControllerFixture(QtCore.QObject):
    """Provide routing state without persistence or connection side effects."""

    stateChanged = QtCore.Signal(object, str)
    interactionEnabledChanged = QtCore.Signal(bool)

    def __init__(self, options, routing):
        """Initialize one immutable selector state."""
        super().__init__()

        self._options = tuple(options)
        self._routing = routing
        self.interactionEnabled = True
        self.selected = []

    def state(self):
        """Return the current options and semantic selection."""
        return self._options, self._routing

    def refresh(self, *, force=False):
        """Return state without consulting plugins or reconnecting."""
        if force:
            self.stateChanged.emit(*self.state())

        return self.state()

    def selectRouting(self, routing):
        """Record explicit user selection attempts."""
        self.selected.append(routing)


class ComboTranslationLayoutTest(unittest.TestCase):
    """Verify translated content can republish useful combo width hints."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish deferred widget deletion between tests."""
        collectAtBoundary()

    def assertCurrentComboTextFits(self, comboBox):
        """Assert the styled combo edit field can display its current text."""
        option = QStyleOptionComboBox()
        comboBox.initStyleOption(option)
        textRect = comboBox.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            comboBox,
        )

        self.assertGreaterEqual(
            textRect.width(),
            comboBox.fontMetrics().horizontalAdvance(comboBox.currentText()),
        )

    def testContentAwareComboRefreshesHintWithoutChangingSemanticData(self):
        """Grow for longer translated text while retaining item identity."""
        parent = QWidget()
        layout = QHBoxLayout(parent)
        combo = AppQComboBox(parent=parent)
        combo.setContentWidthAdjustable()
        combo.addItem('Short', 'semantic-route')
        layout.addWidget(combo)

        shortHint = combo.sizeHint().width()
        translated = 'A significantly longer translated routing option'

        with mock.patch(
            'Furious.Qt.QtWidgets._',
            side_effect=lambda text: translated if text == 'Short' else text,
        ):
            combo.retranslate()

        parent.resize(combo.sizeHint().width() + 100, 100)
        parent.show()
        processQtEvents()

        self.assertEqual(combo.currentData(), 'semantic-route')
        self.assertEqual(combo.currentText(), translated)
        self.assertGreater(combo.sizeHint().width(), shortHint)
        self.assertGreater(
            combo.sizeHint().width(),
            combo.fontMetrics().horizontalAdvance(translated),
        )
        self.assertGreaterEqual(combo.width(), combo.sizeHint().width())

        parent.close()
        parent.deleteLater()

    def testRoutingRetranslationKeepsSelectionAndDoesNotReconnect(self):
        """Rebuild display text without forwarding a synthetic selection."""
        option = RoutingOption(
            'bypass-mainland',
            'Bypass Mainland China',
            translatable=True,
        )
        controller = RoutingControllerFixture((option,), option.id)
        parent = QWidget()
        layout = QHBoxLayout(parent)

        with mock.patch(
            'Furious.Widget.RoutingSelector.AppRoutingController',
            return_value=controller,
        ):
            selector = RoutingSelector(parent=parent)

        layout.addWidget(selector)
        initialHint = selector.sizeHint().width()
        translated = 'Обходить подключения к серверам материкового Китая'

        with mock.patch(
            'Furious.Widget.RoutingSelector._',
            side_effect=lambda text: (
                translated if text == option.displayName else text
            ),
        ):
            selector.retranslate()

        parent.resize(selector.sizeHint().width() + 100, 100)
        parent.show()
        processQtEvents()

        self.assertEqual(selector.currentData(), option.id)
        self.assertEqual(selector.currentText(), translated)
        self.assertGreater(selector.sizeHint().width(), initialHint)
        self.assertGreater(
            selector.sizeHint().width(),
            selector.fontMetrics().horizontalAdvance(translated),
        )
        self.assertEqual(controller.selected, [])

        parent.close()
        parent.deleteLater()

    def testTranslatedSettingsChoicesResizeWithoutChangingSemanticValues(self):
        """Resize translated Settings choices without applying fake changes."""
        cases = (
            (
                _ApplicationThemeSettingsCard,
                APPLICATION_THEME_SETTING,
                ApplicationTheme.System.value,
                'Follow System Appearance',
                'setApplicationTheme',
            ),
            (
                _SystemProxySettingsCard,
                'SystemProxyMode',
                AppBuiltinProxyMode.Auto.value,
                'Automatically Configure System Proxy',
                'setSystemProxyMode',
            ),
        )

        with isolatedSettings(), mock.patch(
            'Furious.Window.SettingsPage.AppSettingsController'
        ) as controllerFactory:
            for cardType, settingName, semanticValue, sourceText, callbackName in cases:
                AppSettings.set('Language', 'EN')
                AppSettings.set(settingName, semanticValue)
                parent = QWidget()
                layout = QHBoxLayout(parent)
                card = cardType(parent=parent)
                layout.addWidget(card)
                parent.resize(1800, 120)
                parent.show()
                processQtEvents()

                comboBox = card.comboBox
                callback = getattr(controllerFactory.return_value, callbackName)
                indexChanges = []
                comboBox.currentIndexChanged.connect(indexChanges.append)

                self.assertEqual(
                    comboBox.sizeAdjustPolicy(),
                    QComboBox.SizeAdjustPolicy.AdjustToContents,
                )

                for language in ('EN', 'ZH', 'RU'):
                    AppSettings.set('Language', language)
                    comboBox.retranslate()
                    processQtEvents()

                    self.assertEqual(comboBox.currentData(), semanticValue)
                    self.assertEqual(comboBox.currentText(), _(sourceText, language))
                    self.assertCurrentComboTextFits(comboBox)

                callback.assert_not_called()
                self.assertEqual(indexChanges, [])

                parent.close()
                parent.deleteLater()


class SettingsPageOrganizationTest(unittest.TestCase):
    """Protect General/Application membership and existing action delegation."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish deferred Settings-page deletion between tests."""
        collectAtBoundary()

    def buildPage(self, *, platform='Windows', flatpakID=''):
        """Build one isolated Settings page for the requested platform state."""
        callbacks = {
            'checkForUpdates': mock.Mock(),
            'openAboutPage': mock.Mock(),
            'restartAsAdmin': mock.Mock(),
            'openApplicationFolder': mock.Mock(),
        }
        proxyBypassDialog = mock.Mock()
        networkTestDialog = mock.Mock()

        with (
            isolatedSettings(),
            mock.patch('Furious.Window.SettingsPage.PLATFORM', platform),
            mock.patch(
                'Furious.Window.SettingsPage.SystemRuntime.isAdmin',
                return_value=False,
            ),
            mock.patch(
                'Furious.Window.SettingsPage.SystemRuntime.flatpakID',
                return_value=flatpakID,
            ),
            mock.patch(
                'Furious.Window.SettingsPage.SystemRuntime.isAssetsFolderWritable',
                return_value=False,
            ),
            mock.patch(
                'Furious.Window.SettingsPage.AppSettings.isStateON_',
                return_value=False,
            ),
            mock.patch.object(SettingsPage, '_buildPluginSections'),
            mock.patch('Furious.Window.SettingsPage.AppSettingsController'),
        ):
            page = SettingsPage(
                tunSettingsDialogFactory=mock.Mock(),
                proxyBypassDialog=proxyBypassDialog,
                networkTestDialog=networkTestDialog,
                **callbacks,
            )

        return page, callbacks

    def testGeneralEndsWithSystemAndEnvironmentActions(self):
        """Keep preferences first and Application focused on maintenance/about."""
        page, _callbacks = self.buildPage()

        expectedGeneralCards = [
            page.tunModeCard,
            page.applicationThemeCard,
            page.languageCard,
            page.monochromeCard,
            page.startupCard,
            page.powerSaveCard,
            page.restartCard,
            page.openFolderCard,
        ]

        self.assertEqual(page.generalSection.cards, expectedGeneralCards)
        self.assertEqual(
            page.applicationSection.cards,
            [page.updateCard, page.aboutCard],
        )
        self.assertEqual(
            [
                page.generalSection.layout.itemAt(index + 1).widget()
                for index in range(len(expectedGeneralCards))
            ],
            expectedGeneralCards,
        )
        self.assertTrue(
            all(card.parent() is page.generalSection for card in expectedGeneralCards)
        )

        page.close()
        page.deleteLater()

    def testMovedCardsKeepTheirInjectedActions(self):
        """Move presentation without replacing restart or folder behavior."""
        page, callbacks = self.buildPage()

        page.restartCard.button.click()
        page.openFolderCard.button.click()

        callbacks['restartAsAdmin'].assert_called_once_with()
        callbacks['openApplicationFolder'].assert_called_once_with()
        callbacks['checkForUpdates'].assert_not_called()
        callbacks['openAboutPage'].assert_not_called()

        page.close()
        page.deleteLater()

    def testMovedCardsPreservePlatformVisibility(self):
        """Retain the existing restart, Darwin, and Flatpak visibility gates."""
        cases = (
            ('Windows', '', True, True),
            ('Darwin', '', True, False),
            ('Linux', '', False, True),
            ('Linux', 'io.github.LorenEteval.Furious', False, False),
        )

        for platform, flatpakID, hasRestart, hasOpenFolder in cases:
            with self.subTest(platform=platform, flatpakID=flatpakID):
                page, _callbacks = self.buildPage(
                    platform=platform,
                    flatpakID=flatpakID,
                )

                self.assertEqual(page.restartCard is not None, hasRestart)
                self.assertEqual(page.openFolderCard is not None, hasOpenFolder)

                for card in (page.restartCard, page.openFolderCard):
                    if card is not None:
                        self.assertIn(card, page.generalSection.cards)
                        self.assertNotIn(card, page.applicationSection.cards)

                page.close()
                page.deleteLater()


def _grayscaleBuffer(image: QImage):
    """Return tightly packed grayscale pixels for zxing-cpp without Pillow."""
    grayscale = image.convertToFormat(QImage.Format.Format_Grayscale8)
    width = grayscale.width()
    height = grayscale.height()
    stride = grayscale.bytesPerLine()
    source = grayscale.constBits()
    pixels = bytearray(width * height)

    for y in range(height):
        sourceStart = y * stride
        targetStart = y * width
        pixels[targetStart : targetStart + width] = source[
            sourceStart : sourceStart + width
        ]

    return memoryview(pixels).cast('B', (height, width))


def _decodeQRCodeImage(image: QImage):
    """Decode one generated image through the application's QR decoder."""
    return zxingcpp.read_barcode(
        _grayscaleBuffer(image),
        formats=zxingcpp.BarcodeFormat.QRCode,
        is_pure=True,
    )


class QRCodeImageGenerationTest(unittest.TestCase):
    """Verify the pure Segno matrix-to-QImage contract."""

    def testLogicalImageMatchesSegnoMatrixAndQuietZone(self):
        """Map matrix modules and the standard quiet zone to exact pixels."""
        payload = 'socks://user:password@example.com:1080#Matrix'
        qrCode = segno.make_qr(payload, error='H')
        border = qrCode.default_border_size
        matrix = tuple(tuple(row) for row in qrCode.matrix)
        image = createQRCodeImage(payload)

        self.assertFalse(qrCode.is_micro)
        self.assertEqual(border, 4)
        self.assertEqual(
            image.size(),
            QtCore.QSize(*qrCode.symbol_size(scale=1, border=border)),
        )
        self.assertEqual(image.format(), QImage.Format.Format_Grayscale8)
        self.assertEqual(image.width(), len(matrix) + (2 * border))
        self.assertTrue(
            all(image.pixelColor(x, 0).red() == 255 for x in range(image.width()))
        )

        darkY, darkX = next(
            (y, x)
            for y, row in enumerate(matrix)
            for x, module in enumerate(row)
            if module
        )
        lightY, lightX = next(
            (y, x)
            for y, row in enumerate(matrix)
            for x, module in enumerate(row)
            if not module
        )

        self.assertEqual(image.pixelColor(border + darkX, border + darkY).red(), 0)
        self.assertEqual(image.pixelColor(border + lightX, border + lightY).red(), 255)

    def testRepresentativePayloadsRoundTripWithoutEncodedIntermediate(self):
        """Decode short, medium, long, special-character, and Unicode payloads."""
        payloads = (
            'socks://example.com:1080',
            (
                'vless://synthetic@example.com:443?'
                + 'transport=xhttp&security=reality&' * 8
                + '#Medium%20Profile'
            ),
            'trojan://p%40ss%3Aword@example.com:443?allowInsecure=0#东京-Привет',
            'vmess://' + ('synthetic-payload-' * 45),
        )

        widths = []

        for payload in payloads:
            image = createQRCodeImage(payload)
            scale = 4
            scaled = image.scaled(
                image.width() * scale,
                image.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.FastTransformation,
            )
            decoded = _decodeQRCodeImage(scaled)

            self.assertIsNotNone(decoded)
            self.assertEqual(decoded.text, payload)
            widths.append(image.width())

        self.assertGreater(len(set(widths)), 1)

    def testIntegerFastScalingKeepsPixelsBinary(self):
        """Keep modules and quiet zone black or white at integer display scales."""
        image = createQRCodeImage('socks://scale.example:1080#Scale')

        for scale in (2, 5, 8):
            scaled = image.scaled(
                image.width() * scale,
                image.height() * scale,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.FastTransformation,
            )
            pixels = _grayscaleBuffer(scaled)

            self.assertEqual(scaled.width(), image.width() * scale)
            self.assertEqual(set(pixels.tobytes()), {0, 255})
            self.assertTrue(
                all(
                    pixels[y, x] == 255
                    for y in range(4 * scale)
                    for x in range(scaled.width())
                )
            )

    def testEmptyPayloadIsRejected(self):
        """Reject an empty payload before asking Segno to encode it."""
        with self.assertRaises(ValueError):
            createQRCodeImage('')


class QRCodeWindowBehaviorTest(unittest.TestCase):
    """Verify responsive QR presentation without changing export semantics."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish deferred page and window deletion between tests."""
        collectAtBoundary()

    @staticmethod
    def buildWindow(*uris):
        """Create one isolated QR window from deterministic export results."""
        profiles = [
            mock.Mock(itemRemark=f'Profile {index + 1}') for index in range(len(uris))
        ]

        with mock.patch(
            'Furious.Window.QRCodeWindow.Storage.UserServers',
            return_value=profiles,
        ), mock.patch(
            'Furious.Window.QRCodeWindow.exportConfiguration',
            side_effect=uris,
        ):
            window = QRCodeWindow()
            window.initTabByIndex(list(range(len(profiles))))

        return window

    def testAllExportFailuresLeaveNoBrokenTabs(self):
        """Leave an unshown empty window when every canonical export fails."""
        window = self.buildWindow('', '')

        self.assertEqual(window.tabCount(), 0)
        self.assertFalse(window.isVisible())
        window.close()

    def testOversizedPayloadDoesNotPreventOtherTabs(self):
        """Skip one Segno overflow while preserving later valid profiles."""
        with self.assertLogs('Furious.Window.QRCodeWindow', level='WARNING'):
            window = self.buildWindow(
                'x' * 5000,
                'socks://valid.example:1080#Valid',
            )

        self.assertEqual(window.tabCount(), 1)
        self.assertEqual(window.tabWidget.tabText(0), '2 - Profile 2')
        window.close()

    def testPageCentersAndDecodesResponsiveSquarePixmap(self):
        """Center one crisp, square, decodable QR at representative sizes."""
        uri = (
            'socks://user:password@example.com:1080'
            '#A%20representative%20Furious%20profile'
        )
        window = self.buildWindow(uri)
        window.show()
        processQtEvents()

        page = window.tabWidget.widget(0)

        self.assertIsInstance(page, _QRCodePage)
        self.assertIsInstance(page.layout(), QVBoxLayout)
        self.assertTrue(
            page.layout().itemAt(0).alignment() & QtCore.Qt.AlignmentFlag.AlignHCenter
        )
        self.assertTrue(
            page.layout().itemAt(0).alignment() & QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.assertTrue(page.qrLabel.alignment() & QtCore.Qt.AlignmentFlag.AlignCenter)

        sourceKey = page.sourceImage().cacheKey()
        displayedSides = []

        for size in (
            QRCodeWindow.MINIMUM_WINDOW_SIZE,
            QRCodeWindow.DEFAULT_WINDOW_SIZE,
            QtCore.QSize(920, 780),
        ):
            window.resize(size)
            processQtEvents()

            displayed = page.qrLabel.pixmap()
            available = page.layout().contentsRect().size()

            self.assertFalse(displayed.isNull())
            self.assertEqual(displayed.width(), displayed.height())
            self.assertEqual(displayed.width() % page.moduleSpan(), 0)
            self.assertLessEqual(displayed.width(), available.width())
            self.assertLessEqual(displayed.height(), available.height())
            self.assertEqual(displayed.width(), page.moduleSpan() * page.displayScale())
            self.assertEqual(page.sourceImage().cacheKey(), sourceKey)

            displayedSides.append(displayed.width())

        self.assertEqual(displayedSides, sorted(displayedSides))
        decoded = _decodeQRCodeImage(page.qrLabel.pixmap().toImage())
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.text, uri)

        window.close()

    def testEveryTabUsesItsSettledLayoutScaleOnFirstVisit(self):
        """Size hidden QR pages correctly the first time each tab becomes visible."""
        uris = tuple(
            f'socks://profile-{index}.example:1080#Profile%20{index}'
            for index in range(10)
        )
        window = self.buildWindow(*uris)
        window.show()
        processQtEvents()

        for index in range(window.tabCount()):
            window.tabWidget.setCurrentIndex(index)
            processQtEvents()

            page = window.tabWidget.widget(index)
            displayed = page.qrLabel.pixmap()
            available = page.layout().contentsRect().size()
            expectedScale = max(
                1,
                min(available.width(), available.height()) // page.moduleSpan(),
            )

            self.assertFalse(displayed.isNull())
            self.assertGreater(expectedScale, 1)
            self.assertEqual(page.displayScale(), expectedScale)
            self.assertEqual(displayed.width(), page.moduleSpan() * expectedScale)

        window.close()

    def testMultipleTabsSkipFailuresAndDestroyClosedPages(self):
        """Keep valid order while failed exports and closed pages leave no debris."""
        window = self.buildWindow(
            'socks://one.example:1080#One',
            '',
            'socks://three.example:1080#Three',
        )
        window.show()
        processQtEvents()

        self.assertEqual(window.tabCount(), 2)
        self.assertEqual(window.tabWidget.tabText(0), '1 - Profile 1')
        self.assertEqual(window.tabWidget.tabText(1), '3 - Profile 3')

        self.assertEqual(window.tabWidget.tabToolTip(0), '1 - Profile 1')
        self.assertEqual(window.tabWidget.tabToolTip(1), '3 - Profile 3')
        firstPage = window.tabWidget.widget(0)
        firstPageReference = weakref.ref(firstPage)
        firstPageDestroyed = []
        firstPage.destroyed.connect(lambda *_args: firstPageDestroyed.append(True))

        window.handleTabCloseRequested(0)
        del firstPage
        collectAtBoundary()

        self.assertEqual(window.tabCount(), 1)
        self.assertEqual(window.tabWidget.tabText(0), '3 - Profile 3')
        self.assertTrue(waitFor(lambda: firstPageReference() is None))
        self.assertEqual(firstPageDestroyed, [True])

        windowReference = weakref.ref(window)
        windowDestroyed = []
        window.destroyed.connect(lambda *_args: windowDestroyed.append(True))

        window.handleTabCloseRequested(0)
        del window
        collectAtBoundary()

        self.assertTrue(waitFor(lambda: windowReference() is None))
        self.assertEqual(windowDestroyed, [True])

    def testThemeChangesLeaveTheHighContrastQRSourceUntouched(self):
        """Restyle the surrounding window without regenerating its QR content."""
        app = application()
        originalStyleSheet = app.styleSheet()
        window = self.buildWindow('socks://theme.example:1080#Theme')
        window.show()
        processQtEvents()

        page = window.tabWidget.widget(0)
        sourceKey = page.sourceImage().cacheKey()

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                app.setStyleSheet(AppStyleSheet.forTheme(theme))
                processQtEvents()

                image = page.sourceImage()
                quietZone = image.pixelColor(0, 0)

                self.assertEqual(page.sourceImage().cacheKey(), sourceKey)
                self.assertEqual(
                    (quietZone.red(), quietZone.green(), quietZone.blue()),
                    (255, 255, 255),
                )
        finally:
            app.setStyleSheet(originalStyleSheet)
            window.close()


class EditorMappingTest(unittest.TestCase):
    """Verify editor fields preserve structured configuration semantics."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish every deferred transient deletion between tests."""
        collectAtBoundary()

    @staticmethod
    def xrayProfile(protocol: Protocol, user: dict) -> ServerProfile:
        """Return one minimal Xray profile for a basic-editor round trip."""
        outbound = configXrayEmptyProxyOutboundObject(protocol)
        server = outbound['settings']['vnext'][0]

        server['address'] = 'server.example.com'
        server['port'] = 443
        server['users'][0].update(user)

        return ServerProfile.fromConfiguration(
            ConfigXray({'outbounds': [outbound]}),
            ProfileMetadata(displayName='Fixture profile'),
        )

    def assertBindingPosition(
        self,
        layout,
        binding,
        row: int,
        labelColumn: int,
        inputColumn: int,
        inputColumnSpan: int = 1,
    ):
        """Assert one binding's logical grid placement without pixel geometry."""
        label, inputWidget = binding.widgets()

        self.assertEqual(
            layout.getItemPosition(layout.indexOf(label)),
            (row, labelColumn, 1, 1),
        )
        self.assertEqual(
            layout.getItemPosition(layout.indexOf(inputWidget)),
            (row, inputColumn, 1, inputColumnSpan),
        )

    def testVlessBasicUsesTlsGridRowsWithoutChangingMapping(self):
        """Pair address/port and encryption/flow around full-width fields."""
        profile = self.xrayProfile(
            Protocol.VLESS,
            {
                'id': 'fixture-vless-id',
                'encryption': 'none',
                'flow': 'future-vless-flow',
            },
        )
        original = copy.deepcopy(profile.connection)
        group = GuiVLESSGroupBoxBasic()
        layout = group._widget.currentWidget().layout()

        group.factoryToInput(profile)

        self.assertFalse(group.inputToFactory(profile))
        self.assertEqual(profile.connection, original)
        self.assertBindingPosition(layout, group._containers[0], 0, 0, 1, 3)
        self.assertBindingPosition(layout, group._containers[1], 1, 0, 1)
        self.assertBindingPosition(layout, group._containers[2], 1, 2, 3)
        self.assertBindingPosition(layout, group._containers[3], 2, 0, 1, 3)
        self.assertBindingPosition(layout, group._containers[4], 3, 0, 1)
        self.assertBindingPosition(layout, group._containers[5], 3, 2, 3)
        self.assertEqual(group._containers[4].text(), 'none')
        self.assertEqual(group._containers[5].text(), 'future-vless-flow')

        group.deleteLater()

    def testVmessBasicUsesTlsGridRowsWithoutChangingMapping(self):
        """Pair address/port and security/alterId around the UUID row."""
        profile = self.xrayProfile(
            Protocol.VMess,
            {
                'id': 'fixture-vmess-id',
                'security': 'future-vmess-security',
                'alterId': 17,
            },
        )
        original = copy.deepcopy(profile.connection)
        group = GuiVMessGroupBoxBasic()
        layout = group._widget.currentWidget().layout()

        group.factoryToInput(profile)

        self.assertFalse(group.inputToFactory(profile))
        self.assertEqual(profile.connection, original)
        self.assertBindingPosition(layout, group._containers[0], 0, 0, 1, 3)
        self.assertBindingPosition(layout, group._containers[1], 1, 0, 1)
        self.assertBindingPosition(layout, group._containers[2], 1, 2, 3)
        self.assertBindingPosition(layout, group._containers[3], 2, 0, 1, 3)
        self.assertBindingPosition(layout, group._containers[5], 3, 0, 1)
        self.assertBindingPosition(layout, group._containers[4], 3, 2, 3)
        self.assertEqual(group._containers[5].text(), 'future-vmess-security')
        self.assertEqual(group._containers[4].value(), 17)

        group.deleteLater()

    def testXHttpHostAndPathShareOneRowWithoutChangingMapping(self):
        """Pair xhttp Host/Path while preserving switching and configuration."""
        profile = self.xrayProfile(
            Protocol.VLESS,
            {
                'id': 'fixture-xhttp-id',
                'encryption': 'none',
                'flow': '',
            },
        )
        streamSettings = ConfigXray.getProxyOutboundStream(profile.connection)
        streamSettings.update(
            {
                'network': 'xhttp',
                'xhttpSettings': {
                    'host': 'cdn.example.com',
                    'path': '/a/representative/xhttp/path',
                    'mode': 'auto',
                    'extra': {'noGRPCHeader': True},
                },
            }
        )
        original = copy.deepcopy(profile.connection)
        group = GuiVTransportQGroupBox()

        group.factoryToInput(profile.connection)

        xhttpIndex = STREAM_NETWORK.index('xhttp')
        wsIndex = STREAM_NETWORK.index('ws')
        page = group.page(xhttpIndex)
        self.assertIsInstance(page, GuiVTransportPageXHttp)
        layout = page.layout()
        host = page._containers[2]
        path = page._containers[3]
        hostInput = host.widgets()[1]
        pathInput = path.widgets()[1]

        self.assertBindingPosition(layout, page._containers[0], 0, 0, 1)
        self.assertBindingPosition(layout, page._containers[1], 1, 0, 1, 3)
        self.assertBindingPosition(layout, page._containers[4], 3, 0, 1)
        self.assertBindingPosition(layout, page._containers[5], 4, 0, 1, 3)
        self.assertBindingPosition(layout, host, 2, 0, 1)
        self.assertBindingPosition(layout, path, 2, 2, 3)
        self.assertEqual(host.text(), 'cdn.example.com')
        self.assertEqual(path.text(), '/a/representative/xhttp/path')
        self.assertEqual(profile.connection, original)

        group.handleActivated(wsIndex)
        group.handleActivated(xhttpIndex)

        self.assertIs(group.page(xhttpIndex), page)
        self.assertIs(host.widgets()[1], hostInput)
        self.assertIs(path.widgets()[1], pathInput)
        self.assertFalse(group.inputToFactory(profile.connection))
        self.assertEqual(profile.connection, original)

        host.setText('edge.example.net')
        path.setText('/updated/path')

        self.assertTrue(group.inputToFactory(profile.connection))
        self.assertEqual(
            streamSettings['xhttpSettings']['host'],
            'edge.example.net',
        )
        self.assertEqual(streamSettings['xhttpSettings']['path'], '/updated/path')

        group.deleteLater()

    def testExternalCoreEditorRoundTripsStructuredFields(self):
        """Keep arguments, environment, process paths, and TUN data distinct."""
        configuration = ConfigExternalCore(copy.deepcopy(BLANK_CONFIG_EXTERNAL_CORE))
        configuration.update(
            {
                'executable': 'C:/Program Files/Fixture/core.exe',
                'workingDirectory': 'C:/Program Files/Fixture',
                'arguments': ['--config', 'name with spaces.json'],
                'environment': {'TOKEN': 'one=two', 'UNICODE': '测试'},
                'useApplicationTun2socks': True,
                'tunRemoteAddress': '2001:db8::42',
                'futureExternalCoreField': {
                    'nested': ['preserve', 7],
                },
            }
        )
        profile = ServerProfile.fromConfiguration(
            configuration,
            ProfileMetadata(displayName='Fixture core'),
        )

        with isolatedSettings():
            editor = ExternalCoreEditor()
            original = copy.deepcopy(profile.connection)
            editor.factoryToInput(profile)

            self.assertEqual(profile.connection, original)

            self.assertEqual(
                editor._argumentsInput.values(),
                ['--config', 'name with spaces.json'],
            )
            self.assertEqual(
                editor._environmentInput.values(),
                {'TOKEN': 'one=two', 'UNICODE': '测试'},
            )
            self.assertTrue(editor._applicationTun2socksInput.isChecked())

            tunLabel, tunSwitch = editor._applicationTun2socksInput.widgets()

            self.assertTrue(tunLabel.text())
            self.assertIsInstance(tunSwitch, AppQSwitch)
            self.assertEqual(tunSwitch.size(), AppQSwitch.CompactControlSize)
            self.assertTrue(editor._tunRemoteAddressInput.widgets()[1].isEnabled())
            self.assertEqual(editor._tunRemoteAddressInput.text(), '2001:db8::42')
            self.assertEqual(len(editor.groupBoxSequence()), 2)

            editor._argumentsInput._input.setText(
                '--mode direct --label "a value with spaces"'
            )
            editor._environmentInput._input.setPlainText('A=1\nB=two=three')
            editor._tunRemoteAddressInput._input.setText('server.example.com')

            self.assertTrue(editor.inputToFactory(profile))
            self.assertEqual(
                profile.connection['arguments'],
                ['--mode', 'direct', '--label', 'a value with spaces'],
            )
            self.assertEqual(
                profile.connection['environment'],
                {'A': '1', 'B': 'two=three'},
            )
            self.assertEqual(
                profile.connection.tunRemoteAddress(),
                'server.example.com',
            )
            self.assertEqual(
                profile.connection['futureExternalCoreField'],
                {'nested': ['preserve', 7]},
            )

            editor.close()

    def testExternalCorePlaceholdersRetranslateWithoutChangingValues(self):
        """Translate field guidance without persisting it as configuration."""
        configuration = ConfigExternalCore(copy.deepcopy(BLANK_CONFIG_EXTERNAL_CORE))
        configuration.update(
            {
                'arguments': ['--config', 'fixture.json', '--verbose'],
                'environment': {'TOKEN': 'fixture'},
                'useApplicationTun2socks': True,
                'tunRemoteAddress': 'server.example.com',
            }
        )
        profile = ServerProfile.fromConfiguration(
            configuration,
            ProfileMetadata(displayName='Fixture core'),
        )

        with isolatedSettings():
            AppSettings.set('Language', 'EN')
            editor = ExternalCoreEditor()
            editor.factoryToInput(profile)
            original = copy.deepcopy(profile.connection)
            basicGroup = editor.groupBoxSequence()[0]
            workingDirectoryInput = basicGroup._containers[2]._input
            placeholderInputs = (
                (
                    workingDirectoryInput,
                    'Leave empty to use executable directory',
                ),
                (
                    editor._argumentsInput._input,
                    'e.g. --config config.json --verbose',
                ),
                (
                    editor._environmentInput._input,
                    'One per line, e.g. KEY=VALUE',
                ),
                (
                    editor._tunRemoteAddressInput._input,
                    'Remote server hostname or IP address',
                ),
            )

            for widget, sourceText in placeholderInputs:
                self.assertEqual(widget.placeholderText(), sourceText)

            for language in ('ZH', 'RU', 'EN'):
                AppSettings.set('Language', language)
                Mixins.QTranslatable.retranslateAll()

                for widget, sourceText in placeholderInputs:
                    self.assertEqual(widget.placeholderText(), _(sourceText, language))

                self.assertEqual(
                    editor._argumentsInput.values(),
                    ['--config', 'fixture.json', '--verbose'],
                )
                self.assertEqual(
                    editor._environmentInput.values(),
                    {'TOKEN': 'fixture'},
                )
                self.assertEqual(
                    editor._tunRemoteAddressInput.text(),
                    'server.example.com',
                )

            self.assertFalse(editor.inputToFactory(profile))
            self.assertEqual(profile.connection, original)
            self.assertEqual(workingDirectoryInput.text(), '')

            editor.close()

    def testExternalCoreSectionUsesCanonicalEditorInset(self):
        """Use canonical editor grids and insets for both External Core groups."""
        editor = ExternalCoreEditor()
        externalGroups = editor.groupBoxSequence()
        referenceGroup = GuiVLESSGroupBoxBasic()
        referenceLayout = referenceGroup._widget.currentWidget().layout()

        self.assertEqual(len(externalGroups), 2)

        for group in externalGroups:
            externalLayout = group._widget.currentWidget().layout()

            self.assertEqual(
                externalLayout.contentsMargins(),
                referenceLayout.contentsMargins(),
            )
            self.assertFalse(externalLayout.contentsMargins().isNull())
            self.assertIsInstance(externalLayout, type(referenceLayout))
            self.assertEqual(externalLayout.columnStretch(1), 1)
            self.assertEqual(
                externalLayout.verticalSpacing(),
                referenceLayout.verticalSpacing(),
            )
            self.assertEqual(
                externalLayout.rowStretch(externalLayout.rowCount() - 1),
                1,
            )

        basicGroup, otherGroup = externalGroups
        basicLayout = basicGroup._widget.currentWidget().layout()
        otherLayout = otherGroup._widget.currentWidget().layout()
        timeoutInput = otherGroup._containers[0].widgets()[1]

        for row, container in enumerate(basicGroup._containers):
            self.assertBindingPosition(basicLayout, container, row, 0, 1, 3)

        self.assertEqual(
            timeoutInput.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        self.assertBindingPosition(otherLayout, otherGroup._containers[0], 0, 0, 1)
        self.assertBindingPosition(otherLayout, otherGroup._containers[1], 1, 0, 1, 3)
        self.assertBindingPosition(otherLayout, otherGroup._containers[2], 2, 0, 1, 3)
        self.assertBindingPosition(otherLayout, otherGroup._containers[4], 4, 0, 1, 3)
        self.assertGreater(basicGroup._containers[-1].widgets()[1].maximumWidth(), 520)
        self.assertGreater(otherGroup._containers[1].widgets()[1].maximumWidth(), 360)
        self.assertGreater(otherGroup._containers[2].widgets()[1].maximumWidth(), 360)
        self.assertGreater(otherGroup._containers[4].widgets()[1].maximumWidth(), 420)
        self.assertEqual(editor.size(), QtCore.QSize(1400, 600))

        editor.close()
        referenceGroup.deleteLater()

    def testExternalCoreRowsRemainTopAlignedAsSectionGrows(self):
        """Assign surplus editor height below the compact form rows."""
        groups = (
            ExternalCoreConfigurationGroup(
                ExternalCoreArgumentsInput(),
                ExternalCoreEnvironmentInput(),
            ),
            ExternalCoreOtherGroup(
                ExternalCoreApplicationTun2socksInput(),
                ExternalCoreTunRemoteAddressInput(),
            ),
        )

        for group in groups:
            containers = group._containers

            group.resize(760, 900)
            group.show()
            processQtEvents()

            initialPositions = tuple(
                container.widgets()[0].geometry().top() for container in containers
            )
            page = group._widget.currentWidget()
            initialBlankHeight = (
                page.height() - containers[-1].widgets()[0].geometry().bottom()
            )

            group.resize(760, 1200)
            processQtEvents()

            grownPositions = tuple(
                container.widgets()[0].geometry().top() for container in containers
            )
            grownBlankHeight = (
                page.height() - containers[-1].widgets()[0].geometry().bottom()
            )

            self.assertEqual(grownPositions, initialPositions)
            self.assertGreater(grownBlankHeight, initialBlankHeight)

            group.close()
            group.deleteLater()

    def testEveryProtocolEditorRetranslatesItsDedicatedWindowTitle(self):
        """Retain title source text when switching from Chinese to English."""
        editorTypes = (
            (ExternalCoreEditor, 'Add External Core'),
            (Hysteria1Editor, 'Add Hysteria1 Server'),
            (Hysteria2Editor, 'Add Hysteria2 Server'),
            (ShadowsocksEditor, 'Add Shadowsocks Server'),
            (SocksEditor, 'Add SOCKS Server'),
            (TrojanEditor, 'Add Trojan Server'),
            (VlessEditor, 'Add VLESS Server'),
            (VmessEditor, 'Add VMess Server'),
        )

        with isolatedSettings():
            AppSettings.set('Language', 'ZH')
            editors = []

            for editorType, sourceTitle in editorTypes:
                editor = editorType(windowTitle=_(sourceTitle))
                editors.append((editor, sourceTitle))

                self.assertEqual(editor.windowTitle(), _(sourceTitle))

            AppSettings.set('Language', 'EN')

            Mixins.QTranslatable.retranslateAll()

            for editor, sourceTitle in editors:
                self.assertEqual(editor.windowTitle(), sourceTitle)

                editor.close()

    def testSubscriptionEditorNormalizesPresentationValues(self):
        """Return one complete subscription record from its visual controls."""
        with isolatedSettings():
            dialog = _SubscriptionEditorDialog(
                {
                    'remark': '  Fixture subscription  ',
                    'webURL': 'https://example.test/subscription',
                    'enabled': False,
                    'autoupdate': 'Every 6 hours',
                    'proxy': 'Direct',
                    'userAgent': '  Fixture/1.0  ',
                    'filter': '  keep.*  ',
                }
            )

            values = dialog.subscription()

            self.assertIsInstance(dialog.enabledSwitch, AppQSwitch)
            self.assertEqual(dialog.enabledSwitch.size(), AppQSwitch.ControlSize)
            self.assertEqual(
                dialog.enabledSwitch.parentWidget().objectName(),
                'SubscriptionEditorForm',
            )
            self.assertEqual(values['remark'], 'Fixture subscription')
            self.assertEqual(values['webURL'], 'https://example.test/subscription')
            self.assertFalse(values['enabled'])
            self.assertEqual(values['userAgent'], 'Fixture/1.0')
            self.assertEqual(values['filter'], 'keep.*')

            dialog.accept()

            self.assertEqual(
                dialog.result(),
                _SubscriptionEditorDialog.DialogCode.Accepted,
            )


class UnifiedLogPageTest(unittest.TestCase):
    """Prove bounded collection is eager while hidden-page rendering is lazy."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish deferred document and widget cleanup between tests."""
        collectAtBoundary()

    def assertRendered(self, page, *, highlighting=True):
        """Wait for the coalesced snapshot and optional highlighting batches."""
        self.assertTrue(waitFor(lambda: not page._entriesDirty))

        if highlighting:
            self.assertTrue(waitFor(lambda: page._highlightNextBlock is None))

    @staticmethod
    def disposePage(page):
        """Release one persistent page and its owned timers."""
        page.close()
        page.deleteLater()

    def testHiddenPageRendersOneOrderedSnapshotWhenShown(self):
        """Do not mutate the document while hidden; catch up exactly once."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=5)
            page = LogPage(manager=manager)

            manager.append('application one', APPLICATION_LOG_CATEGORY)
            manager.append('core one', CORE_LOG_CATEGORY)

            processQtEvents()

            self.assertEqual(page.textBrowser.toPlainText(), '')
            self.assertTrue(page._entriesDirty)

            page.show()

            self.assertRendered(page)

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['application one', 'core one'],
            )

            page.hide()
            manager.append('core two', CORE_LOG_CATEGORY)

            processQtEvents()

            self.assertNotIn('core two', page.textBrowser.toPlainText())

            page.show()

            self.assertRendered(page)

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['application one', 'core one', 'core two'],
            )

            coreIndex = page.filterComboBox.findData(CORE_LOG_CATEGORY)
            page.filterComboBox.setCurrentIndex(coreIndex)

            self.assertRendered(page)

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['core one', 'core two'],
            )

            self.disposePage(page)

    def testLargeHiddenBacklogDefersOneBulkDocumentCatchUp(self):
        """Return from show before rendering and avoid per-entry replay."""
        with isolatedSettings():
            entryCount = 5_000
            manager = LogManager(maximumEntries=entryCount)

            page = LogPage(manager=manager)
            page.resize(900, 420)

            for index in range(entryCount):
                manager.append(f'bulk entry {index:05d}')

            self.assertEqual(page.textBrowser.toPlainText(), '')

            page.show()

            # showEvent only schedules the catch-up; it does not synchronously
            # build and highlight thousands of QTextDocument blocks.
            self.assertTrue(page._entriesDirty)
            self.assertEqual(page.textBrowser.toPlainText(), '')
            self.assertTrue(page.highlightOverlay.isVisible())
            self.assertTrue(page.highlightSpinner.is_spinning)

            self.assertRendered(page)

            self.assertFalse(page.highlightOverlay.isVisible())
            self.assertFalse(page.highlightSpinner.is_spinning)

            lines = page.textBrowser.toPlainText().splitlines()

            self.assertEqual(len(lines), entryCount)
            self.assertEqual(lines[0], 'bulk entry 00000')
            self.assertEqual(lines[-1], 'bulk entry 04999')
            self.assertEqual(page.textBrowser.document().blockCount(), entryCount)

            self.disposePage(page)

    def testFollowingTailSurvivesHideAndCatchUp(self):
        """Restore the newest entry after collecting while the page is hidden."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=500)

            page = LogPage(manager=manager)
            page.resize(800, 320)

            for index in range(200):
                manager.append(f'before hide {index:03d}')

            page.show()

            self.assertRendered(page)

            scrollbar = page.textBrowser.verticalScrollBar()

            self.assertGreater(scrollbar.maximum(), 0)
            self.assertEqual(scrollbar.value(), scrollbar.maximum())
            self.assertTrue(page._followTail)

            page.hide()

            for index in range(25):
                manager.append(f'while hidden {index:03d}')

            page.show()

            self.assertRendered(page)
            self.assertTrue(waitFor(lambda: scrollbar.value() == scrollbar.maximum()))

            self.assertTrue(page._followTail)
            self.assertTrue(page.plainText().endswith('while hidden 024'))

            self.disposePage(page)

    def testLogPreferencesDefaultOnAndPersistAcrossPageRecreation(self):
        """Restore both switch preferences without rewriting them at startup."""
        with isolatedSettings():
            firstManager = LogManager(maximumEntries=20)
            firstPage = LogPage(manager=firstManager)

            self.assertTrue(firstPage.autoScrollSwitch.isChecked())
            self.assertTrue(firstPage.autoClearSwitch.isChecked())
            self.assertTrue(AppSettings.isStateON_(LOG_AUTO_SCROLL_DOWN_SETTING))
            self.assertTrue(AppSettings.isStateON_(LOG_AUTO_CLEAR_SETTING))

            firstPage.autoScrollSwitch.setChecked(False)
            firstPage.autoClearSwitch.setChecked(False)

            self.assertFalse(AppSettings.isStateON_(LOG_AUTO_SCROLL_DOWN_SETTING))
            self.assertFalse(AppSettings.isStateON_(LOG_AUTO_CLEAR_SETTING))
            self.assertFalse(firstManager.autoClearEnabled)

            self.disposePage(firstPage)

            processQtEvents()

            secondManager = LogManager(maximumEntries=20)
            secondPage = LogPage(manager=secondManager)

            self.assertFalse(secondPage.autoScrollSwitch.isChecked())
            self.assertFalse(secondPage.autoClearSwitch.isChecked())
            self.assertFalse(secondManager.autoClearEnabled)

            secondPage.autoScrollSwitch.setChecked(True)
            secondPage.autoClearSwitch.setChecked(True)

            self.assertTrue(AppSettings.isStateON_(LOG_AUTO_SCROLL_DOWN_SETTING))
            self.assertTrue(AppSettings.isStateON_(LOG_AUTO_CLEAR_SETTING))
            self.assertTrue(secondManager.autoClearEnabled)

            self.disposePage(secondPage)

    def testAutoScrollPreferenceMastersTailFollowing(self):
        """Never move a disabled viewer and resume at the newest entry on enable."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=500)

            page = LogPage(manager=manager)
            page.resize(800, 320)

            for index in range(200):
                manager.append(f'initial {index:03d}')

            page.show()

            self.assertRendered(page)

            scrollbar = page.textBrowser.verticalScrollBar()
            page.autoScrollSwitch.setChecked(False)
            scrollbar.setValue(0)
            manager.append('must not move the viewport')

            self.assertRendered(page)

            self.assertEqual(scrollbar.value(), 0)
            self.assertFalse(page._followTail)

            page.autoScrollSwitch.setChecked(True)

            self.assertTrue(waitFor(lambda: scrollbar.value() == scrollbar.maximum()))
            self.assertTrue(page._followTail)

            page.hide()
            manager.append('arrived while hidden')
            page.show()

            self.assertRendered(page)
            self.assertTrue(waitFor(lambda: scrollbar.value() == scrollbar.maximum()))
            self.assertTrue(page.plainText().endswith('arrived while hidden'))

            self.disposePage(page)

    def testHiddenCoreClearRebuildsWithoutForcingScroll(self):
        """Invalidate hidden runtime state and honor disabled tail follow on show."""
        with isolatedSettings():
            manager = LogManager(
                maximumEntries=50,
                autoClearMaximumEntries=3,
            )

            page = LogPage(manager=manager)
            page.resize(800, 260)

            coreIndex = page.filterComboBox.findData(CORE_LOG_CATEGORY)

            page.filterComboBox.setCurrentIndex(coreIndex)
            page.autoScrollSwitch.setChecked(False)

            for index in range(3):
                manager.append(f'old core {index}', CORE_LOG_CATEGORY)

            manager.append('old tun2socks', TUN2SOCKS_LOG_CATEGORY)

            processQtEvents()

            manager.append('new core after clear', CORE_LOG_CATEGORY)
            manager.append('application retained', APPLICATION_LOG_CATEGORY)

            self.assertEqual(page.plainText(), '')
            self.assertEqual(
                tuple(entry.message for entry in manager.entries(CORE_LOG_CATEGORY)),
                ('new core after clear',),
            )
            self.assertEqual(manager.entries(TUN2SOCKS_LOG_CATEGORY), tuple())

            page.show()

            self.assertRendered(page)

            self.assertEqual(page.plainText(), 'new core after clear')
            self.assertFalse(page._followTail)
            self.assertEqual(
                tuple(
                    entry.message for entry in manager.entries(APPLICATION_LOG_CATEGORY)
                ),
                ('application retained',),
            )

            self.disposePage(page)

    def testManualHistoryReadingDisablesAndThenResumesTail(self):
        """Do not yank an upward-scrolled viewport until it returns to bottom."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=500)

            page = LogPage(manager=manager)
            page.resize(800, 320)

            for index in range(200):
                manager.append(f'history {index:03d}')

            page.show()

            self.assertRendered(page)

            scrollbar = page.textBrowser.verticalScrollBar()
            scrollbar.setValue(0)

            page._updateFollowTailFromScrollbar()

            self.assertFalse(page._followTail)

            manager.append('arrived while reading')

            self.assertRendered(page)

            self.assertEqual(scrollbar.value(), 0)
            self.assertLess(scrollbar.value(), scrollbar.maximum())

            scrollbar.setValue(scrollbar.maximum())

            page._updateFollowTailFromScrollbar()

            self.assertTrue(page._followTail)

            manager.append('tail resumed')

            self.assertRendered(page)
            self.assertTrue(waitFor(lambda: scrollbar.value() == scrollbar.maximum()))
            self.assertTrue(page.plainText().endswith('tail resumed'))

            self.disposePage(page)

    def testFilteredTailCatchUpAndPruningRemainExact(self):
        """Keep filtered tail semantics and discard pruned filtered entries."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=40)

            page = LogPage(manager=manager)
            page.resize(800, 260)

            for index in range(30):
                manager.append(f'application {index:03d}', APPLICATION_LOG_CATEGORY)
                manager.append(f'core {index:03d}', CORE_LOG_CATEGORY)

            coreIndex = page.filterComboBox.findData(CORE_LOG_CATEGORY)

            page.filterComboBox.setCurrentIndex(coreIndex)
            page.show()

            self.assertRendered(page)

            scrollbar = page.textBrowser.verticalScrollBar()

            self.assertTrue(page.plainText().endswith('core 029'))
            self.assertEqual(scrollbar.value(), scrollbar.maximum())

            page.hide()

            for index in range(45):
                manager.append(
                    f'new application {index:03d}',
                    APPLICATION_LOG_CATEGORY,
                )

            manager.append('new core tail', CORE_LOG_CATEGORY)

            page.show()

            self.assertRendered(page)
            self.assertTrue(waitFor(lambda: scrollbar.value() == scrollbar.maximum()))

            self.assertEqual(page.plainText(), 'new core tail')
            self.assertTrue(page._followTail)

            self.disposePage(page)

    def testIncrementalBatchesRehighlightChangedBoundaryBlocks(self):
        """Color paragraph boundaries invalidated by append and retention edits."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=24)
            page = LogPage(manager=manager)

            def appendEntries(start, count):
                """Append deterministic lines matched by several log rules."""
                for index in range(start, start + count):
                    manager.append(
                        '2026/08/17 18:45:'
                        f'{index % 60:02d}.000000 from '
                        f'127.0.0.1:{5000 + index} accepted '
                        '//example.com:443 [http >> proxy]'
                    )

            def missingFormats():
                """Return blocks that fell back to the default text format."""
                document = page.textBrowser.document()

                return tuple(
                    blockNumber
                    for blockNumber in range(document.blockCount())
                    if not document.findBlockByNumber(blockNumber).layout().formats()
                )

            appendEntries(0, 20)

            page.show()

            self.assertRendered(page)

            appendEntries(20, 3)

            self.assertRendered(page)

            self.assertEqual(missingFormats(), ())

            # This batch prunes four old entries as it appends five new ones,
            # exercising both the new first and previous last block boundaries.
            appendEntries(23, 5)

            self.assertRendered(page)

            self.assertEqual(page.textBrowser.document().blockCount(), 24)
            self.assertEqual(missingFormats(), ())

            self.disposePage(page)

    def testRepeatedVisibilityCyclesReuseTimersWithoutDuplicateEntries(self):
        """Keep one owned render pipeline stable through repeated page visits."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=500)
            page = LogPage(manager=manager)
            timers = (
                page._updateTimer,
                page._highlightTimer,
                page._scrollTimer,
                page._followStateTimer,
            )

            page.show()

            self.assertRendered(page)

            expected = []

            for index in range(30):
                page.hide()

                line = f'visibility cycle {index:02d}'

                expected.append(line)
                manager.append(line)

                page.show()

                self.assertRendered(page, highlighting=False)

            self.assertEqual(page.plainText().splitlines(), expected)
            self.assertEqual(
                (
                    page._updateTimer,
                    page._highlightTimer,
                    page._scrollTimer,
                    page._followStateTimer,
                ),
                timers,
            )

            self.disposePage(page)

    def testPageDestructionReleasesOwnedRenderTimers(self):
        """Do not retain the page or its persistent timers after destruction."""
        with isolatedSettings():
            manager = LogManager(maximumEntries=20)
            page = LogPage(manager=manager)
            references = tuple(
                weakref.ref(value)
                for value in (
                    page,
                    page._updateTimer,
                    page._highlightTimer,
                    page._scrollTimer,
                    page._followStateTimer,
                    page.autoScrollSwitch,
                    page.autoClearSwitch,
                    page.highlightOverlay,
                    page.highlightSpinner,
                    page.highlightStatusLabel,
                )
            )

            page.show()

            self.assertRendered(page)
            self.disposePage(page)

            del page

            collectAtBoundary()

            self.assertTrue(all(reference() is None for reference in references))


class DialogBehaviorTest(unittest.TestCase):
    """Exercise no-selection guards and QMessageBox-compatible results."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish every deferred transient deletion between tests."""
        collectAtBoundary()

    def testThemeFallbackWorksBeforeConnectionControllerExists(self):
        """Allow startup error dialogs to use the disconnected theme safely."""
        with mock.patch(
            'Furious.Qt.DynamicTheme.AppConnectionController',
            return_value=None,
        ):
            self.assertEqual(AppHue.currentColor(), AppHue.disconnectedColor())
            self.assertEqual(
                AppHue.currentWindowIcon().iconFileName,
                ':/Icons/bootstrap/rocket-takeoff-window.svg',
            )

    def testRoutingRulesActionsStayEnabledAndNoSelectionIsSafe(self):
        """Keep the compact top actions visible without creating a warning."""
        dialog = RoutingRulesDialog({'rules': []})

        self.assertTrue(dialog.addButton.isEnabled())
        self.assertTrue(dialog.deleteButton.isEnabled())
        self.assertTrue(dialog.closeWindowButton.isEnabled())
        self.assertIsNotNone(dialog.layout().itemAt(0).layout())
        self.assertIs(dialog.layout().itemAt(1).widget(), dialog.listView)
        self.assertIs(dialog.listView.model(), dialog.listView.rulesModel)
        self.assertIs(dialog.listView.rulesModel.parent(), dialog.listView)
        self.assertEqual(dialog.listView.rulesModel.stringList(), [])

        dialog.deleteRule()
        dialog.editRule()

        self.assertEqual(AppQDialog._openDialogs, {})
        self.assertEqual(dialog.routing['rules'], [])

        dialog.closeWindowButton.click()

    def testRoutingRuleGuidanceUsesPlaceholdersInsteadOfLabels(self):
        """Keep routing field names compact while retaining input guidance."""
        dialog = RoutingRuleEditDialog({'type': 'field'})

        self.assertEqual(dialog.ruleTagEdit.text(), '')
        self.assertEqual(dialog.outboundEdit.text(), '')

        placeholders = (
            (dialog.ruleTagEdit, 'Optional rule name, e.g. block-ads'),
            (dialog.outboundEdit, 'Outbound tag, e.g. proxy, direct, block'),
            (dialog.balancerTagEdit, 'Balancer tag, e.g. balancer'),
            (
                dialog.domainEdit,
                r'e.g. domain:xray.com, geosite:cn, regexp:\.google\.com$',
            ),
            (dialog.ipEdit, 'e.g. 10.0.0.0/8, geoip:cn, !geoip:private'),
            (dialog.portEdit, 'e.g. 53,443,1000-2000'),
            (dialog.vlessRouteEdit, 'e.g. 53,443,1000-2000'),
            (dialog.sourceIPEdit, 'e.g. 10.0.0.1, 192.168.1.0/24'),
            (dialog.sourcePortEdit, 'e.g. 53,443,1000-2000'),
            (dialog.localIPEdit, 'e.g. 192.168.0.25'),
            (dialog.localPortEdit, 'e.g. 53,443,1000-2000'),
            (dialog.userEdit, 'e.g. love@xray.com'),
            (dialog.inboundTagEdit, 'e.g. tag-vmess'),
            (dialog.processEdit, 'e.g. curl'),
            (dialog.protocolEdit, 'e.g. http, tls, quic, bittorrent'),
        )

        for widget, placeholder in placeholders:
            self.assertEqual(
                widget.placeholderText(),
                _(placeholder),
            )

        self.assertEqual(dialog.networkCombo.currentText(), '')

        labels = {label.text() for label in dialog.findChildren(QLabel)}

        self.assertIn('OutBound', labels)
        self.assertIn('Domain', labels)
        self.assertIn('VLESS Route', labels)
        self.assertFalse(any('(' in label for label in labels))

        dialog.close()

    def testRoutingRulePlaceholdersRetranslateWithoutChangingValues(self):
        """Translate guidance while preserving technical syntax and user input."""
        rule = {
            'type': 'field',
            'ruleTag': 'fixture-rule',
            'outboundTag': 'fixture-outbound',
            'domain': ['domain:example.test', 'geosite:cn'],
            'ip': ['10.0.0.0/8'],
            'port': '53,443,1000-2000',
        }

        with isolatedSettings():
            AppSettings.set('Language', 'EN')
            dialog = RoutingRuleEditDialog(rule)
            expectedRule = dialog.routingRule()

            AppSettings.set('Language', 'ZH')
            Mixins.QTranslatable.retranslateAll()

            self.assertEqual(dialog.routingRule(), expectedRule)
            self.assertIn('domain:xray.com', dialog.domainEdit.placeholderText())
            self.assertIn('geosite:cn', dialog.domainEdit.placeholderText())
            self.assertIn('!geoip:private', dialog.ipEdit.placeholderText())
            self.assertIn('53,443,1000-2000', dialog.portEdit.placeholderText())
            self.assertIn(
                'http, tls, quic, bittorrent', dialog.protocolEdit.placeholderText()
            )

            AppSettings.set('Language', 'RU')
            Mixins.QTranslatable.retranslateAll()

            self.assertEqual(dialog.routingRule(), expectedRule)
            self.assertIn('block-ads', dialog.ruleTagEdit.placeholderText())
            self.assertIn('tag-vmess', dialog.inboundTagEdit.placeholderText())

            AppSettings.set('Language', 'EN')
            Mixins.QTranslatable.retranslateAll()

            dialog.close()

    def testRoutingRuleSerializationStillUsesExistingParsingContract(self):
        """Keep comma/newline parsing and scalar routing fields unchanged."""
        dialog = RoutingRuleEditDialog(
            {
                'type': 'field',
                'ruleTag': 'fixture-rule',
                'outboundTag': 'direct',
                'balancerTag': 'balancer',
                'network': 'tcp,udp',
                'domain': ['domain:xray.com', 'geosite:cn'],
                'ip': ['10.0.0.0/8', '!geoip:private'],
                'port': '53,443,1000-2000',
                'sourceIP': ['10.0.0.1'],
                'sourcePort': '1024-65535',
                'localIP': ['192.168.0.25'],
                'localPort': '10808',
                'user': ['love@xray.com'],
                'vlessRoute': '1,14,14514',
                'inboundTag': ['tag-vmess'],
                'protocol': ['http', 'tls', 'quic', 'bittorrent'],
                'process': ['curl'],
            }
        )

        self.assertEqual(
            dialog.routingRule(),
            {
                'type': 'field',
                'outboundTag': 'direct',
                'ruleTag': 'fixture-rule',
                'network': 'tcp,udp',
                'port': '53,443,1000-2000',
                'sourcePort': '1024-65535',
                'localPort': '10808',
                'vlessRoute': '1,14,14514',
                'balancerTag': 'balancer',
                'domain': ['domain:xray.com', 'geosite:cn'],
                'ip': ['10.0.0.0/8', '!geoip:private'],
                'sourceIP': ['10.0.0.1'],
                'localIP': ['192.168.0.25'],
                'user': ['love@xray.com'],
                'protocol': ['http', 'tls', 'quic', 'bittorrent'],
                'inboundTag': ['tag-vmess'],
                'process': ['curl'],
            },
        )

        dialog.close()

    def testRoutingTextEditorsPreservePlainTextLineBreaks(self):
        """Keep multiline routing values intact in the enlarged editor."""
        text = 'aaa\nbb\ncccc'
        editor = RoutingTextEdit(text)
        dialog = RoutingTextEditDialog(text)

        self.assertEqual(editor.toPlainText(), text)
        self.assertEqual(dialog.text(), text)

        editor.close()
        dialog.close()

    def testAssetListViewKeepsRawFilenameInItsOwnedModel(self):
        """Keep filesystem identity separate from formatted asset row text."""
        with tempfile.TemporaryDirectory() as directory:
            assetDirectory = pathlib.Path(directory)
            filename = 'geo data.dat'
            (assetDirectory / filename).write_bytes(b'fixture')

            with mock.patch(
                'Furious.Backends.Xray.AssetListView.XRAY_ASSET_DIR',
                assetDirectory,
            ):
                view = XrayAssetListView()

                self.assertIs(view.model(), view.assetModel)
                self.assertIs(view.assetModel.parent(), view)
                self.assertEqual(view.assetModel.rowCount(), 1)

                view.show()

                processQtEvents()

                self.assertEqual(view.assetModel.rowCount(), 1)
                self.assertGreaterEqual(
                    view.sizeHintForRow(0),
                    view.iconSize().height(),
                )
                self.assertEqual(view.filenameAt(0), filename)
                self.assertIn(filename, view.assetModel.item(0).text())

                view.close()
                view.deleteLater()

    def testMessageBoxButtonPublishesCompatibleResult(self):
        """Emit one clicked button and finish with its standard-button value."""
        messageBox = AppQMessageBox(
            text='Continue?',
            buttons=(
                AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.No
            ),
        )
        clicked = []
        finished = []
        messageBox.buttonClicked.connect(clicked.append)
        messageBox.finished.connect(finished.append)
        yesButton = messageBox.button(AppQMessageBox.StandardButton.Yes)

        yesButton.click()

        processQtEvents()

        self.assertEqual(clicked, [yesButton])
        self.assertEqual(finished, [int(AppQMessageBox.StandardButton.Yes)])
        self.assertIs(messageBox.clickedButton(), yesButton)

    def testMessageBoxSeparatesNativeTitleHeadingAndBody(self):
        """Keep native metadata independent from visible semantic content."""
        messageBox = AppQMessageBox(
            title='Native window metadata',
            heading='Unable to connect',
            text='Xray-core: Invalid server configuration',
        )
        messageBox.setInformativeText('The outbound server address is missing.')
        messageBox.show()

        processQtEvents()

        self.assertEqual(messageBox.windowTitle(), 'Native window metadata')
        self.assertEqual(messageBox.heading(), 'Unable to connect')
        self.assertEqual(messageBox.text(), 'Xray-core: Invalid server configuration')
        self.assertEqual(
            messageBox.informativeText(),
            'The outbound server address is missing.',
        )
        self.assertEqual(messageBox.headingLabel.text(), 'Unable to connect')
        self.assertEqual(
            messageBox.textLabel.text(),
            'Xray-core: Invalid server configuration',
        )
        self.assertFalse(messageBox.headingLabel.isHidden())

        messageBox.setWindowTitle('Changed native metadata')

        self.assertEqual(messageBox.heading(), 'Unable to connect')

        messageBox.close()

    def testMessageBoxKeepsGenericApplicationTitleAsMetadataOnly(self):
        """Do not promote the default application name into visible content."""
        messageBox = AppQMessageBox(text='Operation completed')
        messageBox.show()

        processQtEvents()

        self.assertEqual(messageBox.windowTitle(), APPLICATION_NAME)
        self.assertEqual(messageBox.heading(), '')
        self.assertTrue(messageBox.headingLabel.isHidden())
        self.assertEqual(messageBox.textLabel.y(), 0)

        positional = AppQMessageBox(
            AppQMessageBox.Icon.Information,
            'Native compatibility title',
            'Compatibility body',
            AppQMessageBox.StandardButton.Ok,
        )

        self.assertEqual(positional.windowTitle(), 'Native compatibility title')
        self.assertEqual(positional.heading(), '')
        self.assertEqual(positional.text(), 'Compatibility body')

        messageBox.close()
        positional.deleteLater()

    def testConnectionErrorPreservesHeadingMessageAndDetails(self):
        """Map every structured connection-error field to visible dialog content."""
        error = ConnectionError(
            'Unable to connect',
            'Xray-core: Invalid server configuration',
            'The outbound server address is missing.',
        )
        opened = []

        with mock.patch.object(
            AppQMessageBox,
            'open',
            lambda messageBox: opened.append(messageBox),
        ):
            ConnectAction.showError(error)

        self.assertEqual(len(opened), 1)

        messageBox = opened[0]

        self.assertEqual(messageBox.windowTitle(), APPLICATION_NAME)
        self.assertEqual(messageBox.heading(), error.title)
        self.assertEqual(messageBox.text(), error.message)
        self.assertEqual(messageBox.informativeText(), error.details)

        messageBox.close()
        messageBox.deleteLater()

    def testMessageBoxHeadingSupportsLongContentIconsAndThemes(self):
        """Keep the semantic stack responsive across themes and icon variants."""
        app = application()
        originalStyleSheet = app.styleSheet()
        longMessage = (
            'Не удалось применить конфигурацию прокси-сервера. '
            'Проверьте адрес, порт и параметры подключения, затем повторите попытку.'
        )

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                app.setStyleSheet(AppStyleSheet.forTheme(theme))

                for icon in (
                    AppQMessageBox.Icon.Information,
                    AppQMessageBox.Icon.Warning,
                    AppQMessageBox.Icon.Critical,
                    AppQMessageBox.Icon.Question,
                ):
                    with self.subTest(theme=theme, icon=icon):
                        messageBox = AppQMessageBox(
                            icon=icon,
                            heading='Unable to connect',
                            text=longMessage,
                        )
                        messageBox.show()

                        processQtEvents()

                        self.assertFalse(messageBox.iconPixmap().isNull())
                        self.assertGreaterEqual(
                            messageBox.textLabel.height(),
                            messageBox.textLabel.fontMetrics().height(),
                        )
                        self.assertLessEqual(
                            messageBox.width(),
                            messageBox.MaximumSurfaceWidth,
                        )

                        messageBox.close()
                        messageBox.deleteLater()
        finally:
            app.setStyleSheet(originalStyleSheet)

    def testMessageBoxButtonsHaveAdaptiveFluentLayoutAndRoles(self):
        """Keep one, two, and three actions slim, separated, and content-driven."""
        configurations = (
            (AppQMessageBox.StandardButton.Ok, 1),
            (
                AppQMessageBox.StandardButton.Ok | AppQMessageBox.StandardButton.Cancel,
                2,
            ),
            (
                AppQMessageBox.StandardButton.Save
                | AppQMessageBox.StandardButton.Discard
                | AppQMessageBox.StandardButton.Cancel,
                3,
            ),
        )
        widths = []

        for buttons, count in configurations:
            with self.subTest(buttonCount=count):
                messageBox = AppQMessageBox(
                    icon=AppQMessageBox.Icon.Question,
                    text='Ready',
                    buttons=buttons,
                )
                messageBox.show()

                processQtEvents()

                actionButtons = messageBox.buttons()

                self.assertEqual(len(actionButtons), count)
                self.assertTrue(
                    all(
                        button.width() > button.height() * 2 for button in actionButtons
                    )
                )

                geometries = sorted(
                    (button.geometry() for button in actionButtons),
                    key=lambda geometry: geometry.x(),
                )

                for left, right in zip(geometries, geometries[1:]):
                    self.assertGreaterEqual(
                        right.left() - left.right() - 1,
                        messageBox.ButtonSpacing,
                    )

                if count > 1:
                    self.assertLessEqual(
                        max(button.width() for button in actionButtons)
                        - min(button.width() for button in actionButtons),
                        1,
                    )

                if buttons & AppQMessageBox.StandardButton.Discard:
                    discard = messageBox.button(AppQMessageBox.StandardButton.Discard)
                    self.assertEqual(
                        discard.property('messageBoxRole'),
                        'destructive',
                    )

                widths.append(messageBox.width())

                messageBox.close()

        self.assertLess(widths[0], widths[2])

    def testMessageBoxEscapeUsesConfiguredCancelResult(self):
        """Preserve Escape semantics without leaving masks or open-box owners."""
        messageBox = AppQMessageBox(
            text='Continue?',
            buttons=(
                AppQMessageBox.StandardButton.Yes | AppQMessageBox.StandardButton.Cancel
            ),
        )

        finished = []

        messageBox.finished.connect(finished.append)
        messageBox.setEscapeButton(AppQMessageBox.StandardButton.Cancel)
        messageBox.show()

        QTest.keyClick(messageBox, QtCore.Qt.Key.Key_Escape)

        processQtEvents()

        self.assertEqual(
            finished,
            [int(AppQMessageBox.StandardButton.Cancel)],
        )
        self.assertEqual(AppQDialog._openDialogs, {})


class SharedConnectionPresentationTest(unittest.TestCase):
    """Keep Home and tray adapters synchronized to one controller state."""

    @classmethod
    def setUpClass(cls):
        application()

    def tearDown(self):
        collectAtBoundary()

    def testHomeSelectionPolicyAndTrayPresentationShareController(self):
        """Apply selection only to Home while lifecycle text remains identical."""
        controller = ConnectionController()
        activation = mock.Mock(return_value=True)

        with (
            mock.patch(
                'Furious.Widget.ConnectionButton.AppConnectionController',
                return_value=controller,
            ),
            mock.patch(
                'Furious.Actions.Connection.AppConnectionController',
                return_value=controller,
            ),
            mock.patch.object(controller, 'toggle', return_value=True) as toggle,
        ):
            home = ConnectionButton(activation)
            tray = ConnectAction()

            home.setSelectionCount(0)

            self.assertTrue(home.isEnabled())

            home.click()
            toggle.assert_not_called()

            home.setSelectionCount(2)

            self.assertFalse(home.isEnabled())

            home.setSelectionCount(1)

            self.assertTrue(home.isEnabled())

            home.click()
            activation.assert_called_once()
            toggle.assert_called_once()

            for state, enabled in (
                (ConnectionState.Connecting, False),
                (ConnectionState.Connected, True),
                (ConnectionState.Disconnecting, False),
                (ConnectionState.Disconnected, True),
            ):
                controller._setState(state)

                processQtEvents()

                self.assertEqual(home.text(), tray.text())
                self.assertEqual(home.isEnabled(), enabled)
                self.assertEqual(tray.isEnabled(), enabled)

            tray.deleteLater()
            home.deleteLater()

        controller.deleteLater()


if __name__ == '__main__':
    unittest.main()
