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

from Furious.QtFramework.Ancestors import QTranslatable
from Furious.QtFramework.DynamicTranslate import gettext as _
from Furious.PyFramework.Ancestors import *
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtGui import *

import logging
import functools
import darkdetect

logger = logging.getLogger(__name__)

__all__ = [
    'bootstrapIcon',
    'bootstrapIconWhite',
    'AppQIcon',
    'AppQAction',
    'AppQActionGroup',
    'AppQSeperator',
]


class AppQIcon(QIcon):
    def __init__(self, iconFileName: str):
        super().__init__(iconFileName)

        self.iconFileName = iconFileName


def iconFn(prefix, name):
    if name.startswith('rocket-takeoff'):
        # Colorful. Use default
        return AppQIcon(f':/Icons/bootstrap/{name}')
    else:
        return AppQIcon(f':/Icons/{prefix}/{name}')


bootstrapIcon = functools.partial(iconFn, 'bootstrap')
bootstrapIconWhite = functools.partial(iconFn, 'bootstrap/white')


class AppQAction(QTranslatable, SupportThemeChangedCallback, QAction):
    def __init__(
        self,
        text,
        icon=None,
        menu=None,
        useActionGroup=True,
        checkable=False,
        checked=False,
        statusTip=None,
        callback=None,
        shortcut=None,
        isTrayAction=False,
        **kwargs,
    ):
        super().__init__(text=text, **kwargs)

        # Do not use QProtection because it's been managed somewhere else!!!
        self.useQProtection = False
        self.iconFileName = ''
        self.isTrayAction = isTrayAction

        self.setShortcutVisibleInContextMenu(True)

        if icon is not None:
            self.setIcon(icon)

        if menu is not None:
            # Create reference
            self._menu = menu

            # Some old version PySide6 does not have setMenu method
            # for QAction. Protect it. Currently only used in SystemTrayIcon
            if hasattr(self, 'setMenu'):
                self.setMenu(menu)

            if useActionGroup:
                # Create reference
                self._actionGroup = AppQActionGroup(self, *menu.actions())

                self.setActionGroup(self._actionGroup)
            else:
                self._actionGroup = None
        else:
            self._menu = None
            self._actionGroup = None

        self.setCheckable(checkable)
        self.setChecked(checked)

        if statusTip is not None:
            self.setStatusTip(statusTip)

        # Handy callback to be able to link with lambda
        self.callback = callback

        if shortcut is not None:
            self.setShortcut(shortcut)

        @QtCore.Slot(bool)
        def triggerSignal(paramChecked):
            logger.info(f'action is \'{self.textEnglish}\'. Checked is {paramChecked}')

            if callable(self.callback):
                self.callback()

            self.triggeredCallback(paramChecked)

        self.triggered.connect(triggerSignal)

    def addAction(self, action):
        if self._menu is not None:
            self._menu.addAction(action)

            if self._actionGroup is not None:
                self._actionGroup.addAction(action)

    def removeAction(self, action):
        if self._menu is not None:
            self._menu.removeAction(action)

            if self._actionGroup is not None:
                self._actionGroup.removeAction(action)

    @property
    def textEnglish(self):
        return _(self.text(), 'EN')

    def __str__(self):
        return self.__class__.__name__

    def textCompare(self, compare):
        return self.textEnglish == compare

    @staticmethod
    @functools.lru_cache(None)
    def getIconFileName(fileName):
        try:
            return fileName.split('/')[-1]
        except Exception:
            # Any non-exit exceptions

            return ''

    def setIconByTheme(self, theme):
        if not self.iconFileName:
            return

        if AppSettings.isStateON_('DarkMode'):
            # Custom dark mode
            super().setIcon(bootstrapIconWhite(self.iconFileName))

            return

        if theme == 'Dark':
            if PLATFORM == 'Windows':
                # Windows. Always use black icon
                super().setIcon(bootstrapIcon(self.iconFileName))
            else:
                if getUbuntuRelease() == '20.04' and self.isTrayAction:
                    # Ubuntu 20.04 system dark theme does not change tray menu color.
                    # Make it go black always
                    super().setIcon(bootstrapIcon(self.iconFileName))
                else:
                    super().setIcon(bootstrapIconWhite(self.iconFileName))
        else:
            super().setIcon(bootstrapIcon(self.iconFileName))

    def setIcon(self, icon: AppQIcon):
        self.iconFileName = self.getIconFileName(icon.iconFileName)

        if not self.iconFileName:
            # Fall back
            super().setIcon(icon)
        else:
            self.setIconByTheme(darkdetect.theme())

    def themeChangedCallback(self, theme):
        self.setIconByTheme(theme)

    def retranslate(self):
        def recursiveTranslate(action, memo):
            if action not in memo and not action.isSeparator() and action.translatable:
                action.setText(_(action.text()))
                action.setStatusTip(_(action.statusTip()))

            memo[action] = True

            # Some old version PySide6 does not have menu() method
            # for QAction. Protect it
            if hasattr(action, 'menu'):
                if action.menu() is not None:
                    for childAction in action.menu().actions():
                        recursiveTranslate(childAction, memo)

        recursiveTranslate(self, dict())

    def triggeredCallback(self, checked):
        # Not a mandatory re-implementation in child class
        pass


class AppQActionGroup(QActionGroup):
    def __init__(self, parent, *actions):
        super().__init__(parent)

        for action in actions:
            self.addAction(action)


class AppQSeperator(QAction):
    def __init__(self):
        super().__init__()
