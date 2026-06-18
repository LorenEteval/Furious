# Copyright (C) 2024-present  Loren Eteval & contributors <loren.eteval@proton.me>
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

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Library import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import *

import uuid
import logging
import functools

__all__ = ['UserRoutingWindow']

logger = logging.getLogger(__name__)

registerAppSettings('UserRoutingWindowGeometry')
registerAppSettings('UserRoutingWindowState')
registerAppSettings('UserRoutingHeaderViewState')


DOMAIN_STRATEGIES, ROUTING_STATES = (
    ['AsIs', 'IPIfNonMatch', 'IPOnDemand'],
    ['Enabled', 'Disabled'],
)


def valuesToList(text: str) -> list[str]:
    values = list()

    for line in text.splitlines():
        for value in line.split(','):
            value = value.strip()

            if value:
                values.append(value)

    return values


def listToText(value) -> str:
    if isinstance(value, list):
        return '\n'.join(str(item) for item in value)

    return ''


def routingStateText(state: str) -> str:
    if state == 'Enabled':
        return _('Enabled')
    elif state == 'Disabled':
        return _('Disabled')

    return _(state)


def addRoutingStateItems(combo: QComboBox):
    combo.clear()

    for state in ROUTING_STATES:
        combo.addItem(routingStateText(state), state)


def comboCurrentData(combo: QComboBox, default=''):
    data = combo.currentData()

    if data is None:
        return default

    return data


class RoutingTextEditDialog(AppQDialog):
    def __init__(self, text='', parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Edit Text'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.textEdit = QTextEdit(text)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.textEdit)
        layout.addWidget(self.dialogBtns)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.setFixedSize(760, 470)

    def text(self):
        return self.textEdit.toPlainText()


class RoutingTextEdit(Mixins.QTranslatable, QTextEdit):
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)

        self.setToolTip(_('Double-click to enlarge'))

    def mouseDoubleClickEvent(self, event):
        dialog = RoutingTextEditDialog(self.toPlainText(), parent=self)

        def handleResultCode(code):
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.setPlainText(dialog.text())

        dialog.finished.connect(handleResultCode)
        dialog.open()

        event.accept()

    def retranslate(self):
        self.setToolTip(_(self.toolTip()))


class RoutingDocumentationURL(AppQLabel):
    URL = 'https://xtls.github.io/config/routing.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWebsiteURL()
        self.linkActivated.connect(self.handleLinkActivated)

    def setWebsiteURL(self):
        self.setText(
            '<html><head/><body><p>'
            f'<a href="{self.URL}">'
            '<span style=" text-decoration: underline; color:#007ad6;">'
            + _('Routing Documentation')
            + '</span></a></p></body></html>'
        )

    @staticmethod
    def handleLinkActivated(link: str):
        if QDesktopServices.openUrl(QtCore.QUrl(link)):
            logger.info(f'open link \'{link}\' success')
        else:
            logger.error(f'open link \'{link}\' failed')

    def retranslate(self):
        self.setWebsiteURL()


class RoutingProfilesModel(QtCore.QAbstractTableModel):
    Headers = ['Remark', 'Domain Strategy', 'State']

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(Storage.UserRoutings())

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(self.Headers)

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.ItemFlag.NoItemFlags

        return QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == QtCore.Qt.Orientation.Horizontal:
            header = self.Headers[section]

            if header in ['Remark', 'State']:
                return _(header)

            return header

        return section + 1

    def routingUniqueByRow(self, row: int):
        return list(Storage.UserRoutings().keys())[row]

    def routingByRow(self, row: int):
        return Storage.UserRoutings()[self.routingUniqueByRow(row)]

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
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
        return False

    def emitAllChanged(self):
        if self.rowCount() == 0:
            return

        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
        )


class RoutingRuleEditDialog(AppQDialog):
    MatchInputHeight = 72
    ShortInputWidth = 240

    @staticmethod
    def textEdit(text=''):
        widget = RoutingTextEdit(text)
        widget.setFixedHeight(RoutingRuleEditDialog.MatchInputHeight)

        return widget

    @staticmethod
    def lineEdit(text=''):
        widget = QLineEdit(text)
        widget.setFixedHeight(RoutingRuleEditDialog.MatchInputHeight)

        return widget

    def __init__(self, rule: dict, parent=None):
        super().__init__(parent)

        self.rule = dict(rule)
        self.setWindowTitle(_('Edit Routing Rule'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.ruleTagEdit = self.lineEdit(self.rule.get('ruleTag', ''))

        self.outboundCombo = AppQComboBox(translatable=False)
        self.outboundCombo.addItems(['proxy', 'direct', 'block'])
        self.outboundCombo.setCurrentText(self.rule.get('outboundTag', 'proxy'))
        self.outboundCombo.setMaximumWidth(self.ShortInputWidth)

        self.balancerTagEdit = self.lineEdit(str(self.rule.get('balancerTag', '')))

        self.networkCombo = AppQComboBox(translatable=False)
        self.networkCombo.addItems(['', 'tcp', 'udp', 'tcp,udp'])
        self.networkCombo.setCurrentText(self.rule.get('network', ''))
        self.networkCombo.setMaximumWidth(self.ShortInputWidth)

        self.portEdit = self.textEdit(str(self.rule.get('port', '')))
        self.portEdit.setMaximumWidth(360)

        self.sourcePortEdit = self.textEdit(str(self.rule.get('sourcePort', '')))
        self.sourcePortEdit.setMaximumWidth(360)

        self.localPortEdit = self.textEdit(str(self.rule.get('localPort', '')))
        self.localPortEdit.setMaximumWidth(360)

        self.vlessRouteEdit = self.textEdit(str(self.rule.get('vlessRoute', '')))
        self.vlessRouteEdit.setMaximumWidth(360)

        self.domainEdit = self.textEdit(listToText(self.rule.get('domain', [])))
        self.ipEdit = self.textEdit(listToText(self.rule.get('ip', [])))
        self.sourceIPEdit = self.textEdit(listToText(self.rule.get('sourceIP', [])))
        self.localIPEdit = self.textEdit(listToText(self.rule.get('localIP', [])))
        self.userEdit = self.textEdit(listToText(self.rule.get('user', [])))
        self.protocolEdit = self.textEdit(listToText(self.rule.get('protocol', [])))
        self.inboundTagEdit = self.textEdit(listToText(self.rule.get('inboundTag', [])))
        self.processEdit = self.textEdit(listToText(self.rule.get('process', [])))

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        generalLayout = QFormLayout()
        generalLayout.addRow(
            AppQLabel('Rule Tag', translatable=False),
            self.ruleTagEdit,
        )
        generalLayout.addRow(
            AppQLabel('Outbound', translatable=False),
            self.outboundCombo,
        )
        generalLayout.addRow(
            AppQLabel('Balancer Tag', translatable=False),
            self.balancerTagEdit,
        )
        generalLayout.addRow(
            AppQLabel('Network', translatable=False),
            self.networkCombo,
        )

        generalGroup = AppQGroupBox(
            'General',
            translatable=False,
        )
        generalGroup.setLayout(generalLayout)

        destinationLayout = QFormLayout()
        destinationLayout.addRow(
            AppQLabel(_('Domain (one per line or comma-separated)')),
            self.domainEdit,
        )
        destinationLayout.addRow(
            AppQLabel(_('IP (one per line or comma-separated)')),
            self.ipEdit,
        )
        destinationLayout.addRow(
            AppQLabel(_('Port (comma/range, e.g. 53,443,1000-2000)')),
            self.portEdit,
        )
        destinationLayout.addRow(
            AppQLabel(_('VLESS Route (comma/range, e.g. 53,443,1000-2000)')),
            self.vlessRouteEdit,
        )

        destinationGroup = AppQGroupBox(
            'Destination Match',
            translatable=False,
        )
        destinationGroup.setLayout(destinationLayout)

        sourceLayout = QFormLayout()
        sourceLayout.addRow(
            AppQLabel(_('Source IP (one per line or comma-separated)')),
            self.sourceIPEdit,
        )
        sourceLayout.addRow(
            AppQLabel(_('Source Port (comma/range, e.g. 53,443,1000-2000)')),
            self.sourcePortEdit,
        )
        sourceLayout.addRow(
            AppQLabel(_('Local IP (one per line or comma-separated)')),
            self.localIPEdit,
        )
        sourceLayout.addRow(
            AppQLabel(_('Local Port (comma/range, e.g. 53,443,1000-2000)')),
            self.localPortEdit,
        )

        sourceGroup = AppQGroupBox(
            'Source / Local Match',
            translatable=False,
        )
        sourceGroup.setLayout(sourceLayout)

        identityLayout = QFormLayout()
        identityLayout.addRow(
            AppQLabel(_('User (one per line or comma-separated)')),
            self.userEdit,
        )
        identityLayout.addRow(
            AppQLabel(_('Inbound Tag (one per line or comma-separated)')),
            self.inboundTagEdit,
        )
        identityLayout.addRow(
            AppQLabel(_('Process (one per line or comma-separated)')),
            self.processEdit,
        )
        identityLayout.addRow(
            AppQLabel(_('Protocol (one per line or comma-separated)')),
            self.protocolEdit,
        )

        identityGroup = AppQGroupBox(
            'Identity / Process / Protocol Match',
            translatable=False,
        )
        identityGroup.setLayout(identityLayout)

        matchGrid = QGridLayout()
        matchGrid.addWidget(generalGroup, 0, 0)
        matchGrid.addWidget(destinationGroup, 0, 1)
        matchGrid.addWidget(sourceGroup, 1, 0)
        matchGrid.addWidget(identityGroup, 1, 1)
        matchGrid.setColumnStretch(0, 1)
        matchGrid.setColumnStretch(1, 1)

        bottomLayout = QHBoxLayout()
        bottomLayout.addWidget(RoutingDocumentationURL())
        bottomLayout.addStretch(1)
        bottomLayout.addWidget(self.dialogBtns)

        layout = QVBoxLayout()
        layout.addLayout(matchGrid)
        layout.addLayout(bottomLayout)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.setFixedSize(int(760 * GOLDEN_RATIO), 760)

    def routingRule(self):
        rule = {'type': 'field', 'outboundTag': self.outboundCombo.currentText()}

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


class RoutingRemarkEditDialog(AppQDialog):
    def __init__(self, remark: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Edit Routing Remark'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.remarkEdit = QLineEdit(remark)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()
        layout.addRow(AppQLabel(_('Remark')), self.remarkEdit)
        layout.addRow(self.dialogBtns)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.resize(420, 120)

    def remark(self):
        return self.remarkEdit.text().strip()


class RoutingProfileEditDialog(AppQDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Add Routing'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.remarkEdit = QLineEdit(_('New Routing'))

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
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()
        layout.addRow(AppQLabel(_('Remark')), self.remarkEdit)
        layout.addRow(
            AppQLabel('Domain Strategy', translatable=False),
            self.domainStrategyCombo,
        )
        layout.addRow(AppQLabel(_('State')), self.enabledCombo)
        layout.addRow(self.dialogBtns)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.resize(460, 160)

    def routing(self):
        return {
            'remark': self.remarkEdit.text().strip() or _('New Routing'),
            'domainStrategy': self.domainStrategyCombo.currentText(),
            'enabled': comboCurrentData(self.enabledCombo, 'Enabled') == 'Enabled',
            'rules': [],
        }


class RoutingRulesDialog(AppQDialog):
    def __init__(self, routing: dict, parent=None):
        super().__init__(parent)

        self.routing = routing
        self.setWindowTitle(_('Routing Rules'))
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self.listWidget = QListWidget()
        self.listWidget.itemDoubleClicked.connect(lambda _item: self.editRule())

        self.addButton = AppQPushButton(_('Add'))
        self.addButton.clicked.connect(self.addRule)

        self.deleteButton = AppQPushButton(_('Delete'))
        self.deleteButton.clicked.connect(self.deleteRule)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.addButton)
        buttonLayout.addWidget(self.deleteButton)

        layout = QVBoxLayout()
        layout.addWidget(self.listWidget)
        layout.addLayout(buttonLayout)

        self.setLayout(layout)

        self.flushAll()

    def setWidthAndHeight(self):
        self.setFixedSize(760, 470)

    def rules(self):
        rules = self.routing.setdefault('rules', list())

        if not isinstance(rules, list):
            self.routing['rules'] = rules = list()

        return rules

    def ruleText(self, rule: dict) -> str:
        name, outbound, domains, ips = (
            rule.get('ruleTag', '') or 'Untitled Rule',
            rule.get('outboundTag', 'proxy'),
            len(rule.get('domain', [])),
            len(rule.get('ip', [])),
        )

        return f'{name} -> {outbound} ({domains} domains, {ips} IPs)'

    def flushAll(self):
        self.listWidget.clear()

        for rule in self.rules():
            self.listWidget.addItem(self.ruleText(rule))

    def currentRow(self) -> int:
        return self.listWidget.currentRow()

    def addRule(self):
        rule = {'type': 'field', 'outboundTag': 'proxy', 'ruleTag': 'New Rule'}
        dialog = RoutingRuleEditDialog(rule, parent=self)

        def handleResultCode(code):
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.rules().append(dialog.routingRule())
                self.flushAll()

        dialog.finished.connect(handleResultCode)
        dialog.open()

    def editRule(self):
        row = self.currentRow()

        if row < 0 or row >= len(self.rules()):
            return

        dialog = RoutingRuleEditDialog(self.rules()[row], parent=self)

        def handleResultCode(_row, code):
            if code == PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                self.rules()[_row] = dialog.routingRule()
                self.flushAll()

        dialog.finished.connect(functools.partial(handleResultCode, row))
        dialog.open()

    def deleteRule(self):
        row = self.currentRow()

        if row < 0 or row >= len(self.rules()):
            return

        def handleResultCode(_row, code):
            if code == PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                self.rules().pop(_row)
                self.flushAll()
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

        mbox.possibleRemark = self.ruleText(self.rules()[row])
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, row))

        # Show the MessageBox asynchronously
        mbox.open()


class UserRoutingQTableViewHorizontalHeader(AppQHeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)


class UserRoutingTableView(Mixins.QTranslatable, AppQTableView):
    RowHeight = 42

    def __init__(self, parent=None):
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
        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(True)
        header.setCustomSectionResizeMode()
        header.restoreSectionSize()

    @property
    def selectedIndex(self):
        return sorted(
            list(set(index.row() for index in self.selectionModel().selectedRows()))
        )

    def routingUniqueByRow(self, row):
        return self.sourceModel.routingUniqueByRow(row)

    def flushItem(self, row: int, column: int):
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
        for column in range(self.sourceModel.columnCount()):
            self.flushItem(row, column)

    def flushAll(self):
        self.sourceModel.emitAllChanged()

        for row in range(self.sourceModel.rowCount()):
            self.flushRow(row)

    def retranslate(self):
        self.sourceModel.headerDataChanged.emit(
            QtCore.Qt.Orientation.Horizontal,
            0,
            self.sourceModel.columnCount() - 1,
        )
        self.flushAll()

    def setDomainStrategy(self, row: int, text: str):
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        self.sourceModel.routingByRow(row)['domainStrategy'] = text
        self.sourceModel.emitAllChanged()

    def setEnabled(self, row: int, state: str):
        if row < 0 or row >= self.sourceModel.rowCount():
            return

        self.sourceModel.routingByRow(row)['enabled'] = state == 'Enabled'
        self.sourceModel.emitAllChanged()

    def appendNewItem(self):
        dialog = RoutingProfileEditDialog(parent=self)

        def handleResultCode(code):
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
        rows = self.selectedIndex

        if not rows:
            # Nothing selected. Do nothing
            return

        def handleResultCode(_rows, code):
            if code != PySide6Legacy.enumValueWrapper(
                AppQMessageBox.StandardButton.Yes
            ):
                return

            for index, row in enumerate(_rows):
                deleteRow = row - index
                unique = self.routingUniqueByRow(deleteRow)

                self.sourceModel.beginRemoveRows(
                    QtCore.QModelIndex(),
                    deleteRow,
                    deleteRow,
                )

                Storage.UserRoutings().pop(unique)

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

        mbox.isMulti = bool(len(rows) > 1)
        mbox.possibleRemark = self.sourceModel.data(
            self.sourceModel.index(rows[0], 0),
            QtCore.Qt.ItemDataRole.DisplayRole,
        )
        mbox.setText(mbox.customText())
        mbox.finished.connect(functools.partial(handleResultCode, rows))

        # Show the MessageBox asynchronously
        mbox.open()

    def renameSelectedItem(self):
        rows = self.selectedIndex

        if not rows:
            # Nothing selected. Do nothing
            return

        if len(rows) > 1:
            # Multiple items selected. Do nothing
            return

        routing = self.sourceModel.routingByRow(rows[0])

        dialog = RoutingRemarkEditDialog(routing.get('remark', ''), parent=self)

        def handleResultCode(code):
            if code != PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                return

            remark = dialog.remark()

            if remark:
                routing['remark'] = remark
                self.sourceModel.emitAllChanged()

        dialog.finished.connect(handleResultCode)
        dialog.open()

    def editSelectedRules(self):
        rows = self.selectedIndex

        if not rows:
            # Nothing selected. Do nothing
            return

        if len(rows) > 1:
            # Multiple items selected. Do nothing
            return

        routing = self.sourceModel.routingByRow(rows[0])

        dialog = RoutingRulesDialog(routing, parent=self)
        dialog.finished.connect(lambda _code: self.flushAll())
        dialog.open()


class UserRoutingWindow(AppQMainWindow):
    DEFAULT_WINDOW_SIZE = QtCore.QSize(980, 560)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Routing'))

        self.tableView = UserRoutingTableView(parent=self)
        self.addButton = AppQPushButton(_('Add'))
        self.addButton.clicked.connect(self.tableView.appendNewItem)
        self.renameButton = AppQPushButton(_('Rename'))
        self.renameButton.clicked.connect(self.tableView.renameSelectedItem)
        self.deleteButton = AppQPushButton(_('Delete'))
        self.deleteButton.clicked.connect(self.tableView.deleteSelectedItem)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.addButton)
        buttonLayout.addWidget(self.renameButton)
        buttonLayout.addWidget(self.deleteButton)

        centralWidget = QWidget()

        layout = QVBoxLayout(centralWidget)
        layout.addWidget(self.tableView)
        layout.addLayout(buttonLayout)

        self.setCentralWidget(centralWidget)

    def setWidthAndHeight(self):
        if AppSettings.get('UserRoutingWindowGeometry') is None:
            self.resize(UserRoutingWindow.DEFAULT_WINDOW_SIZE)
        else:
            try:
                self.restoreGeometry(AppSettings.get('UserRoutingWindowGeometry'))
            except Exception:
                # Any non-exit exceptions

                self.resize(UserRoutingWindow.DEFAULT_WINDOW_SIZE)

            try:
                self.restoreState(AppSettings.get('UserRoutingWindowState'))
            except Exception:
                # Any non-exit exceptions

                pass

    def cleanup(self):
        AppSettings.set('UserRoutingWindowGeometry', self.saveGeometry())
        AppSettings.set('UserRoutingWindowState', self.saveState())
