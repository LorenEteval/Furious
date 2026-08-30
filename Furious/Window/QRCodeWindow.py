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

"""Present exported server configurations as centered QR codes."""

from __future__ import annotations

from Furious.Frozenlib import APPLICATION_NAME
from Furious.Plugins import exportConfiguration
from Furious.Repository import Storage
from Furious.Qt import AppQMainWindow, AppQTabWidget, connectWeakly
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

import segno
import logging

__all__ = ['QRCodeWindow']

_QR_ERROR_CORRECTION = 'H'
_QR_PAGE_MARGIN = 28

logger = logging.getLogger(__name__)


def createQRCodeImage(data: str) -> QImage:
    """Render opaque text as one grayscale pixel per QR module."""
    if not isinstance(data, str) or not data:
        raise ValueError('QR code data must be a non-empty string')

    qrcode = segno.make_qr(data, error=_QR_ERROR_CORRECTION)
    border = qrcode.default_border_size
    width, height = qrcode.symbol_size(scale=1, border=border)

    if width != height:
        raise ValueError('QR code matrix must be square')

    image = QImage(width, height, QImage.Format.Format_Grayscale8)
    image.fill(255)

    for y, row in enumerate(qrcode.matrix_iter(scale=1, border=border)):
        image.scanLine(y)[:width] = bytes(0 if module else 255 for module in row)

    return image


class _QRCodePage(QWidget):
    """Own and responsively present one logical QR image inside a tab page."""

    def __init__(self, image: QImage, parent=None):
        """Create a centered, margin-managed QR presentation page."""
        super().__init__(parent)

        if image.isNull() or image.width() != image.height():
            raise ValueError('QR code image must be a non-null square')

        self.setObjectName('QRCodePage')

        self._sourceImage = QImage(image)
        self._displayScale = 0

        self.qrLabel = QLabel(parent=self)
        self.qrLabel.setObjectName('QRCodeImage')
        self.qrLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.qrLabel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            _QR_PAGE_MARGIN,
            _QR_PAGE_MARGIN,
            _QR_PAGE_MARGIN,
            _QR_PAGE_MARGIN,
        )
        self._layout.setSpacing(0)
        self._layout.addWidget(
            self.qrLabel,
            1,
            QtCore.Qt.AlignmentFlag.AlignCenter,
        )

        self._refreshPixmap()

    def sourceImage(self) -> QImage:
        """Return an implicitly shared copy of the logical QR image."""
        return QImage(self._sourceImage)

    def moduleSpan(self) -> int:
        """Return the QR width expressed in modules including its quiet zone."""
        return self._sourceImage.width()

    def displayScale(self) -> int:
        """Return the integer scale currently used by the presentation pixmap."""
        return self._displayScale

    def _targetScale(self) -> int:
        """Return the largest integer scale that fits this page."""
        available = self._layout.contentsRect().size()
        availableSide = min(available.width(), available.height())

        if availableSide <= 0:
            return 1

        return max(1, availableSide // self.moduleSpan())

    def _refreshPixmap(self):
        """Scale the cached image without regenerating or smoothing QR modules."""
        displayScale = self._targetScale()

        if displayScale == self._displayScale:
            return

        self._displayScale = displayScale

        targetSide = self.moduleSpan() * displayScale

        self.qrLabel.setPixmap(
            QPixmap.fromImage(
                self._sourceImage.scaled(
                    targetSide,
                    targetSide,
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.FastTransformation,
                )
            )
        )

    def resizeEvent(self, event):
        """Refresh only the displayed raster when the available page size changes."""
        super().resizeEvent(event)

        self._refreshPixmap()

    def showEvent(self, event):
        """Fit the QR pixmap after the tab layout receives its final geometry."""
        super().showEvent(event)

        # A newly selected tab has its final page geometry before Qt lays out its
        # hidden children. Activate this page synchronously so its first rendered
        # pixmap uses the available tab area instead of the construction-time size.
        self._layout.activate()

        self._refreshPixmap()


class QRCodeWindow(AppQMainWindow):
    """Present exported configurations in independent QR-code tabs."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(720, 680)
    MINIMUM_WINDOW_SIZE = QtCore.QSize(520, 520)

    def __init__(self, *args, **kwargs):
        """Initialize the transient, resizable QR-code window."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setMinimumSize(self.MINIMUM_WINDOW_SIZE)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.tabWidget = AppQTabWidget(parent=self, translatable=False)
        self.tabWidget.setTabsClosable(True)
        self.tabWidget.setElideMode(QtCore.Qt.TextElideMode.ElideRight)

        connectWeakly(
            self.tabWidget.tabCloseRequested,
            self,
            'handleTabCloseRequested',
        )

        self.setCentralWidget(self.tabWidget)

    def tabCount(self) -> int:
        """Return the number of successfully generated QR-code tabs."""
        return self.tabWidget.count()

    def _clearTabs(self):
        """Remove and destroy every page currently owned by the tab widget."""
        while self.tabWidget.count():
            page = self.tabWidget.widget(0)

            self.tabWidget.removeTab(0)

            if page is not None:
                page.deleteLater()

    def initTabByIndex(self, indexes: list[int]):
        """Replace the tabs with QR pages for the selected profile indexes."""
        self._clearTabs()

        profiles = Storage.UserServers()

        for index in indexes:
            config = profiles[index]

            try:
                uri = exportConfiguration(config)
            except Exception as ex:
                # Any non-exit exceptions
                logger.warning(
                    'unable to export profile %d for QR presentation (%s)',
                    index + 1,
                    type(ex).__name__,
                )
                continue

            if not uri:
                continue

            try:
                image = createQRCodeImage(uri)
            except (segno.DataOverflowError, ValueError) as ex:
                logger.warning(
                    'unable to create QR code for profile %d (%s)',
                    index + 1,
                    type(ex).__name__,
                )

                continue
            except Exception as ex:
                # Any non-exit exceptions

                continue

            page = _QRCodePage(image, parent=self.tabWidget)
            title = f'{index + 1} - {config.itemRemark}'

            tabIndex = self.tabWidget.addTab(page, title)

            self.tabWidget.setTabToolTip(tabIndex, title)

    @QtCore.Slot(int)
    def handleTabCloseRequested(self, index: int):
        """Destroy one requested page and close after the final tab is removed."""
        page = self.tabWidget.widget(index)

        if page is None:
            return

        self.tabWidget.removeTab(index)

        page.deleteLater()

        if self.tabWidget.count() == 0:
            self.close()
