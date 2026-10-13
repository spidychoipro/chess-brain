"""Reusable Qt widgets.

The review panel is the heart of the app: show a line, force me to *type*
the next move from memory, then nudge the SM-2 schedule based on how it
went. No board, no autocomplete - that is the point.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import db
from core import sr as sr_mod


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

        self.label_progress = QLabel()
        self.label_context = QLabel()
        self.label_context.setWordWrap(True)
        self.label_context.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label_context.setStyleSheet("font-size: 15px; padding: 12px;")

        self.input = QLineEdit()
        self.input.setPlaceholderText("다음 수를 SAN 으로 입력 (예: Nf3, exd5, O-O)")
        self.input.returnPressed.connect(self._submit)

        self.label_feedback = QLabel()
        self.label_feedback.setWordWrap(True)

        self.btn_submit = QPushButton("제출 (Enter)")
        self.btn_submit.clicked.connect(self._submit)

        row = QHBoxLayout()
        row.addWidget(self.input, 1)
        row.addWidget(self.btn_submit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.label_progress)
        layout.addWidget(self.label_context, 1)
        layout.addLayout(row)
        layout.addWidget(self.label_feedback)

        self._show_current()

    # -- queue handling -----------------------------------------------------

    def _show_current(self) -> None:
        if not self.queue:
            self.finished.emit(
                {
                    "total": self.total,
                    "done": self.done,
                    "correct_first_try": self.correct_first_try,
                }
            )
            return
        item = self.queue[0]
        self.label_progress.setText(
            f"[{self.title}] 남은 문제 {len(self.queue)} / 전체 {self.total}"
        )
        ctx = item.get("context_sans") or "(기보 없음)"
        self.label_context.setText(f"<b>지금까지의 기보</b><br><br>{ctx}<br><br>다음 수는?")
        self.label_feedback.clear()
        self.input.clear()
        self.input.setFocus()

    def _submit(self) -> None:
        if not self.queue:
            return
        text = self.input.text().strip()
        if not text:
            return
        item = self.queue[0]
        fen = item["fen"]
        target = (
            item.get("best_san") if self.item_type == "mistake" else item.get("target_san")
        ) or ""
        canonical = _canonical_san(fen, text)

        if canonical is None:
            self.label_feedback.setText("지금 포지션에서 둘 수 없는 수야. 기보를 다시 떠올려보자.")
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
            self.label_feedback.setText(f"정답. <b>{target}</b>")
            self.queue.pop(0)
            self._show_current()
        else:
            self._apply(item, sr_mod.GRADE_AGAIN)
            self.label_feedback.setText(
                f"오답. 정답은 <b>{target}</b>. 조금 뒤에 이 문제를 다시 볼게."
            )
            # 오답은 즉시 재도전: 같은 문제를 큐 맨 앞에 다시 넣는다.
            self.queue.pop(0)
            self.queue.insert(0, item)
            self.input.clear()

    def _apply(self, item: Dict[str, Any], grade: int) -> None:
        state = db.row_to_sr(item)
        new_state = sr_mod.review_state(
            state, grade, wrong_due_seconds=self.wrong_due_seconds
        )
        if self.item_type == "mistake":
            db.update_mistake_sr(item["id"], new_state)
        else:
            db.update_problem_sr(item["id"], new_state)
        # 로컬 사본도 갱신해서 재출제 시 최신 상태를 반영
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
        self.resize(720, 480)
        self.result_stats: Dict[str, Any] = {}
        self.panel = ReviewPanel(
            items,
            item_type,
            wrong_due_seconds=wrong_due_seconds,
            title=title,
        )
        self.panel.finished.connect(self._on_finished)
        layout = QVBoxLayout(self)
        layout.addWidget(self.panel)

    def _on_finished(self, stats: Dict[str, Any]) -> None:
        self.result_stats = stats
        self.accept()
