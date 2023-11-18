# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Core.Core import XrayCore, Hysteria2
from Furious.Core.Intellisense import Intellisense
from Furious.Widget.Widget import MessageBox
from Furious.Utility.Constants import APPLICATION_NAME, PROXY_OUTBOUND_USER_EMAIL
from Furious.Utility.Utility import Base64Encoder, Protocol, bootstrapIcon
from Furious.Utility.Translator import gettext as _

import copy
import ujson
import functools
import urllib.parse

# '/' will be quoted for V2rayN compatibility.
quote = functools.partial(urllib.parse.quote, safe='')
unquote = functools.partial(urllib.parse.unquote)
urlunparse = functools.partial(urllib.parse.urlunparse)


class UnsupportedServerExport(Exception):
    pass


class ExportFactory:
    def export(self, remark, jsonObject):
        raise NotImplementedError


class XrayFactory:
    @staticmethod
    def streamTLSSettings(streamObject, tlsType):
        kwargs = {}

        if tlsType == '' or tlsType == 'none':
            return kwargs

        tlsobj = streamObject[ProxyOutboundObject.streamTLSKey(tlsType)]

        if tlsType == 'reality' or tlsType == 'tls':
            if tlsobj.get('fingerprint'):
                kwargs['fp'] = tlsobj['fingerprint']

            if tlsobj.get('serverName'):
                kwargs['sni'] = tlsobj['serverName']

            if tlsobj.get('alpn'):
                kwargs['alpn'] = quote(','.join(tlsobj['alpn']))

        if tlsType == 'reality':
            # More kwargs for reality
            if tlsobj.get('publicKey'):
                kwargs['pbk'] = tlsobj['publicKey']

            if tlsobj.get('shortId'):
                kwargs['sid'] = tlsobj['shortId']

            if tlsobj.get('spiderX'):
                kwargs['spx'] = quote(tlsobj['spiderX'])

        return kwargs

    @staticmethod
    def getProxyOutboundObject(jsonObject):
        for outboundObject in jsonObject['outbounds']:
            if outboundObject['tag'] == 'proxy':
                return outboundObject

        raise Exception('No proxy outbound found')


class ExportVMess(ExportFactory):
    @staticmethod
    def streamNetSettings(streamObject, netType):
        kwargs = {}

        netobj = streamObject.get(ProxyOutboundObject.streamNetworkKey(netType))

        if netobj is None:
            return kwargs

        def hasKey(key):
            return netobj.get(key) is not None

        if netType == 'tcp':
            try:
                kwargs['type'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'kcp':
            try:
                # Get order matters here
                if hasKey('seed'):
                    kwargs['path'] = netobj['seed']

                kwargs['type'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'ws':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(netobj['path'])

                if netobj['headers']['Host']:
                    kwargs['host'] = quote(netobj['headers']['Host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'h2' or netType == 'http':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(netobj['path'])

                kwargs['host'] = quote(','.join(netobj['host']))
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'quic':
            try:
                # Get order matters here
                if hasKey('security'):
                    kwargs['host'] = netobj['security']

                if hasKey('key'):
                    kwargs['path'] = quote(netobj['key'])

                kwargs['type'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'grpc':
            if hasKey('serviceName'):
                kwargs['path'] = netobj['serviceName']

        return kwargs

    def export(self, remark, jsonObject):
        proxyOutbound = XrayFactory.getProxyOutboundObject(jsonObject)

        proxyServer = proxyOutbound['settings']['vnext'][0]
        proxyServerUser = proxyServer['users'][0]

        proxyStream, proxyStreamNet, proxyStreamTLS = (
            proxyOutbound['streamSettings'],
            proxyOutbound['streamSettings']['network'],
            proxyOutbound['streamSettings'].get('security', 'none'),
        )

        return (
            'vmess://'
            + Base64Encoder.encode(
                ujson.dumps(
                    {
                        'v': '2',
                        'ps': quote(remark),
                        'add': proxyServer['address'],
                        'port': proxyServer['port'],
                        'id': proxyServerUser['id'],
                        'aid': proxyServerUser['alterId'],
                        'scy': proxyServerUser['security'],
                        'net': proxyStreamNet,
                        'tls': proxyStreamTLS,
                        # kwargs
                        **ExportVMess.streamNetSettings(proxyStream, proxyStreamNet),
                        **XrayFactory.streamTLSSettings(proxyStream, proxyStreamTLS),
                    },
                    ensure_ascii=False,
                    escape_forward_slashes=False,
                ).encode()
            ).decode()
        )


class ExportVLESS(ExportFactory):
    @staticmethod
    def streamNetSettings(streamObject, netType):
        kwargs = {}

        netobj = streamObject.get(ProxyOutboundObject.streamNetworkKey(netType))

        if netobj is None:
            return kwargs

        def hasKey(key):
            return netobj.get(key) is not None

        if netType == 'tcp':
            try:
                kwargs['headerType'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'kcp':
            try:
                # Get order matters here
                if hasKey('seed'):
                    kwargs['seed'] = netobj['seed']

                kwargs['headerType'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'ws':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(netobj['path'])

                if netobj['headers']['Host']:
                    kwargs['host'] = quote(netobj['headers']['Host'])
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'h2' or netType == 'http':
            try:
                # Get order matters here
                if hasKey('path'):
                    kwargs['path'] = quote(netobj['path'])

                kwargs['host'] = quote(','.join(netobj['host']))
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'quic':
            try:
                # Get order matters here
                if hasKey('security'):
                    kwargs['quicSecurity'] = netobj['security']

                if hasKey('key'):
                    kwargs['path'] = quote(netobj['key'])

                kwargs['headerType'] = netobj['header']['type']
            except Exception:
                # Any non-exit exceptions

                pass

        elif netType == 'grpc':
            if hasKey('serviceName'):
                kwargs['serviceName'] = netobj['serviceName']

        return kwargs

    def export(self, remark, jsonObject):
        proxyOutbound = XrayFactory.getProxyOutboundObject(jsonObject)

        proxyServer = proxyOutbound['settings']['vnext'][0]
        proxyServerUser = proxyServer['users'][0]

        proxyStream, proxyStreamNet, proxyStreamTLS = (
            proxyOutbound['streamSettings'],
            proxyOutbound['streamSettings']['network'],
            proxyOutbound['streamSettings'].get('security', 'none'),
        )

        flowArg = {}

        if proxyServerUser.get('flow'):
            flowArg['flow'] = proxyServerUser['flow']

        netloc = (
            f'{proxyServerUser["id"]}@{proxyServer["address"]}:{proxyServer["port"]}'
        )

        query = '&'.join(
            f'{key}={value}'
            for key, value in {
                'encryption': proxyServerUser['encryption'],
                'type': proxyStreamNet,
                'security': proxyStreamTLS,
                # kwargs
                **flowArg,
                **ExportVLESS.streamNetSettings(proxyStream, proxyStreamNet),
                **XrayFactory.streamTLSSettings(proxyStream, proxyStreamTLS),
            }.items()
        )

        return urlunparse(['vless', netloc, '', '', query, quote(remark)])


class ExportSS(ExportVLESS):
    def export(self, remark, jsonObject):
        proxyOutbound = XrayFactory.getProxyOutboundObject(jsonObject)

        proxyServer = proxyOutbound['settings']['servers'][0]

        method, password, address, port = (
            proxyServer['method'],
            proxyServer['password'],
            proxyServer['address'],
            proxyServer['port'],
        )

        netloc = f'{quote(method)}:{quote(password)}@{address}:{port}'

        return urlunparse(['ss', netloc, '', '', '', quote(remark)])


class ExportTrojan(ExportVLESS):
    def export(self, remark, jsonObject):
        proxyOutbound = XrayFactory.getProxyOutboundObject(jsonObject)

        proxyServer = proxyOutbound['settings']['servers'][0]

        password, address, port = (
            proxyServer['password'],
            proxyServer['address'],
            proxyServer['port'],
        )

        proxyStream, proxyStreamNet, proxyStreamTLS = (
            proxyOutbound['streamSettings'],
            proxyOutbound['streamSettings']['network'],
            proxyOutbound['streamSettings'].get('security', 'none'),
        )

        netloc = f'{quote(password)}@{address}:{port}'

        query = '&'.join(
            f'{key}={value}'
            for key, value in {
                'type': proxyStreamNet,
                'security': proxyStreamTLS,
                # kwargs
                **ExportVLESS.streamNetSettings(proxyStream, proxyStreamNet),
                **XrayFactory.streamTLSSettings(proxyStream, proxyStreamTLS),
            }.items()
        )

        return urlunparse(['trojan', netloc, '', '', query, quote(remark)])


class Configuration:
    ExportClassMap = {
        Protocol.VMess: ExportVMess,
        Protocol.VLESS: ExportVLESS,
        Protocol.Shadowsocks: ExportSS,
        Protocol.Trojan: ExportTrojan,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def toJSON(text):
        return ujson.loads(text)

    @staticmethod
    def corruptedError(errorBox, isAsync=False):
        assert isinstance(errorBox, MessageBox)

        errorBox.setIcon(MessageBox.Icon.Critical)
        errorBox.setWindowTitle(_('Server configuration corrupted'))
        errorBox.setText(
            _(
                f'{APPLICATION_NAME} cannot restore your server configuration. '
                f'It may have been tampered with.'
            )
        )
        errorBox.setInformativeText(
            _(f'The configuration content has been cleared by {APPLICATION_NAME}.')
        )

        if isAsync:
            # Show the MessageBox asynchronously
            errorBox.open()
        else:
            # Show the MessageBox and wait for user to close it
            errorBox.exec()

    @staticmethod
    def export(remark, jsonObject):
        if Intellisense.getCoreType(jsonObject) == XrayCore.name():
            # def getExportObject():
            #     protocol = Intellisense.getCoreProtocol(jsonObject)
            #
            #     return Configuration.ExportClassMap[protocol]()

            from Furious.Library.Configuration import ConfigurationXray

            return ConfigurationXray(jsonObject).toURI(remark)

        if Intellisense.getCoreType(jsonObject) == Hysteria2.name():
            from Furious.Library.Configuration import ConfigurationHysteria2

            return ConfigurationHysteria2(jsonObject).toURI(remark)

            # netloc = f'{jsonObject["auth"]}@{jsonObject["server"]}'
            #
            # tlsArg, obfsArg = {}, {}
            #
            # if jsonObject.get('tls'):
            #     if jsonObject['tls'].get('sni'):
            #         tlsArg['sni'] = jsonObject['tls']['sni']
            #
            #     if jsonObject['tls'].get('insecure') is True:
            #         tlsArg['insecure'] = '1'
            #     else:
            #         tlsArg['insecure'] = '0'
            #
            #     if jsonObject['tls'].get('pinSHA256'):
            #         tlsArg['pinSHA256'] = jsonObject['tls']['pinSHA256']
            #
            # if jsonObject.get('obfs'):
            #     obfsType = jsonObject['obfs'].get('type', 'salamander')
            #
            #     obfsArg['obfs'] = obfsType
            #     obfsArg['obfs-password'] = jsonObject['obfs'][obfsType]['password']
            #
            # query = '&'.join(
            #     f'{key}={value}'
            #     for key, value in {
            #         **tlsArg,
            #         **obfsArg,
            #     }.items()
            # )
            #
            # return urlunparse(['hysteria2', netloc, '', '', query, quote(remark)])

        raise UnsupportedServerExport('Unsupported core protocol export')


class OutboundObject:
    def __init__(self):
        super().__init__()

    def build(self):
        raise NotImplementedError


class ProxyOutboundObject(OutboundObject):
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
        super().__init__()

        self.protocol = protocol
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.uuid_ = uuid_
        self.encryption = encryption
        self.type_ = type_
        self.security = security

        self.kwargs = kwargs

    def getTLSSettings(self, security):
        TLSObject = {}

        if security == 'reality' or security == 'tls':
            # Note: If specify default value 'chrome', some share link fails.
            # Leave default value as empty
            fp = self.kwargs.get('fp')
            sni = self.kwargs.get('sni')
            # Protect "xxx," format
            alpn = list(
                filter(
                    lambda x: x != '',
                    unquote(self.kwargs.get('alpn', '')).split(','),
                )
            )

            if fp:
                TLSObject['fingerprint'] = fp

            if sni:
                TLSObject['serverName'] = sni
            else:
                host = ''

                if self.protocol == 'vmess':
                    host = self.kwargs.get('host')

                if self.protocol == 'vless':
                    host = self.remote_host

                if host:
                    TLSObject['serverName'] = host

            if alpn:
                TLSObject['alpn'] = alpn

        if security == 'reality':
            # More args for reality
            pbk = self.kwargs.get('pbk')
            sid = self.kwargs.get('sid', '')
            spx = self.kwargs.get('spx', '')

            if pbk:
                TLSObject['publicKey'] = pbk

            TLSObject['shortId'] = sid
            TLSObject['spiderX'] = unquote(spx)

        return TLSObject

    @staticmethod
    def streamTLSKey(security):
        # tlsSettings, realitySettings
        return f'{security}Settings'

    @staticmethod
    @functools.lru_cache(None)
    def streamNetworkKey(type_):
        if type_ == 'h2':
            return 'httpSettings'
        else:
            return f'{type_}Settings'

    def getStreamNetworkSettings(self):
        # Note:
        # V2rayN share standard doesn't require unquote. Still
        # unquote value according to (VMess AEAD / VLESS) standard

        if self.type_ == 'tcp':
            TcpObject = {}

            if self.kwargs.get('headerType', 'none'):
                headerType = self.kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    TcpObject['header'] = {
                        'type': headerType,
                    }

                # Request settings for HTTP
                if headerType == 'http' and self.kwargs.get('host'):
                    TcpObject['header']['request'] = {
                        'version': '1.1',
                        'method': 'GET',
                        'path': [self.kwargs.get('path', '/')],
                        'headers': {
                            'Host': [unquote(self.kwargs.get('host'))],
                            'User-Agent': [
                                'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
                                'Mozilla/5.0 (iPhone; CPU iPhone OS 10_0_2 like Mac OS X) AppleWebKit/601.1 (KHTML, like Gecko) CriOS/53.0.2785.109 Mobile/14A456 Safari/601.1.46',
                            ],
                            'Accept-Encoding': ['gzip, deflate'],
                            'Connection': ['keep-alive'],
                            'Pragma': 'no-cache',
                        },
                    }

            return TcpObject

        elif self.type_ == 'kcp':
            KcpObject = {
                # Extension. From V2rayN
                'uplinkCapacity': 12,
                'downlinkCapacity': 100,
            }

            if self.kwargs.get('headerType', 'none'):
                headerType = self.kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    KcpObject['header'] = {
                        'type': headerType,
                    }

            if self.kwargs.get('seed'):
                KcpObject['seed'] = self.kwargs.get('seed')

            return KcpObject

        elif self.type_ == 'ws':
            WebSocketObject = {}

            if self.kwargs.get('path', '/'):
                WebSocketObject['path'] = unquote(self.kwargs.get('path', '/'))

            if self.kwargs.get('host'):
                WebSocketObject['headers'] = {
                    'Host': unquote(self.kwargs.get('host')),
                }

            return WebSocketObject

        elif self.type_ == 'h2' or self.type_ == 'http':
            HttpObject = {}

            if self.kwargs.get('host', self.remote_host):
                # Protect "xxx," format
                HttpObject['host'] = list(
                    filter(
                        lambda x: x != '',
                        unquote(self.kwargs.get('host', self.remote_host)).split(','),
                    )
                )

            if self.kwargs.get('path', '/'):
                HttpObject['path'] = unquote(self.kwargs.get('path', '/'))

            return HttpObject

        elif self.type_ == 'quic':
            QuicObject = {}

            if self.kwargs.get('quicSecurity', 'none'):
                QuicObject['security'] = self.kwargs.get('quicSecurity', 'none')

            if self.kwargs.get('key'):
                QuicObject['key'] = unquote(self.kwargs.get('key'))

            if self.kwargs.get('headerType', 'none'):
                headerType = self.kwargs.get('headerType', 'none')

                # Some dumb share link set this value to 'auto'. Protect it
                if headerType != 'auto':
                    QuicObject['header'] = {
                        'type': headerType,
                    }

            return QuicObject

        elif self.type_ == 'grpc':
            GRPCObject = {}

            if self.kwargs.get('serviceName'):
                GRPCObject['serviceName'] = self.kwargs.get('serviceName')

            if self.kwargs.get('mode', 'gun'):
                GRPCObject['multiMode'] = self.kwargs.get('mode', 'gun') == 'multi'

            return GRPCObject

    def getUserObject(self):
        if self.protocol == 'vmess':
            UserObject = {
                'id': self.uuid_,
                'security': self.encryption,
                # Extension
                'email': PROXY_OUTBOUND_USER_EMAIL,
            }

            # For VMess(V2rayN share standard) only.
            if self.kwargs.get('aid') is not None:
                UserObject['alterId'] = self.kwargs.get('aid')

            return UserObject

        if self.protocol == 'vless':
            UserObject = {
                'id': self.uuid_,
                'encryption': self.encryption,
                # Extension
                'email': PROXY_OUTBOUND_USER_EMAIL,
            }

            if self.kwargs.get('flow'):
                # flow is empty, TLS. Otherwise, XTLS.
                UserObject['flow'] = self.kwargs.get('flow')

            return UserObject

        return {}

    def getDefaultJSON(self):
        securityArgs = {}

        if self.security:
            securityArgs['security'] = self.security

        return {
            'tag': 'proxy',
            'protocol': self.protocol,
            'settings': {
                'vnext': [
                    {
                        'address': self.remote_host,
                        # self.remote_port is already an integer
                        'port': self.remote_port,
                        'users': [
                            self.getUserObject(),
                        ],
                    },
                ]
            },
            'streamSettings': {
                'network': self.type_,
                **securityArgs,
            },
            'mux': {
                'enabled': False,
                'concurrency': -1,
            },
        }

    def build(self):
        myJSON = self.getDefaultJSON()

        if self.security and self.security != 'none':
            # tlsSettings, realitySettings
            myJSON['streamSettings'][
                ProxyOutboundObject.streamTLSKey(self.security)
            ] = self.getTLSSettings(self.security)

        # Stream network settings
        myJSON['streamSettings'][
            ProxyOutboundObject.streamNetworkKey(self.type_)
        ] = self.getStreamNetworkSettings()

        return myJSON


class ProxyOutboundObjectSS(ProxyOutboundObject):
    def __init__(self, method, password, address, port):
        super().__init__('shadowsocks', address, port, password, '', 'tcp', '')

        self.method = method

    def getDefaultJSON(self):
        return {
            'tag': 'proxy',
            'protocol': self.protocol,
            'settings': {
                'servers': [
                    {
                        'address': self.remote_host,
                        'port': int(self.remote_port),
                        'method': self.method,
                        'password': self.uuid_,
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

    def build(self):
        return self.getDefaultJSON()


class ProxyOutboundObjectTrojan(ProxyOutboundObject):
    def __init__(self, password, address, port, type_, security, **kwargs):
        super().__init__(
            'trojan', address, port, password, '', type_, security, **kwargs
        )

    def getDefaultJSON(self):
        securityArgs = {}

        if self.security:
            securityArgs['security'] = self.security

        return {
            'tag': 'proxy',
            'protocol': self.protocol,
            'settings': {
                'servers': [
                    {
                        'address': self.remote_host,
                        'port': int(self.remote_port),
                        'password': self.uuid_,
                        'email': PROXY_OUTBOUND_USER_EMAIL,
                    },
                ]
            },
            'streamSettings': {
                'network': self.type_,
                **securityArgs,
            },
            'mux': {
                'enabled': False,
                'concurrency': -1,
            },
        }


class Outbounds:
    def __init__(self, proxyOutboundObject):
        self.proxyOutboundObject = proxyOutboundObject

    def build(self):
        return [
            # Proxy
            self.proxyOutboundObject.build(),
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
        ]


class XrayCoreConfiguration:
    DEFAULT_JSON = {
        # Default log configuration
        'log': {
            'access': '',
            'error': '',
            'loglevel': 'warning',
        },
        # Default inbounds configuration
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
    }

    @staticmethod
    def getDefaultJSON():
        return copy.deepcopy(XrayCoreConfiguration.DEFAULT_JSON)

    @staticmethod
    def build(proxyOutboundObject):
        # log, inbounds
        myJSON = XrayCoreConfiguration.getDefaultJSON()

        # Add outbounds
        myJSON['outbounds'] = Outbounds(proxyOutboundObject).build()

        # Add empty routing
        myJSON['routing'] = {}

        return myJSON


class Hysteria2Configuration:
    def __init__(self, server, auth, **kwargs):
        self.server = server
        self.auth = auth
        self.obfs = kwargs.get('obfs', '')
        self.obfsPassword = kwargs.get('obfs-password', '')
        self.sni = kwargs.get('sni', '')

        insecure = kwargs.get('insecure', False)

        if isinstance(insecure, bool):
            self.insecure = insecure
        elif insecure == '1':
            self.insecure = True
        else:
            self.insecure = False

        self.pinSHA256 = kwargs.get('pinSHA256', '')

    def build(self):
        obfsArg = {}
        pinSHA256Arg = {}

        if self.obfs and self.obfsPassword:
            obfsArg['obfs'] = {
                'type': self.obfs,
                self.obfs: {
                    'password': self.obfsPassword,
                },
            }

        if self.pinSHA256:
            pinSHA256Arg['pinSHA256'] = self.pinSHA256

        return {
            'server': self.server,
            'auth': self.auth,
            'tls': {
                'sni': self.sni,
                'insecure': self.insecure,
                **pinSHA256Arg,
            },
            **obfsArg,
            'socks5': {
                'listen': '127.0.0.1:10808',
            },
            'http': {
                'listen': '127.0.0.1:10809',
            },
        }
