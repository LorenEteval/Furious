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

from Furious.PyFramework import *

__all__ = ['QBlockSignals', 'QTranslatable']


class QProtection:
    def __init__(self, qobject):
        self.qobject = qobject
        self.hasattr = hasattr(self.qobject, 'setDisabled')

    def __enter__(self):
        if self.hasattr:
            self.qobject.setDisabled(True)

    def __exit__(self, exceptionType, exceptionValue, tb):
        if self.hasattr:
            self.qobject.setDisabled(False)


class QBlockSignals:
    def __init__(self, qobject):
        self.qobject = qobject
        self.hasattr = hasattr(self.qobject, 'blockSignals')

    def __enter__(self):
        if self.hasattr:
            self.qobject.blockSignals(True)

    def __exit__(self, exceptionType, exceptionValue, tb):
        if self.hasattr:
            self.qobject.blockSignals(False)


class QTranslatable(Translatable):
    def __init__(self, *args, **kwargs):
        self.useQProtection = kwargs.pop('useQProtection', True)

        super().__init__(*args, **kwargs)

    def retranslate(self):
        raise NotImplementedError

    @staticmethod
    def retranslateAll():
        for ob in QTranslatable.ObjectsPool:
            assert isinstance(ob, QTranslatable)

            if ob.translatable:
                if ob.useQProtection:
                    with QProtection(ob):
                        ob.retranslate()
                else:
                    ob.retranslate()
