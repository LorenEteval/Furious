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

from Furious.Utility import *
from Furious.Library import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

from typing import Tuple

import logging

__all__ = ['DNSResolver']

logger = logging.getLogger(__name__)


class DNSResolver:
    Manager = QNetworkAccessManager()

    @staticmethod
    def request(address) -> QNetworkRequest:
        request = QNetworkRequest(
            QtCore.QUrl(f'https://cloudflare-dns.com/dns-query?name={address}')
        )
        request.setRawHeader('accept'.encode(), 'application/dns-json'.encode())

        return request

    @staticmethod
    def handleFinishedByNetworkReply(networkReply, domain, resultMap):
        assert isinstance(networkReply, QNetworkReply)

        if networkReply.error() != QNetworkReply.NetworkError.NoError:
            logger.error(
                f'DNS resolution for \'{domain}\' failed. {networkReply.errorString()}'
            )

            resultMap['error'] = True
        else:
            logger.info(f'DNS resolution for \'{domain}\' success')

            # Unchecked?
            replyObject = UJSONEncoder.decode(networkReply.readAll().data())

            for record in replyObject['Answer']:
                address = record['data']

                logger.info(f'\'{domain}\' resolved to \'{address}\'')

                if isValidIPAddress(address):
                    resultMap['result'][address] = True
                else:
                    resultMap['depth'] += 1

                    newNetworkReply = DNSResolver.Manager.get(
                        DNSResolver.request(address)
                    )
                    newNetworkReply.finished.connect(
                        functools.partial(
                            DNSResolver.handleFinishedByNetworkReply,
                            newNetworkReply,
                            address,
                            resultMap,
                        )
                    )

                    resultMap['reference'].append(newNetworkReply)

        resultMap['depth'] -= 1

    @staticmethod
    def resolve(domain, proxyHost=None, proxyPort=None) -> Tuple[bool, list[str]]:
        if proxyHost is None or proxyPort is None:
            DNSResolver.Manager.setProxy(QNetworkProxy.ProxyType.NoProxy)
        else:
            try:
                DNSResolver.Manager.setProxy(
                    QNetworkProxy(
                        QNetworkProxy.ProxyType.HttpProxy, proxyHost, int(proxyPort)
                    )
                )

                logger.info(f'DNS resolution uses proxy server {proxyHost}:{proxyPort}')
            except Exception as ex:
                # Any non-exit exceptions

                logger.error(
                    f'invalid proxy server {proxyHost}:{proxyPort}. {ex}. '
                    f'DNS resolution uses no proxy'
                )

                DNSResolver.Manager.setProxy(QNetworkProxy.ProxyType.NoProxy)

        resultMap = {
            'depth': 0,
            'error': False,
            'reference': [],
            'result': {},
        }

        resultMap['depth'] += 1

        networkReply = DNSResolver.Manager.get(DNSResolver.request(domain))
        networkReply.finished.connect(
            functools.partial(
                DNSResolver.handleFinishedByNetworkReply,
                networkReply,
                domain,
                resultMap,
            )
        )

        resultMap['reference'].append(networkReply)

        DNSResolver.wait(resultMap)

        return resultMap['error'], list(resultMap['result'].keys())

    @staticmethod
    def wait(resultMap, startCounter=0, timeout=30000, step=100):
        if resultMap['depth'] != 0:
            logger.info('DNS resolution in progress. Wait')
        else:
            return

        while resultMap['depth'] != 0 and startCounter < timeout:
            PySide6LegacyEventLoopWait(step)

            startCounter += step

        if resultMap['depth'] != 0:
            logger.error('DNS resolution timeout')

            for networkReply in resultMap['reference']:
                if (
                    isinstance(networkReply, QNetworkReply)
                    and not networkReply.isFinished()
                ):
                    networkReply.abort()
