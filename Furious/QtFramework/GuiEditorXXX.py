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

from Furious.Interface import *
from Furious.QtFramework.DynamicTranslate import gettext as _, needTransFn
from Furious.QtFramework.QtWidgets import *
from Furious.Utility import *

from PySide6 import QtCore
from PySide6.QtWidgets import *

from typing import Callable, Sequence

__all__ = [
    'GuiEditorItemTextInput',
    'GuiEditorItemTextSpinBox',
    'GuiEditorItemTextComboBox',
    'GuiEditorItemTextCheckBox',
    'GuiEditorItemBasicRemark',
    'GuiEditorItemProxyHttp',
    'GuiEditorItemProxySocks',
    'GuiEditorWidgetQWidget',
    'GuiEditorWidgetQGroupBox',
    'GuiEditorWidgetQDialog',
]

needTrans = functools.partial(needTransFn, source=__name__)


class GuiEditorItemTextInput(GuiEditorItemWidgetContainer):
    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        self._title = AppQLabel(_(title), translatable=translatable, parent=parent)
        self._input = QLineEdit(parent=parent)

    def text(self) -> str:
        return self._input.text()

    def setText(self, text: str):
        self._input.setText(text)

    def widgets(self):
        return self._title, self._input


class GuiEditorItemTextSpinBox(GuiEditorItemWidgetContainer):
    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        self._title = AppQLabel(_(title), translatable=translatable, parent=parent)
        self._input = QSpinBox(parent=parent)

    def value(self) -> int:
        return self._input.value()

    def setValue(self, value: int):
        self._input.setValue(value)

    def setRange(self, minRange: int, maxRange: int):
        self._input.setRange(minRange, maxRange)

    def widgets(self):
        return self._title, self._input


class GuiEditorItemTextComboBox(GuiEditorItemWidgetContainer):
    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        self._title = AppQLabel(_(title), translatable=translatable, parent=parent)
        self._input = QComboBox(parent=parent)

    def text(self) -> str:
        return self._input.currentText()

    def setText(self, text: str):
        self._input.setCurrentText(text)

    def addItems(self, texts: Sequence[str]):
        self._input.addItems(texts)

    def connectActivated(self, func: Callable):
        self._input.activated.connect(func)

    def widgets(self):
        return self._title, self._input


class GuiEditorItemTextCheckBox(GuiEditorItemWidgetContainer):
    def __init__(self, *args, **kwargs):
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        self._input = AppQCheckBox(_(title), translatable=translatable, parent=parent)

    def isChecked(self) -> bool:
        return self._input.isChecked()

    def setChecked(self, checked: bool):
        self._input.setChecked(checked)

    def widgets(self):
        return (self._input,)


class GuiEditorItemBasicRemark(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        oldRemark = config.getExtras('remark')
        newRemark = self.text()

        if newRemark != oldRemark:
            config.setExtras('remark', newRemark)

            # Value modified, but not return as a modified behavior
            return False
        else:
            # Not modified
            return False

    def factoryToInput(self, config: ConfigurationFactory):
        self.setText(config.getExtras('remark'))


class GuiEditorItemProxyHttp(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        oldHttp = config.httpProxyEndpoint()
        newHttp = self.text()

        if newHttp == '':
            if oldHttp == '':
                return False
            else:
                config.setHttpProxyEndpoint(newHttp)

                return True
        else:
            if isinstance(oldHttp, str):
                if newHttp != oldHttp:
                    config.setHttpProxyEndpoint(newHttp)

                    return True
                else:
                    return False
            else:
                config.setHttpProxyEndpoint(newHttp)

                return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.httpProxyEndpoint())
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiEditorItemProxySocks(GuiEditorItemTextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        oldSocks = config.socksProxyEndpoint()
        newSocks = self.text()

        if newSocks == '':
            if oldSocks == '':
                return False
            else:
                config.setSocksProxyEndpoint(newSocks)

                return True
        else:
            if isinstance(oldSocks, str):
                if newSocks != oldSocks:
                    config.setSocksProxyEndpoint(newSocks)

                    return True
                else:
                    return False
            else:
                config.setSocksProxyEndpoint(newSocks)

                return True

    def factoryToInput(self, config: ConfigurationFactory):
        try:
            self.setText(config.socksProxyEndpoint())
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiEditorWidget(GuiEditorItemFactory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._containers = self.containerSequence()

    def containerSequence(self) -> Sequence[GuiEditorItemWidgetContainer]:
        raise NotImplementedError

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        modified = False

        for container in self._containers:
            try:
                modified |= container.inputToFactory(config)
            except Exception:
                # Any non-exit exceptions

                modified |= False

        return modified

    def factoryToInput(self, config: ConfigurationFactory):
        for container in self._containers:
            try:
                container.factoryToInput(config)
            except Exception:
                # Any non-exit exceptions

                pass


class GuiEditorWidgetQWidget(GuiEditorWidget, QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QFormLayout()
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for container in self._containers:
            layout.addRow(*container.widgets())

        self.setLayout(layout)


class GuiEditorWidgetQGroupBox(GuiEditorWidget, AppQGroupBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        formLayout = QFormLayout()
        formLayout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        formLayout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        for container in self._containers:
            formLayout.addRow(*container.widgets())

        page = QWidget()
        page.setLayout(formLayout)

        # Align
        self._widget = QStackedWidget()
        self._widget.addWidget(page)

        vboxLayout = QVBoxLayout()
        vboxLayout.addWidget(self._widget)

        self.setLayout(vboxLayout)

        # layout = QFormLayout()
        #
        # for container in self._containers:
        #     layout.addRow(*container.widgets())
        #
        # self.setLayout(layout)


needTrans('Cancel')


class GuiEditorWidgetQDialog(GuiEditorItemFactory, AppQDialog):
    def __init__(self, *args, **kwargs):
        tabText = kwargs.pop('tabText', '')
        tabTranslatable = kwargs.pop('tabTranslatable', False)

        super().__init__(*args, **kwargs)

        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setFixedSize(
            int(450 * GOLDEN_RATIO * GOLDEN_RATIO), int(450 * GOLDEN_RATIO)
        )

        self.tabCentralWidget = QWidget()
        self.tabCentralWidgetLayout = QGridLayout(self.tabCentralWidget)

        self.groupBoxes = self.groupBoxSequence()

        for index, groupBox in enumerate(self.groupBoxes):
            self.tabCentralWidgetLayout.addWidget(groupBox, index // 2, index % 2)

        self.tabCentralWidget.setLayout(self.tabCentralWidgetLayout)

        self.tabWidget = AppQTabWidget(translatable=tabTranslatable)
        self.tabWidget.addTab(self.tabCentralWidget, tabText)

        self.dialogBtns = AppQDialogButtonBox(QtCore.Qt.Orientation.Horizontal)
        self.dialogBtns.addButton(_('OK'), AppQDialogButtonBox.ButtonRole.AcceptRole)
        self.dialogBtns.addButton(
            _('Cancel'), AppQDialogButtonBox.ButtonRole.RejectRole
        )
        self.dialogBtns.accepted.connect(self.accept)
        self.dialogBtns.rejected.connect(self.reject)

        layout = QFormLayout()
        layout.addRow(self.tabWidget)
        layout.addRow(self.dialogBtns)
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

    def groupBoxSequence(self) -> Sequence[GuiEditorWidgetQGroupBox]:
        raise NotImplementedError

    def setTabText(self, text: str):
        self.tabWidget.setTabText(0, text)

    def closeEvent(self, event):
        self.accepted.disconnect()
        self.rejected.disconnect()

    def inputToFactory(self, config: ConfigurationFactory) -> bool:
        modified = False

        for groupBox in self.groupBoxes:
            modified |= groupBox.inputToFactory(config)

        return modified

    def factoryToInput(self, config: ConfigurationFactory):
        for groupBox in self.groupBoxes:
            groupBox.factoryToInput(config)
