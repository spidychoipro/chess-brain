"""Main window: sidebar nav + header + stacked pages.

Home is the entry point: it shows today's work and the actions that lead to it.
"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QTimer

from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core import db
from ui import theme

PAGES = [
    ("홈", "home"),
    ("내 실수", "mistakes"),
    ("기보 트레이닝", "training"),
    ("기록/통계", "stats"),
    ("설정", "settings"),
]

ICON_KEYS = {
    "home": "home",
    "mistakes": "mistakes",
    "training": "training",
    "stats": "stats",
    "settings": "settings",
}

# 탭 클래스는 첫 방문 때 만들어서 시작 부하를 줄인다.
def _tab_classes():
    from ui.tabs.home import HomeTab
    from ui.tabs.mistakes import MistakesTab
    from ui.tabs.settings import SettingsTab
    from ui.tabs.stats import StatsTab
    from ui.tabs.training import TrainingTab

    return {
        "mistakes": MistakesTab,
        "training": TrainingTab,
        "home": HomeTab,
        "stats": StatsTab,
        "settings": SettingsTab,
    }


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("chess-brain")
        self.resize(1080, 680)
        self._pages = {}

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
        for title, key in PAGES:
            self.nav.addItem(QListWidgetItem(theme.icon(ICON_KEYS[key]), title))

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
        self.lbl_sync = theme.label("대국 확인 중…", role="small")
        self.lbl_sync.setWordWrap(True)
        self.btn_update = QPushButton("업데이트 확인")
        self.btn_update.setProperty("variant", "ghost")
        self.btn_update.clicked.connect(self._check_updates)
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("variant", "ghost")
        self.btn_refresh.clicked.connect(self._refresh_all)
        header_layout.addWidget(glyph)
        header_layout.addWidget(brand)
        header_layout.addSpacing(12)
        header_layout.addWidget(self.lbl_sub, 1)
        header_layout.addWidget(self.lbl_sync)
        header_layout.addWidget(self.btn_update)
        header_layout.addWidget(self.btn_refresh)

        self.stack = QStackedWidget()

        right_layout.addWidget(header)
        right_layout.addWidget(self.stack, 1)

        root_layout.addWidget(self.nav)
        root_layout.addWidget(right, 1)
        self.setCentralWidget(root)

        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setCurrentRow(0)

        home = self._page("home")
        home.openReview.connect(self._goto_review)
        home.openImport.connect(self._goto_import)
        home.openSetup.connect(self._goto_setup)
        home.analyze.connect(self._goto_analyze)

        # 앱을 켜지 않은 사이 쌓인 대국을 자동으로 따라잡는다. 켜져 있는 동안에도
        # 10분마다 한 번씩 확인해서 드라이브에 새 대국이 들어오면 바로 읽는다.
        self._auto_worker = None
        # 켜질 때는 과거 게임 전부를 훑는다(방치 기간이 길어도 놓치지 않게).
        # 켜져 있는 동안에는 최근 7일만 가볍게 확인한다.
        QTimer.singleShot(700, lambda: self._auto_catch_up(fetch_all=True))
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(10 * 60 * 1000)
        self._sync_timer.timeout.connect(lambda: self._auto_catch_up(fetch_all=False))
        self._sync_timer.start()

    # -- pages (lazy) -------------------------------------------------------

    def _page(self, key: str) -> QWidget:
        if key not in self._pages:
            page = _tab_classes()[key]()
            self._pages[key] = page
            self.stack.addWidget(page)
            if key == "settings":
                page.config_saved.connect(self._refresh_all)
        return self._pages[key]

    # -- behavior -----------------------------------------------------------

    def _navigate(self, key):
        self.nav.setCurrentRow(next(i for i, (_, k) in enumerate(PAGES) if k == key))

    def _goto_review(self) -> None:
        self._navigate("mistakes")
        self._page("mistakes")._review()

    def _goto_import(self) -> None:
        self._navigate("settings")
        settings = self._page("settings")
        settings._set_status("대국 가져오기를 시작했어요. 결과는 아래 로그에 나와요.", "accent")
        settings._sync_local()

    def _goto_setup(self, target: str) -> None:
        self._navigate("settings")
        self._page("settings").focus_field(target)

    def _goto_analyze(self, source: str) -> None:
        self._navigate("mistakes")
        self._page("mistakes")._analyze(source)

    def _check_updates(self) -> None:
        self._navigate("settings")
        settings = self._page("settings")
        if not getattr(self, "_update_connected", False):
            settings.update_checked.connect(self._on_update_checked)
            self._update_connected = True
        settings.check_update()

    def _on_update_checked(self, result: dict) -> None:
        if not result.get("ok"):
            self.show_toast("업데이트 확인 실패 — 네트워크를 확인해보세요.")
            return
        latest = result.get("latest") or "?"
        if result.get("available"):
            self.show_toast(f"새 버전 v{latest} 있어요. 아래 링크에서 받을 수 있어요.")
        else:
            self.show_toast(f"현재 v{result['current']} — 최신 버전이에요.")

    def show_toast(self, text: str) -> None:
        parent = self.centralWidget()
        toast = QLabel(text, parent)
        toast.setObjectName("Toast")
        toast.setWordWrap(True)
        width = min(520, max(280, parent.width() - 120))
        toast.setGeometry(60, 66, width, 44)
        effect = QGraphicsOpacityEffect(toast)
        toast.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.start()
        self._toast_animation = animation  # keep it alive until it finishes
        toast.show()
        QTimer.singleShot(3200, toast.deleteLater)

    def _fade_page(self, page: QWidget) -> None:
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(160)
        animation.setStartValue(0.55)
        animation.setEndValue(1.0)

        def _cleanup() -> None:
            page.setGraphicsEffect(None)
            self._page_effect = None
            self._page_animation = None

        animation.finished.connect(_cleanup)
        self._page_effect = effect
        self._page_animation = animation
        animation.start()

    def _on_nav(self, index: int) -> None:
        for i, (_, key) in enumerate(PAGES):
            color = "#ffffff" if i == index else theme.MUTED
            self.nav.item(i).setIcon(theme.icon(ICON_KEYS[key], color))
        key = PAGES[index][1]
        page = self._page(key)
        self.stack.setCurrentWidget(page)
        self._fade_page(page)
        if hasattr(page, "refresh"):
            page.refresh()
        self._update_sub()

    def _update_sub(self) -> None:
        mc = db.mistake_counts()
        pc = db.problem_counts()
        self.lbl_sub.setText(
            f"복습할 실수 {mc['due']} · 복습할 문제 {pc['due']} · 실수 총 {mc['total']}"
        )

    def _refresh_all(self) -> None:
        for page in self._pages.values():
            if hasattr(page, "refresh"):
                page.refresh()
        self._update_sub()

    # -- automatic import ---------------------------------------------------

    def _auto_catch_up(self, fetch_all: bool = False) -> None:
        from core import config as cfg_mod
        from core import pipeline
        from ui.worker import PipelineWorker

        if getattr(self, "_selftest", False):
            # 빌드 검증은 1.5초 만에 끝나는데, 그 사이 시작한 스레드가 남으면
            # 종료 순간 크래시한다. 검증 모드에서는 자동 확인을 하지 않는다.
            self.lbl_sync.setText("자동 확인 건너뜀 (검증 모드)")
            return
        if self._auto_worker is not None and self._auto_worker.isRunning():
            return
        self.lbl_sync.setText("새 대국 확인 중…")
        worker = PipelineWorker(
            pipeline.auto_catch_up, cfg=cfg_mod.load_config(), fetch_all=fetch_all
        )
        self._auto_worker = worker
        worker.done.connect(self._on_auto_caught_up)
        worker.failed.connect(
            lambda msg: self.lbl_sync.setText(f"대국 확인 실패: {msg}")
        )
        worker.start()

    def _on_auto_caught_up(self, result: dict) -> None:
        new = int(result.get("new_games", 0) or 0)
        fetched = int(result.get("fetched", 0) or 0)
        if new:
            self.lbl_sync.setText(f"새 대국 {new}개 가져옴")
            self.show_toast(f"방치한 사이 대국 {new}개를 가져왔어요.")
        elif fetched:
            self.lbl_sync.setText(f"chess.com PGN {fetched}개 받음 · 이미 있는 대국")
        else:
            self.lbl_sync.setText("새 대국 없음 · 최신 상태")
        warnings = result.get("warnings") or []
        if warnings:
            self.lbl_sync.setText(self.lbl_sync.text() + " · " + str(warnings[0]))
        self._refresh_all()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt name
        running = [getattr(page, "_worker", None) for page in self._pages.values()]
        running.append(getattr(self, "_auto_worker", None))
        running = [worker for worker in running if worker is not None and worker.isRunning()]
        if running:
            for worker in running:
                worker.requestInterruption()
            self.lbl_sub.setText("진행 중인 작업을 정리한 뒤 종료합니다…")
            event.ignore()
            QTimer.singleShot(400, self.close)
            return
        # 붙여둔 드라이브가 있으면 앱을 닫을 때 함께 해제한다.
        try:
            from core import rclone as rclone_mod

            rclone_mod.stop_mount()
        except Exception:
            pass
        super().closeEvent(event)
