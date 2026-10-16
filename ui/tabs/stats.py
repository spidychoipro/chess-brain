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
from ui import theme


class StatsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cb_source = QComboBox()
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Both", "both")

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
        toolbar.addWidget(theme.label("소스", role="muted"))
        toolbar.addWidget(self.cb_source)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_refresh)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["손실(loss)", "소스", "내가 둔 수", "엔진 정답", "틀린 횟수"]
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
        acc = db.source_accuracy(src)
        self.lbl_acc.setText(f"{acc['accuracy']}%")
        self.lbl_acc_caption.setText(
            f"정답률 (실수 복습 기준) · 맞음 {acc['correct']} · 틀림 {acc['wrong']}"
        )
        rows = db.hardest_mistakes(limit=15, source=src)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                f"{r['loss']:.2f}",
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