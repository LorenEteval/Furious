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

"""Provide cached access to persisted user data collections."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library.UserServers import UserServers
from Furious.Library.UserSubs import UserSubs
from Furious.Library.UserRoutings import UserRoutings
from Furious.Library.UserTUNSettings import UserTUNSettings

from typing import Union

import functools

__all__ = ['Storage']


class Storage:
    """Provide cached access to persisted user configuration collections."""

    @staticmethod
    @functools.lru_cache(None)
    def _UserServersStorage() -> UserServers:
        """Return the application-lifetime user-server storage owner."""
        assert APP() is not None

        return UserServers()

    @staticmethod
    @functools.lru_cache(None)
    def _UserSubsStorage() -> UserSubs:
        """Return the application-lifetime subscription storage owner."""
        assert APP() is not None

        return UserSubs()

    @staticmethod
    @functools.lru_cache(None)
    def _UserTUNSettingsStorage() -> UserTUNSettings:
        """Return the application-lifetime TUN-settings storage owner."""
        assert APP() is not None

        return UserTUNSettings()

    @staticmethod
    @functools.lru_cache(None)
    def _UserRoutingsStorage() -> UserRoutings:
        """Return the application-lifetime custom-routing storage owner."""
        assert APP() is not None

        return UserRoutings()

    @staticmethod
    def UserActivatedItemIndex() -> int:
        """Return the user activated item index value."""
        try:
            return int(AppSettings.get('ActivatedItemIndex'))
        except Exception:
            # Any non-exit exceptions

            return -1

    @staticmethod
    def UserServers() -> list[ConfigFactory]:
        """Return the user servers value."""
        return Storage._UserServersStorage().data()

    @staticmethod
    def UserSubs() -> dict[str, dict]:
        """Return the user subs value."""
        return Storage._UserSubsStorage().data()

    @staticmethod
    def UserTUNSettings() -> dict[str, str]:
        """Return the user TUN settings value."""
        return Storage._UserTUNSettingsStorage().data()

    @staticmethod
    def UserRoutings() -> dict[str, dict]:
        """Return the user routings value."""
        return Storage._UserRoutingsStorage().data()

    class Extras:
        """Derive display and proxy values from the active server."""

        @staticmethod
        @forceToLocalhostIfPossible()
        def UserHttpProxy() -> Union[str, None]:
            """Return the user HTTP proxy value."""
            try:
                if APP().isSystemTrayConnected():
                    index, servers = (
                        Storage.UserActivatedItemIndex(),
                        Storage.UserServers(),
                    )

                    if index >= 0:
                        return servers[index].httpProxy()
                    else:
                        # Should not reach here
                        return None
                else:
                    return None
            except Exception:
                # Any non-exit exceptions

                return None

        @staticmethod
        def UserServerRemark() -> Union[str, None]:
            """Return the user server remark value."""
            try:
                if APP().isSystemTrayConnected():
                    index, servers = (
                        Storage.UserActivatedItemIndex(),
                        Storage.UserServers(),
                    )

                    if index >= 0:
                        return f'{index + 1} - ' + servers[index].getExtras('remark')
                    else:
                        # Should not reach here
                        return ''
                else:
                    return ''
            except Exception:
                # Any non-exit exceptions

                return ''
