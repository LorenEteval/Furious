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

from Furious.Core.Core import XrayCore, Hysteria1
from Furious.Utility.Utility import Protocol, protocolRepr


class Intellisense:
    @staticmethod
    def getCoreType(ob):
        if ob.get('inbounds') is not None or ob.get('outbounds') is not None:
            # Assuming is XrayCore
            return XrayCore.name()

        if ob.get('server') is not None:
            # Assuming is Hysteria1. This behavior might be changed in the future
            return Hysteria1.name()

        return ''

    @staticmethod
    def getCoreProtocol(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        return protocolRepr(outbound['protocol'])

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return Protocol.Hysteria1

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCoreAddr(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                protocol = Intellisense.getCoreProtocol(ob)

                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        if protocol == Protocol.VMess or protocol == Protocol.VLESS:
                            return ';'.join(
                                list(
                                    f'{server["address"]}'
                                    for server in outbound['settings']['vnext']
                                )
                            )

                        if protocol == Protocol.Shadowsocks:
                            return ';'.join(
                                list(
                                    f'{server["address"]}'
                                    for server in outbound['settings']['servers']
                                )
                            )

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return ob['server'].split(':')[0]

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''

    @staticmethod
    def getCorePort(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                protocol = Intellisense.getCoreProtocol(ob)

                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        if protocol == Protocol.VMess or protocol == Protocol.VLESS:
                            return ';'.join(
                                list(
                                    f'{server["port"]}'
                                    for server in outbound['settings']['vnext']
                                )
                            )

                        if protocol == Protocol.Shadowsocks:
                            return ';'.join(
                                list(
                                    f'{server["port"]}'
                                    for server in outbound['settings']['servers']
                                )
                            )

            if Intellisense.getCoreType(ob) == Hysteria1.name():
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

            if Intellisense.getCoreType(ob) == Hysteria1.name():
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

            if Intellisense.getCoreType(ob) == Hysteria1.name():
                return ''

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''
