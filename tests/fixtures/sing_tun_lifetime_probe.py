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

"""Harmless source/Nuitka probe for the new transient settings editor."""

from __future__ import annotations

from Furious.Qt import AppQDialog
from Furious.Repository import Storage
from Furious.Window.SingTUNSettingsDialog import SingTUNSettingsDialog

from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from tests.support import application, isolatedSettings, processQtEvents

import argparse
import copy
import gc
import json
import sys
import weakref
import importlib


def run(iterations, method):
    application()
    destroyed = []
    references = []
    errors = []

    originalHook = sys.excepthook
    sys.excepthook = lambda kind, error, traceback: errors.append(
        (kind.__name__, str(error))
    )
    singGetter, replace = (
        Storage.UserSingTUNSettings,
        Storage.replaceSingTUNSettings,
    )
    sing = {}

    Storage.UserSingTUNSettings = staticmethod(lambda: copy.deepcopy(sing))
    Storage.replaceSingTUNSettings = staticmethod(lambda document: None)
    baseline = len(AppQDialog._openDialogs)

    try:
        with isolatedSettings():
            for index in range(iterations):
                owner = QWidget()
                dialog = SingTUNSettingsDialog(owner)
                dialog.destroyed.connect(lambda *_args: destroyed.append(True))
                references.append(weakref.ref(dialog))

                dialog.open()
                if method == 'owner':
                    owner.deleteLater()
                else:
                    getattr(dialog, method)()
                processQtEvents()

                assert not isValid(dialog), index

                if isValid(owner):
                    owner.deleteLater()
                processQtEvents()
                del dialog, owner

            gc.collect()
            processQtEvents()

            assert len(destroyed) == iterations
            assert all(reference() is None for reference in references)
            assert len(AppQDialog._openDialogs) == baseline
            assert not errors, errors
    finally:
        sys.excepthook = originalHook
        Storage.UserSingTUNSettings = staticmethod(singGetter)
        Storage.replaceSingTUNSettings = staticmethod(replace)

    return {
        'method': method,
        'destroyed': len(destroyed),
        'wrapperReleased': iterations,
        'callbackErrors': len(errors),
        'compiledDialog': hasattr(
            importlib.import_module('Furious.Window.SingTUNSettingsDialog'),
            '__compiled__',
        ),
        'compiledSignals': hasattr(
            importlib.import_module('Furious.Qt.Signals'), '__compiled__'
        ),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=20)
    parser.add_argument(
        '--method', choices=('accept', 'reject', 'close', 'owner'), default='reject'
    )
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.iterations, arguments.method)))
