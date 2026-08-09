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

"""Decode the plain-text and base64 share-link subscription formats."""

from __future__ import annotations

from Furious.Plugins.API import (
    FuriousPlugin,
    SubscriptionDecoder,
    SubscriptionItem,
    SubscriptionResult,
)

import base64
import binascii

__all__ = ['StandardSubscriptionPlugin']


def _shareLinks(text: str):
    """Return validated non-comment share links from subscription text."""
    lines = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(('#', '//'))
    )

    if not lines or any('://' not in line for line in lines):
        return None

    return lines


class ShareLinkSubscriptionDecoder(SubscriptionDecoder):
    """Decode standard newline-delimited plain or base64 share links."""

    decoderId = 'share-links'
    displayName = 'Share Links (plain text or base64)'
    priority = 100

    def decode(self, data: bytes):
        """Decode a validated plain-text or base64 share-link payload."""
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = ''

        links = _shareLinks(text)

        if links is None:
            compact = b''.join(data.split())
            compact += b'=' * (-len(compact) % 4)

            try:
                decoded = base64.b64decode(compact, altchars=b'-_', validate=True)
                links = _shareLinks(decoded.decode('utf-8-sig'))
            except (binascii.Error, UnicodeDecodeError, ValueError):
                return None

        if links is None:
            return None

        return SubscriptionResult(
            self.decoderId,
            tuple(SubscriptionItem(uri=link) for link in links),
        )


class StandardSubscriptionPlugin(FuriousPlugin):
    """Contribute Furious's built-in share-link subscription decoder."""

    pluginId = 'official.standard-subscriptions'
    displayName = 'Standard Subscriptions'
    subscriptionDecoders = (ShareLinkSubscriptionDecoder(),)
