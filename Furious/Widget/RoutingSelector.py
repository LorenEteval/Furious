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

"""Present the shared routing state as a compact Fluent-style selector."""

from __future__ import annotations

from Furious.Frozenlib import AppRoutingController, Mixins
from Furious.Qt import AppQComboBox
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import QSizePolicy

__all__ = ['RoutingSelector']


class RoutingSelector(AppQComboBox):
    """Select routes through the application-wide routing controller."""

    def __init__(self, parent=None):
        """Bind the selector to one shared routing controller."""
        self.controller = AppRoutingController()

        # This widget restores its enabled state from the shared controller in
        # retranslate(), so the generic translation disable/enable wrapper is
        # neither needed nor safe during connection transitions.
        super().__init__(parent, useQSetDisabled=False)

        self.setObjectName('HomeRoutingSelector')
        self.enableThemedSeparators()
        self.setMinimumWidth(180)
        self.setMaximumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(_('Routing'))
        self.setToolTip(_('Routing'))

        self.currentIndexChanged.connect(self._handleCurrentIndexChanged)
        self.controller.stateChanged.connect(self._applyState)
        self.controller.interactionEnabledChanged.connect(self._applyInteractionEnabled)

        self._applyState(*self.controller.state())

    @staticmethod
    def _optionText(option) -> str:
        """Return an option's translated or literal display name."""
        return _(option.displayName) if option.translatable else option.displayName

    @QtCore.Slot(object, str)
    def _applyState(self, options, routing: str):
        """Replace items atomically from one controller state snapshot."""
        with Mixins.QBlockSignalContext(self):
            self.clear()

            for option in options:
                if option.separatorBefore and self.count():
                    self.insertSeparator(self.count())

                self.addItem(self._optionText(option), option.id)

            index = self.findData(routing)

            self.setCurrentIndex(index if index >= 0 else 0)

        self.setVisible(bool(options))
        self._applyInteractionEnabled(self.controller.interactionEnabled)

    @QtCore.Slot(bool)
    def _applyInteractionEnabled(self, enabled: bool):
        """Enable selection only when options and connection state allow it."""
        self.setEnabled(bool(enabled) and self.count() > 0)

    @QtCore.Slot(int)
    def _handleCurrentIndexChanged(self, index: int):
        """Forward user selection without retaining independent state."""
        routing = self.itemData(index)

        if isinstance(routing, str):
            self.controller.selectRouting(routing)

    def showPopup(self):
        """Refresh plugin capabilities immediately before showing options."""
        self.controller.refresh(force=True)

        super().showPopup()

    def retranslate(self):
        """Refresh option text and routing accessibility metadata."""
        self._applyState(*self.controller.state())
        self.setAccessibleName(_('Routing'))
        self.setToolTip(_('Routing'))
