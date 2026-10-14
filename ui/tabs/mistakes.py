"""Main page: 내 실수(My Mistakes).

Reviewing my mistakes is the point of the app. The list shows what I lost
the most, and the review button runs the spaced drill on what is due.
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
from core import db
from ui import theme
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

        self.cb_only_wrong = QCheckBox("자주 틀린 것만 (wrong ≥ 1)")
        self.lbl_stats = theme.label("", role="muted")
        self.btn_analyze = QPushButton("실수 분석 (Stockfish)")
        self.btn_review = QPushButton("실수 복습 시작")
        self.btn_review.setProperty("variant", "primary")

        toolbar = theme.card(flat=True)
        tool = QHBoxLayout(toolbar)
        tool.setContentsMargins(14, 10, 14, 10)
        tool.addWidget(QLabel("소스"))
        tool.addWidget(self.cb_source)
        tool.addWidget(self.cb_only_wrong)
        tool.addStretch(1)
        tool.addWidget(self.btn_analyze)
        tool.addWidget(self.btn_review)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["손실(loss)", "소스", "내가 둔 수", "엔진 정답", "맞음", "틀림", "다음 복습"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("내 실수", role="h1"))
        layout.addWidget(
            theme.label(
                "엔진으로 내가 둔 수의 평가 손실을 재서 실수를 모으고, 그 실수를 간격 반복으로 복습한다.",
                role="muted",
            )
        )
        layout.addWidget(toolbar)
        layout.addWidget(self.lbl_stats)
        layout.addWidget(self.table, 1)

        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("variant", "ghost")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_analyze.clicked.connect(self._analyze)
        self.btn_review.clicked.connect(self._review)
        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.cb_only_wrong.stateChanged.connect(self.refresh)
        self.refresh()

    # -- data ---------------------------------------------------------------

    def refresh(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        only_wrong = self.cb_only_wrong.isChecked()
        counts = db.mistake_counts(src)
        gc = db.game_counts(src)
        self.lbl_stats.setText(
            f"전체 {counts['total']}  ·  지금 복습할 것(due) {counts['due']}  ·  "
            f"아직 안 본 것 {counts['unreviewed']}  ·  미분석 게임 {gc['pending']}"
        )
        rows = db.list_mistakes(source=src, only_wrong=only_wrong)
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            vals = [
                f"{r['loss']:.2f}",
                "봇" if r["source"] == "bot" else "사람",
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
        from core import engine as engine_mod
        from core import pipeline

        cfg = self._cfg()
        source = self.cb_source.currentData()
        if source == "both":
            source = cfg_mod.get(cfg, "mistakes.source", "human")
        if not engine_mod.engine_available(cfg_mod.get(cfg, "stockfish.path", "")):
            QMessageBox.warning(
                self,
                "실수 분석",
                "설정 탭에서 stockfish.exe 경로를 먼저 지정하세요.\n"
                "경로가 없으면 실수 분석은 꺼진 상태다.",
            )
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_analyze.setEnabled(False)
        self._worker = PipelineWorker(
            pipeline.analyze_mistakes, cfg=cfg, source=source, auto_sync=True
        )
        self._worker.message.connect(lambda m: self.lbl_stats.setText(m))
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._on_analyzed)
        self._worker.finished.connect(lambda: self.btn_analyze.setEnabled(True))
        self._worker.start()

    def _on_failed(self, msg: str) -> None:
        QMessageBox.warning(self, "실수 분석", msg)
        self.refresh()

    def _on_analyzed(self, result: dict) -> None:
        games = int(result.get("games", 0) or 0)
        mistakes = int(result.get("mistakes", 0) or 0)
        problems = int(result.get("problems", 0) or 0)
        reason = result.get("reason", "")
        if mistakes:
            msg = f"게임 {games}개 분석 완료 — 실수 {mistakes}개 / 복습문제 {problems}개."
        elif games:
            msg = (
                f"게임 {games}개 분석 완료 — 손실 0.8 을 넘는 실수는 없었다.\n"
                "실수가 너무 적게 잡히면 설정에서 임계값을 낮춰라."
            )
        elif reason == "all_analyzed":
            msg = "새로 분석할 게임이 없다. 이미 다 분석된 상태다."
        elif not result.get("folder_ok", True):
            msg = (
                "분석할 게임이 없고, 로컬 PGN 폴더도 못 찾았다:\n"
                f"{result.get('folder', '') or '(비어 있음)'}\n"
                "설정에서 실제 폴더를 고르거나, 드라이브 문자(X:)를 쓰려면 "
                "WinFsp 설치 후 '드라이브 마운트'가 붙어 있어야 한다."
            )
        else:
            msg = (
                "분석할 게임이 없다. 먼저 PGN 을 가져와야 한다.\n"
                "'설정 → 로컬 동기화'로 폴더를 읽거나 'rclone 으로 받기'로 드라이브에서 받아라."
            )
        QMessageBox.information(self, "실수 분석", msg)
        self.refresh()