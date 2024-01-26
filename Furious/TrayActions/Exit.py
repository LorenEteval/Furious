from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

__all__ = ['ExitAction']


class ExitAction(AppQAction):
    def __init__(self):
        super().__init__(
            _('Exit'),
            icon=bootstrapIcon('box-arrow-in-left.svg'),
        )

    def triggeredCallback(self, checked):
        APP().exit()
