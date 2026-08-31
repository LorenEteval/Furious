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
from Furious.Qt.Signals import connectWeakly
from Furious.Repository import Storage
from Furious.Service.SubscriptionImporter import (
    SubscriptionImportService,
    SubscriptionSource,
    SubscriptionWorkerUnsafe,
)
from Furious.Service.SubscriptionPreparation import (
    SubscriptionPreparationJob,
    SubscriptionPreparationRelay,
)
from Furious.Service.SubscriptionSync import SubscriptionSynchronizer

from PySide6 import QtCore
from PySide6.QtNetwork import QNetworkRequest

from dataclasses import dataclass

import re
import os
import time
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


@dataclass
class _SubscriptionBatchState:
    """Track logical completion independently from network reply completion."""

    pending: set
    showMessageBox: bool
    successful: list
    failed: list
    structural: bool = False


class SubscriptionManager(HttpGetManager):
    """Own subscription networking, decoding, reconciliation, and persistence."""

    # Presentation metadata changed for these stable subscription IDs. This
    # deliberately does not imply that profile topology changed.
    subscriptionStateChanged = QtCore.Signal(object)

    # Subscription groups or their derived profile topology changed.
    subscriptionsChanged = QtCore.Signal()
    subscriptionCommitted = QtCore.Signal(str)
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
        self._batches = {}
        self._preparationJobs = {}
        self._preparationPayloads = {}
        self._nextBatchId = 0
        self._nextPreparationJobId = 0
        self._shuttingDown = False

        self._preparationRelay = SubscriptionPreparationRelay(self)
        self._preparationRelay.completed.connect(
            self._handlePreparationOutcome,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        self._preparationPool = QtCore.QThreadPool(self)
        self._preparationPool.setMaxThreadCount(
            max(1, min((os.cpu_count() or 1) // 2, 4))
        )

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
            not self._shuttingDown
            and subscription
            and self._requestVersions.get(unique) == version
            and subscription.get('webURL') == kwargs.get('webURL')
            and (
                'requestSignature' not in kwargs
                or self._requestSignature(subscription) == kwargs['requestSignature']
            )
        )

    @staticmethod
    def _requestSignature(subscription):
        """Capture every source option whose edit invalidates prepared data."""
        return (
            subscription.get('webURL', ''),
            subscription.get('enabled', True),
            subscription.get('userAgent', ''),
            subscription.get('filter', ''),
            subscription.get('lastDecoderId', ''),
        )

    @QtCore.Slot(object)
    def _autoUpdateTimeout(self, timer):
        """Run the subscription associated with the firing service-owned timer."""
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

            connectWeakly(
                timer.timeout,
                self,
                '_autoUpdateTimeout',
                sender=timer,
                forwardSender=True,
            )

            self._autoUpdateTimers[unique] = timer

        shouldRun = interval is not None and subscription.get('enabled', True)

        if not shouldRun:
            if not timer.isActive():
                return

            timer.stop()

            logger.info(
                f'stop auto update job for subscription '
                f'({subscription.get("remark", "")}, {unique!r})'
            )

            return

        if timer.isActive() and timer.interval() == interval:
            return

        previousInterval = timer.interval() if timer.isActive() else None

        timer.start(interval)

        if previousInterval is None:
            logger.info(
                f'start auto update job for subscription '
                f'({subscription.get("remark", "")}, {unique!r}). '
                f'Interval is {interval // (60 * 1000)} mins'
            )
        else:
            logger.info(
                f'reschedule auto update job for subscription '
                f'({subscription.get("remark", "")}, {unique!r}). '
                f'Interval changed from {previousInterval // (60 * 1000)} '
                f'to {interval // (60 * 1000)} mins'
            )

    def configureAutoUpdate(self, unique: str):
        """Reconcile the schedule for one known subscription mutation."""
        subscription = Storage.UserSubs().get(unique)

        if subscription is None:
            self.removeAutoUpdate(unique)

            return

        self._configureAutoUpdate(unique, subscription)

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

    @QtCore.Slot(object)
    def _releaseFinishedReply(self, reply):
        """Forget one exact subscription reply after its completion is dispatched."""
        unique = self._replySubscriptions.pop(reply, '')

        self._activeReplies.pop(reply, None)

        if unique:
            self._pruneRequestVersion(unique)

    def cancelUpdates(self, unique: str | None = None):
        """Cancel network and preparation work and invalidate eventual completions."""
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

        for job in tuple(self._preparationJobs.values()):
            if unique is None or job.context.get('unique') == unique:
                job.cancel()

    def shutdown(self):
        """Boundedly stop every manager-owned request, timer, and preparation job."""
        if self._shuttingDown:
            return

        self._shuttingDown = True

        for timer in self._autoUpdateTimers.values():
            timer.stop()

        self.cancelUpdates()
        self._preparationPool.clear()

        for job in self._preparationJobs.values():
            job.cancel()

        # Running third-party Python code may not be interruptible. Keep the
        # relay/pool alive until those exact jobs finish rather than allowing a
        # worker to publish through a destroyed QObject during application exit.
        self._preparationPool.waitForDone()

        self._preparationJobs.clear()
        self._preparationPayloads.clear()
        self._batches.clear()

    @staticmethod
    def _filterImportResult(result, profileFilter: str, remark: str):
        """Apply a copied regex filter as part of subscription preparation."""
        profileFilter = str(profileFilter).strip()

        if result is None or not profileFilter:
            return result

        try:
            pattern = re.compile(profileFilter, re.IGNORECASE)
        except re.error as ex:
            logger.error(
                f'invalid subscription filter for {remark!r}: {ex}. '
                f'Importing all profiles'
            )

            return result

        return type(result)(
            result.decoderId,
            tuple(
                profile
                for profile in result.profiles
                if pattern.search(str(getattr(profile, 'itemRemark', '')))
            ),
            result.rejectedItems,
        )

    def _startPreparationJob(self, stage: str, context: dict, work):
        """Dispatch one copied operation to the bounded preparation pool."""
        if not self._isCurrentRequest(context):
            self._finishOperation(context)

            return None

        self._nextPreparationJobId += 1

        jobId = self._nextPreparationJobId
        job = SubscriptionPreparationJob(
            jobId,
            stage,
            context,
            work,
            self._preparationRelay,
        )

        self._preparationJobs[jobId] = job
        self._preparationPool.start(job)

        return jobId

    def _startImportPreparation(self, data: bytes, context: dict):
        """Decode, parse, normalize, and validate a copied payload off-thread."""
        source = SubscriptionSource(
            context.get('unique', ''),
            context.get('webURL', ''),
            context.get('remark', ''),
            context.get('decoderId'),
        )
        importer = self.importer
        filterResult = type(self)._filterImportResult
        profileFilter = str(context.get('filter', ''))
        remark = str(context.get('remark', ''))

        def work(isCancelled):
            """Operate only on captured bytes, values, and plugin data capabilities."""
            result = importer.importPayload(
                data,
                source,
                requireWorkerSafe=True,
                isCancelled=isCancelled,
            )

            return filterResult(result, profileFilter, remark)

        jobId = self._startPreparationJob('import', context, work)

        if jobId is not None:
            self._preparationPayloads[jobId] = data

    def _runGuiThreadImport(self, data: bytes, context: dict):
        """Isolate non-opted-in third-party parsing on its required GUI thread."""
        source = SubscriptionSource(
            context.get('unique', ''),
            context.get('webURL', ''),
            context.get('remark', ''),
            context.get('decoderId'),
        )

        try:
            result = self.importer.importPayload(data, source)
            result = self._filterImportResult(
                result,
                context.get('filter', ''),
                context.get('remark', ''),
            )
        except Exception as ex:
            # Any non-exit exceptions

            logger.exception(
                f'failed to prepare subscription {context.get("unique", "")!r}'
            )

            self._failOperation(context, str(ex) or type(ex).__name__)

            return

        self._handleImportedResult(context, result, 0.0)

    def _handleImportedResult(self, context: dict, result, duration: float):
        """Capture current group data and dispatch copied reconciliation work."""
        if not self._isCurrentRequest(context):
            self._finishOperation(context)

            return

        if result is None or not result.profiles:
            self._failOperation(context, 'UnsupportedSubscriptionFormat')

            return

        context = {**context, 'decoderId': result.decoderId}

        logger.info(
            f'prepared subscription ({context.get("remark", "")}, '
            f'{context.get("unique", "")!r}) with {len(result.profiles)} profiles '
            f'from {result.decoderId!r}; rejected {result.rejectedItems}; '
            f'decode/parse {duration:.3f}s'
        )

        try:
            snapshot = self.synchronizer.snapshot(
                Storage.UserServers(),
                context.get('unique', ''),
            )
        except Exception as ex:
            # Any non-exit exceptions

            self._failOperation(context, str(ex) or type(ex).__name__)

            return

        synchronizer = self.synchronizer
        incoming = result.profiles

        def work(isCancelled):
            """Compare copied existing and incoming profiles without live state."""
            if isCancelled():
                return None

            return synchronizer.prepare(snapshot, incoming)

        self._startPreparationJob('reconcile', context, work)

    @QtCore.Slot(object)
    def _handlePreparationOutcome(self, outcome):
        """Validate one queued worker result and commit only on this Qt thread."""
        jobId = getattr(outcome, 'jobId', -1)

        self._preparationJobs.pop(jobId, None)

        fallbackPayload = self._preparationPayloads.pop(jobId, None)
        context = getattr(outcome, 'context', {})

        if self._shuttingDown:
            return

        if getattr(outcome, 'cancelled', False) or not self._isCurrentRequest(context):
            logger.debug(
                f'discard stale/cancelled subscription preparation for '
                f'{context.get("unique", "")!r}'
            )

            self._finishOperation(context)

            return

        if getattr(outcome, 'errorType', ''):
            if (
                outcome.errorType == SubscriptionWorkerUnsafe.__name__
                and fallbackPayload is not None
            ):
                self._runGuiThreadImport(fallbackPayload, context)
            else:
                logger.error(
                    f'subscription {outcome.stage} preparation failed for '
                    f'{context.get("unique", "")!r} ({outcome.errorType})'
                )

                self._failOperation(context, outcome.error)

            return

        if outcome.stage == 'import':
            self._handleImportedResult(context, outcome.value, outcome.duration)

            return

        if outcome.stage != 'reconcile' or outcome.value is None:
            self._finishOperation(context)

            return

        started = time.perf_counter()

        try:
            result = self._synchronizePreparedProfiles(context['unique'], outcome.value)
        except Exception as ex:
            # Any non-exit exceptions

            error = str(ex) or type(ex).__name__

            if not self._isCurrentRequest(context):
                self._finishOperation(context)
            else:
                logger.exception(
                    f'failed to commit subscription {context.get("unique", "")!r}'
                )
                self._failOperation(context, error)

            return

        committed = {**context, 'syncResult': result}

        self.subscriptionCommitted.emit(context['unique'])
        self._recordGroupSuccess(committed, result)
        self.subscriptionStateChanged.emit((context['unique'],))
        self._finishOperation(committed, successful=committed, structural=True)

        logger.info(
            f'committed subscription {context["unique"]!r}; reconciliation '
            f'{outcome.duration:.3f}s, GUI commit {time.perf_counter() - started:.3f}s'
        )

    def _failOperation(self, context: dict, error: str):
        """Finalize one current logical operation as an isolated failure."""
        failed = {**context, 'error': error}

        if self._isCurrentRequest(context):
            self._recordGroupFailure(failed)
            self.subscriptionStateChanged.emit((context.get('unique', ''),))

        self._finishOperation(context, failed=failed)

    def _finishOperation(
        self,
        context: dict,
        *,
        successful=None,
        failed=None,
        structural: bool = False,
    ):
        """Complete one batch member and publish one coalesced batch outcome."""
        batchId = context.get('batchId')
        state = self._batches.get(batchId)

        if state is None or self._shuttingDown:
            return

        token = (context.get('unique', ''), context.get('requestVersion'))

        if token not in state.pending:
            return

        state.pending.remove(token)

        if successful is not None:
            state.successful.append(successful)
        if failed is not None and self._isCurrentRequest(context):
            state.failed.append(failed)

        state.structural = state.structural or structural

        if state.pending:
            return

        self._batches.pop(batchId, None)

        try:
            Storage.persistSubscriptionGroups()
        except Exception:
            # Any non-exit exceptions

            logger.exception('failed to persist completed subscription batch')

        if state.structural:
            self.subscriptionsChanged.emit()

        if state.successful or state.failed:
            self.updateCompleted.emit(
                SubscriptionUpdateBatch(
                    tuple(state.successful),
                    tuple(state.failed),
                    state.showMessageBox,
                )
            )

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

        try:
            AppSettings.set('ActivatedItemIndex', str(newActivatedIndex))
        except Exception:
            # Any non-exit exceptions

            # Profile reconciliation has committed.  The legacy row-index
            # setting is derived compatibility state, not part of that commit.
            logger.exception(
                'failed to persist the active profile index after '
                f'synchronizing subscription {unique!r}'
            )

        try:
            if wasConnected and activeProfileId:
                if newActivatedIndex < 0 and activeWasManagedByGroup:
                    controller.startDisconnection()
                elif activeProfileId in result.changedProfileIds:
                    controller.startReconnection()
        except Exception:
            # Any non-exit exceptions

            # Reconciliation has committed at this point.  A controller-side
            # follow-up failure is not a failed or rolled-back synchronization.
            logger.exception(
                f'failed to apply connection effects after synchronizing '
                f'subscription {unique!r}'
            )

        return result

    def _synchronizePreparedProfiles(self, unique: str, plan):
        """Commit one accepted worker plan and apply GUI-owned connection effects."""
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
        result = self.synchronizer.commit(servers, plan)
        newActivatedIndex = next(
            (
                index
                for index, profile in enumerate(servers)
                if profile.metadata.profileId == activeProfileId
            ),
            -1,
        )

        try:
            AppSettings.set('ActivatedItemIndex', str(newActivatedIndex))
        except Exception:
            # Any non-exit exceptions

            logger.exception(
                'failed to persist the active profile index after '
                f'synchronizing subscription {unique!r}'
            )

        try:
            if wasConnected and activeProfileId:
                if newActivatedIndex < 0 and activeWasManagedByGroup:
                    controller.startDisconnection()
                elif activeProfileId in result.changedProfileIds:
                    controller.startReconnection()
        except Exception:
            # Any non-exit exceptions

            logger.exception(
                f'failed to apply connection effects after synchronizing '
                f'subscription {unique!r}'
            )

        return result

    @staticmethod
    def _recordGroupFailure(param):
        """Best-effort persist one current request's terminal failure state."""
        try:
            group = Storage.SubscriptionGroup(param.get('unique', ''))

            if group is None:
                return

            group.lastSyncStatus = 'error'
            group.lastSyncError = str(param.get('error', ''))

            Storage.upsertSubscriptionGroup(group)
        except Exception:
            # Any non-exit exceptions

            logger.exception(
                'failed to record synchronization failure for subscription '
                f'{param.get("unique", "")!r}'
            )

    @staticmethod
    def _recordGroupSuccess(param, result):
        """Best-effort persist one successfully committed synchronization state."""
        try:
            group = Storage.SubscriptionGroup(param.get('unique', ''))

            if group is None:
                return

            group.lastUpdated = (
                datetime.datetime.now().astimezone().isoformat(timespec='seconds')
            )
            group.lastDecoderId = param.get('decoderId', '')
            group.lastSyncStatus = 'success'
            group.lastSyncError = ''
            group.profileCount = len(result.profileIds)

            Storage.upsertSubscriptionGroup(group)
        except Exception:
            # Any non-exit exceptions

            logger.exception(
                'failed to record synchronization success for subscription '
                f'{param.get("unique", "")!r}'
            )

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

            try:
                result = self._synchronizeProfiles(
                    param['unique'],
                    param['profiles'],
                )
            except Exception as ex:
                # Any non-exit exceptions

                error = str(ex) or type(ex).__name__

                logger.exception(
                    f'failed to synchronize subscription '
                    f'{param.get("unique", "")!r}'
                )

                failed = {**param, 'error': error}
                committedFailure.append(failed)

                self._recordGroupFailure(failed)

                continue

            param['syncResult'] = result

            committedSuccess.append(param)

            # Reconciliation is the commit boundary. Notify consumers now so
            # subscription-scoped work is invalidated before the rest of a
            # multi-subscription batch finishes.
            self.subscriptionCommitted.emit(param['unique'])

            self._recordGroupSuccess(param, result)

        for param in failureArgs:
            if self._isCurrentRequest(param):
                committedFailure.append(param)

                self._recordGroupFailure(param)
            else:
                logger.info(
                    f'ignore stale subscription failure for '
                    f'{param.get("unique", "")!r}'
                )

        if not committedSuccess and not committedFailure:
            return

        changedSubscriptions = tuple(
            dict.fromkeys(
                param.get('unique', '')
                for param in (*committedSuccess, *committedFailure)
                if param.get('unique')
            )
        )

        if changedSubscriptions:
            self.subscriptionStateChanged.emit(changedSubscriptions)

        if committedSuccess:
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
        if 'batchId' in kwargs:
            return

        depthMap = kwargs.get('depthMap', {})
        depthMap['depth'] -= 1

        if depthMap['depth'] == 0:
            self.handleSynchronizationResults(**kwargs)

    def successCallback(self, networkReply, **kwargs):
        """Decode one successful subscription response."""
        if not self._isCurrentRequest(kwargs):
            self._finishOperation(kwargs)

            return

        if 'batchId' in kwargs:
            data = bytes(networkReply.readAll().data())
            decoderId = kwargs.get('decoderId') or kwargs.get('lastDecoderId')
            context = {**kwargs, 'decoderId': decoderId}

            if self.importer.registry.subscriptionDecoderWorkerSafe(decoderId):
                self._startImportPreparation(data, context)
            else:
                self._runGuiThreadImport(data, context)

            return

        unique = kwargs.get('unique', '')
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

            return

        logger.info(
            f'update subscription ({remark}, {unique!r}) success. '
            f'Got {len(result.profiles)} profiles from {result.decoderId!r}; '
            f'rejected {result.rejectedItems}'
        )

        successArgs.append(
            {**kwargs, 'profiles': result.profiles, 'decoderId': result.decoderId}
        )

    def failureCallback(self, networkReply, **kwargs):
        """Record one failed subscription response."""
        if not self._isCurrentRequest(kwargs):
            self._finishOperation(kwargs)

            return

        unique = kwargs.get('unique', '')
        remark = kwargs.get('remark', '')
        failureArgs = kwargs.get('failureArgs', list())

        error = networkReply.errorString()

        logger.error(f'update subscription ({remark}, {unique!r}) failed: {error}')

        if 'batchId' in kwargs:
            self._failOperation(kwargs, error)

            return

        failureArgs.append({'error': error, **kwargs})

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

        connectWeakly(
            reply.finished,
            self,
            '_releaseFinishedReply',
            sender=reply,
            forwardSender=True,
        )

    def updateSubscriptions(self, uniques, **kwargs):
        """Start eligible stable IDs as one status and completion batch."""
        subscriptions = Storage.UserSubs()

        batch = tuple(
            (unique, subscriptions[unique])
            for unique in dict.fromkeys(uniques)
            if unique in subscriptions
            and subscriptions[unique].get('enabled', True)
            and subscriptions[unique].get('webURL')
        )

        if not batch:
            return

        changedSubscriptions = []
        groups = []
        operations = []

        self._nextBatchId += 1

        batchId = self._nextBatchId

        for unique, subscription in batch:
            group = Storage.SubscriptionGroup(unique)

            if group is None:
                continue

            group.lastSyncStatus = 'syncing'
            group.lastSyncError = ''

            self.cancelUpdates(unique)

            version = self._requestVersions[unique]
            context = {
                'unique': unique,
                'remark': subscription.get('remark', ''),
                'webURL': subscription.get('webURL', ''),
                'userAgent': subscription.get('userAgent', ''),
                'filter': subscription.get('filter', ''),
                'decoderId': subscription.get('lastDecoderId') or None,
                'lastDecoderId': subscription.get('lastDecoderId', ''),
                'batchId': batchId,
                'requestVersion': version,
                'requestSignature': self._requestSignature(subscription),
            }

            groups.append(group)
            operations.append(context)
            changedSubscriptions.append(unique)

        if not operations:
            return

        Storage.upsertSubscriptionGroups(groups)
        Storage.persistSubscriptionGroups()

        self._batches[batchId] = _SubscriptionBatchState(
            {(context['unique'], context['requestVersion']) for context in operations},
            bool(kwargs.get('showMessageBox', True)),
            [],
            [],
        )

        if changedSubscriptions:
            self.subscriptionStateChanged.emit(tuple(changedSubscriptions))

        for context in operations:
            try:
                self.updateSubsByWebGET(
                    **context,
                    logActionMessage=bool(kwargs.get('logActionMessage', False)),
                )
            except Exception as ex:
                # Any non-exit exceptions

                logger.exception(
                    f'failed to start subscription request for '
                    f'{context.get("unique", "")!r}'
                )

                self._failOperation(context, str(ex) or type(ex).__name__)

    def updateSubsByUnique(self, unique: str, **kwargs):
        """Update one enabled subscription through the canonical batch path."""
        self.updateSubscriptions((unique,), **kwargs)

    def updateSubs(self, **kwargs):
        """Update every eligible subscription through the canonical batch path."""
        self.updateSubscriptions(tuple(Storage.UserSubs()), **kwargs)
