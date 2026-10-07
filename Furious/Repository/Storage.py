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
from Furious.Repository.SingTUNSettings import UserSingTUNSettings
from Furious.Models.SingTUN import prepareSingTUNSettings

from PySide6 import QtCore

from typing import Union

import functools
import copy
import json

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
    def _UserSingTUNSettingsStorage() -> UserSingTUNSettings:
        """Return the single sing-tun customization repository."""
        assert APP() is not None

        return UserSingTUNSettings()

    @staticmethod
    def UserSingTUNSettings() -> dict:
        """Expose the compatibility live view of sing-tun settings."""
        return Storage._UserSingTUNSettingsStorage().data()

    @staticmethod
    def replaceSingTUNSettings(singSettings):
        """Commit sing-tun's validated document, then report its flush result."""

        prepareSingTUNSettings(singSettings)

        # Serialization is a fallible pre-commit stage.
        json.dumps(singSettings, allow_nan=False)

        singCandidate = copy.deepcopy(singSettings)

        sing = Storage._UserSingTUNSettingsStorage()
        sing.data().clear()
        sing.data().update(singCandidate)

        sing.sync()

        settings = QtCore.QSettings()
        settings.sync()

        if settings.status() != QtCore.QSettings.Status.NoError:
            raise OSError(
                'sing-tun settings committed in memory, but could not be flushed to disk'
            )

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
    def setUserServersFavorite(profileIds, favorite: bool) -> list[str]:
        """Commit favorite metadata through the server repository owner."""
        return Storage._UserServersStorage().setProfilesFavorite(profileIds, favorite)

    @staticmethod
    def moveUserServers(profileIds, visibleProfileIds, position: str) -> bool:
        """Move selected servers within the caller's visible repository scope."""
        return Storage._UserServersStorage().moveProfiles(
            profileIds,
            visibleProfileIds,
            position,
        )

    @staticmethod
    def moveUserServersToSubscription(profileIds, unique: str) -> bool:
        """Move servers to a subscription group as locally managed entries."""
        if unique and Storage.SubscriptionGroup(unique) is None:
            return False

        return Storage._UserServersStorage().moveProfilesToSubscription(
            profileIds, unique
        )

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
    def moveSubscriptionGroups(groupIds, position: str) -> bool:
        """Move selected subscription groups in their persisted display order."""
        return Storage._UserSubsStorage().moveGroups(groupIds, position)

    @staticmethod
    def upsertSubscriptionGroup(group: SubscriptionGroup):
        """Persist one subscription group through the shared repository."""
        Storage._UserSubsStorage().upsertGroup(group)

    @staticmethod
    def upsertSubscriptionGroups(groups):
        """Mutate a validated subscription-group batch in one commit."""
        Storage._UserSubsStorage().upsertGroups(groups)

    @staticmethod
    def persistSubscriptionGroups():
        """Serialize the current subscription repository once."""
        Storage._UserSubsStorage().sync()

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

                return prefix + profile.itemRemark
            except Exception:
                # Any non-exit exceptions

                return ''
