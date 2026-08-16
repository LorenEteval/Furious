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

"""Provide the lazily imported External Core profile editor."""

from __future__ import annotations

from Furious.Plugins.API import ProtocolEditorProvider

from .Configuration import EXTERNAL_CORE_TYPE

__all__ = ['EXTERNAL_CORE_PROTOCOL_EDITORS']


class ExternalCoreProtocolEditor(ProtocolEditorProvider):
    """Create the External Core editor only when requested by the UI."""

    editorId = 'official.external-core.editor'
    protocolIds = (EXTERNAL_CORE_TYPE,)

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Create one transient External Core configuration editor."""
        from .Editor import ExternalCoreEditor

        return ExternalCoreEditor(parent=parent, **kwargs)


EXTERNAL_CORE_PROTOCOL_EDITORS = (ExternalCoreProtocolEditor(),)
