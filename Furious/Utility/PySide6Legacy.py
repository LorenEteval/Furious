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

from Furious.Utility.Constants import *
from Furious.Utility.Utility import *

import time

__all__ = ['PySide6LegacyEnumValueWrapper', 'PySide6LegacyEventLoopWait']


def PySide6LegacyEnumValueWrapper(enum):
    # Protect PySide6 enum wrapper behavior changes
    if versionToValue(PYSIDE6_VERSION) < versionToValue('6.2.2'):
        return enum
    else:
        return enum.value


def PySide6LegacyEventLoopWait(ms):
    # Protect qWait method does not exist in some
    # old PySide6 version
    if versionToValue(PYSIDE6_VERSION) < versionToValue('6.3.1'):
        for counter in range(0, ms, 10):
            time.sleep(10 / 1000)

            APP().processEvents()
    else:
        from PySide6.QtTest import QTest

        QTest.qWait(ms)

        APP().processEvents()
