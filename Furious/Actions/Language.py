# Copyright (C) 2024–present  Loren Eteval & contributors <loren.eteval@proton.me>
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

"""Implement tray actions for language."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

import logging

__all__ = ['LanguageAction']

logger = logging.getLogger(__name__)

# Handy stuff
SMART_CHOSEN_LANGUAGE = (
    SYSTEM_LANGUAGE if SYSTEM_LANGUAGE in SUPPORTED_LANGUAGE else 'EN'
)

registerAppSettings(
    'Language', validRange=SUPPORTED_LANGUAGE, default=SMART_CHOSEN_LANGUAGE
)


class LanguageChildAction(AppQAction):
    """Handle the language child action."""

    def __init__(self, *args, **kwargs):
        """Initialize the LanguageChildAction."""
        super().__init__(*args, **kwargs)

    def triggeredCallback(self, checked):
        """Handle activation of the action."""
        abbr = LANGUAGE_TO_ABBR[self.text()]

        if AppSettings.get('Language') != abbr:
            logger.info(f'set language to \'{self.text()}\'')

            AppSettings.set('Language', abbr)

            Mixins.QTranslatable.retranslateAll()

    def retranslate(self):
        # Nothing to do
        """Refresh translated text for the language child action."""
        pass


class LanguageAction(AppQAction):
    """Handle the language action."""

    def __init__(self, **kwargs):
        """Initialize the LanguageAction."""
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
