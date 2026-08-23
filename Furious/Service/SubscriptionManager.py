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

"""Download, decode, and reconcile subscription profiles."""

from __future__ import annotations

from Furious.Frozenlib import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    AppConnectionController,
    AppSettings,
)
from Furious.Qt.HttpGetManager import HttpGetManager
from Furious.Repository import Storage
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
)
from Furious.Service.SubscriptionSync import SubscriptionSynchronizer

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkRequest

from dataclasses import dataclass

import re
import logging
import datetime

__all__ = [
    'SUBSCRIPTION_AUTO_UPDATE_OPTIONS',
    'SUBSCRIPTION_PROXY_OPTIONS',
    'SubscriptionManager',
    'SubscriptionUpdateBatch',
    'resolveSubscriptionProxy',
]

logger = logging.getLogger(__name__)

SUBSCRIPTION_AUTO_UPDATE_OPTIONS = {
    '': None,
    'Never': None,
    'Every 5 mins': 5 * 60 * 1000,
    'Every 10 mins': 10 * 60 * 1000,
    'Every 15 mins': 15 * 60 * 1000,
    'Every 30 mins': 30 * 60 * 1000,
    'Every 45 mins': 45 * 60 * 1000,
    'Every 1 hour': 1 * 60 * 60 * 1000,
    'Every 2 hours': 2 * 60 * 60 * 1000,
    'Every 3 hours': 3 * 60 * 60 * 1000,
    'Every 6 hours': 6 * 60 * 60 * 1000,
    'Every 8 hours': 8 * 60 * 60 * 1000,
    'Every 10 hours': 10 * 60 * 60 * 1000,
    'Every 12 hours': 12 * 60 * 60 * 1000,
    'Every 24 hours': 24 * 60 * 60 * 1000,
}

SUBSCRIPTION_PROXY_OPTIONS = (
    '',
    'Use current proxy',
    'Force proxy',
    'No proxy',
)


def resolveSubscriptionProxy(option: str):
    """Resolve one persisted subscription proxy policy."""
    if option == 'Use current proxy':
        return Storage.Extras.UserHttpProxy()

    if option == 'Force proxy':
        return '127.0.0.1:10809'

    return None


@dataclass(frozen=True)
class SubscriptionUpdateBatch:
    """Describe one completed update batch for presentation consumers."""

    successful: tuple[dict, ...]
    failed: tuple[dict, ...]
    showMessageBox: bool


class SubscriptionManager(HttpGetManager):
    """Own subscription networking, decoding, reconciliation, and persistence."""

    subscriptionsChanged = QtCore.Signal()
    updateCompleted = QtCore.Signal(object)

    def __init__(self, parent=None, **kwargs):
        """Initialize the subscription workflow service."""
        actionMessage = kwargs.pop('actionMessage', 'update subs')

        super().__init__(parent, actionMessage=actionMessage, completionRunsOnce=False)

        self.importer = SubscriptionImportService()
        self.synchronizer = SubscriptionSynchronizer()
        self._autoUpdateTimers = {}
        self._requestVersions = {}
        self._activeReplies = {}
        self._replySubscriptions = {}

        self.refreshAutoUpdates()

    def _nextRequestVersion(self, unique: str) -> int:
        """Invalidate older completions and return the next group request version."""
        version = self._requestVersions.get(unique, 0) + 1

        self._requestVersions[unique] = version

        return version

    def _pruneRequestVersion(self, unique: str):
        """Forget version state once no subscription resource needs it."""
        if (
            unique in Storage.UserSubs()
            or unique in self._autoUpdateTimers
            or unique in self._replySubscriptions.values()
        ):
            return

        self._requestVersions.pop(unique, None)

    def _isCurrentRequest(self, kwargs) -> bool:
        """Return whether one completion still targets the current subscription."""
        version = kwargs.get('requestVersion')

        if version is None:
            return True

        unique = kwargs.get('unique', '')
        subscription = Storage.UserSubs().get(unique)

        return bool(
            subscription
            and self._requestVersions.get(unique) == version
            and subscription.get('webURL') == kwargs.get('webURL')
        )

    @QtCore.Slot()
    def _autoUpdateTimeout(self):
        """Run the subscription associated with the firing service-owned timer."""
        timer = self.sender()

        if not isinstance(timer, QtCore.QTimer):
            return

        unique = str(timer.property('subscriptionId') or '')
        subscription = Storage.UserSubs().get(unique)

        if not subscription:
            self.removeAutoUpdate(unique)

            return

        self.configureHttpProxy(resolveSubscriptionProxy(subscription.get('proxy', '')))
        self.updateSubsByUnique(unique, showMessageBox=False)

    def _configureAutoUpdate(self, unique: str, subscription):
        """Configure one stable-ID timer from persisted subscription policy."""
        autoUpdate = subscription.get('autoupdate', '')

        if autoUpdate not in SUBSCRIPTION_AUTO_UPDATE_OPTIONS:
            logger.error(f'{autoUpdate!r} is not in auto update options. Reset')

            autoUpdate = ''

            subscription['autoupdate'] = autoUpdate

        proxy = subscription.get('proxy', '')

        if proxy not in SUBSCRIPTION_PROXY_OPTIONS:
            logger.error(f'{proxy!r} is not in proxy options. Reset')

            subscription['proxy'] = ''

        interval = SUBSCRIPTION_AUTO_UPDATE_OPTIONS[autoUpdate]

        timer = self._autoUpdateTimers.get(unique)

        if timer is None:
            timer = QtCore.QTimer(self)
            timer.setProperty('subscriptionId', unique)
            timer.timeout.connect(self._autoUpdateTimeout)

            self._autoUpdateTimers[unique] = timer

        if interval is not None and subscription.get('enabled', True):
            logger.info(
                f'start auto update job for subscription '
                f'({subscription.get("remark", "")}, '
                f'{subscription.get("webURL", "")}). '
                f'Interval is {interval // (60 * 1000)} mins'
            )

            timer.start(interval)
        else:
            logger.info(
                f'stop auto update job for subscription '
                f'({subscription.get("remark", "")}, '
                f'{subscription.get("webURL", "")})'
            )

            timer.stop()

    def refreshAutoUpdates(self):
        """Reconcile service-owned timers with the current subscription repository."""
        subscriptions = Storage.UserSubs()

        for unique in tuple(self._autoUpdateTimers):
            if unique not in subscriptions:
                self.removeAutoUpdate(unique)

        for unique, subscription in subscriptions.items():
            self._configureAutoUpdate(unique, subscription)

    def removeAutoUpdate(self, unique: str):
        """Stop and destroy the timer owned by one removed subscription."""
        self.cancelUpdates(unique)

        timer = self._autoUpdateTimers.pop(unique, None)

        if timer is not None:
            timer.stop()
            timer.deleteLater()

        self._pruneRequestVersion(unique)

    @QtCore.Slot()
    def _releaseFinishedReply(self):
        """Forget one exact subscription reply after its completion is dispatched."""
        reply = self.sender()
        unique = self._replySubscriptions.pop(reply, '')

        self._activeReplies.pop(reply, None)

        if unique:
            self._pruneRequestVersion(unique)

    def cancelUpdates(self, unique: str | None = None):
        """Cancel exact active replies and invalidate their eventual completions."""
        if unique is None:
            subscriptions = {
                *self._requestVersions,
                *self._replySubscriptions.values(),
            }
        else:
            subscriptions = {unique}

        for subscriptionId in subscriptions:
            self._nextRequestVersion(subscriptionId)

        for reply in tuple(self._activeReplies):
            if unique is None or self._replySubscriptions.get(reply) == unique:
                reply.abort()

    def _synchronizeProfiles(self, unique: str, profiles):
        """Reconcile one group and apply connection effects without UI ownership."""
        servers = Storage.UserServers()
        activatedIndex = Storage.UserActivatedItemIndex()

        activeProfileId = ''
        activeWasManagedByGroup = False

        if 0 <= activatedIndex < len(servers):
            active = servers[activatedIndex]
            activeProfileId = active.metadata.profileId
            activeWasManagedByGroup = (
                active.itemSubscription == unique and active.itemSubscriptionManaged
            )

        controller = AppConnectionController()
        wasConnected = controller is not None and controller.isConnected()

        result = self.synchronizer.reconcile(servers, profiles, unique)

        newActivatedIndex = next(
            (
                index
                for index, profile in enumerate(servers)
                if profile.metadata.profileId == activeProfileId
            ),
            -1,
        )

        AppSettings.set('ActivatedItemIndex', str(newActivatedIndex))

        if wasConnected and activeProfileId:
            if newActivatedIndex < 0 and activeWasManagedByGroup:
                controller.startDisconnection()
            elif activeProfileId in result.changedProfileIds:
                controller.startReconnection()

        return result

    def handleSynchronizationResults(self, **kwargs):
        """Commit successful group-scoped synchronization results."""
        successArgs = kwargs.pop('successArgs', list())
        failureArgs = kwargs.pop('failureArgs', list())
        showMessageBox = kwargs.pop('showMessageBox', True)

        committedSuccess = []
        committedFailure = []

        for param in successArgs:
            if not self._isCurrentRequest(param):
                logger.info(
                    f'ignore stale subscription completion for '
                    f'{param.get("unique", "")!r}'
                )

                continue

            result = self._synchronizeProfiles(param['unique'], param['profiles'])
            param['syncResult'] = result

            committedSuccess.append(param)

            group = Storage.SubscriptionGroup(param['unique'])

            if group is not None:
                group.lastDecoderId = param.get('decoderId', '')
                group.lastSyncStatus = 'success'
                group.lastSyncError = ''
                group.profileCount = len(result.profileIds)

                Storage.upsertSubscriptionGroup(group)

        for param in failureArgs:
            if self._isCurrentRequest(param):
                committedFailure.append(param)
            else:
                logger.info(
                    f'ignore stale subscription failure for '
                    f'{param.get("unique", "")!r}'
                )

        if not committedSuccess and not committedFailure:
            return

        self.subscriptionsChanged.emit()
        self.updateCompleted.emit(
            SubscriptionUpdateBatch(
                tuple(committedSuccess),
                tuple(committedFailure),
                bool(showMessageBox),
            )
        )

    def completionCallback(self, **kwargs):
        """Complete a batch after its final reply finishes."""
        depthMap = kwargs.get('depthMap', {})
        depthMap['depth'] -= 1

        if depthMap['depth'] == 0:
            self.handleSynchronizationResults(**kwargs)

    def successCallback(self, networkReply, **kwargs):
        """Decode one successful subscription response."""
        if not self._isCurrentRequest(kwargs):
            return

        remark = kwargs.get('remark', '')
        webURL = kwargs.get('webURL', '')
        successArgs = kwargs.get('successArgs', list())
        failureArgs = kwargs.get('failureArgs', list())

        data = bytes(networkReply.readAll().data())

        source = SubscriptionSource(
            kwargs.get('unique', ''),
            webURL,
            remark,
            kwargs.get('decoderId'),
        )

        result = self.importer.importPayload(data, source)
        profileFilter = str(kwargs.get('filter', '')).strip()

        if result is not None and profileFilter:
            try:
                pattern = re.compile(profileFilter, re.IGNORECASE)
            except re.error as ex:
                logger.error(
                    f'invalid subscription filter for {remark!r}: {ex}. '
                    f'Importing all profiles'
                )
            else:
                result = type(result)(
                    result.decoderId,
                    tuple(
                        profile
                        for profile in result.profiles
                        if pattern.search(str(getattr(profile, 'itemRemark', '')))
                    ),
                    result.rejectedItems,
                )

        if result is None or not result.profiles:
            failureArgs.append({'error': 'UnsupportedSubscriptionFormat', **kwargs})
            group = Storage.SubscriptionGroup(kwargs.get('unique', ''))

            if group is not None:
                group.lastSyncStatus = 'error'
                group.lastSyncError = 'UnsupportedSubscriptionFormat'

                Storage.upsertSubscriptionGroup(group)

            return

        logger.info(
            f'update subs ({remark}, {webURL}) success. '
            f'Got {len(result.profiles)} profiles from {result.decoderId!r}; '
            f'rejected {result.rejectedItems}'
        )

        successArgs.append(
            {**kwargs, 'profiles': result.profiles, 'decoderId': result.decoderId}
        )

        unique = kwargs.get('unique', '')

        if unique in Storage.UserSubs():
            group = Storage.SubscriptionGroup(unique)

            if group is not None:
                group.lastUpdated = (
                    datetime.datetime.now().astimezone().isoformat(timespec='seconds')
                )
                group.lastDecoderId = result.decoderId

                Storage.upsertSubscriptionGroup(group)

    def failureCallback(self, networkReply, **kwargs):
        """Record one failed subscription response."""
        if not self._isCurrentRequest(kwargs):
            return

        remark = kwargs.get('remark', '')
        webURL = kwargs.get('webURL', '')
        failureArgs = kwargs.get('failureArgs', list())

        error = networkReply.errorString()

        logger.error(f'update subs ({remark}, {webURL}) failed: {error}')

        failureArgs.append({'error': error, **kwargs})

        group = Storage.SubscriptionGroup(kwargs.get('unique', ''))

        if group is not None:
            group.lastSyncStatus = 'error'
            group.lastSyncError = error

            Storage.upsertSubscriptionGroup(group)

    def updateSubsByWebGET(self, **kwargs):
        """Start one configured subscription request."""
        url = kwargs.get('webURL', '')

        if not url:
            return

        logActionMessage = kwargs.pop('logActionMessage', False)

        userAgent = str(kwargs.get('userAgent', '')).strip()

        request = QNetworkRequest(QtCore.QUrl(url))
        request.setRawHeader(
            b'User-Agent',
            (userAgent or f'{APPLICATION_NAME}/{APPLICATION_VERSION}').encode(),
        )

        reply = self.webGET(request, logActionMessage=logActionMessage, **kwargs)

        self._activeReplies[reply] = reply
        self._replySubscriptions[reply] = str(kwargs.get('unique', ''))

        reply.finished.connect(self._releaseFinishedReply)

    def updateSubsByUnique(self, unique: str, **kwargs):
        """Update one enabled subscription group by stable ID."""
        subscription = Storage.UserSubs().get(unique)

        if (
            not subscription
            or not subscription.get('enabled', True)
            or not subscription.get('webURL')
        ):
            return

        group = Storage.SubscriptionGroup(unique)

        if group is not None:
            group.lastSyncStatus = 'syncing'
            group.lastSyncError = ''

            Storage.upsertSubscriptionGroup(group)

        depthMap = kwargs.get('depthMap')
        successArgs = kwargs.get('successArgs')
        failureArgs = kwargs.get('failureArgs')

        if depthMap is None:
            depthMap = {'depth': 1}

        if successArgs is None:
            successArgs = list()

        if failureArgs is None:
            failureArgs = list()

        kwargs.update(
            depthMap=depthMap,
            successArgs=successArgs,
            failureArgs=failureArgs,
            requestVersion=self._nextRequestVersion(unique),
        )

        self.updateSubsByWebGET(unique=unique, **subscription, **kwargs)

    def updateSubs(self, **kwargs):
        """Update every enabled subscription as one completion batch."""
        enabledKeys = tuple(
            key
            for key, subscription in Storage.UserSubs().items()
            if subscription.get('enabled', True) and subscription.get('webURL')
        )

        if not enabledKeys:
            return

        depthMap = {'depth': len(enabledKeys)}
        successArgs = list()
        failureArgs = list()

        for key in enabledKeys:
            self.updateSubsByUnique(
                key,
                depthMap=depthMap,
                successArgs=successArgs,
                failureArgs=failureArgs,
                **kwargs,
            )
