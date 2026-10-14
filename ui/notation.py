"""노테이션 배우기 - 하나도 모르는 사람 기준 4단계.

    1단계  기물 ↔ 글자      K Q R B N, 폰은 글자 없음
    2단계  칸 이름          a1 ~ h8 (파일 a~h, 랭크 1~8)
    3단계  수 읽기          "Nf3", "Bxc6+", "O-O" 를 보드에서 두기
    4단계  머릿속 보드      보드를 가리고 기보만 보고 어느 칸→어느 칸인지 짚기

기보를 읽는 힘은 결국 "글자 → 머릿속 그림"이다. 그래서 마지막 단계에서
보드를 아예 가리고 칸만 짚게 한다. 처음 하는 사람이 대상이라 모든 화면에
설명을 붙여둔다.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

import chess
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.board import ChessBoard

_GLYPH = {
    chess.KING: "\u265a",
    chess.QUEEN: "\u265b",
    chess.ROOK: "\u265c",
    chess.BISHOP: "\u265d",
    chess.KNIGHT: "\u265e",
    chess.PAWN: "\u265f",
}
_PIECE_KR = {
    chess.KING: "킹",
    chess.QUEEN: "퀸",
    chess.ROOK: "룩",
    chess.BISHOP: "비숍",
    chess.KNIGHT: "나이트",
    chess.PAWN: "폰",
}
_LETTER = {
    chess.KING: "K",
    chess.QUEEN: "Q",
    chess.ROOK: "R",
    chess.BISHOP: "B",
    chess.KNIGHT: "N",
}
_LETTER_PIECE = {
    "K": chess.KING,
    "Q": chess.QUEEN,
    "R": chess.ROOK,
    "B": chess.BISHOP,
    "N": chess.KNIGHT,
}
_ANSWER_LETTERS = ["K", "Q", "R", "B", "N"]


def glyph_label(piece_type: int, size: int = 56) -> QLabel:
    lbl = QLabel(_GLYPH[piece_type])
    f = QFont("Segoe UI Symbol")
    f.setPixelSize(size)
    lbl.setFont(f)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("color: #f2f4f8;")
    lbl.setMinimumWidth(size + 14)
    return lbl


def describe_san(san: str) -> str:
    """'Nf3' 같은 수를 초보자용 설명으로 푼다."""
    if not san:
        return ""
    if san.startswith("O-O-O") or san.startswith("0-0-0"):
        return "O-O-O = 퀸사이드 캐슬링 (킹과 룩이 한 번에 움직임)"
    if san.startswith("O-O") or san.startswith("0-0"):
        return "O-O = 킹사이드 캐슬링 (킹과 룩이 한 번에 움직임)"

    body = san.rstrip("+#")
    parts: List[str] = []
    first = body[0]
    if first in _LETTER_PIECE:
        parts.append(f"{first} = {_PIECE_KR[_LETTER_PIECE[first]]}")
        rest = body[1:]
    else:
        parts.append("글자 없음 = 폰")
        rest = body

    promo = None
    if "=" in rest:
        rest, promo = rest.split("=", 1)

    square = rest[-2:]
    head = rest[:-2]
    if "x" in head:
        parts.append("x = 잡기")
    elif head:
        # Nbd2 처럼 같은 기물이 둘 다 갈 수 있어 붙는 출발 힌트
        parts.append(f"'{head}' = 어느 기물인지 구분하는 표시")
    parts.append(f"목적지 칸 = {square}")
    if promo:
        parts.append(f"= {_PIECE_KR.get(_LETTER_PIECE.get(promo), promo)}으로 승격")
    if san.endswith("#"):
        parts.append("# = 체크메이트")
    elif san.endswith("+"):
        parts.append("+ = 체크")
    return "   ·   ".join(parts)


def _steps_from_sans(sans: List[str]) -> List[Dict[str, Any]]:
    b = chess.Board()
    out: List[Dict[str, Any]] = []
    for san in sans:
        mv = b.parse_san(san)
        out.append(
            {
                "fen": b.fen(),
                "san": b.san(mv),
                "from": mv.from_square,
                "to": mv.to_square,
                "piece": b.piece_at(mv.from_square).piece_type,
            }
        )
        b.push(mv)
    return out


def _step_from_fen(fen: str, san: str) -> Dict[str, Any]:
    b = chess.Board(fen)
    mv = b.parse_san(san)
    return {
        "fen": fen,
        "san": b.san(mv),
        "from": mv.from_square,
        "to": mv.to_square,
        "piece": b.piece_at(mv.from_square).piece_type,
    }


def _ruy() -> List[Dict[str, Any]]:
    return _steps_from_sans(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6", "dxc6", "O-O"])


def read_ladder() -> List[Dict[str, Any]]:
    """3단계 문제 사다리. 쉬운 것 → 어려운 것."""
    a = _ruy()
    mate = _steps_from_sans(["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"])
    return [
        a[0],                                          # e4  (폰, 글자 없음)
        a[1],                                          # e5
        a[2],                                          # Nf3 (나이트)
        a[4],                                          # Bb5 (비숍)
        a[6],                                          # Bxc6 (잡기)
        a[8],                                          # O-O  (캐슬링)
        _step_from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "Rh8+"),   # 체크
        mate[-1],                                      # Qxf7# (잡기 + 메이트)
        _step_from_fen("8/P6k/8/8/8/8/7K/8 w - - 0 1", "a8=Q"),     # 승격
    ]


def _two_col(board: QWidget, side: QVBoxLayout) -> QHBoxLayout:
    body = QHBoxLayout()
    body.setSpacing(18)
    body.addWidget(board, 3)
    wrap = QWidget()
    wrap.setLayout(side)
    body.addWidget(wrap, 2)
    return body


class _Stage(QWidget):
    """단계 공통 뼈대."""

    lesson_title = ""

    def __init__(self, parent=None):
        super().__init__(parent)

    def _lesson_card(self, heading: str, lines: List[str]) -> QWidget:
        card = theme.card(flat=True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(theme.label(heading, role="h2"))
        for line in lines:
            lbl = theme.label(line, role="muted")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        return card


# ---------------------------------------------------------------------------
# 1단계: 기물 ↔ 글자
# ---------------------------------------------------------------------------

class Stage1Pieces(_Stage):
    def __init__(self, parent=None):
        super().__init__(parent)
        legend = theme.card(flat=True)
        grid = QGridLayout(legend)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(8)
        grid.addWidget(theme.label("기물과 글자", role="h2"), 0, 0, 1, 3)
        rows = [
            (chess.KING, "K", "킹 (King)"),
            (chess.QUEEN, "Q", "퀸 (Queen)"),
            (chess.ROOK, "R", "룩 (Rook)"),
            (chess.BISHOP, "B", "비숍 (Bishop)"),
            (chess.KNIGHT, "N", "나이트 (kNight)"),
        ]
        for i, (pt, letter, name) in enumerate(rows, start=1):
            grid.addWidget(glyph_label(pt, 40), i, 0)
            grid.addWidget(theme.label(letter, role="h2"), i, 1)
            grid.addWidget(theme.label(name, role="muted"), i, 2)
        grid.addWidget(glyph_label(chess.PAWN, 40), 6, 0)
        grid.addWidget(theme.label("(없음)", role="h2"), 6, 1)
        grid.addWidget(
            theme.label("폰 (Pawn) — 글자가 없다. 목적지 칸만 쓴다. 예: e4", role="muted"),
            6, 2,
        )
        note = theme.label(
            "나이트는 영어로 Knight 라서 K 가 아니라 N 을 쓴다. K 는 킹이라 헷갈리기 쉬움.",
            role="small",
        )
        note.setWordWrap(True)
        grid.addWidget(note, 7, 0, 1, 3)

        self.lbl_q = theme.label("", role="h1")
        self.lbl_q.setAlignment(Qt.AlignCenter)
        self.piece_box = QVBoxLayout()
        self.piece_box.setAlignment(Qt.AlignCenter)
        self.answers = QHBoxLayout()
        self.answers.setAlignment(Qt.AlignCenter)
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setAlignment(Qt.AlignCenter)
        self.lbl_score = theme.label("", role="muted")

        quiz = theme.card()
        qlay = QVBoxLayout(quiz)
        qlay.setContentsMargins(18, 16, 18, 16)
        qlay.setSpacing(14)
        qlay.addWidget(self.lbl_score)
        qlay.addWidget(self.lbl_q)
        qlay.addLayout(self.piece_box)
        qlay.addLayout(self.answers)
        qlay.addWidget(self.lbl_fb)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(12)
        root.addWidget(legend)
        root.addWidget(quiz, 1)

        self.correct = 0
        self.total = 0
        self._piece: Optional[int] = None
        self._kind = "glyph2letter"
        self._answered = False
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._new_question)
        self._new_question()

    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _new_question(self) -> None:
        self._clear(self.piece_box)
        self._clear(self.answers)
        self._answered = False
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")
        self.lbl_score.setText(f"맞음 {self.correct} / {self.total}")

        self._kind = random.choice(["glyph2letter", "letter2glyph"])
        pool = [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        if self._kind == "glyph2letter":
            # 폰도 섞어서 "글자 없음"을 익힌다.
            self._piece = random.choice(pool + [chess.PAWN])
            self.lbl_q.setText("이 기물의 글자는?")
            self.piece_box.addWidget(glyph_label(self._piece, 92))
            opts = list(_ANSWER_LETTERS) + ["폰(없음)"]
            for opt in opts:
                btn = QPushButton(opt)
                btn.clicked.connect(lambda _=False, o=opt: self._answer_letter(o))
                self.answers.addWidget(btn)
        else:
            self._piece = random.choice(pool)
            letter = _LETTER[self._piece]
            self.lbl_q.setText(f"'{letter}' 는 어느 기물?")
            for pt in pool:
                btn = QPushButton(_GLYPH[pt])
                f = QFont("Segoe UI Symbol")
                f.setPixelSize(30)
                btn.setFont(f)
                btn.setMinimumWidth(64)
                btn.clicked.connect(lambda _=False, p=pt: self._answer_piece(p))
                self.answers.addWidget(btn)

    def _answer_letter(self, opt: str) -> None:
        if self._answered:
            return
        expect = "(없음)" if self._piece == chess.PAWN else _LETTER[self._piece]
        ok = opt == expect or (opt == "폰(없음)" and self._piece == chess.PAWN)
        self._finish(
            ok,
            f"'{opt}' 는 아니야. 정답: {expect}" if not ok else f"정답! {expect}",
        )

    def _answer_piece(self, pt: int) -> None:
        if self._answered:
            return
        ok = pt == self._piece
        name = _PIECE_KR[self._piece]
        self._finish(ok, "정답!" if ok else f"정답은 {name} ({_LETTER[self._piece]}) 야.")

    def _finish(self, ok: bool, msg: str) -> None:
        self._answered = True
        self.total += 1
        if ok:
            self.correct += 1
        self.lbl_score.setText(f"맞음 {self.correct} / {self.total}")
        self.lbl_fb.setText(msg + "   (다음 문제로)")
        theme.set_state(self.lbl_fb, "success" if ok else "danger")
        self._advance_timer.start(1100)

    def start(self) -> None:
        self.correct = 0
        self.total = 0
        self._advance_timer.stop()
        self._new_question()


# ---------------------------------------------------------------------------
# 2단계: 칸 이름
# ---------------------------------------------------------------------------

class Stage2Squares(_Stage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = ChessBoard()
        self.board.set_pick_mode(True)
        self.board.squarePicked.connect(self._on_pick)

        side = QVBoxLayout()
        side.setSpacing(12)
        self.lesson = self._lesson_card(
            "칸 이름 읽는 법",
            [
                "세로줄(파일)은 왼쪽부터 a b c d e f g h.",
                "가로줄(랭크)은 아래부터 1 2 3 4 5 6 7 8.",
                "그래서 왼쪽 아래 모서리는 a1, 오른쪽 위는 h8.",
                "이름은 항상 '파일 → 랭크' 순서. 예: e4.",
            ],
        )
        self.lbl_score = theme.label("", role="muted")
        self.lbl_q = theme.label("", role="h2")
        self.lbl_q.setWordWrap(True)
        self.answers = QVBoxLayout()
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setWordWrap(True)
        self.hint = theme.label("", role="muted")
        self.hint.setWordWrap(True)

        side.addWidget(self.lesson)
        side.addWidget(self.lbl_score)
        side.addWidget(self.lbl_q)
        side.addLayout(self.answers)
        side.addWidget(self.hint)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        self.correct = 0
        self.total = 0
        self._kind = "name"
        self._target = 0
        self._answered = False
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._new_question)
        self._new_question()

    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _name(self, sq: int) -> str:
        return chess.square_name(sq)

    def _new_question(self) -> None:
        self._clear(self.answers)
        self._answered = False
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")
        self.hint.setText("")
        self.lbl_score.setText(f"맞음 {self.correct} / {self.total}")
        self.board.clear_picks()
        self.board.clear_marks()

        self._target = chess.square(
            random.randrange(8), random.randrange(8)
        )
        self._kind = random.choice(["name", "place"])
        if self._kind == "name":
            self.board.glow_square(self._target)
            self.lbl_q.setText("파랗게 칠한 칸의 이름은?")
            opts = {self._target}
            # 그럴듯한 오답: 같은 파일 다른 랭크 / 같은 랭크 다른 파일 / 한 칸 옆
            for _ in range(20):
                if len(opts) >= 4:
                    break
                f = chess.square_file(self._target)
                r = chess.square_rank(self._target)
                pick = random.choice(
                    [
                        chess.square(f, random.randrange(8)),
                        chess.square(random.randrange(8), r),
                        chess.square(
                            min(7, max(0, f + random.choice([-1, 1]))),
                            min(7, max(0, r + random.choice([-1, 1]))),
                        ),
                    ]
                )
                opts.add(pick)
            names = sorted(self._name(s) for s in opts)
            random.shuffle(names)
            for nm in names:
                btn = QPushButton(nm)
                btn.clicked.connect(lambda _=False, n=nm: self._answer_name(n))
                self.answers.addWidget(btn)
        else:
            self.board.glow_square(None)
            nm = self._name(self._target)
            self.lbl_q.setText(f"보드에서 {nm} 칸을 클릭하세요.")
            self.hint.setText("아래 왼쪽이 a1 이고 오른쪽 위가 h8 이야.")

    def _answer_name(self, name: str) -> None:
        if self._answered:
            return
        ok = name == self._name(self._target)
        self._finish(
            ok,
            "정답!" if ok else f"정답: {self._name(self._target)}",
        )

    def _on_pick(self, sq: int) -> None:
        if self._answered or self._kind != "place":
            return
        ok = sq == self._target
        self._finish(ok, "정답!" if ok else f"정답: {self._name(self._target)} 이 칸이야.")

    def _finish(self, ok: bool, msg: str) -> None:
        self._answered = True
        self.total += 1
        if ok:
            self.correct += 1
        self.lbl_score.setText(f"맞음 {self.correct} / {self.total}")
        self.board.glow_square(self._target)
        self.lbl_fb.setText(msg + "   (다음 문제로)")
        theme.set_state(self.lbl_fb, "success" if ok else "danger")
        self._advance_timer.start(1200)

    def start(self) -> None:
        self.correct = 0
        self.total = 0
        self._advance_timer.stop()
        self.board.set_position(chess.STARTING_FEN)
        self.board.set_pick_mode(True)
        self._new_question()


# ---------------------------------------------------------------------------
# 3단계: 수 읽기 (SAN -> 보드)
# ---------------------------------------------------------------------------

class Stage3Read(_Stage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = read_ladder()
        self.idx = 0
        self._wrong_streak = 0
        self._last_uci: Optional[str] = None
        self._locked = False

        self.board = ChessBoard()
        self.board.moveMade.connect(self._on_move)
        self.board.movePlayedUci.connect(self._on_uci)

        side = QVBoxLayout()
        side.setSpacing(12)
        self.lesson = self._lesson_card(
            "수 읽는 법",
            [
                "기물 글자 + 목적지 칸. 예: Nf3 = 나이트(N)가 f3 칸으로.",
                "폰은 글자가 없다. 예: e4 = 폰이 e4 로.",
                "x = 잡기 (Bxc6 = 비숍이 c6 을 잡음).",
                "+ = 체크,  # = 체크메이트.",
                "O-O = 킹사이드 캐슬링, O-O-O = 퀸사이드 캐슬링.",
                "=Q = 퀸으로 승격.",
                "출발 칸은 안 쓴다. 둘 다 갈 수 있으면 파일/랭크를 붙인다(예: Nbd2).",
            ],
        )
        self.lbl_score = theme.label("", role="muted")
        self.lbl_q = theme.label("", role="h1")
        self.lbl_q.setWordWrap(True)
        self.lbl_decode = theme.label("", role="small")
        self.lbl_decode.setWordWrap(True)
        self.btn_reveal = QPushButton("모르겠음 (정답 보기)")
        self.btn_reveal.setProperty("variant", "ghost")
        self.btn_reveal.clicked.connect(self._reveal)
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setWordWrap(True)

        side.addWidget(self.lesson)
        side.addWidget(self.lbl_score)
        side.addWidget(self.lbl_q)
        side.addWidget(self.lbl_decode)
        side.addWidget(self.btn_reveal)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        from PySide6.QtCore import QTimer

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self.idx = 0
        self._lock(False)
        self._show()

    def _lock(self, on: bool) -> None:
        self._locked = on
        self.btn_reveal.setEnabled(not on)
        self.board.set_interactive(not on)

    def _cur(self) -> Optional[Dict[str, Any]]:
        if self.idx < len(self.items):
            return self.items[self.idx]
        return None

    def _show(self) -> None:
        self._timer.stop()
        item = self._cur()
        self.board.clear_marks()
        self._wrong_streak = 0
        self._last_uci = None
        if item is None:
            self._lock(True)
            self.lbl_q.setText("다 읽었어.")
            self.lbl_decode.setText("")
            self.lbl_fb.setText("3단계 끝. 위에서 '다시' 를 누르면 처음부터 다시 해.")
            theme.set_state(self.lbl_fb, "success")
            self.lbl_score.setText(f"{len(self.items)} / {len(self.items)}")
            return
        self._lock(False)
        self.board.set_position(item["fen"])
        self.lbl_score.setText(f"{self.idx + 1} / {len(self.items)}")
        self.lbl_q.setText(f"이 수를 보드에서 두세요:   {item['san']}")
        self.lbl_decode.setText(describe_san(item["san"]))
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")

    def _on_uci(self, uci: str) -> None:
        self._last_uci = uci

    def _on_move(self, san: str) -> None:
        item = self._cur()
        if item is None or self._locked:
            return
        if san == item["san"]:
            self._lock(True)
            if self._last_uci:
                self.board.show_hint(self._last_uci)
            self.lbl_fb.setText(f"정답!   {item['san']} = {describe_san(item['san'])}")
            theme.set_state(self.lbl_fb, "success")
            self._timer.start(1300)
            return
        self._wrong_streak += 1
        if self._last_uci:
            self.board.show_wrong(self._last_uci)
        if self._wrong_streak == 1:
            self.lbl_fb.setText("그 수가 아니야. 다시 해봐.")
            theme.set_state(self.lbl_fb, "danger")
            return
        self._show_answer()

    def _reveal(self) -> None:
        if self._locked:
            return
        self._lock(True)
        self._show_answer()

    def _show_answer(self) -> None:
        item = self._cur()
        if item is None:
            return
        from ui.widgets import _uci_of

        self._lock(True)
        uci = _uci_of(item["fen"], item["san"])
        if uci:
            self.board.show_hint(uci)
        self.lbl_fb.setText(
            f"정답: 초록 화살표   {item['san']} = {describe_san(item['san'])}"
        )
        theme.set_state(self.lbl_fb, "danger")
        self._timer.start(2000)

    def _advance(self) -> None:
        self._wrong_streak = 0
        self.idx += 1
        self._show()


# ---------------------------------------------------------------------------
# 4단계: 머릿속 보드 (보드 가리고 칸 짚기)
# ---------------------------------------------------------------------------

class Stage4Blind(_Stage):
    LINE = ["e4", "e5", "Nf3", "Nc6", "Bb5"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = _steps_from_sans(self.LINE)
        self.idx = 0
        self._picked: Optional[int] = None
        self._wrong_streak = 0

        self.board = ChessBoard()
        self.board.set_pick_mode(True)
        self.board.set_hide_pieces(True)
        self.board.picked.connect(self._on_picked)

        side = QVBoxLayout()
        side.setSpacing(12)
        self.lesson = self._lesson_card(
            "머릿속 보드",
            [
                "보드를 가렸다. 기보만 보고 머릿속으로 보드를 그려봐.",
                "수를 읽고, 어느 칸에서 어느 칸으로 가는지 두 칸을 차례로 클릭.",
                "예: e4 → e2 칸, 그다음 e4 칸.",
                "처음엔 어렵다. 힌트로 출발 칸을 볼 수 있어.",
            ],
        )
        self.lbl_moves = theme.label("", role="h1")
        self.lbl_moves.setWordWrap(True)
        self.lbl_q = theme.label("", role="h2")
        self.lbl_q.setWordWrap(True)
        self.btn_hint = QPushButton("힌트 (출발 칸 보기)")
        self.btn_hint.setProperty("variant", "ghost")
        self.btn_hint.clicked.connect(self._hint)
        self.btn_reveal = QPushButton("정답 칸 보기")
        self.btn_reveal.setProperty("variant", "ghost")
        self.btn_reveal.clicked.connect(self._reveal)
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setWordWrap(True)

        side.addWidget(self.lesson)
        side.addWidget(self.lbl_moves)
        side.addWidget(self.lbl_q)
        side.addWidget(self.btn_hint)
        side.addWidget(self.btn_reveal)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        from PySide6.QtCore import QTimer

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self.idx = 0
        # 시작 국면은 백 차례라 백이 아래에 온다(a1 이 왼쪽 아래).
        self.board.set_position(chess.STARTING_FEN)
        self.board.set_hide_pieces(True)
        self.board.set_pick_mode(True)
        self._show()

    def _cur(self) -> Optional[Dict[str, Any]]:
        if self.idx < len(self.steps):
            return self.steps[self.idx]
        return None

    def _notation(self) -> str:
        out = []
        for i, st in enumerate(self.steps):
            token = st["san"]
            if i % 2 == 0:
                out.append(f"{i // 2 + 1}. {token}")
            else:
                out.append(token)
        return " ".join(out)

    def _show(self) -> None:
        self._timer.stop()
        st = self._cur()
        self.board.clear_marks()
        self.board.clear_picks()
        self._picked = None
        self._wrong_streak = 0
        self.lbl_moves.setText(self._notation())
        if st is None:
            self._finish_line()
            return
        self.board.set_pick_mode(True)
        self.lbl_q.setText(
            f"{self.idx + 1}번째 수:   {st['san']}   → 어느 칸에서 어느 칸으로?"
        )
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")

    def _finish_line(self) -> None:
        self.board.set_hide_pieces(False)
        # 실제 최종 국면을 보여준다.
        b = chess.Board()
        for st in self.steps:
            b.push(b.parse_san(st["san"]))
        self.board.set_position(b.fen())
        self.board.set_pick_mode(False)
        self.board.set_interactive(False)
        self.lbl_q.setText("끝! 이게 지금까지 둔 수의 실제 보드 모습이야.")
        self.lbl_fb.setText("머릿속 그림이랑 얼마나 비슷했어? 위에서 '다시' 로 또 할 수 있어.")
        theme.set_state(self.lbl_fb, "success")

    def _on_picked(self, frm: int, to: int) -> None:
        st = self._cur()
        if st is None:
            return
        if frm == st["from"] and to == st["to"]:
            self.board.clear_picks()
            self.board.show_hint(_uci(st))
            self.lbl_fb.setText(f"정답!   {st['san']} = {chev(st['from'])} → {chev(st['to'])}")
            theme.set_state(self.lbl_fb, "success")
            self.board.set_pick_mode(False)
            self._timer.start(1200)
            return
        self._wrong_streak += 1
        self.board.clear_picks()
        self.board.show_wrong(_uci(st))
        if self._wrong_streak == 1:
            self.lbl_fb.setText("그 칸이 아니야. 다시 해봐. (힌트 버튼 있음)")
            theme.set_state(self.lbl_fb, "danger")
            return
        self._reveal()

    def _hint(self) -> None:
        st = self._cur()
        if st is None:
            return
        self.board.glow_square(st["from"])
        self.lbl_fb.setText(f"출발 칸은 {chev(st['from'])} 이야. 도착 칸을 클릭해봐.")
        theme.set_state(self.lbl_fb, "muted")

    def _reveal(self) -> None:
        st = self._cur()
        if st is None:
            return
        from ui.widgets import _uci_of

        uci = _uci_of(st["fen"], st["san"])
        if uci:
            self.board.show_hint(uci)
        self.board.set_pick_mode(False)
        self.lbl_fb.setText(
            f"정답: {st['san']} = {chev(st['from'])} → {chev(st['to'])} (초록 화살표)"
        )
        theme.set_state(self.lbl_fb, "danger")
        self._timer.start(1800)

    def _advance(self) -> None:
        self._wrong_streak = 0
        self.idx += 1
        self.board.clear_marks()
        self._show()


def _uci(st: Dict[str, Any]) -> str:
    return chess.Move(st["from"], st["to"]).uci()


def chev(sq: int) -> str:
    return chess.square_name(sq)


# ---------------------------------------------------------------------------
# 대화상자
# ---------------------------------------------------------------------------

_STAGES = [
    ("1단계 · 기물과 글자", Stage1Pieces),
    ("2단계 · 칸 이름", Stage2Squares),
    ("3단계 · 수 읽기", Stage3Read),
    ("4단계 · 머릿속 보드", Stage4Blind),
]


class NotationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("노테이션 배우기")
        self.resize(1000, 740)

        self.stack = QStackedWidget()
        self.pages: List[_Stage] = []
        self.buttons: List[QPushButton] = []

        nav = QHBoxLayout()
        nav.setSpacing(8)
        for i, (name, cls) in enumerate(_STAGES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=i: self.goto(n))
            self.buttons.append(btn)
            nav.addWidget(btn)
            page = cls()
            self.pages.append(page)
            self.stack.addWidget(page)
        nav.addStretch(1)
        self.btn_restart = QPushButton("다시")
        self.btn_restart.setProperty("variant", "ghost")
        self.btn_restart.clicked.connect(lambda: self.pages[self.stack.currentIndex()].start())
        nav.addWidget(self.btn_restart)

        intro = theme.label(
            "체스 기보를 하나도 몰라도 된다. 1단계부터 순서대로 하면 마지막엔 "
            "기보만 보고 머릿속으로 보드를 그릴 수 있게 된다.",
            role="muted",
        )
        intro.setWordWrap(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(theme.label("노테이션 배우기", role="h1"))
        root.addWidget(intro)
        root.addLayout(nav)
        root.addWidget(self.stack, 1)

        self.goto(0)

    def goto(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)
        self.pages[idx].start()
