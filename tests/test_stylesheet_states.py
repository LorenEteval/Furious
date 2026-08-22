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

"""Protect the application's intentional visual-state precedence."""

from __future__ import annotations

from Furious.Qt import AppStyleSheet
from Furious.Widget.NavigationView import NavigationView

from PySide6 import QtCore
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QStyleOptionButton, QWidget

from tests.support import application, collectAtBoundary, processQtEvents

import unittest


class StyleSheetStateRenderingTest(unittest.TestCase):
    """Exercise focus and disabled precedence through Qt's styled renderer."""

    @classmethod
    def setUpClass(cls):
        """Create the process-wide headless QApplication."""
        application()

    def tearDown(self):
        """Finish deferred widget deletion between tests."""
        collectAtBoundary()

    @staticmethod
    def focusedEdgeColors(button):
        """Render the four straight edge centers of a focused, hovered button."""
        button.resize(220, 40)
        button.show()
        button.setFocus(QtCore.Qt.FocusReason.TabFocusReason)
        QTest.mouseMove(button, button.rect().center())
        processQtEvents()

        image = button.grab().toImage()
        points = (
            (image.width() // 2, 0),
            (image.width() - 1, image.height() // 2),
            (image.width() // 2, image.height() - 1),
            (0, image.height() // 2),
        )
        colors = tuple(image.pixelColor(*point).rgba() for point in points)

        button.close()
        button.deleteLater()

        return colors

    @staticmethod
    def disabledButtonTextColor(button):
        """Return the effective styled text color for one disabled button."""
        button.setDisabled(True)
        button.resize(220, 40)
        button.show()
        processQtEvents()

        option = QStyleOptionButton()
        button.initStyleOption(option)
        color = option.palette.color(QPalette.ColorRole.ButtonText).rgba()

        button.close()
        button.deleteLater()

        return color

    def testFlatAndLinkButtonsRetainFocusedOutlineDuringHover(self):
        """Do not let flat presentation clear the keyboard-focus frame."""
        app = application()
        originalStyleSheet = app.styleSheet()

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                app.setStyleSheet(AppStyleSheet.forTheme(theme))

                regular = QPushButton('Regular')
                flat = QPushButton('Flat')
                flat.setFlat(True)
                link = QPushButton('Link')
                link.setFlat(True)
                link.setObjectName('SettingsLinkButton')

                expected = self.focusedEdgeColors(regular)

                with self.subTest(theme=theme, button='flat'):
                    self.assertEqual(self.focusedEdgeColors(flat), expected)

                with self.subTest(theme=theme, button='settings-link'):
                    self.assertEqual(self.focusedEdgeColors(link), expected)
        finally:
            app.setStyleSheet(originalStyleSheet)

    def testObjectSpecificButtonsUseDisabledForeground(self):
        """Do not let object-name color rules defeat disabled semantics."""
        app = application()
        originalStyleSheet = app.styleSheet()

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                app.setStyleSheet(AppStyleSheet.forTheme(theme))
                expected = self.disabledButtonTextColor(QPushButton('Disabled'))

                for objectName in ('SettingsLinkButton', 'NavigationPageButton'):
                    button = QPushButton('Disabled')
                    button.setObjectName(objectName)

                    if objectName == 'NavigationPageButton':
                        button.setCheckable(True)
                        button.setChecked(True)

                    with self.subTest(theme=theme, objectName=objectName):
                        self.assertEqual(
                            self.disabledButtonTextColor(button),
                            expected,
                        )
        finally:
            app.setStyleSheet(originalStyleSheet)

    def testNavigationCompositeLabelTracksItsOwnVisualState(self):
        """Style the real navigation label without ancestor pseudo-states."""
        app = application()
        originalStyleSheet = app.styleSheet()

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                app.setStyleSheet(AppStyleSheet.forTheme(theme))

                navigation = NavigationView()
                navigation.addPage('home', QWidget(), 'Home', 'house-door.svg')
                navigation.addPage('log', QWidget(), 'Log', 'pin-angle.svg')
                navigation.setExpanded(True, animated=False)
                navigation.resize(240, 400)
                navigation.show()
                processQtEvents()

                homeButton = navigation._pages['home'].button
                logButton = navigation._pages['log'].button
                homeLabel = homeButton._textLabel
                logLabel = logButton._textLabel
                palette = AppStyleSheet.paletteForTheme(theme)

                with self.subTest(theme=theme, state='selected'):
                    self.assertEqual(
                        homeLabel.palette().color(QPalette.ColorRole.WindowText),
                        QColor(palette['text_strong']),
                    )

                with self.subTest(theme=theme, state='unselected'):
                    self.assertEqual(
                        logLabel.palette().color(QPalette.ColorRole.WindowText),
                        QColor(palette['text']),
                    )

                navigation.setCurrentPage('log')
                processQtEvents()

                with self.subTest(theme=theme, state='selection-changed'):
                    self.assertEqual(
                        homeLabel.palette().color(QPalette.ColorRole.WindowText),
                        QColor(palette['text']),
                    )
                    self.assertEqual(
                        logLabel.palette().color(QPalette.ColorRole.WindowText),
                        QColor(palette['text_strong']),
                    )

                navigation.setDisabled(True)
                processQtEvents()

                for label in (homeLabel, logLabel):
                    with self.subTest(theme=theme, state='disabled'):
                        self.assertEqual(
                            label.palette().color(QPalette.ColorRole.WindowText),
                            QColor(palette['disabled']),
                        )

                navigation.close()
                navigation.deleteLater()
                processQtEvents()
        finally:
            app.setStyleSheet(originalStyleSheet)


class StyleSheetStateCompositionTest(unittest.TestCase):
    """Protect shared composite geometry and semantic-state selector ordering."""

    def testCompositeInputSubcontrolsRemainInsideTheOuterFrame(self):
        """Keep combo and spin hover fills out of the focus-border region."""
        selectors = (
            'QComboBox::drop-down {',
            'QSpinBox::up-button,',
            'QSpinBox::down-button,',
        )

        for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
            stylesheet = AppStyleSheet.forTheme(theme)

            for selector in selectors:
                with self.subTest(theme=theme, selector=selector):
                    rule = stylesheet.split(selector, 1)[1].split('}', 1)[0]

                    self.assertIn('subcontrol-origin: padding;', rule)

    def testSemanticStateSelectorsCannotBeReplacedByDecorativeHover(self):
        """Keep selected, checked, and disabled semantics above hover styling."""
        protectedRelationships = (
            ('QListView::item:hover {', 'QListView::item:selected {'),
            ('QToolButton:hover {', 'QToolButton:checked {'),
            ('QMenu::item:selected {', 'QMenu::item:disabled:selected {'),
            ('QCheckBox::indicator:hover {', 'QCheckBox::indicator:checked {'),
            ('QCheckBox::indicator:checked {', 'QCheckBox::indicator:disabled,'),
        )

        for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
            stylesheet = AppStyleSheet.forTheme(theme)

            for decorative, semantic in protectedRelationships:
                with self.subTest(theme=theme, semantic=semantic):
                    self.assertLess(
                        stylesheet.index(decorative),
                        stylesheet.index(semantic),
                    )

            self.assertIn('QTabBar::tab:hover:!selected {', stylesheet)
            self.assertIn('QPushButton:flat:focus {', stylesheet)
            self.assertIn('QPushButton#SettingsLinkButton:disabled {', stylesheet)
            self.assertIn(
                'QPushButton#NavigationPageButton:checked:disabled {',
                stylesheet,
            )


if __name__ == '__main__':
    unittest.main()
