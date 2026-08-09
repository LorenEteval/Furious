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

"""Expose plugin contracts without eagerly loading plugin implementations."""

from __future__ import annotations

from .API import (
    PLUGIN_API_VERSION,
    ActionProvider,
    CapabilityKind,
    FuriousPlugin,
    KernelFactory,
    KernelLaunch,
    KernelRequest,
    PluginCapability,
    PluginContext,
    PluginMetadata,
    ProtocolDescriptor,
    ProtocolEditorProvider,
    ProtocolHandler,
    ProtocolParseResult,
    RoutingOption,
    SubscriptionDecoder,
    SubscriptionItem,
    SubscriptionResult,
    TrafficCounters,
    TrafficStatsMonitor,
    TrafficStatsProvider,
)
from .Profile import (
    blankConfiguration,
    blankProfile,
    configurationFromAny,
    configurationFromMapping,
    exportConfiguration,
    profileFromAny,
    profileFromMapping,
)
from .Registry import (
    PLUGIN_ENTRY_POINT_GROUP,
    PluginRegistry,
    getPluginRegistry,
    initializePluginRegistry,
    registerPlugin,
)

__all__ = [
    'PLUGIN_API_VERSION',
    'PLUGIN_ENTRY_POINT_GROUP',
    'ActionProvider',
    'CapabilityKind',
    'FuriousPlugin',
    'KernelFactory',
    'KernelLaunch',
    'KernelRequest',
    'PluginCapability',
    'PluginContext',
    'PluginRegistry',
    'PluginMetadata',
    'ProtocolDescriptor',
    'ProtocolEditorProvider',
    'ProtocolHandler',
    'ProtocolParseResult',
    'RoutingOption',
    'SubscriptionDecoder',
    'SubscriptionItem',
    'SubscriptionResult',
    'TrafficCounters',
    'TrafficStatsMonitor',
    'TrafficStatsProvider',
    'blankConfiguration',
    'blankProfile',
    'configurationFromAny',
    'configurationFromMapping',
    'exportConfiguration',
    'getPluginRegistry',
    'initializePluginRegistry',
    'profileFromAny',
    'profileFromMapping',
    'registerPlugin',
]
