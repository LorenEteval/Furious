from Furious.Utility import *

__all__ = ['gettext']


class Translator:
    def __init__(self):
        super().__init__()

        self.translation = dict()
        self.dictEnglish = dict()

    def install(self, translation):
        self.translation = translation

        for key, value in translation.items():
            # English -> English
            value['EN'] = key

            for lang, text in value.items():
                self.dictEnglish[text] = key

        # English -> English
        self.dictEnglish.update(dict(list((key, key) for key in translation.keys())))

    def translate(self, source, locale):
        # TODO
        return source

        # if source in NO_TRANSLATION_DICT:
        #     return source
        # else:
        #     return self.translation[self.dictEnglish[source]][locale]


translator = Translator()


def installTranslation(translation):
    translator.install(translation)


def gettext(source, locale=None):
    if locale is None:
        assert APP() is not None

        return translator.translate(source, AppSettings.get('Language'))
    else:
        assert locale in list(LANGUAGE_TO_ABBR.values())

        return translator.translate(source, locale)


LANGUAGE_TO_ABBR = {
    # TODO
    'English': 'EN',
    '简体中文': 'ZH',
}

ABBR_TO_LANGUAGE = {value: key for key, value in LANGUAGE_TO_ABBR.items()}

# DO-NOT-TRANSLATE text
NO_TRANSLATION = []

NO_TRANSLATION_DICT = {key: True for key in NO_TRANSLATION}

TRANSLATION = {}

installTranslation(TRANSLATION)
