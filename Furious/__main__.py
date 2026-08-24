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

"""Provide the Furious GUI application entry point."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Utility import *
from Furious.Application import DesktopApplication

from PySide6 import QtCore
from PySide6.QtGui import QDesktopServices

import sys
import logging
import functools
import traceback

__all__ = ['main']

logger = logging.getLogger(__name__)


def runClearSettings():
    """Run clear settings."""
    app = QtCore.QCoreApplication(sys.argv)
    app.setApplicationName(APPLICATION_NAME)
    app.setApplicationVersion(APPLICATION_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setOrganizationDomain(ORGANIZATION_DOMAIN)

    settings = QtCore.QSettings()
    settings.clear()
    settings.sync()

    logger.info('application settings have been cleared')

    sys.exit(0)


def runAppMain():
    """Run app main."""
    process = AppMainProcess(functools.partial(DesktopApplication, sys.argv))

    process.start()
    process.join()

    exitcode = process.exitcode

    if exitcode == 0:
        sys.exit(exitcode)

    # For Qt runtime. Not used
    _app = DesktopApplication(sys.argv)

    if exitcode == ApplicationRunner.ExitCode.AssertionError.value:
        # Assertion error
        text = _(
            f'{APPLICATION_NAME} encountered an internal error and needs to be stopped'
        )
    else:
        # Unknown exception
        text = _(f'{APPLICATION_NAME} stopped unexpectedly due to an unknown exception')

    mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical)

    mbox.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))
    mbox.setWindowTitle(_(APPLICATION_NAME))
    mbox.setText(text)

    if process.fileWritten.value:
        # Crash log saved
        crashLogFile = str(CRASH_LOG_DIR / process.logFileName)

        logger.info(f'crash log has been saved to {crashLogFile}')

        mbox.setInformativeText(_('Crash log has been saved to') + f' {crashLogFile}')
        openCrashLogButton = mbox.addButton(
            _('Open crash log'), AppQMessageBox.ButtonRole.AcceptRole
        )
        mbox.addButton(_('OK'), AppQMessageBox.ButtonRole.RejectRole)

        def handleButtonClicked(button):
            """Open the saved crash log when its action is selected."""
            if button != openCrashLogButton:
                return

            if QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(crashLogFile)):
                logger.info(f'open crash log {crashLogFile} success')
            else:
                logger.error(f'open crash log {crashLogFile} failed')

        mbox.buttonClicked.connect(handleButtonClicked)
    else:
        logger.info('crash log was not saved')

    # Keep the fallback application's local message box alive until dismissal.
    mbox.exec()

    sys.exit(exitcode)


def main():
    """Run the module command-line entry point."""
    try:
        if len(sys.argv) > 1 and sys.argv[1] == AppBuiltinCommand.Clear.value:
            runClearSettings()
        else:
            runAppMain()
    except Exception:
        # Any non-exit exceptions

        traceback.print_exc()

        sys.exit(-1)


if __name__ == '__main__':
    main()
