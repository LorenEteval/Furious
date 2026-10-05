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

"""Expose execution-only runtime primitives without connection orchestration."""

from __future__ import annotations

from .MultiprocessingRuntime import MultiprocessingRuntime, ProcessLaunchSpec
from .ProcessOutput import MsgQueue, ProcessOutputRedirector
from .Tun2socks import Tun2socks
from .SingTUN import SingTUN

__all__ = [
    'MultiprocessingRuntime',
    'MsgQueue',
    'ProcessLaunchSpec',
    'ProcessOutputRedirector',
    'Tun2socks',
    'SingTUN',
]
