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

"""Provide signal connections that do not retain transient receivers."""

from __future__ import annotations

from PySide6 import QtCore

from shiboken6 import isValid

from typing import Any

import weakref

__all__ = ['connectWeakly']


def _ownsQObject(owner, object_) -> bool:
    """Return whether *object_* belongs to *owner*'s QObject tree."""
    current = object_

    while isinstance(current, QtCore.QObject):
        if current is owner:
            return True

        current = current.parent()

    return False


def connectWeakly(
    signal,
    receiver: Any,
    methodName: str,
    *,
    sender=None,
    forwardSender: bool = False,
):
    """Connect without strongly owning a transient receiver or sender."""
    # A plain dispatcher is intentional. Nuitka's PySide6 compatibility layer
    # process-globally protects compiled bound methods passed directly to connect().
    if not isinstance(methodName, str) or not methodName:
        raise ValueError('method name must be a non-empty string')

    if forwardSender and sender is None:
        raise ValueError('forwarding requires an explicit sender')

    receiverReference = weakref.ref(receiver)
    senderReference = weakref.ref(sender) if sender is not None else None

    def invoke(*args, **kwargs):
        """Invoke the named method while its Python and Qt owners remain valid."""
        currentReceiver = receiverReference()

        if currentReceiver is None:
            return None

        if isinstance(currentReceiver, QtCore.QObject) and not isValid(currentReceiver):
            return None

        method = getattr(currentReceiver, methodName)

        if not forwardSender:
            return method(*args, **kwargs)

        currentSender = senderReference()

        if currentSender is None:
            return None

        if isinstance(currentSender, QtCore.QObject) and not isValid(currentSender):
            return None

        return method(currentSender, *args, **kwargs)

    connection = signal.connect(invoke)

    if (
        isinstance(receiver, QtCore.QObject)
        and isinstance(sender, QtCore.QObject)
        and not _ownsQObject(receiver, sender)
    ):

        def disconnect(*_args):
            """Remove weak dispatch from an independently owned sender."""
            try:
                signal.disconnect(invoke)
            except (RuntimeError, TypeError):
                # The signal owner or connection was already destroyed.
                pass

        receiver.destroyed.connect(disconnect)

    return connection
