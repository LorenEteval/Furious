from Furious.Gui.Action import Action
from Furious.Utility.Utility import bootstrapIcon
from Furious.Utility.Translator import gettext as _

from PySide6.QtWidgets import QApplication


class EditConfigurationAction(Action):
    def __init__(self):
        super().__init__(
            _('Edit Configuration...'),
            icon=bootstrapIcon('pencil-square.svg'),
        )

    def triggeredCallback(self, checked):
        QApplication.instance().MainWidget.show()
