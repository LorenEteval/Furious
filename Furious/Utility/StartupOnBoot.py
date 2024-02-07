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

from Furious.Utility.Constants import *
from Furious.Utility.AppSettings import *
from Furious.Utility.SystemRuntime import isScriptMode

from PySide6 import QtCore

import os
import sys
import logging
import plistlib

__all__ = ['StartupOnBoot']

logger = logging.getLogger(__name__)


class StartupOnBoot:
    @staticmethod
    def on_():
        def _on_():
            if isScriptMode():
                # Script mode
                logger.info('ignore turn on StartupOnBoot in script mode')

                return True

            if PLATFORM == 'Windows':
                settings = QtCore.QSettings(
                    'HKEY_CURRENT_USER\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run',
                    QtCore.QSettings.Format.NativeFormat,
                )

                appFilePath = sys.argv[0].replace('/', '\\')

                settings.setValue(APPLICATION_NAME, f'\"{appFilePath}\"')

                return True

            if PLATFORM == 'Linux':
                autostartDir = os.path.join(
                    os.path.expanduser('~'), '.config', 'autostart'
                )

                try:
                    os.mkdir(autostartDir)
                except FileExistsError:
                    pass
                except Exception:
                    # Any non-exit exceptions

                    return False

                try:
                    with open(
                        os.path.join(autostartDir, f'{APPLICATION_NAME}.desktop'),
                        'w',
                        encoding='utf-8',
                    ) as file:
                        file.write(
                            f'[Desktop Entry]\n'
                            f'Exec={sys.argv[0]}\n'
                            f'Version={APPLICATION_VERSION}\n'
                            f'Type=Application\n'
                            f'Categories=Development\n'
                            f'Name={APPLICATION_NAME}\n'
                            f'Terminal=false\n'
                            f'X-GNOME-Autostart-enabled=true\n'
                            f'StartupNotify=false\n'
                            f'X-GNOME-Autostart-Delay=10\n'
                            f'X-MATE-Autostart-Delay=10\n'
                            f'X-KDE-autostart-after=panel\n'
                        )
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                autostartDir = os.path.join(
                    os.path.expanduser('~'), 'Library', 'LaunchAgents'
                )

                try:
                    os.mkdir(autostartDir)
                except FileExistsError:
                    pass
                except Exception:
                    # Any non-exit exceptions

                    return False

                try:
                    plistData = {
                        'Label': f'{APPLICATION_MACOS_SIGNATURE}.{APPLICATION_NAME}',
                        'ProgramArguments': [sys.argv[0]],
                        'RunAtLoad': True,
                    }

                    with open(
                        os.path.join(
                            autostartDir,
                            f'{APPLICATION_MACOS_SIGNATURE}.{APPLICATION_NAME}.plist',
                        ),
                        'wb',
                    ) as file:
                        plistlib.dump(plistData, file)
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _on_():
            logger.info('turn on StartupOnBoot success')
        else:
            logger.error('turn on StartupOnBoot failed')

    @staticmethod
    def off():
        def _off():
            if PLATFORM == 'Windows':
                settings = QtCore.QSettings(
                    'HKEY_CURRENT_USER\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run',
                    QtCore.QSettings.Format.NativeFormat,
                )

                settings.remove(APPLICATION_NAME)

                return True

            if PLATFORM == 'Linux':
                autostartDir = os.path.join(
                    os.path.expanduser('~'), '.config', 'autostart'
                )

                try:
                    os.remove(os.path.join(autostartDir, f'{APPLICATION_NAME}.desktop'))
                except FileNotFoundError:
                    return True
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

            if PLATFORM == 'Darwin':
                autostartDir = os.path.join(
                    os.path.expanduser('~'), 'Library', 'LaunchAgents'
                )

                try:
                    os.remove(
                        os.path.join(
                            autostartDir,
                            f'{APPLICATION_MACOS_SIGNATURE}.{APPLICATION_NAME}.plist',
                        )
                    )
                except FileNotFoundError:
                    return True
                except Exception:
                    # Any non-exit exceptions

                    return False
                else:
                    return True

        if _off():
            logger.info('turn off StartupOnBoot success')
        else:
            logger.error('turn off StartupOnBoot failed')
