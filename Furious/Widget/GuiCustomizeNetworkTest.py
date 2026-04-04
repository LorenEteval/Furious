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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

import logging
import functools

__all__ = ['GuiCustomizeNetworkTestDialog']

logger = logging.getLogger(__name__)

registerAppSettings('CustomNetworkSpeedTestURL')
registerAppSettings('CustomNetworkConnectivityTestURL')


class GuiCustomizeNetworkTestDialog(AppQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Customize Network Test URL'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.speedTestURLText = AppQLabel(_('Enter network speed test URL:'))
        self.speedTestURLEdit = QLineEdit()

        speedTestURLSettings = AppSettings.get('CustomNetworkSpeedTestURL')

        if speedTestURLSettings is None:
            self.speedTestURLEdit.setText(NETWORK_SPEED_TEST_URL)
        else:
            self.speedTestURLEdit.setText(speedTestURLSettings)

        self.connectivityText = AppQLabel(_('Enter network connectivity test URL:'))
        self.connectivityEdit = QLineEdit()

        connectivitySettings = AppSettings.get('CustomNetworkConnectivityTestURL')

        if connectivitySettings is None:
            self.connectivityEdit.setText(NETWORK_CONNECTIVITY_TEST_URL)
        else:
            self.connectivityEdit.setText(connectivitySettings)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        self.speedTestURLResetBtn = AppQPushButton(_('Reset'))
        self.speedTestURLResetBtn.clicked.connect(
            lambda: self.speedTestURLEdit.setText(NETWORK_SPEED_TEST_URL)
        )
        self.connectivityResetBtn = AppQPushButton(_('Reset'))
        self.connectivityResetBtn.clicked.connect(
            lambda: self.connectivityEdit.setText(NETWORK_CONNECTIVITY_TEST_URL)
        )

        self.speedTestURLHboxLayout = QHBoxLayout()
        self.speedTestURLHboxLayout.addWidget(self.speedTestURLEdit)
        self.speedTestURLHboxLayout.addWidget(self.speedTestURLResetBtn)

        self.connectivityHboxLayout = QHBoxLayout()
        self.connectivityHboxLayout.addWidget(self.connectivityEdit)
        self.connectivityHboxLayout.addWidget(self.connectivityResetBtn)

        layout = QFormLayout()
        layout.addRow(self.speedTestURLText)
        layout.addRow(self.speedTestURLHboxLayout)
        layout.addRow(self.connectivityText)
        layout.addRow(self.connectivityHboxLayout)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

        self.finished.connect(functools.partial(self.handleResultCode))

    def setWidthAndHeight(self):
        self.resize(656, 180)

    def handleResultCode(self, code):
        for widget, info, settingsName, reset in [
            (
                self.speedTestURLEdit,
                'speed test URL',
                'CustomNetworkSpeedTestURL',
                NETWORK_SPEED_TEST_URL,
            ),
            (
                self.connectivityEdit,
                'connectivity test URL',
                'CustomNetworkConnectivityTestURL',
                NETWORK_CONNECTIVITY_TEST_URL,
            ),
        ]:
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                value = widget.text()

                logger.info(f'setting {info} to \'{value}\'')

                AppSettings.set(settingsName, value)
            else:
                try:
                    settings = AppSettings.get(settingsName)

                    if settings is not None:
                        widget.setText(str(settings))
                    else:
                        widget.setText(reset)
                except Exception as ex:
                    # Any non-exit exceptions

                    logger.error(f'error restoring {info}: {ex}')
