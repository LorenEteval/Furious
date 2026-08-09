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

"""Provide the lazily imported Hysteria 2 protocol editor."""

from __future__ import annotations

from Furious.Plugins.API import ProtocolEditorProvider

__all__ = ['HYSTERIA2_PROTOCOL_EDITORS']


class Hysteria2ProtocolEditor(ProtocolEditorProvider):
    """Create the Hysteria 2 editor on demand."""

    editorId = 'official.hysteria2.editor'
    protocolIds = ('hysteria2',)

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Create the Hysteria 2 editor."""
        from .Editor import Hysteria2Editor

        return Hysteria2Editor(parent=parent, **kwargs)


HYSTERIA2_PROTOCOL_EDITORS = (Hysteria2ProtocolEditor(),)
