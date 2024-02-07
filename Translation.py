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

from __future__ import annotations

from Furious.Core import *
from Furious.Interface import *
from Furious.Library import *
from Furious.Utility import *
from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.Storage import *
from Furious.TrayActions import *
from Furious.Widget import *
from Furious.Window import *
from Furious.__main__ import *
from Furious.Externals import *

import copy
import deepl
import logging
import argparse

logging.basicConfig(
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    level=logging.INFO,
)
logging.raiseExceptions = False

logger = logging.getLogger('Translation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', help='DeepL auth key', required=True)
    parser.add_argument(
        '-t', '--target', help='Target translation language', required=True
    )
    parser.add_argument(
        '-i', '--ignore', action='store_true', help='If provided, ignore review value'
    )
    parser.add_argument('-p', '--proxy', help='Proxy server used in API')

    args = parser.parse_args()

    target, proxy = args.target, args.proxy

    logger.info(f'target translation language: {target}')
    logger.info(f'use proxy: {proxy}')

    translation = copy.deepcopy(TRANSLATION)

    for text, source in TranslationPool:
        if text not in translation:
            translation[text] = {'source': [source]}
        else:
            unit = translation[text]

            if source not in unit['source']:
                unit['source'].append(source)

    translator = deepl.Translator(args.key, send_platform_info=False, proxy=args.proxy)

    for text in translation.keys():
        # Remove redundant EN translation
        translation[text].pop('EN', '')

        targetText = translation[text].get(target, '')
        isReviewed = translation[text].get('isReviewed', 'False')

        if targetText and isReviewed == 'True' and not args.ignore:
            # Translation already reviewed. Skip
            logger.info(
                f'skip reviewed translation: \'{text}\' --{target}--> \'{targetText}\''
            )
        else:
            result = translator.translate_text(
                text,
                source_lang='EN',
                target_lang=target,
                context=(
                    f'\'{APPLICATION_NAME}\' is application name. '
                    'Please do not translate this word'
                ),
            )

            logger.info(
                f'query translation: \'{text}\' --{target}--> \'{result.text}\''
            )

            translation[text][target] = result.text

            if not targetText or translation[text].get('isReviewed') is None:
                # Target translation does not exist, or does not have 'isReviewed' field.
                # Set 'isReviewed' field to "False"
                translation[text]['isReviewed'] = 'False'

    try:
        # Write back to file
        with open(GEN_TRANSLATION_FILE, 'w', encoding='utf-8') as file:
            file.write(f'TRANSLATION = {UJSONEncoder.encode(translation, indent=4)}\n')
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'flush result to \'{GEN_TRANSLATION_FILE}\' failed. {ex}')
    else:
        logger.info(f'flush result to \'{GEN_TRANSLATION_FILE}\' success')

    unreviewed = 0

    for text in translation.keys():
        isReviewed = translation[text].get('isReviewed', 'False')

        if isReviewed == 'False':
            unreviewed += 1

            logger.warning(f'have unreviewed translations \'{text}\'')

    if unreviewed > 0:
        logger.error(f'have {unreviewed} unreviewed translations')
    else:
        logger.info(f'all translations have been reviewed')


if __name__ == '__main__':
    main()
