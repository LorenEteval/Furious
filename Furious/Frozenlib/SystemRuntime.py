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

from __future__ import annotations

from Furious.Frozenlib.Constants import *
from Furious.Frozenlib.Utility import *
from Furious.Frozenlib.AppSettings import *

import os
import sys
import ctypes
import functools
import subprocess

__all__ = ['SystemRuntime']


class SystemRuntime:
    @staticmethod
    @functools.lru_cache(None)
    def ubuntuRelease() -> str:
        try:
            if PLATFORM != 'Linux':
                return ''

            result = runExternalCommand(
                ['cat', '/etc/lsb-release'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            values = dict(
                list(line.split('='))
                for line in filter(
                    lambda x: x != '',
                    result.stdout.decode('utf-8', 'replace').split('\n'),
                )
            )

            if values['DISTRIB_ID'] == 'Ubuntu':
                return values['DISTRIB_RELEASE']
            else:
                return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def appImagePath() -> str:
        if PLATFORM != 'Linux':
            return ''

        if 'APPIMAGE' in os.environ:
            return os.environ['APPIMAGE']
        else:
            return ''

    @staticmethod
    def flatpakID() -> str:
        if PLATFORM != 'Linux':
            return ''

        if 'FLATPAK_ID' in os.environ:
            return os.environ['FLATPAK_ID']
        else:
            return ''

    @staticmethod
    @functools.lru_cache(None)
    def isAssetsFolderWritable() -> bool:
        return os.access(XRAY_ASSET_DIR, os.W_OK)

    @staticmethod
    @functools.lru_cache(None)
    def isAdmin() -> bool:
        if PLATFORM == 'Windows':
            return ctypes.windll.shell32.IsUserAnAdmin() == 1
        else:
            return os.geteuid() == 0

    @staticmethod
    def isTUNMode() -> bool:
        if PLATFORM == 'Linux':
            if SystemRuntime.flatpakID():
                # TUN Mode disabled in flatpak
                return False
            else:
                return AppSettings.isStateON_('VPNMode')
        else:
            return AppSettings.isStateON_('VPNMode') and SystemRuntime.isAdmin()

    @staticmethod
    @functools.lru_cache(None)
    def isScriptMode() -> bool:
        return sys.argv[0].endswith('.py')

    @staticmethod
    @functools.lru_cache(None)
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

    @staticmethod
    @functools.lru_cache(None)
    def isWindows7() -> bool:
        return PLATFORM == 'Windows' and PLATFORM_RELEASE == '7'
