"""Main page: 내 실수(My Mistakes).

Reviewing my mistakes is the point of the app. The list shows what I lost
the most, and the review button runs the spaced drill on what is due.
"""
from __future__ import annotations

import time

import chess
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import db
from core.utils import classify_loss, loss_label
from ui import theme
from ui.board import ChessBoard
from ui.widgets import ReviewDialog, _uci_of
from ui.worker import PipelineWorker


def _fmt_ts(ts: int) -> str:
    if not ts:
        return "-"
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


class MistakesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._rows: list = []
        self._previewed = set()
        self._limit = 100

        self.cb_source = QComboBox()
        self.cb_source.addItem("사람", "human")
        self.cb_source.addItem("봇", "bot")
        self.cb_source.addItem("전체", "both")
        # both 로 분석했는데 목록은 Human 만 보여서 '사람만 했다'로 보이던 문제.
        # 기본을 Both 로 둬서 분석한 게 다 보이게 한다.
        self.cb_source.setCurrentIndex(self.cb_source.findData("both"))

        self.cb_only_wrong = QCheckBox("틀린 문제만")
        self.cb_only_wrong.setToolTip("복습에서 한 번 이상 틀린 실수만 표시합니다.")

        # 손실 폰 기준 등급 필터. Grok 지적처럼 '구분이 없다'는 걸 채운다.
        self.cb_grade = QComboBox()
        self.cb_grade.addItem("등급 전체", "all")
        self.cb_grade.addItem("블런더만", "blunder")
        self.cb_grade.addItem("실수 이상", "mistake")
        self.cb_grade.addItem("부정확만", "inaccuracy")

        self.lbl_stats = theme.label("", role="muted")
        self.lbl_stats.setWordWrap(True)
        self.empty_icon = theme.icon_label("empty", 44)
        self.lbl_empty = theme.label("", role="empty")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.hide()
        self.empty_icon.hide()
        self.btn_analyze_h = QPushButton("사람전 분석")
        self.btn_analyze_b = QPushButton("봇전 분석")
        self.btn_analyze_all = QPushButton("전체 분석")
        for button in (self.btn_analyze_h, self.btn_analyze_b, self.btn_analyze_all):
            button.setToolTip("아직 분석하지 않은 대국을 Stockfish로 분석합니다.")
        self.btn_review = QPushButton("복습 시작")
        self.btn_review.setToolTip("복습할 시간이 된 실수와 새 실수를 최대 10개 풉니다.")
        self.btn_review.setProperty("variant", "primary")
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.setProperty("variant", "ghost")

        toolbar = theme.card(flat=True)
        tool_root = QVBoxLayout(toolbar)
        tool_root.setContentsMargins(16, 12, 16, 12)
        tool_root.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("보기"))
        filter_row.addWidget(self.cb_source)
        filter_row.addWidget(QLabel("등급"))
        filter_row.addWidget(self.cb_grade)
        filter_row.addWidget(self.cb_only_wrong)
        filter_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_analyze_h)
        action_row.addWidget(self.btn_analyze_b)
        action_row.addWidget(self.btn_analyze_all)
        action_row.addWidget(self.btn_review)
        action_row.addWidget(self.btn_refresh)

        tool_root.addLayout(filter_row)
        tool_root.addLayout(action_row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setFormat("%p%")
        self.lbl_progress = theme.label("", role="small")
        self.btn_cancel = QPushButton("중단")
        self.btn_cancel.setProperty("variant", "ghost")
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(10)
        progress_row.addWidget(self.bar, 1)
        progress_row.addWidget(self.lbl_progress, 2)
        progress_row.addWidget(self.btn_cancel)
        self.progress_box = QWidget()
        self.progress_box.setLayout(progress_row)
        self.progress_box.hide()

        self.btn_more = QPushButton("더 보기")
        self.btn_more.setProperty("variant", "ghost")
        self.btn_more.hide()

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "손실",
                "등급",
                "상대",
                "내 수",
                "추천 수",
                "응수",
                "맞음",
                "틀림",
                "다음 복습",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(44)
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(34)
        # Review history stays available in row tooltips and the preview caption.
        # Keep the six chess columns visible alongside a useful-sized board.
        for column in (6, 7, 8):
            self.table.setColumnHidden(column, True)
        for column, tip in enumerate((
            "평가 손실 (폰 단위). 메이트 관련 국면은 M으로 표시합니다.",
            "엔진 평가 손실에 따른 분류", "대국 상대 유형",
            "실제 대국에서 둔 수", "엔진이 추천하는 수", "내 수에 대한 상대의 응수",
        )):
            self.table.horizontalHeaderItem(column).setToolTip(tip)
        self.table.verticalHeader().setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)
        layout.addWidget(theme.label("내 실수", role="h1"))
        layout.addWidget(
            theme.label(
                "내 대국에서 놓친 수를 확인하고, 복습할 시간이 된 실수부터 다시 풀어보세요.",
                role="muted",
            )
        )
        layout.addWidget(toolbar)
        layout.addWidget(self.lbl_stats)
        layout.addWidget(self.progress_box)
        layout.addWidget(self.empty_icon)
        layout.addWidget(self.lbl_empty)

        # 노테이션을 모르면 SAN 표가 무의미하니, 행을 고르면 보드가 뜨게 한다.
        self.board = ChessBoard()
        self.board.set_interactive(False)
        self.board.setMinimumSize(260, 260)
        self.lbl_preview_title = theme.label("포지션 미리보기", role="h2")
        self.lbl_preview_move = theme.label("", role="small")
        self.lbl_preview_move.setWordWrap(True)
        self.lbl_preview = theme.label("행을 고르면 여기에 포지션이 뜬다.", role="muted")
        self.lbl_preview.setWordWrap(True)

        side = QWidget()
        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(0, 0, 0, 0)
        side_l.setSpacing(8)
        side_l.addWidget(self.lbl_preview_title)
        side_l.addWidget(self.board, 1)
        side_l.addWidget(self.lbl_preview_move)
        side_l.addWidget(self.lbl_preview)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.table)
        split.addWidget(side)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setHandleWidth(16)
        split.setChildrenCollapsible(False)
        # 작은 창에서도 양쪽이 다 보이게, 보드 쪽은 접을 수 있게 최소를 낮춘다.
        split.setSizes([520, 320])
        layout.addWidget(split, 1)
        layout.addWidget(self.btn_more)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_analyze_h.clicked.connect(lambda: self._analyze("human"))
        self.btn_analyze_b.clicked.connect(lambda: self._analyze("bot"))
        self.btn_analyze_all.clicked.connect(lambda: self._analyze("both"))
        self.btn_review.clicked.connect(self._review)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_more.clicked.connect(self._show_more)
        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.cb_grade.currentIndexChanged.connect(self.refresh)
        self.cb_only_wrong.stateChanged.connect(self.refresh)
        self.table.currentCellChanged.connect(lambda *_: self._on_row())
        self.table.itemDoubleClicked.connect(lambda *_: self._review_current())
        self.refresh()

    def _on_row(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            self.board.set_position(chess.STARTING_FEN)
            self.board.clear_marks()
            self.lbl_preview_move.setText("")
            self.lbl_preview_title.setText("포지션 미리보기")
            self.lbl_preview.setText("목록에서 실수를 선택하세요. 두 번 누르면 해당 문제를 연습합니다.")
            return
        r = self._rows[idx]
        self.lbl_preview_title.setText("선택한 실수")
        self._previewed.add(r["id"])
        fen = r.get("fen") or chess.STARTING_FEN
        self.board.set_position(fen)
        self.board.clear_marks()
        my_san = r.get("my_san") or ""
        best_san = r.get("best_san") or ""
        reply_san = r.get("reply_san") or ""
        if reply_san == "-":   # 국면이 끝나 응수가 없는 경우
            reply_san = ""
        my_uci = _uci_of(fen, my_san)
        best_uci = _uci_of(fen, best_san)
        if my_uci:
            self.board.show_wrong(my_uci)
        if best_uci:
            self.board.show_hint(best_uci)
        self.lbl_preview_move.setText(
            f"빨강: 내 수 {my_san or '?'}  ·  초록: 추천 수 {best_san or '?'}"
        )
        grade = classify_loss(r.get("loss"))[1]
        why = f"상대 응수 {reply_san}" if reply_san else "저장된 상대 응수 없음"
        self.lbl_preview.setText(
            f"{grade} · {loss_label(r)} · {why}\n"
            f"맞음 {r['correct']} · 틀림 {r['wrong']} · 다음 복습 {_fmt_ts(r['due_at'])}"
        )

    # -- data ---------------------------------------------------------------

    def refresh(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        only_wrong = self.cb_only_wrong.isChecked()
        counts = db.mistake_counts(src)
        gc = db.game_counts(src)
        self.lbl_stats.setText(
            f"전체 {counts['total']}  ·  지금 복습 {counts['due']}  ·  "
            f"새 실수 {counts['unreviewed']}  ·  미분석 대국 {gc['pending']}"
        )
        rows = db.list_mistakes(limit=self._limit, source=src, only_wrong=only_wrong)
        self.btn_more.setText(f"{self._limit}개 더 보기 · 전체 {counts['total']}개")
        self.btn_more.setVisible(len(rows) >= self._limit)
        rows = self._filter_by_grade(rows)
        self._rows = rows
        self.lbl_empty.setVisible(not rows)
        self.empty_icon.setVisible(not rows)
        if not rows:
            has_any = bool(db.list_mistakes(limit=1, source=src, only_wrong=only_wrong))
            self.lbl_empty.setText(
                "이 조건에 맞는 실수가 없어요. 필터를 바꿔보세요."
                if has_any
                else "아직 쌓인 실수가 없어요. Stockfish 경로를 확인한 뒤 "
                     "'사람전 분석'이나 '봇전 분석'을 눌러보세요."
            )
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            grade = classify_loss(r.get("loss"))[1]
            vals = [
                "M" if "메이트" in loss_label(r) else f"{float(r.get('loss') or 0):.2f}",
                grade,
                "봇" if r["source"] == "bot" else "사람",
                r["my_san"],
                r["best_san"],
                r.get("reply_san") or "-",
                str(r["correct"]),
                str(r["wrong"]),
                _fmt_ts(r["due_at"]),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                item.setToolTip(
                    f"{loss_label(r)}\n내 수 {r['my_san']} · 추천 수 {r['best_san']} · 응수 {r.get('reply_san') or '-'}\n"
                    f"맞음 {r['correct']} · 틀림 {r['wrong']} · 다음 복습 {_fmt_ts(r['due_at'])}"
                )
                self.table.setItem(i, c, item)

    def _show_more(self) -> None:
        self._limit += 100
        self.refresh()

    def _filter_by_grade(self, rows: list) -> list:
        want = self.cb_grade.currentData()
        if want in (None, "all"):
            return rows

        def keep(r) -> bool:
            try:
                loss = float(r.get("loss") or 0.0)
            except (TypeError, ValueError):
                loss = 0.0
            if want == "blunder":
                return loss >= 2.0
            if want == "mistake":
                return loss >= 1.0
            if want == "inaccuracy":
                return loss < 1.0
            return True

        return [r for r in rows if keep(r)]

    def _cfg(self):
        return cfg_mod.load_config()

    def _review_current(self) -> None:
        idx = self.table.currentRow()
        if idx < 0 or idx >= len(self._rows):
            return
        cfg = self._cfg()
        dialog = ReviewDialog(
            [self._rows[idx]],
            "mistake",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title="실수 하나 복습",
            parent=self,
            practice=(self._rows[idx]["id"] in self._previewed or
                      (self._rows[idx].get("due_at") or 0) > int(time.time())),
        )
        dialog.exec()
        self.refresh()

    def _review(self) -> None:
        source = self.cb_source.currentData()
        src = None if source == "both" else source
        items = db.mistakes_due(limit=10, source=src,
            only_wrong=self.cb_only_wrong.isChecked(), grade=self.cb_grade.currentData())
        for item in items:
            item["practice"] = item["id"] in self._previewed
        if not items:
            self.lbl_stats.setText(
                "복습할 실수가 없어요. 홈의 '대국 가져오기'로 PGN을 읽고 "
                "'사람전 분석'을 눌러보세요."
            )
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

    def _analyze(self, source=None) -> None:
        from core import engine as engine_mod
        from core import pipeline

        if source is None:
            source = self.cb_source.currentData()
        selected = None if source == "both" else source
        cfg = self._cfg()
        if not engine_mod.engine_available(cfg_mod.get(cfg, "stockfish.path", "")):
            self.lbl_stats.setText(
                "설정에서 stockfish.exe 경로를 먼저 지정하세요. 경로가 없으면 실수 분석은 꺼져 있어요."
            )
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_busy(True)
        self._worker = PipelineWorker(
            pipeline.analyze_mistakes, cfg=cfg, source=selected, auto_sync=True
        )
        self._worker.message.connect(self.lbl_progress.setText)
        self._worker.progressed.connect(self._on_progress)
        self._worker.failed.connect(self._on_failed)
        self._worker.done.connect(self._on_analyzed)
        self._worker.ended.connect(self._on_ended)
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self.btn_analyze_h,
            self.btn_analyze_b,
            self.btn_analyze_all,
            self.btn_review,
        ):
            button.setEnabled(not busy)
        self.progress_box.setVisible(busy)
        self.btn_cancel.setEnabled(busy)
        if busy:
            self.bar.setRange(0, 1)
            self.bar.setValue(0)
            self.lbl_progress.setText("준비 중…")

    def _on_ended(self, state: str) -> None:
        self._set_busy(False)
        if state == "cancelled":
            self.lbl_progress.setText("중단됨 — 분석이 멈췄어요.")
        elif state == "failed":
            self.lbl_progress.setText("분석이 실패했어요. 설정의 로그를 확인해보세요.")
        else:
            self.lbl_progress.clear()

    def _on_progress(self, done: int, total: int, message: str) -> None:
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(min(done, total))
            self.lbl_progress.setText(message)
        elif message:
            self.lbl_progress.setText(message)

    def _cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self.btn_cancel.setEnabled(False)
            self.lbl_progress.setText("중단 요청함…")

    def _on_failed(self, msg: str) -> None:
        QMessageBox.warning(self, "실수 분석", msg)

    def _on_analyzed(self, result: dict) -> None:
        games = int(result.get("games", 0) or 0)
        mistakes = int(result.get("mistakes", 0) or 0)
        problems = int(result.get("problems", 0) or 0)
        filled = int(result.get("filled", 0) or 0)
        reason = result.get("reason", "")
        if mistakes:
            msg = f"게임 {games}개 분석 완료 — 실수 {mistakes}개 / 복습문제 {problems}개."
            if filled:
                msg += f"\n옛 실수의 상대 응수 {filled}개도 채웠다."
        elif games:
            msg = (
                f"게임 {games}개 분석 완료 — 손실 0.8 을 넘는 실수는 없었다.\n"
                "실수가 너무 적게 잡히면 설정에서 임계값을 낮춰라."
            )
        elif reason == "all_analyzed":
            if filled:
                msg = f"새로 분석할 게임은 없다. 옛 실수의 상대 응수 {filled}개를 채웠다."
            else:
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
                "분석할 게임이 없어요. 홈의 '대국 가져오기'로 PGN을 읽거나 "
                "설정에서 드라이브 파일을 받아보세요."
            )
        self.lbl_stats.setText(msg.replace("\n", " "))
        QTimer.singleShot(4000, self.refresh)
