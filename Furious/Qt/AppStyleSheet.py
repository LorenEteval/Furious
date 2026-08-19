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

from Furious.Qt.StyleSheets import composeStyleSheet

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
            # Metrics visualization semantics.
            'metrics_download': '#0F8F87',
            'metrics_download_fill': '#BFEDE7',
            'metrics_upload': '#D9772F',
            'metrics_upload_fill': '#F8D7BB',
            'metrics_grid': '#D9E1EC',
            'metrics_axis': '#5E6B80',
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
            # Metrics visualization semantics.
            'metrics_download': '#36D6C5',
            'metrics_download_fill': '#174C47',
            'metrics_upload': '#FF9A52',
            'metrics_upload_fill': '#57321F',
            'metrics_grid': '#2A3340',
            'metrics_axis': '#9AA7B8',
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

        return composeStyleSheet(
            palette,
            progressBarStyleSheet,
            caretDownIcon,
            caretUpIcon,
            caretRightIcon,
            checkIcon,
        )
