from Furious.Widget.Widget import GroupBox, Label
from Furious.Utility.Constants import (
    APP,
    DEFAULT_TOR_SOCKS_PORT,
    DEFAULT_TOR_HTTPS_PORT,
)
from Furious.Utility.Utility import (
    StateContext,
    SupportConnectedCallback,
    TorRelaySettingsStorage,
    bootstrapIcon,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _

from PySide6 import QtCore
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QSpinBox,
    QWidget,
)


class TorRelaySettingsWidget(Translatable, SupportConnectedCallback, QDialog):
    TOR_LOG_LEVEL = ['err', 'warn', 'notice', 'info', 'debug']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Tor Relay Settings'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        try:
            self.StorageObj = TorRelaySettingsStorage.toObject(APP().TorRelaySettings)
        except Exception:
            # Any non-exit exceptions

            self.StorageObj = TorRelaySettingsStorage.init()

            # Clear it
            TorRelaySettingsStorage.clear()

        self.endpointGroupBox = GroupBox(_('Tunnel Port'), parent=self)
        self.useProxyGroupBox = GroupBox(_('Proxy'), parent=self)
        self.torOtherGroupBox = GroupBox(_('Other'), parent=self)

        # Begin endpoint groupbox
        self.socksTunnelLabel = Label(_('socks'), parent=self)
        self.httpsTunnelLabel = Label(_('http'), parent=self)

        self.socksTunnelSpinBox = QSpinBox(parent=self)
        self.socksTunnelSpinBox.setMinimum(0)
        self.socksTunnelSpinBox.setMaximum(65535)

        self.httpsTunnelSpinBox = QSpinBox(parent=self)
        self.httpsTunnelSpinBox.setMinimum(0)
        self.httpsTunnelSpinBox.setMaximum(65535)

        self.socksTunnelWidget = QWidget(parent=self)
        self.socksTunnelLayout = QFormLayout(parent=self.socksTunnelWidget)
        self.socksTunnelLayout.addRow(self.socksTunnelLabel, self.socksTunnelSpinBox)
        self.socksTunnelWidget.setLayout(self.socksTunnelLayout)

        self.httpsTunnelWidget = QWidget(parent=self)
        self.httpsTunnelLayout = QFormLayout(parent=self.httpsTunnelWidget)
        self.httpsTunnelLayout.addRow(self.httpsTunnelLabel, self.httpsTunnelSpinBox)
        self.httpsTunnelWidget.setLayout(self.httpsTunnelLayout)

        self.endpointGroupBoxLayout = QGridLayout(parent=self.endpointGroupBox)
        self.endpointGroupBoxLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.endpointGroupBoxLayout.addWidget(self.socksTunnelWidget, 0, 0)
        self.endpointGroupBoxLayout.addWidget(self.httpsTunnelWidget, 0, 1)

        self.endpointGroupBox.setLayout(self.endpointGroupBoxLayout)
        # End endpoint groupbox

        # Begin useProxy groupbox
        self.useProxyLabel = Label(_('Use Proxy'), parent=self)

        self.useProxyCheckBox = QCheckBox(parent=self)

        self.useProxyWidget = QWidget(parent=self)
        self.useProxyLayout = QFormLayout(parent=self.useProxyWidget)
        self.useProxyLayout.addRow(self.useProxyLabel, self.useProxyCheckBox)
        self.useProxyWidget.setLayout(self.useProxyLayout)

        self.useProxyGroupBoxLayout = QGridLayout(parent=self.useProxyGroupBox)
        self.useProxyGroupBoxLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.useProxyGroupBoxLayout.addWidget(self.useProxyWidget, 0, 0)

        self.useProxyGroupBox.setLayout(self.useProxyGroupBoxLayout)
        # End useProxy groupbox

        # Begin torOther groupbox
        self.torLogLevelLabel = Label(_('Log Level'), parent=self)

        self.torLogLevelComboBox = QComboBox(parent=self)
        self.torLogLevelComboBox.addItems(TorRelaySettingsWidget.TOR_LOG_LEVEL)

        self.torRelayTimeoutLabel = Label(
            _('Relay Establish Timeout(seconds)'), parent=self
        )

        self.torRelayTimeoutSpinBox = QSpinBox(parent=self)
        self.torRelayTimeoutSpinBox.setMinimum(0)
        self.torRelayTimeoutSpinBox.setMaximum(3600)

        self.torLogLevelWidget = QWidget(parent=self)
        self.torLogLevelLayout = QFormLayout(parent=self.torLogLevelWidget)
        self.torLogLevelLayout.addRow(self.torLogLevelLabel, self.torLogLevelComboBox)
        self.torLogLevelWidget.setLayout(self.torLogLevelLayout)

        self.torRelayTimeoutWidget = QWidget(parent=self)
        self.torRelayTimeoutLayout = QFormLayout(parent=self.torRelayTimeoutWidget)
        self.torRelayTimeoutLayout.addRow(
            self.torRelayTimeoutLabel, self.torRelayTimeoutSpinBox
        )
        self.torRelayTimeoutWidget.setLayout(self.torRelayTimeoutLayout)

        self.torOtherGroupBoxLayout = QGridLayout(parent=self.torOtherGroupBox)
        self.torOtherGroupBoxLayout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.torOtherGroupBoxLayout.addWidget(self.torLogLevelWidget, 0, 0)
        self.torOtherGroupBoxLayout.addWidget(self.torRelayTimeoutWidget, 0, 1)

        self.torOtherGroupBox.setLayout(self.torOtherGroupBoxLayout)
        # End torOther groupbox

        # Restore value
        self.restoreValueFromObject()

        # Dialog buttons
        self.dialogBtns = QDialogButtonBox(
            QtCore.Qt.Orientation.Horizontal, parent=self
        )

        self.dialogBtns.addButton(_('OK'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(_('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        self.dialogBtns.accepted.connect(self.handleAccepted)
        self.dialogBtns.rejected.connect(self.handleRejected)

        # Central Widget
        self.fakeCentralWidget = QWidget(parent=self)

        self.layout = QGridLayout(parent=self.fakeCentralWidget)
        self.layout.addWidget(self.endpointGroupBox, 0, 0)
        self.layout.addWidget(self.useProxyGroupBox, 1, 0)
        self.layout.addWidget(self.torOtherGroupBox, 2, 0)
        self.layout.addWidget(self.dialogBtns, 3, 0)

        self.setLayout(self.layout)

    @QtCore.Slot()
    def handleAccepted(self):
        # Sync object
        self.StorageObj['socksTunnelPort'] = self.socksTunnelSpinBox.value()
        self.StorageObj['httpsTunnelPort'] = self.httpsTunnelSpinBox.value()
        self.StorageObj['useProxy'] = self.useProxyCheckBox.isChecked()
        self.StorageObj['logLevel'] = self.torLogLevelComboBox.currentText()
        self.StorageObj['relayEstablishTimeout'] = self.torRelayTimeoutSpinBox.value()

        # Sync it
        TorRelaySettingsStorage.sync()

        self.hide()

    @QtCore.Slot()
    def handleRejected(self):
        self.restoreValueFromObject()
        self.hide()

    def restoreValueFromObject(self):
        # Restore value
        self.socksTunnelSpinBox.setValue(
            self.StorageObj.get('socksTunnelPort', DEFAULT_TOR_SOCKS_PORT)
        )
        self.httpsTunnelSpinBox.setValue(
            self.StorageObj.get('httpsTunnelPort', DEFAULT_TOR_HTTPS_PORT)
        )

        self.useProxyCheckBox.setChecked(self.StorageObj.get('useProxy', True))

        self.torLogLevelComboBox.setCurrentText(
            self.StorageObj.get('logLevel', 'notice')
        )
        self.torRelayTimeoutSpinBox.setValue(
            self.StorageObj.get('relayEstablishTimeout', 15)
        )

    def closeEvent(self, event):
        event.ignore()

        self.restoreValueFromObject()
        self.hide()

    def connectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))

    def disconnectedCallback(self):
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))

            for button in self.dialogBtns.buttons():
                button.setText(_(button.text()))

            moveToCenter(self)
