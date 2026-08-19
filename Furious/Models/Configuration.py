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

"""Define the core-neutral connection-document model."""

from __future__ import annotations

from typing import Union

import copy
import functools
import ujson

__all__ = [
    'ConfigFactory',
]


class ConfigFactory(dict):
    """
    ConfigurationFactory is how Furious sees the core config.

    It subclasses from dict and can be constructed from:
      1. dictionary -- from existing JSON object
      2. string -- from URI or (valid) JSON string
    """

    def __init__(self, config: Union[str, dict] = ''):
        """
        Constructs a ConfigurationFactory. The constructor
        never throws exception

        :param config: The input configuration. Can be a string or dict
        """

        self._constructionError = ''
        self._serializationError = ''
        self._init_dispatch(config)

    @functools.singledispatchmethod
    def _init_dispatch(self, config):
        """Initialize the configuration from a supported input type."""
        super().__init__()

        self._constructionError = (
            f'unsupported configuration input type: {type(config).__name__}'
        )

    @_init_dispatch.register(str)
    def _(self, config):
        """Handle the registered singledispatch variant."""
        try:
            jsonObject = ujson.loads(config)
        except Exception as jsonError:
            # Any non-exit exceptions

            try:
                parsed = self.fromURI(config)
            except Exception as uriError:
                # Any non-exit exceptions

                super().__init__()

                self._constructionError = (
                    f'failed to parse configuration as '
                    f'JSON ({jsonError}) or URI ({uriError})'
                )
            else:
                if parsed:
                    self._constructionError = ''
                else:
                    super().__init__()

                    self._constructionError = (
                        f'configuration is not a JSON object'
                        f' or recognized URI: {jsonError}'
                    )
        else:
            if isinstance(jsonObject, dict) and all(
                isinstance(key, str) for key in jsonObject
            ):
                super().__init__(**jsonObject)

                self._constructionError = ''
            else:
                super().__init__()

                self._constructionError = (
                    'configuration JSON root must be an object with string keys'
                )

    @_init_dispatch.register(dict)
    def _(self, config):
        """Handle the registered singledispatch variant."""
        if all(isinstance(key, str) for key in config):
            super().__init__(**config)

            self._constructionError = ''
        else:
            super().__init__()

            self._constructionError = 'configuration keys must be strings'

    def constructionError(self) -> str:
        """Return the most recent non-throwing construction diagnostic."""
        return self._constructionError

    def serializationError(self) -> str:
        """Return the most recent JSON serialization diagnostic."""
        return self._serializationError

    def __getitem__(self, item: str):
        """Return an item from the config factory."""
        if not isinstance(item, str):
            raise TypeError(f'Bad type {type(item)} for __getitem__ call')

        return super().__getitem__(item)

    def __setitem__(self, item: str, value):
        """Set an item on the config factory."""
        if not isinstance(item, str):
            raise TypeError(f'Bad type {type(item)} for __setitem__ call')

        return super().__setitem__(item, value)

    def deepcopy(self) -> ConfigFactory:
        """Return an independent copy of the configuration."""
        return copy.deepcopy(self)

    def coreName(self) -> str:
        """Return the core implementation name."""
        return 'Unknown'

    def isValid(self) -> bool:
        """Return whether valid."""
        return bool(self)

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

            result = ujson.dumps(
                self,
                ensure_ascii=ensure_ascii,
                escape_forward_slashes=escape_forward_slashes,
                indent=indent,
                **kwargs,
            )
        except Exception as ex:
            # Any non-exit exceptions

            self._serializationError = str(ex)

            # '' is invalid
            return ''

        self._serializationError = ''

        return result

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

    def httpProxy(self) -> str:
        """
        Get current http proxy endpoint

        :return: Http proxy endpoint string
        """

        return ''

    def socksProxy(self) -> str:
        """
        Get current socks proxy endpoint

        :return: Socks proxy endpoint string
        """

        return ''

    def remoteAddress(self) -> str:
        """Return the remote host that must remain reachable outside TUN."""
        return str(getattr(self, 'itemAddress', ''))

    def setHttpProxy(self, endpoint: str) -> bool:
        """
        Set current http proxy endpoint

        :return: True on success, false otherwise
        """

        return False

    def setSocksProxy(self, endpoint: str) -> bool:
        """
        Set current socks proxy endpoint

        :return: True on success, false otherwise
        """

        return False
