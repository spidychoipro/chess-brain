"""Sub page: 기보 시각화 트레이닝.

Two modes over the same data:
  * Recall - keep the lines flowing, soft weighting.
  * Drill  - hammer what I keep getting wrong, mistake-derived first.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import db
from ui import theme
from ui.widgets import ReviewDialog


class TrainingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = cfg_mod.load_config()

        self.cb_mode = QComboBox()
        self.cb_mode.addItem("다음 수 맞추기 (Recall)", "recall")
        self.cb_mode.addItem("실수 집중 훈련 (Drill)", "drill")

        self.cb_source = QComboBox()
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Both", "both")

        self.cb_only_wrong = QCheckBox("자주 틀린 것만 (wrong ≥ 1)")
        self.lbl_stats = theme.label("", role="muted")
        self.btn_start = QPushButton("시작")
        self.btn_start.setProperty("variant", "primary")
        self.btn_start.clicked.connect(self._start)

        toolbar = theme.card(flat=True)
        tool = QHBoxLayout(toolbar)
        tool.setContentsMargins(14, 10, 14, 10)
        tool.addWidget(QLabel("모드"))
        tool.addWidget(self.cb_mode)
        tool.addWidget(QLabel("소스"))
        tool.addWidget(self.cb_source)
        tool.addWidget(self.cb_only_wrong)
        tool.addStretch(1)
        tool.addWidget(self.btn_start)

        desc = theme.card()
        dlay = QVBoxLayout(desc)
        dlay.setContentsMargins(18, 16, 18, 16)
        dlay.setSpacing(8)
        dlay.addWidget(theme.label("보드에서 말을 옮겨서 다음 수를 둔다", role="h2"))
        for line in [
            "- 포지션을 보여주고, 보드에서 기물을 클릭해 다음 수를 둔다. 노테이션 몰라도 된다.",
            "- 정답 → 잠깐 피드백 후 다음 문제. 오답 → 정답을 보드에 화살표로 보여주고, 같은 문제를 곧바로 다시 낸다.",
            "- Drill 모드는 자주 틀린 문제와 실수에서 파생된 문제를 더 자주 뽑는다.",
        ]:
            dlay.addWidget(theme.label(line, role="muted"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("기보 시각화 트레이닝", role="h1"))
        layout.addWidget(toolbar)
        layout.addWidget(self.lbl_stats)
        layout.addWidget(desc)
        layout.addStretch(1)

        self.cb_mode.currentIndexChanged.connect(self.refresh)
        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.cb_only_wrong.stateChanged.connect(self.refresh)

        idx = self.cb_mode.findData(cfg_mod.get(cfg, "training.default_mode", "recall"))
        self.cb_mode.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.cb_source.findData(cfg_mod.get(cfg, "training.default_source", "bot"))
        self.cb_source.setCurrentIndex(idx if idx >= 0 else 0)
        self.refresh()

    def _src(self):
        source = self.cb_source.currentData()
        return None if source == "both" else source

    def refresh(self) -> None:
        counts = db.problem_counts(self._src())
        self.lbl_stats.setText(
            f"문제 {counts['total']}개  ·  지금 복습할 것(due) {counts['due']}개"
        )

    def _start(self) -> None:
        mode = self.cb_mode.currentData()
        soft = mode == "recall"
        items = db.problems_due(
            source=self._src(),
            only_wrong=self.cb_only_wrong.isChecked(),
            soft=soft,
        )
        if not items:
            QMessageBox.information(
                self, "트레이닝", "문제가 없습니다. 설정 탭에서 드라이브 동기화를 먼저 하세요."
            )
            return
        cfg = cfg_mod.load_config()
        title = "다음 수 맞추기" if soft else "실수 집중 훈련"
        dialog = ReviewDialog(
            items,
            "problem",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title=title,
            parent=self,
        )
        dialog.exec()
        self.refresh()