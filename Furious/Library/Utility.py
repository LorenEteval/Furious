import urllib.parse


def parseHostPort(address):
    if address.count('//') == 0:
        result = urllib.parse.urlsplit('//' + address)
    else:
        result = urllib.parse.urlsplit(address)

    return result.hostname, str(result.port)
