"""노테이션 배우기 - 하나도 모르는 사람 기준 4단계.

    1단계  기물 ↔ 글자      K Q R B N, 폰은 글자 없음
    2단계  칸 이름          a1 ~ h8 (난이도: 모서리 → 가장자리 → 전체)
    3단계  수 읽기          "Nf3", "exd5", "Nbd2", "axb8=Q", "exd6"(앙파상)
    4단계  머릿속 보드      기보만 보고 어느 칸→어느 칸인지 짚기

이전 버전은 문제가 고정 몇 개뿐이고 점수가 매번 리셋되는 '퀴즈 쇼'였다.
이번엔 학습 시스템 쪽으로 손을 봤다.

  * 단계별 통과 기준(정답 수 + 정답률)을 두고 진행을 파일로 저장한다.
  * 틀린 항목을 더 자주 낸다(가중 선택 + 같은 판에서 재출제).
  * 3단계 문제 풀을 오프닝 라인 + 특수 개념으로 크게 늘렸다.
  * 3단계는 '읽는 법'을 풀기 전에도 볼 수 있다(기본 켜짐). 답을 본 뒤에만
    알려주던 순서를 뒤집었다.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

import chess
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui import theme
from ui.board import ChessBoard
from ui.notation_pool import (
    CONCEPT_KR,
    concept_tip,
    item_id,
    line_steps,
    stage2_targets,
    stage3_pool,
    stage4_lines,
)
from ui.notation_progress import Record

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

_PIECE_TIP = {
    chess.KING: "K = 킹(King). 가장 중요한 기물.",
    chess.QUEEN: "Q = 퀸(Queen).",
    chess.ROOK: "R = 룩(Rook).",
    chess.BISHOP: "B = 비숍(Bishop).",
    chess.KNIGHT: "N = 나이트(kNight). K(킹)와 헷갈리니 조심.",
    chess.PAWN: "폰은 글자가 없다. 목적지 칸만 쓴다. 예: e4",
}


def glyph_label(piece_type: int, size: int = 56) -> QLabel:
    lbl = QLabel(_GLYPH[piece_type])
    lbl.setAlignment(Qt.AlignCenter)
    # 주의: 테마의 `QWidget { font-size: 13px }` 가 위젯 setFont() 를 덮어쓴다.
    # (show 될 때 polish 되면서 13px 로 리셋됨) 그래서 QSS 로 지정해야 먹는다.
    lbl.setStyleSheet(
        f'color: #f2f4f8; font-family: "Segoe UI Symbol"; font-size: {size}px;'
    )
    lbl.setMinimumWidth(size + 20)
    lbl.setMinimumHeight(size + 20)
    return lbl


def big_text_label(text: str, size: int = 72) -> QLabel:
    """글자 하나를 크게 보여주는 라벨(letter→기물 문제용)."""
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"color: #f2f4f8; font-weight: 700; font-size: {size}px;")
    lbl.setMinimumHeight(size + 20)
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
        # exd5 처럼 폰이 잡을 때는 출발 파일 글자가 붙는다.
        file_hint = head.replace("x", "")
        if file_hint and file_hint[0].isalpha() and file_hint[0] not in _LETTER_PIECE:
            parts.append(f"'{file_hint}' 파일의 폰이")
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
    return line_steps(sans)


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


def read_ladder() -> List[Dict[str, Any]]:
    """3단계 문제 풀(쉬운 것부터). 이제 고정 9개가 아니라 넓은 풀이다."""
    return stage3_pool()


def _two_col(board: QWidget, side: QVBoxLayout) -> QHBoxLayout:
    body = QHBoxLayout()
    body.setSpacing(18)
    body.addWidget(board, 3)
    wrap = QWidget()
    wrap.setLayout(side)
    body.addWidget(wrap, 2)
    return body


def chev(sq: int) -> str:
    return chess.square_name(sq)


class MasteryBar(QWidget):
    """단계 통과 진행을 보여준다. 이전엔 이게 없어서 그냥 넘어갈 수 있었다."""

    def __init__(self, rec: Record, parent=None):
        super().__init__(parent)
        self.rec = rec
        self.lbl = theme.label("", role="caption")
        self.lbl.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, max(1, rec.goal))
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.lbl)
        lay.addWidget(self.bar)
        self.refresh()

    def refresh(self) -> None:
        rec = self.rec
        acc = rec.accuracy() * 100
        if rec.passed:
            self.lbl.setText(
                f"통과 ✓   정답 {rec.correct} · 정답률 {acc:.0f}%"
            )
        else:
            self.lbl.setText(
                f"통과 기준 정답 {rec.goal}개 · 정답률 "
                f"{int(rec.accuracy_goal * 100)}% 이상   "
                f"(지금 {rec.correct}개 · {acc:.0f}%)"
            )
        self.bar.setValue(min(rec.correct, rec.goal))


class _Stage(QWidget):
    """단계 공통 뼈대."""

    key = ""
    goal = 15
    accuracy = 0.8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = Record(self.key, goal=self.goal, accuracy=self.accuracy) if self.key else None

    def _record(self, ok: bool, item_id_: str) -> None:
        if self.prog is None:
            return
        self.prog.note(item_id_, ok)
        self.prog.flush()
        bar = getattr(self, "mastery", None)
        if bar is not None:
            bar.refresh()

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

    # 개발 편의: 화면 구성 없이 시작만 되는지 보는 테스트도 있어서 기본 제공.
    def start(self) -> None:  # pragma: no cover - 각 단계가 덮어쓴다
        pass


# ---------------------------------------------------------------------------
# 1단계: 기물 ↔ 글자
# ---------------------------------------------------------------------------

class Stage1Pieces(_Stage):
    key = "stage1"
    goal = 15
    accuracy = 0.8

    def __init__(self, parent=None):
        super().__init__(parent)
        legend = theme.card(flat=True)
        gl = QVBoxLayout(legend)
        gl.setContentsMargins(14, 10, 14, 10)
        gl.setSpacing(6)
        gl.addWidget(theme.label("기물과 글자", role="h2"))
        # 세로로 길면 창이 화면 밖으로 나가므로 가로 한 줄로 압축한다.
        strip = QHBoxLayout()
        strip.setSpacing(16)
        rows = [
            (chess.KING, "K", "킹"),
            (chess.QUEEN, "Q", "퀸"),
            (chess.ROOK, "R", "룩"),
            (chess.BISHOP, "B", "비숍"),
            (chess.KNIGHT, "N", "나이트"),
            (chess.PAWN, "(없음)", "폰"),
        ]
        for pt, letter, name in rows:
            cell = QVBoxLayout()
            cell.setSpacing(0)
            cell.addWidget(glyph_label(pt, 36), 0, Qt.AlignHCenter)
            cell.addWidget(theme.label(letter, role="h2"), 0, Qt.AlignHCenter)
            cell.addWidget(theme.label(name, role="muted"), 0, Qt.AlignHCenter)
            strip.addLayout(cell)
        strip.addStretch(1)
        gl.addLayout(strip)
        note = theme.label(
            "나이트는 Knight 라서 K 가 아니라 N. K 는 킹. "
            "폰은 글자 없이 목적지 칸만 쓴다(예: e4).",
            role="small",
        )
        note.setWordWrap(True)
        gl.addWidget(note)

        self.mastery = MasteryBar(self.prog)
        self.lbl_q = theme.label("", role="h1")
        self.lbl_q.setAlignment(Qt.AlignCenter)
        self.piece_box = QVBoxLayout()
        self.piece_box.setAlignment(Qt.AlignCenter)
        self.answers = QHBoxLayout()
        self.answers.setAlignment(Qt.AlignCenter)
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setAlignment(Qt.AlignCenter)
        self.lbl_fb.setWordWrap(True)
        self.btn_next = QPushButton("다음 ▶")
        self.btn_next.setProperty("variant", "ghost")
        self.btn_next.clicked.connect(self._new_question)
        self.btn_next.setEnabled(False)

        quiz = theme.card()
        qlay = QVBoxLayout(quiz)
        qlay.setContentsMargins(18, 16, 18, 16)
        qlay.setSpacing(14)
        qlay.addWidget(self.mastery)
        qlay.addWidget(self.lbl_q)
        qlay.addLayout(self.piece_box, 1)
        qlay.addLayout(self.answers)
        qlay.addWidget(self.lbl_fb)
        qlay.addWidget(self.btn_next, 0, Qt.AlignCenter)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(12)
        root.addWidget(legend)
        root.addWidget(quiz, 1)

        self._piece: Optional[int] = None
        self._kind = "glyph2letter"
        self._answered = False
        self._last_id = ""
        self._queue: List[str] = []
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

    def _ids(self) -> List[str]:
        return [f"{k}:{p}" for k in ("glyph2letter", "letter2glyph")
                for p in (chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP,
                          chess.KNIGHT, chess.PAWN)]

    def _next_id(self) -> str:
        if not self._queue:
            # 약점 가중치로 뽑되 같은 게 연달아 나오지 않게 중복을 걸러 담는다.
            pool = self._ids()
            chosen: List[str] = []
            guard = 0
            while len(chosen) < 8 and guard < 80:
                guard += 1
                pick = self.prog.pick(pool) if self.prog else random.choice(pool)
                if pick in chosen:
                    continue
                chosen.append(pick)
            self._queue.extend(chosen)
        return self._queue.pop(0)

    def _new_question(self) -> None:
        self._advance_timer.stop()
        self._clear(self.piece_box)
        self._clear(self.answers)
        self._answered = False
        self.btn_next.setEnabled(False)
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")

        self._last_id = self._next_id()
        self._kind, str_piece = self._last_id.split(":", 1)
        self._piece = int(str_piece)
        pool = [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
        if self._kind == "glyph2letter":
            self.lbl_q.setText("이 기물의 글자는?")
            self.piece_box.addWidget(glyph_label(self._piece, 96))
            for opt in list(_ANSWER_LETTERS) + ["폰(없음)"]:
                btn = QPushButton(opt)
                btn.setMinimumWidth(64)
                btn.clicked.connect(lambda _=False, o=opt: self._answer_letter(o))
                self.answers.addWidget(btn)
        else:
            letter = "(없음)" if self._piece == chess.PAWN else _LETTER[self._piece]
            self.lbl_q.setText("이 글자는 어느 기물?")
            self.piece_box.addWidget(big_text_label(letter, 96))
            for pt in pool + [chess.PAWN]:
                btn = QPushButton(_GLYPH[pt])
                # 위와 같은 이유로 폰트는 QSS 로 지정한다.
                btn.setStyleSheet('font-family: "Segoe UI Symbol"; font-size: 34px;')
                btn.setMinimumWidth(72)
                btn.clicked.connect(lambda _=False, p=pt: self._answer_piece(p))
                self.answers.addWidget(btn)

    def _answer_letter(self, opt: str) -> None:
        if self._answered:
            return
        expect = "(없음)" if self._piece == chess.PAWN else _LETTER[self._piece]
        ok = opt == expect or (opt == "폰(없음)" and self._piece == chess.PAWN)
        self._finish(ok, f"정답! {expect}" if ok else f"'{opt}' 는 아니야. 정답: {expect}")

    def _answer_piece(self, pt: int) -> None:
        if self._answered:
            return
        ok = pt == self._piece
        name = _PIECE_KR[self._piece]
        lab = "(없음)" if self._piece == chess.PAWN else _LETTER[self._piece]
        self._finish(ok, "정답!" if ok else f"정답은 {name} ({lab}) 야.")

    def _finish(self, ok: bool, msg: str) -> None:
        self._answered = True
        self._record(ok, self._last_id)
        if not ok:
            msg += "   " + _PIECE_TIP[self._piece]
            # 틀린 건 잠깐 뒤에 다시 나오게 큐에 되돌린다.
            self._queue.insert(min(2, len(self._queue)), self._last_id)
        self.lbl_fb.setText(msg)
        theme.set_state(self.lbl_fb, "success" if ok else "danger")
        self.btn_next.setEnabled(True)
        if ok:
            self._advance_timer.start(900)

    def start(self) -> None:
        self._advance_timer.stop()
        self._queue = []
        self._new_question()


# ---------------------------------------------------------------------------
# 2단계: 칸 이름 (난이도: 모서리 → 가장자리 → 전체)
# ---------------------------------------------------------------------------

class Stage2Squares(_Stage):
    key = "stage2"
    goal = 20
    accuracy = 0.8

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
                "처음엔 모서리·중앙만 나오고, 맞히면 가장자리 → 전체로 넓어진다.",
            ],
        )
        self.mastery = MasteryBar(self.prog)
        self.lbl_q = theme.label("", role="h2")
        self.lbl_q.setWordWrap(True)
        self.answers = QVBoxLayout()
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setWordWrap(True)
        self.hint = theme.label("", role="muted")
        self.hint.setWordWrap(True)
        self.btn_hint = QPushButton("힌트 (하나씩)")
        self.btn_hint.setProperty("variant", "ghost")
        self.btn_hint.clicked.connect(self._hint)
        self.btn_next = QPushButton("다음 ▶")
        self.btn_next.setProperty("variant", "ghost")
        self.btn_next.clicked.connect(self._new_question)
        self.btn_next.setEnabled(False)

        side.addWidget(self.lesson)
        side.addWidget(self.mastery)
        side.addWidget(self.lbl_q)
        side.addLayout(self.answers)
        side.addWidget(self.hint)
        side.addWidget(self.btn_hint)
        side.addWidget(self.btn_next)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        self._kind = "name"
        self._target = 0
        self._answered = False
        self._hint_i = 0
        self._last_id = ""
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

    def _level(self) -> int:
        c = self.prog.correct if self.prog else 0
        if c < 8:
            return 0
        if c < 18:
            return 1
        return 2

    def _new_question(self) -> None:
        self._advance_timer.stop()
        self._clear(self.answers)
        self._answered = False
        self._hint_i = 0
        self.btn_next.setEnabled(False)
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")
        self.hint.setText("")
        self.board.clear_picks()
        self.board.clear_marks()
        # 기물이 있으면 산만하다는 지적이 있어서 빈 보드로 칸만 본다.
        self.board.set_position("8/8/8/8/8/8/8/8 w - - 0 1")
        self.board.set_pick_mode(True)

        names = stage2_targets(self._level())
        self._target = chess.parse_square(random.choice(names))
        self._kind = random.choice(["name", "place"])
        self._last_id = f"{self._kind}:{self._name(self._target)}"
        if self._kind == "name":
            self.board.glow_square(self._target)
            self.lbl_q.setText("파랗게 칠한 칸의 이름은?")
            opts = {self._target}
            for _ in range(24):
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
            opts_names = sorted(self._name(s) for s in opts)
            random.shuffle(opts_names)
            for nm in opts_names:
                btn = QPushButton(nm)
                btn.clicked.connect(lambda _=False, n=nm: self._answer_name(n))
                self.answers.addWidget(btn)
        else:
            self.board.glow_square(None)
            nm = self._name(self._target)
            self.lbl_q.setText(f"보드에서 {nm} 칸을 클릭하세요.")

    def _answer_name(self, name: str) -> None:
        if self._answered:
            return
        ok = name == self._name(self._target)
        self._finish(ok, "정답!" if ok else f"정답: {self._name(self._target)}")

    def _on_pick(self, sq: int) -> None:
        if self._answered or self._kind != "place":
            return
        ok = sq == self._target
        self._finish(ok, "정답!" if ok else f"정답: {self._name(self._target)} 이 칸이야.")

    def _hint(self) -> None:
        self._hint_i += 1
        nm = self._name(self._target)
        file_ch = nm[0]
        rank_ch = nm[1]
        if self._hint_i == 1:
            self.hint.setText(f"세로줄 글자는 '{file_ch}'. (왼쪽부터 a b c …)")
        elif self._hint_i == 2:
            self.hint.setText(f"가로줄 숫자는 '{rank_ch}'. (아래부터 1 2 3 …)")
        else:
            self.hint.setText(f"파일 먼저, 랭크 다음 → {nm}")

    def _finish(self, ok: bool, msg: str) -> None:
        self._answered = True
        self._record(ok, self._last_id)
        self.board.glow_square(self._target)
        self.lbl_fb.setText(msg)
        theme.set_state(self.lbl_fb, "success" if ok else "danger")
        self.btn_next.setEnabled(True)
        if ok:
            self._advance_timer.start(1200)

    def start(self) -> None:
        self._advance_timer.stop()
        self._new_question()


# ---------------------------------------------------------------------------
# 3단계: 수 읽기 (SAN -> 보드)
# ---------------------------------------------------------------------------

class Stage3Read(_Stage):
    key = "stage3"
    goal = 24
    accuracy = 0.8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: List[Dict[str, Any]] = read_ladder()
        self._by_id = {item_id(it): it for it in self.items}
        self.cur: Optional[Dict[str, Any]] = None
        self._last_uci: Optional[str] = None
        self._locked = False
        self._wrong_streak = 0
        self._queue: List[str] = []

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
                "x = 잡기. Bxc6 = 비숍이 c6 을 잡음. 폰이 잡으면 파일 글자: exd5.",
                "+ = 체크,  # = 체크메이트.",
                "O-O = 킹사이드 캐슬링, O-O-O = 퀸사이드 캐슬링.",
                "=Q = 퀸으로 승격. 잡으면서 하면 axb8=Q.",
                "같은 기물이 둘 다 갈 수 있으면 구분 표시: Nbd2(파일) / R1a3(랭크).",
                "앙파상은 폰이 잡는 것처럼 파일 글자로: exd6.",
            ],
        )
        self.mastery = MasteryBar(self.prog)
        self.cb_explain = QCheckBox("읽는 법 보면서 하기 (끄면 스스로 풀기)")
        self.cb_explain.setChecked(True)
        self.cb_explain.stateChanged.connect(self._toggle_explain)
        self.lbl_q = theme.label("", role="h1")
        self.lbl_q.setWordWrap(True)
        self.lbl_decode = theme.label("", role="small")
        self.lbl_decode.setWordWrap(True)
        self.lbl_tip = theme.label("", role="muted")
        self.lbl_tip.setWordWrap(True)
        self.btn_reveal = QPushButton("모르겠음 (정답 보기)")
        self.btn_reveal.setProperty("variant", "ghost")
        self.btn_reveal.clicked.connect(self._reveal)
        self.lbl_fb = theme.label("", role="small")
        self.lbl_fb.setWordWrap(True)

        side.addWidget(self.lesson)
        side.addWidget(self.mastery)
        side.addWidget(self.cb_explain)
        side.addWidget(self.lbl_q)
        side.addWidget(self.lbl_decode)
        side.addWidget(self.lbl_tip)
        side.addWidget(self.btn_reveal)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self._timer.stop()
        self._queue = []
        self._next()

    # -- 문제 선택 ----------------------------------------------------------
    def _fill_queue(self) -> None:
        pool = list(self._by_id.keys())
        chosen: List[str] = []
        guard = 0
        while len(chosen) < 6 and guard < 60:
            guard += 1
            pick = self.prog.pick(pool) if self.prog else random.choice(pool)
            if pick in chosen:
                continue
            chosen.append(pick)
        self._queue.extend(chosen)

    def _next_id(self) -> str:
        if not self._queue:
            self._fill_queue()
        return self._queue.pop(0)

    def _cur(self) -> Optional[Dict[str, Any]]:
        return self.cur

    def _next(self) -> None:
        self.cur = self._by_id[self._next_id()]
        self._show()

    def _advance(self) -> None:
        self._next()

    # -- 화면 --------------------------------------------------------------
    def _lock(self, on: bool) -> None:
        self._locked = on
        self.btn_reveal.setEnabled(not on)
        self.board.set_interactive(not on)

    def _toggle_explain(self) -> None:
        if self.cur is not None and not self._locked:
            self.lbl_decode.setText(
                describe_san(self.cur["san"]) if self.cb_explain.isChecked() else ""
            )

    def _show(self) -> None:
        self._timer.stop()
        item = self.cur
        self.board.clear_marks()
        self._wrong_streak = 0
        self._last_uci = None
        self.lbl_tip.setText("")
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")
        self._lock(False)
        self.board.set_position(item["fen"])
        self.lbl_q.setText(f"이 수를 보드에서 두세요:   {item['san']}")
        # 학습 단계라 '읽는 법'을 풀기 전에도 볼 수 있다(끄면 스스로 풀기).
        self.lbl_decode.setText(
            describe_san(item["san"]) if self.cb_explain.isChecked() else ""
        )

    def _on_uci(self, uci: str) -> None:
        self._last_uci = uci

    def _on_move(self, san: str) -> None:
        item = self.cur
        if item is None or self._locked:
            return
        if san == item["san"]:
            self._lock(True)
            if self._last_uci:
                self.board.show_hint(self._last_uci)
            self.lbl_decode.setText(describe_san(item["san"]))
            self.lbl_fb.setText(f"정답!   {item['san']}")
            theme.set_state(self.lbl_fb, "success")
            self._record(True, item_id(item))
            self._timer.start(1400)
            return
        self._wrong_streak += 1
        if self._last_uci:
            self.board.show_wrong(self._last_uci)
        # 설명을 껐을 때만 개념 힌트를 준다(켰으면 이미 보이니까).
        if not self.cb_explain.isChecked():
            self.lbl_tip.setText(concept_tip(item.get("concept", "")))
        self.lbl_fb.setText("그 수가 아니야. 다시 해봐.  (정답을 보려면 '모르겠음')")
        theme.set_state(self.lbl_fb, "danger")

    def _reveal(self) -> None:
        if self._locked:
            return
        self._lock(True)
        item = self.cur
        if item is None:
            return
        from ui.widgets import _uci_of

        uci = _uci_of(item["fen"], item["san"])
        if uci:
            self.board.show_hint(uci)
        self.lbl_decode.setText(describe_san(item["san"]))
        self.lbl_tip.setText(
            f"{CONCEPT_KR.get(item.get('concept',''), '')}  {concept_tip(item.get('concept',''))}"
        )
        self.lbl_fb.setText(f"정답: 초록 화살표   {item['san']}")
        theme.set_state(self.lbl_fb, "danger")
        self._record(False, item_id(item))
        # 틀린 문제는 잠깐 뒤 다시 나오게 큐에 넣는다(바로 반복되지 않게 최소 2칸 뒤).
        if len(self._queue) < 2:
            self._fill_queue()
        self._queue.insert(min(2, len(self._queue)), item_id(item))
        self._timer.start(2000)


# ---------------------------------------------------------------------------
# 4단계: 머릿속 보드 (기보만 보고 칸 짚기)
# ---------------------------------------------------------------------------

class Stage4Blind(_Stage):
    key = "stage4"
    goal = 16
    accuracy = 0.75

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines = stage4_lines()
        self._line_idx = 0
        self.steps = line_steps(self.lines[0][1])
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
                "기보만 보고 머릿속으로 보드를 그려봐.",
                "수를 읽고, 어느 칸에서 어느 칸으로 가는지 두 칸을 차례로 클릭.",
                "예: e4 → e2 칸, 그다음 e4 칸.",
                "처음엔 어렵다. '기물 보이기'로 눈으로 익힌 뒤 가리고 해봐.",
            ],
        )
        self.mastery = MasteryBar(self.prog)
        self.cb_show = QCheckBox("기물 보이기 (연습용)")
        self.cb_show.setChecked(False)
        self.cb_show.stateChanged.connect(self._toggle_show)
        self.lbl_line = theme.label("", role="h2")
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
        side.addWidget(self.mastery)
        side.addWidget(self.lbl_line)
        side.addWidget(self.lbl_moves)
        side.addWidget(self.lbl_q)
        side.addWidget(self.cb_show)
        side.addWidget(self.btn_hint)
        side.addWidget(self.btn_reveal)
        side.addWidget(self.lbl_fb)
        side.addStretch(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.addLayout(_two_col(self.board, side), 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self._timer.stop()
        ids = [str(i) for i in range(len(self.lines))]
        if self.prog:
            self._line_idx = int(self.prog.pick(ids))
        else:
            self._line_idx = random.randrange(len(self.lines))
        self._load_line()

    def _load_line(self) -> None:
        name, sans = self.lines[self._line_idx]
        self.steps = line_steps(sans)
        self.idx = 0
        self.lbl_line.setText(f"라인: {name}")
        self._show()

    def _cur(self) -> Optional[Dict[str, Any]]:
        if self.idx < len(self.steps):
            return self.steps[self.idx]
        return None

    def _notation(self) -> str:
        out = []
        for i, st in enumerate(self.steps):
            if i % 2 == 0:
                out.append(f"{i // 2 + 1}. {st['san']}")
            else:
                out.append(st["san"])
        return " ".join(out)

    def _item_id(self) -> str:
        return f"{self._line_idx}:{self.idx}"

    def _show(self) -> None:
        self._timer.stop()
        st = self._cur()
        self.board.clear_marks()
        self.board.clear_picks()
        self._picked = None
        self._wrong_streak = 0
        self.lbl_moves.setText(self._notation())
        self.board.set_interactive(True)
        self.board.set_pick_mode(True)
        self.board.set_hide_pieces(not self.cb_show.isChecked())
        if st is None:
            self._finish_line()
            return
        self.lbl_q.setText(
            f"{self.idx + 1}번째 수:   {st['san']}   → 어느 칸에서 어느 칸으로?"
        )
        self.lbl_fb.setText("")
        theme.set_state(self.lbl_fb, "muted")

    def _toggle_show(self) -> None:
        self.board.set_hide_pieces(not self.cb_show.isChecked())

    def _finish_line(self) -> None:
        self.board.set_hide_pieces(False)
        b = chess.Board()
        for st in self.steps:
            b.push(b.parse_san(st["san"]))
        self.board.set_position(b.fen())
        self.board.set_pick_mode(False)
        self.board.set_interactive(False)
        self.lbl_q.setText("끝! 이게 지금까지 둔 수의 실제 보드 모습이야.")
        self.lbl_fb.setText("머릿속 그림이랑 얼마나 비슷했어? '다시' 로 다른 라인도 해봐.")
        theme.set_state(self.lbl_fb, "success")

    def _on_picked(self, frm: int, to: int) -> None:
        st = self._cur()
        if st is None:
            return
        if frm == st["from"] and to == st["to"]:
            self.board.clear_picks()
            self.board.show_hint(chess.Move(frm, to).uci())
            self.lbl_fb.setText(f"정답!   {st['san']} = {chev(st['from'])} → {chev(st['to'])}")
            theme.set_state(self.lbl_fb, "success")
            self.board.set_pick_mode(False)
            self._record(True, self._item_id())
            self._timer.start(1200)
            return
        self._wrong_streak += 1
        self.board.clear_picks()
        self.board.show_wrong(chess.Move(frm, to).uci())
        self.lbl_fb.setText("그 칸이 아니야. 다시 해봐. (힌트 버튼 있음)")
        theme.set_state(self.lbl_fb, "danger")

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
        self._record(False, self._item_id())
        self._timer.start(1800)

    def _advance(self) -> None:
        self._wrong_streak = 0
        self.idx += 1
        self.board.clear_marks()
        self._show()


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
        # 레이아웃 최소 크기가 화면보다 클 수 있어서, 창이 줄어들 수 있게 바닥을 낮춘다.
        # (넘치는 단계 내용은 아래 스크롤 영역이 처리)
        self.setMinimumSize(620, 420)

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
            "기보만 보고 머릿속으로 보드를 그릴 수 있게 된다. 진행 상황은 저장되고, "
            "틀린 문제는 더 자주 나온다.",
            role="muted",
        )
        intro.setWordWrap(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        root.addWidget(theme.label("노테이션 배우기", role="h1"))
        root.addWidget(intro)
        root.addLayout(nav)
        # 단계 내용이 세로로 길어 창이 화면 밖으로 나갈 수 있으므로 스크롤로 감싼다.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(self.stack)
        root.addWidget(scroll, 1)

        self.resize(1040, 820)
        self._refresh_buttons()
        self.goto(self._first_unpassed(), force=True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 화면 작업영역에 맞춰 크기를 줄이고 화면 안으로 위치시킨다.
        scr = self.screen()
        if scr is None:
            return
        area = scr.availableGeometry()
        self.resize(
            min(self.width(), area.width() - 40),
            min(self.height(), area.height() - 60),
        )
        pos = area.center() - self.rect().center()
        pos.setX(max(area.left(), min(pos.x(), area.right() - self.width())))
        pos.setY(max(area.top(), min(pos.y(), area.bottom() - self.height())))
        self.move(pos)

    def _passed(self, idx: int) -> bool:
        page = self.pages[idx]
        return bool(page.prog and page.prog.passed)

    def _first_unpassed(self) -> int:
        for i in range(len(self.pages)):
            if not self._passed(i):
                return i
        return len(self.pages) - 1

    def _refresh_buttons(self) -> None:
        for i, btn in enumerate(self.buttons):
            locked = i > 0 and not self._passed(i - 1)
            name = _STAGES[i][0]
            btn.setText(("🔒 " if locked else "") + name)
            btn.setToolTip(
                "이전 단계를 통과해야 열린다." if locked else "바로 시작"
            )

    def goto(self, idx: int, force: bool = False) -> None:
        if not force and idx > 0 and not self._passed(idx - 1):
            ans = QMessageBox.question(
                self,
                "아직 이전 단계 통과 전",
                f"{_STAGES[idx-1][0]} 를 아직 통과하지 못했다.\n그래도 이 단계를 볼까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)
        self.pages[idx].start()
        self._refresh_buttons()
