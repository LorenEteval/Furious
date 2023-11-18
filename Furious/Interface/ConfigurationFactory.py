from __future__ import annotations

from Furious.Interface.Encoder import UJSONEncoder, PyBase64Encoder

import typing


class ConfigurationFactory(dict):
    """
    ConfigurationFactory is how Furious sees the core config.

    It subclasses from dict and can be constructed from:
      1. dictionary -- from existing JSON object
      2. string -- from URI or (valid) JSON string
    """

    def __init__(self, config: typing.Union[str, dict] = ''):
        """
        Constructs a ConfigurationFactory. The constructor
        never throws exception

        :param config: The input configuration. Can be a string or dict
        """

        if isinstance(config, str):
            try:
                jsonObject = UJSONEncoder.decode(config)
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

    def toJSONString(self, **kwargs) -> str:
        """
        Converts self to a JSON string

        :param kwargs: Keyword arguments for encoder
        :return: JSON string
        """

        try:
            return UJSONEncoder.encode(self, **kwargs)
        except Exception:
            # Any non-exit exceptions

            # '' is invalid
            return ''

    def __getitem__(self, item: str):
        if not isinstance(item, str):
            raise TypeError('Bad type for __getitem__ call')

        return super().__getitem__(item)

    def __setitem__(self, item: str, value):
        if not isinstance(item, str):
            raise TypeError('Bad type for __setitem__ call')

        return super().__setitem__(item, value)

    def toURI(self, remark: str = '') -> str:
        """
        Converts self to a URI string

        :param remark: Remark (fragment)
        :return: URI string
        """

        raise NotImplementedError

    def fromURI(self, URI: str) -> typing.Tuple[str, bool]:
        """
        Constructs self from a URI string

        :param URI: URI string
        :return: Tuple[remark, success]
        """

        raise NotImplementedError

    def httpProxyEndpoint(self) -> str:
        """
        Get current http proxy endpoint

        :return: Http proxy endpoint string
        """

        raise NotImplementedError

    def socksProxyEndpoint(self) -> str:
        """
        Get current socks proxy endpoint

        :return: Socks proxy endpoint string
        """

        raise NotImplementedError

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        """
        Set current http proxy endpoint

        :return: True on success, false otherwise
        """

        raise NotImplementedError

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        """
        Set current socks proxy endpoint

        :return: True on success, false otherwise
        """

        raise NotImplementedError
