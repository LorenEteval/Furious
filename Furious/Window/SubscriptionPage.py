# Copyright (C) 2024–present  Loren Eteval & contributors <loren.eteval@proton.me>
#
# This file is part of Furious.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Present subscription definitions and synchronization as a dedicated page."""

from __future__ import annotations

from Furious.Frozenlib import APP, Mixins, PySide6Legacy
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Repository import Storage
from Furious.Widget.SubscriptionTableView import SubscriptionTableView

from PySide6 import QtCore
from PySide6.QtWidgets import *

from urllib.parse import urlsplit
import uuid

__all__ = ['SubscriptionPage']


class _SubscriptionEditorDialog(AppQDialog):
    """Edit one complete subscription definition with validation."""

    def __init__(self, subscription=None, parent=None):
        """Initialize fields from an existing definition or defaults."""
        super().__init__(parent)

        subscription = dict(subscription or {})
        self.remarkEdit = QLineEdit(subscription.get('remark', ''))
        self.urlEdit = QLineEdit(subscription.get('webURL', ''))
        self.enabledCheckBox = QCheckBox()
        self.enabledCheckBox.setChecked(subscription.get('enabled', True))
        self.autoUpdateComboBox = QComboBox()
        self.proxyComboBox = QComboBox()
        self.userAgentEdit = QLineEdit(subscription.get('userAgent', ''))
        self.filterEdit = QLineEdit(subscription.get('filter', ''))

        self.remarkEdit.setMaximumWidth(520)
        self.urlEdit.setMaximumWidth(520)
        self.userAgentEdit.setMaximumWidth(520)
        self.filterEdit.setMaximumWidth(520)

        for value in SubscriptionTableView.AutoUpdateOptions:
            self.autoUpdateComboBox.addItem(_(value), value)

        for value in SubscriptionTableView.ProxyOptions:
            self.proxyComboBox.addItem(_(value), value)

        autoIndex = self.autoUpdateComboBox.findData(subscription.get('autoupdate', ''))
        proxyIndex = self.proxyComboBox.findData(subscription.get('proxy', ''))
        self.autoUpdateComboBox.setCurrentIndex(max(autoIndex, 0))
        self.proxyComboBox.setCurrentIndex(max(proxyIndex, 0))

        self.buttons = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.buttons.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(
            _('Cancel'),
            AppQDialogButtonBox.ButtonRole.RejectRole,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        form.addRow(_('Remark'), self.remarkEdit)
        form.addRow(_('URL'), self.urlEdit)
        form.addRow(_('Enabled'), self.enabledCheckBox)
        form.addRow(_('Auto Update'), self.autoUpdateComboBox)
        form.addRow(_('Auto Update Use Proxy'), self.proxyComboBox)
        form.addRow(_('User Agent'), self.userAgentEdit)
        form.addRow(_('Profile Filter (Regex)'), self.filterEdit)
        form.addRow(self.buttons)
        self.setLayout(form)

        self.setWindowTitle(
            _('Edit Subscription') if subscription else _('Add Subscription')
        )
        self.resize(700, 360)

    def _showValidationError(self, message: str):
        """Show one non-blocking validation message owned by this dialog."""
        messageBox = AppQMessageBox(
            icon=AppQMessageBox.Icon.Warning,
            parent=self,
        )
        messageBox.setWindowTitle(_('Invalid data'))
        messageBox.setText(message)
        messageBox.open()

    def accept(self):
        """Validate required fields before accepting the definition."""
        remark = self.remarkEdit.text().strip()
        url = self.urlEdit.text().strip()
        parsed = urlsplit(url)

        if not remark:
            self._showValidationError(_('Please enter a subscription remark.'))

            return

        if parsed.scheme.casefold() not in ('http', 'https') or not parsed.netloc:
            self._showValidationError(_('Please enter a valid subscription URL.'))

            return

        super().accept()

    def subscription(self):
        """Return the normalized values entered by the user."""
        return {
            'remark': self.remarkEdit.text().strip(),
            'webURL': self.urlEdit.text().strip(),
            'enabled': self.enabledCheckBox.isChecked(),
            'autoupdate': self.autoUpdateComboBox.currentData() or '',
            'proxy': self.proxyComboBox.currentData() or '',
            'userAgent': self.userAgentEdit.text().strip(),
            'filter': self.filterEdit.text().strip(),
        }


class SubscriptionPage(Mixins.QTranslatable, Mixins.ThemeAware, QMainWindow):
    """Own subscription editing, grouping, and synchronization workflows."""

    def __init__(self, serverTable, parent=None):
        """Initialize around the existing profile synchronization backend."""
        super().__init__(parent)

        self.setObjectName('SubscriptionPage')
        self.serverTable = serverTable
        self.pageTitleLabel = AppQLabel(translatable=False)
        self.pageTitleLabel.setObjectName('SubscriptionPageTitle')
        self.proxyLabel = AppQLabel(translatable=False)
        self.proxyComboBox = QComboBox()
        self.proxyComboBox.setMinimumWidth(160)

        self.addButton = QPushButton()
        self.addFromClipboardButton = QPushButton()
        self.editButton = QPushButton()
        self.deleteButton = QPushButton()
        self.copyURLButton = QPushButton()
        self.updateSelectedButton = QPushButton()
        self.updateAllButton = QPushButton()

        self.table = SubscriptionTableView(
            deleteUniqueCallback=self._deleteProfilesForSubscription,
            parent=self,
        )
        self.table.doubleClicked.connect(lambda _index: self.editSelected())
        self.serverTable.subsManager.subscriptionsChanged.connect(self.table.flushAll)

        self.addButton.clicked.connect(self.addSubscription)
        self.addFromClipboardButton.clicked.connect(self.addFromClipboard)
        self.editButton.clicked.connect(self.editSelected)
        self.deleteButton.clicked.connect(self.table.deleteSelectedItem)
        self.copyURLButton.clicked.connect(self.copySelectedURL)
        self.updateSelectedButton.clicked.connect(self.updateSelected)
        self.updateAllButton.clicked.connect(self.updateAll)

        for key in SubscriptionTableView.ProxyOptions:
            self.proxyComboBox.addItem(_(key), key)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(self.pageTitleLabel)
        controls.addStretch(1)
        controls.addWidget(self.proxyLabel)
        controls.addWidget(self.proxyComboBox)
        controls.addWidget(self.updateSelectedButton)
        controls.addWidget(self.updateAllButton)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(self.addButton)
        actions.addWidget(self.addFromClipboardButton)
        actions.addWidget(self.editButton)
        actions.addWidget(self.deleteButton)
        actions.addWidget(self.copyURLButton)
        actions.addStretch(1)

        content = QWidget()
        content.setObjectName('SubscriptionPageContent')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)
        layout.addLayout(controls)
        layout.addLayout(actions)
        layout.addWidget(self.table, 1)
        self.setCentralWidget(content)

        self.setIconsByTheme(APP().theme())
        self.retranslate()

    def _deleteProfilesForSubscription(self, unique: str):
        """Remove profiles belonging to a deleted subscription group."""
        indexes = [
            index
            for index, server in enumerate(Storage.UserServers())
            if server.itemSubscription == unique
        ]
        self.serverTable.deleteItemByIndex(indexes, showProgress=False)

    def _selectedUnique(self):
        """Return the first selected subscription ID, if any."""
        selected = self.table.selectedUniques

        return selected[0] if selected else None

    def _openEditor(self, unique=None, initial=None):
        """Open and retain an asynchronous add/edit dialog."""
        source = Storage.UserSubs().get(unique, initial or {})
        dialog = _SubscriptionEditorDialog(source, parent=self)
        dialog.setWindowTitle(
            _('Edit Subscription') if unique else _('Add Subscription')
        )
        dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        def finished(code):
            """Persist accepted values through the existing table model."""
            if code != PySide6Legacy.enumValueWrapper(AppQDialog.DialogCode.Accepted):
                return

            subscriptionUnique = unique or str(uuid.uuid4())
            existing = Storage.UserSubs().get(subscriptionUnique, {})
            self.table.appendNewItem(
                unique=subscriptionUnique,
                lastUpdated=existing.get('lastUpdated', ''),
                **dialog.subscription(),
            )
            self.table.selectRow(list(Storage.UserSubs()).index(subscriptionUnique))

        dialog.finished.connect(finished)
        dialog.open()

    @QtCore.Slot()
    def addSubscription(self):
        """Open the full subscription editor for a new group."""
        self._openEditor()

    @QtCore.Slot()
    def addFromClipboard(self):
        """Seed a subscription from an HTTP(S) URL on the clipboard."""
        url = QApplication.clipboard().text().strip()
        parsed = urlsplit(url)

        if parsed.scheme.casefold() not in ('http', 'https') or not parsed.netloc:
            self._openEditor()

            return

        self._openEditor(
            initial={
                'remark': parsed.hostname or _('Subscription'),
                'webURL': url,
                'enabled': True,
            }
        )

    @QtCore.Slot()
    def editSelected(self):
        """Edit the selected subscription without relying on inline cells."""
        unique = self._selectedUnique()

        if unique is not None:
            self._openEditor(unique)

    @QtCore.Slot()
    def copySelectedURL(self):
        """Copy the selected subscription URL for sharing/export."""
        unique = self._selectedUnique()

        if unique is not None:
            QApplication.clipboard().setText(
                str(Storage.UserSubs()[unique].get('webURL', ''))
            )

    def _selectedProxy(self):
        """Resolve the proxy policy selected for manual synchronization."""
        key = self.proxyComboBox.currentData() or ''
        resolver = SubscriptionTableView.ProxyOptions.get(key)

        return resolver() if callable(resolver) else None

    @QtCore.Slot()
    def updateSelected(self):
        """Synchronize selected enabled subscription groups together."""
        keys = tuple(
            key
            for key in self.table.selectedUniques
            if Storage.UserSubs().get(key, {}).get('enabled', True)
            and Storage.UserSubs().get(key, {}).get('webURL')
        )

        if not keys:
            return

        depthMap = {'depth': len(keys)}
        successArgs = []
        failureArgs = []
        httpProxy = self._selectedProxy()

        for key in keys:
            self.serverTable.updateSubsByUnique(
                key,
                httpProxy,
                depthMap=depthMap,
                successArgs=successArgs,
                failureArgs=failureArgs,
                showMessageBox=True,
                parent=self,
            )

    @QtCore.Slot()
    def updateAll(self):
        """Synchronize every enabled subscription with one proxy policy."""
        self.serverTable.updateSubs(self._selectedProxy(), parent=self)

    def updateSubsByUnique(self, unique: str, httpProxy, **kwargs):
        """Preserve the established application subscription-update API."""
        self.serverTable.updateSubsByUnique(unique, httpProxy, **kwargs)

    def setIconsByTheme(self, theme: str):
        """Apply theme-aware Fluent icons to subscription commands."""
        iconFactory = (
            bootstrapIconWhite if theme == AppStyleSheet.Dark else bootstrapIcon
        )

        for button, iconName in (
            (self.addButton, 'plus-lg.svg'),
            (self.addFromClipboardButton, 'clipboard-plus.svg'),
            (self.editButton, 'pencil-square.svg'),
            (self.deleteButton, 'trash.svg'),
            (self.copyURLButton, 'link-45deg.svg'),
            (self.updateSelectedButton, 'arrow-repeat.svg'),
            (self.updateAllButton, 'cloud-arrow-down.svg'),
        ):
            button.setIcon(iconFactory(iconName))

    def themeChangedCallback(self, theme: str):
        """Refresh command icons after a theme change."""
        self.setIconsByTheme(theme)

    def showEvent(self, event):
        """Refresh persisted subscription data whenever the page is shown."""
        super().showEvent(event)
        self.table.flushAll()

    def retranslate(self):
        """Refresh page labels, commands, and proxy choices."""
        selectedProxy = self.proxyComboBox.currentData()

        with Mixins.QBlockSignalContext(self.proxyComboBox):
            self.proxyComboBox.clear()

            for key in SubscriptionTableView.ProxyOptions:
                self.proxyComboBox.addItem(_(key), key)

            index = self.proxyComboBox.findData(selectedProxy)
            self.proxyComboBox.setCurrentIndex(max(index, 0))

        self.pageTitleLabel.setText(_('Subscriptions'))
        self.proxyLabel.setText(_('Update Using'))
        self.addButton.setText(_('Add'))
        self.addFromClipboardButton.setText(_('Add From Clipboard'))
        self.editButton.setText(_('Edit'))
        self.deleteButton.setText(_('Delete'))
        self.copyURLButton.setText(_('Copy URL'))
        self.updateSelectedButton.setText(_('Update Selected'))
        self.updateAllButton.setText(_('Update All'))
