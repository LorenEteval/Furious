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

"""Protect Xray asset downloads from malformed or mismatched content."""

from Furious.Backends.Xray.AssetDownloadManager import (
    XrayAssetAssetsDownloadManager,
    XrayAssetSHA256DownloadManager,
)

from PySide6 import QtCore

from unittest import TestCase, mock

import os
import hashlib
import unittest
import tempfile

from tests.support import application, processQtEvents


class _Reply:
    """Expose the byte-array portion of QNetworkReply used by the managers."""

    def __init__(self, data: bytes):
        self._data = QtCore.QByteArray(data)

    def readAll(self):
        return self._data


class XrayAssetDownloadTest(TestCase):
    """Verify checksum metadata and downloaded bytes before replacement."""

    @classmethod
    def setUpClass(cls):
        application()

    def tearDown(self):
        processQtEvents()

    def testMalformedChecksumDoesNotStartHashOrAssetDownload(self):
        manager = XrayAssetSHA256DownloadManager()
        download = mock.Mock()

        with (
            mock.patch(
                'Furious.Backends.Xray.AssetDownloadManager.AppThreadPool'
            ) as threadPool,
            self.assertLogs(
                'Furious.Backends.Xray.AssetDownloadManager', level='ERROR'
            ) as logs,
        ):
            manager.successCallback(
                _Reply(b'not-a-sha256 asset.dat'),
                filepath='asset.dat',
                downloadCallback=download,
            )

        threadPool.assert_not_called()
        download.assert_not_called()
        self.assertIn('asset update skipped', '\n'.join(logs.output))
        manager.deleteLater()

    def testChangedLocalAssetForwardsNormalizedExpectedDigest(self):
        manager = XrayAssetSHA256DownloadManager()
        download = mock.Mock()
        expectedDigest = hashlib.sha256(b'new asset').hexdigest()
        pool = mock.Mock()
        pool.start.side_effect = lambda worker: worker.run()

        with (
            tempfile.NamedTemporaryFile() as existing,
            mock.patch(
                'Furious.Backends.Xray.AssetDownloadManager.AppThreadPool',
                return_value=pool,
            ),
        ):
            existing.write(b'old asset')
            existing.flush()
            manager.successCallback(
                _Reply(f'{expectedDigest.upper()}  asset.dat\n'.encode()),
                filepath=existing.name,
                downloadCallback=download,
            )

        download.assert_called_once_with(expectedDigest)
        manager.deleteLater()

    def testMismatchedDownloadPreservesExistingAsset(self):
        manager = XrayAssetAssetsDownloadManager()
        expectedDigest = hashlib.sha256(b'expected asset').hexdigest()

        with tempfile.NamedTemporaryFile(delete=False) as existing:
            existing.write(b'known-good asset')
            filepath = existing.name

        self.addCleanup(os.unlink, filepath)

        with self.assertLogs(
            'Furious.Backends.Xray.AssetDownloadManager', level='ERROR'
        ) as logs:
            manager.successCallback(
                _Reply(b'corrupt download'),
                filepath=filepath,
                expectedDigest=expectedDigest,
            )

        with open(filepath, 'rb') as existing:
            self.assertEqual(existing.read(), b'known-good asset')

        self.assertIn('existing file preserved', '\n'.join(logs.output))
        manager.deleteLater()

    def testMatchingDownloadAtomicallyReplacesExistingAsset(self):
        manager = XrayAssetAssetsDownloadManager()
        downloaded = b'verified new asset'
        expectedDigest = hashlib.sha256(downloaded).hexdigest()

        with tempfile.NamedTemporaryFile(delete=False) as existing:
            existing.write(b'old asset')
            filepath = existing.name

        self.addCleanup(os.unlink, filepath)

        manager.successCallback(
            _Reply(downloaded),
            filepath=filepath,
            expectedDigest=expectedDigest,
        )

        with open(filepath, 'rb') as existing:
            self.assertEqual(existing.read(), downloaded)

        manager.deleteLater()


if __name__ == '__main__':
    unittest.main()
