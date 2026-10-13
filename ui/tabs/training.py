"""Sub tab: 기보 시각화 트레이닝.

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
from ui.widgets import ReviewDialog


class TrainingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = cfg_mod.load_config()

        self.cb_mode = QComboBox()
        self.cb_mode.addItem("다음 수 맞추기 (Recall)", "recall")
        self.cb_mode.addItem("노테이션 연습 (Drill)", "drill")

        self.cb_source = QComboBox()
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Both", "both")

        self.cb_only_wrong = QCheckBox("자주 틀린 것만 (wrong>=1)")
        self.lbl_stats = QLabel("-")
        self.btn_start = QPushButton("시작")

        top = QHBoxLayout()
        top.addWidget(QLabel("모드"))
        top.addWidget(self.cb_mode)
        top.addWidget(QLabel("소스"))
        top.addWidget(self.cb_source)
        top.addWidget(self.cb_only_wrong)
        top.addStretch(1)
        top.addWidget(self.btn_start)

        hint = QLabel(
            "보드 없이 기보만 보고 다음 수를 SAN 으로 입력한다. "
            "오답이면 정답을 보여주고 곧바로 같은 문제를 다시 낸다."
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(hint)
        layout.addWidget(self.lbl_stats)
        layout.addStretch(1)

        self.btn_start.clicked.connect(self._start)
        self.cb_mode.currentIndexChanged.connect(self.refresh)
        self.cb_source.currentIndexChanged.connect(self.refresh)

        # 설정 기본값 반영
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
        self.lbl_stats.setText(f"문제 {counts['total']}개 · 지금 복습할 것(due) {counts['due']}개")

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
        title = "다음 수 맞추기" if soft else "노테이션 연습"
        dialog = ReviewDialog(
            items,
            "problem",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title=title,
            parent=self,
        )
        dialog.exec()
        self.refresh()
