# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from Furious.QtFramework.QtNetwork import *
from Furious.QtFramework.QtWidgets import *
from Furious.QtFramework.DynamicTranslate import gettext as _
from Furious.QtFramework.WebGETManager import *
from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtNetwork import *

from typing import AnyStr, Union, Callable

import os
import logging
import hashlib
import functools

__all__ = ['XrayAssetDownloadManager']

logger = logging.getLogger(__name__)


class SHA256Worker(QtCore.QObject, QtCore.QRunnable):
    finished = QtCore.Signal(str)

    def __init__(self, string=b''):
        # Explictly called __init__
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.string = string

    def run(self):
        self.finished.emit(hashlib.sha256(self.string).hexdigest())


class XrayAssetSHA256DownloadManager(WebGETManager):
    def __init__(self, parent=None, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'download sha256')

        super().__init__(parent, actionMessage=actionMessage)

    @staticmethod
    def fileContent(filepath, mode='rb') -> AnyStr:
        try:
            with open(filepath, mode) as file:
                return file.read()
        except Exception:
            # Any non-exit exceptions

            return b''

    def successCallback(self, networkReply, **kwargs):
        filepath = kwargs.pop('filepath', '')
        downloadCallback = kwargs.pop('downloadCallback', None)

        data = networkReply.readAll().data()

        if isinstance(data, bytes):
            datastr = data.decode('utf-8', 'replace')
        else:
            datastr = str(data)

        logger.debug(f'data: {data}')

        # 6068a73edfa08b63080b8d362bd4c5b069689a3548f413f43cfa58227a201571  geosite.dat
        # 3a12beaa33c81b6751b45833a0a942b9462420d91182e7fa1d768b418e604049  geoip.dat
        value = datastr.split()[0]

        basename = os.path.basename(filepath)

        def handleFinished(_digest, _value=''):
            logger.debug(
                f'computed digest is \'{_digest}\' while repo digest is \'{_value}\''
            )

            if _digest != _value:
                logger.info(f'digest not equal for {basename}. Start downloading asset')

                if callable(downloadCallback):
                    downloadCallback()
            else:
                logger.info(f'digest equal for {basename}. Nothing to do')

        worker = SHA256Worker(self.fileContent(filepath))

        worker.setAutoDelete(True)
        worker.finished.connect(functools.partial(handleFinished, _value=value))

        AppThreadPool().start(worker)

    def download(self, url, filepath, downloadCallback: Callable[[], None]):
        self.webGET(
            url,
            filepath=str(filepath),
            downloadCallback=downloadCallback,
        )


class XrayAssetAssetsDownloadManager(WebGETManager):
    def __init__(self, parent=None, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'download assets')

        super().__init__(parent, actionMessage=actionMessage)

    def successCallback(self, networkReply, **kwargs):
        filepath = kwargs.pop('filepath', '')

        saveFile = QtCore.QSaveFile(filepath)

        data = networkReply.readAll().data()

        if not saveFile.open(QtCore.QSaveFile.OpenModeFlag.WriteOnly):
            logger.error(f'failed to open \'{filepath}\' for writing')
        else:
            saveFile.write(data)

            if not saveFile.commit():
                logger.error(f'save file to \'{filepath}\' failed')
            else:
                logger.info(f'save file to \'{filepath}\' success')

    def download(self, url, filepath):
        self.webGET(url, filepath=str(filepath))


class XrayAssetPairDownloadHelper:
    def __init__(self, *args, **kwargs):
        sha256ActionMessage = kwargs.pop('sha256ActionMessage', 'download sha256')
        assetsActionMessage = kwargs.pop('assetsActionMessage', 'download assets')

        super().__init__(*args, **kwargs)

        self.sha256Downloader = XrayAssetSHA256DownloadManager(
            actionMessage=sha256ActionMessage
        )
        self.assetsDownloader = XrayAssetAssetsDownloadManager(
            actionMessage=assetsActionMessage
        )

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        return all(
            [
                self.sha256Downloader.configureHttpProxy(httpProxy),
                self.assetsDownloader.configureHttpProxy(httpProxy),
            ]
        )

    def download(self, sha256URL, assetsURL, filepath):
        self.sha256Downloader.download(
            url=sha256URL,
            filepath=filepath,
            downloadCallback=functools.partial(
                self.assetsDownloader.download, assetsURL, filepath
            ),
        )


class XrayAssetDownloadManager:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.downloadHelperGeosite = XrayAssetPairDownloadHelper(
            sha256ActionMessage='download geosite sha256',
            assetsActionMessage='download geosite assets',
        )
        self.downloadHelperGeoip = XrayAssetPairDownloadHelper(
            sha256ActionMessage='download geoip sha256',
            assetsActionMessage='download geoip assets',
        )

    def configureHttpProxy(self, httpProxy: Union[str, None]) -> bool:
        return all(
            [
                self.downloadHelperGeosite.configureHttpProxy(httpProxy),
                self.downloadHelperGeoip.configureHttpProxy(httpProxy),
            ]
        )

    def download(self):
        self.downloadHelperGeosite.download(
            sha256URL=URL_GEOSITE_SHA256,
            assetsURL=URL_GEOSITE,
            filepath=XRAY_ASSET_PATH_GEOSITE,
        )
        self.downloadHelperGeoip.download(
            sha256URL=URL_GEOIP_SHA256,
            assetsURL=URL_GEOIP,
            filepath=XRAY_ASSET_PATH_GEOIP,
        )
