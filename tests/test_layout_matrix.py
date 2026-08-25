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

"""Exercise representative Fluent layouts in isolated display-scale processes."""

from __future__ import annotations

from tests.support import assertChildSucceeded, childEnvironment, runPythonChild

import unittest


class IsolatedDisplayMatrixTest(unittest.TestCase):
    """Keep navigation and transient dialogs stable across supported scales."""

    Script = r"""
from Furious.Qt import AppQDialog, AppQMessageBox, AppStyleSheet
from Furious.Widget import NavigationView

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget

from tests.support import application, collectAtBoundary, processQtEvents

app = application()
navigation = NavigationView()
navigation.resize(960, 640)

for index in range(5):
    navigation.addPage(
        f'page-{index}',
        QWidget(parent=navigation),
        f'Page {index} with a translated title',
        'house-door.svg',
    )

navigation.show()
processQtEvents()

for theme in (AppStyleSheet.Light, AppStyleSheet.Dark):
    app.setStyleSheet(AppStyleSheet.forTheme(theme))

    for expanded in (True, False, True):
        navigation.setExpanded(expanded, animated=False)
        processQtEvents()

        assert navigation.width() > 0
        assert navigation.height() > 0

    for index in range(5):
        page_id = f'page-{index}'
        navigation.setCurrentPage(page_id)
        processQtEvents()

        assert navigation.currentPageId() == page_id
        assert navigation.pageStack.currentWidget() is navigation.page(page_id)

    message_box = AppQMessageBox(
        icon=AppQMessageBox.Icon.Information,
        parent=navigation,
        heading='Scale and theme verification',
        text='A sufficiently long localized message must remain readable.',
        buttons=(
            AppQMessageBox.StandardButton.Ok
            | AppQMessageBox.StandardButton.Cancel
        ),
    )
    message_box.show()
    processQtEvents()

    assert message_box.width() >= 300
    assert message_box.height() >= 120
    assert message_box.surface.geometry().contains(
        message_box.contentFrame.geometry().center()
    )

    message_box.close()
    message_box.deleteLater()
    collectAtBoundary()

navigation.close()
navigation.deleteLater()
collectAtBoundary()

assert not AppQDialog._openDialogs
"""

    def testScaleAndThemeMatrix(self):
        """Run each scale before QApplication exists to honor Qt semantics."""
        for scale in ('1', '1.25', '1.5', '2'):
            with self.subTest(scale=scale):
                result = runPythonChild(
                    self.Script,
                    environment=childEnvironment(QT_SCALE_FACTOR=scale),
                )

                assertChildSucceeded(self, result, f'display scale {scale}')


if __name__ == '__main__':
    unittest.main()
