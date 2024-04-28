# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

from PySide6.QtWidgets import *

import functools

__all__ = ['IndentSpinBox']

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Set Indent',
    'Indent:',
    'Cancel',
)


class IndentSpinBox(AppQDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Set Indent'))

        self.indentText = AppQLabel(_('Indent:'))

        self.indentSpin = QSpinBox()
        self.indentSpin.setRange(0, 8)
        self.indentSpin.setValue(2)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()
        layout.addRow(self.indentText, self.indentSpin)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def value(self):
        return self.indentSpin.value()
