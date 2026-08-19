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

"""Provide menu, navigation, input, and common-control QSS."""

from textwrap import dedent


def controlStyleSheet(
    palette,
    caretDownIcon,
    caretUpIcon,
    caretRightIcon,
    checkIcon,
):
    """Return interactive control styling."""
    return dedent(f"""
            QToolTip {{
                padding: 7px 10px;
                border: 1px solid {palette['border_strong']};
                border-radius: 6px;
                background-color: {palette['overlay']};
                color: {palette['text_strong']};
            }}

            QMenuBar {{
                padding: 2px 5px;
                border: none;
                border-bottom: 1px solid {palette['border']};
                background-color: {palette['panel']};
                spacing: 2px;
            }}

            QMenuBar::item {{
                min-height: 22px;
                padding: 6px 10px;
                border-radius: 5px;
                background-color: transparent;
            }}

            QMenuBar::item:selected {{
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QMenuBar::item:pressed {{
                background-color: {palette['pressed']};
            }}

            QMenu {{
                padding: 6px;
                border: 1px solid {palette['border_strong']};
                border-radius: 9px;
                background-color: {palette['overlay']};
            }}

            QMenu::separator {{
                height: 1px;
                margin: 6px 9px;
                background-color: {palette['border_strong']};
            }}

            QMenu::item {{
                min-width: 160px;
                min-height: 22px;
                padding: 7px 32px;
                border-radius: 6px;
                background-color: transparent;
            }}

            QMenu::item:selected {{
                background-color: {palette['accent_soft_hover']};
                color: {palette['text_strong']};
            }}

            QMenu::item:pressed {{
                background-color: {palette['pressed']};
                color: {palette['text_strong']};
            }}

            QMenu::item:disabled {{
                background-color: transparent;
                color: {palette['disabled']};
            }}

            QMenu::item:disabled:selected {{
                background-color: transparent;
            }}

            QMenu::icon {{
                position: relative;
                left: 8px;
            }}

            QMenu::indicator {{
                width: 14px;
                height: 14px;
                position: relative;
                left: 8px;
            }}

            QMenu::indicator:checked {{
                border-radius: 4px;
                background-color: {palette['accent']};
                image: url("{checkIcon}");
            }}

            QMenu::right-arrow {{
                width: 9px;
                height: 9px;
                position: relative;
                right: 8px;
                image: url("{caretRightIcon}");
            }}

            QMenu[menuRole="tray"] {{
                padding: 7px;
                border-radius: 10px;
            }}

            QMenu[menuRole="tray"]::item {{
                min-width: 176px;
                min-height: 24px;
                padding: 8px 34px;
            }}

            QMenu[menuRole="tray"]::separator {{
                margin: 6px 10px;
            }}

            QMenu[menuRole="tray"]::icon,
            QMenu[menuRole="tray"]::indicator {{
                left: 9px;
            }}

            QMenu[menuRole="tray"]::right-arrow {{
                right: 9px;
            }}

            QToolBar {{
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {palette['border']};
                background-color: {palette['panel']};
                spacing: 3px;
            }}

            QToolBar::separator {{
                width: 1px;
                margin: 5px 5px;
                background-color: {palette['border']};
            }}

            QToolBar#AppMainWindow_AppQToolBar,
            QToolBar#HomePageToolBar {{
                padding: 6px 8px;
                spacing: 2px;
                background-color: {palette['panel']};
            }}

            QToolBar#AppMainWindow_AppQToolBar::separator,
            QToolBar#HomePageToolBar::separator {{
                margin: 8px 4px;
            }}

            QToolButton {{
                min-height: 24px;
                padding: 5px 8px;
                border: 1px solid transparent;
                border-radius: 6px;
                background-color: transparent;
                color: {palette['text']};
            }}

            QToolBar#AppMainWindow_AppQToolBar QToolButton,
            QToolBar#HomePageToolBar QToolButton {{
                min-width: 72px;
                min-height: 54px;
                padding: 5px 11px;
                border-radius: 8px;
            }}

            QPushButton#NavigationToggleButton,
            QPushButton#NavigationPageButton {{
                min-width: 0;
                min-height: 38px;
                padding: 0;
                border: 1px solid transparent;
                border-radius: 7px;
                background-color: transparent;
                color: {palette['text']};
                text-align: left;
            }}

            QPushButton#NavigationToggleButton:hover,
            QPushButton#NavigationPageButton:hover {{
                border-color: transparent;
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QPushButton#NavigationPageButton:checked {{
                border: none;
                border-radius: 7px;
                background-color: {palette['accent_soft']};
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QFrame#NavigationSelectionIndicator {{
                border: none;
                border-radius: 0;
                background-color: {palette['accent']};
            }}

            QPushButton#NavigationPageButton:checked:hover {{
                background-color: {palette['accent_soft_hover']};
            }}

            QPushButton#NavigationPageButton QLabel {{
                border: none;
                background-color: transparent;
                color: {palette['text']};
            }}

            QPushButton#NavigationPageButton:checked QLabel {{
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QPushButton#SearchButton {{
                padding: 0;
            }}

            QToolButton:hover {{
                border-color: {palette['border']};
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QToolButton:pressed {{
                border-color: {palette['border_strong']};
                background-color: {palette['pressed']};
            }}

            QToolButton:checked {{
                border-color: {palette['accent']};
                background-color: {palette['accent_soft']};
                color: {palette['text_strong']};
            }}

            QToolButton:checked:hover {{
                background-color: {palette['accent_soft_hover']};
            }}

            QToolButton:disabled {{
                border-color: transparent;
                background-color: transparent;
                color: {palette['disabled']};
            }}

            QPushButton {{
                min-height: 28px;
                padding: 3px 13px;
                border: 1px solid {palette['border_strong']};
                border-radius: 6px;
                background-color: {palette['panel']};
                color: {palette['text']};
            }}

            QPushButton:hover {{
                border-color: {palette['accent']};
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QPushButton:focus {{
                border: 1px solid {palette['accent']};
            }}

            QPushButton:pressed {{
                border-color: {palette['accent_pressed']};
                background-color: {palette['pressed']};
            }}

            QPushButton:default {{
                border-color: {palette['accent']};
                background-color: {palette['accent']};
                color: {palette['accent_text']};
                font-weight: 600;
            }}

            QPushButton:default:hover {{
                border-color: {palette['accent_hover']};
                background-color: {palette['accent_hover']};
            }}

            QPushButton:default:pressed {{
                border-color: {palette['accent_pressed']};
                background-color: {palette['accent_pressed']};
            }}

            QPushButton:flat {{
                border-color: transparent;
                background-color: transparent;
            }}

            QPushButton:disabled {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
                color: {palette['disabled']};
            }}

            QLineEdit,
            QTextEdit,
            QPlainTextEdit,
            QComboBox,
            QSpinBox,
            QDoubleSpinBox,
            QDateEdit,
            QDateTimeEdit,
            QTimeEdit {{
                min-height: 28px;
                padding: 3px 8px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['input']};
                color: {palette['text']};
                selection-background-color: {palette['selection']};
                selection-color: {palette['selection_text']};
            }}

            QLineEdit:hover,
            QTextEdit:hover,
            QPlainTextEdit:hover,
            QComboBox:hover,
            QSpinBox:hover,
            QDoubleSpinBox:hover,
            QDateEdit:hover,
            QDateTimeEdit:hover,
            QTimeEdit:hover {{
                border-color: {palette['border_strong']};
            }}

            QLineEdit:focus,
            QTextEdit:focus,
            QPlainTextEdit:focus,
            QComboBox:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QDateEdit:focus,
            QDateTimeEdit:focus,
            QTimeEdit:focus {{
                border-color: {palette['accent']};
                background-color: {palette['input_focus']};
            }}

            QLineEdit:read-only,
            QTextEdit:read-only,
            QPlainTextEdit:read-only {{
                background-color: {palette['panel_alt']};
                color: {palette['muted']};
            }}

            QLineEdit:disabled,
            QTextEdit:disabled,
            QPlainTextEdit:disabled,
            QComboBox:disabled,
            QSpinBox:disabled,
            QDoubleSpinBox:disabled,
            QDateEdit:disabled,
            QDateTimeEdit:disabled,
            QTimeEdit:disabled {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
                color: {palette['disabled']};
            }}

            QComboBox {{
                padding-right: 32px;
            }}

            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 27px;
                border: none;
                border-left: 1px solid {palette['border']};
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }}

            QComboBox::drop-down:hover {{
                background-color: {palette['hover']};
            }}

            QComboBox::down-arrow {{
                width: 9px;
                height: 9px;
                image: url("{caretDownIcon}");
            }}

            QComboBox QAbstractItemView {{
                padding: 4px;
                border: 1px solid {palette['border_strong']};
                border-radius: 6px;
                background-color: {palette['overlay']};
                color: {palette['text']};
                selection-background-color: {palette['selection']};
                selection-color: {palette['selection_text']};
            }}

            QSpinBox,
            QDoubleSpinBox {{
                padding-right: 31px;
            }}

            QSpinBox::up-button,
            QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 28px;
                height: 16px;
                border: none;
                border-left: 1px solid {palette['border']};
                border-bottom: 1px solid {palette['border']};
                border-top-right-radius: 6px;
                background-color: transparent;
            }}

            QSpinBox::down-button,
            QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 28px;
                height: 16px;
                border: none;
                border-left: 1px solid {palette['border']};
                border-top: 1px solid {palette['border']};
                border-bottom-right-radius: 6px;
                background-color: transparent;
            }}

            QSpinBox::up-button:hover,
            QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {{
                background-color: {palette['hover']};
            }}

            QSpinBox::up-arrow,
            QDoubleSpinBox::up-arrow {{
                width: 8px;
                height: 8px;
                image: url("{caretUpIcon}");
            }}

            QSpinBox::down-arrow,
            QDoubleSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
                image: url("{caretDownIcon}");
            }}

            QTabWidget::pane {{
                top: -1px;
                border: 1px solid {palette['border']};
                border-radius: 8px;
                background-color: {palette['panel']};
            }}

            QTabBar {{
                background-color: transparent;
            }}

            QTabBar::tab {{
                min-height: 28px;
                padding: 6px 14px;
                margin-right: 2px;
                border: none;
                border-bottom: 2px solid transparent;
                background-color: transparent;
                color: {palette['muted']};
            }}

            QTabBar::tab:selected {{
                border-bottom-color: {palette['accent']};
                background-color: {palette['panel']};
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {palette['hover']};
                color: {palette['text']};
            }}

            QTabBar::tab:disabled {{
                color: {palette['disabled']};
            }}

    """).strip()
