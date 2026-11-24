"""Design tokens + one QSS sheet.

Qt stylesheets are not CSS2, so this sticks to the safe subset (colors,
borders, radii, padding, fonts). Everything else is layout work in the tabs.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QLabel, QWidget

# -- tokens -----------------------------------------------------------------
BG = "#0f1115"
SURFACE = "#1c1f24"
SURFACE_2 = "#252a35"
SURFACE_3 = "#303746"
BORDER = "#313847"
TEXT = "#e8eaf0"
MUTED = "#98a0b3"
ACCENT = "#5b8cff"
ACCENT_HI = "#6f9bff"
# 버튼·진행바 배경용. ACCENT 그대로 쓰면 흰 글자 대비가 3.16:1이라 AA 미달.
ACCENT_STRONG = "#2f5fc4"
ACCENT_STRONG_HI = "#3a6bd8"
SUCCESS = "#3fbf7f"
DANGER = "#ef5f6b"
WARNING = "#f0b429"

# Windows 기본 고정 폰트를 쓴다. Noto Sans KR / Cascadia Mono 는 설치된 게
# variable font라 Qt DirectWrite에서 획이 뒤섞여 보인다. 정적 폰트로 고정.
FONT_UI = "Malgun Gothic"
FONT_MONO = "Consolas"

STYLESHEET = f"""
* {{
    font-family: "{FONT_UI}";
}}
QWidget {{
    color: {TEXT};
    font-size: 14px;
}}
#Toast {{
    background: {SURFACE_3};
    color: {TEXT};
    border: 1px solid {ACCENT_STRONG};
    border-radius: 10px;
    padding: 12px 16px;
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
    font-family: "Segoe UI Symbol";
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
QFrame#Card[state="primary"] {{
    background: {SURFACE_2};
    border: 1px solid {ACCENT};
}}

QLabel[role="h1"] {{ font-size: 26px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 17px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="small"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="big"] {{ font-size: 34px; font-weight: 700; }}
QLabel[role="caption"] {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel[state="accent"] {{ color: {ACCENT}; font-weight: 700; }}

QLabel[state="success"] {{ color: {SUCCESS}; font-weight: 600; }}
QLabel[state="danger"] {{ color: {DANGER}; font-weight: 600; }}
QLabel[state="muted"] {{ color: {MUTED}; }}
QLabel[role="empty"] {{
    color: {MUTED};
    font-size: 13px;
    padding: 16px;
    border: 1px dashed {BORDER};
    border-radius: 10px;
}}

QLabel#LineText {{
    font-family: "{FONT_MONO}";
    font-size: 17px;
    color: {TEXT};
    background: {BG};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 18px;
}}
QLabel#AnswerText {{
    font-family: "{FONT_MONO}";
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
    padding: 12px 14px;
    border-radius: 10px;
    margin: 2px 6px;
}}
QListWidget#Nav::item:hover {{
    background: {SURFACE_2};
    color: {TEXT};
}}
QListWidget#Nav::item:selected {{
    background: {ACCENT_STRONG};
    color: #ffffff;
    font-weight: 600;
}}

QPushButton {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 18px;
}}
QPushButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed {{ background: #1f2431; }}
QPushButton:disabled {{ color: #5a6272; background: #1b1e26; border-color: #232733; }}
QPushButton:focus {{ border: 1px solid {ACCENT}; }}
QPushButton[variant="primary"] {{
    background: {ACCENT_STRONG};
    border: 1px solid {ACCENT_STRONG};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background: {ACCENT_STRONG_HI}; border-color: {ACCENT_STRONG_HI}; }}
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
    selection-background-color: {ACCENT_STRONG};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit#AnswerInput {{
    font-family: "{FONT_MONO}";
    font-size: 19px;
    padding: 12px 14px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-style: solid;
    border-width: 6px 5px 0 5px;
    border-color: {MUTED} transparent transparent transparent;
    margin-right: 7px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_STRONG};
    outline: 0;
}}

QTableWidget {{
    background: {SURFACE};
    alternate-background-color: #1f232c;
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: #262b38;
    outline: 0;
}}
QTableWidget:focus {{ border: 1px solid {ACCENT}; }}
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
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {SURFACE_2}; border-radius: 4px; }}

QProgressBar {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    height: 18px;
    text-align: center;
    color: {TEXT};
    font-size: 11px;
}}
QProgressBar::chunk {{ background: {ACCENT_STRONG}; border-radius: 5px; }}

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
    app.setFont(QFont(FONT_UI, 10))


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


# -- icons -------------------------------------------------------------------
# Unicode chess glyphs look different per font and cannot be stroked cleanly.
# These tiny SVGs keep every nav item the same weight and alignment.
_ICON_SVG = {
    "home": "<path fill='{c}' d='M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z'/>",
    "mistakes": (
        "<circle cx='12' cy='12' r='9' fill='none' stroke='{c}' stroke-width='2'/>"
        "<rect x='11' y='6' width='2' height='8' rx='1' fill='{c}'/>"
        "<circle cx='12' cy='17' r='1.2' fill='{c}'/>"
    ),
    "training": (
        "<path fill='{c}' d='M5 20V9l5 2 2-7 7 5-4 11z'/>"
        "<circle cx='10' cy='8' r='1' fill='{BG}'/>"
    ),
    "curriculum": (
        "<path fill='{c}' d='M4 4h7a3 3 0 0 1 3 3v13a3 3 0 0 0-3-2H4z'/>"
        "<path fill='{c}' d='M20 4h-3a3 3 0 0 0-3 3v13a3 3 0 0 1 3-2h3z'/>"
    ),
    "logo": (
        "<rect x='1' y='1' width='22' height='22' rx='5' fill='{SURFACE}' "
        "stroke='{c}' stroke-width='1.5'/>"
        "<path fill='{c}' d='M6.5 18V9l4 2 1.5-6L17.5 9l-2 9z'/>"
        "<circle cx='12' cy='8' r='0.9' fill='{BG}'/>"
    ),
    "stats": (
        "<rect x='4' y='12' width='3' height='8' rx='1' fill='{c}'/>"
        "<rect x='10' y='7' width='3' height='13' rx='1' fill='{c}'/>"
        "<rect x='16' y='4' width='3' height='16' rx='1' fill='{c}'/>"
    ),
    "settings": (
        "<path stroke='{c}' stroke-width='2' d='M4 7h16M4 12h16M4 17h16'/>"
        "<circle cx='9' cy='7' r='2.5' fill='{SURFACE}' stroke='{c}' stroke-width='2'/>"
        "<circle cx='15' cy='12' r='2.5' fill='{SURFACE}' stroke='{c}' stroke-width='2'/>"
        "<circle cx='11' cy='17' r='2.5' fill='{SURFACE}' stroke='{c}' stroke-width='2'/>"
    ),
    "empty": (
        "<rect x='3' y='3' width='18' height='18' rx='2' fill='none' "
        "stroke='{c}' stroke-width='1.6'/>"
        "<path stroke='{c}' stroke-width='1.6' d='M3 9h18M3 15h18M9 3v18M15 3v18'/>"
        "<circle cx='12' cy='12' r='2.2' fill='{SURFACE}' stroke='{c}' stroke-width='1.6'/>"
    ),
}


def icon(key: str, color: str = MUTED) -> QIcon:
    """Build a 24px QIcon from an inline SVG path."""
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'>" + _ICON_SVG.get(
        key, _ICON_SVG["home"]
    ).format(c=color, BG=BG, SURFACE=SURFACE) + "</svg>"
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def icon_label(key: str, size: int = 44, color: str = MUTED) -> QLabel:
    """A centered icon for empty states and other decorative spots."""
    label = QLabel()
    label.setPixmap(icon(key, color).pixmap(size, size))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label
