"""Stats page: per-source accuracy and the mistakes I keep missing."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import db
from core.utils import loss_label
from ui import theme


class StatsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cb_source = QComboBox()
        self.cb_source.addItem("사람", "human")
        self.cb_source.addItem("봇", "bot")
        self.cb_source.addItem("전체", "both")

        self.lbl_acc = theme.label("", role="big")
        self.lbl_acc_caption = theme.label("정답률 (실수 복습 기준)", role="caption")

        summary = theme.card()
        slay = QVBoxLayout(summary)
        slay.setContentsMargins(18, 16, 18, 16)
        slay.setSpacing(4)
        slay.addWidget(self.lbl_acc)
        slay.addWidget(self.lbl_acc_caption)

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("variant", "ghost")
        self.btn_refresh.clicked.connect(self.refresh)

        toolbar = QHBoxLayout()
        toolbar.addWidget(theme.label("상대", role="muted"))
        toolbar.addWidget(self.cb_source)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_refresh)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["손실", "상대", "내 수", "추천 수", "틀린 횟수"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("기록/통계", role="h1"))
        layout.addLayout(toolbar)
        layout.addWidget(summary)
        layout.addWidget(theme.label("자주 틀리는 실수 TOP", role="h2"))
        self.lbl_tip = theme.label(
            "여기 위에 있는 실수부터 복습하면 효율이 좋아.", role="small"
        )
        layout.addWidget(self.lbl_tip)
        layout.addWidget(self.table, 1)

        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        recent = db.recent_review_stats(src)
        total = recent["total"]
        self.lbl_acc.setText(f"{recent['first_try']/total*100:.1f}%" if total else "기록 없음")
        self.lbl_acc_caption.setText(
            f"최근 30일 첫 시도 성공 · {total}회 중 {recent['first_try']}회 · 정답 확인 {recent['reveals']}회 (업데이트 이후)"
        )
        rows = db.hardest_mistakes(limit=15, source=src)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                loss_label(r),
                "봇" if r["source"] == "bot" else "사람",
                r["my_san"],
                r["best_san"],
                str(r["wrong"]),
            ]
            for c, v in enumerate(vals):
                self.table.setItem(i, c, QTableWidgetItem(v))
        self.table.resizeColumnsToContents()
        if rows:
            self.lbl_tip.setText("여기 위에 있는 실수부터 복습하면 효율이 좋아.")
        else:
            self.lbl_tip.setText(
                "아직 자주 틀린 기록이 없어. '내 실수' 탭에서 복습을 시작하면 여기에 쌓여."
            )