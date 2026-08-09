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

"""Provide the application-wide Qt style sheet."""

from __future__ import annotations

from textwrap import dedent

__all__ = ['AppStyleSheet']


class AppStyleSheet:
    """Build the light and dark visual themes used by Furious."""

    Light = 'Light'
    Dark = 'Dark'
    FontPointSize = 10

    Palettes = {
        Light: {
            # Application surfaces and interaction states.
            'window': '#F4F7FB',
            'panel': '#FFFFFF',
            'panel_alt': '#F8FAFD',
            'overlay': '#FFFFFF',
            'raised': '#EAF0F7',
            'hover': '#EEF4FB',
            'pressed': '#E2EAF4',
            'text': '#172033',
            'text_strong': '#0D1525',
            'muted': '#5E6B80',
            'disabled': '#9AA6B5',
            'border': '#D9E1EC',
            'border_strong': '#BAC6D6',
            'accent': '#3B82F6',
            'accent_hover': '#2563EB',
            'accent_pressed': '#1D4ED8',
            'accent_text': '#FFFFFF',
            'accent_soft': '#E8F1FF',
            'accent_soft_hover': '#DCEAFF',
            'selection': '#D8E8FF',
            'selection_text': '#102A56',
            'input': '#FFFFFF',
            'input_focus': '#FFFFFF',
            'danger': '#D94F64',
            'danger_soft': '#FDEBED',
            'success': '#159A70',
            'success_soft': '#E1F7EF',
            'warning': '#B7791F',
            'warning_soft': '#FFF4D6',
            'scroll_handle': '#B9C5D4',
            'scroll_handle_hover': '#93A3B7',
            # Editor semantics.
            'editor_background': '#F8FAFC',
            'editor_text': '#172033',
            'editor_keyword': '#7C3AED',
            'editor_string': '#0F766E',
            'editor_number': '#B45309',
            'editor_comment': '#64748B',
            'editor_ip': '#0369A1',
            'editor_url': '#2563EB',
            'editor_warning': '#A16207',
            'editor_error': '#D33F5A',
            'editor_symbol': '#475569',
            'editor_key': '#047857',
            'editor_timestamp': '#64748B',
            'editor_logger': '#C2410C',
            'editor_info': '#15803D',
            'editor_debug': '#2563EB',
            'editor_critical': '#B91C1C',
            'editor_selection': '#D8E8FF',
            'editor_selection_text': '#102A56',
            # Progress and connection semantics.
            'progress_background': '#DCE5F0',
            'progress_chunk_start': '#2563EB',
            'progress_chunk_end': '#22B8CF',
            'progress_text': '#172033',
            'connection_disconnected': '#D94F64',
            'connection_connecting': '#3B82F6',
            'connection_connected': '#159A70',
        },
        Dark: {
            # Application surfaces and interaction states.
            'window': '#0F131A',
            'panel': '#151A22',
            'panel_alt': '#11161D',
            'overlay': '#1B212B',
            'raised': '#202733',
            'hover': '#202936',
            'pressed': '#293443',
            'text': '#E7ECF4',
            'text_strong': '#F7F9FC',
            'muted': '#9AA7B8',
            'disabled': '#606B79',
            'border': '#2A3340',
            'border_strong': '#3B4656',
            'accent': '#5B9BFF',
            'accent_hover': '#78ACFF',
            'accent_pressed': '#3F83F8',
            'accent_text': '#07101F',
            'accent_soft': '#172A47',
            'accent_soft_hover': '#1E3659',
            'selection': '#214A7D',
            'selection_text': '#F6F9FF',
            'input': '#111720',
            'input_focus': '#151D28',
            'danger': '#FF6B7A',
            'danger_soft': '#351C25',
            'success': '#42D39A',
            'success_soft': '#15342B',
            'warning': '#F7C65F',
            'warning_soft': '#352C18',
            'scroll_handle': '#3B4654',
            'scroll_handle_hover': '#536171',
            # Editor semantics.
            'editor_background': '#10151D',
            'editor_text': '#E7ECF4',
            'editor_keyword': '#C4A7FF',
            'editor_string': '#85E0B7',
            'editor_number': '#F5B971',
            'editor_comment': '#8290A4',
            'editor_ip': '#80D8FF',
            'editor_url': '#8AB4FF',
            'editor_warning': '#F7C65F',
            'editor_error': '#FF7A8A',
            'editor_symbol': '#C7D0DD',
            'editor_key': '#6EE7B7',
            'editor_timestamp': '#8290A4',
            'editor_logger': '#FFAD7A',
            'editor_info': '#7DD3A8',
            'editor_debug': '#82B4FF',
            'editor_critical': '#FF5C70',
            'editor_selection': '#214A7D',
            'editor_selection_text': '#F6F9FF',
            # Progress and connection semantics.
            'progress_background': '#242C38',
            'progress_chunk_start': '#5B9BFF',
            'progress_chunk_end': '#36D6C5',
            'progress_text': '#F7F9FC',
            'connection_disconnected': '#FF6B7A',
            'connection_connecting': '#5B9BFF',
            'connection_connected': '#42D39A',
        },
    }

    @staticmethod
    def normalizeTheme(theme):
        """Return a supported theme name, defaulting to the light theme."""
        if theme == AppStyleSheet.Dark:
            return AppStyleSheet.Dark

        return AppStyleSheet.Light

    @staticmethod
    def paletteForTheme(theme):
        """Return the semantic token palette for *theme*."""
        return AppStyleSheet.Palettes[AppStyleSheet.normalizeTheme(theme)]

    @staticmethod
    def editorStyleSheet(widgetName, fontFamily='', theme=Light):
        """Return editor chrome built exclusively from semantic theme tokens."""
        palette = AppStyleSheet.paletteForTheme(theme)
        escapedFontFamily = fontFamily.replace('\\', '\\\\').replace("'", "\\'")
        fontDeclaration = ''

        if escapedFontFamily:
            fontDeclaration = f"font-family: '{escapedFontFamily}';"

        return dedent(f"""
            {widgetName} {{
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['editor_background']};
                color: {palette['editor_text']};
                selection-background-color: {palette['editor_selection']};
                selection-color: {palette['editor_selection_text']};
                {fontDeclaration}
            }}

            {widgetName}:hover {{
                border-color: {palette['border_strong']};
            }}

            {widgetName}:focus {{
                border-color: {palette['accent']};
                background-color: {palette['editor_background']};
            }}
        """).strip()

    @staticmethod
    def progressBarStyleSheet(theme=Light):
        """Return progress styling built from progress and connection tokens."""
        palette = AppStyleSheet.paletteForTheme(theme)

        return dedent(f"""
            QProgressBar {{
                min-height: 12px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['progress_background']};
                color: {palette['progress_text']};
                text-align: center;
            }}

            QProgressBar::chunk {{
                border-radius: 5px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {palette['progress_chunk_start']},
                    stop: 1 {palette['progress_chunk_end']}
                );
            }}

            QProgressBar[connectionState="disconnected"]::chunk {{
                background: {palette['connection_disconnected']};
            }}

            QProgressBar[connectionState="connecting"]::chunk {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {palette['connection_connecting']},
                    stop: 1 {palette['progress_chunk_end']}
                );
            }}

            QProgressBar[connectionState="connected"]::chunk {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {palette['progress_chunk_start']},
                    stop: 1 {palette['connection_connected']}
                );
            }}
        """).strip()

    @staticmethod
    def forTheme(theme):
        """Return the complete Qt style sheet for *theme*."""
        normalizedTheme = AppStyleSheet.normalizeTheme(theme)
        palette = AppStyleSheet.paletteForTheme(normalizedTheme)
        progressBarStyleSheet = AppStyleSheet.progressBarStyleSheet(normalizedTheme)
        iconPrefix = ':/Icons/bootstrap'

        if normalizedTheme == AppStyleSheet.Dark:
            iconPrefix += '/white'

        caretDownIcon = f'{iconPrefix}/caret-down-fill.svg'
        caretUpIcon = f'{iconPrefix}/caret-up-fill.svg'
        caretRightIcon = f'{iconPrefix}/caret-right-fill.svg'
        checkIcon = ':/Icons/bootstrap/white/check.svg'

        return dedent(f"""
            * {{
                outline: none;
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

            QLabel,
            QDialogButtonBox,
            QSizeGrip {{
                border: none;
                background-color: transparent;
            }}

            QLabel:disabled {{
                color: {palette['disabled']};
            }}

            QFrame {{
                border-color: {palette['border']};
            }}

            QGroupBox {{
                margin-top: 16px;
                padding: 14px 12px 12px 12px;
                border: 1px solid {palette['border']};
                border-radius: 8px;
                background-color: {palette['panel']};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background-color: {palette['panel']};
                color: {palette['muted']};
                font-weight: 600;
            }}

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
                border-radius: 8px;
                background-color: {palette['overlay']};
            }}

            QMenu::separator {{
                height: 1px;
                margin: 5px 8px;
                background-color: {palette['border']};
            }}

            QMenu::item {{
                min-width: 156px;
                min-height: 20px;
                padding: 7px 30px 7px 28px;
                border-radius: 5px;
                background-color: transparent;
            }}

            QMenu::item:selected {{
                background-color: {palette['accent_soft']};
                color: {palette['text_strong']};
            }}

            QMenu::item:disabled {{
                background-color: transparent;
                color: {palette['disabled']};
            }}

            QMenu::icon {{
                position: relative;
                left: 7px;
            }}

            QMenu::indicator {{
                width: 14px;
                height: 14px;
                position: relative;
                left: 7px;
            }}

            QMenu::indicator:checked {{
                border-radius: 4px;
                background-color: {palette['accent']};
                image: url("{checkIcon}");
            }}

            QMenu::right-arrow {{
                width: 9px;
                height: 9px;
                image: url("{caretRightIcon}");
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

            QToolBar#AppMainWindow_AppQToolBar {{
                padding: 6px 8px;
                spacing: 2px;
                background-color: {palette['panel']};
            }}

            QToolBar#AppMainWindow_AppQToolBar::separator {{
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

            QToolBar#AppMainWindow_AppQToolBar QToolButton {{
                min-width: 72px;
                min-height: 54px;
                padding: 5px 11px;
                border-radius: 8px;
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

            QTableView,
            QTableWidget,
            QTreeView,
            QListView,
            QListWidget {{
                border: 1px solid {palette['border']};
                border-radius: 8px;
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
                min-height: 24px;
                padding: 4px 7px;
                border: none;
            }}

            QTableView::item:hover,
            QTableWidget::item:hover,
            QTreeView::item:hover,
            QListView::item:hover,
            QListWidget::item:hover {{
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QTableView::item:selected,
            QTableWidget::item:selected,
            QTreeView::item:selected,
            QListView::item:selected,
            QListWidget::item:selected {{
                background-color: {palette['selection']};
                color: {palette['selection_text']};
            }}

            QTableView::item:selected:!active,
            QTableWidget::item:selected:!active,
            QTreeView::item:selected:!active,
            QListView::item:selected:!active,
            QListWidget::item:selected:!active {{
                background-color: {palette['raised']};
                color: {palette['text']};
            }}

            QHeaderView {{
                border: none;
                background-color: {palette['panel_alt']};
            }}

            QHeaderView::section {{
                min-height: 28px;
                padding: 5px 8px;
                border: none;
                border-right: 1px solid {palette['border']};
                border-bottom: 1px solid {palette['border']};
                background-color: {palette['raised']};
                color: {palette['muted']};
                font-weight: 600;
            }}

            QHeaderView::section:hover {{
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QHeaderView::section:pressed {{
                background-color: {palette['pressed']};
            }}

            QAbstractScrollArea::corner {{
                border: none;
                background-color: {palette['panel_alt']};
            }}

            QScrollBar:vertical {{
                width: 11px;
                margin: 0;
                border: none;
                background-color: transparent;
            }}

            QScrollBar:horizontal {{
                height: 11px;
                margin: 0;
                border: none;
                background-color: transparent;
            }}

            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal {{
                min-height: 28px;
                min-width: 28px;
                margin: 2px;
                border-radius: 3px;
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
                border: none;
                background-color: transparent;
            }}

            {progressBarStyleSheet}

            QCheckBox,
            QRadioButton {{
                spacing: 7px;
                background-color: transparent;
                color: {palette['text']};
            }}

            QCheckBox:hover,
            QRadioButton:hover {{
                color: {palette['text_strong']};
            }}

            QCheckBox:disabled,
            QRadioButton:disabled {{
                color: {palette['disabled']};
            }}

            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {palette['border_strong']};
                border-radius: 4px;
                background-color: {palette['input']};
            }}

            QCheckBox::indicator:hover {{
                border-color: {palette['accent']};
                background-color: {palette['accent_soft']};
            }}

            QCheckBox::indicator:checked {{
                border-color: {palette['accent']};
                background-color: {palette['accent']};
                image: url("{checkIcon}");
            }}

            QCheckBox::indicator:indeterminate {{
                border: 4px solid {palette['accent']};
                background-color: {palette['input']};
            }}

            QRadioButton::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {palette['border_strong']};
                border-radius: 8px;
                background-color: {palette['input']};
            }}

            QRadioButton::indicator:hover {{
                border-color: {palette['accent']};
                background-color: {palette['accent_soft']};
            }}

            QRadioButton::indicator:checked {{
                border: 5px solid {palette['accent']};
                background-color: {palette['input']};
            }}

            QCheckBox::indicator:disabled,
            QRadioButton::indicator:disabled {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
            }}

            QSlider::groove:horizontal {{
                height: 4px;
                border-radius: 2px;
                background-color: {palette['raised']};
            }}

            QSlider::sub-page:horizontal {{
                border-radius: 2px;
                background-color: {palette['accent']};
            }}

            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -6px 0;
                border: 2px solid {palette['panel']};
                border-radius: 8px;
                background-color: {palette['accent']};
            }}

            QSlider::handle:horizontal:hover {{
                background-color: {palette['accent_hover']};
            }}

            QStatusBar {{
                min-height: 24px;
                border-top: 1px solid {palette['border']};
                background-color: {palette['panel']};
                color: {palette['muted']};
            }}

            QStatusBar::item {{
                border: none;
            }}

            QWidget#NetworkStateBadge {{
                min-height: 24px;
                padding: 0 2px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['raised']};
                color: {palette['muted']};
            }}

            QWidget#NetworkStateBadge QLabel {{
                border: none;
                padding: 0;
                background-color: transparent;
                color: {palette['muted']};
            }}

            QWidget#NetworkStateBadge[networkState="success"] {{
                border-color: {palette['success']};
                background-color: {palette['success_soft']};
                color: {palette['text_strong']};
            }}

            QWidget#NetworkStateBadge[networkState="success"] QLabel {{
                color: {palette['text_strong']};
            }}

            QWidget#NetworkStateBadge[networkState="failure"] {{
                border-color: {palette['danger']};
                background-color: {palette['danger_soft']};
                color: {palette['text_strong']};
            }}

            QWidget#NetworkStateBadge[networkState="failure"] QLabel {{
                color: {palette['danger']};
            }}

            QWidget#TrafficSpeedBadge {{
                min-height: 24px;
                padding: 0 2px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['raised']};
                color: {palette['text_strong']};
            }}

            QWidget#TrafficSpeedBadge QLabel {{
                border: none;
                padding: 0;
                background-color: transparent;
                color: {palette['text_strong']};
            }}

            QSplitter::handle {{
                background-color: {palette['border']};
            }}

            QSplitter::handle:hover {{
                background-color: {palette['accent']};
            }}

            QSplitter::handle:horizontal {{
                width: 2px;
            }}

            QSplitter::handle:vertical {{
                height: 2px;
            }}
            """).strip()
