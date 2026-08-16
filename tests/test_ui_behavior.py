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
from Furious.Backends.Xray.RoutingWindow import RoutingRulesDialog
from Furious.Models import ProfileMetadata, ServerProfile
from Furious.Qt import AppQMessageBox
from Furious.Service import (
    APPLICATION_LOG_CATEGORY,
    CORE_LOG_CATEGORY,
    LogManager,
)
from Furious.Window.LogPage import LogPage
from Furious.Window.SubscriptionPage import _SubscriptionEditorDialog

from tests.support import (
    application,
    collectAtBoundary,
    isolatedSettings,
    processQtEvents,
)

import copy
import unittest


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
            }
        )
        profile = ServerProfile.fromConfiguration(
            configuration,
            ProfileMetadata(displayName='Fixture core'),
        )

        with isolatedSettings():
            editor = ExternalCoreEditor()
            editor.factoryToInput(profile)

            self.assertEqual(
                editor._argumentsInput.values(),
                ['--config', 'name with spaces.json'],
            )
            self.assertEqual(
                editor._environmentInput.values(),
                {'TOKEN': 'one=two', 'UNICODE': '测试'},
            )
            self.assertTrue(editor._applicationTun2socksInput.isChecked())
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

            processQtEvents()

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['application one', 'core one'],
            )

            page.hide()
            manager.append('core two', CORE_LOG_CATEGORY)

            processQtEvents()

            self.assertNotIn('core two', page.textBrowser.toPlainText())

            page.show()

            processQtEvents()

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['application one', 'core one', 'core two'],
            )

            coreIndex = page.filterComboBox.findData(CORE_LOG_CATEGORY)
            page.filterComboBox.setCurrentIndex(coreIndex)

            processQtEvents()

            self.assertEqual(
                page.textBrowser.toPlainText().splitlines(),
                ['core one', 'core two'],
            )

            page.close()
            page.deleteLater()


class DialogBehaviorTest(unittest.TestCase):
    """Exercise no-selection guards and QMessageBox-compatible results."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish every deferred transient deletion between tests."""
        collectAtBoundary()

    def testRoutingRulesActionsStayEnabledAndNoSelectionIsSafe(self):
        """Keep the compact top actions visible without creating a warning."""
        dialog = RoutingRulesDialog({'rules': []})

        self.assertTrue(dialog.addButton.isEnabled())
        self.assertTrue(dialog.deleteButton.isEnabled())
        self.assertTrue(dialog.closeWindowButton.isEnabled())
        self.assertIsNotNone(dialog.layout().itemAt(0).layout())
        self.assertIs(dialog.layout().itemAt(1).widget(), dialog.listWidget)

        dialog.deleteRule()
        dialog.editRule()

        self.assertEqual(AppQMessageBox._openMessageBoxes, {})
        self.assertEqual(dialog.routing['rules'], [])

        dialog.closeWindowButton.click()

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


if __name__ == '__main__':
    unittest.main()
