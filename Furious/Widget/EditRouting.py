# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
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

from Furious.Action.Routing import (
    BUILTIN_ROUTING_TABLE,
    BUILTIN_ROUTING,
    RoutingChildAction,
    routingToIndex,
)
from Furious.Core.Core import XrayCore, Hysteria1
from Furious.Gui.Action import Action, Seperator
from Furious.Widget.Widget import (
    Dialog,
    HeaderView,
    Menu,
    MainWindow,
    MessageBox,
    PushButton,
    StyledItemDelegate,
    TableWidget,
    TabWidget,
    ZoomableTextBrowser,
    ZoomablePlainTextEdit,
)
from Furious.Widget.EditConfiguration import (
    JSONErrorBox,
    SaveConfInfo,
    QuestionSaveBox,
    QuestionDeleteBox,
)
from Furious.Widget.AssetViewer import AssetViewerWidget
from Furious.Utility.Constants import (
    APP,
    PLATFORM,
    APPLICATION_NAME,
    GOLDEN_RATIO,
    DATA_DIR,
    TOR_FAQ_URL,
    TOR_FAQ_LABEL,
    Color,
)
from Furious.Utility.Utility import (
    RoutesStorage,
    StateContext,
    SupportConnectedCallback,
    bootstrapIcon,
    moveToCenter,
)
from Furious.Utility.Translator import Translatable, gettext as _
from Furious.Utility.Theme import DraculaTheme

from PySide6 import QtCore
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import ujson
import logging
import operator
import functools

logger = logging.getLogger(__name__)


BUILTIN_ROUTING_TEXT = {
    'Bypass Mainland China': {
        XrayCore.name(): (
            f'# Xray-core Routing rules\n'
            f'# \n'
            f'# This rule is read-only.\n'
            f'# \n'
            f'# This is a built-in RoutingObject that\n'
            f'# implements Bypass Mainland China feature.\n'
            f'# \n'
            f'# There are four RuleObject(rules) from top\n'
            f'# to bottom which implement:\n'
            f'#     1. Block ads.(geosite:category-ads-all)\n'
            f'#     2. Bypass China site.(geosite:cn)\n'
            f'#     3. Bypass private and China IP.(geoip:private, geoip:cn)\n'
            f'#     4. Proxy traffic sent from port 0-65535, in this\n'
            f'#   case meaning any other unmatched traffic.\n'
            f'# respectively.\n'
            f'# \n'
            f'# "geoip.dat" and "geosite.dat" are shipped with\n'
            f'# {APPLICATION_NAME} by default. However, you can import\n'
            f'# and replace them if you need.\n'
            f'# \n'
            f'# See more information:\n'
            f'# \n'
            f'# https://xtls.github.io/config/routing.html\n\n'
        )
        + ujson.dumps(
            BUILTIN_ROUTING_TABLE['Bypass Mainland China'][XrayCore.name()],
            indent=2,
            ensure_ascii=False,
            escape_forward_slashes=False,
        ),
    },
    'Bypass Iran': {
        XrayCore.name(): (
            f'# Xray-core Routing rules\n'
            f'# \n'
            f'# This rule is read-only.\n'
            f'# \n'
            f'# This is a built-in RoutingObject that\n'
            f'# implements Bypass Iran feature.\n'
            f'# \n'
            f'# There are four RuleObject(rules) from top\n'
            f'# to bottom which implement:\n'
            f'#     1. Block ads.(geosite:category-ads-all, iran:ads)\n'
            f'#     2. Bypass Iran site.(iran:ir, iran:other)\n'
            f'#     3. Bypass private and Iran IP.(geoip:private, geoip:ir)\n'
            f'#     4. Proxy traffic sent from port 0-65535, in this\n'
            f'#   case meaning any other unmatched traffic.\n'
            f'# respectively.\n'
            f'# \n'
            f'# "geoip.dat", "geosite.dat" and "iran.dat" are shipped\n'
            f'# with {APPLICATION_NAME} by default. However, you can import\n'
            f'# and replace them if you need.\n'
            f'# \n'
            f'# See more information:\n'
            f'# \n'
            f'# https://xtls.github.io/config/routing.html\n\n'
        )
        + ujson.dumps(
            BUILTIN_ROUTING_TABLE['Bypass Iran'][XrayCore.name()],
            indent=2,
            ensure_ascii=False,
            escape_forward_slashes=False,
        ),
    },
    'Route My Traffic Through Tor': {
        XrayCore.name(): (
            f'# Xray-core Routing rules\n'
            f'# \n'
            f'# This rule is read-only.\n'
            f'# \n'
            f'# Use Tor to achieve better anonymity, but {APPLICATION_NAME}\n'
            f'# never claims nor guarantees *FULL* anonymity.\n'
            f'# \n'
            f'# See more information:\n'
            f'# \n'
            f'# {TOR_FAQ_URL}\n\n'
        ),
    },
    'Global': {
        XrayCore.name(): (
            f'# Xray-core Routing rules\n'
            f'# \n'
            f'# This rule is read-only.\n'
            f'# \n'
            f'# This is a built-in RoutingObject that\n'
            f'# implements Global feature.\n'
            f'# \n'
            f'# There is only one RuleObject(rules)\n'
            f'# which implements:\n'
            f'#     1. Proxy traffic sent from port 0-65535, in this\n'
            f'#   case meaning all traffic.\n'
            f'# \n'
            f'# See more information:\n'
            f'# \n'
            f'# https://xtls.github.io/config/routing.html\n\n'
        )
        + ujson.dumps(
            BUILTIN_ROUTING_TABLE['Global'][XrayCore.name()],
            indent=2,
            ensure_ascii=False,
            escape_forward_slashes=False,
        ),
    },
    'Custom': {
        XrayCore.name(): (
            f'# Xray-core Routing rules\n'
            f'# \n'
            f'# This rule is read-only.\n'
            f'# \n'
            f'# "Custom" will use RoutingObject defined\n'
            f'# in current user configuration.\n\n'
        ),
    },
}


HYSTERIA_ROUTING_HINT = (
    f'Note: If acl is empty or does not exist, {APPLICATION_NAME} '
    f'will fall back to proxy all traffic.'
)


ROUTING_HINT = {
    'Bypass Mainland China': {
        Hysteria1.name(): '',
    },
    'Bypass Iran': {
        Hysteria1.name(): '',
    },
    'Route My Traffic Through Tor': {
        Hysteria1.name(): TOR_FAQ_LABEL,
    },
    'Global': {
        Hysteria1.name(): HYSTERIA_ROUTING_HINT,
    },
    'Custom': {
        Hysteria1.name(): (
            f'Note: "Custom" will use acl and mmdb defined in current user configuration.'
        ),
    },
}


DEFAULT_USER_ROUTING = {
    XrayCore.name(): {
        'domainStrategy': 'IPIfNonMatch',
        'domainMatcher': 'hybrid',
        'rules': [
            # Proxy everything
            {
                'type': 'field',
                'port': '0-65535',
                'outboundTag': 'proxy',
            },
        ],
    },
    Hysteria1.name(): {
        'acl': '',
        'mmdb': (DATA_DIR / 'hysteria' / 'country.mmdb').as_posix(),
    },
}


USER_ROUTING_TEXT = {
    XrayCore.name(): (
        f'# Xray-core Routing rules\n'
        f'# \n'
        f'# Define your own routing rules here.\n'
        f'# \n'
        f'# Need any help? You can check those built-in\n'
        f'# routing rules shipped with {APPLICATION_NAME} first.\n'
        f'# \n'
        f'# Note: JSON does not support comments. Any\n'
        f'# lines starting with "#" will be discarded\n'
        f'# by {APPLICATION_NAME} forever.\n\n'
    )
    + ujson.dumps(
        DEFAULT_USER_ROUTING[XrayCore.name()],
        indent=2,
        ensure_ascii=False,
        escape_forward_slashes=False,
    ),
}


class ImportAssetFileAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Import Asset File...'), **kwargs)

    def triggeredCallback(self, checked):
        APP().RoutesWidget.assetViewer.show()


def questionFastReconnect(saveConfInfo):
    saveConfInfo.setWindowTitle(_('Hint'))
    saveConfInfo.setText(
        _(
            f'{APPLICATION_NAME} is currently connected.\n\n'
            f'The new configuration will take effect the next time you connect.'
        )
    )

    # Show the MessageBox and wait for user to close it
    choice = saveConfInfo.exec()

    if choice == MessageBox.ButtonRole.AcceptRole.value:
        # Reconnect
        APP().tray.ConnectAction.connectingAction(
            showProgressBar=True,
            showRoutingChangedMessage=False,
        )
    else:
        # OK. Do nothing
        pass


class SaveAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Save'), icon=bootstrapIcon('save.svg'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_S
            )
        )

        self.saveErrorBox = JSONErrorBox(icon=MessageBox.Icon.Critical)
        self.saveConfInfo = SaveConfInfo(icon=MessageBox.Icon.Information)

    def getParentIndex(self):
        routingEditor = self.parent()
        routingEditorRef = APP().RoutesWidget.editRoutingTableWidget.routingEditorRef

        for index, editor in enumerate(routingEditorRef[len(BUILTIN_ROUTING) :]):
            if id(routingEditor) == id(editor):
                # Found reference
                return index

        return -1

    def save(self, successCallback=None):
        if not self.parent().modified:
            return True

        coreList = []
        textList = []
        jsonList = []

        editorTab = self.parent().editorTab

        for index in range(editorTab.count()):
            core = editorTab.tabText(index)
            plainText = editorTab.widget(index).toPlainText()
            text = functools.reduce(
                operator.add,
                list(
                    filter(
                        # Discard any comments
                        lambda x: not x.strip().startswith('#'),
                        plainText.split('\n'),
                    )
                ),
            )

            coreList.append(core)
            textList.append(plainText)

            try:
                jsonList.append(ujson.loads(text))
            except ujson.JSONDecodeError as decodeError:
                self.saveErrorBox.decodeError = f'{core}: {decodeError}'
                self.saveErrorBox.setWindowTitle(
                    _('Error saving routing configuration')
                )
                self.saveErrorBox.setText(self.saveErrorBox.getText())

                # Show the MessageBox and wait for user to close it
                self.saveErrorBox.exec()

                return False

        # Fast save
        # Check parent(i.e. routing option) is not deleted by user.
        parentIndex = self.getParentIndex()

        if parentIndex >= 0:
            for core, json in zip(coreList, jsonList):
                APP().RoutesWidget.RoutesList[parentIndex][core] = json

            # Sync it
            RoutesStorage.sync()

            # Refresh last saved text
            self.parent().editorLastSavedText = textList
            self.parent().markAsSaved()

            if callable(successCallback):
                successCallback()

            if parentIndex == routingToIndex() - len(BUILTIN_ROUTING):
                # Activated routing modified

                if APP().tray.ConnectAction.isConnected():
                    questionFastReconnect(self.saveConfInfo)
        else:
            # Corresponding routing option has been deleted. Fake saved
            logger.info('trying to save a deleted routing. Ignore')

            self.parent().markAsSaved()

            if callable(successCallback):
                successCallback()

        return True

    def triggeredCallback(self, checked):
        self.save()


class ExitAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Exit'), **kwargs)

    def triggeredCallback(self, checked):
        self.parent().hide()


class ZoomInAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom In'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Plus
            )
        )

    def triggeredCallback(self, checked):
        for editor in self.parent().editorRef:
            editor.zoomIn()


class ZoomOutAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom Out'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Minus
            )
        )

    def triggeredCallback(self, checked):
        for editor in self.parent().editorRef:
            editor.zoomOut()


class EditRoutingAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.saveConfInfo = SaveConfInfo(icon=MessageBox.Icon.Information)

        self.RoutesList = self.parent().RoutesList

        self.routingEditorRef = self.parent().routingEditorRef
        self.routingDialogRef = self.parent().routingDialogRef

    def triggeredCallback(self, checked):
        if self.textCompare(f'Edit {XrayCore.name()} Routing Rules'):
            for index in self.parent().selectedIndex:
                self.routingEditorRef[index].show()

        if self.textCompare(f'Edit {Hysteria1.name()} Routing Rules'):
            for index in self.parent().selectedIndex:
                dialog = self.routingDialogRef[index]
                choice = dialog.exec()

                if dialog.isBuiltin:
                    # Built-in. Nothing to do
                    logger.info(
                        f'built-in routing dialog \'{BUILTIN_ROUTING[index]}\' called exec. Nothing to do'
                    )

                    continue

                assert index >= len(BUILTIN_ROUTING)

                parentIndex = index - len(BUILTIN_ROUTING)

                if choice == QDialog.DialogCode.Accepted.value:
                    ruleValue = dialog.ruleValue()
                    mmdbValue = dialog.mmdbValue()

                    self.RoutesList[parentIndex][Hysteria1.name()].update(
                        {'acl': ruleValue, 'mmdb': mmdbValue}
                    )

                    # Sync it
                    RoutesStorage.sync()

                    if parentIndex == routingToIndex() - len(BUILTIN_ROUTING):
                        # Activated routing modified

                        if APP().tray.ConnectAction.isConnected():
                            questionFastReconnect(self.saveConfInfo)
                else:
                    # Restore

                    routingObject = self.RoutesList[parentIndex][Hysteria1.name()]

                    dialog.setRuleValue(routingObject.get('acl', ''))
                    dialog.setMmdbValue(routingObject.get('mmdb', ''))


class RoutingTextBrowser(ZoomableTextBrowser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.routingEditorWidget = kwargs.get('parent')

    def wheelEvent(self, event):
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                for editor in self.routingEditorWidget.editorRef:
                    editor.zoomIn()
            if delta < 0:
                for editor in self.routingEditorWidget.editorRef:
                    editor.zoomOut()
        else:
            super().wheelEvent(event)


class RoutingPlainTextEdit(ZoomablePlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.routingEditorWidget = kwargs.get('parent')

    def wheelEvent(self, event):
        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta > 0:
                for editor in self.routingEditorWidget.editorRef:
                    editor.zoomIn()
            if delta < 0:
                for editor in self.routingEditorWidget.editorRef:
                    editor.zoomOut()
        else:
            super().wheelEvent(event)


class RoutingEditor(MainWindow):
    def __init__(self, isBuiltin, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.isBuiltin = isBuiltin
        self.title = ''

        if APP().tray is not None and APP().tray.ConnectAction.isConnected():
            self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
        else:
            self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        # MessageBox
        self.questionSaveBox = QuestionSaveBox(
            icon=MessageBox.Icon.Question, parent=self
        )

        # Modified flag
        self.modified = False
        self.modifiedMark = ' *'

        self.editorRef = []
        self.editorLastSavedText = []
        self.themeReference = []

        self.editorTab = TabWidget(parent=self)
        self.setCentralWidget(self.editorTab)

        if self.isBuiltin:
            fileMenuActions = [
                ImportAssetFileAction(parent=self),
                Seperator(),
                ExitAction(parent=self),
            ]
        else:
            fileMenuActions = [
                ImportAssetFileAction(parent=self),
                Seperator(),
                SaveAction(parent=self),
                Seperator(),
                ExitAction(parent=self),
            ]

        viewMenuActions = [
            ZoomInAction(parent=self),
            ZoomOutAction(parent=self),
        ]

        for menu in (fileMenuActions, viewMenuActions):
            for action in menu:
                if isinstance(action, Action):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

        self._fileMenu = Menu(*fileMenuActions, title=_('File'), parent=self)
        self._viewMenu = Menu(*viewMenuActions, title=_('View'), parent=self)

        self.menuBar().addMenu(self._fileMenu)
        self.menuBar().addMenu(self._viewMenu)

    def setWidthAndHeight(self):
        self.setGeometry(100, 100, 656, 856)

    def addTabWithData(self, core, text):
        if self.isBuiltin:
            editor = RoutingTextBrowser(parent=self)
            editor.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
            editor.setStyleSheet(
                DraculaTheme.getStyleSheet(
                    widgetName='QTextBrowser',
                    fontFamily=APP().customFontName,
                )
            )
        else:
            editor = RoutingPlainTextEdit(parent=self)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            editor.setStyleSheet(
                DraculaTheme.getStyleSheet(
                    widgetName='QPlainTextEdit',
                    fontFamily=APP().customFontName,
                )
            )

            @QtCore.Slot(bool)
            def handleModification(changed):
                if changed:
                    editor.document().setModified(False)
                    self.markAsModified()

            editor.modificationChanged.connect(handleModification)

        # Theme
        self.themeReference.append(DraculaTheme(editor.document()))

        editor.blockSignals(True)
        editor.setPlainText(text)
        editor.blockSignals(False)

        self.editorRef.append(editor)
        self.editorLastSavedText.append(text)
        self.editorTab.addTab(editor, _(f'{core} Routing Rules'))

    def markAsModified(self):
        # Built-in is read-only. Should not be modified
        assert not self.isBuiltin

        self.modified = True
        self.setWindowTitle(self.title + self.modifiedMark)

    def markAsSaved(self):
        # Built-in is read-only. Should not be modified
        assert not self.isBuiltin

        self.modified = False
        self.setWindowTitle(self.title)

    def questionSave(self):
        if self.modified:
            choice = self.questionSaveBox.exec()

            if choice == MessageBox.ButtonRole.AcceptRole.value:
                # Save
                # If save success, close the window.
                return self.SaveAction.save(successCallback=lambda: self.hide())

            if choice == MessageBox.ButtonRole.DestructiveRole.value:
                # Discard
                self.hide()

                # Restore last saved text
                for editor, text in zip(self.editorRef, self.editorLastSavedText):
                    editor.blockSignals(True)
                    editor.setPlainText(text)
                    editor.blockSignals(False)

                self.markAsSaved()  # Fake saved

                return True

            if choice == MessageBox.ButtonRole.RejectRole.value:
                # Cancel. Do nothing
                return False
        else:
            self.hide()

            return True

    def closeEvent(self, event):
        event.ignore()

        self.questionSave()

    def retranslate(self):
        if self.isBuiltin:
            # Built-in routing is translatable
            with StateContext(self):
                self.setWindowTitle(_(self.windowTitle()))


class RoutingDialog(Dialog):
    LINE_EDIT_FIXED_WIDTH = 500
    BUTTON_FIXED_WIDTH = 30

    def __init__(self, isBuiltin, hint='', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.isBuiltin = isBuiltin

        if APP().tray is not None and APP().tray.ConnectAction.isConnected():
            self.setWindowIcon(bootstrapIcon('rocket-takeoff-connected-dark.svg'))
        else:
            self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.ruleText = QLabel(f'{Hysteria1.name()} acl:')

        self.ruleEdit = QLineEdit()
        self.ruleEdit.setFixedWidth(RoutingDialog.LINE_EDIT_FIXED_WIDTH)

        self.ruleFile = QPushButton('...')
        self.ruleFile.setFixedWidth(RoutingDialog.BUTTON_FIXED_WIDTH)

        self.ruleHBox = QHBoxLayout()
        self.ruleHBox.addWidget(self.ruleEdit)
        self.ruleHBox.addWidget(self.ruleFile)

        self.mmdbText = QLabel(f'{Hysteria1.name()} mmdb:')

        self.mmdbEdit = QLineEdit()
        self.mmdbEdit.setFixedWidth(RoutingDialog.LINE_EDIT_FIXED_WIDTH)

        self.mmdbFile = QPushButton('...')
        self.mmdbFile.setFixedWidth(RoutingDialog.BUTTON_FIXED_WIDTH)

        self.mmdbHBox = QHBoxLayout()
        self.mmdbHBox.addWidget(self.mmdbEdit)
        self.mmdbHBox.addWidget(self.mmdbFile)

        self.ruleFile.clicked.connect(self.handleRuleFileClicked)
        self.mmdbFile.clicked.connect(self.handleMmdbFileClicked)

        if self.isBuiltin:
            self.ruleEdit.setReadOnly(True)
            self.mmdbEdit.setReadOnly(True)

        self.dialogBtns = QDialogButtonBox(QtCore.Qt.Orientation.Horizontal)

        self.dialogBtns.addButton(_('OK'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(_('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()

        if hint:
            self.hint = QLabel(hint)
            self.hint.setTextFormat(QtCore.Qt.TextFormat.RichText)
            self.hint.setTextInteractionFlags(
                QtCore.Qt.TextInteractionFlag.TextBrowserInteraction
            )
            self.hint.setOpenExternalLinks(True)

            layout.addRow(self.hint)
        else:
            self.hint = None

        layout.addRow(self.ruleText, self.ruleHBox)
        layout.addRow(self.mmdbText, self.mmdbHBox)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    @QtCore.Slot()
    def handleRuleFileClicked(self):
        filename, selectedFilter = QFileDialog.getOpenFileName(
            self.parent(), _('Import File'), filter=_('All files (*)')
        )

        if not self.isBuiltin and filename:
            self.ruleEdit.setText(filename)

    @QtCore.Slot()
    def handleMmdbFileClicked(self):
        filename, selectedFilter = QFileDialog.getOpenFileName(
            self.parent(), _('Import File'), filter=_('All files (*)')
        )

        if not self.isBuiltin and filename:
            self.mmdbEdit.setText(filename)

    def setRuleValue(self, text):
        self.ruleEdit.setText(text)

    def setMmdbValue(self, text):
        self.mmdbEdit.setText(text)

    def ruleValue(self):
        return self.ruleEdit.text()

    def mmdbValue(self):
        return self.mmdbEdit.text()

    def retranslate(self):
        with StateContext(self):
            if self.isBuiltin:
                # Built-in window title is translatable
                self.setWindowTitle(_(self.windowTitle()))

            if self.hint is not None:
                self.hint.setText(_(self.hint.text()))

            for button in self.dialogBtns.buttons():
                button.setText(_(button.text()))


class EditRoutingTableHorizontalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Horizontal, *args, **kwargs)

        self.sectionResized.connect(self.handleSectionResized)

    @QtCore.Slot(int, int, int)
    def handleSectionResized(self, index, oldSize, newSize):
        # Keys are string when loaded from json
        self.parent().sectionSizeTable[str(index)] = newSize


class EditRoutingTableVerticalHeader(HeaderView):
    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Orientation.Vertical, *args, **kwargs)


class EditRoutingTableWidget(Translatable, SupportConnectedCallback, TableWidget):
    # Might be extended in the future
    HEADER_LABEL = [
        'Remark',
        'Type',
    ]

    # Corresponds to header label
    BUILTIN_ITEM_GET_FUNC = [
        lambda row: _(BUILTIN_ROUTING[row]),
        lambda row: _('Built-in'),
    ]

    USER_ITEM_GET_FUNC = [
        lambda text: text,
        lambda text: _('User Defined'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.RoutesWidget = kwargs.get('parent')

        self.questionDeleteBox = QuestionDeleteBox(
            icon=MessageBox.Icon.Question, parent=self.parent()
        )

        # Handy reference
        self.RoutesList = self.RoutesWidget.RoutesList

        # Currently only has Xray-Core
        self.routingEditorRef = []
        # Currently only has Hysteria1
        self.routingDialogRef = []

        # Column count
        self.setColumnCount(len(EditRoutingTableWidget.HEADER_LABEL))

        # Delegate
        self.delegate = StyledItemDelegate(parent=self)
        self.setItemDelegate(self.delegate)

        # Install custom header
        self.setHorizontalHeader(EditRoutingTableHorizontalHeader(self))

        self.initTableFromData()
        self.activateItemByIndex(routingToIndex(), activate=True)

        # Horizontal header resize mode
        for index in range(self.columnCount()):
            if index < self.columnCount() - 1:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Interactive
                )
            else:
                self.horizontalHeader().setSectionResizeMode(
                    index, QHeaderView.ResizeMode.Stretch
                )

        try:
            # Restore horizontal section size
            self.sectionSizeTable = ujson.loads(APP().RoutesWidgetSectionSizeTable)

            # Fill missing value
            for column in range(self.columnCount()):
                if self.sectionSizeTable.get(str(column)) is None:
                    self.sectionSizeTable[
                        str(column)
                    ] = self.horizontalHeader().defaultSectionSize()

            # Block resize callback
            self.horizontalHeader().blockSignals(True)

            for key, value in self.sectionSizeTable.items():
                self.horizontalHeader().resizeSection(int(key), value)

            # Unblock resize callback
            self.horizontalHeader().blockSignals(False)
        except Exception:
            # Any non-exit exceptions

            # Leave keys as strings since they will be
            # loaded as string from json
            self.sectionSizeTable = {
                str(row): self.horizontalHeader().defaultSectionSize()
                for row in range(self.columnCount())
            }

        self.setHorizontalHeaderLabels(
            list(_(label) for label in EditRoutingTableWidget.HEADER_LABEL)
        )

        for column in range(self.horizontalHeader().count()):
            self.horizontalHeaderItem(column).setFont(QFont(APP().customFontName))

        # Install custom header
        self.setVerticalHeader(EditRoutingTableVerticalHeader(self))

        # Selection
        self.setSelectionColor(Color.LIGHT_BLUE)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        # No drag and drop
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setDropIndicatorShown(False)
        self.setDefaultDropAction(QtCore.Qt.DropAction.IgnoreAction)

        contextMenuActions = [
            EditRoutingAction(_(f'Edit {XrayCore.name()} Routing Rules'), parent=self),
            EditRoutingAction(_(f'Edit {Hysteria1.name()} Routing Rules'), parent=self),
        ]

        self.contextMenu = Menu(*contextMenuActions)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)

        # Signals
        self.customContextMenuRequested.connect(self.handleCustomContextMenuRequested)

    def initTableFromData(self):
        for row, routing in enumerate(BUILTIN_ROUTING):
            self.appendDataByColumn(
                lambda column: EditRoutingTableWidget.BUILTIN_ITEM_GET_FUNC[column](row)
            )

            text = self.item(row, 0).text()

            routingEditor = self.appendRoutingEditor(text, isBuiltin=True)

            for core in [XrayCore.name()]:
                routingEditor.addTabWithData(
                    core,
                    BUILTIN_ROUTING_TEXT[BUILTIN_ROUTING[row]][core],
                )

            routingDialog = self.appendRoutingDialog(
                text, hint=_(ROUTING_HINT[routing][Hysteria1.name()]), isBuiltin=True
            )

            routingDialog.ruleEdit.setText(
                BUILTIN_ROUTING_TABLE[routing][Hysteria1.name()].get('acl', '')
            )
            routingDialog.mmdbEdit.setText(
                BUILTIN_ROUTING_TABLE[routing][Hysteria1.name()].get('mmdb', '')
            )

        for row in range(
            len(BUILTIN_ROUTING),
            len(BUILTIN_ROUTING) + len(self.RoutesList),
        ):
            routesIndex = row - len(BUILTIN_ROUTING)

            remark = self.RoutesList[routesIndex]['remark']

            self.appendDataByColumn(
                lambda column: EditRoutingTableWidget.USER_ITEM_GET_FUNC[column](remark)
            )

            text = self.item(row, 0).text()

            routingEditor = self.appendRoutingEditor(text, isBuiltin=False)

            for core in [XrayCore.name()]:
                routingEditor.addTabWithData(
                    core,
                    ujson.dumps(
                        self.RoutesList[routesIndex][core],
                        indent=2,
                        ensure_ascii=False,
                        escape_forward_slashes=False,
                    ),
                )

            routingDialog = self.appendRoutingDialog(
                text, hint=_(HYSTERIA_ROUTING_HINT), isBuiltin=False
            )

            routingDialog.ruleEdit.setText(
                self.RoutesList[routesIndex][Hysteria1.name()].get('acl', '')
            )
            routingDialog.mmdbEdit.setText(
                self.RoutesList[routesIndex][Hysteria1.name()].get('mmdb', '')
            )

    @QtCore.Slot(QtCore.QPoint)
    def handleCustomContextMenuRequested(self, point):
        self.contextMenu.exec(self.mapToGlobal(point))

    def appendRoutingEditor(self, title, isBuiltin=False):
        routingEditor = RoutingEditor(isBuiltin)
        routingEditor.title = title
        routingEditor.setWindowTitle(title)

        moveToCenter(routingEditor)

        self.routingEditorRef.append(routingEditor)

        return routingEditor

    def appendRoutingDialog(self, title, hint='', isBuiltin=False):
        routingDialog = RoutingDialog(isBuiltin, hint)
        routingDialog.setWindowTitle(title)

        self.routingDialogRef.append(routingDialog)

        return routingDialog

    def deleteSelectedItem(self):
        # Builtin routing cannot be deleted
        indexes = list(filter(lambda x: x >= len(BUILTIN_ROUTING), self.selectedIndex))

        if len(indexes) == 0:
            # Nothing to do
            return

        self.questionDeleteBox.isMulti = bool(len(indexes) > 1)
        self.questionDeleteBox.possibleRemark = f'{self.item(indexes[0], 0).text()}'
        self.questionDeleteBox.setText(self.questionDeleteBox.getText())

        if self.questionDeleteBox.exec() == MessageBox.StandardButton.No.value:
            # Do not delete
            return

        try:
            index = int(APP().Routing)
        except ValueError:
            takedCurrentRouting = False
        else:
            if index + len(BUILTIN_ROUTING) in indexes:
                # Current routing will be deleted
                takedCurrentRouting = True
            else:
                takedCurrentRouting = False

        routingAction = APP().tray.RoutingAction

        for i in range(len(indexes)):
            takedRow = indexes[i] - i

            self.removeRow(takedRow)
            self.routingEditorRef.pop(takedRow)
            self.routingDialogRef.pop(takedRow)
            self.RoutesList.pop(takedRow - len(BUILTIN_ROUTING))

            # Remove entry from routing menu
            routingAction.removeAction(routingAction.menu().actions()[takedRow])

            routingIndex = routingToIndex()

            if not takedCurrentRouting and takedRow < routingIndex:
                APP().Routing = str(routingIndex - len(BUILTIN_ROUTING) - 1)

        # Sync it
        RoutesStorage.sync()

        if takedCurrentRouting:
            currentRow = self.currentIndex().row()

            self.setCurrentItem(self.item(currentRow, 0))

            # Trigger current
            routingAction.menu().actions()[currentRow].trigger()

    def appendDataByColumn(self, func):
        row = self.rowCount()

        self.insertRow(row)

        for column in range(self.columnCount()):
            item = QTableWidgetItem(func(column))

            item.setFont(QFont(APP().customFontName))
            item.setFlags(
                QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
            )

            self.setItem(row, column, item)

    def connectedCallback(self):
        self.setSelectionColor(Color.LIGHT_RED_)
        # Reactivate with possible color
        self.activateItemByIndex(routingToIndex(), activate=True)

    def disconnectedCallback(self):
        self.setSelectionColor(Color.LIGHT_BLUE)
        # Reactivate with possible color
        self.activateItemByIndex(routingToIndex(), activate=True)

    def retranslate(self):
        self.setHorizontalHeaderLabels(
            list(_(label) for label in EditRoutingTableWidget.HEADER_LABEL)
        )

        for row in range(self.rowCount()):
            if row < len(BUILTIN_ROUTING):
                for column in range(self.columnCount()):
                    item = self.item(row, column)

                    item.setText(_(item.text()))
            else:
                for column in range(self.columnCount()):
                    # Do not translate user remark
                    if column != 0:
                        item = self.item(row, column)

                        item.setText(_(item.text()))


class AddRoutingDialog(Dialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(_('Add routing'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.remarkText = QLabel(_('Enter routing remark:'))
        self.remarkEdit = QLineEdit()

        self.dialogBtns = QDialogButtonBox(QtCore.Qt.Orientation.Horizontal)

        self.dialogBtns.addButton(_('OK'), QDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(_('Cancel'), QDialogButtonBox.ButtonRole.RejectRole)
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()

        layout.addRow(self.remarkText)
        layout.addRow(self.remarkEdit)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def setWidthAndHeight(self):
        self.setGeometry(100, 100, 276, 80)

    def routingRemark(self):
        return self.remarkEdit.text()

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))

            self.remarkText.setText(_(self.remarkText.text()))

            for button in self.dialogBtns.buttons():
                button.setText(_(button.text()))

            moveToCenter(self)


class EditRoutingWidget(MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Edit Routing'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.assetViewer = AssetViewerWidget()
        self.addRoutingDialog = AddRoutingDialog()

        try:
            self.StorageObj = RoutesStorage.toObject(APP().CustomRouting)
            # Check model. Shallow copy
            self.RoutesList = self.StorageObj['model']
        except Exception:
            # Any non-exit exceptions

            self.StorageObj = RoutesStorage.init()
            # Shallow copy
            self.RoutesList = self.StorageObj['model']

            # Clear it
            RoutesStorage.clear()

        self.editRoutingTableWidget = EditRoutingTableWidget(parent=self)

        self.editorTab = TabWidget(self)
        self.editorTab.addTab(self.editRoutingTableWidget, _('Routing Rules'))

        # Buttons
        self.addButton = PushButton(_('Add'))
        self.addButton.clicked.connect(lambda: self.addRoute())
        self.deleteButton = PushButton(_('Delete'))
        self.deleteButton.clicked.connect(lambda: self.deleteSelectedItem())

        # Button Layout
        self.buttonWidget = QWidget()
        self.buttonWidgetLayout = QGridLayout(parent=self.buttonWidget)
        self.buttonWidgetLayout.addWidget(self.addButton, 0, 0)
        self.buttonWidgetLayout.addWidget(self.deleteButton, 0, 1)

        self.fakeCentralWidget = QWidget()
        self.fakeCentralWidgetLayout = QVBoxLayout(self.fakeCentralWidget)
        self.fakeCentralWidgetLayout.addWidget(self.editorTab)
        self.fakeCentralWidgetLayout.addWidget(self.buttonWidget)

        self.setCentralWidget(self.fakeCentralWidget)

    def setWidthAndHeight(self):
        try:
            self.setGeometry(
                100,
                100,
                *list(int(size) for size in APP().RoutesWidgetWindowSize.split(',')),
            )
        except Exception:
            # Any non-exit exceptions

            self.setGeometry(100, 100, 360 * GOLDEN_RATIO, 360)

    def addRoute(self):
        choice = self.addRoutingDialog.exec()

        if choice == QDialog.DialogCode.Accepted.value:
            routingRemark = self.addRoutingDialog.routingRemark()

            if routingRemark:
                self.editRoutingTableWidget.appendDataByColumn(
                    lambda column: EditRoutingTableWidget.USER_ITEM_GET_FUNC[column](
                        routingRemark
                    )
                )

                routingEditor = self.editRoutingTableWidget.appendRoutingEditor(
                    routingRemark, isBuiltin=False
                )

                for core in [XrayCore.name()]:
                    routingEditor.addTabWithData(
                        core,
                        USER_ROUTING_TEXT[core],
                    )

                routingDialog = self.editRoutingTableWidget.appendRoutingDialog(
                    routingRemark, hint=_(HYSTERIA_ROUTING_HINT), isBuiltin=False
                )

                # Set default value
                routingDialog.ruleEdit.setText(
                    DEFAULT_USER_ROUTING[Hysteria1.name()].get('acl', '')
                )
                routingDialog.mmdbEdit.setText(
                    DEFAULT_USER_ROUTING[Hysteria1.name()].get('mmdb', '')
                )

                self.RoutesList.append(
                    {'remark': routingRemark, **DEFAULT_USER_ROUTING}
                )

                # Sync it
                RoutesStorage.sync()

                routingAction = APP().tray.RoutingAction
                # Add entry in routing menu
                routingAction.addAction(
                    RoutingChildAction(routingRemark, checkable=True, checked=False)
                )
        else:
            # Do nothing
            pass

    def deleteSelectedItem(self):
        self.editRoutingTableWidget.deleteSelectedItem()

    def activateItemByIndex(self, index, activate=True):
        self.editRoutingTableWidget.activateItemByIndex(index, activate)

    def syncSettings(self):
        APP().RoutesWidgetWindowSize = (
            f'{self.geometry().width()},{self.geometry().height()}'
        )

        APP().RoutesWidgetSectionSizeTable = ujson.dumps(
            self.editRoutingTableWidget.sectionSizeTable,
            ensure_ascii=False,
            escape_forward_slashes=False,
        )

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.deleteSelectedItem()
        else:
            super().keyPressEvent(event)
