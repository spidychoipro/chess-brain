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
        self.cb_mode.addItem("노테이션 배우기 (기초부터)", "notation")

        self.cb_source = QComboBox()
        self.cb_source.addItem("사람", "human")
        self.cb_source.addItem("봇", "bot")
        self.cb_source.addItem("전체", "both")

        self.cb_only_wrong = QCheckBox("틀린 문제만")
        self.lbl_stats = theme.label("", role="muted")
        self.btn_start = QPushButton("시작")
        self.btn_start.setProperty("variant", "primary")
        self.btn_start.clicked.connect(self._start)

        toolbar = theme.card(flat=True)
        tool = QHBoxLayout(toolbar)
        tool.setContentsMargins(14, 10, 14, 10)
        tool.addWidget(QLabel("모드"))
        tool.addWidget(self.cb_mode)
        tool.addWidget(QLabel("상대"))
        tool.addWidget(self.cb_source)
        tool.addWidget(self.cb_only_wrong)
        tool.addStretch(1)
        tool.addWidget(self.btn_start)

        desc = theme.card()
        dlay = QVBoxLayout(desc)
        dlay.setContentsMargins(18, 16, 18, 16)
        dlay.setSpacing(8)
        self.desc_heading = theme.label("", role="h2")
        self.desc_body = theme.label("", role="muted")
        self.desc_body.setWordWrap(True)
        dlay.addWidget(self.desc_heading)
        dlay.addWidget(self.desc_body)

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
        mode = self.cb_mode.currentData()
        self.cb_source.setVisible(mode != "notation")
        self.cb_only_wrong.setVisible(mode != "notation")
        descriptions = {
            "notation": ("기물 글자부터 기보 읽기까지", "1단계 기물과 글자 → 2단계 칸 이름 → 3단계 수 읽기 → 4단계 머릿속 보드. 진행은 저장됩니다."),
            "recall": ("실제 대국의 기보 재현", "내가 실제로 둔 수를 보드에서 재현합니다. 좋은 수 찾기와는 구분됩니다. 한 번에 최대 10문제를 풉니다."),
            "drill": ("내 실수에서 더 좋은 수 찾기", "복습 시간이 된 실수와 새 실수를 최대 10개씩 풉니다. 정답 뒤에는 상대 응수와 추천 변형을 확인할 수 있습니다."),
        }
        heading, body = descriptions[mode]
        self.desc_heading.setText(heading)
        self.desc_body.setText(body)
        counts = db.problem_counts(self._src())
        self.lbl_stats.setText(
            f"문제 {counts['total']}개  ·  지금 복습 {counts['due']}개"
        )

    def _start(self) -> None:
        mode = self.cb_mode.currentData()
        if mode == "notation":
            from ui.notation import NotationDialog

            NotationDialog(self).exec()
            return
        soft = mode == "recall"
        items = (db.problems_due(limit=10, source=self._src(),
                   only_wrong=self.cb_only_wrong.isChecked(), soft=True, origin="line") if soft else
                 db.mistakes_due(limit=10, source=self._src(), only_wrong=self.cb_only_wrong.isChecked()))
        if not items:
            QMessageBox.information(
                self, "트레이닝", "문제가 없습니다. 홈에서 대국을 가져오거나 분석을 먼저 해보세요."
            )
            return
        cfg = cfg_mod.load_config()
        title = "다음 수 맞추기" if soft else "실수 집중 훈련"
        dialog = ReviewDialog(
            items,
            "problem" if soft else "mistake",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title=title,
            parent=self,
        )
        dialog.exec()
        self.refresh()