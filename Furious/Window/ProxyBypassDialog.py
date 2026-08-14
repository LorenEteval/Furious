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

"""Provide widgets for GUI customize proxy bypass."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import *

import logging

__all__ = ['ProxyBypassDialog']

logger = logging.getLogger(__name__)


class ProxyBypassDialog(AppQDialog):
    """Present the GUI customize proxy bypass dialog."""

    def __init__(self, *args, **kwargs):
        """Initialize the proxy bypass settings dialog."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Customize System Proxy Bypass Address'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.proxyBypassText = AppQLabel(
            _('Enter system proxy bypass address (separated by semicolons):')
        )
        self.proxyBypassEdit = QLineEdit()

        settings = AppSettings.get('CustomProxyBypass')

        if isinstance(settings, str):
            self.proxyBypassEdit.setText(settings)
        else:
            self.proxyBypassEdit.setText(PROXY_SERVER_BYPASS)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        self.resetBtn = AppQPushButton(_('Reset'))
        self.resetBtn.clicked.connect(self.handleResetButtonClicked)

        self.hboxLayout = QHBoxLayout()
        self.hboxLayout.addWidget(self.resetBtn)
        self.hboxLayout.addWidget(self.dialogBtns)

        layout = QFormLayout()
        layout.addRow(self.proxyBypassText)
        layout.addRow(self.proxyBypassEdit)
        layout.addRow(self.hboxLayout)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

        self.finished.connect(self.handleResultCode)

    def setWidthAndHeight(self):
        """Apply the default size for the GUI customize proxy bypass dialog."""
        self.resize(656, 125)

    def handleResultCode(self, code):
        """Handle result code."""
        if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
            oldValue = AppSettings.get('CustomProxyBypass')
            newValue = self.proxyBypassEdit.text()

            def writeNewSettings(value):
                """Handle write new settings for the GUI customize proxy bypass dialog."""
                logger.info(f'setting custom proxy bypass address to \'{value}\'')

                AppSettings.set('CustomProxyBypass', value)

                showMBoxNewChangesNextTime()

            if not isinstance(oldValue, str):
                if newValue == PROXY_SERVER_BYPASS:
                    return
                else:
                    writeNewSettings(newValue)
            else:
                if oldValue != newValue:
                    writeNewSettings(newValue)
        else:
            try:
                settings = AppSettings.get('CustomProxyBypass')

                if settings is not None:
                    self.proxyBypassEdit.setText(str(settings))
                else:
                    self.proxyBypassEdit.setText(PROXY_SERVER_BYPASS)
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(f'error restoring proxy bypass address: {ex}')

    @QtCore.Slot()
    def handleResetButtonClicked(self):
        """Handle reset button clicked."""
        self.proxyBypassEdit.setText(PROXY_SERVER_BYPASS)
