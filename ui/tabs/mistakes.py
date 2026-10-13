"""Main tab: 내 실수(My Mistakes).

The mistake list is the point of the app. Reviewing it is spaced and
weighted, and every mistake also spawns a notation problem so the sub
feature reinforces the same weakness.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import db, pipeline
from ui.widgets import ReviewDialog
from ui.worker import PipelineWorker


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "-"
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


class MistakesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None

        self.cb_source = QComboBox()
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Both", "both")
        self.cb_only_wrong = QCheckBox("자주 틀린 것만 (wrong>=1)")

        self.lbl_stats = QLabel("-")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_review = QPushButton("실수 복습 시작")
        self.btn_analyze = QPushButton("Stockfish로 실수 분석")

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["loss", "src", "내가 둔 수", "정답", "맞음", "틀림", "다음 복습"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        top = QHBoxLayout()
        top.addWidget(QLabel("소스"))
        top.addWidget(self.cb_source)
        top.addWidget(self.cb_only_wrong)
        top.addStretch(1)
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_review)
        top.addWidget(self.btn_analyze)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.lbl_stats)
        layout.addWidget(self.table, 1)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_review.clicked.connect(self._review)
        self.btn_analyze.clicked.connect(self._analyze)
        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.cb_only_wrong.stateChanged.connect(self.refresh)
        self.refresh()

    # -- data ---------------------------------------------------------------

    def refresh(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        only_wrong = self.cb_only_wrong.isChecked()
        counts = db.mistake_counts(src)
        self.lbl_stats.setText(
            f"전체 {counts['total']} · 지금 복습할 것(due) {counts['due']} · 아직 안 본 것 {counts['unreviewed']}"
        )
        rows = db.list_mistakes(source=src, only_wrong=only_wrong)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                f"{r['loss']:.2f}",
                r["source"],
                r["my_san"],
                r["best_san"],
                str(r["correct"]),
                str(r["wrong"]),
                _fmt_ts(r["due_at"]),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c == 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, c, item)
        self.table.resizeColumnsToContents()

    def _cfg(self):
        return cfg_mod.load_config()

    def _review(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        items = db.mistakes_due(source=src, only_wrong=self.cb_only_wrong.isChecked())
        if not items:
            QMessageBox.information(self, "내 실수 복습", "복습할 실수가 없습니다. 먼저 동기화/분석을 하세요.")
            return
        cfg = self._cfg()
        dialog = ReviewDialog(
            items,
            "mistake",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title="내 실수 복습",
            parent=self,
        )
        dialog.exec()
        self.refresh()

    def _analyze(self) -> None:
        cfg = self._cfg()
        source = self.cb_source.currentData()
        if source == "both":
            source = cfg_mod.get(cfg, "mistakes.source", "human")
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_analyze.setEnabled(False)
        self._worker = PipelineWorker(pipeline.analyze_mistakes, cfg=cfg, source=source)
        self._worker.message.connect(lambda m: self.lbl_stats.setText(m))
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._on_analyzed)
        self._worker.finished.connect(lambda: self.btn_analyze.setEnabled(True))
        self._worker.start()

    def _on_failed(self, msg: str) -> None:
        QMessageBox.warning(self, "실수 분석", msg)

    def _on_analyzed(self, result: dict) -> None:
        QMessageBox.information(self, "실수 분석", f"완료: {result}")
        self.refresh()
