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

"""Define configuration data and the registry used to construct it."""

from __future__ import annotations

from Furious.Interface.UserServersTableItem import UserServersTableItem

from typing import Union

import copy
import functools
import threading
import ujson

__all__ = [
    'ConfigFactory',
    'ConfigurationRegistry',
    'configurationRegistry',
    'registerConfigurationProvider',
    'configFactoryFromDict',
    'configFactoryFromAny',
    'configFactoryBlank',
]


class ConfigFactory(UserServersTableItem, dict):
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

        self._index = kwargs.pop('index', 0)
        self._deleted = kwargs.pop('deleted', False)

        # Extra attributes
        self.kwargs = kwargs

        self._init_dispatch(config)

    @functools.singledispatchmethod
    def _init_dispatch(self, config):
        """Initialize the configuration from a supported input type."""
        super().__init__()

    @_init_dispatch.register(str)
    def _(self, config):
        """Handle the registered singledispatch variant."""
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

    @_init_dispatch.register(dict)
    def _(self, config):
        """Handle the registered singledispatch variant."""
        super().__init__(**config)

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

    def getExtras(self, item):
        """Return non-core metadata associated with the configuration."""
        return self.kwargs.get(item, '')

    def setExtras(self, item, value):
        """Store non-core metadata associated with the configuration."""
        self.kwargs[item] = value

    @property
    def index(self) -> int:
        """Return the index value."""
        return self._index

    @index.setter
    def index(self, value: int):
        """Set the index value."""
        assert isinstance(value, int)

        self._index = value

    @property
    def deleted(self) -> bool:
        """Return the deleted value."""
        return self._deleted

    @deleted.setter
    def deleted(self, value: bool):
        """Set the deleted value."""
        assert isinstance(value, bool)

        self._deleted = value

    @property
    def itemRemark(self) -> str:
        """Return the item remark value."""
        return self.getExtras('remark')

    @property
    def itemSubscription(self) -> str:
        """Return the persisted subscription identifier."""
        return self.getExtras('subsId') or ''

    @property
    def itemLatency(self) -> str:
        """Return the item latency value."""
        return self.getExtras('delayResult')

    @property
    def itemSpeed(self) -> str:
        """Return the item speed value."""
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
        """Build the persisted representation of the configuration."""
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


class ConfigurationRegistry:
    """Construct configuration objects through registered providers.

    Providers are deliberately defined by behavior instead of by a plugin base
    class.  This keeps configuration and persistence independent from the
    optional plugin system while allowing plugins to contribute parsers.
    """

    def __init__(self):
        """Initialize an empty provider registry."""
        self._providers = []
        self._lock = threading.RLock()

    def register(self, provider):
        """Register *provider* once and return it."""
        requiredMethods = ('configFromString', 'configFromDict', 'blankConfig')

        if not all(callable(getattr(provider, name, None)) for name in requiredMethods):
            raise TypeError(
                'configuration providers must implement configFromString, '
                'configFromDict, and blankConfig'
            )

        with self._lock:
            if any(item is provider for item in self._providers):
                raise ValueError('configuration provider is already registered')

            self._providers.append(provider)

        return provider

    def providers(self):
        """Return registered providers in deterministic registration order."""
        with self._lock:
            return tuple(self._providers)

    def fromString(self, config: str, **kwargs):
        """Return the first provider result for textual *config*."""
        for provider in self.providers():
            factory = provider.configFromString(config, **kwargs)

            if factory is not None:
                return factory

        return None

    def fromDict(self, config: dict, **kwargs):
        """Return the first provider result for mapping *config*."""
        for provider in self.providers():
            factory = provider.configFromDict(config, **kwargs)

            if factory is not None:
                return factory

        return None

    def blank(self, protocol, **kwargs):
        """Return a blank configuration from the first matching provider."""
        for provider in self.providers():
            factory = provider.blankConfig(protocol, **kwargs)

            if factory is not None:
                return factory

        return None


configurationRegistry = ConfigurationRegistry()


def registerConfigurationProvider(provider):
    """Register a configuration provider with the process-wide registry."""
    return configurationRegistry.register(provider)


def configFactoryFromDict(config: dict, **kwargs) -> ConfigFactory:
    """Construct a configuration mapping through registered providers."""
    if not isinstance(config, dict):
        return ConfigFactory(**kwargs)

    factory = configurationRegistry.fromDict(config, **kwargs)

    return factory if factory is not None else ConfigFactory(config, **kwargs)


def configFactoryFromAny(config: Union[str, dict], **kwargs) -> ConfigFactory:
    """Construct configuration data from text or a mapping."""
    if isinstance(config, str):
        factory = configurationRegistry.fromString(config, **kwargs)

        if factory is not None:
            return factory

        try:
            return configFactoryFromDict(ujson.loads(config), **kwargs)
        except Exception:
            # Any non-exit exceptions
            return ConfigFactory(**kwargs)

    if isinstance(config, dict):
        return configFactoryFromDict(config, **kwargs)

    return ConfigFactory(**kwargs)


def configFactoryBlank(protocol, **kwargs) -> ConfigFactory:
    """Construct a blank configuration through a registered provider."""
    factory = configurationRegistry.blank(protocol, **kwargs)

    return factory if factory is not None else ConfigFactory(**kwargs)
