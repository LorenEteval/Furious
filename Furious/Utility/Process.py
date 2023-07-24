from Furious.Widget.Application import Application
from Furious.Utility.Constants import PLATFORM, CRASH_LOG_DIR

from PySide6.QtWidgets import QApplication

import os
import sys
import logging
import datetime
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

        if QApplication.instance() is not None:
            QApplication.instance().exit(error)
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
                lambda x, y: x + y,
                traceback.format_exception(exceptionType, exceptionValue, tb),
            )

            if QApplication.instance() is None:
                crashLog = f'{stackLog}'
            else:
                crashLog = f'{QApplication.instance().log()}\n{stackLog}'

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
