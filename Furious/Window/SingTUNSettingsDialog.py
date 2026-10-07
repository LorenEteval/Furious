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

"""A staged, transient editor for sing-tun's native and host configuration."""

from __future__ import annotations

from Furious.Models.SingTUN import (
    SING_TUN_DEFAULTS,
    SING_TUN_HOST_DEFAULTS,
    prepareSingTUNSettings,
)
from Furious.Repository import Storage
from Furious.Frozenlib import PLATFORM, GOLDEN_RATIO, AppFontName
from Furious.Qt import (
    AppQTransientDialog,
    AppQLabel,
    AppQLineEdit,
    AppQComboBox,
    AppQSpinBox,
    AppQSwitch,
    AppQTabWidget,
    AppQDialogButtonBox,
    DraculaJSONTextEditor,
)
from Furious.Qt.Signals import connectWeakly, singleShotWeakly
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QStyle,
    QStyleOptionFrame,
)

import copy
import json


class SingTUNSettingsDialog(AppQTransientDialog):
    """Never import the native engine or mutate storage while loading widgets."""

    FIXED_DIALOG_SIZE = (
        QtCore.QSize(int(690 * GOLDEN_RATIO), 690)
        if PLATFORM in ('Darwin', 'Linux')
        else QtCore.QSize(int(620 * GOLDEN_RATIO), 620)
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Customize sing-tun Settings'))

        self._original = copy.deepcopy(Storage.UserSingTUNSettings())
        self.fields = {}

        self.tabs = AppQTabWidget(self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        common = copy.deepcopy(SING_TUN_DEFAULTS)

        for key, value in self._original.items():
            if key in ('tun_options', 'stack_options', 'host_options') and isinstance(
                value, dict
            ):
                common[key].update(value)
            elif key in common:
                common[key] = value

        bridge = self._page(_('SOCKS Transit'))

        self._choice(
            bridge,
            'stack',
            _('Stack'),
            [
                ('go', 'go'),
                ('gvisor', 'gvisor'),
                ('system', 'system'),
                ('mixed', 'mixed'),
                (_('Automatic'), ''),
            ],
            common.get('stack'),
        )
        self._choice(
            bridge,
            'log_level',
            _('Log Level'),
            [
                (value, value)
                for value in ('trace', 'debug', 'info', 'warn', 'error', 'silent')
            ],
            common.get('log_level'),
        )
        self._text(
            bridge,
            'network_interface',
            _('SOCKS Interface Binding'),
            common.get('network_interface'),
            placeholder=_('empty for automatic'),
            maximumWidth=360,
        )
        self._number(
            bridge,
            'max_sessions',
            _('Maximum Sessions'),
            common.get('max_sessions'),
            1,
            16384,
        )

        self._text(
            bridge,
            'connect_timeout',
            _('Connect Timeout (seconds)'),
            common.get('connect_timeout'),
            maximumWidth=160,
        )
        self._text(
            bridge,
            'udp_timeout',
            _('SOCKS UDP Timeout (seconds)'),
            common.get('udp_timeout'),
            maximumWidth=160,
        )
        self._text(
            bridge,
            'tcp_idle_timeout',
            _('TCP Idle Timeout (seconds)'),
            common.get('tcp_idle_timeout'),
            maximumWidth=160,
        )

        native = self._page(_('Interface and Stack'))
        tun = (
            common['tun_options']
            if isinstance(common.get('tun_options'), dict)
            else SING_TUN_DEFAULTS['tun_options']
        )

        self._text(
            native,
            'Name',
            _('Device Name'),
            tun.get('Name', ''),
            placeholder=_('empty for automatic'),
            maximumWidth=360,
        )
        self._number(native, 'MTU', _('MTU'), tun.get('MTU', 1500), 68, 65535)
        self._text(
            native,
            'Inet4Address',
            _('IPv4 Address Prefixes'),
            (
                ', '.join(str(value) for value in tun.get('Inet4Address', []))
                if isinstance(tun.get('Inet4Address'), list)
                else ''
            ),
            placeholder=_('separated by commas'),
            maximumWidth=600,
        )
        self._text(
            native,
            'Inet6Address',
            _('IPv6 Address Prefixes'),
            (
                ', '.join(str(value) for value in tun.get('Inet6Address', []))
                if isinstance(tun.get('Inet6Address'), list)
                else ''
            ),
            placeholder=_('separated by commas'),
            maximumWidth=600,
        )

        stack = (
            common['stack_options']
            if isinstance(common.get('stack_options'), dict)
            else {}
        )

        self._choice(
            native,
            'TCPCongestionControl',
            _('TCP Congestion Control'),
            [
                (_('Automatic'), ''),
                ('cubic', 'cubic'),
                ('reno', 'reno'),
                ('bbr', 'bbr'),
            ],
            stack.get('TCPCongestionControl', ''),
        )
        self.fields['TCPCongestionControl'].setToolTip(
            _('Available when Stack is set to go or Automatic.')
        )

        self._text(
            native,
            'UDPNATMax',
            _('Native UDP NAT Limit'),
            stack.get('UDPNATMax', 0),
            placeholder=_('0 for default'),
            maximumWidth=200,
        )
        self._text(
            native,
            'UDPTimeout',
            _('Native UDP Timeout'),
            stack.get('UDPTimeout', '1m'),
            placeholder=_('duration with units, e.g. 1m'),
            maximumWidth=180,
        )
        self._text(
            native,
            'ICMPTimeout',
            _('Native ICMP Timeout'),
            stack.get('ICMPTimeout', '0'),
            placeholder=_('duration with units, or 0 for default'),
            maximumWidth=180,
        )

        for key, label in (
            ('UDPMapping', _('UDP Mapping')),
            ('UDPFiltering', _('UDP Filtering')),
        ):
            self._choice(
                native,
                key,
                label,
                [
                    (_('Endpoint Independent'), 0),
                    (_('Address Dependent'), 1),
                    (_('Address and Port Dependent'), 2),
                ],
                stack.get(key, 0),
            )

        host = (
            common['host_options']
            if isinstance(common.get('host_options'), dict)
            else SING_TUN_HOST_DEFAULTS
        )
        hostForm = self._page(_('Host Settings'))

        for key, label, width in (
            ('primaryAdapterInterfaceName', _('Primary Adapter Interface Name'), 360),
            ('primaryAdapterInterfaceIP', _('Primary Adapter Interface IP'), 360),
            ('tunAdapterInterfaceDNS', _('TUN Adapter Interface DNS'), 360),
            (
                'bypassTUNAdapterInterfaceIP',
                _('Bypass TUN Adapter Interface IP (separated by commas)'),
                600,
            ),
        ):
            self._text(hostForm, key, label, host.get(key, ''), maximumWidth=width)

        self.disableDNS = AppQSwitch()
        self.disableDNS.setChecked(
            host.get('disablePrimaryAdapterInterfaceDNS', True) is True
        )

        disableDNSRow = QHBoxLayout()
        disableDNSRow.setContentsMargins(0, 0, 0, 0)
        disableDNSRow.addWidget(
            AppQLabel(
                _(
                    'Disable Primary Adapter Interface DNS (Mitigating DNS leaks on Windows)'
                )
            )
        )
        disableDNSRow.addWidget(self.disableDNS)
        disableDNSRow.addStretch()
        hostForm.addRow(disableDNSRow)

        advanced = self._page(_('Advanced Options'))

        self.advanced = DraculaJSONTextEditor(fontFamily=AppFontName())
        self.advanced.setLineWrapMode(DraculaJSONTextEditor.LineWrapMode.NoWrap)

        extra = copy.deepcopy(self._original)

        for key in SING_TUN_DEFAULTS:
            if key not in ('tun_options', 'stack_options', 'host_options'):
                extra.pop(key, None)

        for key, represented in (
            ('tun_options', ('Name', 'MTU', 'Inet4Address', 'Inet6Address')),
            ('host_options', tuple(SING_TUN_HOST_DEFAULTS)),
            (
                'stack_options',
                (
                    'UDPTimeout',
                    'ICMPTimeout',
                    'UDPNATMax',
                    'UDPMapping',
                    'UDPFiltering',
                    'TCPCongestionControl',
                ),
            ),
        ):
            if isinstance(extra.get(key), dict):
                for field in represented:
                    extra[key].pop(field, None)

        self.advanced.setPlainText(json.dumps(extra, indent=2, ensure_ascii=False))

        advanced.addRow(self.advanced)

        instructions = AppQLabel(
            _(
                'Use exact native JSON field names. Supported: route address/exclusion '
                'lists, StrictRoute, InterfaceScope, ForwarderBindInterface and '
                'IncludeAllNetworks. AutoRoute, external configuration and DNS '
                'ownership are managed. Unsupported fields are rejected.'
            )
        )
        instructions.setWordWrap(True)
        advanced.addRow(instructions)

        self.errorLabel = AppQLabel('')
        self.errorLabel.setWordWrap(True)

        layout.addWidget(self.errorLabel)

        buttons = AppQDialogButtonBox(
            AppQDialogButtonBox.StandardButton.Ok
            | AppQDialogButtonBox.StandardButton.Cancel
        )

        connectWeakly(buttons.accepted, self, 'accept')
        connectWeakly(buttons.rejected, self, 'reject')

        layout.addWidget(buttons)

    def _fitDurationInputs(self):
        for key in ('UDPTimeout', 'ICMPTimeout'):
            widget = self.fields[key]
            widget.ensurePolished()

            option = QStyleOptionFrame()
            widget.initStyleOption(option)

            margins = widget.textMargins()
            textWidth = widget.fontMetrics().horizontalAdvance(widget.placeholderText())
            size = widget.style().sizeFromContents(
                QStyle.ContentsType.CT_LineEdit,
                option,
                QtCore.QSize(
                    textWidth + margins.left() + margins.right() + 4,
                    widget.sizeHint().height(),
                ),
                widget,
            )
            width = max(180, size.width() + 80)

            widget.setMinimumWidth(width)
            widget.setMaximumWidth(width)

    def showEvent(self, event):
        super().showEvent(event)

        self._fitDurationInputs()

    def retranslate(self):
        super().retranslate()

        singleShotWeakly(0, self, '_fitDurationInputs')

    def _page(self, title):
        page = QWidget()

        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)

        self.tabs.addTab(scroll, title)

        return form

    def _addField(self, form, label, widget):
        form.addRow(AppQLabel(label), widget)

    def _text(self, form, key, label, value, *, placeholder='', maximumWidth=None):
        widget = AppQLineEdit()
        widget.setText(str(value) if value is not None else '')
        widget.setPlaceholderText(placeholder)

        if maximumWidth is not None:
            widget.setMaximumWidth(maximumWidth)

        self.fields[key] = widget

        self._addField(form, label, widget)

    def _number(self, form, key, label, value, minimum, maximum):
        widget = AppQSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value if type(value) is int else minimum)
        widget.setMaximumWidth(135)

        self.fields[key] = widget

        self._addField(form, label, widget)

    def _choice(self, form, key, label, choices, value):
        widget = AppQComboBox()

        for text, data in choices:
            widget.addItem(text, data)

        widget.setCurrentIndex(max(widget.findData(value), 0))

        self.fields[key] = widget

        self._addField(form, label, widget)

    def document(self):
        """Prepare sing-tun's complete candidate before its live collection changes."""
        document = json.loads(self.advanced.toPlainText())

        if not isinstance(document, dict):
            raise ValueError('Advanced options must be a JSON object')

        tun = document.setdefault('tun_options', {})
        stack = document.setdefault('stack_options', {})

        if not isinstance(tun, dict) or not isinstance(stack, dict):
            raise ValueError('Native options must be JSON objects')

        for key in ('stack', 'log_level'):
            document[key] = self.fields[key].currentData()

        document['network_interface'] = self.fields['network_interface'].text().strip()
        document['max_sessions'] = self.fields['max_sessions'].value()

        for key in ('connect_timeout', 'udp_timeout', 'tcp_idle_timeout'):
            document[key] = float(self.fields[key].text())

        tun['Name'], tun['MTU'] = (
            self.fields['Name'].text().strip(),
            self.fields['MTU'].value(),
        )

        for key in ('Inet4Address', 'Inet6Address'):
            tun[key] = [
                value.strip()
                for value in self.fields[key].text().split(',')
                if value.strip()
            ]

        for key in ('UDPTimeout', 'ICMPTimeout'):
            value = self.fields[key].text().strip()
            stack[key] = int(value) if value.isdigit() else value

        stack['UDPNATMax'] = int(self.fields['UDPNATMax'].text())

        for key in ('UDPMapping', 'UDPFiltering', 'TCPCongestionControl'):
            stack[key] = self.fields[key].currentData()

        host = document.setdefault('host_options', {})

        if not isinstance(host, dict):
            raise ValueError('sing-tun host options must be a JSON object')

        for key in (
            'primaryAdapterInterfaceName',
            'primaryAdapterInterfaceIP',
            'tunAdapterInterfaceDNS',
            'bypassTUNAdapterInterfaceIP',
        ):
            host[key] = self.fields[key].text().strip()

        host['disablePrimaryAdapterInterfaceDNS'] = self.disableDNS.isChecked()

        prepareSingTUNSettings(document, platform=PLATFORM)

        return document

    def accept(self):
        try:
            document = self.document()

            Storage.replaceSingTUNSettings(document)
        except (ValueError, TypeError, OSError) as ex:
            self.errorLabel.setText(str(ex))

            return

        super().accept()
