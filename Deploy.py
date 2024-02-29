from Furious.Version import __version__
from Furious.Utility import *

import os
import sys
import time
import shutil
import logging
import argparse
import subprocess

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
    if PYSIDE6_VERSION == '6.4.3':
        ARTIFACT_NAME = (
            f'{APPLICATION_NAME}-{__version__}-'
            f'macOS-10.9-{PLATFORM_MACHINE.lower()}'
        )
    else:
        ARTIFACT_NAME = (
            f'{APPLICATION_NAME}-{__version__}-'
            f'macOS-11.0-{PLATFORM_MACHINE.lower()}'
        )
else:
    ARTIFACT_NAME = ''


def printArtifactName():
    if PLATFORM == 'Windows':
        print(f'{ARTIFACT_NAME}.zip')


def cleanup():
    try:
        shutil.rmtree(ROOT_DIR / DEPLOY_DIR_NAME)
    except Exception as ex:
        logger.error(f'remove deployment dir failed: {ex}')
    else:
        logger.info(f'remove deployment dir success')

    if PLATFORM == 'Windows':
        # More cleanup on Windows
        try:
            os.remove(ROOT_DIR / f'{ARTIFACT_NAME}.zip')
        except Exception as ex:
            logger.error(f'remove artifact failed: {ex}')
        else:
            logger.info(f'remove artifact success')

        try:
            shutil.rmtree(
                ROOT_DIR / f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
                f'{PLATFORM.lower()}{PLATFORM_RELEASE}'
            )
        except Exception as ex:
            logger.error(f'remove potential unzipped dir failed: {ex}')
        else:
            logger.info(f'remove potential unzipped dir success')


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
        import nuitka
    except ImportError:
        # Any non-exit exceptions

        logger.error('please install nuitka to run this script')

        sys.exit(-1)

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
            + err.stderr.decode('utf-8', 'replace')
        )
    else:
        logger.info(f'build success')

        print(
            'stdout:\n'
            + result.stdout.decode('utf-8', 'replace')
            + 'stderr:\n'
            + result.stderr.decode('utf-8', 'replace')
        )

    if PLATFORM == 'Windows':
        # Sleep for a while for any running nuitka tasks
        time.sleep(2)

        foldername = (
            f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
            f'{PLATFORM.lower()}{PLATFORM_RELEASE}'
        )

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


if __name__ == '__main__':
    main()
