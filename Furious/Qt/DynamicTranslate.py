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

"""Provide Qt support for dynamic translate."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Externals import *

__all__ = [
    'gettext',
    'LANGUAGE_TO_ABBR',
    'ABBR_TO_LANGUAGE',
    'SUPPORTED_LANGUAGE',
]


class Translator:
    """Represent translator."""
    def __init__(self):
        """Initialize the Translator."""
        super().__init__()

        self.translation = dict()
        self.dictEnglish = dict()

    def install(self, translation):
        """Handle install for the translator."""
        self.translation = translation

        for key, value in translation.items():
            # English -> English
            value['EN'] = key

            for lang, text in value.items():
                if lang.isupper():
                    # is 'ZH', 'EN', etc.
                    self.dictEnglish[text] = key

        # English -> English
        self.dictEnglish.update(dict(list((key, key) for key in translation.keys())))

    def translate(self, source, locale):
        """Return the translate value used by the translator."""
        try:
            return self.translation[self.dictEnglish[source]][locale]
        except Exception:
            # Any non-exit exceptions

            # No changes
            return source


translator = Translator()


def installTranslation(translation):
    """Handle install translation for the application."""
    translator.install(translation)


def gettext(source, locale=None):
    """Return text."""
    if locale is None:
        if APP() is None:
            # Normally should not reach here if performing a translation
            return source
        else:
            return translator.translate(source, AppSettings.get('Language'))
    else:
        assert locale in SUPPORTED_LANGUAGE

        return translator.translate(source, locale)


# Register new translation type here
LANGUAGE_TO_ABBR = {
    'English': 'EN',
    'Русский': 'RU',
    '简体中文': 'ZH',
}

ABBR_TO_LANGUAGE = {value: key for key, value in LANGUAGE_TO_ABBR.items()}

SUPPORTED_LANGUAGE = list(LANGUAGE_TO_ABBR.values())

installTranslation(TRANSLATION)
