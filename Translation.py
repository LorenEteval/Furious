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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Externals import *
from Furious.Models import *

import os
import re
import ast
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

APP_CONSTANT_PATTERN = re.compile(r'\{([^{}]+)\}')


@functools.lru_cache(None)
def getAppSourceCodePath(path):
    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(path):
        # Check if __init__.py exists in the current directory
        if '__init__.py' in filenames:
            for filename in filenames:
                if filename.endswith('.py'):
                    yield os.path.join(dirpath, filename)


@functools.lru_cache(None)
def getMagicNameFromPath(path):
    return os.path.relpath(path, ROOT_DIR).removesuffix('.py').replace(os.sep, '.')


@functools.lru_cache(None)
def getAppConstantsByName(name):
    return getattr(Furious.Frozenlib.Constants, name)


APPLICATION_SOURCE_CODE_PATH = getAppSourceCodePath(PACKAGE_DIR)


def getTranslationKeys(content):
    """Return literal strings passed directly to the translation function."""
    syntaxTree = ast.parse(content)

    for node in ast.walk(syntaxTree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name) or node.func.id not in ('_', 'gettext'):
            continue

        if not node.args:
            continue

        source = node.args[0]

        if isinstance(source, ast.Constant) and isinstance(source.value, str):
            yield source.value


def resolveAppConstants(source):
    """Replace application-constant references in a translation key."""
    return APP_CONSTANT_PATTERN.sub(
        lambda match: getAppConstantsByName(match.group(1)), source
    )


def addTranslationSource(translation, source, magicName):
    """Register a source module while preserving deterministic list order."""
    sources = translation.setdefault(source, {'source': []})['source']

    if magicName not in sources:
        sources.append(magicName)


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

        for source in getTranslationKeys(content):
            source = resolveAppConstants(source)

            addTranslationSource(translation, source, magicName)

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

            # TODO: Temporarily set the same as original text
            translation[text][target] = text

            if not targetText or translation[text].get('isReviewed') is None:
                # Target translation does not exist, or does not have 'isReviewed' field.
                # Set 'isReviewed' field to "False"
                translation[text]['isReviewed'] = 'False'

    translationReverseMap = dict()

    for text in translation.keys():
        targetText = translation[text].get(target, '')

        if not targetText:
            continue

        translationReverseMap.setdefault(targetText, list()).append(text)

    duplicateTranslations = dict(
        (targetText, texts)
        for targetText, texts in translationReverseMap.items()
        if len(set(texts)) > 1
    )

    for targetText, texts in duplicateTranslations.items():
        logger.error(
            f'translation collision in target language \'{target}\': '
            f'{texts} --{target}--> \'{targetText}\''
        )

    if duplicateTranslations:
        logger.error(
            f'have {len(duplicateTranslations)} duplicate target translation(s) '
            f'in language \'{target}\''
        )

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
