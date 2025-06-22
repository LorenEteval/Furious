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

from __future__ import annotations

from Furious.Utility.Constants import *
from Furious.Utility.AppSettings import *

from typing import Union

import functools

__all___ = [
    'AS_UserActivatedItemIndex',
    'AS_UserServers',
    'AS_UserSubscription',
    'AS_UserTUNSettings',
    'connectedHttpProxyEndpoint',
    'connectedServerRemark',
]


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


def _userTUNSettingsData() -> dict[str, str]:
    try:
        return APP().userTUNSettings.data()
    except Exception:
        # Any non-exit exceptions

        return {}


AS_UserActivatedItemIndex = functools.partial(_activatedItemIndex)
AS_UserServers = functools.partial(_userServersData)
AS_UserSubscription = functools.partial(_userSubscriptionData)
AS_UserTUNSettings = functools.partial(_userTUNSettingsData)


def connectedHttpProxyEndpoint() -> Union[str, None]:
    try:
        if APP().isSystemTrayConnected():
            index = AS_UserActivatedItemIndex()

            if index >= 0:
                return AS_UserServers()[index].httpProxyEndpoint()
            else:
                # Should not reach here
                return None
        else:
            return None
    except Exception:
        # Any non-exit exceptions

        return None


def connectedServerRemark() -> str:
    try:
        if APP().isSystemTrayConnected():
            index = AS_UserActivatedItemIndex()

            if index >= 0:
                return f'{index + 1} - ' + AS_UserServers()[index].getExtras('remark')
            else:
                # Should not reach here
                return ''
        else:
            return ''
    except Exception:
        # Any non-exit exceptions

        return ''
