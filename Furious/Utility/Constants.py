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

from Furious.Version import __version__

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

import PySide6

import math
import pathlib
import platform
import functools

APP = functools.partial(QApplication.instance)

APPLICATION_NAME = 'Furious'
APPLICATION_VERSION = __version__
APPLICATION_MACOS_SIGNATURE = 'com.Furious'
APPLICATION_ABOUT_PAGE = 'https://github.com/LorenEteval/Furious/'
APPLICATION_REPO_OWNER_NAME = 'LorenEteval'
APPLICATION_REPO_NAME = 'Furious'

ORGANIZATION_NAME = 'Furious'
ORGANIZATION_DOMAIN = 'Furious.GUI'

# Tested: Furious supports minimum PySide6 version 6.1.0
PYSIDE6_VERSION = PySide6.__version__

PLATFORM = platform.system()
PLATFORM_RELEASE = platform.release()

LOCAL_SERVER_NAME = '891ad49d-8996-43cb-820c-d9baf42a04de'

SYSTEM_LANGUAGE = QtCore.QLocale().name()[:2].upper()

GOLDEN_RATIO = (math.sqrt(5) + 1) / 2

PROXY_OUTBOUND_USER_EMAIL = f'user@{ORGANIZATION_DOMAIN}'

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / APPLICATION_NAME / 'Data'
CRASH_LOG_DIR = ROOT_DIR / APPLICATION_NAME / 'CrashLog'

PROXY_SERVER_BYPASS = (
    'localhost;*.local;127.*;10.*;172.16.*;172.17.*;'
    '172.18.*;172.19.*;172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;'
    '172.26.*;172.27.*;172.28.*;172.29.*;172.30.*;172.31.*;192.168.*'
)

if PLATFORM == 'Windows':
    APPLICATION_TUN_DEVICE_NAME = APPLICATION_NAME
elif PLATFORM == 'Darwin':
    APPLICATION_TUN_DEVICE_NAME = 'utun777'
else:
    APPLICATION_TUN_DEVICE_NAME = ''

APPLICATION_TUN_NETWORK_INTERFACE_NAME = 'en0' if PLATFORM == 'Darwin' else ''
APPLICATION_TUN_GATEWAY_ADDRESS = '10.0.68.1'

if PLATFORM == 'Windows':
    APPLICATION_TUN_IP_ADDRESS = '10.0.68.10'
else:
    APPLICATION_TUN_IP_ADDRESS = APPLICATION_TUN_GATEWAY_ADDRESS

TOR_FAQ_URL = 'https://support.torproject.org/faq/'
TOR_FAQ_LABEL = f'Tor FAQ: <a href=\"{TOR_FAQ_URL}\">{TOR_FAQ_URL}</a>'

# Avoid standard Tor port in case of running Tor services
DEFAULT_TOR_SOCKS_PORT = 9048
DEFAULT_TOR_HTTPS_PORT = 9047
# 20s
DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT = 20

ADMINISTRATOR_NAME = 'Administrator' if PLATFORM == 'Windows' else 'root'


class LogType:
    Core = 'Core'
    App = 'App'
    Tor = 'Tor'


class Color:
    LIGHT_BLUE = '#43ACED'
    LIGHT_RED_ = '#FF7276'
    LIGHT_PURPLE = '#DA70D6'
