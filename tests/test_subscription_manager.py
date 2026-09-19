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

"""Verify subscription workflow ownership outside table widgets."""

import os
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from Furious.Repository import Storage
from Furious.Repository.Subscriptions import SubscriptionGroup
from Furious.Qt import gettext
from Furious.Service.SubscriptionManager import (
    SubscriptionManager,
    _SubscriptionBatchState,
    _parseSubscriptionUserInfo,
)
from Furious.Window.SubscriptionPage import SubscriptionPage
from Furious.Widget.SubscriptionTableView import SubscriptionTableView

from tests.support import application, processQtEvents, waitFor

from PySide6 import QtCore, QtNetwork, QtTest, QtWidgets

from shiboken6 import isValid

from types import SimpleNamespace
from unittest import TestCase, mock


class _Reply(QtNetwork.QNetworkReply):
    """Supply in-memory data while preserving Qt's real header API contract."""

    def __init__(self, value=b'', error='request failed', headers=None):
        super().__init__()

        self._value = value
        self._error = error

        for name, headerValue in (headers or {}).items():
            self.setRawHeader(name, headerValue)

        self.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)

    def readData(self, maxSize):
        data, self._value = self._value[:maxSize], self._value[maxSize:]

        return data

    def errorString(self):
        return self._error

    def abort(self):
        self.close()


class _AbortableReply:
    """Record cancellation of one exact service-owned network reply."""

    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True


class SubscriptionManagerTest(TestCase):
    """Protect decoding, failure, and stable-ID scheduling boundaries."""

    @classmethod
    def setUpClass(cls):
        cls.application = application()

    @staticmethod
    def _manager(subscriptions=None):
        subscriptions = subscriptions if subscriptions is not None else {}

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            return SubscriptionManager()

    @staticmethod
    def _subscription(**overrides):
        """Return one enabled five-minute subscription definition."""
        subscription = {
            'remark': 'Group A',
            'webURL': 'https://invalid.test/a',
            'autoupdate': 'Every 5 mins',
            'proxy': '',
            'enabled': True,
        }
        subscription.update(overrides)

        return subscription

    def testSuccessfulAndInvalidPayloadsProduceSemanticBatchInputs(self):
        manager = self._manager()
        profile = SimpleNamespace(itemRemark='profile')
        imported = SimpleNamespace(
            decoderId='decoder',
            profiles=(profile,),
            rejectedItems=2,
        )
        manager.importer = SimpleNamespace(
            importPayload=mock.Mock(return_value=imported)
        )
        successful = []
        failed = []

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
            return_value=None,
        ):
            manager.successCallback(
                _Reply(
                    b'payload',
                    headers={
                        b'Subscription-Userinfo': (
                            b'upload=1024; download=2048; total=8192; '
                            b'expire=1893456000'
                        )
                    },
                ),
                unique='group-a',
                remark='Group A',
                webURL='https://invalid.test/subscription',
                successArgs=successful,
                failureArgs=failed,
            )

        self.assertEqual(len(successful), 1)
        self.assertEqual(successful[0]['profiles'], (profile,))
        self.assertEqual(successful[0]['decoderId'], 'decoder')
        self.assertEqual(
            successful[0]['subscriptionInfo'],
            {
                'upload': 1024,
                'download': 2048,
                'total': 8192,
                'expire': 1893456000,
            },
        )
        self.assertEqual(failed, [])

        manager.importer = SimpleNamespace(importPayload=mock.Mock(return_value=None))

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
            return_value=None,
        ):
            manager.successCallback(
                _Reply(b'invalid'),
                unique='group-a',
                successArgs=successful,
                failureArgs=failed,
            )

        self.assertEqual(failed[-1]['error'], 'UnsupportedSubscriptionFormat')
        manager.deleteLater()

    def testSubscriptionUserInfoParserRejectsInvalidAndUnboundedValues(self):
        """Treat provider quota headers as bounded advisory network input."""
        self.assertIsNone(_parseSubscriptionUserInfo(b''))
        self.assertIsNone(_parseSubscriptionUserInfo(b'upload=\xff'))
        self.assertEqual(
            _parseSubscriptionUserInfo(QtCore.QByteArray(b'Upload=1')),
            {'upload': 1, 'download': 0, 'total': 0, 'expire': 0},
        )
        self.assertEqual(
            _parseSubscriptionUserInfo(
                b'upload=1024; download=2048; total=8192; expire=1893456000; '
                b'ignored=value; upload=-1; total=999999999999999999999999'
            ),
            {
                'upload': 1024,
                'download': 2048,
                'total': 8192,
                'expire': 1893456000,
            },
        )

    def testBatchResponseCarriesSubscriptionInfoIntoWorkerContext(self):
        """Keep response metadata attached to the exact asynchronous request."""
        manager = self._manager()
        manager._isCurrentRequest = mock.Mock(return_value=True)
        manager.importer = SimpleNamespace(
            registry=SimpleNamespace(
                subscriptionDecoderWorkerSafe=mock.Mock(return_value=True)
            )
        )
        manager._startImportPreparation = mock.Mock()

        manager.successCallback(
            _Reply(
                b'payload',
                headers={
                    b'Subscription-Userinfo': (
                        b'upload=1024; download=2048; total=8192; ' b'expire=1893456000'
                    )
                },
            ),
            unique='group-a',
            batchId=7,
            lastDecoderId='decoder',
        )

        payload, context = manager._startImportPreparation.call_args.args
        self.assertEqual(payload, b'payload')
        self.assertEqual(
            context['subscriptionInfo'],
            {
                'upload': 1024,
                'download': 2048,
                'total': 8192,
                'expire': 1893456000,
            },
        )
        manager.deleteLater()

    def testSuccessfulCommitReplacesSubscriptionInfoButFailurePreservesIt(self):
        """Tie advisory metadata to the same successful group commit boundary."""
        group = SubscriptionGroup(
            id='group-a',
            subscriptionUpload=1,
            subscriptionDownload=2,
            subscriptionTotal=3,
            subscriptionExpire=4,
        )
        result = SimpleNamespace(profileIds=('profile-a', 'profile-b'))

        with (
            mock.patch.object(Storage, 'SubscriptionGroup', return_value=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroup') as upsert,
        ):
            SubscriptionManager._recordGroupSuccess(
                {
                    'unique': 'group-a',
                    'decoderId': 'decoder',
                    'subscriptionInfo': {
                        'upload': 1024,
                        'download': 2048,
                        'total': 8192,
                        'expire': 1893456000,
                    },
                },
                result,
            )

            SubscriptionManager._recordGroupFailure(
                {'unique': 'group-a', 'error': 'offline'}
            )
            metadataAfterFailure = (
                group.subscriptionUpload,
                group.subscriptionDownload,
                group.subscriptionTotal,
                group.subscriptionExpire,
            )

            SubscriptionManager._recordGroupSuccess(
                {'unique': 'group-a', 'subscriptionInfo': None},
                result,
            )

        self.assertEqual(metadataAfterFailure, (1024, 2048, 8192, 1893456000))
        self.assertEqual(group.subscriptionUpload, 0)
        self.assertEqual(group.subscriptionDownload, 0)
        self.assertEqual(group.subscriptionTotal, 0)
        self.assertEqual(group.subscriptionExpire, 0)
        self.assertEqual(group.lastSyncStatus, 'success')
        self.assertEqual(upsert.call_count, 3)

    def testRequestFailureIsDataForPresentationNotAWidgetSideEffect(self):
        manager = self._manager()
        failed = []

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
            return_value=None,
        ):
            manager.failureCallback(
                _Reply(error='offline'),
                unique='group-a',
                remark='Group A',
                webURL='https://invalid.test/subscription',
                failureArgs=failed,
            )

        self.assertEqual(failed[-1]['error'], 'offline')
        self.assertFalse(hasattr(manager, 'table'))
        manager.deleteLater()

    def testSubscriptionDiagnosticsExcludeConfiguredURL(self):
        """Identify a request without logging its credential-bearing URL."""
        manager = self._manager()
        profile = SimpleNamespace(itemRemark='profile')
        manager.importer = SimpleNamespace(
            importPayload=mock.Mock(
                return_value=SimpleNamespace(
                    decoderId='decoder',
                    profiles=(profile,),
                    rejectedItems=0,
                )
            )
        )
        configuredURL = 'https://example.invalid/subscription?token=value'

        with mock.patch('Furious.Service.SubscriptionManager.logger.info') as infoLog:
            manager.successCallback(
                _Reply(b'payload'),
                unique='group-a',
                remark='Group A',
                webURL=configuredURL,
                successArgs=[],
                failureArgs=[],
            )

        with mock.patch('Furious.Service.SubscriptionManager.logger.error') as errorLog:
            manager.failureCallback(
                _Reply(error='offline'),
                unique='group-a',
                remark='Group A',
                webURL=configuredURL,
                failureArgs=[],
            )

        self.assertIn('Group A', infoLog.call_args.args[0])
        self.assertIn('Group A', errorLog.call_args.args[0])
        self.assertIn('group-a', infoLog.call_args.args[0])
        self.assertIn('group-a', errorLog.call_args.args[0])
        self.assertNotIn(configuredURL, infoLog.call_args.args[0])
        self.assertNotIn(configuredURL, errorLog.call_args.args[0])
        self.assertNotIn('token=value', infoLog.call_args.args[0])
        self.assertNotIn('token=value', errorLog.call_args.args[0])

        manager.deleteLater()

    def testStaleRequestCompletionCannotMutateCurrentSubscription(self):
        subscriptions = {
            'group-a': {
                'webURL': 'https://invalid.test/current',
                'enabled': True,
            }
        }
        manager = self._manager(subscriptions)
        manager._requestVersions['group-a'] = 2
        manager.importer = SimpleNamespace(importPayload=mock.Mock())

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.successCallback(
                _Reply(b'stale'),
                unique='group-a',
                webURL='https://invalid.test/current',
                requestVersion=1,
                successArgs=[],
                failureArgs=[],
            )

        manager.importer.importPayload.assert_not_called()
        manager.deleteLater()

    def testStaleBatchEntriesAreNotReconciledOrReported(self):
        subscriptions = {
            'group-a': {
                'webURL': 'https://invalid.test/current',
                'enabled': True,
            }
        }
        manager = self._manager(subscriptions)
        manager._requestVersions['group-a'] = 2
        manager._synchronizeProfiles = mock.Mock()
        completed = []
        manager.updateCompleted.connect(completed.append)
        stale = {
            'unique': 'group-a',
            'webURL': 'https://invalid.test/current',
            'requestVersion': 1,
            'profiles': (),
        }

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.handleSynchronizationResults(
                successArgs=[stale],
                failureArgs=[{'error': 'offline', **stale}],
            )

        manager._synchronizeProfiles.assert_not_called()
        self.assertEqual(completed, [])
        manager.deleteLater()

    def testStaleDecodedResultCannotCommitSubscriptionMetadata(self):
        """Delay group metadata writes until the final current-request check."""
        subscriptions = {
            'group-a': {
                'webURL': 'https://invalid.test/current',
                'enabled': True,
            }
        }

        manager = self._manager(subscriptions)
        manager._requestVersions['group-a'] = 1

        profile = SimpleNamespace(itemRemark='profile')
        manager.importer = SimpleNamespace(
            importPayload=mock.Mock(
                return_value=SimpleNamespace(
                    decoderId='decoder',
                    profiles=(profile,),
                    rejectedItems=0,
                )
            )
        )

        successful = []
        failed = []

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.successCallback(
                _Reply(b'payload'),
                unique='group-a',
                webURL='https://invalid.test/current',
                requestVersion=1,
                successArgs=successful,
                failureArgs=failed,
            )

        manager._requestVersions['group-a'] = 2

        with (
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.UserSubs',
                return_value=subscriptions,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.upsertSubscriptionGroup'
            ) as upsert,
        ):
            manager.handleSynchronizationResults(
                successArgs=successful,
                failureArgs=failed,
            )

        upsert.assert_not_called()

        manager.deleteLater()

    def testOneSynchronizationFailureDoesNotAbortOtherGroups(self):
        """Isolate one group's preparation failure from the rest of a batch."""
        manager = self._manager()
        committed = SimpleNamespace(profileIds=('profile-id',))
        manager._isCurrentRequest = mock.Mock(return_value=True)
        manager._synchronizeProfiles = mock.Mock(
            side_effect=(RuntimeError('injected failure'), committed)
        )

        completed = []
        committedSubscriptions = []
        stateChanges = []
        structuralChanges = []

        manager.updateCompleted.connect(completed.append)
        manager.subscriptionCommitted.connect(committedSubscriptions.append)
        manager.subscriptionStateChanged.connect(
            lambda uniques: stateChanges.append(tuple(uniques))
        )
        manager.subscriptionsChanged.connect(lambda: structuralChanges.append(True))

        failed = {'unique': 'group-a', 'profiles': ()}
        successful = {'unique': 'group-b', 'profiles': ()}

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
            return_value=None,
        ):
            manager.handleSynchronizationResults(
                successArgs=[failed, successful],
                failureArgs=[],
            )

        self.assertEqual(manager._synchronizeProfiles.call_count, 2)
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].successful[0]['unique'], 'group-b')
        self.assertEqual(completed[0].failed[0]['unique'], 'group-a')
        self.assertIn('injected failure', completed[0].failed[0]['error'])

        self.assertEqual(committedSubscriptions, ['group-b'])
        self.assertEqual(stateChanges, [('group-b', 'group-a')])
        self.assertEqual(structuralChanges, [True])

        manager.deleteLater()

    def testFailedBatchPublishesStateWithoutStructuralChange(self):
        """Present terminal failure metadata without resetting profile consumers."""
        manager = self._manager()
        stateChanges = []
        structuralChanges = []
        completed = []

        manager.subscriptionStateChanged.connect(
            lambda uniques: stateChanges.append(tuple(uniques))
        )
        manager.subscriptionsChanged.connect(lambda: structuralChanges.append(True))
        manager.updateCompleted.connect(completed.append)

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
            return_value=None,
        ):
            manager.handleSynchronizationResults(
                successArgs=[],
                failureArgs=[{'unique': 'group-a', 'error': 'offline'}],
            )

        self.assertEqual(stateChanges, [('group-a',)])
        self.assertEqual(structuralChanges, [])
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].failed[0]['error'], 'offline')

        manager.deleteLater()

    def testCommittedMetadataFailureDoesNotAbortOtherGroups(self):
        """Treat status metadata as post-commit and keep processing the batch."""
        manager = self._manager()
        result = SimpleNamespace(profileIds=('profile-id',))
        manager._isCurrentRequest = mock.Mock(return_value=True)
        manager._synchronizeProfiles = mock.Mock(return_value=result)
        completed = []
        manager.updateCompleted.connect(completed.append)

        with (
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.SubscriptionGroup',
                side_effect=(SimpleNamespace(), SimpleNamespace()),
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.upsertSubscriptionGroup',
                side_effect=(RuntimeError('metadata write failed'), None),
            ) as upsert,
        ):
            manager.handleSynchronizationResults(
                successArgs=[
                    {'unique': 'group-a', 'profiles': ()},
                    {'unique': 'group-b', 'profiles': ()},
                ],
                failureArgs=[],
            )

        self.assertEqual(upsert.call_count, 2)
        self.assertEqual(len(completed), 1)
        self.assertEqual(
            [item['unique'] for item in completed[0].successful],
            ['group-a', 'group-b'],
        )

        manager.deleteLater()

    def testPostCommitConnectionFailureDoesNotUndoSynchronization(self):
        """Keep a committed reconciliation successful if reconnect later fails."""
        manager = self._manager()
        active = SimpleNamespace(
            metadata=SimpleNamespace(profileId='active-profile'),
            itemSubscription='group-a',
            itemSubscriptionManaged=True,
        )
        servers = [active]
        result = SimpleNamespace(
            profileIds=('active-profile',),
            changedProfileIds=('active-profile',),
        )
        manager.synchronizer.reconcile = mock.Mock(return_value=result)
        controller = SimpleNamespace(
            isConnected=mock.Mock(return_value=True),
            startDisconnection=mock.Mock(),
            startReconnection=mock.Mock(side_effect=RuntimeError('reconnect failed')),
        )

        with (
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.UserServers',
                return_value=servers,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.UserActivatedItemIndex',
                return_value=0,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.AppConnectionController',
                return_value=controller,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.AppSettings.set',
                side_effect=RuntimeError('settings write failed'),
            ),
        ):
            committed = manager._synchronizeProfiles('group-a', ())

        self.assertIs(committed, result)

        controller.startReconnection.assert_called_once_with()
        manager.deleteLater()

    def testCancellationInvalidatesAndAbortsOnlyTheSelectedSubscription(self):
        manager = self._manager()
        groupAReply = _AbortableReply()
        groupBReply = _AbortableReply()
        manager._requestVersions.update({'group-a': 1, 'group-b': 4})
        manager._activeReplies.update(
            {groupAReply: groupAReply, groupBReply: groupBReply}
        )
        manager._replySubscriptions.update(
            {groupAReply: 'group-a', groupBReply: 'group-b'}
        )

        manager.cancelUpdates('group-a')

        self.assertTrue(groupAReply.aborted)
        self.assertFalse(groupBReply.aborted)
        self.assertEqual(manager._requestVersions, {'group-a': 2, 'group-b': 4})

        manager._activeReplies.clear()
        manager._replySubscriptions.clear()
        manager.deleteLater()

    def testUnchangedAutoUpdateReconciliationPreservesDeadlineAndConnection(self):
        """Make repeated full reconciliation a true scheduler no-op."""
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        timer = manager._autoUpdateTimers['group-a']
        timerId = timer.timerId()

        QtTest.QTest.qWait(40)

        remainingBefore = timer.remainingTime()

        with (
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.UserSubs',
                return_value=subscriptions,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.logger.info'
            ) as lifecycleLog,
        ):
            for _index in range(100):
                manager.refreshAutoUpdates()

        self.assertIs(manager._autoUpdateTimers['group-a'], timer)
        self.assertEqual(timer.timerId(), timerId)
        self.assertEqual(timer.property('subscriptionId'), 'group-a')
        self.assertEqual(len(manager._autoUpdateTimers), 1)
        self.assertLessEqual(timer.remainingTime(), remainingBefore + 5)
        lifecycleLog.assert_not_called()

        manager.configureHttpProxy = mock.Mock()
        manager.updateSubsByUnique = mock.Mock()

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            timer.timeout.emit()

        manager.updateSubsByUnique.assert_called_once_with(
            'group-a', showMessageBox=False
        )
        manager.deleteLater()

    def testAutoUpdatePolicyTransitionsReuseTimerAndLogOnlyRealChanges(self):
        """Start, reschedule, and stop exactly when policy state changes."""
        subscriptions = {
            'group-a': self._subscription(autoupdate='Never'),
        }
        manager = self._manager(subscriptions)
        timer = manager._autoUpdateTimers['group-a']

        with (
            mock.patch(
                'Furious.Service.SubscriptionManager.Storage.UserSubs',
                return_value=subscriptions,
            ),
            mock.patch(
                'Furious.Service.SubscriptionManager.logger.info'
            ) as lifecycleLog,
        ):
            manager.configureAutoUpdate('group-a')

            lifecycleLog.assert_not_called()

            subscriptions['group-a']['autoupdate'] = 'Every 5 mins'

            manager.configureAutoUpdate('group-a')

            self.assertTrue(timer.isActive())
            self.assertEqual(timer.interval(), 5 * 60 * 1000)
            self.assertIn('start auto update job', lifecycleLog.call_args.args[0])

            activeTimerId = timer.timerId()

            manager.configureAutoUpdate('group-a')

            self.assertEqual(timer.timerId(), activeTimerId)
            self.assertEqual(lifecycleLog.call_count, 1)

            subscriptions['group-a']['autoupdate'] = 'Every 10 mins'

            manager.configureAutoUpdate('group-a')

            self.assertIs(manager._autoUpdateTimers['group-a'], timer)
            self.assertEqual(timer.interval(), 10 * 60 * 1000)
            self.assertIn('reschedule auto update job', lifecycleLog.call_args.args[0])

            subscriptions['group-a']['enabled'] = False

            manager.configureAutoUpdate('group-a')

            self.assertFalse(timer.isActive())
            self.assertIn('stop auto update job', lifecycleLog.call_args.args[0])

            manager.configureAutoUpdate('group-a')

            self.assertEqual(lifecycleLog.call_count, 3)

            subscriptions['group-a']['enabled'] = True

            manager.configureAutoUpdate('group-a')

            self.assertTrue(timer.isActive())
            self.assertIn('start auto update job', lifecycleLog.call_args.args[0])

        self.assertEqual(lifecycleLog.call_count, 4)

        manager.deleteLater()

    def testUnrelatedSubscriptionEditDoesNotRestartItsTimer(self):
        """Keep the real table edit path outside unchanged timer deadlines."""
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        timer = manager._autoUpdateTimers['group-a']

        QtTest.QTest.qWait(40)

        remainingBefore = timer.remainingTime()
        timerId = timer.timerId()

        def group(unique):
            """Return the exact in-memory group edited by the table."""
            value = subscriptions.get(unique)

            return (
                SubscriptionGroup.fromMapping(unique, value)
                if value is not None
                else None
            )

        def upsert(value):
            """Persist the edited group into the isolated test repository."""
            subscriptions[value.id] = value.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroup', side_effect=upsert),
        ):
            table = SubscriptionTableView(subscriptionManager=manager)
            table.appendNewItem(
                unique='group-a',
                remark='Renamed Group',
                webURL=subscriptions['group-a']['webURL'],
                enabled=True,
                autoupdate='Every 5 mins',
                proxy='',
                userAgent='',
                filter='',
                lastUpdated='',
            )

        self.assertEqual(subscriptions['group-a']['remark'], 'Renamed Group')
        self.assertIs(manager._autoUpdateTimers['group-a'], timer)
        self.assertEqual(timer.timerId(), timerId)
        self.assertLessEqual(timer.remainingTime(), remainingBefore + 5)
        table.deleteLater()
        manager.deleteLater()

    def testSubscriptionTableExposesPersistedSynchronizationStatus(self):
        """Present the existing sync state without inventing a UI-owned copy."""
        subscriptions = {
            'group-a': self._subscription(lastSyncStatus=''),
        }

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch(
                'Furious.Widget.SubscriptionTableView._',
                side_effect=lambda text: text,
            ),
        ):
            table = SubscriptionTableView()
            model = table.sourceModel
            statusColumn = table.ItemKey.index('lastSyncStatus')
            statusIndex = model.index(0, statusColumn)

            for persisted, expected in (
                ('', 'Never'),
                ('syncing', 'Updating...'),
                ('success', 'Updated'),
                ('error', 'Update Failed'),
                ('cancelled', 'Update Cancelled'),
                ('future-value', 'Never'),
            ):
                with self.subTest(persisted=persisted):
                    subscriptions['group-a']['lastSyncStatus'] = persisted

                    self.assertEqual(
                        model.data(statusIndex, QtCore.Qt.ItemDataRole.DisplayRole),
                        expected,
                    )

            self.assertFalse(
                model.flags(statusIndex) & QtCore.Qt.ItemFlag.ItemIsEditable
            )

            table.deleteLater()

        self.assertEqual(
            gettext('Sync Status', 'RU'),
            'Статус синхронизации',
        )
        self.assertEqual(gettext('Updating...', 'RU'), 'Обновление...')
        self.assertEqual(gettext('Updated', 'ZH'), '已更新')
        self.assertEqual(gettext('Update Failed', 'ZH'), '更新失败')
        self.assertEqual(gettext('Update Cancelled', 'ZH'), '更新已取消')
        self.assertEqual(gettext('Update Cancelled', 'RU'), 'Обновление отменено')
        self.assertEqual(gettext('Stop Updates', 'ZH'), '停止更新')
        self.assertEqual(gettext('Stop Updates', 'RU'), 'Остановить обновления')
        self.assertEqual(gettext('Usage / Expiry', 'RU'), 'Трафик / Срок')
        self.assertEqual(gettext('Usage / Expiry', 'ZH'), '用量 / 到期')

    def testSubscriptionTableShowsOptionalUsageAndExpiryMetadata(self):
        """Keep provider metadata compact and blank when it is unavailable."""
        subscriptions = {
            'group-a': self._subscription(
                subscriptionUpload=1024,
                subscriptionDownload=2048,
                subscriptionTotal=8192,
                subscriptionExpire=1893456000,
            ),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
            ),
        }

        with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
            table = SubscriptionTableView()
            model = table.sourceModel
            column = table.ItemKey.index('subscriptionInfo')

            self.assertEqual(
                model.data(model.index(0, column), QtCore.Qt.ItemDataRole.DisplayRole),
                '3 KiB / 8 KiB · 2030-01-01',
            )
            self.assertEqual(
                model.data(model.index(1, column), QtCore.Qt.ItemDataRole.DisplayRole),
                '',
            )
            self.assertFalse(
                model.flags(model.index(0, column)) & QtCore.Qt.ItemFlag.ItemIsEditable
            )
            table.deleteLater()

    def testSubscriptionStateNotificationRepaintsOnlyAffectedMetadataRow(self):
        """Resolve stable IDs at delivery and avoid a whole-table refresh."""
        subscriptions = {
            'group-a': self._subscription(),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
            ),
            'group-c': self._subscription(
                remark='Group C',
                webURL='https://invalid.test/c',
            ),
        }

        with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
            table = SubscriptionTableView()
            changes = []

            def changed(topLeft, bottomRight, _roles):
                """Capture one exact model repaint range."""
                changes.append(
                    (
                        (topLeft.row(), topLeft.column()),
                        (bottomRight.row(), bottomRight.column()),
                    )
                )

            table.sourceModel.dataChanged.connect(changed)

            with mock.patch.object(table, 'flushAll') as flushAll:
                table.refreshSubscriptionState(('group-b',))

            self.assertEqual(
                changes,
                [
                    (
                        (1, table.ItemKey.index('lastSyncStatus')),
                        (1, table.ItemKey.index('profiles')),
                    )
                ],
            )
            flushAll.assert_not_called()
            table.deleteLater()

    def testUpdateAllPublishesOneImmediateSyncingSnapshot(self):
        """Expose one metadata batch without publishing structural changes."""
        subscriptions = {
            'group-a': self._subscription(),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
            ),
        }
        manager = self._manager(subscriptions)
        snapshots = []
        stateChanges = []
        structuralChanges = []

        def group(unique):
            """Return one isolated persisted group."""
            value = subscriptions.get(unique)

            return (
                SubscriptionGroup.fromMapping(unique, value)
                if value is not None
                else None
            )

        def upsert(groups):
            """Persist one status batch into the isolated repository."""
            for value in groups:
                subscriptions[value.id] = value.toMapping()

        def stateChanged(uniques):
            """Capture the stable IDs and their state at notification time."""
            stateChanges.append(tuple(uniques))
            snapshots.append(
                tuple(
                    subscriptions[unique].get('lastSyncStatus', '')
                    for unique in ('group-a', 'group-b')
                )
            )

        manager.subscriptionStateChanged.connect(stateChanged)
        manager.subscriptionsChanged.connect(lambda: structuralChanges.append(True))

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroups', side_effect=upsert),
            mock.patch.object(Storage, 'persistSubscriptionGroups') as persist,
            mock.patch.object(manager, 'updateSubsByWebGET') as update,
        ):
            manager.updateSubs()

        self.assertEqual(snapshots, [('syncing', 'syncing')])
        self.assertEqual(stateChanges, [('group-a', 'group-b')])
        self.assertEqual(structuralChanges, [])
        persist.assert_called_once_with()
        self.assertEqual(update.call_count, 2)
        self.assertEqual(
            {call.kwargs['unique'] for call in update.call_args_list},
            {'group-a', 'group-b'},
        )

        manager.deleteLater()

    def testTargetedUpdatePublishesImmediateSyncingState(self):
        """Publish one narrow targeted state before network I/O."""
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        group = SubscriptionGroup.fromMapping('group-a', subscriptions['group-a'])
        snapshots = []
        stateChanges = []
        structuralChanges = []

        def stateChanged(uniques):
            """Capture the target and persisted state before network I/O."""
            stateChanges.append(tuple(uniques))
            snapshots.append(group.lastSyncStatus)

        manager.subscriptionStateChanged.connect(stateChanged)
        manager.subscriptionsChanged.connect(lambda: structuralChanges.append(True))

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', return_value=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroups'),
            mock.patch.object(Storage, 'persistSubscriptionGroups') as persist,
            mock.patch.object(manager, 'updateSubsByWebGET') as update,
        ):
            manager.updateSubsByUnique('group-a')

        self.assertEqual(snapshots, ['syncing'])
        self.assertEqual(stateChanges, [('group-a',)])
        self.assertEqual(structuralChanges, [])
        persist.assert_called_once_with()
        update.assert_called_once()

        manager.deleteLater()

    def testTargetedPolicyChangeDoesNotDisturbOtherSubscriptions(self):
        """Reconcile only the edited subscription's schedule."""
        subscriptions = {
            'group-a': self._subscription(),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
                autoupdate='Every 10 mins',
            ),
        }
        manager = self._manager(subscriptions)
        groupATimer = manager._autoUpdateTimers['group-a']
        groupBTimer = manager._autoUpdateTimers['group-b']
        groupBTimerId = groupBTimer.timerId()

        QtTest.QTest.qWait(40)

        groupBRemainingBefore = groupBTimer.remainingTime()
        subscriptions['group-a']['autoupdate'] = 'Every 10 mins'

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.configureAutoUpdate('group-a')

        self.assertIs(manager._autoUpdateTimers['group-a'], groupATimer)
        self.assertEqual(groupATimer.interval(), 10 * 60 * 1000)
        self.assertIs(manager._autoUpdateTimers['group-b'], groupBTimer)
        self.assertEqual(groupBTimer.timerId(), groupBTimerId)
        self.assertLessEqual(groupBTimer.remainingTime(), groupBRemainingBefore + 5)
        self.assertEqual(len(manager._autoUpdateTimers), 2)
        manager.deleteLater()

    def testRemovingSubscriptionDestroysOnlyItsTimerAndCancelsItsReply(self):
        """Release one removed subscription without disturbing its sibling."""
        subscriptions = {
            'group-a': self._subscription(),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
            ),
        }
        manager = self._manager(subscriptions)
        groupATimer = manager._autoUpdateTimers['group-a']
        groupBTimer = manager._autoUpdateTimers['group-b']
        groupBTimerId = groupBTimer.timerId()

        groupAReply = _AbortableReply()
        groupBReply = _AbortableReply()
        destroyed = []
        groupATimer.destroyed.connect(lambda *_args: destroyed.append(True))

        manager._activeReplies.update(
            {groupAReply: groupAReply, groupBReply: groupBReply}
        )
        manager._replySubscriptions.update(
            {groupAReply: 'group-a', groupBReply: 'group-b'}
        )

        subscriptions.pop('group-a')

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.removeAutoUpdate('group-a')

        self.assertTrue(groupAReply.aborted)
        self.assertFalse(groupBReply.aborted)
        self.assertNotIn('group-a', manager._autoUpdateTimers)
        self.assertIs(manager._autoUpdateTimers['group-b'], groupBTimer)
        self.assertEqual(groupBTimer.timerId(), groupBTimerId)
        self.assertTrue(groupBTimer.isActive())

        processQtEvents()

        self.assertEqual(destroyed, [True])
        self.assertFalse(isValid(groupATimer))

        manager._activeReplies.clear()
        manager._replySubscriptions.clear()
        manager.deleteLater()

    def testUpdateSelectedUsesOneOrderedCanonicalBatchCall(self):
        """Keep a real selected-update click narrow and event-loop responsive."""
        subscriptions = {
            'group-a': self._subscription(),
            'group-b': self._subscription(
                remark='Group B',
                webURL='https://invalid.test/b',
            ),
            'group-c': self._subscription(
                remark='Group C',
                webURL='https://invalid.test/c',
            ),
        }

        def group(unique):
            """Return one isolated persisted group."""
            value = subscriptions.get(unique)

            return (
                SubscriptionGroup.fromMapping(unique, value)
                if value is not None
                else None
            )

        def upsert(groups):
            """Persist one status batch into the isolated repository."""
            for value in groups:
                subscriptions[value.id] = value.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroups', side_effect=upsert),
            mock.patch.object(Storage, 'persistSubscriptionGroups'),
        ):
            manager = SubscriptionManager()
            stateChanges = []
            structuralChanges = []

            def updateSubscriptions(uniques, _httpProxy, **kwargs):
                """Cross the production wrapper boundary into the real manager."""
                kwargs.pop('parent', None)
                manager.updateSubscriptions(uniques, **kwargs)

            serverTable = SimpleNamespace(subsManager=manager)
            serverTable.updateSubscriptions = mock.Mock(side_effect=updateSubscriptions)
            page = SubscriptionPage(serverTable)
            selection = page.table.selectionModel()
            flags = (
                QtCore.QItemSelectionModel.SelectionFlag.Select
                | QtCore.QItemSelectionModel.SelectionFlag.Rows
            )

            selection.select(page.table.sourceModel.index(0, 0), flags)
            selection.select(page.table.sourceModel.index(2, 0), flags)

            manager.subscriptionStateChanged.connect(
                lambda uniques: stateChanges.append(tuple(uniques))
            )
            manager.subscriptionsChanged.connect(lambda: structuralChanges.append(True))

            page.show()
            processQtEvents(1)

            handled = []
            QtCore.QTimer.singleShot(0, lambda: handled.append(True))

            with mock.patch.object(manager, 'updateSubsByWebGET') as update:
                QtTest.QTest.mouseClick(
                    page.updateSelectedButton,
                    QtCore.Qt.MouseButton.LeftButton,
                )

            processQtEvents(1)

            serverTable.updateSubscriptions.assert_called_once_with(
                ('group-a', 'group-c'),
                None,
                showMessageBox=True,
                parent=page,
            )
            self.assertEqual(stateChanges, [('group-a', 'group-c')])
            self.assertEqual(structuralChanges, [])
            self.assertEqual(update.call_count, 2)
            self.assertEqual(handled, [True])

            page.deleteLater()
            manager.deleteLater()

        processQtEvents()

    def testStopUpdatesClickPreservesCommitsSchedulesAndRejectsLateWork(self):
        """Cancel a partial batch through real Qt input and allow another update."""
        subscriptions = {
            unique: self._subscription(remark=unique)
            for unique in ('group-a', 'group-b')
        }

        def group(unique):
            return SubscriptionGroup.fromMapping(unique, subscriptions[unique])

        def upsert(groups):
            for value in groups:
                subscriptions[value.id] = value.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroups', side_effect=upsert),
            mock.patch.object(Storage, 'persistSubscriptionGroups'),
        ):
            manager = SubscriptionManager()
            page = SubscriptionPage(SimpleNamespace(subsManager=manager))

            replies = []
            contexts = []
            completed = []
            manager.updateCompleted.connect(completed.append)

            timerIds = {
                key: timer.timerId() for key, timer in manager._autoUpdateTimers.items()
            }

            def request(**context):
                reply = _Reply()
                replies.append(reply)
                contexts.append(context)
                manager._activeReplies[reply] = reply
                manager._replySubscriptions[reply] = context['unique']

            try:
                page.show()
                processQtEvents()

                self.assertFalse(page.stopUpdatesButton.isEnabled())

                with mock.patch.object(
                    manager, 'updateSubsByWebGET', side_effect=request
                ):
                    manager.updateSubscriptions(('group-a', 'group-b'))

                    self.assertTrue(page.stopUpdatesButton.isEnabled())

                    subscriptions['group-a']['lastSyncStatus'] = 'success'
                    subscriptions['group-a']['lastUpdated'] = 'preserved timestamp'

                    manager._finishOperation(
                        contexts[0], successful=contexts[0], structural=True
                    )
                    manager._releaseFinishedReply(replies[0])

                    QtTest.QTest.mouseClick(
                        page.stopUpdatesButton, QtCore.Qt.MouseButton.LeftButton
                    )
                    processQtEvents()

                    self.assertFalse(page.stopUpdatesButton.isEnabled())
                    self.assertEqual(
                        subscriptions['group-a']['lastSyncStatus'], 'success'
                    )
                    self.assertEqual(
                        subscriptions['group-a']['lastUpdated'], 'preserved timestamp'
                    )
                    self.assertEqual(
                        subscriptions['group-b']['lastSyncStatus'], 'cancelled'
                    )

                    self.assertFalse(replies[1].isOpen())
                    self.assertEqual(manager._batches, {})
                    self.assertEqual(len(completed), 1)
                    self.assertEqual(completed[0].successful, (contexts[0],))
                    self.assertEqual(completed[0].failed, ())
                    self.assertFalse(manager._isCurrentRequest(contexts[1]))

                    self.assertEqual(
                        timerIds,
                        {
                            key: timer.timerId()
                            for key, timer in manager._autoUpdateTimers.items()
                        },
                    )

                    with mock.patch.object(
                        manager, '_startImportPreparation'
                    ) as prepare:
                        manager.successCallback(replies[1], **contexts[1])

                        prepare.assert_not_called()

                    manager.updateSubscriptions(('group-b',))

                    self.assertTrue(page.stopUpdatesButton.isEnabled())
                    self.assertTrue(manager._isCurrentRequest(contexts[2]))

                    manager.stopUpdates()

                    self.assertEqual(len(completed), 1)
            finally:
                manager.shutdown()

                for reply in replies:
                    manager._releaseFinishedReply(reply)
                    reply.deleteLater()

                page.deleteLater()
                manager.deleteLater()
                processQtEvents()

    def testStopCompletionCanImmediatelyStartANewUpdate(self):
        """A synchronous abort observer must not lose the next generation's status."""
        subscriptions = {'group-a': self._subscription(lastSyncStatus='syncing')}
        manager = self._manager()
        context = {'unique': 'group-a', 'batchId': 1, 'requestVersion': 1}
        manager._nextBatchId = 1
        manager._requestVersions['group-a'] = 1
        manager._batches[1] = _SubscriptionBatchState(
            {('group-a', 1)}, False, [{'unique': 'completed-group'}], []
        )
        reply = mock.Mock()
        manager._activeReplies[reply] = reply
        manager._replySubscriptions[reply] = 'group-a'

        def abort():
            manager._releaseFinishedReply(reply)
            manager._finishOperation(context)

        reply.abort.side_effect = abort
        manager.updateCompleted.connect(
            lambda _batch: manager.updateSubsByUnique('group-a')
        )

        def upsert(groups):
            for group in groups:
                subscriptions[group.id] = group.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(
                Storage,
                'SubscriptionGroup',
                side_effect=lambda unique: SubscriptionGroup.fromMapping(
                    unique, subscriptions[unique]
                ),
            ),
            mock.patch.object(Storage, 'upsertSubscriptionGroups', side_effect=upsert),
            mock.patch.object(Storage, 'persistSubscriptionGroups'),
            mock.patch.object(manager, 'updateSubsByWebGET') as request,
        ):
            try:
                manager.stopUpdates()
                request.assert_called_once()

                self.assertTrue(manager._isCurrentRequest(request.call_args.kwargs))
                self.assertEqual(subscriptions['group-a']['lastSyncStatus'], 'syncing')
                self.assertEqual(len(manager._batches), 1)
            finally:
                manager.shutdown()
                manager.deleteLater()

                processQtEvents()

    def testStopUpdatesRetainsRunningPreparationUntilItsLateResultArrives(self):
        """Logical stop releases the batch, while the pool retains executing work."""
        manager = self._manager()
        started = threading.Event()
        release = threading.Event()

        context = {'unique': 'group-a', 'batchId': 1, 'requestVersion': 1}
        subscriptions = {'group-a': self._subscription()}

        manager._requestVersions['group-a'] = 1
        context['webURL'] = subscriptions['group-a']['webURL']
        manager._batches[1] = _SubscriptionBatchState({('group-a', 1)}, True, [], [])
        manager._handleImportedResult = mock.Mock()

        completed = []
        manager.updateCompleted.connect(completed.append)

        def work(_isCancelled):
            started.set()
            release.wait(3)

            return object()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'persistSubscriptionGroups'),
        ):
            try:
                manager._startPreparationJob('import', context, work)
                self.assertTrue(started.wait(2))

                manager.stopUpdates()

                self.assertEqual(manager._batches, {})
                self.assertEqual(len(manager._preparationJobs), 1)
                self.assertEqual(manager._preparationPool.activeThreadCount(), 1)

                release.set()
                self.assertTrue(waitFor(lambda: not manager._preparationJobs))

                manager._handleImportedResult.assert_not_called()
                self.assertEqual(completed, [])
            finally:
                release.set()
                manager.shutdown()
                manager.deleteLater()

                processQtEvents()

    def testLargePreparationRunsOffGuiThreadAndKeepsEventLoopResponsive(self):
        """Keep unrelated Qt delivery responsive while payload work is gated."""
        subscriptions = {'group-a': self._subscription(autoupdate='Never')}
        started = threading.Event()
        release = threading.Event()
        workerThreads = []

        class Registry:
            """Declare this deterministic test importer worker-safe."""

            @staticmethod
            def subscriptionDecoderWorkerSafe(_decoderId):
                return True

        class Importer:
            """Gate representative expensive parsing in the pool."""

            registry = Registry()

            @staticmethod
            def importPayload(_data, _source, **_kwargs):
                workerThreads.append(threading.get_ident())
                started.set()
                release.wait(2)

                return None

        def group(unique):
            return SubscriptionGroup.fromMapping(unique, subscriptions[unique])

        def upsert(groups):
            for value in groups:
                subscriptions[value.id] = value.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroups', side_effect=upsert),
            mock.patch.object(
                Storage,
                'upsertSubscriptionGroup',
                side_effect=lambda value: upsert((value,)),
            ),
            mock.patch.object(Storage, 'persistSubscriptionGroups') as persist,
        ):
            manager = SubscriptionManager()
            manager.importer = Importer()
            requests = []
            manager.updateSubsByWebGET = lambda **context: requests.append(context)
            completed = []
            manager.updateCompleted.connect(completed.append)

            manager.updateSubsByUnique('group-a')
            manager.successCallback(_Reply(b'large payload'), **requests[0])

            self.assertTrue(started.wait(2))

            handled = []

            QtCore.QTimer.singleShot(0, lambda: handled.append(True))
            processQtEvents(1)

            self.assertEqual(handled, [True])
            self.assertNotEqual(workerThreads, [threading.get_ident()])

            release.set()
            deadline = time.monotonic() + 3

            while not completed and time.monotonic() < deadline:
                QtTest.QTest.qWait(10)

            self.assertEqual(len(completed), 1)
            self.assertEqual(
                completed[0].failed[0]['error'],
                'UnsupportedSubscriptionFormat',
            )
            self.assertEqual(persist.call_count, 2)

            manager.shutdown()
            manager.deleteLater()

        processQtEvents()

    def testParsingResultIsDiscardedAfterReupdateDeleteOrSourceEdit(self):
        """Reject worker results after every source-generation invalidation path."""
        base = self._subscription(autoupdate='Never')

        for mutation in ('reupdate', 'delete', 'edit'):
            with self.subTest(mutation=mutation):
                subscriptions = {'group-a': dict(base)}
                manager = self._manager(subscriptions)
                manager._requestVersions['group-a'] = 1
                context = {
                    'unique': 'group-a',
                    'webURL': base['webURL'],
                    'requestVersion': 1,
                    'requestSignature': manager._requestSignature(base),
                }
                manager._handleImportedResult = mock.Mock()

                if mutation == 'reupdate':
                    manager._nextRequestVersion('group-a')
                elif mutation == 'delete':
                    subscriptions.clear()
                else:
                    subscriptions['group-a']['filter'] = 'changed'

                with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
                    self.assertFalse(manager._isCurrentRequest(context))

                manager._handleImportedResult.assert_not_called()
                manager.shutdown()
                manager.deleteLater()

        processQtEvents()

    def testPartialBatchFailuresRemainIsolatedAndPublishOnce(self):
        """Commit successful members and report failed members as one batch."""
        subscriptions = {
            unique: self._subscription(
                remark=unique,
                webURL=f'https://invalid.test/{unique}',
                autoupdate='Never',
            )
            for unique in ('group-a', 'group-b', 'group-c', 'group-d')
        }
        manager = self._manager(subscriptions)
        contexts = []

        for unique, subscription in subscriptions.items():
            manager._requestVersions[unique] = 1
            contexts.append(
                {
                    'unique': unique,
                    'remark': subscription['remark'],
                    'webURL': subscription['webURL'],
                    'requestVersion': 1,
                    'requestSignature': manager._requestSignature(subscription),
                    'batchId': 7,
                }
            )

        manager._batches[7] = _SubscriptionBatchState(
            {(context['unique'], 1) for context in contexts},
            True,
            [],
            [],
        )

        completed = []
        structural = []
        manager.updateCompleted.connect(completed.append)
        manager.subscriptionsChanged.connect(lambda: structural.append(True))

        def group(unique):
            return SubscriptionGroup.fromMapping(unique, subscriptions[unique])

        def upsert(value):
            subscriptions[value.id] = value.toMapping()

        with (
            mock.patch.object(Storage, 'UserSubs', return_value=subscriptions),
            mock.patch.object(Storage, 'SubscriptionGroup', side_effect=group),
            mock.patch.object(Storage, 'upsertSubscriptionGroup', side_effect=upsert),
            mock.patch.object(Storage, 'persistSubscriptionGroups') as persist,
        ):
            manager._finishOperation(
                contexts[0], successful=contexts[0], structural=True
            )
            manager._failOperation(contexts[1], 'decode failed')
            manager._failOperation(contexts[2], 'network failed')
            manager._finishOperation(
                contexts[3], successful=contexts[3], structural=True
            )

        self.assertEqual(len(completed), 1)
        self.assertEqual(
            [value['unique'] for value in completed[0].successful],
            ['group-a', 'group-d'],
        )
        self.assertEqual(
            [value['unique'] for value in completed[0].failed],
            ['group-b', 'group-c'],
        )
        self.assertEqual(structural, [True])
        persist.assert_called_once_with()

        manager.shutdown()
        manager.deleteLater()
        processQtEvents()

    def testShutdownCancelsAndWaitsForRunningPreparation(self):
        """Prevent an active worker from delivering any post-shutdown commit."""
        subscriptions = {'group-a': self._subscription(autoupdate='Never')}
        manager = self._manager(subscriptions)
        manager._requestVersions['group-a'] = 1
        context = {
            'unique': 'group-a',
            'webURL': subscriptions['group-a']['webURL'],
            'requestVersion': 1,
            'requestSignature': manager._requestSignature(subscriptions['group-a']),
        }
        started = threading.Event()
        stopped = threading.Event()

        def work(isCancelled):
            started.set()

            while not isCancelled():
                stopped.wait(0.005)

            stopped.set()

        with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
            manager._startPreparationJob('probe', context, work)
            self.assertTrue(started.wait(2))
            manager.shutdown()

        self.assertTrue(stopped.is_set())
        self.assertEqual(manager._preparationJobs, {})
        self.assertEqual(manager._preparationPool.activeThreadCount(), 0)

        manager.deleteLater()
        processQtEvents()

    def testSlowShutdownWarnsAndRetainsWorkersUntilTheyFinish(self):
        """Keep synchronous ownership after the warning threshold expires."""
        manager = self._manager({})
        manager.ShutdownWarningMilliseconds = 1
        manager._preparationPool.setMaxThreadCount(1)

        started = threading.Event()
        release = threading.Event()
        queuedStarted = threading.Event()
        manager._handleImportedResult = mock.Mock()

        def work(_isCancelled):
            started.set()
            # Bound the fixture even if the expected diagnostic never arrives.
            release.wait(5)
            return object()

        def afterWarning(*_args):
            self.assertTrue(manager._preparationJobs)
            self.assertTrue(isValid(manager._preparationRelay))
            self.assertTrue(
                all(job.cancelled.is_set() for job in manager._preparationJobs.values())
            )

            release.set()

        try:
            manager._startPreparationJob('import', {}, work)
            self.assertTrue(started.wait(2))

            manager._startPreparationJob('import', {}, lambda _: queuedStarted.set())

            with mock.patch(
                'Furious.Service.SubscriptionManager.logger.warning',
                side_effect=afterWarning,
            ) as warning:
                manager.shutdown()
                manager.shutdown()

                warning.assert_called_once()

            processQtEvents()

            self.assertFalse(queuedStarted.is_set())
            self.assertEqual(manager._preparationPool.activeThreadCount(), 0)
            self.assertEqual(manager._preparationJobs, {})
            self.assertEqual(manager._preparationPayloads, {})
            manager._handleImportedResult.assert_not_called()
        finally:
            release.set()
            manager.shutdown()
            manager.deleteLater()

            processQtEvents()

    def testShutdownRejectsNewWorkAndVersionlessCompletions(self):
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        manager.shutdown()
        with mock.patch.object(Storage, 'persistSubscriptionGroups') as persist:
            self.assertFalse(manager._isCurrentRequest({}))
            self.assertIsNone(manager._startPreparationJob('import', {}, mock.Mock()))
            with mock.patch.object(manager, 'webGET') as request:
                manager.updateSubsByWebGET(webURL='https://invalid.test')
                manager.updateSubscriptions(('group-a',))
                request.assert_not_called()
            with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
                manager.refreshAutoUpdates()
            self.assertFalse(manager._autoUpdateTimers['group-a'].isActive())
            persist.assert_not_called()
        manager.deleteLater()
        processQtEvents()

    def testPageNavigationIsPresentationOnlyForAutoUpdateScheduler(self):
        """Keep page show/hide cycles outside scheduler policy ownership."""
        subscriptions = {'group-a': self._subscription()}

        with mock.patch.object(Storage, 'UserSubs', return_value=subscriptions):
            manager = SubscriptionManager()
            timer = manager._autoUpdateTimers['group-a']
            timerId = timer.timerId()

            manager.refreshAutoUpdates = mock.Mock(
                side_effect=AssertionError(
                    'page presentation must not reconcile background schedules'
                )
            )

            serverTable = SimpleNamespace(subsManager=manager)
            page = SubscriptionPage(serverTable)
            placeholder = QtWidgets.QWidget()

            stack = QtWidgets.QStackedWidget()
            stack.addWidget(page)
            stack.addWidget(placeholder)
            stack.show()

            for _index in range(20):
                stack.setCurrentWidget(placeholder)
                processQtEvents(1)
                stack.setCurrentWidget(page)
                processQtEvents(1)

            self.assertIs(page.table.subsManager, manager)
            self.assertIs(manager._autoUpdateTimers['group-a'], timer)
            self.assertEqual(timer.timerId(), timerId)
            self.assertEqual(len(manager._autoUpdateTimers), 1)
            manager.refreshAutoUpdates.assert_not_called()

            stack.deleteLater()
            manager.deleteLater()

        processQtEvents()

    def testManagerDestructionDestroysItsServiceOwnedTimers(self):
        """Let QObject parent ownership release all scheduler resources."""
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        timer = manager._autoUpdateTimers['group-a']
        destroyed = []
        manager.destroyed.connect(lambda *_args: destroyed.append('manager'))
        timer.destroyed.connect(lambda *_args: destroyed.append('timer'))

        manager.deleteLater()
        processQtEvents()

        self.assertFalse(isValid(manager))
        self.assertFalse(isValid(timer))
        self.assertCountEqual(destroyed, ('manager', 'timer'))

    def testMissingSubscriptionRemovalPrunesTimerDuringFullReconciliation(self):
        """Retain removal behavior while unchanged groups remain untouched."""
        subscriptions = {'group-a': self._subscription()}
        manager = self._manager(subscriptions)
        timer = manager._autoUpdateTimers['group-a']

        subscriptions.clear()

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value=subscriptions,
        ):
            manager.refreshAutoUpdates()

        self.assertEqual(manager._autoUpdateTimers, {})
        self.assertFalse(timer.isActive())

        manager.deleteLater()

    def testDeletedSubscriptionVersionIsPrunedAfterItsReplyFinishes(self):
        """Release stale-request bookkeeping after the last exact owner ends."""
        manager = self._manager()
        reply = _AbortableReply()
        manager._requestVersions['deleted-group'] = 4
        manager._activeReplies[reply] = reply
        manager._replySubscriptions[reply] = 'deleted-group'

        with mock.patch(
            'Furious.Service.SubscriptionManager.Storage.UserSubs',
            return_value={},
        ):
            manager._pruneRequestVersion('deleted-group')
            self.assertIn('deleted-group', manager._requestVersions)

            manager._activeReplies.pop(reply)
            manager._replySubscriptions.pop(reply)
            manager._pruneRequestVersion('deleted-group')

        self.assertNotIn('deleted-group', manager._requestVersions)

        manager.deleteLater()
