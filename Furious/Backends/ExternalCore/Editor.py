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

"""Provide a structured Fluent-style editor for local executable profiles."""

from __future__ import annotations

from Furious.Interface import EditorWidgetBinding
from Furious.Models import CoreConfiguration, ServerProfile
from Furious.Qt import (
    AppQLabel,
    AppQLineEdit,
    AppQMessageBox,
    AppQPushButton,
    GuiEditorItemBasicRemark,
    GuiEditorItemProxyHttp,
    GuiEditorItemProxySocks,
    GuiEditorItemTextSwitch,
    GuiEditorItemTextSpinBox,
    GuiEditorWidgetQDialog,
    GuiEditorWidgetQGroupBox,
    addEditorGridBinding,
    addEditorGridFullRow,
)
from Furious.Qt import gettext as _
from Furious.Qt.Signals import connectWeakly

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from collections.abc import Mapping
from pathlib import Path

import shlex

__all__ = ['ExternalCoreEditor']


def _connection(config):
    """Return the connection mapping wrapped by an optional profile."""
    return config.connection if isinstance(config, ServerProfile) else config


class ExternalCorePathInput(EditorWidgetBinding):
    """Bind a path field and native file/directory chooser to one key."""

    def __init__(
        self,
        title: str,
        key: str,
        *,
        directory: bool = False,
        placeholder: str = '',
    ):
        """Initialize one translated path editor row."""
        super().__init__()

        self._key = key
        self._directory = directory
        self._title = AppQLabel(_(title), translatable=True)
        self._input = AppQLineEdit()
        self._input.setPlaceholderText(_(placeholder) if placeholder else '')
        self._browse = AppQPushButton(_('Browse...'))

        connectWeakly(self._browse.clicked, self, 'browse')

        container = QWidget()

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._input, 1)
        layout.addWidget(self._browse)

        container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._container = container

    def widgets(self):
        """Return the form-row label and field container."""
        return self._title, self._container

    def text(self) -> str:
        """Return the current path text."""
        return self._input.text().strip()

    @QtCore.Slot()
    def browse(self):
        """Open the native chooser appropriate for this path field."""
        initial = self.text()

        if initial and not Path(initial).exists():
            initial = str(Path(initial).parent)

        if self._directory:
            selected = QFileDialog.getExistingDirectory(
                self._container,
                _('Select Working Directory'),
                initial,
            )
        else:
            selected, _selectedFilter = QFileDialog.getOpenFileName(
                self._container,
                _('Select Executable'),
                initial,
                _('All files (*)'),
            )

        if selected:
            self._input.setText(str(Path(selected).resolve(strict=False)))

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist this path without combining it with command arguments."""
        config = _connection(config)
        oldValue = str(config.get(self._key, ''))
        newValue = self.text()

        if oldValue == newValue:
            return False

        config[self._key] = newValue

        return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load this path from a profile connection mapping."""
        self._input.setText(str(_connection(config).get(self._key, '')))


class ExternalCoreArgumentsInput(EditorWidgetBinding):
    """Bind one quoted command-line field to a persisted argument list."""

    def __init__(self):
        """Initialize the single-line command argument editor."""
        super().__init__()

        self._title = AppQLabel(_('Arguments'), translatable=True)
        self._input = AppQLineEdit()
        self._input.setPlaceholderText(_('Space-separated arguments'))

    def widgets(self):
        """Return the form-row label and line editor."""
        return self._title, self._input

    def values(self) -> list[str]:
        """Parse the editor syntax into arguments without invoking a shell."""
        text = self._input.text().strip()

        if not text:
            return []

        try:
            return shlex.split(text)
        except ValueError as ex:
            raise ValueError('Arguments contain invalid quoting') from ex

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist the literal argument vector."""
        config = _connection(config)
        oldValue = config.get('arguments', [])
        newValue = self.values()

        if oldValue == newValue:
            return False

        config['arguments'] = newValue

        return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load the argument vector using reversible quoted syntax."""
        values = _connection(config).get('arguments', [])

        self._input.setText(
            shlex.join(str(value) for value in values)
            if isinstance(values, list)
            else ''
        )


class ExternalCoreEnvironmentInput(EditorWidgetBinding):
    """Bind KEY=VALUE lines to inherited-environment overrides."""

    def __init__(self):
        """Initialize the environment override editor."""
        super().__init__()

        self._title = AppQLabel(_('Environment Variables'), translatable=True)
        self._input = QPlainTextEdit()
        self._input.setStyleSheet('min-height: 120px; max-height: 136px;')
        self._input.setPlaceholderText(_('KEY=VALUE, one per line'))

    def widgets(self):
        """Return the form-row label and environment editor."""
        return self._title, self._input

    def values(self) -> dict[str, str]:
        """Parse environment overrides while preserving values verbatim."""
        result = {}

        for lineNumber, line in enumerate(self._input.toPlainText().splitlines(), 1):
            if not line.strip():
                continue

            key, separator, value = line.partition('=')
            key = key.strip()

            if not separator or not key or '=' in key or '\0' in key or '\0' in value:
                raise ValueError(
                    f'Environment entry on line {lineNumber} must use KEY=VALUE'
                )

            result[key] = value

        return result

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist validated environment overrides as a mapping."""
        config = _connection(config)
        oldValue = config.get('environment', {})
        newValue = self.values()

        if oldValue == newValue:
            return False

        config['environment'] = newValue

        return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load environment overrides as KEY=VALUE lines."""
        values = _connection(config).get('environment', {})

        self._input.setPlainText(
            '\n'.join(f'{key}={value}' for key, value in values.items())
            if isinstance(values, Mapping)
            else ''
        )


class ExternalCoreShutdownTimeoutInput(GuiEditorItemTextSpinBox):
    """Bind the bounded external-process shutdown timeout."""

    def __init__(self):
        """Initialize a one-to-sixty-second timeout input."""
        super().__init__(title=_('Shutdown Timeout (seconds)'), translatable=True)

        self.setRange(1, 60)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist the selected shutdown timeout."""
        config = _connection(config)
        oldValue = config.get('shutdownTimeout', 5)
        newValue = self.value()

        if oldValue == newValue:
            return False

        config['shutdownTimeout'] = newValue

        return True

    def factoryToInput(self, config: CoreConfiguration):
        """Load the configured shutdown timeout."""
        value = _connection(config).get('shutdownTimeout', 5)

        self.setValue(value if isinstance(value, int) else 5)


class ExternalCoreApplicationTun2socksInput(GuiEditorItemTextSwitch):
    """Bind this profile's host-managed tun2socks participation flag."""

    def __init__(self):
        """Initialize the application tun2socks opt-in control."""
        super().__init__(title=_('Use Application Tun2socks'), translatable=True)

    def connectToggled(self, receiver, methodName: str):
        """Connect a field-state callback without retaining its binding."""
        connectWeakly(self._input.toggled, receiver, methodName)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist the explicit application tun2socks preference."""
        return _connection(config).setUseApplicationTun2socks(self.isChecked())

    def factoryToInput(self, config: CoreConfiguration):
        """Restore the application tun2socks preference."""
        self.setChecked(_connection(config).usesApplicationTun2socks())


class ExternalCoreTunRemoteAddressInput(EditorWidgetBinding):
    """Bind the remote destination used only by application-managed TUN."""

    def __init__(self):
        """Initialize a hostname-or-IP input independent of process paths."""
        super().__init__()

        self._title = AppQLabel(_('TUN Remote Address'), translatable=True)
        self._input = AppQLineEdit()
        self._input.setPlaceholderText(_('Hostname, IPv4, or IPv6 address'))

    def widgets(self):
        """Return the form-row label and remote-address editor."""
        return self._title, self._input

    def text(self) -> str:
        """Return the normalized remote-address text."""
        return self._input.text().strip()

    def setEnabled(self, enabled: bool):
        """Enable both parts of this dependent form row."""
        self._title.setEnabled(enabled)
        self._input.setEnabled(enabled)

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist the remote destination without interpreting it as a path."""
        return _connection(config).setTunRemoteAddress(self.text())

    def factoryToInput(self, config: CoreConfiguration):
        """Restore the configured TUN remote destination."""
        self._input.setText(_connection(config).tunRemoteAddress())


class ExternalCoreConfigurationGroup(GuiEditorWidgetQGroupBox):
    """Present External Core profile and process settings."""

    def __init__(
        self,
        argumentsInput: ExternalCoreArgumentsInput,
        environmentInput: ExternalCoreEnvironmentInput,
    ):
        """Initialize the process form around its shared validated inputs."""
        self._argumentsInput = argumentsInput
        self._environmentInput = environmentInput

        super().__init__(_('Basic Configuration'))

    def containerSequence(self):
        """Return profile and process fields in display order."""
        return (
            GuiEditorItemBasicRemark(title=_('Remark')),
            ExternalCorePathInput(_('Executable'), 'executable'),
            ExternalCorePathInput(
                _('Working Directory'),
                'workingDirectory',
                directory=True,
                placeholder=_('Defaults to executable folder'),
            ),
            self._argumentsInput,
            self._environmentInput,
        )

    def setupPageLayout(self):
        """Arrange process fields as full rows like the VLESS remark row."""
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)

        for row, container in enumerate(self._containers):
            addEditorGridFullRow(layout, container, row)

        layout.setRowStretch(len(self._containers), 1)

        return layout


class ExternalCoreOtherGroup(GuiEditorWidgetQGroupBox):
    """Present the remaining External Core process and network settings."""

    def __init__(
        self,
        applicationTun2socksInput: ExternalCoreApplicationTun2socksInput,
        tunRemoteAddressInput: ExternalCoreTunRemoteAddressInput,
    ):
        """Initialize the secondary form around its shared validated inputs."""
        self._applicationTun2socksInput = applicationTun2socksInput
        self._tunRemoteAddressInput = tunRemoteAddressInput

        super().__init__(_('Other'))

    def containerSequence(self):
        """Return secondary process, proxy, and TUN fields in display order."""
        return (
            ExternalCoreShutdownTimeoutInput(),
            GuiEditorItemProxyHttp(title=_('HTTP Proxy')),
            GuiEditorItemProxySocks(title=_('SOCKS Proxy')),
            self._applicationTun2socksInput,
            self._tunRemoteAddressInput,
        )

    def setupPageLayout(self):
        """Arrange secondary fields and keep the timeout compact like VLESS port."""
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)

        timeoutInput = self._containers[0].widgets()[1]

        if isinstance(timeoutInput, QSpinBox):
            timeoutInput.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                timeoutInput.sizePolicy().verticalPolicy(),
            )

        for row, container in enumerate(self._containers):
            if row in (1, 2, 4):
                addEditorGridFullRow(layout, container, row)
            else:
                addEditorGridBinding(layout, container, row, 0)

        layout.setRowStretch(len(self._containers), 1)

        return layout


class ExternalCoreEditor(GuiEditorWidgetQDialog):
    """Edit one External Core profile without retaining it after close."""

    def __init__(self, *args, **kwargs):
        """Initialize the External Core configuration editor."""
        self._argumentsInput = ExternalCoreArgumentsInput()
        self._environmentInput = ExternalCoreEnvironmentInput()
        self._applicationTun2socksInput = ExternalCoreApplicationTun2socksInput()
        self._tunRemoteAddressInput = ExternalCoreTunRemoteAddressInput()
        self._applicationTun2socksInput.connectToggled(
            self._tunRemoteAddressInput,
            'setEnabled',
        )
        self._tunRemoteAddressInput.setEnabled(False)

        super().__init__(*args, **kwargs)

        self.setFixedSize(1400, 600)
        self.setTabText(_('External Core'))

    def createGroupBoxSequence(self):
        """Create separate basic and secondary configuration groups."""
        return [
            ExternalCoreConfigurationGroup(
                self._argumentsInput,
                self._environmentInput,
            ),
            ExternalCoreOtherGroup(
                self._applicationTun2socksInput,
                self._tunRemoteAddressInput,
            ),
        ]

    def inputToFactory(self, config: CoreConfiguration) -> bool:
        """Persist editor values and normalize both local paths."""
        modified = super().inputToFactory(config)
        connection = _connection(config)
        oldPaths = (
            connection.get('executable', ''),
            connection.get('workingDirectory', ''),
        )
        connection.normalizePaths()

        return modified or oldPaths != (
            connection.get('executable', ''),
            connection.get('workingDirectory', ''),
        )

    def accept(self):
        """Keep malformed arguments or environment rows open for correction."""
        try:
            self._argumentsInput.values()
        except ValueError:
            validationMessage = _('Arguments contain invalid quoting.')
        else:
            try:
                self._environmentInput.values()
            except ValueError:
                validationMessage = _(
                    'Environment variables must use KEY=VALUE, one per line.'
                )
            else:
                validationMessage = ''

        if (
            not validationMessage
            and self._applicationTun2socksInput.isChecked()
            and not self._tunRemoteAddressInput.text()
        ):
            validationMessage = _(
                'TUN remote address is required when application tun2socks is enabled'
            )

        if validationMessage:
            mbox = AppQMessageBox(
                icon=AppQMessageBox.Icon.Warning,
                parent=self,
            )
            mbox.setHeading(_('Invalid data'))
            mbox.setText(validationMessage)
            mbox.open()

            return

        # No error messages. Accept
        super().accept()
