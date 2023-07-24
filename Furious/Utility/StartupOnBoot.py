from Furious.Utility.Constants import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    APPLICATION_MACOS_SIGNATURE,
    PLATFORM,
)

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

import os
import sys
import logging
import plistlib

logger = logging.getLogger(__name__)


class StartupOnBoot:
    def __init__(self):
        super().__init__()

    @staticmethod
    def on_():
        def _on():
            if sys.argv[0].endswith('.py'):
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

        if _on():
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
