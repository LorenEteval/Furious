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

"""Provide the lazily imported Hysteria 1 protocol editor."""

from __future__ import annotations

from Furious.Plugins.API import ProtocolEditorProvider

__all__ = ['HYSTERIA1_PROTOCOL_EDITORS']


class Hysteria1ProtocolEditor(ProtocolEditorProvider):
    """Create the Hysteria 1 editor on demand."""

    editorId = 'official.hysteria1.editor'
    protocolIds = ('hysteria1',)

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Create the Hysteria 1 editor."""
        from .Editor import Hysteria1Editor

        return Hysteria1Editor(parent=parent, **kwargs)


HYSTERIA1_PROTOCOL_EDITORS = (Hysteria1ProtocolEditor(),)
