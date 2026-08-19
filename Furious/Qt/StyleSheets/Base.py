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

"""Provide global, page, dialog, settings, and metrics QSS."""

from textwrap import dedent


def baseStyleSheet(palette):
    """Return base application and page component styling."""
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

            QFrame#NavigationPanel {{
                border: none;
                border-right: 1px solid {palette['border']};
                background-color: {palette['panel_alt']};
            }}

            QFrame#NavigationRailPlaceholder {{
                border: none;
                background-color: {palette['panel_alt']};
            }}

            QFrame#AppMessageBoxMask {{
                border: none;
                background-color: rgba(0, 0, 0, 84);
            }}

            QDialog#AppMessageBox {{
                border: none;
                background-color: transparent;
            }}

            QFrame#AppMessageBoxSurface {{
                border: 1px solid {palette['border_strong']};
                border-radius: 10px;
                background-color: {palette['panel']};
            }}

            QFrame#AppMessageBoxContent,
            QWidget#AppMessageBoxTextWidget,
            QScrollArea#AppMessageBoxTextViewport,
            QScrollArea#AppMessageBoxTextViewport > QWidget > QWidget,
            QLabel#AppMessageBoxIcon {{
                border: none;
                background-color: transparent;
            }}

            QLabel#AppMessageBoxTitle {{
                padding: 0;
                border: none;
                background-color: transparent;
                color: {palette['text_strong']};
            }}

            QLabel#AppMessageBoxBody {{
                padding: 0;
                border: none;
                background-color: transparent;
                color: {palette['muted']};
            }}

            QFrame#AppMessageBoxButtonBar {{
                border-top: 1px solid {palette['border']};
                border-left: none;
                border-right: none;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
                background-color: {palette['panel_alt']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton {{
                padding: 5px 14px;
                border: 1px solid {palette['border']};
                border-radius: 6px;
                background-color: {palette['input']};
                color: {palette['text']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton:hover {{
                border-color: {palette['border_strong']};
                background-color: {palette['hover']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton:pressed {{
                background-color: {palette['pressed']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton[messageBoxRole="primary"] {{
                border-color: {palette['accent']};
                background-color: {palette['accent']};
                color: {palette['accent_text']};
                font-weight: 600;
            }}

            QFrame#AppMessageBoxButtonBar QPushButton[messageBoxRole="primary"]:hover {{
                border-color: {palette['accent_hover']};
                background-color: {palette['accent_hover']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton[messageBoxRole="primary"]:pressed {{
                border-color: {palette['accent_pressed']};
                background-color: {palette['accent_pressed']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton[messageBoxRole="destructive"] {{
                border-color: {palette['danger']};
                background-color: {palette['danger_soft']};
                color: {palette['danger']};
            }}

            QFrame#AppMessageBoxButtonBar QPushButton:disabled {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
                color: {palette['disabled']};
            }}

            QStackedWidget#ApplicationPageStack {{
                border: none;
                background-color: {palette['window']};
            }}

            QScrollArea#MetricsScrollArea,
            QWidget#MetricsPageContent,
            QScrollArea#SettingsScrollArea,
            QWidget#SettingsPageContent,
            QScrollArea#SubscriptionScrollArea,
            QWidget#SubscriptionPageContent,
            QWidget#HomePageContent,
            QWidget#LogPageContent {{
                border: none;
                background-color: {palette['window']};
            }}

            QLabel#MetricsPageTitle,
            QLabel#LogPageTitle,
            QLabel#SubscriptionPageTitle,
            QLabel#HomePageTitle,
            QLabel#SettingsPageTitle {{
                color: {palette['text_strong']};
                font-size: 16pt;
                font-weight: 600;
            }}

            QLabel#SettingsSectionTitle {{
                padding: 4px 2px;
                color: {palette['text_strong']};
                font-size: 12pt;
                font-weight: 600;
            }}

            QFrame#SettingsCard {{
                border: 1px solid {palette['border']};
                border-radius: 9px;
                background-color: {palette['panel']};
            }}

            QFrame#SettingsCard:hover {{
                border-color: {palette['border_strong']};
                background-color: {palette['panel_alt']};
            }}

            QFrame#SubscriptionEditorForm {{
                border: 1px solid {palette['border']};
                border-radius: 9px;
                background-color: {palette['panel']};
            }}

            QLabel#SettingsCardTitle {{
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QLabel#SettingsCardDescription {{
                color: {palette['muted']};
            }}

            QPushButton#SettingsActionButton {{
                min-width: 82px;
            }}

            QPushButton#SettingsLinkButton {{
                min-height: 20px;
                padding: 0;
                border: none;
                background-color: transparent;
                color: {palette['accent']};
            }}

            QPushButton#SettingsLinkButton:hover {{
                color: {palette['text_strong']};
            }}

            QCheckBox#SettingsToggle::indicator {{
                width: 34px;
                height: 18px;
                border: 1px solid {palette['border_strong']};
                border-radius: 9px;
                background-color: {palette['raised']};
                image: none;
            }}

            QCheckBox#SettingsToggle::indicator:hover {{
                border-color: {palette['accent']};
                background-color: {palette['hover']};
            }}

            QCheckBox#SettingsToggle::indicator:checked {{
                border-color: {palette['accent']};
                background-color: {palette['accent']};
                image: none;
            }}

            QCheckBox#SettingsToggle::indicator:disabled {{
                border-color: {palette['border']};
                background-color: {palette['raised']};
                image: none;
            }}

            QFrame#MetricsSection {{
                border: 1px solid {palette['border']};
                border-radius: 10px;
                background-color: {palette['panel']};
            }}

            QLabel#MetricsSectionTitle {{
                color: {palette['text_strong']};
                font-size: 12pt;
                font-weight: 600;
            }}

            QFrame#MetricCard {{
                border: 1px solid {palette['border']};
                border-radius: 8px;
                background-color: {palette['panel_alt']};
            }}

            QLabel#MetricCardTitle {{
                color: {palette['muted']};
                font-weight: 600;
            }}

            QLabel#EndpointStatusLabel {{
                color: {palette['text_strong']};
                font-weight: 600;
            }}

            QWidget#EndpointStatusWidget {{
                background-color: transparent;
            }}

            QLabel#EndpointFieldName {{
                color: {palette['muted']};
            }}

            QLabel#EndpointFieldValue {{
                color: {palette['text_strong']};
            }}

            QWidget#EndpointFieldValueContainer {{
                background-color: transparent;
            }}

            QLabel#EndpointNoteLabel {{
                color: {palette['muted']};
            }}

            QPushButton#EndpointCopyButton {{
                min-width: 34px;
                padding: 0;
            }}

            QWidget#EndpointMapWidget {{
                border: none;
                background-color: transparent;
            }}

            QWidget#MetricsGraphWidget {{
                border: none;
                background-color: transparent;
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

    """).strip()
