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

"""Provide Qt support for Xray asset download manager."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt import *

from PySide6 import QtCore

from typing import AnyStr, Union, Callable

import os
import re
import logging
import hashlib
import functools

__all__ = ['XrayAssetDownloadManager']

logger = logging.getLogger(__name__)


class SHA256Worker(QtCore.QObject, QtCore.QRunnable):
    """Run SHA-256 work in the background."""

    finished = QtCore.Signal(str)

    def __init__(self, string=b''):
        # Explictly called __init__
        """Initialize the SHA256Worker."""
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)

        self.string = string

    def run(self):
        """Run the SHA-256 worker task."""
        self.finished.emit(hashlib.sha256(self.string).hexdigest())


class XrayAssetSHA256DownloadManager(HttpGetManager):
    """Coordinate Xray asset SHA-256 download operations."""

    def __init__(self, parent=None, **kwargs):
        """Initialize the XrayAssetSHA256DownloadManager."""
        actionMessage = kwargs.pop('actionMessage', 'download sha256')

        super().__init__(parent, actionMessage=actionMessage)

    @staticmethod
    def fileContent(filepath, mode='rb') -> AnyStr:
        """Return the file content value used by the Xray asset SHA-256 download manager."""
        try:
            with open(filepath, mode) as file:
                return file.read()
        except Exception:
            # Any non-exit exceptions

            return b''

    @staticmethod
    def parseDigest(data) -> str:
        """Return one normalized SHA-256 token or an empty string."""
        if isinstance(data, bytes):
            text = data.decode('ascii', 'replace')
        else:
            text = str(data)

        fields = text.split()

        if not fields or re.fullmatch(r'[0-9a-fA-F]{64}', fields[0]) is None:
            return ''

        return fields[0].lower()

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        filepath = kwargs.pop('filepath', '')
        downloadCallback = kwargs.pop('downloadCallback', None)

        # 6068a73edfa08b63080b8d362bd4c5b069689a3548f413f43cfa58227a201571  geosite.dat
        # 3a12beaa33c81b6751b45833a0a942b9462420d91182e7fa1d768b418e604049  geoip.dat
        basename = os.path.basename(filepath)
        value = self.parseDigest(networkReply.readAll().data())

        if not value:
            logger.error(
                f'invalid SHA-256 metadata for {basename}; asset update skipped'
            )

            return

        def handleFinished(_digest, _value=''):
            """Handle finished."""
            logger.debug(
                f'computed digest is \'{_digest}\' while repo digest is \'{_value}\''
            )

            if _digest != _value:
                logger.info(f'digest not equal for {basename}. Start downloading asset')

                if callable(downloadCallback):
                    downloadCallback(_value)
            else:
                logger.info(f'digest equal for {basename}. Nothing to do')

        worker = SHA256Worker(self.fileContent(filepath))

        worker.setAutoDelete(True)
        worker.finished.connect(functools.partial(handleFinished, _value=value))

        AppThreadPool().start(worker)

    def download(self, url, filepath, downloadCallback: Callable[[str], None]):
        """Download the Xray asset SHA-256 download manager."""
        self.webGET(
            url,
            filepath=str(filepath),
            downloadCallback=downloadCallback,
        )


class XrayAssetAssetsDownloadManager(HttpGetManager):
    """Coordinate Xray asset assets download operations."""

    def __init__(self, parent=None, **kwargs):
        """Initialize the XrayAssetAssetsDownloadManager."""
        actionMessage = kwargs.pop('actionMessage', 'download assets')

        super().__init__(parent, actionMessage=actionMessage)

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        filepath = kwargs.pop('filepath', '')
        expectedDigest = str(kwargs.pop('expectedDigest', '')).lower()

        data = bytes(networkReply.readAll().data())
        actualDigest = hashlib.sha256(data).hexdigest()
        basename = os.path.basename(filepath)

        if not expectedDigest or actualDigest != expectedDigest:
            logger.error(
                f'downloaded asset digest mismatch for {basename}; '
                f'existing file preserved'
            )

            return

        saveFile = QtCore.QSaveFile(filepath)

        if not saveFile.open(QtCore.QSaveFile.OpenModeFlag.WriteOnly):
            logger.error(
                f'failed to open \'{filepath}\' for writing. {saveFile.errorString()}'
            )
        else:
            written = saveFile.write(data)

            if written != len(data):
                saveFile.cancelWriting()

                logger.error(
                    f'write asset to \'{filepath}\' failed. '
                    f'{saveFile.errorString()}'
                )

                return

            if not saveFile.commit():
                logger.error(
                    f'save file to \'{filepath}\' failed. {saveFile.errorString()}'
                )
            else:
                logger.info(f'save file to \'{filepath}\' success')

    def download(self, url, filepath, expectedDigest: str):
        """Download the Xray asset assets download manager."""
        self.webGET(
            url,
            filepath=str(filepath),
            expectedDigest=expectedDigest,
        )


class XrayAssetPairDownloadHelper:
    """Represent Xray asset pair download helper."""

    def __init__(self, *args, **kwargs):
        """Initialize the XrayAssetPairDownloadHelper."""
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
        """Configure HTTP proxy."""
        return all(
            [
                self.sha256Downloader.configureHttpProxy(httpProxy),
                self.assetsDownloader.configureHttpProxy(httpProxy),
            ]
        )

    def download(self, sha256URL, assetsURL, filepath):
        """Download the Xray asset pair download helper."""
        self.sha256Downloader.download(
            url=sha256URL,
            filepath=filepath,
            downloadCallback=functools.partial(
                self.assetsDownloader.download, assetsURL, filepath
            ),
        )


class XrayAssetDownloadManager:
    """Coordinate Xray asset download operations."""

    def __init__(self, *args, **kwargs):
        """Initialize the XrayAssetDownloadManager."""
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
        """Configure HTTP proxy."""
        return all(
            [
                self.downloadHelperGeosite.configureHttpProxy(httpProxy),
                self.downloadHelperGeoip.configureHttpProxy(httpProxy),
            ]
        )

    def download(self):
        """Download the Xray asset download manager."""
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
