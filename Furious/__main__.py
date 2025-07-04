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

from Furious.Interface import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Widget.Application import Application

from PySide6 import QtCore
from PySide6.QtGui import QDesktopServices

import os
import sys
import logging
import functools
import traceback

__all__ = ['main']

logger = logging.getLogger(__name__)


def runAppMain():
    process = AppMainProcess(functools.partial(Application, sys.argv))

    process.start()
    process.join()

    exitcode = process.exitcode

    if exitcode == 0:
        sys.exit(exitcode)

    # For Qt runtime. Not used
    _app = Application(sys.argv)

    if exitcode == ApplicationFactory.ExitCode.PlatformNotSupported:
        messageBox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)

        messageBox.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
        messageBox.setWindowTitle(_(APPLICATION_NAME))
        messageBox.setText(
            _(f'{APPLICATION_NAME} is not able to run on this operating system')
        )

        if hasattr(os, 'uname'):
            # Unix-like OS
            unameTuple = (
                'sysname',
                'nodename',
                'release',
                'version',
                'machine',
            )

            messageBox.setInformativeText(
                _('Operating system information')
                + '\n'
                + '\n'.join(
                    list(f'{arg}: {val}' for arg, val in zip(unameTuple, os.uname()))
                )
            )

        # Show the MessageBox and wait for the user to close it
        messageBox.exec()
    else:
        if exitcode == ApplicationFactory.ExitCode.AssertionError:
            # Assertion error
            text = _(
                f'{APPLICATION_NAME} encountered an internal error and needs to be stopped'
            )
        else:
            # Unknown exception
            text = _(
                f'{APPLICATION_NAME} stopped unexpectedly due to an unknown exception'
            )

        messageBox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)

        messageBox.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
        messageBox.setWindowTitle(_(APPLICATION_NAME))
        messageBox.setText(text)

        if process.fileWritten.value:
            # Crash log saved
            crashLogFile = str(CRASH_LOG_DIR / process.logFileName)

            logger.info(f'crash log has been saved to {crashLogFile}')

            messageBox.setInformativeText(
                _('Crash log has been saved to') + f' {crashLogFile}'
            )
            button0 = messageBox.addButton(
                _('Open crash log'), AppQMessageBox.ButtonRole.AcceptRole
            )
            button1 = messageBox.addButton(
                _('OK'), AppQMessageBox.ButtonRole.RejectRole
            )

            def handleButtonClicked(button):
                if button == button0:
                    # Open
                    if QDesktopServices.openUrl(
                        QtCore.QUrl.fromLocalFile(crashLogFile)
                    ):
                        logger.info(f'open crash log {crashLogFile} success')
                    else:
                        logger.error(f'open crash log {crashLogFile} failed')
                else:
                    # OK. Do nothing
                    pass

            messageBox.buttonClicked.connect(handleButtonClicked)

            # Show the MessageBox and wait for the user to close it
            messageBox.exec()
        else:
            # Crash log wasn't saved
            logger.info(f'crash log was not saved')

            # Show the MessageBox and wait for the user to close it
            messageBox.exec()

    sys.exit(exitcode)


def main():
    try:
        runAppMain()
    except Exception:
        # Any non-exit exceptions

        traceback.print_exc()

        sys.exit(-1)


if __name__ == '__main__':
    main()
