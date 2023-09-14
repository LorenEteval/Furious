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

from Furious.Core.Core import XrayCore, Hysteria1, Hysteria2
from Furious.Utility.Utility import Protocol, protocolRepr


class Intellisense:
    @staticmethod
    def getCoreType(ob):
        def hasField(field):
            return ob.get(field) is not None

        if hasField('inbounds') or hasField('outbounds'):
            # Assuming is XrayCore
            return XrayCore.name()

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
                or isinstance(ob.get('obfs'), str)
                or hasField('fast_open')
                or hasField('lazy_start')
            ):
                return Hysteria1.name()
            elif (
                hasField('tls')
                or hasField('transport')
                or hasField('quic')
                or hasField('bandwidth')
                or hasField('tcpForwarding')
                or hasField('udpForwarding')
                or hasField('tcpTProxy')
                or hasField('udpTProxy')
                or isinstance(ob.get('obfs'), dict)
                or hasField('fastOpen')
                or hasField('lazy')
            ):
                return Hysteria2.name()

        return ''

    @staticmethod
    def getCoreProtocol(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        return protocolRepr(outbound['protocol'])

                return ''

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return Protocol.Hysteria1

            if Intellisense.getCoreType(ob) == Hysteria2.name():
                return Protocol.Hysteria2

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCoreAddr(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        protocol = protocolRepr(outbound['protocol'])

                        if protocol == Protocol.VMess or protocol == Protocol.VLESS:
                            return ';'.join(
                                list(
                                    f'{server["address"]}'
                                    for server in outbound['settings']['vnext']
                                )
                            )

                        if (
                            protocol == Protocol.Shadowsocks
                            or protocol == Protocol.Trojan
                        ):
                            return ';'.join(
                                list(
                                    f'{server["address"]}'
                                    for server in outbound['settings']['servers']
                                )
                            )

                return ''

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return ob['server'].split(':')[0]

            if Intellisense.getCoreType(ob) == Hysteria2.name():
                return ob['server'].split(':')[0]

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCorePort(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        protocol = protocolRepr(outbound['protocol'])

                        if protocol == Protocol.VMess or protocol == Protocol.VLESS:
                            return ';'.join(
                                list(
                                    f'{server["port"]}'
                                    for server in outbound['settings']['vnext']
                                )
                            )

                        if (
                            protocol == Protocol.Shadowsocks
                            or protocol == Protocol.Trojan
                        ):
                            return ';'.join(
                                list(
                                    f'{server["port"]}'
                                    for server in outbound['settings']['servers']
                                )
                            )

                return ''

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return ob['server'].split(':')[1]

            if Intellisense.getCoreType(ob) == Hysteria2.name():
                return ob['server'].split(':')[1]

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCoreTransport(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        return outbound['streamSettings']['network']

                return ''

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCoreTLS(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        return outbound['streamSettings']['security']

                return ''

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''
