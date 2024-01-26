from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

__all__ = ['LanguageAction']

BUILTIN_LANGUAGE = ['EN', 'ZH']

registerAppSettings('Language')


class LanguageChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        pass


class LanguageAction(AppQAction):
    def __init__(self):
        super().__init__(
            _('Language'),
            icon=bootstrapIcon('globe2.svg'),
            # menu=AppQMenu(
            #     *list(
            #         LanguageChildAction(
            #             # Language representation
            #             text,
            #             checkable=True,
            #             checked=text == ABBR_TO_LANGUAGE[APP().Language],
            #         )
            #         for text in list(LANGUAGE_TO_ABBR.keys())
            #     ),
            # ),
        )
