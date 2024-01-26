from __future__ import annotations

from Furious.Utility.Constants import *
from Furious.Utility.AppSettings import *

import functools

__all___ = ['AS_UserActivatedItemIndex', 'AS_UserServers', 'AS_UserSubscription']


def _activatedItemIndex() -> int:
    try:
        return int(AppSettings.get('ActivatedItemIndex'))
    except Exception:
        # Any non-exit exceptions

        return -1


def _userServersData() -> list:
    try:
        return APP().userServers.data()
    except Exception:
        # Any non-exit exceptions

        return []


def _userSubscriptionData() -> dict[str, dict]:
    try:
        return APP().userSubs.data()
    except Exception:
        # Any non-exit exceptions

        return {}


AS_UserActivatedItemIndex = functools.partial(_activatedItemIndex)
AS_UserServers = functools.partial(_userServersData)
AS_UserSubscription = functools.partial(_userSubscriptionData)
