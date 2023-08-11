from Furious.Gui.Action import Action
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import bootstrapIcon
from Furious.Utility.Translator import gettext as _


class ExitAction(Action):
    def __init__(self):
        super().__init__(
            _('Exit'),
            icon=bootstrapIcon('box-arrow-in-left.svg'),
        )

    def triggeredCallback(self, checked):
        APP().exit()
