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

from types import SimpleNamespace
from unittest import TestCase, mock

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6 import QtCore, QtTest, QtWidgets

from shiboken6 import isValid

from Furious.Repository import Storage
from Furious.Repository.Subscriptions import SubscriptionGroup
from Furious.Service.SubscriptionManager import SubscriptionManager
from Furious.Window.SubscriptionPage import SubscriptionPage
from Furious.Widget.SubscriptionTableView import SubscriptionTableView
from tests.support import application, processQtEvents


class _Payload:
    """Expose the minimal QNetworkReply byte-array contract."""

    def __init__(self, value):
        self._value = value

    def data(self):
        return self._value


class _Reply:
    """Provide deterministic response data and failure diagnostics."""

    def __init__(self, value=b'', error='request failed'):
        self._value = value
        self._error = error

    def readAll(self):
        return _Payload(self._value)

    def errorString(self):
        return self._error


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
                _Reply(b'payload'),
                unique='group-a',
                remark='Group A',
                webURL='https://invalid.test/subscription',
                successArgs=successful,
                failureArgs=failed,
            )

        self.assertEqual(len(successful), 1)
        self.assertEqual(successful[0]['profiles'], (profile,))
        self.assertEqual(successful[0]['decoderId'], 'decoder')
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
        manager.updateCompleted.connect(completed.append)
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
