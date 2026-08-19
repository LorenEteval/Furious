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
from Furious.Models import ServerProfile
from Furious.Repository.Routings import UserRoutings
from Furious.Repository.Servers import UserServers
from Furious.Repository.Subscriptions import SubscriptionGroup, UserSubs
from Furious.Repository.TunSettings import UserTUNSettings

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
    def UserServers() -> list[ServerProfile]:
        """Return the user servers value."""
        return Storage._UserServersStorage().data()

    @staticmethod
    def UserSubs() -> dict[str, dict]:
        """Return the user subs value."""
        return Storage._UserSubsStorage().data()

    @staticmethod
    def SubscriptionGroups() -> tuple[SubscriptionGroup, ...]:
        """Return first-class subscription groups in their display order."""
        return Storage._UserSubsStorage().groups()

    @staticmethod
    def SubscriptionGroup(unique: str) -> SubscriptionGroup | None:
        """Return one subscription group by stable ID."""
        return Storage._UserSubsStorage().group(unique)

    @staticmethod
    def upsertSubscriptionGroup(group: SubscriptionGroup):
        """Persist one subscription group through the shared repository."""
        Storage._UserSubsStorage().upsertGroup(group)

    @staticmethod
    def removeSubscriptionGroup(unique: str) -> SubscriptionGroup | None:
        """Remove one subscription group through the shared repository."""
        return Storage._UserSubsStorage().removeGroup(unique)

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
                controller = AppConnectionController()

                profile = controller.activeProfile

                if controller.isConnected() and isinstance(profile, ServerProfile):
                    return profile.httpProxy()

                return None
            except Exception:
                # Any non-exit exceptions

                return None

        @staticmethod
        def UserServerRemark() -> Union[str, None]:
            """Return the user server remark value."""
            try:
                controller = AppConnectionController()

                profile = controller.activeProfile

                if not controller.isConnected() or not isinstance(
                    profile, ServerProfile
                ):
                    return ''

                index = next(
                    (
                        index
                        for index, server in enumerate(Storage.UserServers())
                        if server is profile
                    ),
                    -1,
                )
                prefix = f'{index + 1} - ' if index >= 0 else ''

                return prefix + configuration.itemRemark
            except Exception:
                # Any non-exit exceptions

                return ''
