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

from Furious.Controllers import (
    APPLICATION_THEME_SETTING,
    SYSTEM_PROXY_MODE_OPTIONS,
)
from Furious.Frozenlib import *
from Furious.Plugins import (
    CapabilityKind,
    PluginSettingControl,
    PluginSettingDescriptor,
    PluginSettingsSection,
    getPluginRegistry,
)
from Furious.Qt import *
from Furious.Qt import gettext as _
from Furious.Service import PROXY_ENDPOINT_INFO_SETTING, isCoreActive
from Furious.Service.TrafficStatsManager import (
    CLEAR_TRAFFIC_USAGE_ON_RECONNECT_SETTING,
    METRICS_COLLECTION_SETTING,
)

from PySide6 import QtCore
from PySide6.QtWidgets import *

from collections import Counter
from collections.abc import Callable

import logging

__all__ = ['SettingsPage']

logger = logging.getLogger(__name__)


def _endpointPrivacyParagraphs():
    """Return concise translated disclosure text for the current providers."""
    return (
        _(
            '<b>Public IP</b><br>\n'
            "Your proxy's public IPv4 and IPv6 addresses are checked<br>\n"
            'through the active proxy connection using Cloudflare,<br>\n'
            'with ipify as a fallback.<br>\nThese services '
            "can observe the proxy's public IP."
        ),
        _(
            '<b>Approximate Location</b><br>\n'
            'The detected public IP is sent to ipapi.co<br>\n'
            'to estimate country, city, region, and network organization.<br>\n'
            'IP-based location can be inaccurate.'
        ),
        _(
            '<b>Map</b><br>\n'
            'Map styles and tiles for the approximate area are loaded<br>\n'
            'from OpenFreeMap, using OpenStreetMap data.<br>\n'
            'OpenFreeMap receives these map requests.'
        ),
    )


def _endpointPrivacyMessageBox(parent=None):
    """Build one transient Fluent data-usage disclosure."""
    mbox = AppQMessageBox(
        icon=AppQMessageBox.Icon.Information,
        parent=parent,
        text=_('Proxy Endpoint Information & Privacy'),
        buttons=AppQMessageBox.StandardButton.Ok,
    )
    mbox.informativeLabel.setTextFormat(QtCore.Qt.TextFormat.RichText)
    mbox.setInformativeText('<br><br>\n'.join(_endpointPrivacyParagraphs()))

    return mbox


def _tunModeTitle() -> str:
    """Return the platform-appropriate translated TUN setting title."""
    if PLATFORM == 'Linux' or SystemRuntime.isAdmin():
        return _('TUN Mode')

    if ADMINISTRATOR_NAME == 'Administrator':
        return _('TUN Mode Disabled (Administrator)')

    return _('TUN Mode Disabled (Superuser)')


def _restartApplicationTitle() -> str:
    """Return the translated privilege-restart title for this platform."""
    if ADMINISTRATOR_NAME == 'Administrator':
        return _('Restart The Application As Administrator')

    return _('Restart The Application As Superuser')


class _SettingsCard(Mixins.ThemeAware, QFrame):
    """Lay out a themed icon, title, description, and trailing control."""

    IconSize = QtCore.QSize(20, 20)

    def __init__(
        self,
        iconFileName: str,
        control: QWidget,
        title='',
        description='',
        *,
        translatable=True,
        parent=None,
    ):
        """Initialize one reusable settings row."""
        super().__init__(parent)

        self.setObjectName('SettingsCard')
        self.iconFileName = ''
        self.iconLabel = QLabel(parent=self)
        self.iconLabel.setObjectName('SettingsCardIcon')
        self.iconLabel.setFixedSize(self.IconSize)
        self.titleLabel = AppQLabel(
            title,
            translatable=translatable,
            parent=self,
        )
        self.titleLabel.setObjectName('SettingsCardTitle')
        self.descriptionLabel = AppQLabel(
            description,
            translatable=translatable,
            parent=self,
        )
        self.descriptionLabel.setObjectName('SettingsCardDescription')
        self.descriptionLabel.setWordWrap(True)
        self.control = control
        self.control.setParent(self)

        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 0, 0, 0)
        self.textLayout.setSpacing(2)
        self.textLayout.addWidget(self.titleLabel)
        self.textLayout.addWidget(self.descriptionLabel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        layout.addWidget(self.iconLabel, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(self.textLayout, 1)
        layout.addSpacing(16)
        layout.addWidget(self.control, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.setIconFileName(iconFileName)

    def setTexts(self, title: str, description: str):
        """Set already translated card text."""
        self.titleLabel.setText(title)
        self.descriptionLabel.setText(description)

    def setIconFileName(self, iconFileName: str | None):
        """Set or remove the optional leading card icon."""
        self.iconFileName = iconFileName or ''

        # Keep the fixed-size icon column in the layout even when no artwork is
        # requested so every card's title and description share one text edge.
        self.iconLabel.setVisible(True)

        if self.iconFileName:
            self.setIconByTheme(APP().theme())
        else:
            self.iconLabel.clear()

    def setIconByTheme(self, theme: str):
        """Refresh the card icon for the active theme."""
        if not self.iconFileName:
            return

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

    def __init__(
        self,
        iconFileName,
        settingName,
        callback,
        title='',
        description='',
        *,
        translatable=True,
        parent=None,
    ):
        """Initialize a persistent binary setting card."""
        self.settingName = settingName
        self._callback = callback

        self.checkBox = AppQSwitch()
        self.checkBox.syncChecked(AppSettings.isStateON_(settingName))
        self.checkBox.toggled.connect(self._requestedState)

        super().__init__(
            iconFileName,
            self.checkBox,
            title,
            description,
            translatable=translatable,
            parent=parent,
        )

    @QtCore.Slot(bool)
    def _requestedState(self, checked: bool):
        """Apply a requested setting and restore persisted state on failure."""
        if self._callback(checked) is False:
            self.sync()

    def sync(self):
        """Refresh the control from persistent state without applying it."""
        self.checkBox.syncChecked(AppSettings.isStateON_(self.settingName))


class _EndpointInfoSettingsCard(_ToggleSettingsCard):
    """Pair the opt-in endpoint switch with an in-app privacy explanation."""

    def __init__(self, callback, privacyCallback, parent=None):
        """Initialize one translated privacy-sensitive settings card."""
        super().__init__(
            'geo-alt.svg',
            PROXY_ENDPOINT_INFO_SETTING,
            callback,
            _('Enable Proxy Endpoint Information'),
            _('Inspect the active proxy public address and approximate location.'),
            parent=parent,
        )

        self.privacyButton = AppQPushButton(_('Data usage'), parent=self)
        self.privacyButton.setObjectName('SettingsLinkButton')
        self.privacyButton.setFlat(True)

        linkFont = self.privacyButton.font()
        linkFont.setUnderline(True)

        self.privacyButton.setFont(linkFont)
        self.privacyButton.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.privacyButton.clicked.connect(privacyCallback)

        self.textLayout.addWidget(
            self.privacyButton,
            0,
            QtCore.Qt.AlignmentFlag.AlignLeft,
        )


class _ActionToggleSettingsCard(_SettingsCard):
    """Present a plugin-provided checkable action as a Fluent switch."""

    def __init__(
        self,
        iconFileName,
        action,
        title='',
        description='',
        *,
        translatable=False,
        parent=None,
    ):
        """Bind switch requests and external action-state changes."""
        self.action = action

        self.checkBox = AppQSwitch()
        self.checkBox.syncChecked(action.isChecked())
        self.checkBox.setEnabled(action.isEnabled())
        self.checkBox.toggled.connect(self._requestedState)

        action.toggled.connect(self.sync)
        action.changed.connect(self.sync)

        super().__init__(
            iconFileName,
            self.checkBox,
            title,
            description,
            translatable=translatable,
            parent=parent,
        )

    @QtCore.Slot(bool)
    def _requestedState(self, checked: bool):
        """Trigger the action only when its state differs from the switch."""
        if self.action.isChecked() != checked:
            self.action.trigger()

    @QtCore.Slot()
    def sync(self, *_args):
        """Synchronize state changed by another plugin UI entry point."""
        if self.checkBox.isChecked() != self.action.isChecked():
            self.checkBox.syncChecked(self.action.isChecked())

        self.checkBox.setEnabled(self.action.isEnabled())


class _ActionSettingsCard(_SettingsCard):
    """Expose an existing command through one settings row."""

    def __init__(
        self,
        iconFileName,
        callback: Callable,
        title='',
        description='',
        buttonText='',
        *,
        translatable=True,
        buttonTranslatable=None,
        parent=None,
    ):
        """Initialize a card with a compact trailing action button."""
        if buttonTranslatable is None:
            buttonTranslatable = translatable

        self.button = AppQPushButton(
            buttonText,
            translatable=buttonTranslatable,
        )
        self.button.setObjectName('SettingsActionButton')
        self.button.clicked.connect(callback)

        super().__init__(
            iconFileName,
            self.button,
            title,
            description,
            translatable=translatable,
            parent=parent,
        )


class _LineEditSettingsCard(_SettingsCard):
    """Persist one text setting when editing finishes."""

    def __init__(
        self,
        iconFileName,
        settingName,
        title='',
        description='',
        *,
        placeholder='',
        secret=False,
        strip=True,
        translatable=True,
        parent=None,
    ):
        """Initialize one bounded settings text editor."""
        self.settingName = settingName
        self.strip = strip
        self.lineEdit = AppQLineEdit(translatable=False)
        self.lineEdit.setObjectName('SettingsLineEdit')
        self.lineEdit.setMaximumWidth(420)
        self.lineEdit.setMinimumWidth(260)
        self.lineEdit.setPlaceholderText(placeholder)
        self.lineEdit.setText(str(AppSettings.get(settingName) or ''))

        if secret:
            self.lineEdit.setEchoMode(AppQLineEdit.EchoMode.Password)

        self.lineEdit.editingFinished.connect(self.persist)

        super().__init__(
            iconFileName,
            self.lineEdit,
            title,
            description,
            translatable=translatable,
            parent=parent,
        )

    def persist(self):
        """Store the current text without coupling it to graph code."""
        value = self.lineEdit.text()

        if self.strip:
            value = value.strip()

        AppSettings.set(self.settingName, value)


class _LanguageSettingsCard(_SettingsCard):
    """Select and apply one supported application language."""

    def __init__(self, title='', description='', parent=None):
        """Initialize the stable language-name selector."""
        # These are intentional native-language representations (for example,
        # "Русский" and "简体中文"), not strings in the active UI locale.
        self.comboBox = QComboBox()
        self.comboBox.setObjectName('SettingsComboBox')
        self.comboBox.setMinimumWidth(180)

        for languageName, language in LANGUAGE_TO_ABBR.items():
            self.comboBox.addItem(languageName, language)

        self.sync()
        self.comboBox.currentIndexChanged.connect(self._selectionChanged)

        super().__init__(
            'globe2.svg',
            self.comboBox,
            title,
            description,
            parent=parent,
        )

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
            AppSettingsController().setLanguage(language)


class _ApplicationThemeSettingsCard(_SettingsCard):
    """Select the source of the application light or dark appearance."""

    Options = (
        ('Follow System Appearance', ApplicationTheme.System),
        ('Light Theme', ApplicationTheme.Light),
        ('Dark Theme', ApplicationTheme.Dark),
    )

    _TranslatableOptions = (
        _('Follow System Appearance'),
        _('Light Theme'),
        _('Dark Theme'),
    )

    def __init__(self, title='', description='', parent=None):
        """Initialize the translated application-theme selector."""
        self.comboBox = AppQComboBox()
        self.comboBox.setObjectName('SettingsComboBox')
        self.comboBox.setContentWidthAdjustable()
        self.comboBox.setMinimumWidth(260)

        for label, preference in self.Options:
            self.comboBox.addItem(_(label), preference.value)

        self.sync()

        self.comboBox.currentIndexChanged.connect(self._selectionChanged)

        super().__init__(
            'moon-stars.svg',
            self.comboBox,
            title,
            description,
            parent=parent,
        )

    def sync(self):
        """Select the persisted preference without applying it again."""
        blocker = QtCore.QSignalBlocker(self.comboBox)

        index = self.comboBox.findData(AppSettings.get(APPLICATION_THEME_SETTING))

        self.comboBox.setCurrentIndex(max(index, 0))

        del blocker

    @QtCore.Slot(int)
    def _selectionChanged(self, _index: int):
        """Persist and apply the selected application theme preference."""
        preference = self.comboBox.currentData()

        if isinstance(preference, str):
            AppSettingsController().setApplicationTheme(preference)


class _SystemProxySettingsCard(_SettingsCard):
    """Select how Furious manages the operating-system proxy."""

    Options = SYSTEM_PROXY_MODE_OPTIONS

    _TranslatableOptions = (
        _('Automatically Configure System Proxy'),
        _('Do Not Change System Proxy'),
    )

    def __init__(self, title='', description='', parent=None):
        """Initialize the translated system-proxy mode selector."""
        self.comboBox = AppQComboBox()
        self.comboBox.setObjectName('SettingsComboBox')
        self.comboBox.setContentWidthAdjustable()
        self.comboBox.setMinimumWidth(260)

        for label, mode in self.Options:
            self.comboBox.addItem(_(label), mode)

        self.sync()
        self.comboBox.currentIndexChanged.connect(self._selectionChanged)

        super().__init__(
            'hdd-network.svg',
            self.comboBox,
            title,
            description,
            parent=parent,
        )

    def sync(self, mode=None):
        """Select the persisted proxy mode without writing it again."""
        blocker = QtCore.QSignalBlocker(self.comboBox)
        selectedMode = (
            mode if isinstance(mode, str) else AppSettings.get('SystemProxyMode')
        )
        index = self.comboBox.findData(selectedMode)

        self.comboBox.setCurrentIndex(max(index, 0))

        del blocker

    @QtCore.Slot(int)
    def _selectionChanged(self, _index: int):
        """Persist the selected proxy-management mode."""
        mode = self.comboBox.currentData()

        if isinstance(mode, str):
            AppSettingsController().setSystemProxyMode(mode)


class _SettingsSection(QWidget):
    """Group a translated heading and a stack of settings cards."""

    def __init__(self, title='', *, translatable=True, parent=None):
        """Initialize an empty settings section."""
        super().__init__(parent)

        self.titleLabel = AppQLabel(
            title,
            translatable=translatable,
            parent=self,
        )
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

    def suppressDuplicateIcons(self):
        """Remove repeated artwork that adds no meaning within this section."""
        iconCounts = Counter(
            card.iconFileName for card in self.cards if card.iconFileName
        )
        duplicateIcons = {
            iconFileName for iconFileName, count in iconCounts.items() if count > 1
        }

        for card in self.cards:
            if card.iconFileName in duplicateIcons:
                card.setIconFileName(None)


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

        self.pageTitleLabel = AppQLabel(_('Settings'))
        self.pageTitleLabel.setObjectName('SettingsPageTitle')

        self.generalSection = _SettingsSection(_('General'))
        self.connectionSection = _SettingsSection(_('Connection and Interface'))
        self.applicationSection = _SettingsSection(_('Application'))
        self.pluginSettingsTitleLabel = AppQLabel(_('Plugin Settings'))
        self.pluginSettingsTitleLabel.setObjectName('SettingsSectionTitle')
        self.pluginSections = []
        self._pluginActions = []

        self._tunModeAvailable = AppSettingsController().tunModeAvailable()

        self.tunModeCard = _ToggleSettingsCard(
            'shield-check.svg',
            'VPNMode',
            AppSettingsController().setTUNMode,
            _tunModeTitle(),
            _('Route system traffic through the active proxy connection.'),
        )
        self.tunModeCard.checkBox.setEnabled(self._tunModeAvailable)

        AppSettingsController().tunModeChanged.connect(
            self.tunModeCard.checkBox.syncChecked
        )

        (
            self.applicationThemeCard,
            self.languageCard,
            self.monochromeCard,
            self.startupCard,
            self.powerSaveCard,
        ) = (
            _ApplicationThemeSettingsCard(
                _('Application Theme'),
                _('Choose how the application appearance is determined.'),
            ),
            _LanguageSettingsCard(
                _('Language'),
                _('Choose the language used by the application interface.'),
            ),
            _ToggleSettingsCard(
                'circle-half.svg',
                'UseMonochromeTrayIcon',
                AppSettingsController().setMonochromeTrayIcon,
                _('Use Monochrome Tray Icon'),
                _('Use a theme-aware single-color system tray icon.'),
            ),
            _ToggleSettingsCard(
                'power.svg',
                'StartupOnBoot',
                AppSettingsController().setStartupOnBoot,
                _('Startup On Boot'),
                _('Start the application automatically after signing in.'),
            ),
            _ToggleSettingsCard(
                'battery-half.svg',
                'PowerSaveMode',
                AppSettingsController().setPowerSaveMode,
                _('Power Save Mode'),
                _('Reduce background activity when the application is idle.'),
            ),
        )

        self.generalSection.addCard(self.tunModeCard)
        self.generalSection.addCard(self.applicationThemeCard)
        self.generalSection.addCard(self.languageCard)
        self.generalSection.addCard(self.monochromeCard)

        if PLATFORM == 'Darwin':
            self.hideDockCard = _ToggleSettingsCard(
                'window.svg',
                'HideDockIcon',
                AppSettingsController().setDockIconHidden,
                _('Hide Dock Icon'),
                _('Keep the application available from the menu bar only.'),
            )
            self.generalSection.addCard(self.hideDockCard)
        else:
            self.hideDockCard = None

        self.generalSection.addCard(self.startupCard)
        self.generalSection.addCard(self.powerSaveCard)

        (
            self.tunSettingsCard,
            self.systemProxyCard,
            self.proxyBypassCard,
            self.networkTestCard,
            self.forceLocalhostCard,
            self.connectionProgressCard,
            self.metricsCollectionCard,
            self.endpointInfoCard,
            self.clearTrafficUsageCard,
            self.editorWhitespaceCard,
        ) = (
            _ActionSettingsCard(
                'diagram-3.svg',
                self._openTUNSettings,
                _('Customize Tun2socks Settings...'),
                _('Configure the external Tun2socks network interface and routing.'),
                _('Open'),
            ),
            _SystemProxySettingsCard(
                _('System Proxy'),
                _(
                    'Choose whether Furious automatically configures the operating system proxy.'
                ),
            ),
            _ActionSettingsCard(
                'signpost-split.svg',
                self._proxyBypassDialog.open,
                _('Customize System Proxy Bypass Address...'),
                _('Choose destinations that bypass the operating system proxy.'),
                _('Open'),
            ),
            _ActionSettingsCard(
                'link-45deg.svg',
                self._networkTestDialog.open,
                _('Customize Network Test URL...'),
                _('Choose the URL used for download speed tests.'),
                _('Open'),
            ),
            _ToggleSettingsCard(
                'pc-display-horizontal.svg',
                'ForceToLocalhostWhenSettingLocalProxy',
                AppSettingsController().setForceLocalProxy,
                _('Force To 127.0.0.1 When Setting Local Proxy'),
                _('Use the IPv4 loopback address when configuring the system proxy.'),
            ),
            _ToggleSettingsCard(
                'hourglass-split.svg',
                'ShowProgressBarWhenConnecting',
                AppSettingsController().setConnectionProgressVisible,
                _('Show Progress Bar When Connecting'),
                _('Show connection progress while proxy services are starting.'),
            ),
            _ToggleSettingsCard(
                'speedometer.svg',
                METRICS_COLLECTION_SETTING,
                AppSettingsController().setMetricsCollectionEnabled,
                _('Enable Metrics Collection'),
                _('Collect network speed and traffic history while connected.'),
            ),
            _EndpointInfoSettingsCard(
                AppSettingsController().setProxyEndpointInfoEnabled,
                self._showEndpointPrivacy,
            ),
            _ToggleSettingsCard(
                'arrow-repeat.svg',
                CLEAR_TRAFFIC_USAGE_ON_RECONNECT_SETTING,
                AppSettingsController().setClearTrafficUsageOnReconnect,
                _('Clear Traffic Usage Statistics On Reconnect'),
                _(
                    'Start accumulated upload and download usage from zero after reconnecting.'
                ),
            ),
            _ToggleSettingsCard(
                'text-paragraph.svg',
                'ShowTabAndSpacesInEditor',
                AppSettingsController().setEditorWhitespaceVisible,
                _('Show Tab And Spaces In Editor'),
                _('Display whitespace markers in configuration editors.'),
            ),
        )

        AppSettingsController().systemProxyModeChanged.connect(
            self.systemProxyCard.sync
        )

        if not SystemRuntime.flatpakID():
            self.connectionSection.addCard(self.tunSettingsCard)

        self.connectionSection.addCard(self.systemProxyCard)
        self.connectionSection.addCard(self.proxyBypassCard)
        self.connectionSection.addCard(self.networkTestCard)
        self.connectionSection.addCard(self.forceLocalhostCard)
        self.connectionSection.addCard(self.connectionProgressCard)
        self.connectionSection.addCard(self.metricsCollectionCard)
        self.connectionSection.addCard(self.endpointInfoCard)
        self.connectionSection.addCard(self.clearTrafficUsageCard)
        self.connectionSection.addCard(self.editorWhitespaceCard)

        if SystemRuntime.isAssetsFolderWritable():
            self.autoAssetsCard = _ToggleSettingsCard(
                'cloud-arrow-down.svg',
                'AutoUpdateAssetFiles',
                AppSettingsController().setAutoUpdateAssets,
                _('Automatically Update Asset Files'),
                _('Keep supported proxy-core data files up to date.'),
            )
            self.connectionSection.addCard(self.autoAssetsCard)
        else:
            self.autoAssetsCard = None

        self._buildPluginSections()

        (
            self.updateCard,
            self.aboutCard,
        ) = (
            _ActionSettingsCard(
                'download.svg',
                lambda: self._checkForUpdates(parent=self),
                _('Check For Updates'),
                _('Check for a newer application and proxy-core release.'),
                _('Check'),
            ),
            _ActionSettingsCard(
                'info-circle.svg',
                self._openAboutPage,
                _('About'),
                f'{APPLICATION_NAME} {APPLICATION_VERSION}',
                _('View'),
            ),
        )

        self.applicationSection.addCard(self.updateCard)
        self.applicationSection.addCard(self.aboutCard)

        if PLATFORM == 'Windows' or PLATFORM == 'Darwin':
            self.restartCard = _ActionSettingsCard(
                'arrow-clockwise.svg',
                self._restartAsAdmin,
                _restartApplicationTitle(),
                _('Restart with privileges required by system-level networking.'),
                _('Restart'),
            )
            self.generalSection.addCard(self.restartCard)
        else:
            self.restartCard = None

        if PLATFORM != 'Darwin' and not SystemRuntime.flatpakID():
            self.openFolderCard = _ActionSettingsCard(
                'folder2-open.svg',
                self._openApplicationFolder,
                _('Open Application Folder'),
                _('Open the folder containing the current application.'),
                _('Open'),
            )
            self.generalSection.addCard(self.openFolderCard)
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

        if self.pluginSections:
            contentLayout.addWidget(self.pluginSettingsTitleLabel)

            for section in self.pluginSections:
                contentLayout.addWidget(section)

        contentLayout.addWidget(self.applicationSection)
        contentLayout.addStretch(1)

        self.scrollArea = QScrollArea()
        self.scrollArea.setObjectName('SettingsScrollArea')
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setWidget(contentWidget)
        self.setCentralWidget(self.scrollArea)

        self.retranslate()

    @staticmethod
    def _translatedPluginText(value: str, translatable: bool) -> str:
        """Translate host-owned plugin metadata only when explicitly requested."""
        return _(value) if translatable else value

    def _cardFromPluginDescriptor(self, descriptor: PluginSettingDescriptor):
        """Create one host-owned Fluent card from a plugin descriptor."""
        if not descriptor.id or not descriptor.title:
            raise ValueError('plugin settings require non-empty IDs and titles')

        try:
            control = PluginSettingControl(descriptor.control)
        except ValueError as ex:
            raise ValueError(
                f'unsupported plugin setting control: {descriptor.control!r}'
            ) from ex

        title, description = (
            self._translatedPluginText(
                descriptor.title,
                descriptor.translatable,
            ),
            self._translatedPluginText(
                descriptor.description,
                descriptor.translatable,
            ),
        )

        if control == PluginSettingControl.Toggle:
            if not descriptor.settingName:
                raise ValueError('toggle plugin settings require settingName')

            callback = descriptor.callback

            if callback is None:

                def callback(enabled, settingName=descriptor.settingName):
                    """Persist a declarative plugin toggle by default."""
                    if enabled:
                        AppSettings.turnON_(settingName)
                    else:
                        AppSettings.turnOFF(settingName)

            card = _ToggleSettingsCard(
                descriptor.iconFileName,
                descriptor.settingName,
                callback,
                title,
                description,
                translatable=descriptor.translatable,
            )
        elif control in (PluginSettingControl.Text, PluginSettingControl.Password):
            if not descriptor.settingName:
                raise ValueError('text plugin settings require settingName')

            card = _LineEditSettingsCard(
                descriptor.iconFileName,
                descriptor.settingName,
                title,
                description,
                placeholder=descriptor.placeholder,
                secret=control == PluginSettingControl.Password,
                strip=descriptor.strip,
                translatable=descriptor.translatable,
            )
        else:
            if not callable(descriptor.callback):
                raise ValueError('action plugin settings require a callback')

            card = _ActionSettingsCard(
                descriptor.iconFileName,
                descriptor.callback,
                title,
                description,
                self._translatedPluginText(
                    descriptor.buttonText,
                    descriptor.translatable,
                ),
                translatable=descriptor.translatable,
            )

        return card

    def _addPluginDescriptorSection(
        self,
        sectionDescriptor: PluginSettingsSection,
    ):
        """Validate and append one declarative plugin settings section."""
        if not isinstance(sectionDescriptor, PluginSettingsSection):
            raise TypeError('plugin settings providers must return sections')

        section = _SettingsSection(
            self._translatedPluginText(
                sectionDescriptor.title,
                sectionDescriptor.translatable,
            ),
            translatable=sectionDescriptor.translatable,
        )
        section._pluginDescriptor = sectionDescriptor

        for descriptor in sectionDescriptor.settings:
            if not isinstance(descriptor, PluginSettingDescriptor):
                raise TypeError('plugin settings sections must contain descriptors')

            section.addCard(self._cardFromPluginDescriptor(descriptor))

        section.suppressDuplicateIcons()

        if section.cards:
            self.pluginSections.append(section)

    def _addPluginActionSection(self, plugin, metadata, registry):
        """Move legacy plugin management actions into dynamic Settings cards."""
        actions = registry.managementActions(
            plugin,
            parent=self,
            isCoreActive=isCoreActive,
        )

        section = _SettingsSection(
            metadata.displayName,
            translatable=False,
        )
        section._pluginActionMetadata = metadata

        description = (
            _(metadata.description) if metadata.description else metadata.displayName
        )

        for action in actions:
            if isinstance(action, AppQSeparator):
                continue

            if not isinstance(action, AppQAction):
                continue

            self._pluginActions.append(action)

            iconFileName = action.iconFileName or 'plugin.svg'

            if action.isCheckable():
                card = _ActionToggleSettingsCard(
                    iconFileName,
                    action,
                    action.text(),
                    description,
                    translatable=True,
                )
            else:
                card = _ActionSettingsCard(
                    iconFileName,
                    lambda _checked=False, target=action: target.trigger(),
                    action.text(),
                    description,
                    _('Open'),
                    translatable=True,
                    buttonTranslatable=True,
                )

            # Plugin/action names are literal identities; descriptions may be
            # host translation keys contributed through the static catalog.
            card.titleLabel.translatable = False

            action.changed.connect(
                lambda target=card, source=action, owner=metadata: target.setTexts(
                    source.text(),
                    _(owner.description) if owner.description else owner.displayName,
                )
            )

            section.addCard(card)

        section.suppressDuplicateIcons()

        if section.cards:
            self.pluginSections.append(section)

    def _buildPluginSections(self):
        """Build plugin settings/actions without hard-coding plugin identities."""
        registry = getPluginRegistry()

        for plugin in registry.plugins():
            metadata = registry.metadataFor(plugin)

            for provider in registry.capabilities(
                CapabilityKind.PluginSettings,
                plugin,
            ):
                try:
                    sections = tuple(provider.createSections(parent=self))

                    for section in sections:
                        self._addPluginDescriptorSection(section)
                except Exception as ex:
                    logger.error(
                        f'failed to create settings from plugin '
                        f'{metadata.id!r}: {ex}'
                    )

            if registry.capabilities(CapabilityKind.ActionProvider, plugin):
                try:
                    self._addPluginActionSection(plugin, metadata, registry)
                except Exception as ex:
                    logger.error(
                        f'failed to create management settings from plugin '
                        f'{metadata.id!r}: {ex}'
                    )

    def _openTUNSettings(self):
        """Create and retain the existing Tun2socks settings dialog."""
        self._tunSettingsDialogFactory(parent=self).open()

    def _showEndpointPrivacy(self):
        """Show the end-user disclosure for the active endpoint providers."""
        _endpointPrivacyMessageBox(self).open()

    def setConnectionControlsEnabled(self, enabled: bool):
        """Disable connection-sensitive settings during a transition."""
        self.tunModeCard.checkBox.setEnabled(bool(enabled) and self._tunModeAvailable)
        self.systemProxyCard.comboBox.setEnabled(bool(enabled))

    def showEvent(self, event):
        """Synchronize controls in case a legacy action changed a setting."""
        super().showEvent(event)

        for section in (
            self.generalSection,
            self.connectionSection,
            self.applicationSection,
            *self.pluginSections,
        ):
            for card in section.cards:
                sync = getattr(card, 'sync', None)

                if callable(sync):
                    sync()

        self.languageCard.sync()

    def retranslate(self):
        """Synchronize page-level dynamic state after a language change."""
        self.languageCard.sync()
