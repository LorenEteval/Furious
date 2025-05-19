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

from Furious.PyFramework import *
from Furious.QtFramework.WebGETManager import *
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

import logging
import functools

__all__ = ['NetworkStateManager']

logger = logging.getLogger(__name__)


class NetworkStateManager(SupportConnectedCallback, WebGETManager):
    MIN_JOB_INTERVAL = 2500
    MAX_JOB_INTERVAL = 2000000000

    def __init__(self, parent=None, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'test network state')

        super().__init__(parent, actionMessage=actionMessage)

        self.jobStatus = False
        self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

        self.jobTimeoutTimer = QtCore.QTimer()
        self.jobArrangeTimer = QtCore.QTimer()

        self.jobArrangeTimer.timeout.connect(lambda: self.startSingleTest())

    def recalculateJobInterval(self, jobStatus: bool) -> int:
        assert isinstance(jobStatus, bool)

        if self.jobStatus is jobStatus:
            self.jobInterval *= 2
        else:
            self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

        self.jobStatus = jobStatus

        if self.jobInterval >= NetworkStateManager.MAX_JOB_INTERVAL:
            # Limited
            self.jobInterval = NetworkStateManager.MAX_JOB_INTERVAL

        return self.jobInterval

    def successCallback(self, networkReply, **kwargs):
        self.jobTimeoutTimer.stop()
        self.jobArrangeTimer.start(self.recalculateJobInterval(jobStatus=True))

    def failureCallback(self, networkReply, **kwargs):
        self.jobTimeoutTimer.stop()
        self.jobArrangeTimer.start(self.recalculateJobInterval(jobStatus=False))

    def startSingleTest(self):
        networkReply = self.webGET(NETWORK_STATE_TEST_URL)

        def abort(_networkReply):
            if isinstance(_networkReply, QNetworkReply):
                _networkReply.abort()

        self.jobTimeoutTimer.timeout.connect(functools.partial(abort, networkReply))
        self.jobTimeoutTimer.start(NetworkStateManager.MIN_JOB_INTERVAL - 500)

    def stopTest(self):
        self.jobArrangeTimer.stop()
        self.jobTimeoutTimer.stop()

    def connectedCallback(self):
        if AppSettings.isStateON_('PowerSaveMode'):
            # Power optimization
            logger.info('no job for network state manager in power save mode')

            self.stopTest()
        else:
            self.jobInterval = NetworkStateManager.MIN_JOB_INTERVAL

            self.jobArrangeTimer.start(self.jobInterval)

    def disconnectedCallback(self):
        self.stopTest()
