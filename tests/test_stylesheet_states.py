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

from Furious.Qt import (
    AppQComboBox,
    AppQLineEdit,
    AppQListView,
    AppQMenu,
    AppQTableView,
    AppStyleSheet,
)
from Furious.Widget.NavigationView import NavigationView

from PySide6 import QtCore
from PySide6.QtGui import (
    QColor,
    QImage,
    QPalette,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QPushButton,
    QStyleOptionButton,
    QToolButton,
    QWidget,
)

from tests.support import application, collectAtBoundary, processQtEvents, waitFor

import shiboken6
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

    def assertItemViewInsetsAndListCorners(self, view, theme):
        """Check zero table padding and intact padded list corners."""
        if isinstance(view, AppQTableView):
            self.assertEqual(view.contentsRect(), view.rect().adjusted(1, 1, -1, -1))
            return

        actual = view.grab().toImage()
        frame = QImage(actual.size(), QImage.Format.Format_ARGB32_Premultiplied)
        frame.setDevicePixelRatio(actual.devicePixelRatio())
        frame.fill(QtCore.Qt.transparent)

        view.render(frame, renderFlags=QWidget.RenderFlag.DrawWindowBackground)

        panel = QColor(AppStyleSheet.Palettes[theme]['panel'])
        paddingPoint = QtCore.QPoint(view.width() // 2, 2)
        host = view.parentWidget()
        hostImage = host.grab().toImage()
        hostPoint = view.mapTo(host, paddingPoint)

        self.assertEqual(
            hostImage.pixelColor(
                round(hostPoint.x() * hostImage.devicePixelRatio()),
                round(hostPoint.y() * hostImage.devicePixelRatio()),
            ),
            QColor(AppStyleSheet.Palettes[theme]['window']),
        )

        cornerSize = round(8 * actual.devicePixelRatio())

        for left in (0, actual.width() - cornerSize):
            for top in (0, actual.height() - cornerSize):
                checked = 0

                for x in range(left, left + cornerSize):
                    for y in range(top, top + cornerSize):
                        expected = frame.pixelColor(x, y)

                        if expected.alpha() and expected != panel:
                            self.assertEqual(
                                actual.pixelColor(x, y),
                                expected,
                                f"frame pixel {(x, y)}",
                            )
                            checked += 1

                self.assertGreater(checked, 0)

    def testItemViewInsetsAndListCornersAcrossThemes(self):
        """Keep table insets and list corners stable while resizing and scrolling."""
        app = application()
        originalStyleSheet = app.styleSheet()

        try:
            for viewType in (AppQTableView, AppQListView):
                host = QWidget()
                view = viewType(host)
                view.move(10, 10)

                model = QStandardItemModel(view)

                for row in range(20):
                    model.appendRow([QStandardItem(f'Item {row}') for _ in range(5)])

                view.setModel(model)
                view.setAlternatingRowColors(True)

                try:
                    for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
                        app.setStyleSheet(AppStyleSheet.forTheme(theme))

                        for direction in (QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft):
                            view.setLayoutDirection(direction)

                            for size in (
                                QtCore.QSize(360, 180),
                                QtCore.QSize(620, 340),
                            ):
                                with self.subTest(
                                    view=viewType,
                                    theme=theme,
                                    direction=direction,
                                    size=size,
                                ):
                                    view.resize(size)
                                    host.resize(size + QtCore.QSize(20, 20))
                                    host.show()
                                    view.setCurrentIndex(model.index(0, 0))
                                    view.scrollToTop()
                                    processQtEvents()

                                    self.assertItemViewInsetsAndListCorners(view, theme)

                                    view.setCurrentIndex(model.index(19, 4))
                                    view.scrollToBottom()
                                    view.horizontalScrollBar().setValue(
                                        view.horizontalScrollBar().maximum()
                                    )
                                    processQtEvents()

                                    self.assertItemViewInsetsAndListCorners(view, theme)

                    model.clear()
                    processQtEvents()

                    self.assertItemViewInsetsAndListCorners(view, AppStyleSheet.Dark)

                    viewportImage = view.viewport().grab().toImage()
                    self.assertEqual(
                        viewportImage.pixelColor(viewportImage.rect().center()),
                        QColor(AppStyleSheet.Palettes[AppStyleSheet.Dark]['panel']),
                    )
                finally:
                    host.close()
                    host.deleteLater()
                    processQtEvents()
        finally:
            app.setStyleSheet(originalStyleSheet)

    def assertRoundedPopup(self, popup):
        """Require clear outer corners and an opaque painted surface."""
        image = popup.grab().toImage()
        self.assertTrue(image.hasAlphaChannel())

        for x in (0, image.width() - 1):
            for y in (0, image.height() - 1):
                self.assertEqual(image.pixelColor(x, y).alpha(), 0)

        self.assertEqual(
            image.pixelColor(image.width() // 2, image.height() // 2).alpha(), 255
        )
        self.assertTrue(popup.windowFlags() & QtCore.Qt.WindowType.FramelessWindowHint)

    def testMenuCornersStayTransparentAcrossThemesAndReopens(self):
        """Keep menu and submenu surfaces rounded without changing activation."""
        app = application()
        originalStyleSheet = app.styleSheet()

        menu = AppQMenu()
        action = menu.addAction('Example')
        action.setCheckable(True)

        submenu = AppQMenu(parent=menu)
        submenu.setTitle('More')
        submenu.addAction('Another example')

        menu.addMenu(submenu)

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark) * 3:
                app.setStyleSheet(AppStyleSheet.forTheme(theme))

                for direction in (QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft):
                    with self.subTest(theme=theme, direction=direction):
                        # Reproduce the shadow installed by the Windows 11 style
                        # even when the headless test application uses Fusion.
                        shadow = QGraphicsDropShadowEffect(menu)
                        shadow.setBlurRadius(3)
                        shadow.setOffset(3, 3)

                        menu.setGraphicsEffect(shadow)
                        menu.setLayoutDirection(direction)
                        menu.popup(QtCore.QPoint(20, 20))
                        processQtEvents()

                        self.assertRoundedPopup(menu)
                        self.assertFalse(shiboken6.isValid(shadow))

                        menu.setActiveAction(submenu.menuAction())
                        openKey = (
                            QtCore.Qt.Key_Right
                            if direction == QtCore.Qt.LeftToRight
                            else QtCore.Qt.Key_Left
                        )

                        QTest.keyClick(menu, openKey)
                        waitFor(submenu.isVisible)

                        self.assertRoundedPopup(submenu)

                        QTest.keyClick(submenu, QtCore.Qt.Key_Escape)

                        self.assertFalse(submenu.isVisible())

                        menu.setActiveAction(action)
                        wasChecked = action.isChecked()

                        QTest.keyClick(menu, QtCore.Qt.Key_Return)

                        self.assertEqual(action.isChecked(), not wasChecked)
                        self.assertFalse(menu.isVisible())
        finally:
            menu.close()
            menu.deleteLater()
            processQtEvents()

            app.setStyleSheet(originalStyleSheet)

    def testComboPopupCornersStayTransparentAcrossThemesAndReopens(self):
        """Paint one rounded view and retain native keyboard selection and reuse."""
        app = application()
        originalStyleSheet = app.styleSheet()

        combo = AppQComboBox()
        combo.addItems(['First', 'Second', 'Third'])
        combo.resize(260, 36)
        combo.show()

        popup = combo.view().window()
        # Some native styles already enable translucency while polishing.
        popup.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark) * 3:
                app.setStyleSheet(AppStyleSheet.forTheme(theme))

                for direction in (QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft):
                    with self.subTest(theme=theme, direction=direction):
                        shadow = QGraphicsDropShadowEffect(popup)
                        shadow.setBlurRadius(3)
                        shadow.setOffset(3, 3)
                        popup.setGraphicsEffect(shadow)

                        combo.setLayoutDirection(direction)
                        combo.setCurrentIndex(0)
                        combo.showPopup()
                        processQtEvents()

                        self.assertIs(combo.view().window(), popup)
                        self.assertRoundedPopup(popup)

                        # Dropdown padding must remain opaque over the page below.
                        popupImage = combo.view().grab().toImage()
                        self.assertEqual(
                            popupImage.pixelColor(
                                popupImage.width() // 2,
                                round(2 * popupImage.devicePixelRatio()),
                            ).alpha(),
                            255,
                        )
                        self.assertFalse(shiboken6.isValid(shadow))

                        QTest.keyClick(combo.view(), QtCore.Qt.Key_Down)
                        QTest.keyClick(combo.view(), QtCore.Qt.Key_Return)

                        self.assertEqual(combo.currentIndex(), 1)
                        self.assertFalse(popup.isVisible())

                        combo.showPopup()
                        processQtEvents()

                        self.assertRoundedPopup(popup)

                        QTest.keyClick(combo.view(), QtCore.Qt.Key_Escape)

                        self.assertFalse(popup.isVisible())
                        self.assertEqual(combo.currentIndex(), 1)
        finally:
            combo.hidePopup()
            combo.close()
            combo.deleteLater()
            processQtEvents()
            app.setStyleSheet(originalStyleSheet)

    def testClearButtonKeepsNativeBehaviorAndGeometryAcrossThemes(self):
        """Keep embedded buttons centered, theme-correct and bounded after restyling."""
        app = application()
        originalStyleSheet = app.styleSheet()

        edit = AppQLineEdit()
        edit.setClearButtonEnabled(True)
        edit.resize(340, 36)
        edit.show()
        edit.activateWindow()
        edit.setFocus()

        try:
            for theme in (AppStyleSheet.Light, AppStyleSheet.Dark) * 3:
                for direction in (QtCore.Qt.LeftToRight, QtCore.Qt.RightToLeft):
                    with self.subTest(theme=theme, direction=direction):
                        edit.setLayoutDirection(direction)
                        edit.setText('example search')
                        edit.setSelection(0, 7)

                        app.setStyleSheet(AppStyleSheet.forTheme(theme))
                        processQtEvents()

                        self.assertEqual(edit.selectedText(), 'example')

                        buttons = edit.findChildren(QToolButton)
                        self.assertEqual(len(buttons), 1)
                        button = buttons[0]
                        self.assertTrue(edit.rect().contains(button.geometry()))
                        self.assertLessEqual(
                            abs(
                                button.geometry().center().y()
                                - edit.rect().center().y()
                            ),
                            1,
                        )

                        self.assertFalse(button.icon().isNull())
                        pixmap = button.icon().pixmap(16, 16).toImage()
                        colors = [
                            pixmap.pixelColor(x, y)
                            for x in range(pixmap.width())
                            for y in range(pixmap.height())
                            if pixmap.pixelColor(x, y).alpha() > 128
                        ]

                        self.assertTrue(colors)
                        self.assertTrue(
                            all(
                                (color.lightness() > 128)
                                == (theme == AppStyleSheet.Dark)
                                for color in colors
                            )
                        )

                        QTest.mouseClick(button, QtCore.Qt.LeftButton)

                        self.assertEqual(edit.text(), '')
                        self.assertTrue(edit.hasFocus())
                        self.assertTrue(waitFor(lambda: not button.isVisible()))

            edit.setText('read only')
            edit.setReadOnly(True)
            app.setStyleSheet(AppStyleSheet.forTheme(AppStyleSheet.Light))
            processQtEvents()

            self.assertEqual(edit.text(), 'read only')
            self.assertFalse(edit.findChild(QToolButton).isEnabled())

            app.setStyleSheet(AppStyleSheet.forTheme(AppStyleSheet.Dark))
            edit.setClearButtonEnabled(False)
            processQtEvents()

            self.assertFalse(edit.isClearButtonEnabled())
            self.assertFalse(edit.findChildren(QToolButton))
        finally:
            edit.close()
            edit.deleteLater()
            processQtEvents()

            app.setStyleSheet(originalStyleSheet)

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
