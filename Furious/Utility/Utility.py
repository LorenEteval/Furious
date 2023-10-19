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

from Furious.Gui.Icon import Icon
from Furious.Utility.Constants import (
    APP,
    PLATFORM,
    ROOT_DIR,
    PYSIDE6_VERSION,
    DEFAULT_TOR_SOCKS_PORT,
    DEFAULT_TOR_HTTPS_PORT,
    DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT,
)

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

import os
import sys
import time
import copy
import ujson
import queue
import ctypes
import logging
import pybase64
import threading
import functools
import ipaddress
import subprocess

logger = logging.getLogger(__name__)


class Base64Encoder:
    @staticmethod
    @functools.lru_cache(128)
    def encode(text):
        return pybase64.b64encode(text)

    @staticmethod
    @functools.lru_cache(128)
    def decode(text):
        return pybase64.b64decode(text, validate=False)


class Protocol:
    VMess = 'VMess'
    VLESS = 'VLESS'
    Shadowsocks = 'Shadowsocks'
    Trojan = 'Trojan'
    Hysteria1 = 'hysteria1'
    Hysteria2 = 'hysteria2'


class StateContext:
    def __init__(self, ob, *args, **kwargs):
        super().__init__(*args, **kwargs)

        assert hasattr(ob, 'setDisabled')

        self._ob = ob

    def __enter__(self):
        self._ob.setDisabled(True)

    def __exit__(self, exceptionType, exceptionValue, tb):
        self._ob.setDisabled(False)


class Storage:
    def __init__(self, emptyObject, getObjectFn, settingName):
        self.emptyObject = emptyObject
        self.getObjectFn = getObjectFn
        self.settingName = settingName

    def init(self):
        return copy.deepcopy(self.emptyObject)

    def sync(self, ob=None):
        if ob is None:
            # Object is up-to-date
            setattr(APP(), self.settingName, Storage.toStorage(self.getObjectFn()))
        else:
            # Object is up-to-date
            setattr(APP(), self.settingName, Storage.toStorage(ob))

    def toObject(self, storage):
        if not storage:
            # Storage does not exist, or is empty
            return self.init()

        return ujson.loads(Base64Encoder.decode(storage))

    @staticmethod
    def toStorage(ob):
        return Base64Encoder.encode(
            ujson.dumps(ob, ensure_ascii=False, escape_forward_slashes=False).encode()
        )

    def clear(self):
        setattr(APP(), self.settingName, '')


class _ServerStorage(Storage):
    # remark, config, subsId. (subsId corresponds to unique in Subscription Object)
    EMPTY_OBJECT = {'model': []}

    def __init__(self):
        super().__init__(
            _ServerStorage.EMPTY_OBJECT,
            lambda: APP().ServerWidget.StorageObj,
            'Configuration',
        )

    def clear(self):
        super().clear()

        APP().ActivatedItemIndex = str(-1)


class _RoutesStorage(Storage):
    # remark, corename, routes
    EMPTY_OBJECT = {'model': []}

    def __init__(self):
        super().__init__(
            _RoutesStorage.EMPTY_OBJECT,
            lambda: APP().RoutesWidget.StorageObj,
            'CustomRouting',
        )


class _SubscriptionStorage(Storage):
    # unique: remark, webURL
    EMPTY_OBJECT = {}

    def __init__(self):
        super().__init__(
            _SubscriptionStorage.EMPTY_OBJECT,
            lambda: APP().SubscriptionWidget.StorageObj,
            'CustomSubscription',
        )


class _TorRelaySettingsStorage(Storage):
    EMPTY_OBJECT = {
        'socksTunnelPort': DEFAULT_TOR_SOCKS_PORT,
        'httpsTunnelPort': DEFAULT_TOR_HTTPS_PORT,
        'useProxy': True,
        'logLevel': 'notice',
        'relayEstablishTimeout': DEFAULT_TOR_RELAY_ESTABLISH_TIMEOUT,
    }

    def __init__(self):
        super().__init__(
            _TorRelaySettingsStorage.EMPTY_OBJECT,
            lambda: APP().TorRelayWidget.StorageObj,
            'TorRelaySettings',
        )


ServerStorage = _ServerStorage()
RoutesStorage = _RoutesStorage()
SubscriptionStorage = _SubscriptionStorage()
TorRelaySettingsStorage = _TorRelaySettingsStorage()


class AsyncSubprocessMessage:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.msgQueue = queue.Queue()
        self.msgTimer = QtCore.QTimer()

        self.daemonThread = None

    def connectTimeoutCallback(self, callback):
        self.msgTimer.timeout.connect(callback)

    def startDaemonThread(self, stdout):
        def enqueue(msgQueue):
            for line in iter(stdout.readline, b''):
                msgQueue.put(line.decode('utf-8', 'replace').strip())

            stdout.close()

        self.daemonThread = threading.Thread(
            target=enqueue, args=(self.msgQueue,), daemon=True
        )
        self.daemonThread.start()

    def startTimer(self, msec=1):
        self.msgTimer.start(msec)

    def stopTimer(self):
        self.msgTimer.stop()

    def getLineNoWait(self):
        try:
            return self.msgQueue.get_nowait()
        except queue.Empty:
            # Queue is empty

            return ''


class Switch:
    OFF = '0'
    ON_ = '1'

    RANGE = [OFF, ON_]


class SupportConnectedCallback:
    Object = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportConnectedCallback.Object.append(self)

    def disconnectedCallback(self):
        raise NotImplementedError

    def connectedCallback(self):
        raise NotImplementedError

    @staticmethod
    def callConnectedCallback():
        for ob in SupportConnectedCallback.Object:
            assert isinstance(ob, SupportConnectedCallback)

            ob.connectedCallback()

    @staticmethod
    def callDisconnectedCallback():
        for ob in SupportConnectedCallback.Object:
            assert isinstance(ob, SupportConnectedCallback)

            ob.disconnectedCallback()


class NeedSyncSettings:
    Object = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        NeedSyncSettings.Object.append(self)

    def syncSettings(self):
        raise NotImplementedError

    @staticmethod
    def syncAll():
        for ob in NeedSyncSettings.Object:
            assert isinstance(ob, NeedSyncSettings)

            ob.syncSettings()


class SupportThemeChangedCallback:
    Object = list()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        SupportThemeChangedCallback.Object.append(self)

    def themeChangedCallback(self, theme):
        raise NotImplementedError

    @staticmethod
    def callThemeChangedCallback(theme):
        logger.info(f'system theme changed to {theme}')

        for ob in SupportThemeChangedCallback.Object:
            assert isinstance(ob, SupportThemeChangedCallback)

            ob.themeChangedCallback(theme)


def icon(prefix, name):
    if name.startswith('rocket-takeoff'):
        # Colorful. Use default
        return Icon(f':/Icons/bootstrap/{name}')
    else:
        return Icon(f':/Icons/{prefix}/{name}')


bootstrapIcon = functools.partial(icon, 'bootstrap')
bootstrapIconWhite = functools.partial(icon, 'bootstrap/white')


@functools.lru_cache(None)
def protocolRepr(protocol):
    if protocol.lower() == 'vmess':
        return Protocol.VMess

    if protocol.lower() == 'vless':
        return Protocol.VLESS

    if protocol.lower() == 'shadowsocks':
        return Protocol.Shadowsocks

    if protocol.lower() == 'trojan':
        return Protocol.Trojan

    return protocol


@functools.lru_cache(None)
def isValidIPAddress(address):
    try:
        ipaddress.ip_address(address)
    except Exception:
        # Any non-exita exceptions

        return False
    else:
        return True


def enumValueWrapper(enum):
    # Protect PySide6 enum wrapper behavior changes
    if PYSIDE6_VERSION < '6.2.2':
        return enum
    else:
        return enum.value


def eventLoopWait(ms):
    # Protect qWait method does not exist in some
    # old PySide6 version
    if PYSIDE6_VERSION < '6.3.1':
        startCounter, step = 0, 1

        while startCounter < ms:
            time.sleep(step / 1000)

            APP().processEvents()

            startCounter += step
    else:
        from PySide6.QtTest import QTest

        QTest.qWait(ms)


def runCommand(*args, **kwargs):
    if PLATFORM == 'Windows':
        return subprocess.run(
            *args, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs
        )
    else:
        return subprocess.run(*args, **kwargs)


def getAbsolutePath(path):
    return path if os.path.isabs(path) else str(ROOT_DIR / path)


@functools.lru_cache(None)
def getUbuntuRelease():
    try:
        result = runCommand(
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


def swapListItem(listOrTuple, index0, index1):
    swap = listOrTuple[index0]

    listOrTuple[index0] = listOrTuple[index1]
    listOrTuple[index1] = swap


@functools.lru_cache(None)
def isAdministrator():
    if PLATFORM == 'Windows':
        return ctypes.windll.shell32.IsUserAnAdmin() == 1
    else:
        return os.geteuid() == 0


def isVPNMode():
    return isAdministrator() and APP().VPNMode == Switch.ON_


def isScriptMode():
    return sys.argv[0].endswith('.py')


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


def isPythonw():
    # pythonw.exe. Also applies to packed GUI application on Windows
    return not isRealFile(sys.__stdout__) or not isRealFile(sys.__stderr__)


def moveToCenter(widget, parent=None):
    geometry = widget.geometry()

    if parent is None:
        center = QApplication.primaryScreen().availableGeometry().center()
    else:
        center = parent.geometry().center()

    geometry.moveCenter(center)

    widget.move(geometry.topLeft())
