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

"""Bridge plugin UI capabilities into the host's page-based interface."""

from __future__ import annotations

from Furious.Frozenlib import AppConnectionController
from Furious.Plugins import (
    CapabilityKind,
    NavigationPageDescriptor,
    getPluginRegistry,
)

from PySide6.QtWidgets import QWidget

import logging

__all__ = ['PluginNavigationManager', 'isCoreActive']

logger = logging.getLogger(__name__)


def isCoreActive(coreType) -> bool:
    """Return whether the active connection owns a core of ``coreType``."""
    try:
        controller = AppConnectionController()

        return controller.isConnected() and any(
            isinstance(process, coreType) for process in controller.processes
        )
    except (AttributeError, RuntimeError):
        return False


class PluginNavigationManager:
    """Validate, construct, and retain plugin-contributed navigation pages."""

    def __init__(self, registry=None):
        """Initialize with the process-wide registry unless one is supplied."""
        self.registry = registry or getPluginRegistry()
        self._pages = []

    def registerPages(self, navigationView):
        """Register plugin pages in stable plugin/provider/order sequence."""
        contributions = []

        for plugin in self.registry.plugins():
            metadata = self.registry.metadataFor(plugin)

            for provider in self.registry.capabilities(
                CapabilityKind.NavigationPage,
                plugin,
            ):
                try:
                    descriptors = tuple(provider.pageDescriptors())
                except Exception as ex:
                    logger.error(
                        f'plugin navigation provider '
                        f'{provider.capabilityId!r} failed: {ex}'
                    )

                    continue

                for descriptor in descriptors:
                    if not isinstance(descriptor, NavigationPageDescriptor):
                        logger.error(
                            f'plugin {metadata.id!r} returned an invalid '
                            f'navigation-page descriptor'
                        )

                        continue

                    contributions.append((plugin, metadata, descriptor))

        contributions.sort(key=lambda item: item[2].order)

        for _plugin, metadata, descriptor in contributions:
            pageId = f'plugin:{metadata.id}:{descriptor.id}'

            try:
                page = descriptor.factory(parent=navigationView)
            except Exception as ex:
                logger.error(f'failed to create plugin page {pageId!r}: {ex}')

                continue

            if not isinstance(page, QWidget):
                logger.error(f'plugin page {pageId!r} did not create a QWidget')

                continue

            try:
                navigationView.addPage(
                    pageId,
                    page,
                    descriptor.title,
                    descriptor.iconFileName,
                    translatable=descriptor.translatable,
                )
            except Exception as ex:
                logger.error(f'failed to register plugin page {pageId!r}: {ex}')

                page.deleteLater()

                continue

            self._pages.append((pageId, page))

        return tuple(self._pages)

    def pages(self):
        """Return successfully registered plugin pages."""
        return tuple(self._pages)
