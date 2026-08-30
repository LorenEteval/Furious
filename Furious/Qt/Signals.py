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

__all__ = ['connectWeakly', 'singleShotWeakly']


def _ownsQObject(owner, object_) -> bool:
    """Return whether *object_* belongs to *owner*'s QObject tree."""
    current = object_

    while isinstance(current, QtCore.QObject):
        if current is owner:
            return True

        current = current.parent()

    return False


def _weakMethodInvoker(
    receiver: Any,
    methodName: str,
    *,
    sender=None,
    forwardSender: bool = False,
):
    """Return a plain callable that weakly dispatches to one named method."""
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

    return invoke


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
    invoke = _weakMethodInvoker(
        receiver,
        methodName,
        sender=sender,
        forwardSender=forwardSender,
    )
    connection = signal.connect(invoke)

    if (
        isinstance(receiver, QtCore.QObject)
        and isinstance(sender, QtCore.QObject)
        and not _ownsQObject(receiver, sender)
    ):

        def disconnect(*_args):
            """Remove weak dispatch from an independently owned sender."""
            # Retain only Qt's opaque connection handle. Capturing ``signal``
            # here keeps the sender's SignalInstance wrapper alive until the
            # receiver dies; when the native sender died first, PySide6 could
            # then access that stale wrapper during application teardown.
            QtCore.QObject.disconnect(connection)

        receiver.destroyed.connect(disconnect)

    return connection


def singleShotWeakly(milliseconds: int, receiver: Any, methodName: str):
    """Schedule one named method without retaining its receiver."""
    # QTimer.singleShot() is patched by the packaged runtime for compiled bound
    # methods just like SignalInstance.connect().  Keep the scheduled callable
    # plain and resolve the receiver only if it still exists when the timer fires.
    invoke = _weakMethodInvoker(receiver, methodName)

    QtCore.QTimer.singleShot(milliseconds, invoke)
