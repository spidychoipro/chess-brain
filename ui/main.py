"""Main window: sidebar nav + header + stacked pages.

Mistakes stay the first page - that is the point of the app.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import db
from ui import theme
from ui.tabs.home import HomeTab
from ui.tabs.mistakes import MistakesTab
from ui.tabs.settings import SettingsTab
from ui.tabs.stats import StatsTab
from ui.tabs.training import TrainingTab

PAGES = [
    ("♟  내 실수", "mistakes"),
    ("♞  기보 트레이닝", "training"),
    ("♜  홈", "home"),
    ("♝  기록/통계", "stats"),
    ("⚙  설정", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("chess-brain")
        self.resize(1080, 680)

        db.init_db()

        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -- sidebar --------------------------------------------------------
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setFixedWidth(190)
        for title, _key in PAGES:
            self.nav.addItem(title)

        # -- right column ---------------------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        glyph = QLabel("♞")
        glyph.setObjectName("BrandGlyph")
        brand = QLabel("chess-brain")
        brand.setObjectName("Brand")
        self.lbl_sub = theme.label("", role="small")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("variant", "ghost")
        self.btn_refresh.clicked.connect(self._refresh_all)
        header_layout.addWidget(glyph)
        header_layout.addWidget(brand)
        header_layout.addSpacing(12)
        header_layout.addWidget(self.lbl_sub, 1)
        header_layout.addWidget(self.btn_refresh)

        self.stack = QStackedWidget()
        self.mistakes = MistakesTab()
        self.training = TrainingTab()
        self.home = HomeTab()
        self.stats = StatsTab()
        self.settings = SettingsTab()
        for page in (self.mistakes, self.training, self.home, self.stats, self.settings):
            self.stack.addWidget(page)

        right_layout.addWidget(header)
        right_layout.addWidget(self.stack, 1)

        root_layout.addWidget(self.nav)
        root_layout.addWidget(right, 1)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self._on_nav)
        self.settings.config_saved.connect(self._refresh_all)
        self.nav.setCurrentRow(0)

    # -- behavior -----------------------------------------------------------

    def _on_nav(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.widget(index)
        if hasattr(page, "refresh"):
            page.refresh()
        self._update_sub()

    def _update_sub(self) -> None:
        mc = db.mistake_counts()
        pc = db.problem_counts()
        self.lbl_sub.setText(
            f"복습할 실수 {mc['due']} · 노테이션 {pc['due']} · 실수 총 {mc['total']}"
        )

    def _refresh_all(self) -> None:
        for page in (self.mistakes, self.training, self.home, self.stats, self.settings):
            if hasattr(page, "refresh"):
                page.refresh()
        self._update_sub()