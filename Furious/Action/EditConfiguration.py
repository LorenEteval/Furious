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
        APP().MainWidget.show()
