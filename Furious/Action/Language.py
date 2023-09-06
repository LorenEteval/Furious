# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Gui.Action import Action
from Furious.Widget.Widget import Menu
from Furious.Utility.Constants import APP
from Furious.Utility.Utility import bootstrapIcon
from Furious.Utility.Translator import (
    Translatable,
    gettext as _,
    ABBR_TO_LANGUAGE,
    LANGUAGE_TO_ABBR,
)

import logging

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGE = tuple(LANGUAGE_TO_ABBR.values())


class LanguageChildAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        checkedLanguage = LANGUAGE_TO_ABBR[self.text()]

        if APP().Language != checkedLanguage:
            logger.info(f'set language to \'{self.text()}\'')

            APP().Language = checkedLanguage

            Translatable.retranslateAll()


class LanguageAction(Action):
    def __init__(self):
        super().__init__(
            _('Language'),
            icon=bootstrapIcon('globe2.svg'),
            menu=Menu(
                *list(
                    LanguageChildAction(
                        # Language representation
                        text,
                        checkable=True,
                        checked=text == ABBR_TO_LANGUAGE[APP().Language],
                    )
                    for text in list(LANGUAGE_TO_ABBR.keys())
                ),
            ),
        )
