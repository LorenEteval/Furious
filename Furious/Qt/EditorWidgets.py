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

"""Provide Qt support for GUI editor xxx."""

from __future__ import annotations

from Furious.Frozenlib import *
from Furious.Interface import *
from Furious.Models import ConfigFactory, ServerProfile
from Furious.Qt.DynamicTranslate import gettext as _
from Furious.Qt.QtWidgets import *

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


class GuiEditorItemTextInput(EditorWidgetBinding):
    """Represent GUI editor item text input."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemTextInput."""
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        if translatable:
            title = _(title)

        self._title = AppQLabel(title, translatable=translatable, parent=parent)
        self._input = QLineEdit(parent=parent)

    def text(self) -> str:
        """Return the text value."""
        return self._input.text()

    def setText(self, text: str):
        """Set text."""
        self._input.setText(text)

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return self._title, self._input


class GuiEditorItemTextSpinBox(EditorWidgetBinding):
    """Represent GUI editor item text spin box."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemTextSpinBox."""
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        if translatable:
            title = _(title)

        self._title = AppQLabel(title, translatable=translatable, parent=parent)
        self._input = AppQSpinBox(parent=parent)

    def value(self) -> int:
        """Return the value value."""
        return self._input.value()

    def setValue(self, value: int):
        """Set value."""
        self._input.setValue(value)

    def setRange(self, minRange: int, maxRange: int):
        """Set range."""
        self._input.setRange(minRange, maxRange)

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return self._title, self._input


class GuiEditorItemTextComboBox(EditorWidgetBinding):
    """Represent GUI editor item text combo box."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemTextComboBox."""
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        if translatable:
            title = _(title)

        self._title = AppQLabel(title, translatable=translatable, parent=parent)
        self._input = AppQComboBox(parent=parent, translatable=False)

    def text(self) -> str:
        """Return the text value."""
        return self._input.currentText()

    def setText(self, text: str):
        """Set text."""
        self._input.setCurrentText(text)

    def addItems(self, texts: Sequence[str]):
        """Add items."""
        self._input.addItems(texts)

    def connectActivated(self, func: Callable):
        """Connect activated."""
        self._input.activated.connect(func)

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return self._title, self._input


class GuiEditorItemTextCheckBox(EditorWidgetBinding):
    """Represent GUI editor item text check box."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemTextCheckBox."""
        title = kwargs.pop('title', '')
        translatable = kwargs.pop('translatable', True)
        parent = kwargs.pop('parent', None)

        super().__init__(*args, **kwargs)

        self._input = AppQCheckBox(_(title), translatable=translatable, parent=parent)

    def isChecked(self) -> bool:
        """Return whether checked."""
        return self._input.isChecked()

    def setChecked(self, checked: bool):
        """Set checked."""
        self._input.setChecked(checked)

    def widgets(self):
        """Return the widgets owned by this editor item."""
        return (self._input,)


class GuiEditorItemBasicRemark(GuiEditorItemTextInput):
    """Represent GUI editor item basic remark."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemBasicRemark."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ServerProfile) -> bool:
        """Apply the current editor value to the configuration."""
        oldRemark = config.metadata.displayName
        newRemark = self.text()

        if newRemark != oldRemark:
            config.metadata.displayName = newRemark

            # Value modified, but not return as a modified behavior
            return False
        else:
            # Not modified
            return False

    def factoryToInput(self, config: ServerProfile):
        """Load the configuration value into the editor."""
        self.setText(config.metadata.displayName)


class GuiEditorItemProxyHttp(GuiEditorItemTextInput):
    """Represent GUI editor item proxy HTTP."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemProxyHttp."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldHttp = config.httpProxy()
        newHttp = self.text()

        if newHttp == '':
            if oldHttp == '':
                return False
            else:
                config.setHttpProxy(newHttp)

                return True
        else:
            if isinstance(oldHttp, str):
                if newHttp != oldHttp:
                    config.setHttpProxy(newHttp)

                    return True
                else:
                    return False
            else:
                config.setHttpProxy(newHttp)

                return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.httpProxy())
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiEditorItemProxySocks(GuiEditorItemTextInput):
    """Represent GUI editor item proxy SOCKS."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorItemProxySocks."""
        super().__init__(*args, **kwargs)

    def inputToFactory(self, config: ConfigFactory) -> bool:
        """Apply the current editor value to the configuration."""
        oldSocks = config.socksProxy()
        newSocks = self.text()

        if newSocks == '':
            if oldSocks == '':
                return False
            else:
                config.setSocksProxy(newSocks)

                return True
        else:
            if isinstance(oldSocks, str):
                if newSocks != oldSocks:
                    config.setSocksProxy(newSocks)

                    return True
                else:
                    return False
            else:
                config.setSocksProxy(newSocks)

                return True

    def factoryToInput(self, config: ConfigFactory):
        """Load the configuration value into the editor."""
        try:
            self.setText(config.socksProxy())
        except Exception:
            # Any non-exit exceptions

            self.setText('')


class GuiEditorWidget(EditorBinding):
    """Provide the GUI editor widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorWidget."""
        super().__init__(*args, **kwargs)

        self._containers = self.containerSequence()

    def containerSequence(self) -> Sequence[EditorWidgetBinding]:
        """Return the editor item containers in display order."""
        raise NotImplementedError

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        modified = False

        for container in self._containers:
            try:
                modified |= container.inputToFactory(config)
            except Exception:
                # Any non-exit exceptions

                modified |= False

        return modified

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        for container in self._containers:
            try:
                container.factoryToInput(config)
            except Exception:
                # Any non-exit exceptions

                pass


class GuiEditorWidgetQWidget(GuiEditorWidget, QWidget):
    """Provide the GUI editor  Qt widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorWidgetQWidget."""
        super().__init__(*args, **kwargs)

        self.setupLayout()

    def setupLayout(self):
        """Set up layout."""
        layout = QFormLayout()
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for container in self._containers:
            layout.addRow(*container.widgets())

        self.setLayout(layout)


class GuiEditorWidgetQGroupBox(GuiEditorWidget, AppQGroupBox):
    """Group the GUI editor widget q editor controls."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorWidgetQGroupBox."""
        super().__init__(*args, **kwargs)

        page = QWidget()
        page.setLayout(self.setupPageLayout())

        # Align
        self._widget = QStackedWidget()
        self._widget.addWidget(page)

        vboxLayout = QVBoxLayout()
        vboxLayout.addWidget(self._widget)

        self.setLayout(vboxLayout)

    def setupPageLayout(self):
        """Set up page layout."""
        layout = QFormLayout()
        layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for container in self._containers:
            layout.addRow(*container.widgets())

        return layout


class GuiEditorWidgetQDialog(EditorBinding, AppQTransientDialog):
    """Present the GUI editor widget Qt dialog."""

    def __init__(self, *args, **kwargs):
        """Initialize the GuiEditorWidgetQDialog."""
        tabText, tabTranslatable, style = (
            kwargs.pop('tabText', ''),
            kwargs.pop('tabTranslatable', False),
            kwargs.pop('style', 'grid'),
        )
        self._groupBoxes = None

        super().__init__(*args, **kwargs)

        dialogHeight = 770

        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setFixedSize(int(dialogHeight * GOLDEN_RATIO), int(dialogHeight))

        self.tabCentralWidget = QWidget()
        self.tabCentralWidgetLayout = QGridLayout(self.tabCentralWidget)

        self.setGroupBoxStyle(style)

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
        """Return this dialog's configuration group boxes."""
        if self._groupBoxes is None:
            self._groupBoxes = tuple(self.createGroupBoxSequence())

        return self._groupBoxes

    def createGroupBoxSequence(self) -> Sequence[GuiEditorWidgetQGroupBox]:
        """Create the configuration group boxes in display order."""
        raise NotImplementedError

    def setGroupBoxStyle(self, style: str):
        """Set group box style."""
        if style == 'grid':
            for index, groupBox in enumerate(self.groupBoxSequence()):
                self.tabCentralWidgetLayout.addWidget(groupBox, index // 2, index % 2)
        elif style == 'landscape':
            for index, groupBox in enumerate(self.groupBoxSequence()):
                self.tabCentralWidgetLayout.addWidget(groupBox, 0, index)
        elif style == 'portrait':
            for index, groupBox in enumerate(self.groupBoxSequence()):
                self.tabCentralWidgetLayout.addWidget(groupBox, index, 0)

    def setTabText(self, text: str):
        """Set tab text."""
        self.tabWidget.setTabText(0, text)

    def closeEvent(self, event):
        """Handle closure of the GUI editor widget Qt dialog."""
        # Preserve QDialog's rejection/finished lifecycle for a title-bar close.
        # Server-editor callbacks disconnect themselves from the rejected signal.
        super().closeEvent(event)

    def inputToFactory(self, config: dict) -> bool:
        """Apply the current editor value to the configuration."""
        modified = False

        for groupBox in self.groupBoxSequence():
            modified |= groupBox.inputToFactory(config)

        return modified

    def factoryToInput(self, config: dict):
        """Load the configuration value into the editor."""
        for groupBox in self.groupBoxSequence():
            groupBox.factoryToInput(config)
