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

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Library.UserServers import UserServers
from Furious.Library.UserSubs import UserSubs
from Furious.Library.UserTUNSettings import UserTUNSettings

from typing import Union

import functools

__all__ = ['Storage']


class Storage:
    @staticmethod
    def UserActivatedItemIndex() -> int:
        try:
            return int(AppSettings.get('ActivatedItemIndex'))
        except Exception:
            # Any non-exit exceptions

            return -1

    @staticmethod
    @functools.lru_cache(None)
    def UserServers() -> list[ConfigFactory]:
        assert APP() is not None

        return UserServers().data()

    @staticmethod
    @functools.lru_cache(None)
    def UserSubs() -> dict[str, dict]:
        assert APP() is not None

        return UserSubs().data()

    @staticmethod
    @functools.lru_cache(None)
    def UserTUNSettings() -> dict[str, str]:
        assert APP() is not None

        return UserTUNSettings().data()

    class Extras:
        @staticmethod
        @forceToLocalhostIfPossible()
        def UserHttpProxy() -> Union[str, None]:
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
