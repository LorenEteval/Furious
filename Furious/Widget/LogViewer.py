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

from Furious.Gui.Action import Action, Seperator
from Furious.Widget.Widget import (
    MainWindow,
    Menu,
    MessageBox,
    TabWidget,
    ZoomableTextBrowser,
)
from Furious.Utility.Constants import APP, APPLICATION_NAME, LogType
from Furious.Utility.Utility import (
    StateContext,
    SupportConnectedCallback,
    bootstrapIcon,
)
from Furious.Utility.Translator import Translatable, gettext as _
from Furious.Utility.Theme import DraculaTheme

from PySide6 import QtCore
from PySide6.QtWidgets import QFileDialog, QTextBrowser, QVBoxLayout, QWidget

import logging

logger = logging.getLogger(__name__)


class SaveErrorBox(MessageBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.saveError = ''

    def getText(self):
        if self.saveError:
            return _('Unable to save log.') + f'\n\n{self.saveError}'
        else:
            return _('Unable to save log.')

    def retranslate(self):
        with StateContext(self):
            self.setWindowTitle(_(self.windowTitle()))
            self.setText(self.getText())

            # Ignore informative text, buttons

            self.moveToCenter()


class SaveAsFileAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Save As...'), **kwargs)

        self.saveErrorBox = SaveErrorBox(
            icon=MessageBox.Icon.Critical, parent=self.parent()
        )

    def triggeredCallback(self, checked):
        filename, selectedFilter = QFileDialog.getSaveFileName(
            self.parent(), _('Save File'), filter=_('Text files (*.txt);;All files (*)')
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.write(self.parent().currentTextBrowser().toPlainText())
            except Exception as ex:
                # Any non-exit exceptions

                self.saveErrorBox.saveError = str(ex)
                self.saveErrorBox.setWindowTitle(_('Error saving log'))
                self.saveErrorBox.setText(self.saveErrorBox.getText())

                # Show the MessageBox and wait for user to close it
                self.saveErrorBox.exec()


class ExitAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Exit'), **kwargs)

    def triggeredCallback(self, checked):
        self.parent().syncSettings()
        self.parent().hide()


class CopyAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Copy'), icon=bootstrapIcon('files.svg'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_C,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().currentTextBrowser().copy()


class SelectAllAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Select All'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier,
                QtCore.Qt.Key.Key_A,
            )
        )

    def triggeredCallback(self, checked):
        self.parent().currentTextBrowser().selectAll()


class ZoomInAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom In'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Plus
            )
        )

    def triggeredCallback(self, checked):
        self.parent().currentTextBrowser().zoomIn()


class ZoomOutAction(Action):
    def __init__(self, **kwargs):
        super().__init__(_('Zoom Out'), **kwargs)

        self.setShortcut(
            QtCore.QKeyCombination(
                QtCore.Qt.KeyboardModifier.ControlModifier, QtCore.Qt.Key.Key_Minus
            )
        )

    def triggeredCallback(self, checked):
        self.parent().currentTextBrowser().zoomOut()


class AppLogViewerWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.textBrowser = ZoomableTextBrowser(parent=self)
        self.textBrowser.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
        self.textBrowser.setStyleSheet(
            DraculaTheme.getStyleSheet(
                widgetName='QTextBrowser',
                fontFamily=APP().customFontName,
            )
        )

        self.restorePointSize()

        self.widgetLayout = QVBoxLayout()
        self.widgetLayout.addWidget(self.textBrowser)

        self.setLayout(self.widgetLayout)

    def pointSizeSetting(self):
        return f'{self.__class__.__name__}PointSize'

    def restorePointSize(self):
        try:
            # Restore point size
            font = self.textBrowser.font()
            font.setPointSize(int(getattr(APP(), self.pointSizeSetting())))

            self.textBrowser.setFont(font)
        except Exception:
            # Any non-exit exceptions

            pass

    def syncSettings(self):
        setattr(
            APP(), self.pointSizeSetting(), str(self.textBrowser.font().pointSize())
        )


class CoreLogViewerWidget(AppLogViewerWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class TorLogViewerWidget(AppLogViewerWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class LogViewerWidget(MainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setWindowTitle(_('Log Viewer'))
        self.setWindowIcon(bootstrapIcon('rocket-takeoff-window.svg'))

        self.coreLogViewerWidget = CoreLogViewerWidget()
        self.appLogViewerWidget = AppLogViewerWidget()
        self.torLogViewerWidget = TorLogViewerWidget()

        self.tabWidget = TabWidget()
        self.tabWidget.addTab(self.coreLogViewerWidget, _('Core Log'))
        self.tabWidget.addTab(self.appLogViewerWidget, _(f'{APPLICATION_NAME} Log'))
        self.tabWidget.addTab(self.torLogViewerWidget, _('Tor Log'))

        self.textBrowserMap = {
            LogType.Core: self.coreLogViewerWidget.textBrowser,
            LogType.App: self.appLogViewerWidget.textBrowser,
            LogType.Tor: self.torLogViewerWidget.textBrowser,
        }

        self.setCentralWidget(self.tabWidget)

        fileMenuActions = [
            SaveAsFileAction(parent=self),
            Seperator(),
            ExitAction(parent=self),
        ]

        editMenuActions = [
            CopyAction(parent=self),
            Seperator(),
            SelectAllAction(parent=self),
        ]

        viewMenuActions = [
            ZoomInAction(parent=self),
            ZoomOutAction(parent=self),
        ]

        for menu in (fileMenuActions, editMenuActions, viewMenuActions):
            for action in menu:
                if isinstance(action, Action):
                    if hasattr(self, f'{action}'):
                        logger.warning(f'{self} already has action {action}')

                    setattr(self, f'{action}', action)

        self._fileMenu = Menu(*fileMenuActions, title=_('File'), parent=self)
        self._editMenu = Menu(*editMenuActions, title=_('Edit'), parent=self)
        self._viewMenu = Menu(*viewMenuActions, title=_('View'), parent=self)

        self.menuBar().addMenu(self._fileMenu)
        self.menuBar().addMenu(self._editMenu)
        self.menuBar().addMenu(self._viewMenu)

    def currentTextBrowser(self):
        return self.tabWidget.currentWidget().textBrowser

    def textBrowser(self, logType):
        return self.textBrowserMap[logType]

    def log(self, logType):
        return self.textBrowser(logType).toPlainText()

    def appendLog(self, logType, line):
        textBrowser = self.textBrowser(logType)

        hScrollBar = textBrowser.horizontalScrollBar()
        vScrollBar = textBrowser.verticalScrollBar()
        scrollEnds = vScrollBar.maximum() - vScrollBar.value() <= 10

        if line.endswith('\n'):
            textBrowser.insertPlainText(line)
        else:
            textBrowser.append(line)

        APP().processEvents()

        if scrollEnds:
            vScrollBar.setValue(vScrollBar.maximum())  # Scrolls to the bottom
            hScrollBar.setValue(0)  # scroll to the left

    def clear(self, logType):
        self.textBrowser(logType).clear()

    def syncSettings(self):
        for index in range(self.tabWidget.count()):
            self.tabWidget.widget(index).syncSettings()
