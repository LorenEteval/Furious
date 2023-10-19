# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Widget.Application import Application
from Furious.Widget.Widget import MessageBox
from Furious.Utility.Constants import APPLICATION_NAME, CRASH_LOG_DIR
from Furious.Utility.Utility import bootstrapIcon, enumValueWrapper
from Furious.Utility.Process import Process
from Furious.Utility.Translator import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QDesktopServices

import os
import sys
import logging
import traceback

logger = logging.getLogger(__name__)


def main():
    try:
        process = Process()

        process.start()
        process.join()

        exitcode = process.exitcode

        if exitcode == 0:
            sys.exit(exitcode)

        # For Qt runtime. Not used
        _app = Application(sys.argv)

        if exitcode == Application.ErrorCode.PlatformNotSupported:
            messageBox = MessageBox(icon=MessageBox.Icon.Critical)

            messageBox.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
            messageBox.setWindowTitle(_(APPLICATION_NAME))
            messageBox.setText(
                _(f'{APPLICATION_NAME} is not be able to run on this operating system.')
            )

            if hasattr(os, 'uname'):
                messageBox.setInformativeText(
                    f'{_("Operating system information:")}\n'
                    + '\n'.join(
                        list(
                            f'{arg}: {val}'
                            for arg, val in zip(
                                (
                                    'sysname',
                                    'nodename',
                                    'release',
                                    'version',
                                    'machine',
                                ),
                                os.uname(),
                            )
                        )
                    )
                )

            # Show the MessageBox and wait for user to close it
            messageBox.exec()
        else:
            if exitcode == Application.ErrorCode.AssertionError:
                # Assertion error
                text = _(
                    f'{APPLICATION_NAME} encountered an internal error and needs to be stopped.'
                )
            else:
                # Unknown exception
                text = _(
                    f'{APPLICATION_NAME} stopped unexpectedly due to an unknown exception.'
                )

            messageBox = MessageBox(icon=MessageBox.Icon.Critical)

            messageBox.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
            messageBox.setWindowTitle(_(APPLICATION_NAME))
            messageBox.setText(text)

            if process.fileWritten.value:
                # Crash log saved

                crashLogFile = str(CRASH_LOG_DIR / process.logFileName)

                messageBox.setInformativeText(
                    _('Crash log has been saved to: ') + f'{crashLogFile}'
                )
                messageBox.addButton(
                    _('Open crash log'), MessageBox.ButtonRole.AcceptRole
                )
                messageBox.addButton(_('OK'), MessageBox.ButtonRole.RejectRole)

                # Show the MessageBox and wait for user to close it
                choice = messageBox.exec()

                if choice == enumValueWrapper(MessageBox.ButtonRole.AcceptRole):
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
            else:
                # Crash log not saved

                # Show the MessageBox and wait for user to close it
                messageBox.exec()

        sys.exit(exitcode)
    except Exception:
        # Any non-exit exceptions

        traceback.print_exc()

        sys.exit(-1)


if __name__ == '__main__':
    main()
