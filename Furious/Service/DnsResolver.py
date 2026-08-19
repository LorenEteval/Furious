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

"""Provide Qt support for DNS resolver."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Models import *
from Furious.Qt.HttpGetManager import *

from PySide6 import QtCore
from PySide6.QtNetwork import *

from typing import Tuple

import logging

__all__ = ['DnsResolver']

logger = logging.getLogger(__name__)


class _DnsResolver(HttpGetManager):
    """Represent DNS resolver."""

    MAX_REFERENCE_DEPTH = 32

    def __init__(self, parent=None, **kwargs):
        """Initialize the DNS resolver."""
        actionMessage = kwargs.pop('actionMessage', 'DNS resolution')

        super().__init__(parent, actionMessage=actionMessage)

    @staticmethod
    def request(address) -> QNetworkRequest:
        """Return the request value used by the DNS resolver."""
        request = QNetworkRequest(
            QtCore.QUrl(f'https://cloudflare-dns.com/dns-query?name={address}')
        )
        request.setRawHeader('accept'.encode(), 'application/dns-json'.encode())

        return request

    def successCallback(self, networkReply, **kwargs):
        """Handle a successful network operation."""
        domain, resultMap, referenceDepth, ancestry = (
            kwargs.pop('domain', ''),
            kwargs.pop('resultMap', {}),
            kwargs.pop('referenceDepth', 0),
            kwargs.pop('ancestry', tuple()),
        )

        data = networkReply.readAll().data()

        try:
            replyObject = UJSONEncoder.decode(data)
        except Exception as ex:
            # Any non-exit exceptions

            logger.error(
                f'bad network reply while resolving DNS for \'{domain}\'. {ex}'
            )

            resultMap['error'] = True
        else:
            answers = (
                replyObject.get('Answer') if isinstance(replyObject, dict) else None
            )

            if not isinstance(answers, list) or not answers:
                status = (
                    replyObject.get('Status') if isinstance(replyObject, dict) else None
                )

                logger.error(
                    f'DNS resolution for \'{domain}\' returned no answer. '
                    f'Status: {status!r}'
                )

                resultMap['error'] = True
                answers = []
            else:
                logger.info(f'DNS resolution for \'{domain}\' success')

            for record in answers:
                address = record.get('data') if isinstance(record, dict) else None

                if not isinstance(address, str) or not address:
                    logger.error(
                        f'DNS resolution for \'{domain}\' returned an invalid '
                        f'answer record'
                    )
                    resultMap['error'] = True

                    continue

                logger.info(f'\'{domain}\' resolved to \'{address}\'')

                if isValidIPAddress(address):
                    resultMap['result'][address] = True
                    continue

                try:
                    recordType = int(record.get('type', 0))
                except (TypeError, ValueError):
                    recordType = 0

                if recordType != 5:
                    logger.error(
                        f'DNS resolution for \'{domain}\' returned an unsupported '
                        f'non-address answer record'
                    )
                    resultMap['error'] = True

                    continue

                reference = address.rstrip('.').strip()
                normalizedReference = reference.casefold()

                if not reference:
                    resultMap['error'] = True

                    continue

                if normalizedReference in ancestry:
                    logger.error(
                        f'DNS resolution for \'{domain}\' returned a cyclic '
                        f'reference to \'{reference}\''
                    )
                    resultMap['error'] = True

                    continue

                if referenceDepth >= self.MAX_REFERENCE_DEPTH:
                    logger.error(
                        f'DNS resolution for \'{domain}\' exceeded the maximum '
                        f'reference depth {self.MAX_REFERENCE_DEPTH}'
                    )
                    resultMap['error'] = True

                    continue

                if normalizedReference in resultMap['visited']:
                    continue

                resultMap['visited'].add(normalizedReference)
                resultMap['depth'] += 1

                try:
                    newNetworkReply = self.webGET(
                        self.request(reference),
                        logActionMessage=False,
                        domain=reference,
                        resultMap=resultMap,
                        referenceDepth=referenceDepth + 1,
                        ancestry=ancestry + (normalizedReference,),
                    )
                except Exception as ex:
                    # Any non-exit exceptions

                    resultMap['depth'] -= 1

                    logger.error(
                        f'failed to follow DNS reference \'{reference}\'. {ex}'
                    )

                    resultMap['error'] = True

                    continue

                resultMap['reference'].append(newNetworkReply)

        resultMap['depth'] -= 1

    def failureCallback(self, networkReply: QNetworkReply, **kwargs):
        """Handle a failed network operation."""
        domain = kwargs.pop('domain', '')
        resultMap = kwargs.pop('resultMap', {})

        logger.error(
            f'DNS resolution for \'{domain}\' failed. {networkReply.errorString()}'
        )

        resultMap['error'] = True
        resultMap['depth'] -= 1

    def resolve(self, domain, timeout=30000) -> Tuple[bool, list[str]]:
        """Resolve the DNS resolver."""
        resultMap = {
            'domain': domain,
            'depth': 0,
            'error': False,
            'reference': [],
            'result': {},
            'visited': {str(domain).rstrip('.').strip().casefold()},
        }

        resultMap['depth'] += 1

        networkReply = self.webGET(
            self.request(domain),
            logActionMessage=False,
            domain=domain,
            resultMap=resultMap,
            referenceDepth=0,
            ancestry=(str(domain).rstrip('.').strip().casefold(),),
        )

        resultMap['reference'].append(networkReply)

        self.wait(resultMap, timeout=timeout)

        return resultMap['error'], list(resultMap['result'].keys())

    @staticmethod
    def wait(resultMap, startCounter=0, timeout=30000, step=100):
        """Wait for the DNS resolver operation to complete."""
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
            resultMap['error'] = True

            for networkReply in resultMap['reference']:
                if (
                    isinstance(networkReply, QNetworkReply)
                    and not networkReply.isFinished()
                ):
                    networkReply.abort()


DnsResolver = _DnsResolver()
