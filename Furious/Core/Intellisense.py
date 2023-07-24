from Furious.Core.Core import XrayCore, Hysteria
from Furious.Utility.Utility import protocolRepr


class Intellisense:
    @staticmethod
    def getCoreType(ob):
        if ob.get('inbounds') is not None or ob.get('outbounds') is not None:
            # Assuming is XrayCore
            return XrayCore.name()

        if ob.get('server') is not None:
            # Assuming is Hysteria. This behavior might be changed in the future
            return Hysteria.name()

        return ''

    @staticmethod
    def getCoreProtocol(ob):
        try:
            if Intellisense.getCoreType(ob) == XrayCore.name():
                for outbound in ob['outbounds']:
                    if outbound['tag'] == 'proxy':
                        return protocolRepr(outbound['protocol'])

            if Intellisense.getCoreType(ob) == Hysteria.name():
                return 'hysteria'

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
                        return ';'.join(
                            list(
                                f'{server["address"]}'
                                for server in outbound['settings']['vnext']
                            )
                        )

            if Intellisense.getCoreType(ob) == Hysteria.name():
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
                        return ';'.join(
                            list(
                                f'{server["port"]}'
                                for server in outbound['settings']['vnext']
                            )
                        )

            if Intellisense.getCoreType(ob) == Hysteria.name():
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

            if Intellisense.getCoreType(ob) == Hysteria.name():
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

            if Intellisense.getCoreType(ob) == Hysteria.name():
                return ''

            return ''
        except Exception:
            # Any non-exit exceptions

            return ''
