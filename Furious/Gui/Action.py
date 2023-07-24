from Furious.Utility.Constants import PLATFORM
from Furious.Utility.Utility import (
    SupportThemeChangedCallback,
    bootstrapIcon,
    bootstrapIconWhite,
    getUbuntuRelease,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication

import logging
import darkdetect

logger = logging.getLogger(__name__)


class Action(Translatable, SupportThemeChangedCallback, QAction):
    def __init__(
        self,
        text,
        icon=None,
        menu=None,
        useActionGroup=True,
        checkable=False,
        checked=False,
        callback=None,
        **kwargs,
    ):
        super().__init__(text=text, **kwargs)

        self.iconFileName = ''

        if icon is not None:
            self.setIcon(icon)

        if menu is not None:
            # Create reference
            self._menu = menu

            self.setMenu(menu)

            if useActionGroup:
                # Create reference
                self._actionGroup = ActionGroup(self, *menu.actions())

                self.setActionGroup(self._actionGroup)

        self.setCheckable(checkable)
        self.setChecked(checked)

        # Handy callback to be able to link with lambda
        self.callback = callback

        @QtCore.Slot(bool)
        def triggerSignal(paramChecked):
            logger.info(f'action is \'{self.textEnglish}\'. Checked is {paramChecked}')

            if callable(self.callback):
                self.callback()

            self.triggeredCallback(paramChecked)

        self.triggered.connect(triggerSignal)

    @property
    def textEnglish(self):
        return _(self.text(), 'EN')

    def __str__(self):
        return self.__class__.__name__

    def textCompare(self, compare):
        return self.textEnglish == compare

    @staticmethod
    def getIconFileName(fileName):
        try:
            return fileName.split('/')[-1]
        except Exception:
            # Any non-exit exceptions

            return ''

    def setIcon(self, icon):
        self.iconFileName = self.getIconFileName(icon.iconFileName)

        if self.iconFileName:
            if darkdetect.theme() == 'Dark':
                if PLATFORM == 'Windows':
                    # Windows. Always use black icon
                    super().setIcon(bootstrapIcon(self.iconFileName))
                else:
                    if getUbuntuRelease() == '20.04':
                        # Ubuntu 20.04 system dark theme does not change menu color.
                        # Make it go black always
                        super().setIcon(bootstrapIcon(self.iconFileName))
                    else:
                        super().setIcon(bootstrapIconWhite(self.iconFileName))
            else:
                super().setIcon(bootstrapIcon(self.iconFileName))
        else:
            # Fall back
            super().setIcon(icon)

    def triggeredCallback(self, checked):
        # Not a mandatory re-implementation in child class
        pass

    def themeChangedCallback(self, theme):
        if self.iconFileName:
            if theme == 'Dark':
                if PLATFORM == 'Windows':
                    # Windows. Always use black icon
                    super().setIcon(bootstrapIcon(self.iconFileName))
                else:
                    if getUbuntuRelease() == '20.04':
                        # Ubuntu 20.04 system dark theme does not change menu color.
                        # Make it go black always
                        super().setIcon(bootstrapIcon(self.iconFileName))
                    else:
                        super().setIcon(bootstrapIconWhite(self.iconFileName))
            else:
                super().setIcon(bootstrapIcon(self.iconFileName))

    def retranslate(self):
        def recursiveTranslate(action, memo):
            if action not in memo and not action.isSeparator():
                action.setText(_(action.text()))

            memo[action] = True

            if action.menu() is not None:
                for childAction in action.menu().actions():
                    recursiveTranslate(childAction, memo)

        # Do not use StateContext because it's been managed somewhere else!!!
        recursiveTranslate(self, dict())


class ActionGroup(QActionGroup):
    def __init__(self, parent, *actions):
        super().__init__(parent)

        for action in actions:
            self.addAction(action)


class Seperator(QAction):
    def __init__(self):
        super().__init__()
