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
from Furious.Models import ServerProfile
from Furious.Plugins import exportConfiguration
from Furious.Repository import Storage
from Furious.Qt import (
    AppQMainWindow,
    AppQTabWidget,
    connectWeakly,
)
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

import segno
import logging

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    'MAXIMUM_QR_EXPORT_PROFILES',
    'QRCodeExportItem',
    'QRCodeWindow',
    'captureQRCodeExportItems',
]

_QR_ERROR_CORRECTION = 'H'
_QR_PAGE_MARGIN = 28
MAXIMUM_QR_EXPORT_PROFILES = 50

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


@dataclass(frozen=True)
class QRCodeExportItem:
    """Capture one profile exactly as selected for later QR export."""

    position: int
    remark: str
    profile: ServerProfile


def captureQRCodeExportItems(
    indexes: Iterable[int],
    profiles: Sequence[ServerProfile] | None = None,
) -> tuple[QRCodeExportItem, ...]:
    """Snapshot at most the first eligible selected profiles in caller order."""
    sourceProfiles = Storage.UserServers() if profiles is None else profiles
    items = []

    for rawIndex in indexes:
        if len(items) >= MAXIMUM_QR_EXPORT_PROFILES:
            break

        try:
            index = int(rawIndex)
        except (TypeError, ValueError):
            continue

        if index < 0 or index >= len(sourceProfiles):
            continue

        profile = sourceProfiles[index]

        try:
            snapshot = profile.deepcopy()
        except Exception as ex:
            # Any non-exit exceptions

            # A malformed plugin profile must not abort the remaining export.
            logger.warning(
                'unable to snapshot profile %d for QR presentation (%s)',
                index + 1,
                type(ex).__name__,
            )

            continue

        items.append(
            QRCodeExportItem(
                position=index + 1,
                remark=str(profile.itemRemark),
                profile=snapshot,
            )
        )

    return tuple(items)


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
    """Incrementally present exported configurations in QR-code tabs."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(720, 680)
    MINIMUM_WINDOW_SIZE = QtCore.QSize(520, 520)

    def __init__(self, *args, **kwargs):
        """Initialize the transient, resizable QR-code window."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_(APPLICATION_NAME))
        self.setMinimumSize(self.MINIMUM_WINDOW_SIZE)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._exportItems = tuple()
        self._exportProcessedCount = 0
        self._exportGeneratedCount = 0
        self._exporting = False
        self._exportTimer = QtCore.QTimer(self)
        self._exportTimer.setSingleShot(True)

        connectWeakly(
            self._exportTimer.timeout,
            self,
            'processNextExportItem',
            sender=self._exportTimer,
        )

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

    def isExporting(self) -> bool:
        """Return whether incremental QR generation still owns pending items."""
        return self._exporting

    def exportProcessedCount(self) -> int:
        """Return the number of items attempted by the current export."""
        return self._exportProcessedCount

    def exportGeneratedCount(self) -> int:
        """Return the number of tabs generated by the current export."""
        return self._exportGeneratedCount

    def _clearTabs(self):
        """Remove and destroy every page currently owned by the tab widget."""
        while self.tabWidget.count():
            page = self.tabWidget.widget(0)

            self.tabWidget.removeTab(0)

            if page is not None:
                page.deleteLater()

    def appendExportItem(self, item: QRCodeExportItem) -> bool:
        """Generate and append one captured profile without affecting its siblings."""
        try:
            uri = exportConfiguration(item.profile)
        except Exception as ex:
            # Any non-exit exceptions

            logger.warning(
                'unable to export profile %d for QR presentation (%s)',
                item.position,
                type(ex).__name__,
            )

            return False

        if not uri:
            return False

        try:
            image = createQRCodeImage(uri)
        except (segno.DataOverflowError, ValueError) as ex:
            logger.warning(
                'unable to create QR code for profile %d (%s)',
                item.position,
                type(ex).__name__,
            )

            return False
        except Exception as ex:
            # Any non-exit exceptions

            logger.warning(
                'unable to create QR code for profile %d (%s)',
                item.position,
                type(ex).__name__,
            )

            return False

        page = _QRCodePage(image, parent=self.tabWidget)
        title = f'{item.position} - {item.remark}'

        tabIndex = self.tabWidget.addTab(page, title)

        self.tabWidget.setTabToolTip(tabIndex, title)

        return True

    def initTabByIndex(self, indexes: list[int]):
        """Synchronously initialize capped tabs for compatibility callers."""
        self.cancelExport()
        self._clearTabs()

        for item in captureQRCodeExportItems(indexes):
            self.appendExportItem(item)

    def startExportByIndex(self, indexes: Iterable[int]):
        """Start one bounded, window-owned incremental QR export."""
        items = captureQRCodeExportItems(tuple(indexes))

        self.cancelExport()
        self._clearTabs()
        self._exportProcessedCount = 0
        self._exportGeneratedCount = 0

        if not items:
            self.deleteLater()

            return None

        if len(items) == 1:
            if self.appendExportItem(items[0]):
                self._exportProcessedCount = 1
                self._exportGeneratedCount = 1
                self.show()
            else:
                self._exportProcessedCount = 1
                self.deleteLater()

            return self

        self._exportItems = items
        self._exporting = True
        self.show()
        self._exportTimer.start(0)

        return self

    def processNextExportItem(self):
        """Attempt one captured profile, then yield to the Qt event loop."""
        if not self._exporting:
            return

        if self._exportProcessedCount >= len(self._exportItems):
            self.finishExport()

            return

        item = self._exportItems[self._exportProcessedCount]
        generated = self.appendExportItem(item)

        self._exportProcessedCount += 1
        self._exportGeneratedCount += int(generated)

        if self._exportProcessedCount >= len(self._exportItems):
            self.finishExport()

            return

        self._exportTimer.start(0)

    def finishExport(self):
        """Release completed export state and discard an empty result window."""
        if not self._exporting:
            return

        generatedCount = self._exportGeneratedCount

        self._exportTimer.stop()
        self._exportItems = tuple()
        self._exporting = False

        if generatedCount == 0:
            self.close()

    def cancelExport(self):
        """Cancel pending work without removing tabs already generated."""
        self._exportTimer.stop()
        self._exportItems = tuple()
        self._exporting = False

    def closeEvent(self, event):
        """Cancel an active export after Qt accepts closing this window."""
        super().closeEvent(event)

        if event.isAccepted():
            self.cancelExport()

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
