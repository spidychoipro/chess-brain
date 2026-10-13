"""Reusable Qt widgets.

The review panel is the heart of the app: show a line, force me to *type*
the next move from memory, then nudge the SM-2 schedule. No board, no
autocomplete - that is the point.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import db
from core import sr as sr_mod
from ui import theme


def _canonical_san(fen: str, user_input: str) -> Optional[str]:
    """Return the canonical SAN for the user's move, or None if illegal."""
    board = chess.Board(fen)
    try:
        move = board.parse_san(user_input.strip())
    except Exception:
        return None
    if move not in board.legal_moves:
        return None
    return board.san(move)


class ReviewPanel(QWidget):
    """SAN-input spaced-repetition drill over a list of items."""

    finished = Signal(dict)

    FEEDBACK_MS = 650

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

        # -- question card --------------------------------------------------
        self.lbl_section = theme.label("지금까지의 기보", role="caption")
        self.lbl_context = theme.label("", parent=None)
        self.lbl_context.setObjectName("LineText")
        self.lbl_context.setWordWrap(True)
        self.lbl_context.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_context.setMinimumHeight(90)
        self.lbl_context.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.lbl_prompt = theme.label("다음 수를 SAN 으로 입력하세요", role="muted")

        self.input = QLineEdit()
        self.input.setObjectName("AnswerInput")
        self.input.setPlaceholderText("예: Nf3   exd5   O-O   Bxc6+")
        self.input.returnPressed.connect(self._submit)

        self.btn_submit = QPushButton("제출 (Enter)")
        self.btn_submit.setProperty("variant", "primary")
        self.btn_submit.clicked.connect(self._submit)

        input_row = QHBoxLayout()
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.btn_submit)

        self.lbl_feedback = theme.label("", role="small")

        card = theme.card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)
        card_layout.addWidget(self.lbl_section)
        card_layout.addWidget(self.lbl_context)
        card_layout.addWidget(self.lbl_prompt)
        card_layout.addLayout(input_row)
        card_layout.addWidget(self.lbl_feedback)

        self.lbl_hint = theme.label(
            "Enter 로 제출 · 보드 없이 머릿속에서 말 배치를 떠올리는 훈련", role="small"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(14)
        root.addLayout(header)
        root.addWidget(self.progress)
        root.addWidget(card)
        root.addStretch(1)
        root.addWidget(self.lbl_hint)

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
        self.lbl_section.setText(self._section_text(item))
        self.lbl_feedback.setText("")
        theme.set_state(self.lbl_feedback, "muted")
        self.input.clear()
        self.input.setEnabled(True)
        self.input.setFocus()

    def _section_text(self, item: Dict[str, Any]) -> str:
        src = {"bot": "봇전", "human": "사람전"}.get(item.get("source"), item.get("source", ""))
        ply = item.get("ply")
        return f"지금까지의 기보  ·  {src}  ·  {ply}수째" if ply else f"지금까지의 기보  ·  {src}"

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

    def _submit(self) -> None:
        if not self.queue or not self.input.isEnabled():
            return
        text = self.input.text().strip()
        if not text:
            return
        item = self.queue[0]
        target = self._target(item)
        canonical = _canonical_san(item["fen"], text)

        if canonical is None:
            self.lbl_feedback.setText("지금 포지션에서 둘 수 없는 수야. 기보를 다시 떠올려보자.")
            theme.set_state(self.lbl_feedback, "muted")
            self.input.selectAll()
            return

        key = item.get("id")
        first_try = key not in self.attempted
        self.attempted.add(key)

        if canonical == target:
            self._apply(item, sr_mod.GRADE_GOOD)
            if first_try:
                self.correct_first_try += 1
            self.done += 1
            self.queue.pop(0)
            self.progress.setValue(self.done)
            self.input.setEnabled(False)
            self.lbl_feedback.setText(f"정답!  {target}")
            theme.set_state(self.lbl_feedback, "success")
            self._timer.start(self.FEEDBACK_MS)
        else:
            self._apply(item, sr_mod.GRADE_AGAIN)
            self.lbl_feedback.setText(f"오답. 정답은 {target} 이었어. 조금 뒤에 이 문제를 다시 볼게.")
            theme.set_state(self.lbl_feedback, "danger")
            # 오답은 즉시 재도전: 같은 문제를 큐 맨 앞에 다시 둔다.
            self.queue.pop(0)
            self.queue.insert(0, item)
            self.input.clear()
            self.input.setFocus()

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
        self.resize(800, 560)
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
