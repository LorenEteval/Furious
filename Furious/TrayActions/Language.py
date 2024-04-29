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

from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *

import logging
import functools

__all__ = ['LanguageAction']

logger = logging.getLogger(__name__)

# Handy stuff
SMART_CHOSEN_LANGUAGE = (
    SYSTEM_LANGUAGE if SYSTEM_LANGUAGE in SUPPORTED_LANGUAGE else 'EN'
)

registerAppSettings(
    'Language', validRange=SUPPORTED_LANGUAGE, default=SMART_CHOSEN_LANGUAGE
)

needTrans = functools.partial(needTransFn, source=__name__)


class LanguageChildAction(AppQAction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        abbr = LANGUAGE_TO_ABBR[self.text()]

        if AppSettings.get('Language') != abbr:
            logger.info(f'set language to \'{self.text()}\'')

            AppSettings.set('Language', abbr)

            QTranslatable.retranslateAll()

    def retranslate(self):
        # Nothing to do
        pass


needTrans('Language')


class LanguageAction(AppQAction):
    def __init__(self, **kwargs):
        super().__init__(
            _('Language'),
            icon=bootstrapIcon('globe2.svg'),
            menu=AppQMenu(
                *list(
                    LanguageChildAction(
                        # Language representation
                        text,
                        checkable=True,
                        checked=text == ABBR_TO_LANGUAGE[AppSettings.get('Language')],
                    )
                    for text in list(LANGUAGE_TO_ABBR.keys())
                ),
            ),
            **kwargs,
        )
