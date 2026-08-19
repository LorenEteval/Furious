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

"""Model a structured invocation of a user-managed local proxy core."""

from __future__ import annotations

from Furious.Models import CoreConfiguration

from pathlib import Path
from typing import Mapping

import os
import copy

__all__ = [
    'BLANK_CONFIG_EXTERNAL_CORE',
    'ConfigExternalCore',
    'ExternalCoreConfigurationError',
    'EXTERNAL_CORE_TYPE',
]

EXTERNAL_CORE_TYPE = 'external-core'

BLANK_CONFIG_EXTERNAL_CORE = {
    'type': EXTERNAL_CORE_TYPE,
    'executable': '',
    'workingDirectory': '',
    'arguments': [],
    'environment': {},
    'httpProxy': '127.0.0.1:10809',
    'socksProxy': '127.0.0.1:10808',
    'useApplicationTun2socks': False,
    'tunRemoteAddress': '',
    'shutdownTimeout': 5,
}


class ExternalCoreConfigurationError(ValueError):
    """Describe an invalid external-core process invocation."""


class ConfigExternalCore(CoreConfiguration):
    """Store one external executable invocation as structured JSON data."""

    def __init__(self, config: Mapping | str = ''):
        """Initialize an External Core configuration."""
        super().__init__(dict(config) if isinstance(config, Mapping) else config)

    @staticmethod
    def _absolutePath(value: str, base: str = '') -> str:
        """Return a normalized absolute local path, preserving empty values."""
        value = str(value or '').strip()

        if not value:
            return ''

        path = Path(value).expanduser()

        if not path.is_absolute():
            path = Path(base).expanduser() / path if base else Path.cwd() / path

        return str(path.resolve(strict=False))

    def normalizePaths(self):
        """Normalize persisted executable and working-directory paths in place."""
        workingDirectory = self._absolutePath(self.get('workingDirectory', ''))
        executable = self._absolutePath(
            self.get('executable', ''),
            workingDirectory,
        )

        self['workingDirectory'] = workingDirectory
        self['executable'] = executable

    def coreName(self) -> str:
        """Return the runtime implementation name."""
        return 'External Core'

    @property
    def itemProtocol(self) -> str:
        """Return the profile protocol label."""
        return EXTERNAL_CORE_TYPE

    @property
    def itemAddress(self) -> str:
        """Return the remote destination displayed by the server table."""
        return self.remoteAddress()

    def remoteAddress(self) -> str:
        """Return the remote destination used by routing and TUN code."""
        return self.tunRemoteAddress()

    @property
    def itemPort(self) -> str:
        """Return the local HTTP proxy port for the server table."""
        endpoint = self.httpProxy()

        return endpoint.rsplit(':', 1)[-1] if ':' in endpoint else ''

    @property
    def itemTransport(self) -> str:
        """Return an empty transport label for a local executable."""
        return ''

    @property
    def itemTLS(self) -> str:
        """Return an empty TLS label for a local executable."""
        return ''

    def httpProxy(self) -> str:
        """Return the local HTTP proxy exposed by the configured program."""
        return str(self.get('httpProxy', ''))

    def socksProxy(self) -> str:
        """Return the local SOCKS proxy exposed by the configured program."""
        return str(self.get('socksProxy', ''))

    def usesApplicationTun2socks(self) -> bool:
        """Return whether this profile opts into host-managed tun2socks."""
        return self.get('useApplicationTun2socks', False) is True

    def setUseApplicationTun2socks(self, enabled: bool) -> bool:
        """Persist whether Furious should provide tun2socks for this profile."""
        enabled = bool(enabled)
        oldValue = self.get('useApplicationTun2socks', False)

        if isinstance(oldValue, bool) and enabled == oldValue:
            return False

        self['useApplicationTun2socks'] = enabled

        return True

    def tunRemoteAddress(self) -> str:
        """Return the hostname or IP used for TUN bypass routing."""
        return str(self.get('tunRemoteAddress', '')).strip()

    def setTunRemoteAddress(self, address: str) -> bool:
        """Persist the remote hostname or IP independently of process paths."""
        address = str(address or '').strip()

        if address == self.tunRemoteAddress():
            return False

        self['tunRemoteAddress'] = address

        return True

    def setHttpProxy(self, endpoint: str) -> bool:
        """Set the external program's local HTTP proxy endpoint."""
        endpoint = str(endpoint or '').strip()

        if endpoint == self.httpProxy():
            return False

        self['httpProxy'] = endpoint

        return True

    def setSocksProxy(self, endpoint: str) -> bool:
        """Set the external program's local SOCKS proxy endpoint."""
        endpoint = str(endpoint or '').strip()

        if endpoint == self.socksProxy():
            return False

        self['socksProxy'] = endpoint

        return True

    def command(self) -> tuple[str, ...]:
        """Return the direct process argument vector without shell expansion."""
        executable = str(self.get('executable', ''))
        arguments = self.get('arguments', [])

        if not isinstance(arguments, list) or not all(
            isinstance(argument, str) for argument in arguments
        ):
            raise ExternalCoreConfigurationError(
                'Command-line arguments must be a list of strings'
            )

        return executable, *arguments

    def processEnvironment(self) -> dict[str, str]:
        """Return the inherited process environment with configured overrides."""
        overrides = self.get('environment', {})

        if not isinstance(overrides, Mapping):
            raise ExternalCoreConfigurationError(
                'Environment overrides must be a mapping'
            )

        environment = dict(os.environ)

        for key, value in overrides.items():
            if not isinstance(key, str) or not key or '=' in key or '\0' in key:
                raise ExternalCoreConfigurationError(
                    'Environment variable names cannot be empty or contain ='
                )

            if not isinstance(value, str) or '\0' in value:
                raise ExternalCoreConfigurationError(
                    'Environment variable values must be strings without NUL bytes'
                )

            environment[key] = value

        return environment

    def shutdownTimeout(self) -> float:
        """Return the bounded graceful-shutdown timeout in seconds."""
        value = self.get('shutdownTimeout', 5)

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExternalCoreConfigurationError(
                'Shutdown timeout must be a number of seconds'
            )

        value = float(value)

        if value < 0.1 or value > 60:
            raise ExternalCoreConfigurationError(
                'Shutdown timeout must be between 0.1 and 60 seconds'
            )

        return value

    def validateProcess(self) -> tuple[str, ...]:
        """Return connection-time process configuration errors."""
        errors = []
        executableText = str(self.get('executable', '')).strip()
        workingDirectoryText = str(self.get('workingDirectory', '')).strip()

        if not executableText:
            errors.append('Executable path is required')
        else:
            executable = Path(executableText).expanduser()

            if not executable.is_absolute():
                errors.append('Executable path must be absolute')
            elif not executable.exists():
                errors.append('Executable does not exist')
            elif not executable.is_file():
                errors.append('Executable path does not point to a file')
            elif os.name != 'nt' and not os.access(executable, os.X_OK):
                errors.append('Executable is not launchable')

        if workingDirectoryText:
            workingDirectory = Path(workingDirectoryText).expanduser()

            if not workingDirectory.is_absolute():
                errors.append('Working directory path must be absolute')
            elif not workingDirectory.exists():
                errors.append('Working directory does not exist')
            elif not workingDirectory.is_dir():
                errors.append('Working directory path is not a directory')

        try:
            command = self.command()

            if any('\0' in argument for argument in command):
                errors.append('Executable and arguments cannot contain NUL bytes')
        except ExternalCoreConfigurationError as ex:
            errors.append(str(ex))

        try:
            self.processEnvironment()
        except ExternalCoreConfigurationError as ex:
            errors.append(str(ex))

        try:
            self.shutdownTimeout()
        except ExternalCoreConfigurationError as ex:
            errors.append(str(ex))

        applicationTun2socks = self.get('useApplicationTun2socks', False)

        if not isinstance(applicationTun2socks, bool):
            errors.append('Use Application tun2socks must be a boolean')
        elif applicationTun2socks:
            tunRemoteAddress = self.tunRemoteAddress()

            if not tunRemoteAddress:
                errors.append(
                    'TUN remote address is required when application '
                    'tun2socks is enabled'
                )
            elif '\0' in tunRemoteAddress:
                errors.append('TUN remote address cannot contain NUL bytes')

            if not self.socksProxy().strip():
                errors.append(
                    'Local SOCKS proxy endpoint is required when application '
                    'tun2socks is enabled'
                )

        return tuple(errors)

    def isValid(self) -> bool:
        """Return whether the persisted process invocation is well formed."""
        return not self.validateProcess() and bool(self.httpProxy())

    def deepcopy(self):
        """Return an independent External Core configuration."""
        return ConfigExternalCore(copy.deepcopy(dict(self)))
