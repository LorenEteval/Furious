# Copyright (C) 2024–present  Loren Eteval & contributors <loren.eteval@proton.me>
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

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt.WebGETManager import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

from typing import Tuple

import logging

__all__ = ['DNSResolver']

logger = logging.getLogger(__name__)


class _DNSResolver(WebGETManager):
    def __init__(self, parent=None, **kwargs):
        actionMessage = kwargs.pop('actionMessage', 'DNS resolution')

        super().__init__(parent, actionMessage=actionMessage)

    @staticmethod
    def request(address) -> QNetworkRequest:
        request = QNetworkRequest(
            QtCore.QUrl(f'https://cloudflare-dns.com/dns-query?name={address}')
        )
        request.setRawHeader('accept'.encode(), 'application/dns-json'.encode())

        return request

    def successCallback(self, networkReply, **kwargs):
        domain = kwargs.pop('domain', '')
        resultMap = kwargs.pop('resultMap', {})

        data = networkReply.readAll().data()

        try:
            replyObject = UJSONEncoder.decode(data)
        except Exception as ex:
            logger.error(
                f'bad network reply while resolving DNS for \'{domain}\'. {ex}'
            )

            resultMap['error'] = True
        else:
            logger.info(f'DNS resolution for \'{domain}\' success')

            for record in replyObject['Answer']:
                address = record['data']

                logger.info(f'\'{domain}\' resolved to \'{address}\'')

                if isValidIPAddress(address):
                    resultMap['result'][address] = True
                else:
                    resultMap['depth'] += 1

                    newNetworkReply = self.webGET(
                        self.request(address),
                        logActionMessage=False,
                        domain=address,
                        resultMap=resultMap,
                    )

                    resultMap['reference'].append(newNetworkReply)

        resultMap['depth'] -= 1

    def failureCallback(self, networkReply: QNetworkReply, **kwargs):
        domain = kwargs.pop('domain', '')
        resultMap = kwargs.pop('resultMap', {})

        logger.error(
            f'DNS resolution for \'{domain}\' failed. {networkReply.errorString()}'
        )

        resultMap['error'] = True
        resultMap['depth'] -= 1

    def resolve(self, domain, timeout=30000) -> Tuple[bool, list[str]]:
        resultMap = {
            'domain': domain,
            'depth': 0,
            'error': False,
            'reference': [],
            'result': {},
        }

        resultMap['depth'] += 1

        networkReply = self.webGET(
            self.request(domain),
            logActionMessage=False,
            domain=domain,
            resultMap=resultMap,
        )

        resultMap['reference'].append(networkReply)

        self.wait(resultMap, timeout=timeout)

        return resultMap['error'], list(resultMap['result'].keys())

    @staticmethod
    def wait(resultMap, startCounter=0, timeout=30000, step=100):
        domain = resultMap.get('domain', '')

        if not domain:
            return

        if resultMap['depth'] != 0:
            logger.info(f'DNS resolution for \'{domain}\' in progress. Wait')
        else:
            return

        while resultMap['depth'] != 0 and startCounter < timeout:
            PySide6Legacy.eventLoopWait(step)

            startCounter += step

        if resultMap['depth'] != 0:
            logger.error(
                f'DNS resolution for \'{domain}\' reached timeout {timeout // 1000}s'
            )

            for networkReply in resultMap['reference']:
                if (
                    isinstance(networkReply, QNetworkReply)
                    and not networkReply.isFinished()
                ):
                    networkReply.abort()


DNSResolver = _DNSResolver()
