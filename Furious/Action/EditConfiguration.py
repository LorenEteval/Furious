# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Gui.Action import Action
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import bootstrapIcon
from Furious.Utility.Translator import gettext as _


class EditConfigurationAction(Action):
    def __init__(self):
        super().__init__(
            _('Edit Configuration...'),
            icon=bootstrapIcon('pencil-square.svg'),
        )

    def triggeredCallback(self, checked):
        APP().ServerWidget.show()
