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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

import functools

__all__ = ['ExitAction']


class ExitAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Exit'),
            icon=bootstrapIcon('box-arrow-in-left.svg'),
            **kwargs,
        )

    def triggeredCallback(self, checked):
        APP().exit()
