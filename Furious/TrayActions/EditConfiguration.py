from Furious.QtFramework import *
from Furious.QtFramework import gettext as _

__all__ = ['EditConfigurationAction']


class EditConfigurationAction(AppQAction):
    def __init__(self):
        super().__init__(
            _('Edit Configuration...'),
            icon=bootstrapIcon('pencil-square.svg'),
        )

    def triggeredCallback(self, checked):
        pass
