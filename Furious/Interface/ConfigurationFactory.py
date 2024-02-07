# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Interface.UserServersTableItem import *

from PySide6.QtWidgets import QApplication

from abc import ABC
from typing import Union

import copy
import ujson

__all__ = ['ConfigurationFactory']


class ConfigurationFactory(UserServersTableItem, dict, ABC):
    """
    ConfigurationFactory is how Furious sees the core config.

    It subclasses from dict and can be constructed from:
      1. dictionary -- from existing JSON object
      2. string -- from URI or (valid) JSON string
    """

    def __init__(self, config: Union[str, dict] = '', **kwargs):
        """
        Constructs a ConfigurationFactory. The constructor
        never throws exception

        :param config: The input configuration. Can be a string or dict
        """

        # Extra attributes
        self.kwargs = kwargs

        if isinstance(config, str):
            try:
                jsonObject = ujson.loads(config)
            except Exception:
                # Any non-exit exceptions

                try:
                    self.fromURI(config)
                except Exception:
                    # Any non-exit exceptions

                    super().__init__()
            else:
                super().__init__(**jsonObject)
        elif isinstance(config, dict):
            super().__init__(**config)
        else:
            super().__init__()

    def __getitem__(self, item: str):
        if not isinstance(item, str):
            raise TypeError(f'Bad type {type(item)} for __getitem__ call')

        return super().__getitem__(item)

    def __setitem__(self, item: str, value):
        if not isinstance(item, str):
            raise TypeError(f'Bad type {type(item)} for __setitem__ call')

        return super().__setitem__(item, value)

    def deepcopy(self) -> ConfigurationFactory:
        return copy.deepcopy(self)

    def coreName(self) -> str:
        return 'Unknown'

    def isValid(self) -> bool:
        return bool(self)

    def getExtras(self, item):
        return self.kwargs.get(item, '')

    def setExtras(self, item, value):
        self.kwargs[item] = value

    @property
    def itemRemark(self) -> str:
        return self.getExtras('remark')

    @property
    def itemSubscription(self) -> str:
        try:
            app = QApplication.instance()

            if app is None:
                return ''
            else:
                subsId = self.getExtras('subsId')
                subsOb = app.userSubs.data().get(subsId, {})

                return subsOb.get('remark', '')
        except Exception:
            # Any non-exit exceptions

            return ''

    @property
    def itemLatency(self) -> str:
        return self.getExtras('delayResult')

    @property
    def itemSpeed(self) -> str:
        return self.getExtras('speedResult')

    def toJSONString(self, **kwargs) -> str:
        """
        Converts self to a JSON string

        :param kwargs: Keyword arguments for encoder
        :return: JSON string
        """

        try:
            ensure_ascii = kwargs.pop('ensure_ascii', False)
            escape_forward_slashes = kwargs.pop('escape_forward_slashes', False)
            indent = kwargs.pop('indent', 4)

            return ujson.dumps(
                self,
                ensure_ascii=ensure_ascii,
                escape_forward_slashes=escape_forward_slashes,
                indent=indent,
                **kwargs,
            )
        except Exception:
            # Any non-exit exceptions

            # '' is invalid
            return ''

    def toStorageObject(self) -> dict:
        if self.kwargs.get('remark') is None:
            # compatibility: remark field is mandatory in previous application version
            self.kwargs['remark'] = ''

        # self.toJSONString() is used to maintain backward compatibility
        return {'config': self.toJSONString(), **self.kwargs}

    def toURI(self, remark: str = '') -> str:
        """
        Converts self to a URI string

        :param remark: Remark (fragment)
        :return: URI string
        """

        return ''

    def fromURI(self, URI: str) -> bool:
        """
        Constructs self from a URI string

        :param URI: URI string
        :return: True on success, false otherwise
        """

        return False

    def httpProxyEndpoint(self) -> str:
        """
        Get current http proxy endpoint

        :return: Http proxy endpoint string
        """

        return ''

    def socksProxyEndpoint(self) -> str:
        """
        Get current socks proxy endpoint

        :return: Socks proxy endpoint string
        """

        return ''

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        """
        Set current http proxy endpoint

        :return: True on success, false otherwise
        """

        return False

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        """
        Set current socks proxy endpoint

        :return: True on success, false otherwise
        """

        return False
