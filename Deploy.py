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

from Furious.Utility import *

import os
import sys
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

# Exit status
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

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
    # Deploy: Not implemented
    NUITKA_BUILD = ''

if PLATFORM == 'Windows':
    if PLATFORM_RELEASE.endswith('Server'):
        # Windows server. Fixed to windows10
        winVerCompatible = f'{PLATFORM.lower()}10'
    else:
        winVerCompatible = f'{PLATFORM.lower()}{PLATFORM_RELEASE}'

    ARTIFACT_NAME = (
        f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
        f'{winVerCompatible}-{PLATFORM_MACHINE.lower()}'
    )

    WIN_UNZIPPED = f'{APPLICATION_NAME}-{APPLICATION_VERSION}-{winVerCompatible}'
elif PLATFORM == 'Darwin':
    value = versionToValue(PYSIDE6_VERSION)

    # https://doc.qt.io/qt-6/supported-platforms.html
    if value <= versionToValue('6.4.3'):
        macVerCompatible = 'macOS-10.9'
    elif value <= versionToValue('6.7.3'):
        macVerCompatible = 'macos-11.0'
    else:
        macVerCompatible = 'macOS-12.0'

    ARTIFACT_NAME = (
        f'{APPLICATION_NAME}-{APPLICATION_VERSION}-'
        f'{macVerCompatible}-{PLATFORM_MACHINE.lower()}'
    )

    MAC_APP_DIR = ROOT_DIR / 'app'
    MAC_DMG_FILENAME = f'{ARTIFACT_NAME}.dmg'
    MAC_CREATE_DMG_CMD = (
        f'create-dmg '
        f'--volname \"Furious\" '
        f'--volicon \"Icons/png/rocket-takeoff-window.png\" '
        f'--window-pos 200 120 '
        f'--window-size 600 300 '
        f'--icon-size 100 '
        f'--icon \"Furious-GUI.app\" 175 120 '
        f'--hide-extension \"Furious-GUI.app\" '
        f'--app-drop-link 425 120 '
        f'\"{ROOT_DIR / MAC_DMG_FILENAME}\" '
        f'\"{MAC_APP_DIR}\"'
    )
else:
    # Deploy: Not implemented
    ARTIFACT_NAME = ''


def downloadXrayAssets(url, filename):
    try:
        import requests
    except ImportError:
        raise ModuleNotFoundError('missing requests module')

    try:
        # Make sure the save directory exists
        if not os.path.exists(XRAY_ASSET_DIR):
            os.makedirs(XRAY_ASSET_DIR)

        # Full path where the file will be saved
        filepath = os.path.join(XRAY_ASSET_DIR, filename)

        # Send an HTTP GET request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful

        # Open the save_path in write-binary mode and write the content of the response
        with open(filepath, 'wb') as file:
            file.write(response.content)

    except Exception as ex:
        # Any non-exit exceptions

        logger.error(
            f'failed to download file from {url}. Status code: {response.status_code}'
        )

        return False
    else:
        logger.info(f'file downloaded successfully and saved to {filepath}')

        return True


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
            # Remove artifact
            os.remove(ROOT_DIR / f'{ARTIFACT_NAME}.zip')
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove artifact failed: {ex}')
        else:
            logger.info(f'remove artifact success')

        try:
            # Remove unzipped folder
            shutil.rmtree(ROOT_DIR / WIN_UNZIPPED)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove unzipped dir failed: {ex}')
        else:
            logger.info('remove unzipped dir success')
    elif PLATFORM == 'Darwin':
        # More cleanup on Darwin
        try:
            # Remove artifact
            os.remove(ROOT_DIR / f'{ARTIFACT_NAME}.dmg')
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove artifact failed: {ex}')
        else:
            logger.info(f'remove artifact success')

        try:
            # Remove app folder
            shutil.rmtree(MAC_APP_DIR)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(f'remove app dir failed: {ex}')
        else:
            logger.info(f'remove app dir success')
    else:
        # Deploy: Not implemented
        pass


def download():
    # URLs of geosite and geoip assets
    url_geosite = 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat'
    url_geoip = 'https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat'

    # Xray assets names
    filename_geosite = 'geosite.dat'
    filename_geoip = 'geoip.dat'

    return all(
        [
            downloadXrayAssets(url_geosite, filename_geosite),
            downloadXrayAssets(url_geoip, filename_geoip),
        ]
    )


def printStandardStream(stdout, stderr):
    if isinstance(stdout, bytes):
        decoded_stdout = stdout.decode('utf-8', 'replace')
    else:
        decoded_stdout = stdout

    if isinstance(stderr, bytes):
        decoded_stderr = stderr.decode('utf-8', 'replace')
    else:
        decoded_stderr = stderr

    print(f'stdout:\n{decoded_stdout}stderr:\n{decoded_stderr}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--download',
        action='store_true',
        help='Download latest asset files',
    )
    parser.add_argument(
        '-c',
        '--cleanup',
        action='store_true',
        help='Cleanup deployment files',
    )

    args = parser.parse_args()

    if args.cleanup:
        cleanup()

        logger.info('cleanup done')

        sys.exit(EXIT_SUCCESS)

    if args.download:
        success = EXIT_SUCCESS if download() else EXIT_FAILURE

        sys.exit(success)

    try:
        import nuitka
    except ImportError:
        raise ModuleNotFoundError('please install nuitka to run this script')

    logger.info('building')

    try:
        result = runExternalCommand(
            NUITKA_BUILD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        logger.error(f'build failed with returncode {err.returncode}')

        printStandardStream(err.stdout, err.stderr)

        sys.exit(EXIT_FAILURE)
    else:
        logger.info(f'build success')

        printStandardStream(result.stdout, result.stderr)

    if PLATFORM == 'Windows':
        try:
            shutil.rmtree(ROOT_DIR / DEPLOY_DIR_NAME / WIN_UNZIPPED)
        except FileNotFoundError:
            pass
        except Exception:
            # Any non-exit exceptions

            raise

        shutil.copytree(
            ROOT_DIR / DEPLOY_DIR_NAME / f'{APPLICATION_NAME}.dist',
            ROOT_DIR / DEPLOY_DIR_NAME / WIN_UNZIPPED,
        )
        shutil.make_archive(
            ARTIFACT_NAME,
            'zip',
            ROOT_DIR / DEPLOY_DIR_NAME,
            WIN_UNZIPPED,
            logger=logger,
        )
    elif PLATFORM == 'Darwin':
        try:
            shutil.rmtree(MAC_APP_DIR)
        except FileNotFoundError:
            pass
        except Exception:
            # Any non-exit exceptions

            raise

        try:
            os.mkdir(MAC_APP_DIR)
        except Exception:
            # Any non-exit exceptions

            raise

        shutil.copytree(
            ROOT_DIR / DEPLOY_DIR_NAME / 'Furious-GUI.app',
            MAC_APP_DIR / 'Furious-GUI.app',
        )

        logger.info('generating dmg')

        try:
            result = runExternalCommand(
                MAC_CREATE_DMG_CMD,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            logger.error(f'generate dmg failed with returncode {err.returncode}')

            printStandardStream(err.stdout, err.stderr)

            sys.exit(EXIT_FAILURE)
        else:
            logger.info(f'generate dmg success: {MAC_DMG_FILENAME}')

            printStandardStream(result.stdout, result.stderr)
    else:
        # Deploy: Not implemented
        pass

    sys.exit(EXIT_SUCCESS)


if __name__ == '__main__':
    main()
