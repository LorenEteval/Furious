# Copyright (C) 2024  Loren Eteval <loren.eteval@proton.me>
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

from Furious.PyFramework import *
from Furious.QtFramework import *
from Furious.QtFramework import gettext as _
from Furious.Utility import *
from Furious.Library import *
from Furious.Widget.IndentSpinBox import *

from PySide6 import QtCore
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import functools

__all__ = ['TextEditorWindow']

registerAppSettings('ServerWidgetPointSize')

needTrans = functools.partial(needTransFn, source=__name__)

needTrans(
    'Save Changes',
    'The content has been modified. Save changes?',
    'Save',
    'Cancel',
    'Discard',
)


class QuestionSaveMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Save Changes'))
        self.setText(_('The content has been modified. Save changes?'))

        self.button0 = self.addButton(_('Save'), AppQMessageBox.ButtonRole.AcceptRole)
        self.button1 = self.addButton(_('Cancel'), AppQMessageBox.ButtonRole.RejectRole)
        self.button2 = self.addButton(
            _('Discard'), AppQMessageBox.ButtonRole.DestructiveRole
        )

        self.setDefaultButton(self.button0)


needTrans('Please check if the configuration is in valid JSON format')


class JSONDecodeErrorMBox(AppQMessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.error = ''

    def customText(self):
        return (
            _('Please check if the configuration is in valid JSON format')
            + f'\n\n{self.error}'
        )

    def retranslate(self):
        self.setWindowTitle(_(self.windowTitle()))
        self.setText(self.customText())

        # Ignore informative text, buttons

        self.moveToCenter()


needTrans(
    'Save',
    'Save As...',
    'Exit',
    'File',
    'Undo',
    'Redo',
    'Cut',
    'Copy',
    'Paste',
    'Select All',
    'Indent...',
    'Edit',
    'Zoom In',
    'Zoom Out',
    'View',
    'Error saving configuration',
    'Save File',
    'Text files (*.json);;All files (*)',
    'Error Saving File',
    'Invalid server configuration',
    'Error setting indent',
)


class TextEditorWindow(AppQMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.customWindowTitle = ''
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setFixedSize(450, int(450 * GOLDEN_RATIO))

        # Current editing index
        self.currentIndex = -1

        self.modified = False
        self.modifiedMark = ' *'

        self.lineColumnLabel = QLabel('1:1 0')
        self.statusBar().addPermanentWidget(self.lineColumnLabel)

        def modificationCallback():
            self.markAsModified()

        def cursorChangedCallback(cursor: QTextCursor):
            self.lineColumnLabel.setText(
                f'{cursor.blockNumber() + 1}:{cursor.columnNumber() + 1} {cursor.position()}'
            )

        self.jsonEditor = DraculaJSONTextEditor(
            fontFamily=APP().customFontName,
            pointSizeSettingsName='ServerWidgetPointSize',
        )
        self.jsonEditor.setLineWrapMode(DraculaJSONTextEditor.LineWrapMode.NoWrap)
        self.jsonEditor.registerModificationChangedCb(modificationCallback)
        self.jsonEditor.registerCursorPositionChangedCb(cursorChangedCallback)

        self.setCentralWidget(self.jsonEditor)

        self.fileMenu = AppQMenu(
            AppQAction(
                _('Save'),
                icon=bootstrapIcon('save.svg'),
                callback=lambda: self.save(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_S,
                ),
            ),
            AppQAction(
                _('Save As...'),
                callback=lambda: self.saveAsFile(),
            ),
            AppQSeperator(),
            AppQAction(
                _('Exit'),
                callback=lambda: self.questionSave(),
            ),
            title=_('File'),
            parent=self.menuBar(),
        )

        self.editMenu = AppQMenu(
            AppQAction(
                _('Undo'),
                icon=bootstrapIcon('arrow-return-left.svg'),
                callback=lambda: self.jsonEditor.undo(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Z,
                ),
            ),
            AppQAction(
                _('Redo'),
                icon=bootstrapIcon('arrow-return-right.svg'),
                callback=lambda: self.jsonEditor.redo(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier
                    | QtCore.Qt.KeyboardModifier.ShiftModifier,
                    QtCore.Qt.Key.Key_Z,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Cut'),
                icon=bootstrapIcon('scissors.svg'),
                callback=lambda: self.jsonEditor.cut(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_X,
                ),
            ),
            AppQAction(
                _('Copy'),
                icon=bootstrapIcon('files.svg'),
                callback=lambda: self.jsonEditor.copy(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_C,
                ),
            ),
            AppQAction(
                _('Paste'),
                callback=lambda: self.jsonEditor.paste(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_V,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Select All'),
                callback=lambda: self.jsonEditor.selectAll(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_A,
                ),
            ),
            AppQSeperator(),
            AppQAction(
                _('Indent...'),
                callback=lambda: self.setIndent(),
            ),
            title=_('Edit'),
            parent=self.menuBar(),
        )

        self.viewMenu = AppQMenu(
            AppQAction(
                _('Zoom In'),
                callback=lambda: self.jsonEditor.zoomIn(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Plus,
                ),
            ),
            AppQAction(
                _('Zoom Out'),
                callback=lambda: self.jsonEditor.zoomOut(),
                shortcut=QtCore.QKeyCombination(
                    QtCore.Qt.KeyboardModifier.ControlModifier,
                    QtCore.Qt.Key.Key_Minus,
                ),
            ),
            title=_('View'),
            parent=self.menuBar(),
        )

        self.menuBar().addMenu(self.fileMenu)
        self.menuBar().addMenu(self.editMenu)
        self.menuBar().addMenu(self.viewMenu)

    def markAsModified(self):
        self.modified = True
        self.setWindowTitle(self.customWindowTitle + self.modifiedMark)

    def markAsSaved(self):
        self.modified = False
        self.setWindowTitle(self.customWindowTitle)

    def questionSave(self):
        if self.modified:

            def handleResultCode(code):
                if code == PySide6LegacyEnumValueWrapper(
                    AppQMessageBox.ButtonRole.AcceptRole
                ):
                    if self.save():
                        self.hide()
                if code == PySide6LegacyEnumValueWrapper(
                    AppQMessageBox.ButtonRole.DestructiveRole
                ):
                    self.markAsSaved()
                    self.hide()
                if code == PySide6LegacyEnumValueWrapper(
                    AppQMessageBox.ButtonRole.RejectRole
                ):
                    # Cancel. Do nothing
                    pass

            mbox = QuestionSaveMBox(icon=AppQMessageBox.Icon.Question, parent=self)
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            mbox.finished.connect(functools.partial(handleResultCode))

            # dummy ref
            setattr(self, '_questionSaveMBox', mbox)

            # Show the MessageBox asynchronously
            mbox.open()
        else:
            self.hide()

    def setPlainText(self, text: str, blockSignals: bool):
        if blockSignals:
            with QBlockSignals(self.jsonEditor):
                self.jsonEditor.setPlainText(text)
        else:
            self.jsonEditor.setPlainText(text)

    def save(self) -> bool:
        index = self.currentIndex

        if index < 0:
            # Should not reach here. Do nothing
            self.markAsSaved()

            return True

        plain = self.jsonEditor.toPlainText()

        try:
            jsonObject = JSONEncoder.decode(plain)
        except Exception as ex:
            # Any non-exit exceptions

            mbox = JSONDecodeErrorMBox(icon=AppQMessageBox.Icon.Critical, parent=self)
            mbox.error = str(ex)
            mbox.setWindowTitle(_('Error saving configuration'))
            mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            mbox.setText(mbox.customText())

            # Show the MessageBox asynchronously
            mbox.open()

            return False
        else:
            old = AS_UserServers()[index]
            new = constructFromDict(jsonObject, **old.kwargs)

            FastItemDeletionSearch.moveToTrash(old)

            AS_UserServers()[index] = new

            try:
                APP().mainWindow.flushRow(index, new)
            except Exception:
                # Any non-exit exceptions

                pass

            if index == AS_UserActivatedItemIndex():
                showNewChangesNextTimeMBox(parent=self)

            self.markAsSaved()

            return True

    def saveAsFile(self):
        filename, selectedFilter = QFileDialog.getSaveFileName(
            None, _('Save File'), filter=_('Text files (*.json);;All files (*)')
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.write(self.jsonEditor.toPlainText())
            except Exception as ex:
                # Any non-exit exceptions

                mbox = AppQMessageBox(icon=AppQMessageBox.Icon.Critical, parent=self)
                mbox.setWindowTitle(_('Error Saving File'))
                mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                mbox.setText(_('Invalid server configuration'))
                mbox.setInformativeText(str(ex))

                # Show the MessageBox asynchronously
                mbox.open()

    def setIndent(self):
        def handleResultCode(_indentSpinBox, code):
            if code == PySide6LegacyEnumValueWrapper(AppQDialog.DialogCode.Accepted):
                plain = self.jsonEditor.toPlainText()

                try:
                    jsonObject = JSONEncoder.decode(plain)
                except Exception as ex:
                    # Any non-exit exceptions

                    mbox = JSONDecodeErrorMBox(
                        icon=AppQMessageBox.Icon.Critical, parent=self
                    )
                    mbox.error = str(ex)
                    mbox.setWindowTitle(_('Error setting indent'))
                    mbox.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                    mbox.setText(mbox.customText())

                    # Show the MessageBox asynchronously
                    mbox.open()
                else:
                    text = JSONEncoder.encode(jsonObject, indent=_indentSpinBox.value())

                    self.setPlainText(text, False)
            else:
                # Do nothing
                pass

        indentSpinBox = IndentSpinBox(parent=self)
        indentSpinBox.finished.connect(
            functools.partial(handleResultCode, indentSpinBox)
        )

        # dummy ref
        setattr(self, '_IndentSpinBox', indentSpinBox)

        # Show the MessageBox asynchronously
        indentSpinBox.open()

    def showTabAndSpaces(self):
        textOption = QTextOption()
        textOption.setFlags(QTextOption.Flag.ShowTabsAndSpaces)

        self.jsonEditor.document().setDefaultTextOption(textOption)
        # Reset. Set
        self.jsonEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.jsonEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def hideTabAndSpaces(self):
        textOption = QTextOption()

        self.jsonEditor.document().setDefaultTextOption(textOption)
        # Reset. Set
        self.jsonEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.jsonEditor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def closeEvent(self, event: QtCore.QEvent):
        event.ignore()

        self.questionSave()

    def retranslate(self):
        # Do nothing
        pass
