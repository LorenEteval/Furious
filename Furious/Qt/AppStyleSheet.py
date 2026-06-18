# Copyright (C) 2024-present  Loren Eteval & contributors <loren.eteval@proton.me>
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

from textwrap import dedent

__all__ = ['AppStyleSheet']


class AppStyleSheet:
    Light = 'Light'
    Dark = 'Dark'
    FontPointSize = 10

    Palettes = {
        Light: {
            'window': '#F4F6F8',
            'panel': '#FFFFFF',
            'panel_alt': '#F8FAFC',
            'raised': '#EEF3F7',
            'text': '#1D2733',
            'muted': '#667382',
            'disabled': '#98A2AE',
            'border': '#D7DEE7',
            'border_strong': '#BEC8D4',
            'accent': '#2F817D',
            'accent_hover': '#28716D',
            'accent_pressed': '#22615E',
            'accent_soft': '#DDF1EF',
            'selection': '#CFEDEA',
            'selection_text': '#102033',
            'input': '#FFFFFF',
            'input_focus': '#F7FBFF',
            'danger': '#D9514E',
            'danger_soft': '#FDECEC',
            'success': '#2F817D',
            'success_soft': '#DDF1EF',
            'scroll_handle': '#B4C0CC',
            'scroll_handle_hover': '#96A5B4',
        },
        Dark: {
            'window': '#202124',
            'panel': '#292A2D',
            'panel_alt': '#242528',
            'raised': '#33353A',
            'text': '#ECEFF3',
            'muted': '#B5BAC2',
            'disabled': '#737981',
            'border': '#3F4248',
            'border_strong': '#50545C',
            'accent': '#4FB6B2',
            'accent_hover': '#68C6C2',
            'accent_pressed': '#3EA29E',
            'accent_soft': '#1F3A3A',
            'selection': '#285A59',
            'selection_text': '#F7FBFF',
            'input': '#232427',
            'input_focus': '#282D2F',
            'danger': '#F07178',
            'danger_soft': '#4A2528',
            'success': '#4FB6B2',
            'success_soft': '#1F3A3A',
            'scroll_handle': '#5B6067',
            'scroll_handle_hover': '#70767F',
        },
    }

    @staticmethod
    def normalizeTheme(theme):
        if theme == AppStyleSheet.Dark:
            return AppStyleSheet.Dark

        return AppStyleSheet.Light

    @staticmethod
    def forTheme(theme):
        normalizedTheme = AppStyleSheet.normalizeTheme(theme)
        palette = AppStyleSheet.Palettes[normalizedTheme]
        iconPrefix = ':/Icons/bootstrap'

        if normalizedTheme == AppStyleSheet.Dark:
            iconPrefix += '/white'

        caretDownIcon, caretUpIcon = (
            f'{iconPrefix}/caret-down-fill.svg',
            f'{iconPrefix}/caret-up-fill.svg',
        )

        return dedent(f"""
            * {{
                outline: 0;
            }}

            QWidget {{
                background-color: {palette['window']};
                color: {palette['text']};
                selection-background-color: {palette['selection']};
                selection-color: {palette['selection_text']};
            }}

            QMainWindow,
            QDialog,
            QMessageBox {{
                background-color: {palette['window']};
            }}

            QFrame,
            QGroupBox {{
                border-color: {palette['border']};
            }}

            QGroupBox {{
                margin-top: 14px;
                padding: 10px 8px 8px 8px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {palette['muted']};
            }}

            QToolTip {{
                padding: 6px 8px;
                border: 1px solid {palette['border_strong']};
                border-radius: 4px;
                background-color: {palette['raised']};
                color: {palette['text']};
            }}

            QMenuBar {{
                background-color: {palette['panel']};
                border-bottom: 1px solid {palette['border']};
                spacing: 2px;
            }}

            QMenuBar::item {{
                min-height: 24px;
                padding: 9px 14px;
                border-radius: 4px;
                background: transparent;
            }}

            QMenuBar::item:selected,
            QMenuBar::item:pressed {{
                background-color: {palette['accent_soft']};
                color: {palette['text']};
            }}

            QMenu {{
                padding: 8px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['panel']};
            }}

            QMenu::separator {{
                height: 1px;
                margin: 6px 8px;
                background-color: {palette['border']};
            }}

            QMenu::item {{
                min-width: 132px;
                min-height: 18px;
                padding: 9px 28px 9px 14px;
                border-radius: 4px;
                background-color: transparent;
            }}

            QMenu::item:selected {{
                background-color: {palette['selection']};
                color: {palette['selection_text']};
            }}

            QToolBar {{
                padding: 5px;
                spacing: 5px;
                border: 0;
                border-bottom: 1px solid {palette['border']};
                background-color: {palette['panel']};
            }}

            QToolBar::separator {{
                width: 1px;
                margin: 4px 6px;
                background-color: {palette['border']};
            }}

            QToolButton {{
                min-height: 24px;
                padding: 4px 7px;
                border: 1px solid transparent;
                border-radius: 5px;
                background-color: transparent;
            }}

            QToolButton:hover {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
            }}

            QToolButton:pressed,
            QToolButton:checked {{
                border-color: {palette['accent']};
                background-color: {palette['accent_soft']};
            }}

            QPushButton {{
                min-height: 26px;
                padding: 4px 12px;
                border: 1px solid {palette['border_strong']};
                border-radius: 5px;
                background-color: {palette['panel']};
                color: {palette['text']};
            }}

            QPushButton:hover {{
                border-color: {palette['accent']};
                background-color: {palette['raised']};
            }}

            QPushButton:pressed {{
                border-color: {palette['accent_pressed']};
                background-color: {palette['accent_soft']};
            }}

            QPushButton:default {{
                border-color: {palette['accent']};
            }}

            QPushButton:disabled {{
                border-color: {palette['border']};
                color: {palette['disabled']};
                background-color: {palette['raised']};
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
                min-height: 26px;
                padding: 3px 7px;
                border: 1px solid {palette['border']};
                border-radius: 5px;
                background-color: {palette['input']};
                color: {palette['text']};
            }}

            QTextEdit,
            QPlainTextEdit {{
                selection-background-color: {palette['selection']};
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

            QLineEdit:disabled,
            QTextEdit:disabled,
            QPlainTextEdit:disabled,
            QComboBox:disabled,
            QSpinBox:disabled,
            QDoubleSpinBox:disabled,
            QDateEdit:disabled,
            QDateTimeEdit:disabled,
            QTimeEdit:disabled {{
                color: {palette['disabled']};
                background-color: {palette['raised']};
            }}

            QComboBox::drop-down {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                border: 0;
                border-left: 1px solid {palette['border']};
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
                background-color: transparent;
            }}

            QComboBox {{
                padding-right: 31px;
            }}

            QComboBox::down-arrow {{
                width: 10px;
                height: 10px;
                image: url("{caretDownIcon}");
            }}

            QComboBox::down-arrow:disabled {{
                image: url("{caretDownIcon}");
            }}

            QComboBox QAbstractItemView {{
                border: 1px solid {palette['border']};
                border-radius: 5px;
                background-color: {palette['panel']};
                selection-background-color: {palette['selection']};
                selection-color: {palette['selection_text']};
            }}

            QSpinBox,
            QDoubleSpinBox {{
                padding-right: 30px;
            }}

            QSpinBox::up-button,
            QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 27px;
                height: 15px;
                border-left: 1px solid {palette['border']};
                border-bottom: 1px solid {palette['border']};
                border-top-right-radius: 5px;
                background-color: transparent;
            }}

            QSpinBox::down-button,
            QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 27px;
                height: 15px;
                border-left: 1px solid {palette['border']};
                border-bottom-right-radius: 5px;
                background-color: transparent;
            }}

            QSpinBox::up-button:hover,
            QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {{
                background-color: {palette['raised']};
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

            QSpinBox::up-arrow:disabled,
            QDoubleSpinBox::up-arrow:disabled {{
                image: url("{caretUpIcon}");
            }}

            QSpinBox::down-arrow:disabled,
            QDoubleSpinBox::down-arrow:disabled {{
                image: url("{caretDownIcon}");
            }}

            QTabWidget::pane {{
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['panel']};
                top: -1px;
            }}

            QTabBar::tab {{
                min-height: 26px;
                padding: 5px 12px;
                margin-right: 2px;
                border: 1px solid {palette['border']};
                border-bottom-color: {palette['border']};
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                background-color: {palette['raised']};
                color: {palette['muted']};
            }}

            QTabBar::tab:selected {{
                background-color: {palette['panel']};
                color: {palette['text']};
                border-bottom-color: {palette['panel']};
            }}

            QTabBar::tab:hover:!selected {{
                color: {palette['text']};
                background-color: {palette['accent_soft']};
            }}

            QTableView,
            QTableWidget,
            QTreeView,
            QListView,
            QListWidget {{
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['panel']};
                alternate-background-color: {palette['panel_alt']};
                gridline-color: {palette['border']};
                color: {palette['text']};
                selection-background-color: {palette['selection']};
                selection-color: {palette['selection_text']};
            }}

            QTableView::item,
            QTableWidget::item,
            QTreeView::item,
            QListView::item,
            QListWidget::item {{
                min-height: 22px;
                padding: 3px 6px;
                border: 0;
            }}

            QTableView::item:hover,
            QTableWidget::item:hover,
            QTreeView::item:hover,
            QListView::item:hover,
            QListWidget::item:hover {{
                background-color: {palette['accent_soft']};
            }}

            QTableView::item:selected,
            QTableWidget::item:selected,
            QTreeView::item:selected,
            QListView::item:selected,
            QListWidget::item:selected {{
                background-color: {palette['selection']};
                color: {palette['selection_text']};
            }}

            QHeaderView {{
                background-color: {palette['panel']};
            }}

            QHeaderView::section {{
                min-height: 26px;
                padding: 5px 7px;
                border: 0;
                border-right: 1px solid {palette['border']};
                border-bottom: 1px solid {palette['border']};
                background-color: {palette['raised']};
                color: {palette['text']};
            }}

            QHeaderView::section:hover {{
                background-color: {palette['accent_soft']};
            }}

            QAbstractScrollArea::corner {{
                background-color: {palette['panel']};
            }}

            QScrollBar:vertical {{
                width: 12px;
                margin: 0;
                border: 0;
                background-color: {palette['panel_alt']};
            }}

            QScrollBar:horizontal {{
                height: 12px;
                margin: 0;
                border: 0;
                background-color: {palette['panel_alt']};
            }}

            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal {{
                min-height: 24px;
                min-width: 24px;
                margin: 2px;
                border-radius: 4px;
                background-color: {palette['scroll_handle']};
            }}

            QScrollBar::handle:vertical:hover,
            QScrollBar::handle:horizontal:hover {{
                background-color: {palette['scroll_handle_hover']};
            }}

            QScrollBar::add-line,
            QScrollBar::sub-line,
            QScrollBar::add-page,
            QScrollBar::sub-page {{
                width: 0;
                height: 0;
                background: transparent;
            }}

            QProgressBar {{
                min-height: 12px;
                border: 1px solid {palette['border']};
                border-radius: 5px;
                background-color: {palette['raised']};
                color: {palette['text']};
                text-align: center;
            }}

            QProgressBar::chunk {{
                border-radius: 4px;
                background-color: {palette['accent']};
            }}

            QCheckBox,
            QRadioButton {{
                spacing: 6px;
                color: {palette['text']};
            }}

            QCheckBox:disabled,
            QRadioButton:disabled {{
                color: {palette['disabled']};
            }}

            QStatusBar {{
                border-top: 1px solid {palette['border']};
                background-color: {palette['panel']};
            }}

            QWidget#NetworkStateBadge {{
                min-height: 22px;
                border: 1px solid {palette['border']};
                border-radius: 5px;
                background-color: {palette['raised']};
                color: {palette['muted']};
            }}

            QWidget#NetworkStateBadge QLabel {{
                border: 0;
                padding: 0;
                background-color: transparent;
                color: {palette['muted']};
            }}

            QWidget#NetworkStateBadge[networkState="success"] {{
                border-left: 4px solid {palette['success']};
                background-color: {palette['success_soft']};
                color: {palette['text']};
            }}

            QWidget#NetworkStateBadge[networkState="success"] QLabel {{
                color: {palette['text']};
            }}

            QWidget#NetworkStateBadge[networkState="failure"] {{
                border-left: 4px solid {palette['danger']};
                background-color: {palette['danger_soft']};
                color: {palette['text']};
            }}

            QWidget#NetworkStateBadge[networkState="failure"] QLabel {{
                color: {palette['danger']};
            }}

            QSplitter::handle {{
                background-color: {palette['border']};
            }}
            """).strip()
