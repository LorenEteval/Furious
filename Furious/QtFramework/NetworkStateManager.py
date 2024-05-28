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

from Furious.PyFramework import *
from Furious.QtFramework.QtNetwork import *
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

import logging
import functools

__all__ = ['NetworkStateManager']

logger = logging.getLogger(__name__)


class NetworkStateManager(SupportConnectedCallback, AppQNetworkAccessManager):
    MIN_JOB_INTERVAL = 2500
    MAX_JOB_INTERVAL = 2000000000

    def __init__(self, parent=None):
        super().__init__(parent)

        self.jobStatus = False
        self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

        self.jobTimeoutTimer = QtCore.QTimer()
        self.jobArrangeTimer = QtCore.QTimer()

        self.jobArrangeTimer.timeout.connect(lambda: self.startSingleTest())

    def successCallback(self):
        raise NotImplementedError

    def errorCallback(self, errorString: str):
        raise NotImplementedError

    def handleFinishedByNetworkReply(self, networkReply):
        assert isinstance(networkReply, QNetworkReply)

        if networkReply.error() != QNetworkReply.NetworkError.NoError:
            self.jobTimeoutTimer.stop()

            errorString = networkReply.errorString()

            logger.error(f'connection test failed. {errorString}')

            self.errorCallback(errorString)

            if self.jobStatus is False:
                self.jobInterval *= 2
            else:
                self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

            self.jobStatus = False
        else:
            self.jobTimeoutTimer.stop()

            logger.info(f'connection test success')

            self.successCallback()

            if self.jobStatus is True:
                self.jobInterval *= 2
            else:
                self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

            self.jobStatus = True

        if self.jobInterval >= NetworkStateManager.MAX_JOB_INTERVAL:
            # Limited
            self.jobInterval = NetworkStateManager.MAX_JOB_INTERVAL

        self.jobArrangeTimer.start(self.jobInterval)

    def startSingleTest(self):
        networkReply = self.get(QNetworkRequest(QtCore.QUrl(NETWORK_STATE_TEST_URL)))
        networkReply.finished.connect(
            functools.partial(
                self.handleFinishedByNetworkReply,
                networkReply,
            )
        )

        def abort(_networkReply):
            if isinstance(_networkReply, QNetworkReply):
                _networkReply.abort()

        self.jobTimeoutTimer.timeout.connect(functools.partial(abort, networkReply))
        self.jobTimeoutTimer.start(NetworkStateManager.MIN_JOB_INTERVAL - 500)

    def stopTest(self):
        self.jobArrangeTimer.stop()

    def connectedCallback(self):
        if AppSettings.isStateON_('PowerSaveMode'):
            # Power optimization
            logger.info('no job for network state manager in power save mode')

            self.jobArrangeTimer.stop()
        else:
            self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

            self.jobArrangeTimer.start(self.jobInterval)

    def disconnectedCallback(self):
        self.jobArrangeTimer.stop()
