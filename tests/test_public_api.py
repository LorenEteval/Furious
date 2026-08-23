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

"""Protect curated package exports and import-time isolation."""

from __future__ import annotations

from tests.support import assertChildSucceeded, runPythonChild

import unittest


class PublicPackageAPITest(unittest.TestCase):
    """Keep the documented package-level import surface deliberate."""

    Packages = (
        'Actions',
        'Application',
        'Backends',
        'Controllers',
        'Core',
        'Extensions',
        'Externals',
        'Frozenlib',
        'Interface',
        'Models',
        'Plugins',
        'Qt',
        'Repository',
        'Service',
        'Utility',
        'Widget',
        'Window',
    )

    def testEveryPackageDeclaresAndResolvesItsPublicAPI(self):
        """Make every curated star export importable in one isolated process."""
        script = f"""
import importlib

packages = {self.Packages!r}

for package_name in packages:
    module_name = f'Furious.{{package_name}}'
    module = importlib.import_module(module_name)
    exports = getattr(module, '__all__', None)

    assert isinstance(exports, list), (module_name, exports)
    assert exports, module_name
    assert len(exports) == len(set(exports)), module_name

    namespace = {{}}
    exec(f'from {{module_name}} import *', namespace)

    actual = set(namespace).difference({{'__builtins__'}})
    assert actual == set(exports), (module_name, sorted(actual), sorted(exports))
"""
        result = runPythonChild(script)

        assertChildSucceeded(self, result, 'public package import child')

    def testRepresentativeCompatibilitySymbolsRemainStable(self):
        """Pin the architectural entry points used across package boundaries."""
        script = """
from Furious.Application import DesktopApplication, TrayIcon
from Furious.Controllers import (
    ConnectionController,
    RoutingController,
    SettingsController,
)
from Furious.Interface import (
    ApplicationRunner,
    CoreRuntime,
    EditorBinding,
    StorageBackend,
)
from Furious.Models import CoreConfiguration, ProfileMetadata, ServerProfile
from Furious.Plugins import CoreRuntimeFactory, FuriousPlugin, PluginRegistry
from Furious.Qt import AppQDialog, AppQMainWindow, AppQMessageBox
from Furious.Repository import Storage, SubscriptionGroup
from Furious.Service import (
    ConnectionManager,
    LogManager,
    MetricsHistory,
    SubscriptionManager,
)
from Furious.Utility import AppMainProcess
from Furious.Widget import NavigationView
from Furious.Window import MainWindow, SettingsPage

symbols = (
    DesktopApplication,
    TrayIcon,
    ConnectionController,
    RoutingController,
    SettingsController,
    ApplicationRunner,
    CoreRuntime,
    EditorBinding,
    StorageBackend,
    CoreConfiguration,
    ProfileMetadata,
    ServerProfile,
    CoreRuntimeFactory,
    FuriousPlugin,
    PluginRegistry,
    AppQDialog,
    AppQMainWindow,
    AppQMessageBox,
    Storage,
    SubscriptionGroup,
    ConnectionManager,
    LogManager,
    MetricsHistory,
    SubscriptionManager,
    AppMainProcess,
    NavigationView,
    MainWindow,
    SettingsPage,
)
assert all(symbol is not None for symbol in symbols)
"""
        result = runPythonChild(script)

        assertChildSucceeded(self, result, 'representative public API child')

    def testBackendPluginDiscoveryStaysLazyAndComplete(self):
        """Resolve bundled plugin types without constructing plugin instances."""
        script = """
import sys
import Furious.Backends as backends

assert 'Furious.Backends.Xray.Plugin' not in sys.modules

plugin_types = backends.OFFICIAL_PLUGIN_TYPES

assert tuple(plugin.__name__ for plugin in plugin_types) == (
    'XrayPlugin',
    'Hysteria1Plugin',
    'Hysteria2Plugin',
    'ExternalCorePlugin',
)
"""
        result = runPythonChild(script)

        assertChildSucceeded(self, result, 'lazy backend discovery child')


if __name__ == '__main__':
    unittest.main()
