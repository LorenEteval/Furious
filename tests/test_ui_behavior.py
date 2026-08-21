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

from Furious.Backends.ExternalCore.Configuration import (
    BLANK_CONFIG_EXTERNAL_CORE,
    ConfigExternalCore,
)
from Furious.Backends.ExternalCore.Editor import ExternalCoreEditor
from Furious.Backends.Hysteria1.Editor import Hysteria1Editor
from Furious.Backends.Hysteria2.Editor import Hysteria2Editor
from Furious.Backends.Xray.AssetListWidget import XrayAssetListWidget
from Furious.Backends.Xray.RoutingWindow import RoutingRulesDialog
from Furious.Backends.Xray.ShadowsocksEditor import ShadowsocksEditor
from Furious.Backends.Xray.SocksEditor import SocksEditor
from Furious.Backends.Xray.TrojanEditor import TrojanEditor
from Furious.Backends.Xray.VlessEditor import VlessEditor
from Furious.Backends.Xray.VmessEditor import VmessEditor
from Furious.Actions.Connection import ConnectAction
from Furious.Controllers.ConnectionController import (
    ConnectionController,
    ConnectionState,
)
from Furious.Controllers.SettingsController import (
    LOG_AUTO_CLEAR_SETTING,
    LOG_AUTO_SCROLL_DOWN_SETTING,
)
from Furious.Frozenlib import AppSettings, Mixins
from Furious.Models import ProfileMetadata, ServerProfile
from Furious.Qt import AppHue, AppQMessageBox, AppQSwitch, gettext as _
from Furious.Service import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    TUN2SOCKS_LOG_CATEGORY,
    LogManager,
)
from Furious.Window.LogPage import LogPage
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog
from Furious.Widget.ConnectionButton import ConnectionButton

from PySide6 import QtCore
from PySide6.QtTest import QTest

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


class EditorMappingTest(unittest.TestCase):
    """Verify editor fields preserve structured configuration semantics."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish every deferred transient deletion between tests."""
        collectAtBoundary()

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
            self.assertEqual(len(editor.groupBoxSequence()), 1)
            self.assertAlmostEqual(editor.height() / editor.width(), 1.618, places=2)

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

        self.assertEqual(AppQMessageBox._openMessageBoxes, {})
        self.assertEqual(dialog.routing['rules'], [])

        dialog.closeWindowButton.click()

    def testAssetListViewKeepsRawFilenameInItsOwnedModel(self):
        """Keep filesystem identity separate from formatted asset row text."""
        with tempfile.TemporaryDirectory() as directory:
            assetDirectory = pathlib.Path(directory)
            filename = 'geo data.dat'
            (assetDirectory / filename).write_bytes(b'fixture')

            with mock.patch(
                'Furious.Backends.Xray.AssetListWidget.XRAY_ASSET_DIR',
                assetDirectory,
            ):
                view = XrayAssetListWidget()

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
        self.assertEqual(AppQMessageBox._openMessageBoxes, {})


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
