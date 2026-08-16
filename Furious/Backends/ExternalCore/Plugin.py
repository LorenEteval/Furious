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

"""Integrate user-managed local executables with the Furious kernel API."""

from __future__ import annotations

from Furious.Plugins.API import (
    FuriousPlugin,
    KernelFactory,
    KernelLaunch,
    KernelRequest,
    PluginMetadata,
)

from .Configuration import ConfigExternalCore
from .Process import ExternalCoreProcess
from .ProtocolEditors import EXTERNAL_CORE_PROTOCOL_EDITORS
from .Protocols import EXTERNAL_CORE_PROTOCOL_HANDLERS

import logging

__all__ = ['ExternalCorePlugin']

logger = logging.getLogger(__name__)


class ExternalCoreKernelFactory(KernelFactory):
    """Construct a managed direct-process runtime from a structured profile."""

    factoryId = 'official.external-core'
    configurationTypes = (ConfigExternalCore,)
    kernelTypes = (ExternalCoreProcess,)

    def usesApplicationTun2socks(self, config) -> bool:
        """Honor this profile's explicit host-managed tun2socks preference."""
        return config.usesApplicationTun2socks()

    def create(self, request: KernelRequest):
        """Create an External Core process launch for the connection manager."""
        process = ExternalCoreProcess(
            exitCallback=request.exitCallback,
            msgCallback=request.messageCallback,
        )

        if request.log:
            logger.info('core External Core configured')

            if request.configuration.usesApplicationTun2socks():
                logger.info('profile application tun2socks integration is enabled')
                logger.info(
                    f'TUN remote address: '
                    f'{request.configuration.tunRemoteAddress()!r}'
                )
            else:
                logger.info(
                    'profile application tun2socks integration is disabled; '
                    'application-managed TUN will be skipped'
                )

        return KernelLaunch(
            process,
            request.configuration,
            options=request.options,
        )

    def coreExitMessage(self, core, exitcode: int):
        """Describe an external program that exited after successful startup."""
        return 'External core exited unexpectedly'


class ExternalCorePlugin(FuriousPlugin):
    """Bundle local process configuration, editor, and runtime capabilities."""

    metadata = PluginMetadata(
        'official.external-core',
        'External Core',
        description='Run a user-configured local executable as a managed core.',
        provider='Furious',
    )

    def __init__(self):
        """Create isolated capability objects for this plugin instance."""
        self.capabilities = (
            *EXTERNAL_CORE_PROTOCOL_HANDLERS,
            *EXTERNAL_CORE_PROTOCOL_EDITORS,
            ExternalCoreKernelFactory(),
        )
