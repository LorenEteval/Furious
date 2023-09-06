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
from Furious.Utility.Constants import APP, PLATFORM, CRASH_LOG_DIR

import os
import sys
import logging
import datetime
import operator
import traceback
import functools
import multiprocessing

logger = logging.getLogger(__name__)

if PLATFORM == 'Windows':
    ProcessContext = multiprocessing
else:
    ProcessContext = multiprocessing.get_context('spawn')


class Process(ProcessContext.Process):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.startUpTime = str(datetime.datetime.now()).replace(':', '')
        self.logFileName = f'{self.startUpTime}.log'
        self.fileWritten = multiprocessing.Manager().Value('b', False)
        self.application = None

    def exceptHook(self, exceptionType, exceptionValue, tb):
        if logger.level < logging.CRITICAL:
            traceback.print_exception(exceptionType, exceptionValue, tb)

        if isinstance(exceptionValue, AssertionError):
            error = Application.ErrorCode.AssertionError
        else:
            error = Application.ErrorCode.UnknownException

        logger.error(f'stopped with exitcode {error}')

        self.saveCrashLog(exceptionType, exceptionValue, tb)

        if APP() is not None:
            APP().exit(error)
        else:
            sys.exit(error)

    def saveCrashLog(self, exceptionType, exceptionValue, tb):
        try:
            os.mkdir(CRASH_LOG_DIR)
        except FileExistsError:
            # Directory already exists
            pass
        except Exception:
            # Any non-exit exceptions

            return

        try:
            stackLog = functools.reduce(
                operator.add,
                traceback.format_exception(exceptionType, exceptionValue, tb),
            )

            if APP() is None:
                crashLog = f'{stackLog}'
            else:
                crashLog = f'{APP().log()}\n{stackLog}'

            with open(CRASH_LOG_DIR / self.logFileName, 'w', encoding='utf-8') as file:
                file.write(crashLog)

            self.fileWritten.value = True
        except Exception:
            # Any non-exit exceptions

            pass

    def run(self):
        sys.excepthook = self.exceptHook

        self.application = Application(sys.argv)

        sys.exit(self.application.run())
