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
registerAppSettings('CustomNetworkStateTestURL')


class GuiCustomizeNetworkTestDialog(AppQDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Customize Network Test URL'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.speedTestURLText = AppQLabel(_('Enter network speed test URL:'))
        self.speedTestURLEdit = QLineEdit()

        speedTestSettings = AppSettings.get('CustomNetworkSpeedTestURL')

        if speedTestSettings is None:
            self.speedTestURLEdit.setText(NETWORK_SPEED_TEST_URL)
        else:
            self.speedTestURLEdit.setText(speedTestSettings)

        self.stateTestURLText = AppQLabel(_('Enter network state test URL:'))
        self.stateTestURLEdit = QLineEdit()

        stateTestSettings = AppSettings.get('CustomNetworkStateTestURL')

        if stateTestSettings is None:
            self.stateTestURLEdit.setText(NETWORK_STATE_TEST_URL)
        else:
            self.stateTestURLEdit.setText(stateTestSettings)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        self.speedTestResetBtn = AppQPushButton(_('Reset'))
        self.speedTestResetBtn.clicked.connect(
            lambda: self.speedTestURLEdit.setText(NETWORK_SPEED_TEST_URL)
        )
        self.stateTestResetBtn = AppQPushButton(_('Reset'))
        self.stateTestResetBtn.clicked.connect(
            lambda: self.stateTestURLEdit.setText(NETWORK_STATE_TEST_URL)
        )

        self.speedTestHboxLayout = QHBoxLayout()
        self.speedTestHboxLayout.addWidget(self.speedTestURLEdit)
        self.speedTestHboxLayout.addWidget(self.speedTestResetBtn)

        self.stateTestHboxLayout = QHBoxLayout()
        self.stateTestHboxLayout.addWidget(self.stateTestURLEdit)
        self.stateTestHboxLayout.addWidget(self.stateTestResetBtn)

        layout = QFormLayout()
        layout.addRow(self.speedTestURLText)
        layout.addRow(self.speedTestHboxLayout)
        layout.addRow(self.stateTestURLText)
        layout.addRow(self.stateTestHboxLayout)
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
                self.stateTestURLEdit,
                'state test URL',
                'CustomNetworkStateTestURL',
                NETWORK_STATE_TEST_URL,
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
