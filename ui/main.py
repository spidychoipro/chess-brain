"""Main window: mistakes first, everything else supports it."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from core import db
from ui.tabs.home import HomeTab
from ui.tabs.mistakes import MistakesTab
from ui.tabs.settings import SettingsTab
from ui.tabs.stats import StatsTab
from ui.tabs.training import TrainingTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("chess-brain")
        self.resize(980, 640)

        db.init_db()

        self.tabs = QTabWidget()
        self.mistakes = MistakesTab()
        self.training = TrainingTab()
        self.home = HomeTab()
        self.stats = StatsTab()
        self.settings = SettingsTab()

        # 메인(내 실수)이 첫 탭이다.
        self.tabs.addTab(self.mistakes, "내 실수")
        self.tabs.addTab(self.training, "기보 시각화 트레이닝")
        self.tabs.addTab(self.home, "홈")
        self.tabs.addTab(self.stats, "기록/통계")
        self.tabs.addTab(self.settings, "설정")
        self.tabs.setCurrentIndex(0)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.settings.config_saved.connect(self._refresh_all)
        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _refresh_all(self) -> None:
        for w in (self.mistakes, self.training, self.home, self.stats):
            if hasattr(w, "refresh"):
                w.refresh()
