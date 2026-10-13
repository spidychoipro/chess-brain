"""Design tokens + one QSS sheet.

Qt stylesheets are not CSS2, so this sticks to the safe subset (colors,
borders, radii, padding, fonts). Everything else is layout work in the tabs.
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QWidget

# -- tokens -----------------------------------------------------------------
BG = "#12141a"
SURFACE = "#1b1e26"
SURFACE_2 = "#232733"
SURFACE_3 = "#2b3040"
BORDER = "#2c3140"
TEXT = "#e8eaf0"
MUTED = "#98a0b3"
ACCENT = "#5b8cff"
ACCENT_HI = "#6f9bff"
SUCCESS = "#3fbf7f"
DANGER = "#ef5f6b"
WARNING = "#f0b429"

STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif;
}}
QWidget {{
    color: {TEXT};
    font-size: 13px;
}}
#Root, QDialog {{
    background: {BG};
}}
#Sidebar {{
    background: {SURFACE};
    border-right: 1px solid {BORDER};
}}
#Header {{
    background: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}
#Brand {{
    font-size: 17px;
    font-weight: 700;
    color: {TEXT};
}}
#BrandGlyph {{
    font-size: 22px;
}}
#HeaderSub {{
    color: {MUTED};
    font-size: 12px;
}}

QFrame#Card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#CardFlat {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QLabel[role="h1"] {{ font-size: 20px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 15px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="small"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="big"] {{ font-size: 30px; font-weight: 700; }}
QLabel[role="caption"] {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}

QLabel[state="success"] {{ color: {SUCCESS}; font-weight: 600; }}
QLabel[state="danger"] {{ color: {DANGER}; font-weight: 600; }}
QLabel[state="muted"] {{ color: {MUTED}; }}

QLabel#LineText {{
    font-family: "Cascadia Mono", "Consolas", "D2Coding", monospace;
    font-size: 17px;
    color: {TEXT};
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 18px;
}}
QLabel#AnswerText {{
    font-family: "Cascadia Mono", "Consolas", "D2Coding", monospace;
    font-size: 15px;
    color: {MUTED};
}}

QListWidget#Nav {{
    background: transparent;
    border: none;
    outline: 0;
    padding: 6px;
}}
QListWidget#Nav::item {{
    color: {MUTED};
    padding: 10px 12px;
    border-radius: 9px;
    margin: 2px 6px;
}}
QListWidget#Nav::item:hover {{
    background: {SURFACE_2};
    color: {TEXT};
}}
QListWidget#Nav::item:selected {{
    background: {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}

QPushButton {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 14px;
}}
QPushButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed {{ background: #1f2431; }}
QPushButton:disabled {{ color: #5a6272; background: #1b1e26; border-color: #232733; }}
QPushButton[variant="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_HI}; border-color: {ACCENT_HI}; }}
QPushButton[variant="success"] {{
    background: {SUCCESS}; border: 1px solid {SUCCESS};
    color: #06210f; font-weight: 700;
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid {BORDER};
    color: {MUTED};
}}
QPushButton[variant="ghost"]:hover {{ color: {TEXT}; border-color: {ACCENT}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit#AnswerInput {{
    font-family: "Cascadia Mono", "Consolas", "D2Coding", monospace;
    font-size: 19px;
    padding: 12px 14px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: 0;
}}

QTableWidget {{
    background: {SURFACE};
    alternate-background-color: #1f232c;
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: #262b38;
}}
QTableWidget::item {{ padding: 6px 8px; }}
QTableWidget::item:selected {{ background: #2b3a5e; color: {TEXT}; }}
QHeaderView::section {{
    background: {SURFACE_2};
    color: {MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 9px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {SURFACE_2}; border: none; }}

QProgressBar {{
    background: {SURFACE_2};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}

QPlainTextEdit {{
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px;
    color: {MUTED};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QWidget#SettingsContent {{ background: transparent; }}

QCheckBox {{ spacing: 8px; color: {MUTED}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 5px;
    border: 1px solid #3a4152;
    background: {SURFACE_2};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: #333a4a; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3f4759; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: #333a4a; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def apply(app) -> None:
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))


def card(parent: QWidget | None = None, flat: bool = False) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("CardFlat" if flat else "Card")
    return f


def label(
    text: str = "",
    role: str | None = None,
    state: str | None = None,
    parent: QWidget | None = None,
) -> QLabel:
    lbl = QLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    if state:
        lbl.setProperty("state", state)
    return lbl


def set_state(widget: QWidget, state: str) -> None:
    """Change a dynamic QSS property and repolish so it takes effect."""
    widget.setProperty("state", state)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
