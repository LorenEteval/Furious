from Furious.Gui.Action import Action
from Furious.Utility.Utility import bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6.QtWidgets import QApplication


class ExitAction(Action):
    def __init__(self):
        super().__init__(
            _('Exit'),
            icon=bootstrapIcon('box-arrow-in-left.svg'),
        )

    def triggeredCallback(self, checked):
        QApplication.instance().exit()
