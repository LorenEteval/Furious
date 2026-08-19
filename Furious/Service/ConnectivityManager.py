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

"""Provide Qt support for network connectivity manager."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Qt.HttpGetManager import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

import logging

__all__ = ['ConnectivityManager']

logger = logging.getLogger(__name__)


class ConnectivityManager(Mixins.ConnectionAware, HttpGetManager):
    """Coordinate network connectivity operations."""

    MIN_JOB_INTERVAL = 2500
    MAX_JOB_INTERVAL = 2000000000

    def __init__(self, parent=None, **kwargs):
        """Initialize the connectivity manager."""
        actionMessage = kwargs.pop('actionMessage', 'test network connectivity')

        super().__init__(parent, actionMessage=actionMessage)

        self.jobStatus = False
        self.jobInterval = ConnectivityManager.MIN_JOB_INTERVAL
        self._testingEnabled = False
        self._activeReply = None

        self.jobTimeoutTimer = QtCore.QTimer(self)
        self.jobTimeoutTimer.setSingleShot(True)
        self.jobTimeoutTimer.timeout.connect(self._abortActiveReply)

        self.jobArrangeTimer = QtCore.QTimer(self)
        self.jobArrangeTimer.setSingleShot(True)
        self.jobArrangeTimer.timeout.connect(self.startSingleTest)

    @QtCore.Slot()
    def _abortActiveReply(self):
        """Abort the one currently active connectivity request."""
        if isinstance(self._activeReply, QNetworkReply):
            self._activeReply.abort()

    def recalculateJobInterval(self, jobStatus: bool) -> int:
        """Return the recalculate job interval value used by the network connectivity manager."""
        assert isinstance(jobStatus, bool)

        if self.jobStatus is jobStatus:
            self.jobInterval *= 2
        else:
            self.jobInterval = ConnectivityManager.MIN_JOB_INTERVAL

        self.jobStatus = jobStatus

        if self.jobInterval >= ConnectivityManager.MAX_JOB_INTERVAL:
            # Limited
            self.jobInterval = ConnectivityManager.MAX_JOB_INTERVAL

        return self.jobInterval

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        if self._activeReply is networkReply:
            self._activeReply = None

        self.jobTimeoutTimer.stop()

        if self._testingEnabled:
            self.jobArrangeTimer.start(self.recalculateJobInterval(jobStatus=True))

    def failureCallback(self, networkReply, **kwargs):
        """Handle a failed network operation."""
        if self._activeReply is networkReply:
            self._activeReply = None

        self.jobTimeoutTimer.stop()

        if self._testingEnabled:
            self.jobArrangeTimer.start(self.recalculateJobInterval(jobStatus=False))

    def startSingleTest(self):
        # Use custom network connectivity test URL if possible
        """Start single test."""
        if not self._testingEnabled or self._activeReply is not None:
            return

        settings = AppSettings.get('CustomNetworkConnectivityTestURL')

        if isinstance(settings, str):
            url = settings
        else:
            url = NETWORK_CONNECTIVITY_TEST_URL

        self._activeReply = self.webGET(url)
        self.jobTimeoutTimer.start(ConnectivityManager.MIN_JOB_INTERVAL - 500)

    def stopTest(self):
        """Stop test."""
        self._testingEnabled = False
        self.jobArrangeTimer.stop()
        self.jobTimeoutTimer.stop()
        self._abortActiveReply()

    def connectedCallback(self):
        """Update the network connectivity manager for a connected state."""
        if AppSettings.isStateON_('PowerSaveMode'):
            # Power optimization
            logger.info('no job for network connectivity manager in power save mode')

            self.stopTest()
        else:
            self.jobInterval = ConnectivityManager.MIN_JOB_INTERVAL
            self._testingEnabled = True

            self.jobArrangeTimer.start(self.jobInterval)

    def disconnectedCallback(self):
        """Update the network connectivity manager for a disconnected state."""
        self.stopTest()
