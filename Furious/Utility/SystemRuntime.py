from __future__ import annotations

from Furious.Utility.Constants import *
from Furious.Utility.AppSettings import AppSettings
from Furious.Utility.Utility import runExternalCommand

import os
import sys
import ctypes
import functools
import subprocess

__all__ = [
    'getPythonVersion',
    'getUbuntuRelease',
    'isAdministrator',
    'isVPNMode',
    'isScriptMode',
    'isPythonw',
    'isWindows7',
]


def getPythonVersion():
    return '.'.join(str(info) for info in sys.version_info)


@functools.lru_cache(None)
def getUbuntuRelease() -> str:
    try:
        result = runExternalCommand(
            ['cat', '/etc/lsb-release'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        values = dict(
            list(line.split('='))
            for line in filter(lambda x: x != '', result.stdout.decode().split('\n'))
        )

        if values['DISTRIB_ID'] == 'Ubuntu':
            return values['DISTRIB_RELEASE']
        else:
            return ''
    except Exception:
        # Any non-exit exceptions

        return ''


@functools.lru_cache(None)
def isAdministrator() -> bool:
    if PLATFORM == 'Windows':
        return ctypes.windll.shell32.IsUserAnAdmin() == 1
    else:
        return os.geteuid() == 0


def isVPNMode() -> bool:
    return isAdministrator() and AppSettings.isStateON_('VPNMode')


def isScriptMode() -> bool:
    return sys.argv[0].endswith('.py')


def isPythonw() -> bool:
    def isRealFile(file):
        if not hasattr(file, 'fileno'):
            return False

        try:
            tmp = os.dup(file.fileno())
        except Exception:
            # Any non-exit exceptions

            return False
        else:
            os.close(tmp)

            return True

    # pythonw.exe. Also applies to packed GUI application on Windows
    return not isRealFile(sys.__stdout__) or not isRealFile(sys.__stderr__)


def isWindows7() -> bool:
    return PLATFORM == 'Windows' and PLATFORM_RELEASE == '7'
