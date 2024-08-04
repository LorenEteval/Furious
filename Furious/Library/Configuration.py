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

from Furious.Interface import *
from Furious.Utility import *
from Furious.Library.Encoder import *

from typing import Union, Tuple

import functools
import urllib.parse

quote = functools.partial(urllib.parse.quote, safe='')
unquote = functools.partial(urllib.parse.unquote)
parse_qsl = functools.partial(urllib.parse.parse_qsl)
urlparse = functools.partial(urllib.parse.urlparse)
urlunparse = functools.partial(urllib.parse.urlunparse)


__all__ = [
    'ConfigurationXray',
    'ConfigurationHysteria1',
    'ConfigurationHysteria2',
    'constructFromDict',
    'constructFromAny',
]


class ConfigurationXrayProxyOutboundObjectV(dict):
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


class ConfigurationXrayProxyOutboundObjectSS(dict):
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
                            'email': PROXY_OUTBOUND_USER_EMAIL,
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


class ConfigurationXrayProxyOutboundObjectTrojan(dict):
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
                            'email': PROXY_OUTBOUND_USER_EMAIL,
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
    def __init__(self, config: Union[str, dict] = '', **kwargs):
        super().__init__(config, **kwargs)

    def coreName(self):
        return 'Xray-core'

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

        elif network == 'httpupgrade':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(networkObject['host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'splithttp':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(networkObject['host'])
            except Exception:
                # Any non-exit exceptions

                pass

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

            if hasKey('multiMode'):
                if networkObject['multiMode']:
                    kwargs['mode'] = 'multi'

            if hasKey('authority'):
                kwargs['authority'] = networkObject['authority']

        elif network == 'httpupgrade':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(networkObject['host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif network == 'splithttp':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(networkObject['path'])

                kwargs['host'] = quote(networkObject['host'])
            except Exception:
                # Any non-exit exceptions

                pass

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

            if kwargs.get('authority'):
                GRPCObject['authority'] = kwargs.get('authority')

            return GRPCObject

        elif type_ == 'httpupgrade':
            httpUpgradeObject = {}

            if kwargs.get('path', '/'):
                httpUpgradeObject['path'] = unquote(kwargs.get('path', '/'))

            if kwargs.get('host'):
                httpUpgradeObject['host'] = unquote(kwargs.get('host'))

            return httpUpgradeObject

        elif type_ == 'splithttp':
            splitHttpObject = {}

            if kwargs.get('path', '/'):
                splitHttpObject['path'] = unquote(kwargs.get('path', '/'))

            if kwargs.get('host'):
                splitHttpObject['host'] = unquote(kwargs.get('host'))

            return splitHttpObject

    @property
    def kwargsFromProxyStreamSettingsTLSObject(self) -> dict:
        kwargs = {}

        TLS = self.proxyStreamSettingsTLS
        TLSObject = self.proxyStreamSettingsTLSObject

        if TLS == '' or TLS == 'none':
            return kwargs

        if TLS == 'reality' or TLS == 'tls':
            if TLSObject.get('fingerprint'):
                kwargs['fp'] = TLSObject['fingerprint']

            if TLSObject.get('serverName'):
                kwargs['sni'] = TLSObject['serverName']

            if TLSObject.get('alpn'):
                kwargs['alpn'] = quote(','.join(TLSObject['alpn']))

        if TLS == 'reality':
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
                'email': PROXY_OUTBOUND_USER_EMAIL,
            }

            # For VMess(v2rayN share standard) only.
            if kwargs.get('aid') is not None:
                # int: extra guard
                UserObject['alterId'] = int(kwargs.get('aid'))

            return UserObject

        if protocol == 'vless':
            UserObject = {
                'id': uuid_,
                'encryption': encryption,
                'email': PROXY_OUTBOUND_USER_EMAIL,
            }

            if kwargs.get('flow'):
                # flow is empty, TLS. Otherwise, XTLS.
                UserObject['flow'] = kwargs.get('flow')

            return UserObject

        return {}

    @staticmethod
    def URI2ProxyOutboundObjectVMess(URI: str) -> Tuple[str, dict]:
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

            return ConfigurationXray.URI2ProxyOutboundObjectVLESS(URI, protocol='vmess')
        else:

            def getOrDefault(key, default=''):
                return myJSON.get(key, default)

            remark = unquote(getOrDefault('ps'))

            return (
                remark,
                # Ignore: v
                ConfigurationXrayProxyOutboundObjectV(
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
    def URI2ProxyOutboundObjectVLESS(URI: str, **kwargs) -> Tuple[str, dict]:
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
            ConfigurationXrayProxyOutboundObjectV(
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
    def URI2ProxyOutboundObjectSS(URI: str) -> Tuple[str, dict]:
        try:
            result = urlparse(URI)
            remark = unquote(result.fragment)
        except Exception:
            # Any non-exit exceptions

            return '', {}

        def getSSParams():
            # Begin SIP002...
            try:
                # Try pack with 3 element
                userinfo, server = result.netloc.split('@')

                # Some old SS share link doesn't add padding
                # in base64 encoding. Add padding to userinfo
                return [
                    *PyBase64Encoder.decode(userinfo + '===').decode().split(':', 1),
                    *parseHostPort(server),
                ]
            except Exception:
                # Any non-exit exceptions

                pass

            try:
                # Try pack with 4 element
                userinfo, server = result.netloc.split('@')

                return [*userinfo.split(':', 1), *parseHostPort(server)]
            except Exception:
                # Any non-exit exceptions

                pass

            try:
                # ss://base64...#fragment
                userinfo, server = (
                    PyBase64Encoder.decode(result.netloc).decode().split('@')
                )

                return [*userinfo.split(':', 1), *parseHostPort(server)]
            except Exception:
                # Any non-exit exceptions

                pass

            raise ValueError(f'Invalid SS URI format {URI}')

        return (
            remark,
            ConfigurationXrayProxyOutboundObjectSS(*getSSParams()),
        )

    @staticmethod
    def URI2ProxyOutboundObjectTrojan(URI: str) -> Tuple[str, dict]:
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
            ConfigurationXrayProxyOutboundObjectTrojan(
                password, address, port, type_, security, **queryObject
            ),
        )

    @staticmethod
    def URI2ProxyOutboundObject(URI: str) -> Tuple[str, dict]:
        if URI.startswith('vmess://'):
            return ConfigurationXray.URI2ProxyOutboundObjectVMess(URI)

        if URI.startswith('vless://'):
            return ConfigurationXray.URI2ProxyOutboundObjectVLESS(URI)

        if URI.startswith('ss://'):
            return ConfigurationXray.URI2ProxyOutboundObjectSS(URI)

        if URI.startswith('trojan://'):
            return ConfigurationXray.URI2ProxyOutboundObjectTrojan(URI)

        raise ValueError(f'Unrecognized URI scheme {URI}')

    @property
    def itemRemark(self) -> str:
        return self.getExtras('remark')

    @property
    def itemProtocol(self) -> str:
        return protocolRepr(self.proxyProtocol)

    @property
    def itemAddress(self) -> str:
        addr = self.proxyServerObject.get('address', '')

        return str(addr)

    @property
    def itemPort(self) -> str:
        port = self.proxyServerObject.get('port', '')

        return str(port)

    @property
    def itemTransport(self) -> str:
        return self.proxyStreamSettingsNetwork

    @property
    def itemTLS(self) -> str:
        return self.proxyStreamSettingsTLS

    @property
    def itemLatency(self) -> str:
        # Backward compatibility
        return self.getExtras('delayResult')

    @property
    def itemSpeed(self) -> str:
        # Backward compatibility
        return self.getExtras('speedResult')

    def toJSONString(self, **kwargs) -> str:
        indent = kwargs.pop('indent', 2)

        return super().toJSONString(indent=indent)

    def toURI(self, remark: str = '') -> str:
        if remark == '':
            override = self.itemRemark
        else:
            override = remark

        if self.proxyProtocol.lower() == 'vmess':
            netloc = PyBase64Encoder.encode(
                UJSONEncoder.encode(
                    {
                        'v': '2',
                        'ps': override,
                        **{
                            key: str(self.proxyServerObject[value])
                            for key, value in {
                                'add': 'address',
                                'port': 'port',
                            }.items()
                        },
                        **{
                            key: str(self.proxyUserObject[value])
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

            return urlunparse(['vless', netloc, '', '', query, quote(override)])

        if self.proxyProtocol.lower() == 'shadowsocks':
            method, password, address, port = list(
                self.proxyServerObject[value]
                for value in ['method', 'password', 'address', 'port']
            )

            netloc = f'{quote(method)}:{quote(password)}@{address}:{port}'

            return urlunparse(['ss', netloc, '', '', '', quote(override)])

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

            return urlunparse(['trojan', netloc, '', '', query, quote(override)])

        # Unrecognized protocol
        return ''

    def fromURI(self, URI: str) -> bool:
        try:
            remark, proxyOutboundObject = ConfigurationXray.URI2ProxyOutboundObject(URI)

            dict.__init__(
                self,
                **{
                    # log
                    'log': {
                        'access': '',
                        'error': '',
                        'loglevel': 'warning',
                    },
                    # inbounds
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
                    # outbounds
                    'outbounds': [
                        # proxy
                        proxyOutboundObject,
                        # direct
                        {
                            'tag': 'direct',
                            'protocol': 'freedom',
                            'settings': {},
                        },
                        # block
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
                    # routing
                    'routing': {},
                },
            )

            self.setExtras('remark', remark)

            return True
        except Exception:
            # Any non-exit exceptions

            return False

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
            if self.get('inbounds') is None:
                self['inbounds'] = []

            if not isinstance(self['inbounds'], list):
                self['inbounds'] = []

            if endpoint == '':
                for inbound in self['inbounds']:
                    if inbound['protocol'] == 'http':
                        self['inbounds'].remove(inbound)

                        # Remove first chosen
                        return True

                # None satisfied. Return success
                return True

            listen, port = parseHostPort(endpoint)

            for inbound in self['inbounds']:
                if inbound['protocol'] == 'http':
                    # Note: If there are multiple http inbounds
                    # satisfied, the first one will be chosen.
                    inbound['listen'], inbound['port'] = listen, int(port)

                    return True

            # No entry. Add new one
            self['inbounds'].append(
                {
                    'tag': 'http',
                    'port': int(port),
                    'listen': listen,
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
                }
            )

            return True
        except Exception:
            # Any non-exit exceptions

            return False

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        try:
            if self.get('inbounds') is None:
                self['inbounds'] = []

            if not isinstance(self['inbounds'], list):
                self['inbounds'] = []

            if endpoint == '':
                for inbound in self['inbounds']:
                    if inbound['protocol'] == 'socks':
                        self['inbounds'].remove(inbound)

                        # Remove first chosen
                        return True

                # None satisfied. Return success
                return True

            listen, port = parseHostPort(endpoint)

            for inbound in self['inbounds']:
                if inbound['protocol'] == 'socks':
                    # Note: If there are multiple socks inbounds
                    # satisfied, the first one will be chosen.
                    inbound['listen'], inbound['port'] = listen, int(port)

                    return True

            # No entry. Add new one
            self['inbounds'].append(
                {
                    'tag': 'socks',
                    'port': int(port),
                    'listen': listen,
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
                }
            )

            return True
        except Exception:
            # Any non-exit exceptions

            return False


class ConfigurationHysteria1(ConfigurationFactory):
    def __init__(self, config: Union[str, dict] = '', **kwargs):
        super().__init__(config, **kwargs)

    def coreName(self):
        return 'Hysteria1'

    @property
    def itemRemark(self) -> str:
        return self.getExtras('remark')

    @property
    def itemProtocol(self) -> str:
        return Protocol.Hysteria1

    @property
    def itemAddress(self) -> str:
        server = self.get('server', '')

        pos = server.rfind(':')

        if pos == -1:
            return server
        else:
            return server[:pos]

    @property
    def itemPort(self) -> str:
        server = self.get('server', '')

        pos = server.rfind(':')

        if pos == -1:
            return ''
        else:
            return server[pos + 1 :]

    @property
    def itemTransport(self) -> str:
        return ''

    @property
    def itemTLS(self) -> str:
        return ''

    @property
    def itemLatency(self) -> str:
        return self.getExtras('delayResult')

    @property
    def itemSpeed(self) -> str:
        return self.getExtras('speedResult')

    def toJSONString(self, **kwargs) -> str:
        indent = kwargs.pop('indent', 4)

        return super().toJSONString(indent=indent)

    def toURI(self, remark: str = '') -> str:
        if remark == '':
            override = self.itemRemark
        else:
            override = remark

        try:
            netloc, mport = self['server'].split(',')
        except Exception:
            # Any non-exit exceptions

            netloc, mport = self['server'], ''

        if mport:
            mportArgs = {'mport': mport}
        else:
            mportArgs = {}

        protocol = self.get('protocol', 'udp')

        if self.get('auth_str'):
            # auth in string
            authArgs = {'auth': self['auth_str']}
        else:
            authArgs = {}

        if self.get('server_name'):
            peerArgs = {'peer': self['server_name']}
        else:
            peerArgs = {}

        if self.get('insecure') is True:
            insecureArgs = {'insecure': '1'}
        else:
            insecureArgs = {}

        upmbps = self['up_mbps']
        downmbps = self['down_mbps']

        if self.get('alpn'):
            alpnArgs = {'alpn': self['alpn']}
        else:
            alpnArgs = {}

        if self.get('obfs'):
            obfsParamArgs = {'obfsParam': self['obfs']}
        else:
            obfsParamArgs = {}

        query = '&'.join(
            f'{key}={value}'
            for key, value in {
                **mportArgs,
                'protocol': protocol,
                **authArgs,
                **peerArgs,
                **insecureArgs,
                'upmbps': upmbps,
                'downmbps': downmbps,
                **alpnArgs,
                **obfsParamArgs,
            }.items()
        )

        return urlunparse(['hysteria', netloc, '', '', query, quote(override)])

    def fromURI(self, URI: str) -> bool:
        try:
            result = urlparse(URI)
            remark = unquote(result.fragment)
            queryObject = {key: value for key, value in parse_qsl(result.query)}

            if result.scheme != 'hysteria':
                raise ValueError('Invalid hysteria1 URI scheme')

            server = result.netloc

            mport = queryObject.get('mport', '')

            if mport:
                server += f',{mport}'

            protocol = queryObject.get('protocol', 'udp')

            if queryObject.get('auth', ''):
                # auth in string
                authArgs = {'auth_str': queryObject['auth']}
            else:
                authArgs = {}

            if queryObject.get('peer', ''):
                peerArgs = {'server_name': queryObject['peer']}
            else:
                peerArgs = {}

            insecure = queryObject.get('insecure', False)

            if isinstance(insecure, bool):
                pass
            elif insecure == '1':
                insecure = True
            else:
                insecure = False

            upmbps = queryObject.get('upmbps', 24)
            downmbps = queryObject.get('downmbps', 96)

            if queryObject.get('alpn', ''):
                alpnArgs = {'alpn': queryObject['alpn']}
            else:
                alpnArgs = {}

            # obfs mode seems not required, ignored...

            if queryObject.get('obfsParam', ''):
                obfsParamArgs = {'obfs': queryObject['obfsParam']}
            else:
                obfsParamArgs = {}

            dict.__init__(
                self,
                **{
                    'server': server,
                    'protocol': protocol,
                    **authArgs,
                    **obfsParamArgs,
                    'up_mbps': int(upmbps),
                    'down_mbps': int(downmbps),
                    **peerArgs,
                    **alpnArgs,
                    'insecure': insecure,
                    'socks5': {
                        'listen': '127.0.0.1:10808',
                    },
                    'http': {
                        'listen': '127.0.0.1:10809',
                    },
                },
            )

            self.setExtras('remark', remark)

            return True
        except Exception:
            # Any non-exit exceptions

            return False

    def httpProxyEndpoint(self) -> str:
        try:
            return self['http']['listen']
        except Exception:
            # Any non-exit exceptions

            return ''

    def socksProxyEndpoint(self) -> str:
        try:
            return self['socks5']['listen']
        except Exception:
            # Any non-exit exceptions

            return ''

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        try:
            if endpoint == '':
                self.pop('http', None)

                return True

            if self.get('http') is None:
                self['http'] = {}

            self['http']['listen'] = endpoint

            return True
        except Exception:
            # Any non-exit exceptions

            return False

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        try:
            if endpoint == '':
                self.pop('socks5', None)

                return True

            if self.get('socks5') is None:
                self['socks5'] = {}

            self['socks5']['listen'] = endpoint

            return True
        except Exception:
            # Any non-exit exceptions

            return False


class ConfigurationHysteria2(ConfigurationFactory):
    def __init__(self, config: Union[str, dict] = '', **kwargs):
        super().__init__(config, **kwargs)

    def coreName(self):
        return 'Hysteria2'

    @property
    def itemRemark(self) -> str:
        return self.getExtras('remark')

    @property
    def itemProtocol(self) -> str:
        return Protocol.Hysteria2

    @property
    def itemAddress(self) -> str:
        server = self.get('server', '')

        pos = server.rfind(':')

        if pos == -1:
            return server
        else:
            return server[:pos]

    @property
    def itemPort(self) -> str:
        server = self.get('server', '')

        pos = server.rfind(':')

        if pos == -1:
            return ''
        else:
            return server[pos + 1 :]

    @property
    def itemTransport(self) -> str:
        return ''

    @property
    def itemTLS(self) -> str:
        return ''

    @property
    def itemLatency(self) -> str:
        return self.getExtras('delayResult')

    @property
    def itemSpeed(self) -> str:
        return self.getExtras('speedResult')

    def toJSONString(self, **kwargs) -> str:
        indent = kwargs.pop('indent', 4)

        return super().toJSONString(indent=indent)

    def toURI(self, remark: str = '') -> str:
        if remark == '':
            override = self.itemRemark
        else:
            override = remark

        netloc = self['auth'] + '@' + self['server']

        TLSArg, obfsArg = {}, {}

        if self.get('tls'):
            if self['tls'].get('sni'):
                TLSArg['sni'] = self['tls']['sni']

            if self['tls'].get('insecure') is True:
                TLSArg['insecure'] = '1'
            else:
                TLSArg['insecure'] = '0'

            if self['tls'].get('pinSHA256'):
                TLSArg['pinSHA256'] = self['tls']['pinSHA256']

        if self.get('obfs'):
            obfsType = self['obfs'].get('type', 'salamander')

            obfsArg['obfs'] = obfsType
            obfsArg['obfs-password'] = self['obfs'][obfsType]['password']

        query = '&'.join(
            f'{key}={value}'
            for key, value in {
                **TLSArg,
                **obfsArg,
            }.items()
        )

        return urlunparse(['hysteria2', netloc, '', '', query, quote(override)])

    def fromURI(self, URI: str) -> bool:
        try:
            result = urlparse(URI)
            remark = unquote(result.fragment)
            queryObject = {key: value for key, value in parse_qsl(result.query)}

            if result.scheme != 'hysteria2' and result.scheme != 'hy2':
                raise ValueError('Invalid hysteria2 URI scheme')

            auth, server = result.netloc.split('@')

            obfs = queryObject.get('obfs', '')
            obfsPassword = queryObject.get('obfs-password', '')
            sni = queryObject.get('sni', '')

            insecure = queryObject.get('insecure', False)

            if isinstance(insecure, bool):
                pass
            elif insecure == '1':
                insecure = True
            else:
                insecure = False

            pinSHA256 = queryObject.get('pinSHA256', '')

            obfsArg = {}
            pinSHA256Arg = {}

            if obfs and obfsPassword:
                obfsArg['obfs'] = {
                    'type': obfs,
                    obfs: {
                        'password': obfsPassword,
                    },
                }

            if pinSHA256:
                pinSHA256Arg['pinSHA256'] = pinSHA256

            dict.__init__(
                self,
                **{
                    'server': server,
                    'auth': auth,
                    **obfsArg,
                    'tls': {
                        'sni': sni,
                        'insecure': insecure,
                        **pinSHA256Arg,
                    },
                    'socks5': {
                        'listen': '127.0.0.1:10808',
                    },
                    'http': {
                        'listen': '127.0.0.1:10809',
                    },
                },
            )

            self.setExtras('remark', remark)

            return True
        except Exception:
            # Any non-exit exceptions

            return False

    def httpProxyEndpoint(self) -> str:
        try:
            return self['http']['listen']
        except Exception:
            # Any non-exit exceptions

            return ''

    def socksProxyEndpoint(self) -> str:
        try:
            return self['socks5']['listen']
        except Exception:
            # Any non-exit exceptions

            return ''

    def setHttpProxyEndpoint(self, endpoint: str) -> bool:
        try:
            if endpoint == '':
                self.pop('http', None)

                return True

            if self.get('http') is None:
                self['http'] = {}

            self['http']['listen'] = endpoint

            return True
        except Exception:
            # Any non-exit exceptions

            return False

    def setSocksProxyEndpoint(self, endpoint: str) -> bool:
        try:
            if endpoint == '':
                self.pop('socks5', None)

                return True

            if self.get('socks5') is None:
                self['socks5'] = {}

            self['socks5']['listen'] = endpoint

            return True
        except Exception:
            # Any non-exit exceptions

            return False


def constructFromDict(config: dict, **kwargs) -> ConfigurationFactory:
    if not isinstance(config, dict):
        return ConfigurationFactory()

    def hasField(field):
        return config.get(field) is not None

    if hasField('inbounds') or hasField('outbounds'):
        # Assuming is Xray-Core
        return ConfigurationXray(config, **kwargs)

    if hasField('server'):
        if (
            hasField('protocol')
            or hasField('up_mbps')
            or hasField('down_mbps')
            or hasField('auth_str')
            or hasField('alpn')
            or hasField('server_name')
            or hasField('insecure')
            or hasField('recv_window_conn')
            or hasField('recv_window')
            or isinstance(config.get('obfs'), str)
            or hasField('fast_open')
            or hasField('lazy_start')
        ):
            return ConfigurationHysteria1(config, **kwargs)
        if (
            hasField('tls')
            or hasField('transport')
            or hasField('quic')
            or hasField('bandwidth')
            or hasField('tcpForwarding')
            or hasField('udpForwarding')
            or hasField('tcpTProxy')
            or hasField('udpTProxy')
            or isinstance(config.get('obfs'), dict)
            or hasField('fastOpen')
            or hasField('lazy')
        ):
            return ConfigurationHysteria2(config, **kwargs)

    # Copied to factory unrecognized
    return ConfigurationFactory(config, **kwargs)


def constructFromAny(config: Union[str, dict], **kwargs) -> ConfigurationFactory:
    if isinstance(config, str):
        if (
            config.startswith('vmess://')
            or config.startswith('vless://')
            or config.startswith('ss://')
            or config.startswith('trojan://')
        ):
            return ConfigurationXray(config, **kwargs)
        if config.startswith('hysteria://'):
            return ConfigurationHysteria1(config, **kwargs)
        if config.startswith('hy2://') or config.startswith('hysteria2://'):
            return ConfigurationHysteria2(config, **kwargs)

        try:
            # Try to construct from JSON string
            return constructFromDict(UJSONEncoder.decode(config), **kwargs)
        except Exception:
            # Any non-exit exceptions

            return ConfigurationFactory(**kwargs)

    if isinstance(config, dict):
        return constructFromDict(config, **kwargs)

    return ConfigurationFactory(**kwargs)
