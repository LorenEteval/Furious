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

"""Provide lazily imported Xray protocol editors."""

from __future__ import annotations

from Furious.Plugins.API import ProtocolEditorProvider

__all__ = ['XRAY_PROTOCOL_EDITORS']


def _createVmessEditor(parent=None, **kwargs):
    """Create the VMess editor without importing Qt during plugin discovery."""
    from .VmessEditor import VmessEditor

    return VmessEditor(parent=parent, **kwargs)


def _createVlessEditor(parent=None, **kwargs):
    """Create the VLESS editor without importing Qt during plugin discovery."""
    from .VlessEditor import VlessEditor

    return VlessEditor(parent=parent, **kwargs)


def _createShadowsocksEditor(parent=None, **kwargs):
    """Create the Shadowsocks editor without importing Qt during plugin discovery."""
    from .ShadowsocksEditor import ShadowsocksEditor

    return ShadowsocksEditor(parent=parent, **kwargs)


def _createTrojanEditor(parent=None, **kwargs):
    """Create the Trojan editor without importing Qt during plugin discovery."""
    from .TrojanEditor import TrojanEditor

    return TrojanEditor(parent=parent, **kwargs)


def _createSocksEditor(parent=None, **kwargs):
    """Create the SOCKS editor without importing Qt during plugin discovery."""
    from .SocksEditor import SocksEditor

    return SocksEditor(parent=parent, **kwargs)


class XrayProtocolEditors(ProtocolEditorProvider):
    """Create the editor registered for each supported Xray protocol."""

    editorId = 'official.xray.editors'
    protocolIds = ('vmess', 'vless', 'shadowsocks', 'trojan', 'socks')
    # Keep these as callables containing literal imports. They preserve lazy Qt
    # initialization while allowing standalone compilers such as Nuitka to see
    # every editor dependency during static import analysis.
    _editors = {
        'vmess': _createVmessEditor,
        'vless': _createVlessEditor,
        'shadowsocks': _createShadowsocksEditor,
        'trojan': _createTrojanEditor,
        'socks': _createSocksEditor,
    }

    def createEditor(self, protocolId: str, parent=None, **kwargs):
        """Load and create the requested Xray editor on demand."""
        editor = self._editors.get(protocolId.casefold())

        if editor is None:
            return None

        return editor(parent=parent, **kwargs)


XRAY_PROTOCOL_EDITORS = (XrayProtocolEditors(),)
