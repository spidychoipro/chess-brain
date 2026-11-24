"""Board review, deliberate feedback and engine variation playback."""
from __future__ import annotations

import json
from typing import Optional
import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget
from core import db, sr as sr_mod
from core.utils import loss_label
from ui import theme
from ui.board import ChessBoard


def _uci_of(fen: str, san: str) -> Optional[str]:
    try:
        return chess.Board(fen).parse_san(san).uci() if san else None
    except ValueError:
        return None


def collapsible_help(text: str) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    head, _, rest = text.partition("\n")
    summary = theme.label(head, role="muted")
    summary.setWordWrap(True)
    lay.addWidget(summary)
    if rest.strip():
        detail = theme.label(rest.strip(), role="small")
        detail.setWordWrap(True)
        detail.hide()
        btn = QPushButton("자세히 ▾")
        btn.setCheckable(True)
        btn.setMaximumWidth(110)
        btn.toggled.connect(lambda on: (detail.setVisible(on), btn.setText("접기 ▴" if on else "자세히 ▾")))
        lay.addWidget(detail)
        lay.addWidget(btn, 0, Qt.AlignLeft)
    return box


class ReviewPanel(QWidget):
    finished = Signal(dict)

    def __init__(self, items, item_type, wrong_due_seconds=600, title="복습", parent=None, practice=False):
        super().__init__(parent)
        self.queue = [dict(item) for item in items]
        self.total = len(self.queue)
        self.item_type = item_type
        self.wrong_due_seconds = wrong_due_seconds
        self.practice = practice
        self.done = self.correct_first_try = self.revealed = 0
        self.attempted = set()
        self._exposed = set()
        self._last_uci = None
        self._feedback = False
        self._replay_moves = []
        self._replay_index = 0
        header = QHBoxLayout()
        header.addWidget(theme.label(title, role="h1"))
        self.lbl_score = theme.label("", role="small")
        header.addWidget(self.lbl_score, 1, Qt.AlignRight)
        self.progress = QProgressBar()
        self.progress.setFormat("%p%")
        self.progress.setFixedHeight(18)
        self.board = ChessBoard()
        self.board.movePlayedUci.connect(self._remember_uci)
        self.board.moveMade.connect(self._on_move)
        self.lbl_section = theme.label("", role="caption")
        self.lbl_turn = QLabel("")
        self.lbl_turn.setWordWrap(True)
        self.lbl_prompt = theme.label("", role="h1")
        self.lbl_context = theme.label("", role="muted")
        self.lbl_feedback = theme.label("", role="h2")
        self.lbl_reason = theme.label("", role="muted")
        for label in (self.lbl_section, self.lbl_prompt, self.lbl_context, self.lbl_feedback, self.lbl_reason):
            label.setWordWrap(True)
        self.btn_reveal = QPushButton("모르겠어요 · 정답과 해설 보기")
        self.btn_reveal.clicked.connect(self._reveal)
        self.btn_next = QPushButton("다음 문제 →")
        self.btn_next.setProperty("variant", "primary")
        self.btn_next.clicked.connect(self._after_feedback)
        self.btn_retry = QPushButton("답을 가리고 연습하기")
        self.btn_retry.clicked.connect(self._show_current)

        self.replay = QWidget()
        replay_layout = QVBoxLayout(self.replay)
        replay_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_my_line = QPushButton("내 수와 상대 응수")
        self.btn_best_line = QPushButton("추천 수 살펴보기")
        self.btn_my_line.clicked.connect(lambda: self._start_replay(False))
        self.btn_best_line.clicked.connect(lambda: self._start_replay(True))
        replay_layout.addWidget(self.btn_my_line)
        replay_layout.addWidget(self.btn_best_line)
        self.lbl_replay = theme.label("", role="small")
        self.lbl_replay.setWordWrap(True)
        replay_layout.addWidget(self.lbl_replay)
        navigation = QHBoxLayout()
        self.btn_previous = QPushButton("← 이전 수")
        self.btn_step = QPushButton("다음 수 →")
        self.btn_previous.clicked.connect(lambda: self._step_replay(-1))
        self.btn_step.clicked.connect(lambda: self._step_replay(1))
        navigation.addWidget(self.btn_previous)
        navigation.addWidget(self.btn_step)
        replay_layout.addLayout(navigation)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 0, 8, 0)
        side_layout.setSpacing(14)
        for widget in (self.lbl_section, self.lbl_turn, self.lbl_prompt, self.lbl_context, self.btn_reveal,
                       self.lbl_feedback, self.lbl_reason, self.replay, self.btn_retry, self.btn_next):
            side_layout.addWidget(widget)
        side_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(side)
        body = QHBoxLayout()
        body.addWidget(self.board, 3)
        body.addWidget(scroll, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(header)
        root.addWidget(self.progress)
        root.addLayout(body, 1)
        self._show_current()

    def _show_current(self):
        if not self.queue:
            self._finish()
            return
        item = self.queue[0]
        self._feedback = False
        self._last_uci = None
        self.progress.setRange(0, max(1, self.total))
        self.progress.setValue(self.done)
        self.lbl_score.setText(f"첫 시도 성공 {self.correct_first_try} · {self.done}/{self.total} 완료")
        self.board.set_position(item["fen"])
        self.board.set_interactive(True)
        position = chess.Board(item["fen"])
        source = {"human": "사람전", "bot": "봇전"}.get(item.get("source"), "")
        mode = "연습 · 복습 일정 유지" if self._is_practice(item) else "오늘의 복습"
        white_turn = bool(position.turn == chess.WHITE)
        turn_text = "백 차례" if white_turn else "흑 차례"
        turn_bg = "#f3f4f6" if white_turn else "#111827"
        turn_fg = "#111827" if white_turn else "#f9fafb"
        turn_border = "#9ca3af" if white_turn else "#374151"
        self.lbl_turn.setText(f"● {turn_text} · 내가 둘 차례")
        self.lbl_turn.setStyleSheet(
            f"QLabel {{ background:{turn_bg}; color:{turn_fg}; border:1px solid {turn_border};"
            " border-radius:10px; padding:10px 12px; font-size:16px; font-weight:700; }"
        )
        self.lbl_section.setText(f"{source} · {position.fullmove_number}수째 · {turn_text}\n{mode}")
        self.lbl_context.setText("이전 기보\n" + (item.get("context_sans") or "시작 국면"))
        self.lbl_prompt.setText("이 국면에서 더 좋은 수를 찾아보세요")
        if self.item_type == "problem" and item.get("origin") == "line":
            self.lbl_prompt.setText("실제 대국에서 둔 수를 재현하세요")
            self.lbl_context.setText(self.lbl_context.text() + "\n좋은 수를 찾는 게 아니라 기보를 외우는 연습입니다.")
        if item["id"] in self._exposed:
            self.lbl_prompt.setText("방금 본 수를 보드에서 연습하세요")
            self.lbl_context.setText("정답을 본 뒤의 연습입니다. 복습 성공으로 다시 기록하지 않습니다.")
        self.lbl_feedback.clear()
        self.lbl_reason.clear()
        self.btn_reveal.show()
        self.btn_reveal.setEnabled(True)
        self.btn_retry.hide()
        self.btn_next.hide()
        self.replay.hide()
        if not _uci_of(item["fen"], self._target(item)):
            self._show_feedback("풀이 정보가 없어 건너뜁니다", "이 문제는 기록을 변경하지 않습니다.")

    def _is_practice(self, item):
        return self.practice or item.get("practice", False)

    def _target(self, item):
        return item.get("best_san", "") if self.item_type == "mistake" else item.get("target_san", "")

    def _remember_uci(self, uci):
        self._last_uci = uci

    def _accepted(self, item):
        targets = [self._target(item)]
        if self.item_type == "mistake":
            try:
                targets += json.loads(item.get("accepted_sans") or "[]")
            except (ValueError, TypeError):
                pass
        return list(dict.fromkeys(targets))

    def _on_move(self, san):
        if not self.queue or self._feedback:
            return
        item = self.queue[0]
        first_try = item["id"] not in self.attempted
        self.attempted.add(item["id"])
        if san not in self._accepted(item):
            if self._last_uci:
                self.board.show_wrong(self._last_uci)
            self.lbl_feedback.setText("저장된 해법과 달라요. 다시 생각해 보세요.")
            theme.set_state(self.lbl_feedback, "danger")
            self.lbl_reason.setText("다른 좋은 수가 있을 수도 있습니다. 정답과 변형을 보고 비교할 수 있어요.")
            return
        exposed = item["id"] in self._exposed
        if not exposed and not self._is_practice(item):
            self._apply(item, sr_mod.GRADE_GOOD, first_try)
        if first_try and not exposed:
            self.correct_first_try += 1
        if self._last_uci:
            self._show_played_move(item, self._last_uci)
        message = "연습 완료 · 재학습 일정은 유지됩니다" if exposed else f"좋아요! {san}"
        self._show_feedback(message, self._reason_text(item))

    def _show_played_move(self, item, uci):
        b = chess.Board(item["fen"])
        b.push_uci(uci)
        self.board.set_position(b.fen(), flipped=chess.Board(item["fen"]).turn == chess.BLACK)
        self.board.show_hint(uci)

    def _reveal(self):
        if not self.queue or self._feedback:
            return
        item = self.queue[0]
        key = item["id"]
        if key not in self._exposed:
            self.revealed += 1
            if not self._is_practice(item):
                self._apply(item, sr_mod.GRADE_AGAIN, False)
        self._exposed.add(key)
        self.attempted.add(key)
        uci = _uci_of(item["fen"], self._target(item))
        if uci:
            self._show_played_move(item, uci)
        note = "연습 모드라 일정은 변경하지 않습니다." if self._is_practice(item) else f"{max(1, self.wrong_due_seconds // 60)}분 뒤 다시 복습합니다. 따라 두는 연습은 일정을 변경하지 않습니다."
        self._show_feedback(f"추천 수: {self._target(item)}", self._reason_text(item) + "\n" + note)
        self.btn_retry.setVisible(bool(uci))

    def _show_feedback(self, title, reason):
        self._feedback = True
        self.board.set_interactive(False)
        self.btn_reveal.hide()
        self.lbl_feedback.setText(title)
        theme.set_state(self.lbl_feedback, "success")
        self.lbl_reason.setText(reason)
        self.btn_next.setText("세션 결과 보기" if len(self.queue) == 1 else "다음 문제 →")
        self.btn_next.show()
        self.replay.setVisible(self.item_type == "mistake" and bool(self._target(self.queue[0])))
        self.btn_previous.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.lbl_replay.setText("변형을 선택하면 한 수씩 비교할 수 있습니다.")

    def _reason_text(self, item):
        if self.item_type != "mistake":
            return "실제 기보의 지정 수를 재현하는 연습입니다." if item.get("origin") == "line" else "실수 분석에서 찾은 추천 수입니다."
        text = f"내 수 {item.get('my_san') or '?'} · {loss_label(item)}"
        from core import curriculum

        theme_key = item.get("theme") or ""
        if theme_key:
            text += f"\n테마: {curriculum.THEMES.get(theme_key, theme_key)}"
        explanation = (item.get("explanation") or "").strip()
        if explanation:
            text += f"\n{explanation}"
        reply = item.get("reply_san")
        if reply and reply != "-":
            text += f"\n상대는 {reply}로 응수할 수 있었습니다. 아래에서 보드로 확인하세요."
        else:
            text += "\n저장된 상대 응수가 없습니다. 분석을 다시 하면 보완됩니다."
        text += f"\n추천 수: {item.get('best_san') or '?'}"
        if len(self._accepted(item)) > 1:
            text += "\n함께 인정되는 수: " + ", ".join(self._accepted(item))
        return text

    def _start_replay(self, best):
        item = self.queue[0]
        try:
            moves = json.loads(item.get("best_line" if best else "reply_line") or "[]")
        except (ValueError, TypeError):
            moves = []
        if not moves:
            b = chess.Board(item["fen"])
            for san in ([item.get("best_san")] if best else [item.get("my_san"), item.get("reply_san")]):
                try:
                    move = b.parse_san(san or "")
                except ValueError:
                    break
                moves.append(move.uci())
                b.push(move)
        b = chess.Board(item["fen"])
        self._replay_moves = []
        for uci in moves:
            try:
                b.push_uci(uci)
            except ValueError:
                break
            self._replay_moves.append(uci)
        self._replay_index = 0
        self._render_replay()

    def _step_replay(self, direction):
        self._replay_index = max(0, min(len(self._replay_moves), self._replay_index + direction))
        self._render_replay()

    def _render_replay(self):
        item = self.queue[0]
        b = chess.Board(item["fen"])
        sans = []
        for uci in self._replay_moves[:self._replay_index]:
            move = chess.Move.from_uci(uci)
            sans.append(b.san(move))
            b.push(move)
        self.board.set_position(b.fen(), flipped=chess.Board(item["fen"]).turn == chess.BLACK)
        if self._replay_index:
            self.board.show_hint(self._replay_moves[self._replay_index - 1])
        self.lbl_replay.setText(f"{self._replay_index}/{len(self._replay_moves)}수 · " + (" → ".join(sans) or "원래 국면"))
        self.btn_previous.setEnabled(self._replay_index > 0)
        self.btn_step.setEnabled(self._replay_index < len(self._replay_moves))

    def _after_feedback(self):
        if not self._feedback:
            return
        self.done += 1
        self.queue.pop(0)
        self._show_current()

    def _apply(self, item, grade, first_try=False):
        state = sr_mod.review_state(db.row_to_sr(item), grade, self.wrong_due_seconds)
        update = db.update_mistake_sr if self.item_type == "mistake" else db.update_problem_sr
        update(item["id"], state, first_try=first_try)
        item.update(vars(state))

    def _finish(self):
        self.finished.emit({"total": self.total, "done": self.done,
                            "correct_first_try": self.correct_first_try, "revealed": self.revealed})


class ReviewDialog(QDialog):
    def __init__(self, items, item_type, wrong_due_seconds=600, title="복습", parent=None, practice=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 720)
        self.result_stats = {}
        self.panel = ReviewPanel(items, item_type, wrong_due_seconds, title, practice=practice)
        self.panel.finished.connect(self._on_finished)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)

    def done(self, result):
        super().done(result)
        parent = self.parentWidget()
        window = parent.window() if parent is not None else None
        refresh = getattr(window, "_refresh_all", None)
        if refresh is not None:
            refresh()

    def _on_finished(self, stats):
        self.result_stats = stats
        self.panel.hide()
        summary = theme.label(f"{stats['done']}문제 완료\n첫 시도 성공 {stats['correct_first_try']}개\n정답 확인 {stats['revealed']}개", role="h1")
        summary.setWordWrap(True)
        self.layout().addWidget(summary)
        note = theme.label("연습 모드에서는 기존 복습 일정을 유지합니다." if self.panel.practice else
                           "정답을 확인한 문제는 재학습 시간이 되면 다시 만납니다.", role="muted")
        note.setWordWrap(True)
        self.layout().addWidget(note)
        close = QPushButton("학습 마치기")
        close.setProperty("variant", "primary")
        close.clicked.connect(self.accept)
        self.layout().addWidget(close)
