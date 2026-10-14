"""Reusable Qt widgets.

The review panel is the heart of the app. It shows the position on a real
board and you answer by *moving a piece*, not by typing SAN - notation is a
skill nobody should need to review their own mistakes. When the answer is
wrong the correct move is drawn as an arrow so it stays visible.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import db
from core import sr as sr_mod
from ui import theme
from ui.board import ChessBoard


def _uci_of(fen: str, san: str) -> Optional[str]:
    """SAN -> UCI. 보드에 정답 화살표를 그리려고 쓴다."""
    if not san:
        return None
    try:
        board = chess.Board(fen)
        return board.parse_san(san).uci()
    except Exception:
        return None


class ReviewPanel(QWidget):
    """Board-input spaced-repetition drill over a list of items."""

    finished = Signal(dict)

    FEEDBACK_MS = 900

    def __init__(
        self,
        items: List[Dict[str, Any]],
        item_type: str,          # 'mistake' | 'problem'
        wrong_due_seconds: int = 600,
        title: str = "복습",
        parent=None,
    ):
        super().__init__(parent)
        self.queue: List[Dict[str, Any]] = list(items)
        self.total = len(self.queue)
        self.item_type = item_type
        self.wrong_due_seconds = wrong_due_seconds
        self.title = title
        self.done = 0
        self.correct_first_try = 0
        self.attempted: set = set()
        self._last_uci: Optional[str] = None
        self._wrong_streak = 0

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._after_feedback)

        # -- header ---------------------------------------------------------
        self.lbl_title = theme.label(title, role="h1")
        self.lbl_score = theme.label("", role="small")
        self.lbl_score.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header = QHBoxLayout()
        header.addWidget(self.lbl_title)
        header.addStretch(1)
        header.addWidget(self.lbl_score)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(12)

        # -- board ----------------------------------------------------------
        self.board = ChessBoard()
        self.board.moveMade.connect(self._on_move)
        self.board.movePlayedUci.connect(self._remember_uci)

        # -- side info ------------------------------------------------------
        self.lbl_section = theme.label("", role="caption")
        self.lbl_context = theme.label("", role="muted")
        self.lbl_context.setWordWrap(True)
        self.lbl_context.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.lbl_prompt = theme.label(
            "보드에서 다음 수를 두세요. (수를 옮기려면 기물 → 도착칸 클릭)", role="muted"
        )
        self.lbl_prompt.setWordWrap(True)

        self.btn_reveal = QPushButton("모르겠음 (정답 보기)")
        self.btn_reveal.setProperty("variant", "ghost")
        self.btn_reveal.clicked.connect(self._reveal)

        self.lbl_feedback = theme.label("", role="small")
        self.lbl_feedback.setWordWrap(True)

        side = QVBoxLayout()
        side.setSpacing(12)
        side.addWidget(self.lbl_section)
        side.addWidget(self.lbl_context)
        side.addWidget(self.lbl_prompt)
        side.addWidget(self.btn_reveal)
        side.addWidget(self.lbl_feedback)
        side.addStretch(1)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.board, 3)
        side_wrap = QWidget()
        side_wrap.setLayout(side)
        body.addWidget(side_wrap, 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)
        root.addLayout(header)
        root.addWidget(self.progress)
        root.addLayout(body, 1)

        self._show_current()

    # -- queue handling -----------------------------------------------------

    def _show_current(self) -> None:
        self._timer.stop()
        if not self.queue:
            self._finish()
            return
        item = self.queue[0]
        self.progress.setRange(0, max(1, self.total))
        self.progress.setValue(self.done)
        self.lbl_score.setText(
            f"맞음 {self.correct_first_try} · 남은 문제 {len(self.queue)} / 전체 {self.total}"
        )
        ctx = item.get("context_sans") or "(첫 수라 보여줄 기보가 없음)"
        self.lbl_context.setText(ctx)
        self.lbl_feedback.setText("")
        theme.set_state(self.lbl_feedback, "muted")
        self._last_uci = None
        self._wrong_streak = 0
        self.board.set_position(item["fen"])
        self.board.clear_marks()
        self.board.set_interactive(True)
        self.btn_reveal.setEnabled(True)
        # 포지션을 먼저 세팅한 뒤 라벨을 만든다. 순서를 바꾸면 라벨이 직전
        # 문제의 차례를 읽어서 색이 한 문제씩 어긋난다.
        self.lbl_section.setText(self._section_text(item))
        self.lbl_prompt.setText(
            "보드에서 다음 수를 두세요. (기물 → 도착칸 클릭)"
        )

    def _section_text(self, item: Dict[str, Any]) -> str:
        src = {"bot": "봇전", "human": "사람전"}.get(item.get("source"), item.get("source", ""))
        ply = item.get("ply")
        try:
            turn = "흑" if chess.Board(item["fen"]).turn == chess.BLACK else "백"
        except Exception:
            turn = "백"
        tail = f"{src} · {ply}수째 · 내 차례({turn})" if ply else f"{src} · 내 차례({turn})"
        return tail

    def _finish(self) -> None:
        self.finished.emit(
            {
                "total": self.total,
                "done": self.done,
                "correct_first_try": self.correct_first_try,
            }
        )

    def _target(self, item: Dict[str, Any]) -> str:
        if self.item_type == "mistake":
            return item.get("best_san") or ""
        return item.get("target_san") or ""

    def _remember_uci(self, uci: str) -> None:
        self._last_uci = uci

    def _on_move(self, san: str) -> None:
        if not self.queue or not self.board.is_interactive():
            return
        item = self.queue[0]
        target = self._target(item)

        key = item.get("id")
        first_try = key not in self.attempted
        self.attempted.add(key)

        # 정답 정보가 없는 문제는 판정할 수 없으니 넘어간다(무한 재투입 방지).
        if not target:
            self.board.set_interactive(False)
            self.btn_reveal.setEnabled(False)
            self.done += 1
            self.queue.pop(0)
            self.progress.setValue(self.done)
            self.lbl_feedback.setText("정답 정보가 없는 문제라 넘어갈게.")
            theme.set_state(self.lbl_feedback, "muted")
            self._timer.start(self.FEEDBACK_MS)
            return

        if san == target:
            self.board.set_interactive(False)
            self.btn_reveal.setEnabled(False)
            self._apply(item, sr_mod.GRADE_GOOD)
            if first_try:
                self.correct_first_try += 1
            self.done += 1
            self.queue.pop(0)
            self.progress.setValue(self.done)
            if self._last_uci:
                self.board.show_hint(self._last_uci)
            self.lbl_feedback.setText(f"정답!  ({target})")
            theme.set_state(self.lbl_feedback, "success")
            self._timer.start(self.FEEDBACK_MS)
            return

        # 오답
        self._wrong_streak += 1
        if self._last_uci:
            self.board.show_wrong(self._last_uci)

        if self._wrong_streak == 1:
            # 첫 오답: 빨간 표시만 하고 정답은 감춘다. 다시 시도하게 둔다.
            self.lbl_feedback.setText(
                "그 수는 아니야. 다시 해봐.  (정답을 보려면 '모르겠음')"
            )
            theme.set_state(self.lbl_feedback, "danger")
            return

        # 두 번째 오답: 이제 정답을 보여주고 같은 문제를 큐 맨 앞에 다시 둔다.
        self.board.set_interactive(False)
        self.btn_reveal.setEnabled(False)
        self._apply(item, sr_mod.GRADE_AGAIN)
        target_uci = _uci_of(item["fen"], target)
        if target_uci:
            self.board.show_hint(target_uci)
        self.lbl_feedback.setText(
            f"이번엔 정답을 볼게. 초록 화살표가 정답이야. 조금 뒤에 다시 낼게.  ({target})"
        )
        theme.set_state(self.lbl_feedback, "danger")
        self.queue.pop(0)
        self.queue.insert(0, item)
        self._timer.start(self.FEEDBACK_MS)

    def _reveal(self) -> None:
        """모르겠음: 정답 화살표만 보여주고 오답 처리한다(바로 큐 재투입)."""
        if not self.queue or not self.board.is_interactive():
            return
        item = self.queue[0]
        self.attempted.add(item.get("id"))  # 정답을 보여줬으니 첫시도 정답으로 안 친다
        target = self._target(item)
        target_uci = _uci_of(item["fen"], target)
        if target_uci:
            self.board.show_hint(target_uci)
        self.board.set_interactive(False)
        self.btn_reveal.setEnabled(False)
        self._apply(item, sr_mod.GRADE_AGAIN)
        self.lbl_feedback.setText(
            f"정답: 초록 화살표  ({target})" if target else "정답 정보가 없는 문제야."
        )
        theme.set_state(self.lbl_feedback, "danger")
        self.queue.pop(0)
        self.queue.insert(0, item)
        self._timer.start(self.FEEDBACK_MS + 600)

    def _after_feedback(self) -> None:
        self._show_current()

    def _apply(self, item: Dict[str, Any], grade: int) -> None:
        state = db.row_to_sr(item)
        new_state = sr_mod.review_state(
            state, grade, wrong_due_seconds=self.wrong_due_seconds
        )
        if self.item_type == "mistake":
            db.update_mistake_sr(item["id"], new_state)
        else:
            db.update_problem_sr(item["id"], new_state)
        item.update(
            {
                "ease": new_state.ease,
                "interval": new_state.interval,
                "reps": new_state.reps,
                "lapses": new_state.lapses,
                "due_at": new_state.due_at,
                "reviewed_at": new_state.reviewed_at,
                "streak": new_state.streak,
                "correct": new_state.correct,
                "wrong": new_state.wrong,
                "last_wrong": new_state.last_wrong,
            }
        )


class ReviewDialog(QDialog):
    def __init__(
        self,
        items: List[Dict[str, Any]],
        item_type: str,
        wrong_due_seconds: int = 600,
        title: str = "복습",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(960, 700)
        self.result_stats: Dict[str, Any] = {}
        self.panel = ReviewPanel(
            items,
            item_type,
            wrong_due_seconds=wrong_due_seconds,
            title=title,
        )
        self.panel.finished.connect(self._on_finished)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)

    def _on_finished(self, stats: Dict[str, Any]) -> None:
        self.result_stats = stats
        self.accept()
