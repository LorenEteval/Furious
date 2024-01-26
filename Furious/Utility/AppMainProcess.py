from __future__ import annotations

from Furious.Interface import *
from Furious.Utility.Constants import *

from typing import Callable

import os
import sys
import logging
import datetime
import operator
import functools
import traceback
import multiprocessing

__all__ = ['AppMainProcess']

logger = logging.getLogger(__name__)

if PLATFORM == 'Windows':
    ProcessContext = multiprocessing
else:
    ProcessContext = multiprocessing.get_context('spawn')


class AppMainProcess(ProcessContext.Process):
    def __init__(self, loaderFn: Callable[[], ApplicationFactory], **kwargs):
        super().__init__(**kwargs)

        self.startupTime = str(datetime.datetime.now()).replace(':', '')
        self.logFileName = f'{self.startupTime}.log'
        self.fileWritten = multiprocessing.Manager().Value('b', False)

        self.appLoaderFn = loaderFn
        self.application = None

    def exceptHook(self, exceptionType, exceptionValue, tb):
        if logger.level < logging.CRITICAL:
            traceback.print_exception(exceptionType, exceptionValue, tb)

        if isinstance(exceptionValue, AssertionError):
            exitcode = ApplicationFactory.ExitCode.AssertionError
        else:
            exitcode = ApplicationFactory.ExitCode.UnknownException

        logger.error(f'stopped with exitcode {exitcode}')

        self.saveCrashLog(exceptionType, exceptionValue, tb)

        if APP() is not None:
            APP().exit(exitcode)
        else:
            sys.exit(exitcode)

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

        self.application = self.appLoaderFn()

        sys.exit(self.application.run())
