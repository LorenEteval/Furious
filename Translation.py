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

from Furious.Library import *
from Furious.Utility import *
from Furious.Externals import *

import os
import re
import copy

# import deepl
import logging
import argparse
import functools

import Furious

logging.basicConfig(
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    level=logging.INFO,
)
logging.raiseExceptions = False

logger = logging.getLogger('Translation')


@functools.lru_cache(None)
def getAppSourceCodePath(path):
    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(path):
        # Check if __init__.py exists in the current directory
        if '__init__.py' in filenames:
            for filename in filenames:
                yield os.path.join(dirpath, filename)


@functools.lru_cache(None)
def getMagicNameFromPath(path):
    return os.path.relpath(path, ROOT_DIR).removesuffix('.py').replace(os.sep, '.')


@functools.lru_cache(None)
def getAppConstantsByName(name):
    return getattr(Furious.Utility.Constants, name)


APPLICATION_SOURCE_CODE_PATH = getAppSourceCodePath(PACKAGE_DIR)


def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument('-k', '--key', help='DeepL auth key', required=True)
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

    for key in translation.keys():
        # Reset source
        translation[key]['source'] = []

    for sourceCodePath in APPLICATION_SOURCE_CODE_PATH:
        with open(sourceCodePath, 'r', encoding='utf-8') as file:
            content = file.read()

        magicName = getMagicNameFromPath(sourceCodePath)

        pattern = r"(?<![a-zA-Z])_\(\s*f?\s*(?:'([^']*)'|\"([^\"]*)\")\s*\)"
        matches = re.findall(pattern, content)

        if matches:
            match = [m[0] or m[1] for m in matches]

            for source in match:
                foundBraces = True

                while foundBraces:
                    lBraceIndex = source.find('{')
                    rBraceIndex = source.find('}')

                    if lBraceIndex >= 0 and rBraceIndex >= 0:
                        parsed = source[lBraceIndex + 1 : rBraceIndex]

                        source = source.replace(
                            source[lBraceIndex : rBraceIndex + 1],
                            getAppConstantsByName(parsed),
                        )
                    else:
                        foundBraces = False

                if source not in translation:
                    translation[source] = {'source': [magicName]}
                else:
                    if magicName not in translation[source]['source']:
                        translation[source]['source'].append(magicName)

    nonexist = []

    for key in translation.keys():
        if len(translation[key]['source']) == 0:
            # No source, add to nonexist
            nonexist.append(key)

    for key in nonexist:
        # Key with no source, remove
        translation.pop(key, None)

    # translator = deepl.Translator(args.key, send_platform_info=False, proxy=proxy)

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
            # result = translator.translate_text(
            #     text,
            #     source_lang='EN',
            #     target_lang=target,
            #     context=(
            #         f'\'{APPLICATION_NAME}\' is application name. '
            #         'Please do not translate this word'
            #     ),
            # )
            #
            # logger.info(
            #     f'query translation: \'{text}\' --{target}--> \'{result.text}\''
            # )
            #
            # translation[text][target] = result.text

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

            logger.warning(f'have unreviewed translation \'{text}\'')

    if unreviewed > 0:
        logger.error(f'have {unreviewed} unreviewed translation(s)')
    else:
        logger.info(f'all {len(translation)} translation(s) have been reviewed')


if __name__ == '__main__':
    main()
