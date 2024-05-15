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

from Furious.Version import __version__
from Furious.Utility import *

import os
import sys
import time
import shutil
import logging
import argparse
import subprocess

try:
    from nuitka.Version import getNuitkaVersion
except ImportError:
    raise
else:
    NUITKA_VERSION = getNuitkaVersion()

logging.basicConfig(
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    level=logging.INFO,
)
logging.raiseExceptions = False

logger = logging.getLogger('Deploy')

DEPLOY_DIR_NAME = f'{APPLICATION_NAME}-Deploy'

if PLATFORM == 'Windows':
    NUITKA_BUILD = (
        f'python -m nuitka '
        f'--standalone --plugin-enable=pyside6 '
        f'--disable-console '
        f'--assume-yes-for-downloads '
        f'--include-package-data=Furious '
        f'--windows-icon-from-ico=\"Icons/png/rocket-takeoff-window.png\" '
        f'--force-stdout-spec=^%TEMP^%/_Furious_Enable_Stdout '
        f'--force-stderr-spec=^%TEMP^%/_Furious_Enable_Stderr '
        f'Furious '
        f'--output-dir=\"{ROOT_DIR / DEPLOY_DIR_NAME}\"'
    )
elif PLATFORM == 'Darwin':
    NUITKA_BUILD = (
        f'python -m nuitka '
        f'--standalone --plugin-enable=pyside6 '
        f'--disable-console '
        f'--assume-yes-for-downloads '
        f'--include-package-data=Furious '
        f'--macos-create-app-bundle '
        f'--macos-app-icon=\"Icons/png/rocket-takeoff-window.png\" '
        f'--macos-app-name=\"Furious\" '
        f'Furious-GUI.py '
        f'--output-dir=\"{ROOT_DIR / DEPLOY_DIR_NAME}\"'
    )
else:
    NUITKA_BUILD = ''

if PLATFORM == 'Windows':
    ARTIFACT_NAME = (
        f'{APPLICATION_NAME}-{__version__}-'
        f'{PLATFORM.lower()}{PLATFORM_RELEASE}-{PLATFORM_MACHINE.lower()}'
    )
elif PLATFORM == 'Darwin':
    if versionToValue(PYSIDE6_VERSION) <= versionToValue('6.4.3'):
        ARTIFACT_NAME = (
            f'{APPLICATION_NAME}-{__version__}-'
            f'macOS-10.9-{PLATFORM_MACHINE.lower()}'
        )
    else:
        if versionToValue(NUITKA_VERSION) <= versionToValue('1.8.6'):
            ARTIFACT_NAME = (
                f'{APPLICATION_NAME}-{__version__}-'
                f'macOS-11.0-{PLATFORM_MACHINE.lower()}'
            )
        else:
            ARTIFACT_NAME = (
                f'{APPLICATION_NAME}-{__version__}-'
                f'macOS-12.0-{PLATFORM_MACHINE.lower()}'
            )
else:
    ARTIFACT_NAME = ''


def printArtifactName():
    if PLATFORM == 'Windows':
        print(f'{ARTIFACT_NAME}.zip', flush=True)


def cleanup():
    try:
        shutil.rmtree(ROOT_DIR / DEPLOY_DIR_NAME)
    except Exception as ex:
        # Any non-exit exceptions

        logger.error(f'remove deployment dir failed: {ex}')
    else:
        logger.info(f'remove deployment dir success')

    if PLATFORM == 'Windows':
        # More cleanup on Windows
        try:
            os.remove(ROOT_DIR / f'{ARTIFACT_NAME}.zip')
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove artifact failed: {ex}')
        else:
            logger.info(f'remove artifact success')

        try:
            shutil.rmtree(
                ROOT_DIR / f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
                f'{PLATFORM.lower()}{PLATFORM_RELEASE}'
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove potential unzipped dir failed: {ex}')
        else:
            logger.info(f'remove potential unzipped dir success')
    elif PLATFORM == 'Darwin':
        # More cleanup on Darwin
        try:
            os.remove(ROOT_DIR / f'{ARTIFACT_NAME}.dmg')
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove artifact failed: {ex}')
        else:
            logger.info(f'remove artifact success')

        try:
            shutil.rmtree(ROOT_DIR / 'dmg')
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove dmg dir failed: {ex}')
        else:
            logger.info(f'remove dmg dir success')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-n', '--name', action='store_true', help='Target artifact name'
    )
    parser.add_argument(
        '-c', '--cleanup', action='store_true', help='Cleanup deployment files'
    )

    args = parser.parse_args()

    if args.name:
        printArtifactName()

        sys.exit(0)

    if args.cleanup:
        cleanup()

        logger.info('cleanup done')

        sys.exit(0)

    try:
        logger.info('building')

        result = runExternalCommand(
            NUITKA_BUILD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        logger.error(f'build failed with returncode {err.returncode}')

        print(
            'stdout:\n'
            + err.stdout.decode('utf-8', 'replace')
            + 'stderr:\n'
            + err.stderr.decode('utf-8', 'replace'),
            flush=True,
        )

        sys.exit(-1)
    else:
        logger.info(f'build success')

        print(
            'stdout:\n'
            + result.stdout.decode('utf-8', 'replace')
            + 'stderr:\n'
            + result.stderr.decode('utf-8', 'replace'),
            flush=True,
        )

    # Sleep for a while for any running nuitka tasks
    time.sleep(5)

    if PLATFORM == 'Windows':
        foldername = (
            f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
            f'{PLATFORM.lower()}{PLATFORM_RELEASE}'
        )

        try:
            shutil.rmtree(ROOT_DIR / DEPLOY_DIR_NAME / foldername)
        except FileNotFoundError:
            pass
        except Exception:
            # Any non-exit exceptions

            raise

        shutil.copytree(
            ROOT_DIR / DEPLOY_DIR_NAME / f'{APPLICATION_NAME}.dist',
            ROOT_DIR / DEPLOY_DIR_NAME / foldername,
        )
        shutil.make_archive(
            ARTIFACT_NAME,
            'zip',
            ROOT_DIR / DEPLOY_DIR_NAME,
            foldername,
            logger=logger,
        )
    elif PLATFORM == 'Darwin':
        appDir = ROOT_DIR / 'app'

        try:
            shutil.rmtree(appDir)
        except FileNotFoundError:
            pass
        except Exception:
            # Any non-exit exceptions

            raise

        try:
            os.mkdir(appDir)
        except Exception:
            # Any non-exit exceptions

            raise

        shutil.copytree(
            ROOT_DIR / DEPLOY_DIR_NAME / 'Furious-GUI.app',
            appDir / 'Furious-GUI.app',
        )

        try:
            logger.info('generating dmg')

            output = f'{ARTIFACT_NAME}.dmg'

            result = runExternalCommand(
                (
                    f'create-dmg '
                    f'--volname \"Furious\" '
                    f'--volicon \"Icons/png/rocket-takeoff-window.png\" '
                    f'--window-pos 200 120 '
                    f'--window-size 600 300 '
                    f'--icon-size 100 '
                    f'--icon \"Furious-GUI.app\" 175 120 '
                    f'--hide-extension \"Furious-GUI.app\" '
                    f'--app-drop-link 425 120 '
                    f'\"{ROOT_DIR / output}\" '
                    f'\"{appDir}\"'
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(f'generate dmg failed with returncode {err.returncode}')

            print(
                'stdout:\n'
                + err.stdout.decode('utf-8', 'replace')
                + 'stderr:\n'
                + err.stderr.decode('utf-8', 'replace'),
                flush=True,
            )

            sys.exit(-1)
        else:
            print(
                'stdout:\n'
                + result.stdout.decode('utf-8', 'replace')
                + 'stderr:\n'
                + result.stderr.decode('utf-8', 'replace'),
                flush=True,
            )

            logger.info(f'generate dmg success: {output}')

    # Sleep for a while for any running tasks
    time.sleep(5)


if __name__ == '__main__':
    main()
