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

"""Provide the application window for user routing window."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Models import *
from Furious.Repository import *
from Furious.Qt import *
from Furious.Qt.Signals import connectWeakly
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import copy
import uuid
import logging
import functools

from .Routing import cleanRoutingRule

__all__ = [
    'XrayRoutingWindow',
    # Begin export for testing
    'RoutingPreviewDialog',
    'RoutingRuleEditDialog',
    'RoutingRulesDialog',
    # End export for testing
]

logger = logging.getLogger(__name__)

registerAppSettings('UserRoutingWindowGeometry')
registerAppSettings('UserRoutingWindowState')
registerAppSettings('UserRoutingHeaderViewState')

DOMAIN_STRATEGIES, ROUTING_STATES = (
    ['AsIs', 'IPIfNonMatch', 'IPOnDemand'],
    ['Enabled', 'Disabled'],
)


def valuesToList(text: str) -> list[str]:
    """Return the values to list value used by the application."""
    values = list()

    for line in text.splitlines():
        for value in line.split(','):
            value = value.strip()

            if value:
                values.append(value)

    return values


def listToText(value) -> str:
    """Return the list to text value used by the application."""
    if isinstance(value, list):
        return '\n'.join(str(item) for item in value)

    return ''


def routingStateText(state: str) -> str:
    """Return the routing state text value used by the application."""
    if state == 'Enabled':
        return _('Enabled')
    elif state == 'Disabled':
        return _('Disabled')

    return _(state)


def addRoutingStateItems(combo: QComboBox):
    """Add routing state items."""
    combo.clear()

    for state in ROUTING_STATES:
        combo.addItem(routingStateText(state), state)


def comboCurrentData(combo: QComboBox, default=''):
    """Return the combo current data value used by the application."""
    data = combo.currentData()

    if data is None:
        return default

    return data


def routingObjectFromProfile(routingProfile: dict):
    """Return the routing object from profile value used by the application."""
    if not isinstance(routingProfile, dict):
        routingProfile = dict()

    domainStrategy = routingProfile.get('domainStrategy', 'AsIs')

    if domainStrategy not in DOMAIN_STRATEGIES:
        domainStrategy = 'AsIs'

    rules = list(
        filter(
            lambda rule: rule is not None,
            list(cleanRoutingRule(rule) for rule in routingProfile.get('rules', [])),
        )
    )

    return {
        'domainStrategy': domainStrategy,
        'domainMatcher': 'hybrid',
        'rules': rules,
    }


class RoutingPreviewDialog(AppQTransientDialog):
    """Present the routing preview dialog."""

    FIXED_DIALOG_SIZE = QtCore.QSize(400, int(400 * GOLDEN_RATIO))

    def __init__(self, routingProfile: dict, parent=None):
        """Initialize the RoutingPreviewDialog."""
        super().__init__(parent)

        self.setWindowTitle(_('Preview Routing'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.textEditor = DraculaJSONTextEditor(fontFamily=AppFontName())
        self.textEditor.setLineWrapMode(DraculaJSONTextEditor.LineWrapMode.NoWrap)
        self.textEditor.setPlainText(
            UJSONEncoder.encode(routingObjectFromProfile(routingProfile), indent=4)
        )
        self.textEditor.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.textEditor)

        self.setLayout(layout)


class RoutingTextEditDialog(AppQTransientDialog):
    """Present the routing text edit dialog."""

    FIXED_DIALOG_SIZE = QtCore.QSize(760, 470)

    def __init__(self, text='', parent=None):
        """Initialize the RoutingTextEditDialog."""
        super().__init__(parent)

        self.setWindowTitle(_('Edit Text'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.textEdit = QTextEdit()
        self.textEdit.setPlainText(text)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )

        connectWeakly(self.dialogBtns.accepted, self, 'accept')
        connectWeakly(self.dialogBtns.rejected, self, 'reject')

        layout = QVBoxLayout()
        layout.addWidget(self.textEdit)
        layout.addWidget(self.dialogBtns)

        self.setLayout(layout)

    def text(self):
        """Return the text value."""
        return self.textEdit.toPlainText()


class RoutingTextEdit(Mixins.QTranslatable, QTextEdit):
    """Represent routing text edit."""

    def __init__(self, plainText='', placeholderText='', parent=None):
        """Initialize the RoutingTextEdit."""
        super().__init__(parent)

        self.setPlainText(plainText)
        self.setPlaceholderText(placeholderText)
        self.setToolTip(_('Double-click to enlarge'))

    def mouseDoubleClickEvent(self, event):
        """Handle the mouse double click event."""
        dialog = RoutingTextEditDialog(self.toPlainText(), parent=self)

        def handleResultCode(code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.setPlainText(dialog.text())

        dialog.finished.connect(handleResultCode)
        dialog.open()

        event.accept()

    def retranslate(self):
        """Refresh translated text for the routing text edit."""
        self.setPlaceholderText(_(self.placeholderText()))
        self.setToolTip(_(self.toolTip()))


class RoutingDocumentationURL(AppQLabel):
    """Represent routing documentation URL."""

    URL = 'https://xtls.github.io/config/routing.html'

    def __init__(self, *args, **kwargs):
        """Initialize the RoutingDocumentationURL."""
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        """Set website URL."""
        self.setText(
            '<html><head/><body><p>'
            f'<a href="{self.URL}">'
            '<span style=" text-decoration: underline; color:#007ad6;">'
            + _('Routing Documentation')
            + '</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        """Handle link activated."""
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        """Refresh translated text for the routing documentation URL."""
        self.setWebsiteURL()


class RoutingProfilesModel(QtCore.QAbstractTableModel):
    """Expose routing profiles data through a Qt item model."""

    Headers = ['Remark', 'Domain Strategy', 'State']

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of rows exposed by the model."""
        if parent.isValid():
            return 0

        return len(Storage.UserRoutings())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        """Return the number of columns exposed by the model."""
        if parent.isValid():
            return 0

        return len(self.Headers)

    def flags(self, index):
        """Return the Qt item flags for a model index."""
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Return display data for a table header section."""
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            header = self.Headers[section]

            if header in ['Remark', 'State']:
                return _(header)

            return header

        return section + 1

    def routingUniqueByRow(self, row: int):
        """Return the routing unique by row value used by the routing profiles model."""
        return list(Storage.UserRoutings().keys())[row]

    def routingByRow(self, row: int):
        """Return the routing by row value used by the routing profiles model."""
        return Storage.UserRoutings()[self.routingUniqueByRow(row)]

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        """Return the data managed by the routing profiles model."""
        if not index.isValid():
            return None

        row, column = index.row(), index.column()

        if row < 0 or row >= len(Storage.UserRoutings()):
            return None

        routing = self.routingByRow(row)

        if role in [
            QtCore.Qt.ItemDataRole.DisplayRole,
            QtCore.Qt.ItemDataRole.EditRole,
        ]:
            if column == 0:
                return routing.get('remark', '')
            elif column == 1:
                return routing.get('domainStrategy', 'AsIs')
            elif column == 2:
                return routingStateText(
                    'Enabled' if routing.get('enabled', True) else 'Disabled'
                )

        return None

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        """Update model data for the requested role."""
        return False

    def emitAllChanged(self):
        """Handle emit all changed for the routing profiles model."""
        if self.rowCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
        )


class RoutingRuleEditDialog(AppQTransientDialog):
    """Present the routing rule edit dialog."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(int(800 * GOLDEN_RATIO), 800)

    MatchInputHeight = 65
    ShortInputWidth = 240

    @staticmethod
    def textEdit(text='', placeholderText=''):
        """Return the text edit value used by the routing rule edit dialog."""
        widget = RoutingTextEdit(text, placeholderText)
        widget.setFixedHeight(RoutingRuleEditDialog.MatchInputHeight)

        return widget

    @staticmethod
    def lineEdit(text='', placeholderText=''):
        """Return the line edit value used by the routing rule edit dialog."""
        widget = AppQLineEdit(text)
        widget.setPlaceholderText(placeholderText)
        widget.setFixedHeight(RoutingRuleEditDialog.MatchInputHeight)

        return widget

    @staticmethod
    def _createGroupBox(title: str, rows):
        """Create one routing section using the protocol-editor grid structure."""
        page = QWidget()

        pageLayout = QGridLayout()
        pageLayout.setColumnStretch(1, 1)
        pageLayout.setColumnStretch(3, 1)

        for row, (labelText, inputWidget) in enumerate(rows):
            pageLayout.addWidget(
                AppQLabel(labelText, translatable=False),
                row,
                0,
            )
            pageLayout.addWidget(inputWidget, row, 1, 1, 3)

        pageLayout.setRowStretch(len(rows), 1)
        page.setLayout(pageLayout)

        groupBox = AppQGroupBox(title, translatable=False)
        pageStack = QStackedWidget()
        pageStack.addWidget(page)

        groupBoxLayout = QVBoxLayout()
        groupBoxLayout.addWidget(pageStack)
        groupBox.setLayout(groupBoxLayout)

        return groupBox

    def __init__(self, rule: dict, parent=None):
        """Initialize the RoutingRuleEditDialog."""
        super().__init__(parent)

        self.rule = dict(rule)

        self.setWindowTitle(_('Edit Routing Rule'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        (
            self.ruleTagEdit,
            self.outboundEdit,
            self.balancerTagEdit,
        ) = (
            self.lineEdit(
                self.rule.get('ruleTag', ''),
                _('Optional rule name, e.g. block-ads'),
            ),
            self.lineEdit(
                self.rule.get('outboundTag', ''),
                _('Outbound tag, e.g. proxy, direct, block'),
            ),
            self.lineEdit(
                str(self.rule.get('balancerTag', '')),
                _('Balancer tag, e.g. balancer'),
            ),
        )

        self.networkCombo = AppQComboBox(translatable=False)
        self.networkCombo.addItems(['', 'tcp', 'udp', 'tcp,udp'])
        self.networkCombo.setCurrentText(self.rule.get('network', ''))
        self.networkCombo.setMaximumWidth(self.ShortInputWidth)

        portPlaceholder = _('e.g. 53,443,1000-2000')

        (
            self.portEdit,
            self.sourcePortEdit,
            self.localPortEdit,
            self.vlessRouteEdit,
            self.domainEdit,
            self.ipEdit,
            self.sourceIPEdit,
            self.localIPEdit,
            self.userEdit,
            self.protocolEdit,
            self.inboundTagEdit,
            self.processEdit,
        ) = (
            self.textEdit(
                str(self.rule.get('port', '')),
                portPlaceholder,
            ),
            self.textEdit(
                str(self.rule.get('sourcePort', '')),
                portPlaceholder,
            ),
            self.textEdit(
                str(self.rule.get('localPort', '')),
                portPlaceholder,
            ),
            self.textEdit(
                str(self.rule.get('vlessRoute', '')),
                portPlaceholder,
            ),
            self.textEdit(
                listToText(self.rule.get('domain', [])),
                _(r'e.g. domain:xray.com, geosite:cn, regexp:\.google\.com$'),
            ),
            self.textEdit(
                listToText(self.rule.get('ip', [])),
                _('e.g. 10.0.0.0/8, geoip:cn, !geoip:private'),
            ),
            self.textEdit(
                listToText(self.rule.get('sourceIP', [])),
                _('e.g. 10.0.0.1, 192.168.1.0/24'),
            ),
            self.textEdit(
                listToText(self.rule.get('localIP', [])),
                _('e.g. 192.168.0.25'),
            ),
            self.textEdit(
                listToText(self.rule.get('user', [])),
                _('e.g. love@xray.com'),
            ),
            self.textEdit(
                listToText(self.rule.get('protocol', [])),
                _('e.g. http, tls, quic, bittorrent'),
            ),
            self.textEdit(
                listToText(self.rule.get('inboundTag', [])),
                _('e.g. tag-vmess'),
            ),
            self.textEdit(
                listToText(self.rule.get('process', [])),
                _('e.g. curl'),
            ),
        )

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )

        connectWeakly(self.dialogBtns.accepted, self, 'accept')
        connectWeakly(self.dialogBtns.rejected, self, 'reject')

        (
            generalGroup,
            destinationGroup,
            sourceGroup,
            identityGroup,
        ) = (
            self._createGroupBox(
                'General',
                (
                    ('Rule Tag', self.ruleTagEdit),
                    ('OutBound', self.outboundEdit),
                    ('Balancer Tag', self.balancerTagEdit),
                    ('Network', self.networkCombo),
                ),
            ),
            self._createGroupBox(
                'Destination Match',
                (
                    ('Domain', self.domainEdit),
                    ('IP', self.ipEdit),
                    ('Port', self.portEdit),
                    ('VLESS Route', self.vlessRouteEdit),
                ),
            ),
            self._createGroupBox(
                'Source / Local Match',
                (
                    ('Source IP', self.sourceIPEdit),
                    ('Source Port', self.sourcePortEdit),
                    ('Local IP', self.localIPEdit),
                    ('Local Port', self.localPortEdit),
                ),
            ),
            self._createGroupBox(
                'Identity / Process / Protocol Match',
                (
                    ('User', self.userEdit),
                    ('Inbound Tag', self.inboundTagEdit),
                    ('Process', self.processEdit),
                    ('Protocol', self.protocolEdit),
                ),
            ),
        )

        matchGrid = QGridLayout()
        matchGrid.addWidget(generalGroup, 0, 0)
        matchGrid.addWidget(destinationGroup, 0, 1)
        matchGrid.addWidget(sourceGroup, 1, 0)
        matchGrid.addWidget(identityGroup, 1, 1)
        matchGrid.setColumnStretch(0, 1)
        matchGrid.setColumnStretch(1, 1)

        matchPage = QWidget()
        matchPage.setLayout(matchGrid)

        bottomLayout = QHBoxLayout()
        bottomLayout.addWidget(RoutingDocumentationURL())
        bottomLayout.addStretch(1)
        bottomLayout.addWidget(self.dialogBtns)

        layout = QVBoxLayout()
        layout.addWidget(matchPage)
        layout.addLayout(bottomLayout)

        self.setLayout(layout)

    def routingRule(self):
        """Return the routing rule value used by the routing rule edit dialog."""
        rule = {
            'type': 'field',
            'outboundTag': self.outboundEdit.text().strip() or 'proxy',
        }

        for key, value in [
            ('ruleTag', self.ruleTagEdit.text().strip()),
            ('network', self.networkCombo.currentText().strip()),
            ('port', self.portEdit.toPlainText().strip()),
            ('sourcePort', self.sourcePortEdit.toPlainText().strip()),
            ('localPort', self.localPortEdit.toPlainText().strip()),
            ('vlessRoute', self.vlessRouteEdit.toPlainText().strip()),
            ('balancerTag', self.balancerTagEdit.text().strip()),
        ]:
            if value:
                rule[key] = value

        for key, widget in [
            ('domain', self.domainEdit),
            ('ip', self.ipEdit),
            ('sourceIP', self.sourceIPEdit),
            ('localIP', self.localIPEdit),
            ('user', self.userEdit),
            ('protocol', self.protocolEdit),
            ('inboundTag', self.inboundTagEdit),
            ('process', self.processEdit),
        ]:
            values = valuesToList(widget.toPlainText())

            if values:
                rule[key] = values

        return rule


class RoutingRemarkEditDialog(AppQTransientDialog):
    """Present the routing remark edit dialog."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(420, 120)

    def __init__(self, remark: str, parent=None):
        """Initialize the RoutingRemarkEditDialog."""
        super().__init__(parent)

        self.setWindowTitle(_('Edit Routing Remark'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.remarkEdit = AppQLineEdit(remark)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )

        connectWeakly(self.dialogBtns.accepted, self, 'accept')
        connectWeakly(self.dialogBtns.rejected, self, 'reject')

        layout = QFormLayout()
        layout.addRow(AppQLabel(_('Remark')), self.remarkEdit)
        layout.addRow(self.dialogBtns)

        self.setLayout(layout)

    def remark(self):
        """Return the remark value used by the routing remark edit dialog."""
        return self.remarkEdit.text().strip()


class RoutingProfileEditDialog(AppQTransientDialog):
    """Present the routing profile edit dialog."""

    DEFAULT_DIALOG_SIZE = QtCore.QSize(460, 160)

    def __init__(self, parent=None):
        """Initialize the RoutingProfileEditDialog."""
        super().__init__(parent)

        self.setWindowTitle(_('Add Routing'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.remarkEdit = AppQLineEdit(_('New Routing'))

        self.domainStrategyCombo = AppQComboBox(translatable=False)
        self.domainStrategyCombo.addItems(DOMAIN_STRATEGIES)
        self.domainStrategyCombo.setCurrentText('AsIs')

        self.enabledCombo = AppQComboBox(translatable=False)
        addRoutingStateItems(self.enabledCombo)
        self.enabledCombo.setCurrentIndex(ROUTING_STATES.index('Enabled'))

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )

        connectWeakly(self.dialogBtns.accepted, self, 'accept')
        connectWeakly(self.dialogBtns.rejected, self, 'reject')

        layout = QFormLayout()
        layout.addRow(AppQLabel(_('Remark')), self.remarkEdit)
        layout.addRow(
            AppQLabel('Domain Strategy', translatable=False),
            self.domainStrategyCombo,
        )
        layout.addRow(AppQLabel(_('State')), self.enabledCombo)
        layout.addRow(self.dialogBtns)

        self.setLayout(layout)

    def routing(self):
        """Return the routing value used by the routing profile edit dialog."""
        return {
            'remark': self.remarkEdit.text().strip() or _('New Routing'),
            'domainStrategy': self.domainStrategyCombo.currentText(),
            'enabled': comboCurrentData(self.enabledCombo, 'Enabled') == 'Enabled',
            'rules': [],
        }


class RoutingRulesListView(AppQListView):
    """Provide the model-based routing rules list."""

    editRequested = QtCore.Signal()

    def __init__(self, routing: dict, parent=None):
        """Initialize the routing rules list view."""
        super().__init__(parent)

        self.routing = routing
        self.rulesModel = QtCore.QStringListModel(parent=self)
        self.setModel(self.rulesModel)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(AppQListView.SelectionBehavior.SelectRows)
        self.setSelectionMode(AppQListView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(AppQListView.EditTrigger.NoEditTriggers)

        connectWeakly(self.doubleClicked, self, '_requestEdit')

        self.flushAll()

    @QtCore.Slot(QtCore.QModelIndex)
    def _requestEdit(self, _index):
        """Forward a row double-click without retaining a Python closure."""
        self.editRequested.emit()

    def rules(self):
        """Return the rules represented by the routing list."""
        rules = self.routing.setdefault('rules', list())

        if not isinstance(rules, list):
            self.routing['rules'] = rules = list()

        return rules

    def ruleAt(self, index: int):
        """Return the rule represented by one list row."""
        return self.rules()[index]

    def ruleText(self, rule: dict) -> str:
        """Return the display text for one routing rule."""
        name, outbound, domains, ips = (
            rule.get('ruleTag', '') or 'Untitled Rule',
            rule.get('outboundTag', 'proxy'),
            len(rule.get('domain', [])),
            len(rule.get('ip', [])),
        )

        return f'{name} -> {outbound} ({domains} domains, {ips} IPs)'

    def selectedRuleText(self):
        """Select ed rule text."""
        indexes = self.selectedIndex

        if not indexes:
            return ''

        return self.ruleText(self.ruleAt(indexes[0]))

    def appendRule(self, rule: dict):
        """Append rule."""
        self.rules().append(rule)
        self.flushAll()

    def setRule(self, index: int, rule: dict):
        """Set rule."""
        self.rules()[index] = rule
        self.flushAll()

    def deleteRules(self, indexes: list[int]):
        """Delete rules."""
        for i in range(len(indexes)):
            self.rules().pop(indexes[i] - i)

        self.flushAll()

    def flushAll(self):
        """Refresh all."""
        self.rulesModel.setStringList([self.ruleText(rule) for rule in self.rules()])


class RoutingRulesDialog(AppQTransientDialog):
    """Present the routing rules dialog."""

    FIXED_DIALOG_SIZE = QtCore.QSize(760, 470)

    def __init__(self, routing: dict, parent=None):
        """Initialize the RoutingRulesDialog."""
        super().__init__(parent)

        self.routing = routing
        self.setWindowTitle(_('Routing Rules'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.listView = RoutingRulesListView(self.routing, parent=self)

        connectWeakly(self.listView.editRequested, self, 'editRule')

        self.addButton = AppQPushButton(
            _('Add'),
            icon=bootstrapIcon('plus-lg.svg'),
        )

        connectWeakly(self.addButton.clicked, self, 'addRule')

        self.deleteButton = AppQPushButton(
            _('Delete'),
            icon=bootstrapIcon('trash.svg'),
        )

        connectWeakly(self.deleteButton.clicked, self, 'deleteRule')

        self.closeWindowButton = AppQPushButton(
            _('Close Window'),
            icon=bootstrapIcon('window-x.svg'),
        )

        connectWeakly(self.closeWindowButton.clicked, self, 'close')

        for button in (
            self.addButton,
            self.deleteButton,
            self.closeWindowButton,
        ):
            button.setAutoDefault(False)
            button.setDefault(False)

        actionLayout = QHBoxLayout()
        actionLayout.setContentsMargins(0, 0, 0, 0)
        actionLayout.setSpacing(8)
        actionLayout.addWidget(self.addButton)
        actionLayout.addWidget(self.deleteButton)
        actionLayout.addStretch(1)
        actionLayout.addWidget(self.closeWindowButton)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(actionLayout)
        layout.addWidget(self.listView)

        self.setLayout(layout)

    def addRule(self):
        """Add rule."""
        rule = {'type': 'field'}
        # This editor is subordinate to the transient rules dialog.  Parenting
        # it prevents an asynchronous child from outliving its owner and later
        # invoking a callback on a deleted list widget.
        dialog = RoutingRuleEditDialog(rule, parent=self)

        def handleResultCode(code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.listView.appendRule(dialog.routingRule())

        dialog.finished.connect(handleResultCode)
        dialog.open()

    def editRule(self):
        """Handle edit rule for the routing rules dialog."""
        indexes = self.listView.selectedIndex

        if len(indexes) != 1:
            return

        index = indexes[0]
        dialog = RoutingRuleEditDialog(self.listView.ruleAt(index), parent=self)

        def handleResultCode(_index, code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.listView.setRule(_index, dialog.routingRule())

        dialog.finished.connect(functools.partial(handleResultCode, index))
        dialog.open()

    def deleteRule(self):
        """Delete rule."""
        indexes = self.listView.selectedIndex

        if len(indexes) == 0:
            return

        def handleResultCode(_indexes, code):
            """Handle result code."""
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                self.listView.deleteRules(_indexes)
            else:
                # Do not delete
                pass

        if PLATFORM == 'Windows':
            # Windows
            mbox = MBoxQuestionDelete(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = MBoxQuestionDelete(
                icon=AppQMessageBox.Icon.Question,
                parent=self,
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = self.listView.selectedRuleText()
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()


class UserRoutingQTableViewHorizontalHeader(AppQHeaderView):
    """Provide the user routing Qt table view horizontal table header."""

    def __init__(self, *args, **kwargs):
        """Initialize the UserRoutingQTableViewHorizontalHeader."""
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class UserRoutingTableView(Mixins.QTranslatable, AppQTableView):
    """Represent user routing table view."""

    RowHeight = 42

    def __init__(self, parent=None):
        """Initialize the UserRoutingTableView."""
        super().__init__(parent)

        self.sourceModel = RoutingProfilesModel(parent=self)
        self.setModel(self.sourceModel)
        self.setHorizontalHeader(
            UserRoutingQTableViewHorizontalHeader(
                parent=self,
                sectionSizeSettingsName='UserRoutingHeaderViewState',
            )
        )
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)
        self.doubleClicked.connect(self.editSelectedRules)

        self.setDefaultRowHeight(self.RowHeight)
        self.configureHeader()
        self.flushAll()

    def configureHeader(self):
        """Configure header."""
        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setCustomSectionResizeMode()
        header.restoreSectionSize()

    @property
    def selectedIndex(self):
        """Return the selected index value."""
        return sorted(
            list(set(index.row() for index in self.selectionModel().selectedRows()))
        )

    def routingUniqueByRow(self, row):
        """Return the routing unique by row value used by the user routing table view."""
        return self.sourceModel.routingUniqueByRow(row)

    def flushItem(self, row: int, column: int):
        """Refresh item."""
        index = self.sourceModel.index(row, column)

        if column == 1:
            combo = AppQComboBox(parent=self.viewport(), translatable=False)
            combo.addItems(DOMAIN_STRATEGIES)
            combo.setMinimumWidth(0)
            combo.setCurrentText(
                self.sourceModel.routingByRow(row).get('domainStrategy', 'AsIs')
            )
            combo.currentTextChanged.connect(
                lambda text, _row=row: self.setDomainStrategy(_row, text)
            )

            self.setIndexWidget(index, combo)
        elif column == 2:
            combo = AppQComboBox(parent=self.viewport(), translatable=False)
            addRoutingStateItems(combo)
            combo.setMinimumWidth(0)
            combo.setCurrentIndex(
                ROUTING_STATES.index(
                    'Enabled'
                    if self.sourceModel.routingByRow(row).get('enabled', True)
                    else 'Disabled'
                )
            )
            combo.currentIndexChanged.connect(
                lambda _index, _row=row, _combo=combo: self.setEnabled(
                    _row,
                    comboCurrentData(_combo, 'Enabled'),
                )
            )

            self.setIndexWidget(index, combo)

    def flushRow(self, row: int):
        """Refresh row."""
        for column in range(self.sourceModel.columnCount()):
            self.flushItem(row, column)

    def flushAll(self):
        """Refresh all."""
        self.sourceModel.emitAllChanged()

        for row in range(self.sourceModel.rowCount()):
            self.flushRow(row)

    def retranslate(self):
        """Refresh translated text for the user routing table view."""
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            self.sourceModel.columnCount() - 1,
        )
        self.flushAll()

    def setDomainStrategy(self, row: int, text: str):
        """Set domain strategy."""
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        self.sourceModel.routingByRow(row)['domainStrategy'] = text
        self.sourceModel.emitAllChanged()

    def setEnabled(self, row: int, state: str):
        """Set enabled."""
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        self.sourceModel.routingByRow(row)['enabled'] = state == 'Enabled'
        self.sourceModel.emitAllChanged()

    def appendNewItem(self):
        """Append new item."""
        dialog = RoutingProfileEditDialog(parent=self)

        def handleResultCode(code):
            """Handle result code."""
            if code != PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                return

            row = self.sourceModel.rowCount()
            unique = str(uuid.uuid4())

            self.sourceModel.beginInsertRows(QtCore.QModelIndex(), row, row)

            Storage.UserRoutings()[unique] = dialog.routing()

            self.sourceModel.endInsertRows()
            self.flushRow(row)

        dialog.finished.connect(handleResultCode)
        dialog.open()

    def deleteSelectedItem(self):
        """Delete selected item."""
        indexes = self.selectedIndex

        if not indexes:
            # Nothing selected. Do nothing
            return

        def handleResultCode(_indexes, code):
            """Handle result code."""
            if code != PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                return

            for i in range(len(_indexes)):
                deleteIndex = _indexes[i] - i
                deleteUnique = self.routingUniqueByRow(deleteIndex)

                self.sourceModel.beginRemoveRows(
                    QtCore.QModelIndex(),
                    deleteIndex,
                    deleteIndex,
                )

                Storage.UserRoutings().pop(deleteUnique)

                self.sourceModel.endRemoveRows()

            self.flushAll()

        if PLATFORM == 'Windows':
            # Windows
            mbox = MBoxQuestionDelete(icon=AppQMessageBox.Icon.Question)
        else:
            # macOS & linux
            mbox = MBoxQuestionDelete(
                icon=AppQMessageBox.Icon.Question,
                parent=self,
            )
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        mbox.isMulti = bool(len(indexes) > 1)
        mbox.possibleRemark = self.sourceModel.data(
            self.sourceModel.index(indexes[0], 0),
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, indexes))

        # Show the MessageBox asynchronously
        mbox.open()

    def renameSelectedItem(self):
        """Handle rename selected item for the user routing table view."""
        indexes = self.selectedIndex

        if not indexes:
            # Nothing selected. Do nothing
            return

        if len(indexes) > 1:
            # Multiple items selected. Do nothing
            return

        routing = self.sourceModel.routingByRow(indexes[0])

        dialog = RoutingRemarkEditDialog(routing.get('remark', ''), parent=self)

        def handleResultCode(code):
            """Handle result code."""
            if code != PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                return

            remark = dialog.remark()

            if remark:
                routing['remark'] = remark
                self.sourceModel.emitAllChanged()

        dialog.finished.connect(handleResultCode)
        dialog.open()

    def previewSelectedItem(self):
        """Handle preview selected item for the user routing table view."""
        indexes = self.selectedIndex

        if len(indexes) != 1:
            return

        routing = copy.deepcopy(self.sourceModel.routingByRow(indexes[0]))

        dialog = RoutingPreviewDialog(routing, parent=self)
        dialog.open()

    def editSelectedRules(self):
        """Handle edit selected rules for the user routing table view."""
        indexes = self.selectedIndex

        if not indexes:
            # Nothing selected. Do nothing
            return

        if len(indexes) > 1:
            # Multiple items selected. Do nothing
            return

        routing = self.sourceModel.routingByRow(indexes[0])

        dialog = RoutingRulesDialog(routing, parent=self)

        connectWeakly(
            dialog.finished,
            self,
            '_rulesDialogFinished',
            sender=dialog,
        )

        dialog.open()

    @QtCore.Slot(int)
    def _rulesDialogFinished(self, _code):
        """Refresh routing presentation after the rules dialog finishes."""
        self.flushAll()


class XrayRoutingWindow(AppQMainWindow):
    """Present the user routing window."""

    DEFAULT_WINDOW_SIZE = QtCore.QSize(980, 560)

    def __init__(self, *args, **kwargs):
        """Initialize the Xray routing editor window."""
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Routing'))

        self.tableView = UserRoutingTableView(parent=self)

        self.addButton, self.previewButton, self.renameButton, self.deleteButton = (
            AppQPushButton(
                _('Add'),
                icon=bootstrapIcon('plus-lg.svg'),
            ),
            AppQPushButton(
                _('Preview'),
                icon=bootstrapIcon('file-earmark-text.svg'),
            ),
            AppQPushButton(
                _('Rename'),
                icon=bootstrapIcon('pencil-square.svg'),
            ),
            AppQPushButton(
                _('Delete'),
                icon=bootstrapIcon('trash.svg'),
            ),
        )

        for button, methodName in (
            (self.addButton, 'appendNewItem'),
            (self.previewButton, 'previewSelectedItem'),
            (self.renameButton, 'renameSelectedItem'),
            (self.deleteButton, 'deleteSelectedItem'),
        ):
            connectWeakly(
                button.clicked,
                self.tableView,
                methodName,
                sender=button,
            )

        actionLayout = QHBoxLayout()
        actionLayout.setContentsMargins(0, 0, 0, 0)
        actionLayout.setSpacing(8)
        actionLayout.addWidget(self.addButton)
        actionLayout.addWidget(self.previewButton)
        actionLayout.addWidget(self.renameButton)
        actionLayout.addWidget(self.deleteButton)
        actionLayout.addStretch(1)

        centralWidget = QWidget()
        centralWidget.setObjectName('UserRoutingWindowContent')

        layout = QVBoxLayout(centralWidget)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(actionLayout)
        layout.addWidget(self.tableView)

        self.setCentralWidget(centralWidget)

    def prepareInitialGeometry(self):
        """Restore routing-window geometry and state before its first show."""
        savedGeometry = AppSettings.get('UserRoutingWindowGeometry')

        if savedGeometry is None:
            self.resize(self.DEFAULT_WINDOW_SIZE)
        else:
            try:
                restored = self.restoreInitialGeometry(savedGeometry)
            except Exception:
                # Any non-exit exceptions

                logger.exception('unexpected routing-window geometry restore failure')

                restored = False

            if not restored:
                logger.warning(
                    'saved routing-window geometry was invalid and was ignored'
                )

                self.resize(self.DEFAULT_WINDOW_SIZE)

        savedState = AppSettings.get('UserRoutingWindowState')

        if savedState is None:
            return

        try:
            restored = self.restoreState(savedState)
        except Exception:
            # Any non-exit exceptions

            logger.exception('unexpected routing-window state restore failure')

            return

        if not restored:
            logger.warning('saved routing-window state was invalid and was ignored')

    def cleanup(self):
        """Release resources owned by the user routing window."""
        # Settings eagerly owns this reusable editor even when Edit Routing was
        # never opened. Saving then would replace the user's geometry with Qt's
        # tiny pre-show placeholder, so leave the persisted state untouched.
        if not self.hasPreparedInitialGeometry():
            return

        AppSettings.set('UserRoutingWindowGeometry', self.saveGeometry())
        AppSettings.set('UserRoutingWindowState', self.saveState())
