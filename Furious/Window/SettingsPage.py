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

"""Present application configuration as a Fluent page of reusable cards."""

from __future__ import annotations

from Furious.Actions.Language import LANGUAGE_TO_ABBR
from Furious.Actions.Settings import (
    SettingsController,
    TUNModeAction,
)
from Furious.Backends.Hysteria2.Stats import (
    HYSTERIA2_STATS_CLIENT_ID_SETTING,
    HYSTERIA2_STATS_SECRET_SETTING,
    HYSTERIA2_STATS_URL_SETTING,
)
from Furious.Frozenlib import *
from Furious.Qt import *
from Furious.Qt import gettext as _

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import *

from collections.abc import Callable

__all__ = ['SettingsPage']


class _SettingsSwitch(QCheckBox):
    """Paint a lightweight Fluent-style binary switch with Qt."""

    ControlSize = QtCore.QSize(38, 22)

    def __init__(self, parent=None):
        """Initialize the compact switch control."""
        super().__init__(parent)

        self.setObjectName('SettingsToggle')
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self.ControlSize)
        self.toggled.connect(lambda _checked: self.update())

    def paintEvent(self, event):
        """Draw the track and animated-position-equivalent thumb."""
        del event

        palette = AppStyleSheet.Palettes[APP().theme()]
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        track = QtCore.QRectF(1, 2, self.width() - 2, self.height() - 4)
        radius = track.height() / 2

        if not self.isEnabled():
            background, border, thumb = (
                palette['raised'],
                palette['border'],
                palette['disabled'],
            )
        elif self.isChecked():
            background, border, thumb = (
                palette['accent'],
                palette['accent'],
                palette['accent_text'],
            )
        else:
            background, border, thumb = (
                palette['raised'],
                palette['border_strong'],
                palette['muted'],
            )

        painter.setPen(QtGui.QPen(QtGui.QColor(border), 1))
        painter.setBrush(QtGui.QColor(background))
        painter.drawRoundedRect(track, radius, radius)

        thumbDiameter = track.height() - 6
        thumbX = (
            track.right() - thumbDiameter - 3 if self.isChecked() else track.left() + 3
        )
        thumbRect = QtCore.QRectF(
            thumbX,
            track.top() + 3,
            thumbDiameter,
            thumbDiameter,
        )

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(thumb))
        painter.drawEllipse(thumbRect)

        if self.hasFocus():
            focusRect = track.adjusted(-0.5, -0.5, 0.5, 0.5)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor(palette['accent']), 1))
            painter.drawRoundedRect(focusRect, radius, radius)


class _SettingsCard(Mixins.ThemeAware, QFrame):
    """Lay out a themed icon, title, description, and trailing control."""

    IconSize = QtCore.QSize(20, 20)

    def __init__(self, iconFileName: str, control: QWidget, parent=None):
        """Initialize one reusable settings row."""
        super().__init__(parent)

        self.setObjectName('SettingsCard')
        self.iconFileName = iconFileName
        self.iconLabel = QLabel(parent=self)
        self.iconLabel.setObjectName('SettingsCardIcon')
        self.iconLabel.setFixedSize(self.IconSize)
        self.titleLabel = QLabel(parent=self)
        self.titleLabel.setObjectName('SettingsCardTitle')
        self.descriptionLabel = QLabel(parent=self)
        self.descriptionLabel.setObjectName('SettingsCardDescription')
        self.descriptionLabel.setWordWrap(True)
        self.control = control
        self.control.setParent(self)

        textLayout = QVBoxLayout()
        textLayout.setContentsMargins(0, 0, 0, 0)
        textLayout.setSpacing(2)
        textLayout.addWidget(self.titleLabel)
        textLayout.addWidget(self.descriptionLabel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        layout.addWidget(self.iconLabel, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(textLayout, 1)
        layout.addSpacing(16)
        layout.addWidget(self.control, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.setIconByTheme(APP().theme())

    def setTexts(self, title: str, description: str):
        """Set already translated card text."""
        self.titleLabel.setText(title)
        self.descriptionLabel.setText(description)

    def setIconByTheme(self, theme: str):
        """Refresh the card icon for the active theme."""
        iconFactory = (
            bootstrapIconWhite if theme == AppStyleSheet.Dark else bootstrapIcon
        )
        self.iconLabel.setPixmap(iconFactory(self.iconFileName).pixmap(self.IconSize))

    def themeChangedCallback(self, theme: str):
        """Refresh themed card artwork."""
        self.setIconByTheme(theme)
        self.control.update()


class _ToggleSettingsCard(_SettingsCard):
    """Bind one binary application preference to a trailing checkbox."""

    def __init__(self, iconFileName, settingName, callback, parent=None):
        """Initialize a persistent binary setting card."""
        self.settingName = settingName
        self.checkBox = _SettingsSwitch()
        self.checkBox.setChecked(AppSettings.isStateON_(settingName))
        self.checkBox.toggled.connect(callback)

        super().__init__(iconFileName, self.checkBox, parent)

    def sync(self):
        """Refresh the control from persistent state without applying it."""
        blocker = QtCore.QSignalBlocker(self.checkBox)

        self.checkBox.setChecked(AppSettings.isStateON_(self.settingName))

        del blocker


class _ActionSettingsCard(_SettingsCard):
    """Expose an existing command through one settings row."""

    def __init__(self, iconFileName, callback: Callable, parent=None):
        """Initialize a card with a compact trailing action button."""
        self.button = QPushButton()
        self.button.setObjectName('SettingsActionButton')
        self.button.clicked.connect(callback)

        super().__init__(iconFileName, self.button, parent)


class _LineEditSettingsCard(_SettingsCard):
    """Persist one text setting when editing finishes."""

    def __init__(
        self,
        iconFileName,
        settingName,
        *,
        placeholder='',
        secret=False,
        strip=True,
        parent=None,
    ):
        """Initialize one bounded settings text editor."""
        self.settingName = settingName
        self.strip = strip
        self.lineEdit = QLineEdit()
        self.lineEdit.setObjectName('SettingsLineEdit')
        self.lineEdit.setMaximumWidth(420)
        self.lineEdit.setMinimumWidth(260)
        self.lineEdit.setPlaceholderText(placeholder)
        self.lineEdit.setText(str(AppSettings.get(settingName) or ''))

        if secret:
            self.lineEdit.setEchoMode(QLineEdit.EchoMode.Password)

        self.lineEdit.editingFinished.connect(self.persist)

        super().__init__(iconFileName, self.lineEdit, parent)

    def persist(self):
        """Store the current text without coupling it to graph code."""
        value = self.lineEdit.text()

        if self.strip:
            value = value.strip()

        AppSettings.set(self.settingName, value)


class _LanguageSettingsCard(_SettingsCard):
    """Select and apply one supported application language."""

    def __init__(self, parent=None):
        """Initialize the stable language-name selector."""
        self.comboBox = QComboBox()
        self.comboBox.setObjectName('SettingsComboBox')
        self.comboBox.setMinimumWidth(180)

        for languageName, language in LANGUAGE_TO_ABBR.items():
            self.comboBox.addItem(languageName, language)

        self.sync()
        self.comboBox.currentIndexChanged.connect(self._selectionChanged)

        super().__init__('globe2.svg', self.comboBox, parent)

    def sync(self):
        """Select the persisted language without retriggering translation."""
        if not hasattr(self, 'comboBox'):
            return

        blocker = QtCore.QSignalBlocker(self.comboBox)
        index = self.comboBox.findData(AppSettings.get('Language'))

        self.comboBox.setCurrentIndex(max(index, 0))

        del blocker

    @QtCore.Slot(int)
    def _selectionChanged(self, _index: int):
        """Delegate language application to the settings controller."""
        language = self.comboBox.currentData()

        if isinstance(language, str):
            SettingsController.setLanguage(language)


class _SettingsSection(QWidget):
    """Group a translated heading and a stack of settings cards."""

    def __init__(self, parent=None):
        """Initialize an empty settings section."""
        super().__init__(parent)

        self.titleLabel = QLabel(parent=self)
        self.titleLabel.setObjectName('SettingsSectionTitle')
        self.cards = []

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)
        self.layout.addWidget(self.titleLabel)

    def addCard(self, card: _SettingsCard):
        """Append a card while retaining it for translation and syncing."""
        self.cards.append(card)
        self.layout.addWidget(card)


class SettingsPage(Mixins.QTranslatable, QMainWindow):
    """Compose application settings without owning their operational logic."""

    def __init__(
        self,
        *,
        tunSettingsDialogFactory,
        proxyBypassDialog,
        networkTestDialog,
        checkForUpdates,
        openAboutPage,
        restartAsAdmin,
        openApplicationFolder,
        parent=None,
    ):
        """Build settings sections around existing actions and dialogs."""
        super().__init__(parent)

        self.setObjectName('SettingsPage')

        (
            self._tunSettingsDialogFactory,
            self._proxyBypassDialog,
            self._networkTestDialog,
            self._checkForUpdates,
            self._openAboutPage,
            self._restartAsAdmin,
            self._openApplicationFolder,
        ) = (
            tunSettingsDialogFactory,
            proxyBypassDialog,
            networkTestDialog,
            checkForUpdates,
            openAboutPage,
            restartAsAdmin,
            openApplicationFolder,
        )

        self.pageTitleLabel = QLabel()
        self.pageTitleLabel.setObjectName('SettingsPageTitle')

        self.generalSection = _SettingsSection()
        self.connectionSection = _SettingsSection()
        self.hysteriaSection = _SettingsSection()
        self.applicationSection = _SettingsSection()

        self.tunModeAction = TUNModeAction(
            checkable=True,
            checked=AppSettings.isStateON_('VPNMode'),
        )
        self.tunModeCard = _ToggleSettingsCard(
            'shield-check.svg',
            'VPNMode',
            self._setTUNMode,
        )
        self.tunModeCard.checkBox.setEnabled(self.tunModeAction.isEnabled())

        self.tunModeAction.changed.connect(self._syncTUNModeAction)
        self.tunModeAction.toggled.connect(self._syncTUNModeAction)

        (
            self.darkModeCard,
            self.languageCard,
            self.monochromeCard,
            self.startupCard,
            self.powerSaveCard,
        ) = (
            _ToggleSettingsCard(
                'moon-stars.svg',
                'DarkMode',
                SettingsController.setDarkMode,
            ),
            _LanguageSettingsCard(),
            _ToggleSettingsCard(
                'circle-half.svg',
                'UseMonochromeTrayIcon',
                SettingsController.setMonochromeTrayIcon,
            ),
            _ToggleSettingsCard(
                'power.svg',
                'StartupOnBoot',
                SettingsController.setStartupOnBoot,
            ),
            _ToggleSettingsCard(
                'battery-half.svg',
                'PowerSaveMode',
                SettingsController.setPowerSaveMode,
            ),
        )

        self.generalSection.addCard(self.tunModeCard)
        self.generalSection.addCard(self.darkModeCard)
        self.generalSection.addCard(self.languageCard)
        self.generalSection.addCard(self.monochromeCard)

        if PLATFORM == 'Darwin':
            self.hideDockCard = _ToggleSettingsCard(
                'window.svg',
                'HideDockIcon',
                SettingsController.setDockIconHidden,
            )
            self.generalSection.addCard(self.hideDockCard)
        else:
            self.hideDockCard = None

        self.generalSection.addCard(self.startupCard)
        self.generalSection.addCard(self.powerSaveCard)

        (
            self.tunSettingsCard,
            self.proxyBypassCard,
            self.networkTestCard,
            self.forceLocalhostCard,
            self.connectionProgressCard,
            self.editorWhitespaceCard,
        ) = (
            _ActionSettingsCard(
                'diagram-3.svg',
                self._openTUNSettings,
            ),
            _ActionSettingsCard(
                'signpost-split.svg',
                self._proxyBypassDialog.open,
            ),
            _ActionSettingsCard(
                'link-45deg.svg',
                self._networkTestDialog.open,
            ),
            _ToggleSettingsCard(
                'pc-display-horizontal.svg',
                'ForceToLocalhostWhenSettingLocalProxy',
                SettingsController.setForceLocalProxy,
            ),
            _ToggleSettingsCard(
                'hourglass-split.svg',
                'ShowProgressBarWhenConnecting',
                SettingsController.setConnectionProgressVisible,
            ),
            _ToggleSettingsCard(
                'text-paragraph.svg',
                'ShowTabAndSpacesInEditor',
                SettingsController.setEditorWhitespaceVisible,
            ),
        )

        if not SystemRuntime.flatpakID():
            self.connectionSection.addCard(self.tunSettingsCard)

        self.connectionSection.addCard(self.proxyBypassCard)
        self.connectionSection.addCard(self.networkTestCard)
        self.connectionSection.addCard(self.forceLocalhostCard)
        self.connectionSection.addCard(self.connectionProgressCard)
        self.connectionSection.addCard(self.editorWhitespaceCard)

        if SystemRuntime.isAssetsFolderWritable():
            self.autoAssetsCard = _ToggleSettingsCard(
                'cloud-arrow-down.svg',
                'AutoUpdateAssetFiles',
                SettingsController.setAutoUpdateAssets,
            )
            self.connectionSection.addCard(self.autoAssetsCard)
        else:
            self.autoAssetsCard = None

        (
            self.hysteriaURLCard,
            self.hysteriaClientIdCard,
            self.hysteriaSecretCard,
        ) = (
            _LineEditSettingsCard(
                'activity.svg',
                HYSTERIA2_STATS_URL_SETTING,
                placeholder='http://server:9999',
            ),
            _LineEditSettingsCard(
                'person-badge.svg',
                HYSTERIA2_STATS_CLIENT_ID_SETTING,
            ),
            _LineEditSettingsCard(
                'key.svg',
                HYSTERIA2_STATS_SECRET_SETTING,
                secret=True,
                strip=False,
            ),
        )

        self.hysteriaSection.addCard(self.hysteriaURLCard)
        self.hysteriaSection.addCard(self.hysteriaClientIdCard)
        self.hysteriaSection.addCard(self.hysteriaSecretCard)

        (
            self.updateCard,
            self.aboutCard,
        ) = (
            _ActionSettingsCard(
                'download.svg',
                lambda: self._checkForUpdates(parent=self),
            ),
            _ActionSettingsCard(
                'info-circle.svg',
                self._openAboutPage,
            ),
        )

        self.applicationSection.addCard(self.updateCard)
        self.applicationSection.addCard(self.aboutCard)

        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            self.restartCard = _ActionSettingsCard(
                'arrow-clockwise.svg',
                self._restartAsAdmin,
            )
            self.applicationSection.addCard(self.restartCard)
        else:
            self.restartCard = None

        if PLATFORM != 'Darwin' and not SystemRuntime.flatpakID():
            self.openFolderCard = _ActionSettingsCard(
                'folder2-open.svg',
                self._openApplicationFolder,
            )
            self.applicationSection.addCard(self.openFolderCard)
        else:
            self.openFolderCard = None

        contentWidget = QWidget()
        contentWidget.setObjectName('SettingsPageContent')

        contentLayout = QVBoxLayout(contentWidget)
        contentLayout.setContentsMargins(20, 18, 20, 24)
        contentLayout.setSpacing(22)
        contentLayout.addWidget(self.pageTitleLabel)
        contentLayout.addWidget(self.generalSection)
        contentLayout.addWidget(self.connectionSection)
        contentLayout.addWidget(self.hysteriaSection)
        contentLayout.addWidget(self.applicationSection)
        contentLayout.addStretch(1)

        self.scrollArea = QScrollArea()
        self.scrollArea.setObjectName('SettingsScrollArea')
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setWidget(contentWidget)
        self.setCentralWidget(self.scrollArea)

        self.retranslate()

    def _setTUNMode(self, enabled: bool):
        """Trigger the compatibility action used by connection state."""
        if self.tunModeAction.isChecked() != enabled:
            self.tunModeAction.trigger()

    @QtCore.Slot()
    def _syncTUNModeAction(self, *_args):
        """Mirror compatibility-action state into the settings control."""
        blocker = QtCore.QSignalBlocker(self.tunModeCard.checkBox)

        self.tunModeCard.checkBox.setChecked(self.tunModeAction.isChecked())
        self.tunModeCard.checkBox.setEnabled(self.tunModeAction.isEnabled())

        del blocker

    def _openTUNSettings(self):
        """Create and retain the existing Tun2socks settings dialog."""
        self._tunSettingsDialogFactory(parent=self).open()

    def setTUNModeControlEnabled(self, enabled: bool):
        """Disable TUN changes while a connection transition is active."""
        self.tunModeAction.setEnabled(enabled)
        self.tunModeCard.checkBox.setEnabled(enabled)

    @staticmethod
    def _setActionCardText(card, buttonText, title, description):
        """Apply translated action-card text consistently."""
        card.button.setText(buttonText)
        card.setTexts(title, description)

    def showEvent(self, event):
        """Synchronize controls in case a legacy action changed a setting."""
        super().showEvent(event)

        for section in (
            self.generalSection,
            self.connectionSection,
            self.applicationSection,
        ):
            for card in section.cards:
                sync = getattr(card, 'sync', None)

                if callable(sync):
                    sync()

        self.languageCard.sync()

    def retranslate(self):
        """Refresh section, card, button, and accessibility text."""
        self.pageTitleLabel.setText(_('Settings'))
        self.generalSection.titleLabel.setText(_('General'))
        self.connectionSection.titleLabel.setText(_('Connection and Interface'))
        self.hysteriaSection.titleLabel.setText(_('Hysteria2 Traffic Statistics'))
        self.applicationSection.titleLabel.setText(_('Application'))

        tunTitle = _('TUN Mode')

        if PLATFORM != 'Linux' and not SystemRuntime.isAdmin():
            if ADMINISTRATOR_NAME == 'Administrator':
                tunTitle = _('TUN Mode Disabled (Administrator)')
            else:
                tunTitle = _('TUN Mode Disabled (Superuser)')

        self.tunModeCard.setTexts(
            tunTitle,
            _('Route system traffic through the active proxy connection.'),
        )
        self.darkModeCard.setTexts(
            _('Dark Mode'),
            _('Use the application dark theme instead of automatic appearance.'),
        )
        self.languageCard.setTexts(
            _('Language'),
            _('Choose the language used by the application interface.'),
        )
        self.monochromeCard.setTexts(
            _('Use Monochrome Tray Icon'),
            _('Use a theme-aware single-color system tray icon.'),
        )
        self.startupCard.setTexts(
            _('Startup On Boot'),
            _('Start the application automatically after signing in.'),
        )
        self.powerSaveCard.setTexts(
            _('Power Save Mode'),
            _('Reduce background activity when the application is idle.'),
        )

        if self.hideDockCard is not None:
            self.hideDockCard.setTexts(
                _('Hide Dock Icon'),
                _('Keep the application available from the menu bar only.'),
            )

        self._setActionCardText(
            self.tunSettingsCard,
            _('Open'),
            _('Customize Tun2socks Settings...'),
            _('Configure the external Tun2socks network interface and routing.'),
        )
        self._setActionCardText(
            self.proxyBypassCard,
            _('Open'),
            _('Customize System Proxy Bypass Address...'),
            _('Choose destinations that bypass the operating system proxy.'),
        )
        self._setActionCardText(
            self.networkTestCard,
            _('Open'),
            _('Customize Network Test URL...'),
            _('Choose the URL used for download speed tests.'),
        )
        self.forceLocalhostCard.setTexts(
            _('Force To 127.0.0.1 When Setting Local Proxy'),
            _('Use the IPv4 loopback address when configuring the system proxy.'),
        )
        self.connectionProgressCard.setTexts(
            _('Show Progress Bar When Connecting'),
            _('Show connection progress while proxy services are starting.'),
        )
        self.editorWhitespaceCard.setTexts(
            _('Show Tab And Spaces In Editor'),
            _('Display whitespace markers in configuration editors.'),
        )

        if self.autoAssetsCard is not None:
            self.autoAssetsCard.setTexts(
                _('Automatically Update Asset Files'),
                _('Keep supported proxy-core data files up to date.'),
            )

        self.hysteriaURLCard.setTexts(
            _('Traffic Stats API URL'),
            _('Hysteria2 server API address; /traffic is appended automatically.'),
        )
        self.hysteriaClientIdCard.setTexts(
            _('Traffic Stats Client ID'),
            _('Authentication ID reported by the Hysteria2 server.'),
        )
        self.hysteriaSecretCard.setTexts(
            _('Traffic Stats API Secret'),
            _('Authorization value configured by the Hysteria2 server.'),
        )

        self._setActionCardText(
            self.updateCard,
            _('Check'),
            _('Check For Updates'),
            _('Check for a newer application and proxy-core release.'),
        )
        self._setActionCardText(
            self.aboutCard,
            _('View'),
            _('About'),
            f'{APPLICATION_NAME} {APPLICATION_VERSION}',
        )

        if self.restartCard is not None:
            if ADMINISTRATOR_NAME == 'Administrator':
                restartTitle = _('Restart The Application As Administrator')
            else:
                restartTitle = _('Restart The Application As Superuser')

            self._setActionCardText(
                self.restartCard,
                _('Restart'),
                restartTitle,
                _('Restart with privileges required by system-level networking.'),
            )

        if self.openFolderCard is not None:
            self._setActionCardText(
                self.openFolderCard,
                _('Open'),
                _('Open Application Folder'),
                _('Open the folder containing the current application.'),
            )

        self.languageCard.sync()
