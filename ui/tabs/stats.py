"""Stats tab: per-source accuracy and the mistakes I keep missing."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import db


class StatsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cb_source = QComboBox()
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Both", "both")
        self.btn = QPushButton("새로고침")
        self.btn.clicked.connect(self.refresh)
        self.lbl = QLabel("-")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["loss", "src", "내가 둔 수", "정답", "틀린 횟수"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        top = QHBoxLayout()
        top.addWidget(QLabel("소스"))
        top.addWidget(self.cb_source)
        top.addStretch(1)
        top.addWidget(self.btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.lbl)
        layout.addWidget(QLabel("자주 틀리는 실수 TOP"))
        layout.addWidget(self.table, 1)

        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        acc = db.source_accuracy(src)
        self.lbl.setText(
            f"정답률 {acc['accuracy']}% (맞음 {acc['correct']} · 틀림 {acc['wrong']})"
        )
        rows = db.hardest_mistakes(limit=15, source=src)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            for c, v in enumerate(
                [
                    f"{r['loss']:.2f}",
                    r["source"],
                    r["my_san"],
                    r["best_san"],
                    str(r["wrong"]),
                ]
            ):
                self.table.setItem(i, c, QTableWidgetItem(v))
        self.table.resizeColumnsToContents()
