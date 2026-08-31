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

"""Decode standard subscription representations independently."""

from __future__ import annotations

from Furious.Plugins.API import (
    FuriousPlugin,
    PluginMetadata,
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


class PlainShareLinkDecoder(SubscriptionDecoder):
    """Decode newline-delimited plain-text share links."""

    workerSafe = True
    decoderId = 'plain-share-links'
    displayName = 'Share Links (plain text)'
    priority = 100

    def decode(self, data: bytes):
        """Decode a validated plain-text share-link payload."""
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            return None

        links = _shareLinks(text)

        return (
            SubscriptionResult(
                self.decoderId,
                tuple(SubscriptionItem(uri=link) for link in links),
            )
            if links is not None
            else None
        )


class Base64ShareLinkDecoder(SubscriptionDecoder):
    """Decode a Base64 envelope containing plain share links."""

    workerSafe = True
    decoderId = 'base64-share-links'
    displayName = 'Share Links (Base64)'
    priority = 90

    def decode(self, data: bytes):
        """Decode Base64 bytes before validating contained share links."""
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

    metadata = PluginMetadata(
        'official.standard-subscriptions',
        'Standard Subscriptions',
        description='Plain-text and Base64 share-link subscription decoders.',
        provider='Furious',
    )
    capabilities = (PlainShareLinkDecoder(), Base64ShareLinkDecoder())
