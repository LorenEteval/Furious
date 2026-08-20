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

"""Expose reusable Qt helpers and application-aware widgets."""

from __future__ import annotations

from .AppStyleSheet import AppStyleSheet
from .DynamicTheme import AppHue
from .DynamicTranslate import (
    ABBR_TO_LANGUAGE,
    LANGUAGE_TO_ABBR,
    SUPPORTED_LANGUAGE,
    gettext,
)
from .EditorWidgets import (
    GuiEditorItemBasicRemark,
    GuiEditorItemProxyHttp,
    GuiEditorItemProxySocks,
    GuiEditorItemTextSwitch,
    GuiEditorItemTextComboBox,
    GuiEditorItemTextInput,
    GuiEditorItemTextSpinBox,
    GuiEditorWidgetQDialog,
    GuiEditorWidgetQGroupBox,
    GuiEditorWidgetQWidget,
)
from .QtGui import (
    AppQAction,
    AppQActionGroup,
    AppQIcon,
    AppQSeparator,
    bootstrapIcon,
    bootstrapIconMask,
    bootstrapIconWhite,
    bootstrapIconWithOpacity,
)
from .QtNetwork import AppQNetworkAccessManager
from .QtWidgets import (
    AppQComboBox,
    AppQComboBoxSeparatorDelegate,
    AppQDialog,
    AppQTransientDialog,
    AppQDialogButtonBox,
    AppQGroupBox,
    AppQHeaderView,
    AppQIconTextPushButton,
    AppQLabel,
    AppQLineEdit,
    AppQListView,
    AppQMainWindow,
    AppQMenu,
    AppQMenuBar,
    AppQMenuPushButton,
    AppQMessageBox,
    AppQPushButton,
    AppQSpinBox,
    AppQSwitch,
    AppQTableView,
    AppQTabWidget,
    AppQToolBar,
    IconTextPushButton,
    MBoxDirectRulesNotAllowed,
    MBoxNewChangesNextTime,
    MBoxQuestionDelete,
    MBoxUnrecognizedConfig,
    moveToCenter,
    showMBoxDirectRulesNotAllowed,
    showMBoxNewChangesNextTime,
    showMBoxUnrecognizedConfig,
)
from .TextEditor import (
    AppQPlainTextEdit,
    AppQTextBrowser,
    DraculaJSONTextEditor,
    DraculaTextBrowser,
    DraculaTextEditor,
)
from .TextEditorTheme import (
    DraculaEditorTheme,
    DraculaJSONSyntaxHighlighter,
    DraculaLoggerSyntaxHighlighter,
    configureEditorLogMetadata,
)
from .HttpGetManager import HttpGetManager

__all__ = [
    'ABBR_TO_LANGUAGE',
    'AppHue',
    'AppQAction',
    'AppQActionGroup',
    'AppQComboBox',
    'AppQComboBoxSeparatorDelegate',
    'AppQDialog',
    'AppQTransientDialog',
    'AppQDialogButtonBox',
    'AppQGroupBox',
    'AppQHeaderView',
    'AppQIconTextPushButton',
    'AppQIcon',
    'AppQLabel',
    'AppQLineEdit',
    'AppQListView',
    'AppQMainWindow',
    'AppQMenu',
    'AppQMenuBar',
    'AppQMenuPushButton',
    'AppQMessageBox',
    'AppQNetworkAccessManager',
    'AppQPlainTextEdit',
    'AppQPushButton',
    'AppQSeparator',
    'AppQSpinBox',
    'AppQSwitch',
    'AppQTabWidget',
    'AppQTableView',
    'AppQTextBrowser',
    'AppQToolBar',
    'AppStyleSheet',
    'DraculaEditorTheme',
    'DraculaJSONSyntaxHighlighter',
    'DraculaJSONTextEditor',
    'DraculaLoggerSyntaxHighlighter',
    'DraculaTextBrowser',
    'DraculaTextEditor',
    'GuiEditorItemBasicRemark',
    'GuiEditorItemProxyHttp',
    'GuiEditorItemProxySocks',
    'GuiEditorItemTextSwitch',
    'GuiEditorItemTextComboBox',
    'GuiEditorItemTextInput',
    'GuiEditorItemTextSpinBox',
    'GuiEditorWidgetQDialog',
    'GuiEditorWidgetQGroupBox',
    'GuiEditorWidgetQWidget',
    'IconTextPushButton',
    'LANGUAGE_TO_ABBR',
    'MBoxDirectRulesNotAllowed',
    'MBoxNewChangesNextTime',
    'MBoxQuestionDelete',
    'MBoxUnrecognizedConfig',
    'SUPPORTED_LANGUAGE',
    'HttpGetManager',
    'bootstrapIcon',
    'bootstrapIconMask',
    'bootstrapIconWhite',
    'bootstrapIconWithOpacity',
    'configureEditorLogMetadata',
    'gettext',
    'moveToCenter',
    'showMBoxDirectRulesNotAllowed',
    'showMBoxNewChangesNextTime',
    'showMBoxUnrecognizedConfig',
]
