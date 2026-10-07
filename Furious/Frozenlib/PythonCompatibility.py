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

"""Provide standard-library operations shared across supported Python versions."""

from __future__ import annotations

from concurrent.futures import Executor, Future
from importlib import metadata
from typing import Iterable

import sys

__all__ = ['PythonCompatibility']

_PYTHON_39_OR_NEWER = sys.version_info >= (3, 9)


if _PYTHON_39_OR_NEWER:
    _removePrefix = str.removeprefix
    _removeSuffix = str.removesuffix

    def _shutdownExecutor(executor, pendingFutures, *, wait):
        """Use native queued-work cancellation on Python 3.9 and newer."""
        executor.shutdown(wait=wait, cancel_futures=True)

else:

    def _removePrefix(value: str, prefix: str) -> str:
        """Remove one exact prefix on Python 3.8."""
        if not isinstance(prefix, str):
            raise TypeError('prefix must be a string')

        return value[len(prefix) :] if value.startswith(prefix) else value

    def _removeSuffix(value: str, suffix: str) -> str:
        """Remove one exact nonempty suffix on Python 3.8."""
        if not isinstance(suffix, str):
            raise TypeError('suffix must be a string')

        return value[: -len(suffix)] if suffix and value.endswith(suffix) else value

    def _shutdownExecutor(executor, pendingFutures, *, wait):
        """Cancel caller-owned queued futures before Python 3.8 shutdown."""
        for future in pendingFutures:
            future.cancel()

        executor.shutdown(wait=wait)


if hasattr(metadata, 'EntryPoints'):

    def _entryPoints(group: str) -> tuple:
        """Use selectable entry points without an import-time metadata scan."""
        return tuple(metadata.entry_points(group=group))

else:

    def _entryPoints(group: str) -> tuple:
        """Select from the legacy metadata mapping without an import-time scan."""
        return tuple(metadata.entry_points().get(group, ()))


class PythonCompatibility:
    """Keep version-dependent standard-library behavior at one boundary."""

    PackageNotFoundError = metadata.PackageNotFoundError

    @staticmethod
    def removePrefix(value: str, prefix: str) -> str:
        """Remove one exact prefix using the implementation selected at import."""
        return _removePrefix(value, prefix)

    @staticmethod
    def removeSuffix(value: str, suffix: str) -> str:
        """Remove one exact suffix using the implementation selected at import."""
        return _removeSuffix(value, suffix)

    @staticmethod
    def distributionVersion(name: str) -> str:
        """Read installed metadata, preserving missing-distribution diagnostics."""
        return metadata.version(name)

    @staticmethod
    def entryPoints(group: str) -> tuple:
        """Fetch a group using the metadata API selected at import."""
        return _entryPoints(group)

    @staticmethod
    def shutdownExecutor(
        executor: Executor,
        pendingFutures: Iterable[Future],
        *,
        wait: bool = True,
    ) -> None:
        """Cancel queued work and close admission without terminating running calls.

        The caller closes its own submission path before invoking this method and
        supplies all uncancelled pending futures for the Python 3.8 fallback.
        """
        _shutdownExecutor(executor, pendingFutures, wait=wait)
