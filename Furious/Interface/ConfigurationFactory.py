from __future__ import annotations

from Furious.Interface.Encoder import UJSONEncoder, PyBase64Encoder

import typing
import functools
import urllib.parse

quote = functools.partial(urllib.parse.quote, safe='')
unquote = functools.partial(urllib.parse.unquote)
parse_qsl = functools.partial(urllib.parse.parse_qsl)
urlsplit = functools.partial(urllib.parse.urlsplit)
urlparse = functools.partial(urllib.parse.urlparse)
urlunparse = functools.partial(urllib.parse.urlunparse)


def parseHostPort(address):
    if address.count('//') == 0:
        result = urlsplit('//' + address)
    else:
        result = urlsplit(address)

    return result.hostname, str(result.port)


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
            if config.count('://'):
                try:
                    self.fromURI(config)
                except Exception:
                    # Any non-exit exceptions

                    super().__init__()
            else:
                try:
                    jsonObject = UJSONEncoder.decode(config)
                except Exception:
                    # Any non-exit exceptions

                    jsonObject = {}

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
        Converts self to a JSON string

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


class ConfigurationXrayProxyOutboundObject(dict):
    def __init__(
        self,
        protocol,
        remote_host,
        remote_port,
        uuid_,
        encryption,
        type_,
        security,
        **kwargs,
    ):
        networkObjectArgs, securityArgs, TLSObjectArgs = {}, {}, {}

        if type_ == 'h2':
            networkKey = 'httpSettings'
        else:
            networkKey = f'{type_}Settings'

        networkObjectArgs[
            networkKey
        ] = ConfigurationXray.kwargs2ProxyStreamSettingsNetworkObject(
            type_, remote_host, kwargs
        )

        if security:
            securityArgs['security'] = security

            if security != 'none':
                TLSObjectArgs[
                    # tlsSettings, realitySettings
                    f'{security}Settings'
                ] = ConfigurationXray.kwargs2ProxyStreamSettingsTLSObject(
                    protocol, remote_host, security, kwargs
                )

        super().__init__(
            **{
                'tag': 'proxy',
                'protocol': protocol,
                'settings': {
                    'vnext': [
                        {
                            'address': remote_host,
                            'port': int(remote_port),
                            'users': [
                                ConfigurationXray.kwargs2ProxyUserObject(
                                    protocol, uuid_, encryption, kwargs
                                ),
                            ],
                        },
                    ]
                },
                'streamSettings': {
                    'network': type_,
                    **networkObjectArgs,
                    **securityArgs,
                    **TLSObjectArgs,
                },
                'mux': {
                    'enabled': False,
                    'concurrency': -1,
                },
            },
        )


class ConfigurationXraySSProxyOutboundObject(dict):
    def __init__(self, method, password, address, port):
        super().__init__(
            **{
                'tag': 'proxy',
                'protocol': 'shadowsocks',
                'settings': {
                    'servers': [
                        {
                            'address': address,
                            'port': int(port),
                            'method': method,
                            'password': password,
                            # TODO. Extension
                            'email': 'example@email.com',
                            'ota': False,
                        },
                    ]
                },
                'streamSettings': {
                    'network': 'tcp',
                },
                'mux': {
                    'enabled': False,
                    'concurrency': -1,
                },
            }
        )


class ConfigurationXrayTrojanProxyOutboundObject(dict):
    def __init__(self, password, address, port, type_, security, **kwargs):
        networkObjectArgs, securityArgs, TLSObjectArgs = {}, {}, {}

        if type_ == 'h2':
            networkKey = 'httpSettings'
        else:
            networkKey = f'{type_}Settings'

        networkObjectArgs[
            networkKey
        ] = ConfigurationXray.kwargs2ProxyStreamSettingsNetworkObject(
            type_, address, kwargs
        )

        if security:
            securityArgs['security'] = security

            if security != 'none':
                TLSObjectArgs[
                    # tlsSettings, realitySettings
                    f'{security}Settings'
                ] = ConfigurationXray.kwargs2ProxyStreamSettingsTLSObject(
                    'trojan', address, security, kwargs
                )

        super().__init__(
            **{
                'tag': 'proxy',
                'protocol': 'trojan',
                'settings': {
                    'servers': [
                        {
                            'address': address,
                            'port': int(port),
                            'password': password,
                            # TODO. Extension
                            'email': 'example@email.com',
                        },
                    ]
                },
                'streamSettings': {
                    'network': type_,
                    **networkObjectArgs,
                    **securityArgs,
                    **TLSObjectArgs,
                },
                'mux': {
                    'enabled': False,
                    'concurrency': -1,
                },
            },
        )


class ConfigurationXray(ConfigurationFactory):
    def __init__(self, config: typing.Union[str, dict] = ''):
        super().__init__(config)

    @property
    def proxyOutboundObject(self) -> dict:
        try:
            for outboundObject in self['outbounds']:
                if outboundObject['tag'] == 'proxy':
                    return outboundObject

            return {}
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def proxyProtocol(self) -> str:
        try:
            return self.proxyOutboundObject['protocol']
        except Exception:
            # Any non-exit exceptions

            return ''

    @property
    def proxyServerObject(self) -> dict:
        try:
            if (
                self.proxyProtocol.lower() == 'vmess'
                or self.proxyProtocol.lower() == 'vless'
            ):
                return self.proxyOutboundObject['settings']['vnext'][0]

            if (
                self.proxyProtocol.lower() == 'shadowsocks'
                or self.proxyProtocol.lower() == 'trojan'
            ):
                return self.proxyOutboundObject['settings']['servers'][0]

            return {}
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def proxyUserObject(self) -> dict:
        try:
            return self.proxyServerObject['users'][0]
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def proxyStreamSettingsObject(self) -> dict:
        try:
            return self.proxyOutboundObject['streamSettings']
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def proxyStreamSettingsTLS(self) -> str:
        try:
            return self.proxyStreamSettingsObject.get('security', 'none')
        except Exception:
            # Any non-exit exceptions

            return ''

    @property
    def proxyStreamSettingsTLSObject(self) -> dict:
        try:
            # tlsSettings, realitySettings
            TLSKey = f'{self.proxyStreamSettingsTLS}Settings'

            return self.proxyStreamSettingsObject[TLSKey]
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def proxyStreamSettingsNetwork(self) -> str:
        try:
            return self.proxyStreamSettingsObject['network']
        except Exception:
            # Any non-exit exceptions

            return ''

    @property
    def proxyStreamSettingsNetworkObject(self) -> dict:
        try:
            if self.proxyStreamSettingsNetwork == 'h2':
                networkKey = 'httpSettings'
            else:
                networkKey = f'{self.proxyStreamSettingsNetwork}Settings'

            return self.proxyStreamSettingsObject[networkKey]
        except Exception:
            # Any non-exit exceptions

            return {}

    @property
    def kwargsFromVMessProxyStreamSettingsNetworkObject(self) -> dict:
        kwargs = {}

        network = self.proxyStreamSettingsNetwork
        networkObject = self.proxyStreamSettingsNetworkObject

        if not networkObject:
            return kwargs

        def hasKey(key):
            return networkObject.get(key) is not None

        if network == 'tcp':
            try:
                kwargs['type'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'kcp':
            try:
                # Get order matters here
                if hasKey('seed'):
                    kwargs['path'] = networkObject['seed']

                kwargs['type'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'ws':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                if networkObject['headers']['Host']:
                    kwargs['host'] = quote(networkObject['headers']['Host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'h2' or network == 'http':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(','.join(networkObject['host']))
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'quic':
            try:
                # Get order matters here
                if hasKey('security'):
                    kwargs['host'] = networkObject['security']

                if hasKey('key'):
                    kwargs['path'] = quote(networkObject['key'])

                kwargs['type'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'grpc':
            if hasKey('serviceName'):
                kwargs['path'] = networkObject['serviceName']

        return kwargs

    @property
    def kwargsFromVLESSProxyStreamSettingsNetworkObject(self) -> dict:
        kwargs = {}

        network = self.proxyStreamSettingsNetwork
        networkObject = self.proxyStreamSettingsNetworkObject

        if not networkObject:
            return kwargs

        def hasKey(key):
            return networkObject.get(key) is not None

        if network == 'tcp':
            try:
                kwargs['headerType'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'kcp':
            try:
                # Get order matters here
                if hasKey('seed'):
                    kwargs['seed'] = networkObject['seed']

                kwargs['headerType'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'ws':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                if networkObject['headers']['Host']:
                    kwargs['host'] = quote(networkObject['headers']['Host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'h2' or network == 'http':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(','.join(networkObject['host']))
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'quic':
            try:
                # Get order matters here
                if hasKey('security'):
                    kwargs['quicSecurity'] = networkObject['security']

                if hasKey('key'):
                    kwargs['path'] = quote(networkObject['key'])

                kwargs['headerType'] = networkObject['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'grpc':
            if hasKey('serviceName'):
                kwargs['serviceName'] = networkObject['serviceName']

        return kwargs

    @staticmethod
    def kwargs2ProxyStreamSettingsNetworkObject(type_, remote_host, kwargs) -> dict:
        # Note:
        # v2rayN share standard doesn't require unquote. Still
        # unquote value according to (VMess AEAD / VLESS) standard

        if type_ == 'tcp':
            TcpObject = {}

            if kwargs.get('headerType', 'none'):
                headerType = kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    TcpObject['header'] = {
                        'type': headerType,
                    }

                # Request settings for HTTP
                if headerType == 'http' and kwargs.get('host'):
                    TcpObject['header']['request'] = {
                        'version': '1.1',
                        'method': 'GET',
                        'path': [kwargs.get('path', '/')],
                        'headers': {
                            'Host': [unquote(kwargs.get('host'))],
                            'User-Agent': [
                                (
                                    'Mozilla/5.0 (Windows NT 10.0; WOW64) '
                                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                                    'Chrome/53.0.2785.143 Safari/537.36'
                                ),
                                (
                                    'Mozilla/5.0 (iPhone; CPU iPhone OS 10_0_2 like Mac OS X) '
                                    'AppleWebKit/601.1 (KHTML, like Gecko) '
                                    'CriOS/53.0.2785.109 '
                                    'Mobile/14A456 '
                                    'Safari/601.1.46'
                                ),
                            ],
                            'Accept-Encoding': ['gzip, deflate'],
                            'Connection': ['keep-alive'],
                            'Pragma': 'no-cache',
                        },
                    }

            return TcpObject

        elif type_ == 'kcp':
            KcpObject = {
                # Extension. From v2rayN
                'uplinkCapacity': 12,
                'downlinkCapacity': 100,
            }

            if kwargs.get('headerType', 'none'):
                headerType = kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    KcpObject['header'] = {
                        'type': headerType,
                    }

            if kwargs.get('seed'):
                KcpObject['seed'] = kwargs.get('seed')

            return KcpObject

        elif type_ == 'ws':
            WebSocketObject = {}

            if kwargs.get('path', '/'):
                WebSocketObject['path'] = unquote(kwargs.get('path', '/'))

            if kwargs.get('host'):
                WebSocketObject['headers'] = {
                    'Host': unquote(kwargs.get('host')),
                }

            return WebSocketObject

        elif type_ == 'h2' or type_ == 'http':
            HttpObject = {}

            if kwargs.get('host', remote_host):
                # Protect "xxx," format
                HttpObject['host'] = list(
                    filter(
                        lambda x: x != '',
                        unquote(kwargs.get('host', remote_host)).split(','),
                    )
                )

            if kwargs.get('path', '/'):
                HttpObject['path'] = unquote(kwargs.get('path', '/'))

            return HttpObject

        elif type_ == 'quic':
            QuicObject = {}

            if kwargs.get('quicSecurity', 'none'):
                QuicObject['security'] = kwargs.get('quicSecurity', 'none')

            if kwargs.get('key'):
                QuicObject['key'] = unquote(kwargs.get('key'))

            if kwargs.get('headerType', 'none'):
                headerType = kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    QuicObject['header'] = {
                        'type': headerType,
                    }

            return QuicObject

        elif type_ == 'grpc':
            GRPCObject = {}

            if kwargs.get('serviceName'):
                GRPCObject['serviceName'] = kwargs.get('serviceName')

            if kwargs.get('mode', 'gun'):
                GRPCObject['multiMode'] = kwargs.get('mode', 'gun') == 'multi'

            return GRPCObject

    @property
    def kwargsFromProxyStreamSettingsTLSObject(self) -> dict:
        kwargs = {}

        if self.proxyStreamSettingsTLS == '' or self.proxyStreamSettingsTLS == 'none':
            return kwargs

        TLSObject = self.proxyStreamSettingsTLSObject

        if (
            self.proxyStreamSettingsTLS == 'reality'
            or self.proxyStreamSettingsTLS == 'tls'
        ):
            if TLSObject.get('fingerprint'):
                kwargs['fp'] = TLSObject['fingerprint']

            if TLSObject.get('serverName'):
                kwargs['sni'] = TLSObject['serverName']

            if TLSObject.get('alpn'):
                kwargs['alpn'] = quote(','.join(TLSObject['alpn']))

        if self.proxyStreamSettingsTLS == 'reality':
            # More kwargs for reality
            if TLSObject.get('publicKey'):
                kwargs['pbk'] = TLSObject['publicKey']

            if TLSObject.get('shortId'):
                kwargs['sid'] = TLSObject['shortId']

            if TLSObject.get('spiderX'):
                kwargs['spx'] = quote(TLSObject['spiderX'])

        return kwargs

    @staticmethod
    def kwargs2ProxyStreamSettingsTLSObject(
        protocol, remote_host, security, kwargs
    ) -> dict:
        TLSObject = {}

        if security == 'reality' or security == 'tls':
            # Note: If specify default value 'chrome', some share link fails.
            # Leave default value as empty
            fp = kwargs.get('fp')
            sni = kwargs.get('sni')
            # Protect "xxx," format
            alpn = list(
                filter(
                    lambda x: x != '',
                    unquote(kwargs.get('alpn', '')).split(','),
                )
            )

            if fp:
                TLSObject['fingerprint'] = fp

            if sni:
                TLSObject['serverName'] = sni
            else:
                host = ''

                if protocol == 'vmess':
                    host = kwargs.get('host')

                if protocol == 'vless':
                    host = remote_host

                if host:
                    TLSObject['serverName'] = host

            if alpn:
                TLSObject['alpn'] = alpn

        if security == 'reality':
            # More args for reality
            pbk = kwargs.get('pbk')
            sid = kwargs.get('sid', '')
            spx = kwargs.get('spx', '')

            if pbk:
                TLSObject['publicKey'] = pbk

            TLSObject['shortId'] = sid
            TLSObject['spiderX'] = unquote(spx)

        return TLSObject

    @staticmethod
    def kwargs2ProxyUserObject(protocol, uuid_, encryption, kwargs) -> dict:
        if protocol == 'vmess':
            UserObject = {
                'id': uuid_,
                'security': encryption,
                # TODO. Extension
                'email': 'example@email.com',
            }

            # For VMess(v2rayN share standard) only.
            if kwargs.get('aid') is not None:
                UserObject['alterId'] = kwargs.get('aid')

            return UserObject

        if protocol == 'vless':
            UserObject = {
                'id': uuid_,
                'encryption': encryption,
                # TODO. Extension
                'email': 'example@email.com',
            }

            if kwargs.get('flow'):
                # flow is empty, TLS. Otherwise, XTLS.
                UserObject['flow'] = kwargs.get('flow')

            return UserObject

        return {}

    def toURI(self, remark: str = '') -> str:
        if self.proxyProtocol.lower() == 'vmess':
            netloc = PyBase64Encoder.encode(
                UJSONEncoder.encode(
                    {
                        'v': '2',
                        'ps': remark,
                        **{
                            key: self.proxyServerObject[value]
                            for key, value in {
                                'add': 'address',
                                'port': 'port',
                            }.items()
                        },
                        **{
                            key: self.proxyUserObject[value]
                            for key, value in {
                                'id': 'id',
                                'aid': 'alterId',
                                'scy': 'security',
                            }.items()
                        },
                        'net': self.proxyStreamSettingsNetwork,
                        'tls': self.proxyStreamSettingsTLS,
                        # kwargs
                        **self.kwargsFromVMessProxyStreamSettingsNetworkObject,
                        **self.kwargsFromProxyStreamSettingsTLSObject,
                    }
                ).encode()
            ).decode()

            return urlunparse(['vmess', netloc, '', '', {}, ''])

        if self.proxyProtocol.lower() == 'vless':
            flowArg = {}

            if self.proxyUserObject.get('flow'):
                flowArg['flow'] = self.proxyUserObject['flow']

            netloc = (
                self.proxyUserObject['id']
                + '@'
                + self.proxyServerObject['address']
                + ':'
                + str(self.proxyServerObject['port'])
            )

            query = '&'.join(
                f'{key}={value}'
                for key, value in {
                    'encryption': self.proxyUserObject['encryption'],
                    'type': self.proxyStreamSettingsNetwork,
                    'security': self.proxyStreamSettingsTLS,
                    # kwargs
                    **flowArg,
                    **self.kwargsFromVLESSProxyStreamSettingsNetworkObject,
                    **self.kwargsFromProxyStreamSettingsTLSObject,
                }.items()
            )

            return urlunparse(['vless', netloc, '', '', query, quote(remark)])

        if self.proxyProtocol.lower() == 'shadowsocks':
            method, password, address, port = list(
                self.proxyServerObject[value]
                for value in ['method', 'password', 'address', 'port']
            )

            netloc = f'{quote(method)}:{quote(password)}@{address}:{port}'

            return urlunparse(['ss', netloc, '', '', '', quote(remark)])

        if self.proxyProtocol.lower() == 'trojan':
            password, address, port = list(
                self.proxyServerObject[value]
                for value in ['password', 'address', 'port']
            )

            netloc = f'{quote(password)}@{address}:{port}'

            query = '&'.join(
                f'{key}={value}'
                for key, value in {
                    'type': self.proxyStreamSettingsNetwork,
                    'security': self.proxyStreamSettingsTLS,
                    # kwargs
                    **self.kwargsFromVLESSProxyStreamSettingsNetworkObject,
                    **self.kwargsFromProxyStreamSettingsTLSObject,
                }.items()
            )

            return urlunparse(['trojan', netloc, '', '', query, quote(remark)])

        raise ValueError(
            f'Unrecognized protocol {self.proxyProtocol} when converting to URI'
        )

    @staticmethod
    def URI2VMessProxyOutboundObject(URI: str) -> typing.Tuple[str, dict]:
        try:
            myHead, myBody = URI.split('://')
        except Exception:
            # Any non-exit exceptions

            return '', {}

        try:
            myData = PyBase64Encoder.decode(myBody)
            myJSON = UJSONEncoder.decode(myData)
        except Exception:
            # Any non-exit exceptions

            return ConfigurationXray.URI2VLESSProxyOutboundObject(URI, protocol='vmess')
        else:

            def getOrDefault(key, default=''):
                return myJSON.get(key, default)

            remark = unquote(getOrDefault('ps'))

            return (
                remark,
                # Ignore: v
                ConfigurationXrayProxyOutboundObject(
                    'vmess',
                    getOrDefault('add'),
                    int(getOrDefault('port', '0')),
                    getOrDefault('id'),
                    getOrDefault('scy', 'auto'),
                    getOrDefault('net', 'tcp'),
                    getOrDefault('tls', 'none'),
                    # kwargs. v2rayN share standard -> (VMess AEAD / VLESS) standard
                    aid=int(getOrDefault('aid', '0')),
                    headerType=getOrDefault('type', 'none'),
                    host=getOrDefault('host'),
                    quicSecurity=getOrDefault('host', 'none'),
                    path=getOrDefault('path'),
                    key=getOrDefault('path'),
                    seed=getOrDefault('path'),
                    serviceName=getOrDefault('path'),
                    sni=getOrDefault('sni'),
                    alpn=getOrDefault('alpn'),
                    # Note: If specify default value 'chrome', some share link fails.
                    # Leave default value as empty
                    fp=getOrDefault('fp'),
                ),
            )

    @staticmethod
    def URI2VLESSProxyOutboundObject(URI: str, **kwargs) -> typing.Tuple[str, dict]:
        result = urlparse(URI)
        remark = unquote(result.fragment)

        queryObject = {key: value for key, value in parse_qsl(result.query)}

        uuid_, server = result.netloc.split('@')

        remote_host, remote_port = parseHostPort(server)

        encryption = queryObject.pop('encryption', 'none')
        type_ = queryObject.pop('type', 'tcp')
        security = queryObject.pop('security', 'none')

        return (
            remark,
            ConfigurationXrayProxyOutboundObject(
                kwargs.pop('protocol', 'vless'),
                remote_host,
                int(remote_port),
                uuid_,
                encryption,
                type_,
                security,
                # kwargs
                **queryObject,
            ),
        )

    @staticmethod
    def URI2SSProxyOutboundObject(URI: str) -> typing.Tuple[str, dict]:
        try:
            result = urlparse(URI)
            remark = unquote(result.fragment)
        except Exception:
            # Any non-exit exceptions

            return '', {}

        def getSSParams():
            try:
                # ss://base64...#fragment
                userinfo, server = (
                    PyBase64Encoder.decode(result.netloc).decode().split('@')
                )

                return [*userinfo.split(':'), *parseHostPort(server)]
            except Exception:
                # Any non-exit exceptions

                pass

            # Begin SIP002...
            try:
                # Try pack with 3 element
                userinfo, server = result.netloc.split('@')

                # Some old SS share link doesn't add padding
                # in base64 encoding. Add padding to userinfo
                return [
                    *PyBase64Encoder.decode(userinfo + '===').decode().split(':'),
                    *parseHostPort(server),
                ]
            except Exception:
                # Any non-exit exceptions

                pass

            try:
                # Try pack with 4 element
                userinfo, server = result.netloc.split('@')

                return [*userinfo.split(':'), *parseHostPort(server)]
            except Exception:
                # Any non-exit exceptions

                pass

            raise ValueError(f'Invalid SS URI format {URI}')

        return (
            remark,
            ConfigurationXraySSProxyOutboundObject(*getSSParams()),
        )

    @staticmethod
    def URI2TrojanProxyOutboundObject(URI: str) -> typing.Tuple[str, dict]:
        result = urlparse(URI)
        remark = unquote(result.fragment)

        queryObject = {key: value for key, value in parse_qsl(result.query)}

        password, server = result.netloc.split('@')

        address, port = parseHostPort(server)

        type_ = queryObject.pop('type', 'tcp')
        # For Trojan: Assign tls by default
        security = queryObject.pop('security', 'tls')

        return (
            remark,
            ConfigurationXrayTrojanProxyOutboundObject(
                password, address, port, type_, security, **queryObject
            ),
        )

    @staticmethod
    def URI2ProxyOutboundObject(URI: str) -> typing.Tuple[str, dict]:
        try:
            myHead, myBody = URI.split('://')
        except Exception as ex:
            # Any non-exit exceptions

            raise ValueError(f'Invalid URI format {URI}') from ex

        if myHead.lower() == 'vmess':
            return ConfigurationXray.URI2VMessProxyOutboundObject(URI)

        if myHead.lower() == 'vless':
            return ConfigurationXray.URI2VLESSProxyOutboundObject(URI)

        if myHead.lower() == 'ss':
            return ConfigurationXray.URI2SSProxyOutboundObject(URI)

        if myHead.lower() == 'trojan':
            return ConfigurationXray.URI2TrojanProxyOutboundObject(URI)

        raise ValueError(f'Unrecognized URI scheme {URI}')

    def fromURI(self, URI: str) -> typing.Tuple[str, bool]:
        try:
            myHead, myBody = URI.split('://')
        except Exception:
            # Any non-exit exceptions

            return '', False

        try:
            remark, proxyOutboundObject = ConfigurationXray.URI2ProxyOutboundObject(URI)

            dict.__init__(
                self,
                **{
                    'log': {
                        'access': '',
                        'error': '',
                        'loglevel': 'warning',
                    },
                    'inbounds': [
                        {
                            'tag': 'socks',
                            'port': 10808,
                            'listen': '127.0.0.1',
                            'protocol': 'socks',
                            'sniffing': {
                                'enabled': True,
                                'destOverride': [
                                    'http',
                                    'tls',
                                ],
                            },
                            'settings': {
                                'auth': 'noauth',
                                'udp': True,
                                'allowTransparent': False,
                            },
                        },
                        {
                            'tag': 'http',
                            'port': 10809,
                            'listen': '127.0.0.1',
                            'protocol': 'http',
                            'sniffing': {
                                'enabled': True,
                                'destOverride': [
                                    'http',
                                    'tls',
                                ],
                            },
                            'settings': {
                                'auth': 'noauth',
                                'udp': True,
                                'allowTransparent': False,
                            },
                        },
                    ],
                    'outbounds': [
                        # Proxy
                        proxyOutboundObject,
                        # Direct
                        {
                            'tag': 'direct',
                            'protocol': 'freedom',
                            'settings': {},
                        },
                        # Block
                        {
                            'tag': 'block',
                            'protocol': 'blackhole',
                            'settings': {
                                'response': {
                                    'type': 'http',
                                }
                            },
                        },
                    ],
                    'routing': {},
                },
            )

            return remark, True
        except Exception:
            # Any non-exit exceptions

            return '', False

    def httpProxyEndpoint(self) -> str:
        try:
            for inbound in self['inbounds']:
                if inbound['protocol'] == 'http':
                    # Note: If there are multiple http inbounds
                    # satisfied, the first one will be chosen.
                    return str(inbound['listen']) + ':' + str(inbound['port'])

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    def socksProxyEndpoint(self) -> str:
        try:
            for inbound in self['inbounds']:
                if inbound['protocol'] == 'socks':
                    # Note: If there are multiple socks inbounds
                    # satisfied, the first one will be chosen.
                    return str(inbound['listen']) + ':' + str(inbound['port'])

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        try:
            for inbound in self['inbounds']:
                if inbound['protocol'] == 'http':
                    # Note: If there are multiple http inbounds
                    # satisfied, the first one will be chosen.
                    listen, port = parseHostPort(endpoint)

                    inbound['listen'], inbound['port'] = listen, int(port)

                    return True

            return False
        except Exception:
            # Any non-exit exceptions

            return False

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        try:
            for inbound in self['inbounds']:
                if inbound['protocol'] == 'socks':
                    # Note: If there are multiple socks inbounds
                    # satisfied, the first one will be chosen.
                    listen, port = parseHostPort(endpoint)

                    inbound['listen'], inbound['port'] = listen, int(port)

                    return True

            return False
        except Exception:
            # Any non-exit exceptions

            return False

    def loggingAccessPath(self) -> str:
        try:
            return self['log']['access']
        except Exception:
            # Any non-exit exceptions

            return ''

    def loggingErrorPath(self) -> str:
        try:
            return self['log']['error']
        except Exception:
            # Any non-exit exceptions

            return ''


# TODO


class ConfigurationHysteria1(ConfigurationFactory):
    def __init__(self, config: typing.Union[str, dict] = ''):
        super().__init__(config)

    def toURI(self, remark: str = '') -> str:
        raise NotImplementedError

    def fromURI(self, URI: str) -> typing.Tuple[str, bool]:
        raise NotImplementedError

    def httpProxyEndpoint(self) -> str:
        pass

    def socksProxyEndpoint(self) -> str:
        pass

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        pass

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        pass


class ConfigurationHysteria2(ConfigurationFactory):
    def __init__(self, config: typing.Union[str, dict] = ''):
        super().__init__(config)

    def toURI(self, remark: str = '') -> str:
        pass

    def fromURI(self, URI: str) -> typing.Tuple[str, bool]:
        pass

    def httpProxyEndpoint(self) -> str:
        pass

    def socksProxyEndpoint(self) -> str:
        pass

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        pass

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        pass
