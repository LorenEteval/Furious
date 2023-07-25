from Furious.Core.Core import XrayCore
from Furious.Core.Intellisense import Intellisense
from Furious.Widget.Widget import MessageBox
from Furious.Utility.Constants import APPLICATION_NAME
from Furious.Utility.Utility import Base64Encoder, bootstrapIcon
from Furious.Utility.Translator import gettext as _

import copy
import ujson
import functools
import urllib.parse

quote = functools.partial(urllib.parse.quote)
unquote = functools.partial(urllib.parse.unquote)
urlunparse = functools.partial(urllib.parse.urlunparse)


class UnsupportedServerExport(Exception):
    pass


class Configuration:
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
    def export(remark, ob):
        if Intellisense.getCoreType(ob) == XrayCore.name():

            def hasKey(obj, key):
                return obj.get(key) is not None

            def getStreamNetSettings(protocol, streamObject, netType):
                kwargs = {}

                netobj = streamObject[
                    ProxyOutboundObject.getStreamNetworkSettingsName(netType)
                ]

                if netType == 'tcp':
                    try:
                        if protocol.lower() == 'vmess':
                            kwargs['type'] = netobj['header']['type']

                        if protocol.lower() == 'vless':
                            kwargs['headerType'] = netobj['header']['type']
                    except Exception:
                        # Any non-exit exceptions

                        pass

                elif netType == 'kcp':
                    try:
                        # Get order matters here
                        if protocol.lower() == 'vmess':
                            if hasKey(netobj, 'seed'):
                                kwargs['path'] = netobj['seed']

                            kwargs['type'] = netobj['header']['type']

                        if protocol.lower() == 'vless':
                            if hasKey(netobj, 'seed'):
                                kwargs['seed'] = netobj['seed']

                            kwargs['headerType'] = netobj['header']['type']
                    except Exception:
                        # Any non-exit exceptions

                        pass

                elif netType == 'ws':
                    try:
                        # Get order matters here
                        if hasKey(netobj, 'path'):
                            kwargs['path'] = quote(netobj['path'])

                        if netobj['headers']['Host']:
                            kwargs['host'] = quote(netobj['headers']['Host'])
                    except Exception:
                        # Any non-exit exceptions

                        pass

                elif netType == 'h2' or netType == 'http':
                    try:
                        # Get order matters here
                        if hasKey(netobj, 'path'):
                            kwargs['path'] = quote(netobj['path'])

                        kwargs['host'] = quote(','.join(netobj['host']))
                    except Exception:
                        # Any non-exit exceptions

                        pass

                elif netType == 'quic':
                    try:
                        # Get order matters here
                        if protocol.lower() == 'vmess':
                            if hasKey(netobj, 'security'):
                                kwargs['host'] = netobj['security']

                            if hasKey(netobj, 'key'):
                                kwargs['path'] = quote(netobj['key'])

                            kwargs['type'] = netobj['header']['type']

                        if protocol.lower() == 'vless':
                            if hasKey(netobj, 'security'):
                                kwargs['quicSecurity'] = netobj['security']

                            if hasKey(netobj, 'key'):
                                kwargs['path'] = quote(netobj['key'])

                            kwargs['headerType'] = netobj['header']['type']
                    except Exception:
                        # Any non-exit exceptions

                        pass

                elif netType == 'grpc':
                    if protocol.lower() == 'vmess':
                        if hasKey(netobj, 'serviceName'):
                            kwargs['path'] = netobj['serviceName']

                    if protocol.lower() == 'vless':
                        if hasKey(netobj, 'serviceName'):
                            kwargs['serviceName'] = netobj['serviceName']

                return kwargs

            def getStreamTLSSettings(streamObject, tlsType):
                if tlsType == 'none':
                    return {}

                kwargs = {}

                tlsobj = streamObject[
                    ProxyOutboundObject.getStreamTLSSettingsName(tlsType)
                ]

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

            # Begin export
            coreProtocol = Intellisense.getCoreProtocol(ob).lower()

            if coreProtocol == 'vmess' or coreProtocol == 'vless':
                proxyOutbound = None

                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        proxyOutbound = outbound

                        break

                if proxyOutbound is None:
                    raise Exception('No proxy outbound found')

                proxyServer = proxyOutbound['settings']['vnext'][0]
                proxyServerUser = proxyServer['users'][0]

                proxyStream = proxyOutbound['streamSettings']
                proxyStreamNet = proxyStream['network']
                proxyStreamTLS = proxyStream['security']

                if coreProtocol == 'vmess':
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
                                    **getStreamNetSettings(
                                        coreProtocol, proxyStream, proxyStreamNet
                                    ),
                                    **getStreamTLSSettings(proxyStream, proxyStreamTLS),
                                },
                                ensure_ascii=False,
                                escape_forward_slashes=False,
                            ).encode()
                        ).decode()
                    )

                if coreProtocol == 'vless':
                    flowArg = {}

                    if proxyServerUser.get('flow'):
                        flowArg['flow'] = proxyServerUser['flow']

                    netloc = f'{proxyServerUser["id"]}@{proxyServer["address"]}:{proxyServer["port"]}'

                    query = '&'.join(
                        f'{key}={value}'
                        for key, value in {
                            'encryption': proxyServerUser['encryption'],
                            'type': proxyStreamNet,
                            'security': proxyStreamTLS,
                            # kwargs
                            **flowArg,
                            **getStreamNetSettings(
                                coreProtocol, proxyStream, proxyStreamNet
                            ),
                            **getStreamTLSSettings(proxyStream, proxyStreamTLS),
                        }.items()
                    )

                    return urlunparse(['vless', netloc, '', '', query, quote(remark)])
        else:
            raise UnsupportedServerExport('Unsupported core protocol export')


class ProxyOutboundObject:
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
            sni = self.kwargs.get('sni', self.remote_host)
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
    def getStreamTLSSettingsName(security):
        # tlsSettings, realitySettings
        return f'{security}Settings'

    @staticmethod
    def getStreamNetworkSettingsName(type_):
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
                TcpObject['header'] = {
                    'type': self.kwargs.get('headerType', 'none'),
                }

            return TcpObject

        elif self.type_ == 'kcp':
            KcpObject = {
                # Extension. From V2rayN
                'uplinkCapacity': 12,
                'downlinkCapacity': 100,
            }

            if self.kwargs.get('headerType', 'none'):
                KcpObject['header'] = {
                    'type': self.kwargs.get('headerType', 'none'),
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
                QuicObject['header'] = {
                    'type': self.kwargs.get('headerType', 'none'),
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
                'email': 'user@Furious.GUI',
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
                'email': 'user@Furious.GUI',
            }

            if self.kwargs.get('flow'):
                # flow is empty, TLS. Otherwise, XTLS.
                UserObject['flow'] = self.kwargs.get('flow')

            return UserObject

        return {}

    def build(self):
        myJSON = {
            'tag': 'proxy',
            'protocol': self.protocol,
            'settings': {
                'vnext': [
                    {
                        'address': self.remote_host,
                        'port': self.remote_port,
                        'users': [
                            self.getUserObject(),
                        ],
                    },
                ]
            },
            'streamSettings': {
                'network': self.type_,
                'security': self.security,
            },
            'mux': {
                'enabled': False,
                'concurrency': -1,
            },
        }

        if self.security != 'none':
            # tlsSettings, realitySettings
            myJSON['streamSettings'][
                ProxyOutboundObject.getStreamTLSSettingsName(self.security)
            ] = self.getTLSSettings(self.security)

        # Stream network settings
        myJSON['streamSettings'][
            ProxyOutboundObject.getStreamNetworkSettingsName(self.type_)
        ] = self.getStreamNetworkSettings()

        return myJSON


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
    DEFAULT_CONF = {
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
        return copy.deepcopy(XrayCoreConfiguration.DEFAULT_CONF)

    @staticmethod
    def build(proxyOutboundObject):
        # log, inbounds
        myJSON = XrayCoreConfiguration.getDefaultJSON()

        # Add outbounds
        myJSON['outbounds'] = Outbounds(proxyOutboundObject).build()

        # Add empty routing
        myJSON['routing'] = {}

        return myJSON
