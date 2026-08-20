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

"""Provide item-view, scrolling, selection, and status QSS."""

from textwrap import dedent


def dataViewStyleSheet(palette, progressBarStyleSheet, checkIcon):
    """Return data-view and status component styling."""
    return dedent(f"""
            QTableView,
            QTableWidget,
            QTreeView,
            QListView {{
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
            QListView::item {{
                min-height: 24px;
                padding: 4px 7px;
                border: none;
            }}

            QTableView::item:hover,
            QTableWidget::item:hover,
            QTreeView::item:hover,
            QListView::item:hover {{
                background-color: {palette['hover']};
                color: {palette['text_strong']};
            }}

            QTableView::item:selected,
            QTableWidget::item:selected,
            QTreeView::item:selected,
            QListView::item:selected {{
                background-color: {palette['selection']};
                color: {palette['selection_text']};
            }}

            QTableView::item:selected:!active,
            QTableWidget::item:selected:!active,
            QTreeView::item:selected:!active,
            QListView::item:selected:!active {{
                background-color: {palette['raised']};
                color: {palette['text']};
            }}

            QTableView[selectionShape="rounded"],
            QListView[selectionShape="rounded"] {{
                selection-background-color: transparent;
            }}

            QTableView[selectionShape="rounded"]::item:selected,
            QTableView[selectionShape="rounded"]::item:selected:!active,
            QListView[selectionShape="rounded"]::item:selected,
            QListView[selectionShape="rounded"]::item:selected:!active {{
                background-color: transparent;
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
                min-height: 30px;
                border-top: 1px solid {palette['border']};
                background-color: {palette['panel']};
                color: {palette['muted']};
            }}

            QStatusBar::item {{
                border: none;
            }}

            QFrame#NetworkStateBadge {{
                min-height: 24px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['raised']};
                color: {palette['muted']};
            }}

            QFrame#NetworkStateBadge QLabel {{
                border: none;
                padding: 0;
                background-color: transparent;
                color: {palette['muted']};
            }}

            QFrame#NetworkStateBadge QLabel#NetworkStateLabel {{
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QFrame#NetworkStateBadge[networkState="disconnected"] QLabel#NetworkStateLabel {{
                color: {palette['muted']};
            }}

            QFrame#NetworkStateBadge[networkState="connecting"] {{
                border-color: {palette['accent']};
                background-color: {palette['accent_soft']};
            }}

            QFrame#NetworkStateBadge[networkState="connecting"] QLabel#NetworkStateLabel {{
                color: {palette['accent']};
            }}

            QFrame#NetworkStateBadge[networkState="connected"],
            QFrame#NetworkStateBadge[networkState="success"] {{
                border-color: {palette['success']};
                background-color: {palette['success_soft']};
            }}

            QFrame#NetworkStateBadge[networkState="connected"] QLabel#NetworkStateLabel,
            QFrame#NetworkStateBadge[networkState="success"] QLabel#NetworkStateLabel {{
                color: {palette['success']};
            }}

            QFrame#NetworkStateBadge[networkState="disconnecting"] {{
                border-color: {palette['warning']};
                background-color: {palette['warning_soft']};
            }}

            QFrame#NetworkStateBadge[networkState="disconnecting"] QLabel#NetworkStateLabel {{
                color: {palette['warning']};
            }}

            QFrame#NetworkStateBadge[networkState="failure"] {{
                border-color: {palette['danger']};
                background-color: {palette['danger_soft']};
            }}

            QFrame#NetworkStateBadge[networkState="failure"] QLabel#NetworkStateLabel {{
                color: {palette['danger']};
            }}

            QWidget#TrafficStatsBadge {{
                min-height: 24px;
                padding: 0;
                border: none;
                background-color: transparent;
            }}

            QFrame#TrafficDirectionBadge {{
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['raised']};
                color: {palette['text_strong']};
            }}

            QFrame#TrafficDirectionBadge QLabel {{
                border: none;
                padding: 0;
                background-color: transparent;
                color: {palette['text_strong']};
            }}

            QFrame#TrafficDirectionBadge[direction="download"] QLabel#TrafficSpeedLabel {{
                color: {palette['metrics_download']};
                font-weight: 600;
            }}

            QFrame#TrafficDirectionBadge[direction="upload"] QLabel#TrafficSpeedLabel {{
                color: {palette['metrics_upload']};
                font-weight: 600;
            }}

            QFrame#TrafficDirectionBadge QLabel#TrafficUsageLabel {{
                color: {palette['muted']};
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
