"""Interactive chess board (click-to-move).

The review drill used to make you *type* SAN, which is useless if you never
learned notation. This draws a real board and lets you move a piece with the
mouse, and it draws the correct move as an arrow so a wrong answer is still
something you can *see* rather than read.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QMenu, QWidget

# 채워진 글리프(U+265A..)를 흑/백 모두에 쓰고 색만 바꾼다. 윤곽선 글리프보다
# 굵게 보여서 작은 보드에서도 구분이 잘 된다.
_GLYPH = {
    chess.KING: "\u265a",
    chess.QUEEN: "\u265b",
    chess.ROOK: "\u265c",
    chess.BISHOP: "\u265d",
    chess.KNIGHT: "\u265e",
    chess.PAWN: "\u265f",
}

LIGHT = QColor("#ebecd0")
DARK = QColor("#779556")
SELECTED = QColor(255, 236, 120, 170)
LEGAL = QColor(20, 20, 20, 55)
LEGAL_CAP = QColor(20, 20, 20, 80)
HINT = QColor(80, 200, 120, 120)
WRONG = QColor(230, 90, 90, 120)
GLOW = QColor(91, 140, 255, 165)
WHITE_FILL = QColor("#fbfbfb")
WHITE_LINE = QColor("#2f2f2f")
BLACK_FILL = QColor("#2a2a2a")
BLACK_LINE = QColor("#ededed")


class ChessBoard(QWidget):
    """Click a piece, then click a destination. Emits SAN."""

    moveMade = Signal(str)       # 정답 판정용: canonical SAN
    movePlayedUci = Signal(str)  # 표시용: UCI (예: e2e4e5? promotion 포함)
    squarePicked = Signal(int)   # 칸 하나 고르기 모드(칸 이름 퀴즈)
    picked = Signal(int, int)    # 칸 두 개 고르기 모드(머릿속 보드)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.flipped = False
        self._interactive = True
        self._selected: Optional[int] = None
        self._legal_targets: List[int] = []
        self._hint: Optional[Tuple[int, int]] = None
        self._wrong: Optional[Tuple[int, int]] = None
        # 노테이션 훈련용: 규칙 없이 칸만 고르는 모드, 기물 숨기기, 칸 강조.
        self._pick_mode = False
        self._hide_pieces = False
        self._picks: List[int] = []
        self._glow: Optional[int] = None
        self.setMinimumSize(340, 340)

    # -- api ---------------------------------------------------------------

    def set_position(self, fen: str, flipped: Optional[bool] = None) -> None:
        self.board = chess.Board(fen)
        # 내가 둘 차례이므로 그 진영을 아래에 둔다.
        self.flipped = (self.board.turn == chess.BLACK) if flipped is None else flipped
        self._selected = None
        self._legal_targets = []
        self._hint = None
        self._wrong = None
        self.update()

    def set_interactive(self, on: bool) -> None:
        self._interactive = on
        if not on:
            self._selected = None
            self._legal_targets = []
        self.update()

    def is_interactive(self) -> bool:
        return self._interactive

    def show_hint(self, uci: str) -> None:
        try:
            m = chess.Move.from_uci(uci)
        except ValueError:
            return
        self._hint = (m.from_square, m.to_square)
        self.update()

    def show_wrong(self, uci: str) -> None:
        try:
            m = chess.Move.from_uci(uci)
        except ValueError:
            return
        self._wrong = (m.from_square, m.to_square)
        self.update()

    def clear_marks(self) -> None:
        self._hint = None
        self._wrong = None
        self.update()

    # -- 노테이션 훈련용 api -------------------------------------------------

    def set_pick_mode(self, on: bool) -> None:
        """체스 규칙 없이 칸만 고른다. 칸 이름 퀴즈, 머릿속 보드에 쓴다."""
        self._pick_mode = on
        self._picks = []
        self._selected = None
        self._legal_targets = []
        self.update()

    def set_hide_pieces(self, on: bool) -> None:
        """기물을 숨긴다. 머릿속 보드(기보만 보고 칸 짚기)용."""
        self._hide_pieces = on
        self.update()

    def glow_square(self, sq: Optional[int]) -> None:
        """칸 하나를 파랗게 강조한다."""
        self._glow = sq
        self.update()

    def clear_picks(self) -> None:
        self._picks = []
        self.update()

    # -- geometry ----------------------------------------------------------

    def _square_size(self) -> float:
        return min(self.width(), self.height()) / 8.0

    def _origin(self) -> Tuple[float, float]:
        s = self._square_size()
        return (self.width() - s * 8) / 2.0, (self.height() - s * 8) / 2.0

    def _sq_rect(self, sq: int) -> QRectF:
        s = self._square_size()
        ox, oy = self._origin()
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        col = f if self.flipped else 7 - f
        row = r if self.flipped else 7 - r
        return QRectF(ox + col * s, oy + row * s, s, s)

    def _point_square(self, p: QPointF) -> Optional[int]:
        s = self._square_size()
        ox, oy = self._origin()
        col = int((p.x() - ox) // s)
        row = int((p.y() - oy) // s)
        if not (0 <= col <= 7 and 0 <= row <= 7):
            return None
        f = col if self.flipped else 7 - col
        r = row if self.flipped else 7 - row
        return chess.square(f, r)

    # -- paint -------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt name
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        s = self._square_size()
        ox, oy = self._origin()

        for row in range(8):
            for col in range(8):
                rect = QRectF(ox + col * s, oy + row * s, s, s)
                p.fillRect(rect, LIGHT if (row + col) % 2 == 0 else DARK)

        if self._glow is not None:
            p.fillRect(self._sq_rect(self._glow), GLOW)
        for sq in self._picks:
            p.fillRect(self._sq_rect(sq), SELECTED)

        if self._selected is not None:
            p.fillRect(self._sq_rect(self._selected), SELECTED)
        for t in self._legal_targets:
            rect = self._sq_rect(t)
            if self.board.piece_at(t) is not None:
                pen = QPen(LEGAL_CAP)
                pen.setWidthF(max(3.0, s * 0.08))
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(rect.adjusted(s * 0.05, s * 0.05, -s * 0.05, -s * 0.05))
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(LEGAL)
                p.drawEllipse(rect.center(), s * 0.14, s * 0.14)

        for mark, color in ((self._hint, HINT), (self._wrong, WRONG)):
            if mark:
                for sq in mark:
                    p.fillRect(self._sq_rect(sq), color)

        self._draw_coords(p, s, ox, oy)

        if self._hint:
            self._draw_arrow(p, self._hint[0], self._hint[1], QColor(46, 160, 90))
        if self._wrong:
            self._draw_arrow(p, self._wrong[0], self._wrong[1], QColor(200, 60, 60))

        self._draw_pieces(p, s)

    def _draw_coords(self, p: QPainter, s: float, ox: float, oy: float) -> None:
        p.setFont(QFont("Segoe UI", max(7, int(s * 0.17))))
        for col in range(8):
            f = col if self.flipped else 7 - col
            rect = QRectF(ox + col * s, oy + 7 * s, s, s)
            p.setPen(QPen(DARK if (7 + col) % 2 == 0 else LIGHT))
            p.drawText(
                rect.adjusted(0, 0, -s * 0.08, -s * 0.02),
                Qt.AlignRight | Qt.AlignBottom,
                chr(ord("a") + f),
            )
        for row in range(8):
            r = row if self.flipped else 7 - row
            rect = QRectF(ox, oy + row * s, s, s)
            p.setPen(QPen(DARK if row % 2 == 0 else LIGHT))
            p.drawText(
                rect.adjusted(s * 0.06, s * 0.02, 0, 0),
                Qt.AlignLeft | Qt.AlignTop,
                str(r + 1),
            )

    def _draw_pieces(self, p: QPainter, s: float) -> None:
        if self._hide_pieces:
            return
        # 주의: Segoe UI Symbol 같은 'symbol' 폰트는 QPainterPath.addText 로는
        # 글리프가 안 나온다(빈 path). 그래서 일반 텍스트 경로(drawText)로 그린다.
        font = QFont("Segoe UI Symbol")
        font.setPixelSize(max(10, int(s * 0.78)))
        p.setFont(font)
        w = max(1.0, s * 0.035)
        offsets = [
            (-w, 0), (w, 0), (0, -w), (0, w),
            (-w, -w), (w, w), (-w, w), (w, -w),
        ]
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece is None:
                continue
            rect = self._sq_rect(sq)
            ch = _GLYPH[piece.piece_type]
            if piece.color == chess.WHITE:
                fill, line = WHITE_FILL, WHITE_LINE
            else:
                fill, line = BLACK_FILL, BLACK_LINE
            p.setPen(QPen(line))
            for dx, dy in offsets:
                p.drawText(rect.translated(dx, dy), Qt.AlignCenter, ch)
            p.setPen(QPen(fill))
            p.drawText(rect, Qt.AlignCenter, ch)

    def _draw_arrow(self, p: QPainter, frm: int, to: int, color: QColor) -> None:
        s = self._square_size()
        p1 = self._sq_rect(frm).center()
        p2 = self._sq_rect(to).center()
        vx, vy = p2.x() - p1.x(), p2.y() - p1.y()
        length = math.hypot(vx, vy) or 1.0
        ux, uy = vx / length, vy / length

        start = QPointF(p1.x() + ux * s * 0.30, p1.y() + uy * s * 0.30)
        tip = QPointF(p2.x() - ux * s * 0.16, p2.y() - uy * s * 0.16)
        pen = QPen(color)
        pen.setWidthF(max(3.0, s * 0.11))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawLine(start, tip)

        head = s * 0.30
        wide = s * 0.22
        hx, hy = -uy, ux
        base = QPointF(tip.x() - ux * head, tip.y() - uy * head)
        poly = QPolygonF(
            [
                tip,
                QPointF(base.x() + hx * wide, base.y() + hy * wide),
                QPointF(base.x() - hx * wide, base.y() - hy * wide),
            ]
        )
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawPolygon(poly)

    # -- input -------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt name
        if not self._interactive or event.button() != Qt.LeftButton:
            return
        sq = self._point_square(event.position())
        if sq is None:
            return
        if self._pick_mode:
            self._on_pick(sq)
            return
        if self._selected is not None and sq in self._legal_targets:
            self._try_move(self._selected, sq)
            return
        piece = self.board.piece_at(sq)
        if piece is not None and piece.color == self.board.turn:
            self._selected = sq
            self._legal_targets = [
                m.to_square for m in self.board.legal_moves if m.from_square == sq
            ]
        else:
            self._selected = None
            self._legal_targets = []
        self.update()

    def _try_move(self, frm: int, to: int) -> None:
        moves = [
            m
            for m in self.board.legal_moves
            if m.from_square == frm and m.to_square == to
        ]
        if not moves:
            return
        if len(moves) > 1:  # 승격: 어떤 기물로 바꿀지 물어본다
            promo = self._ask_promotion(to)
            if promo is None:
                return
            moves = [m for m in moves if m.promotion == promo]
        if not moves:
            return
        move = moves[0]
        san = self.board.san(move)
        self._selected = None
        self._legal_targets = []
        self.update()
        self.movePlayedUci.emit(move.uci())
        self.moveMade.emit(san)

    def _on_pick(self, sq: int) -> None:
        # 칸 하나 고르기(칸 이름 퀴즈)에는 매 클릭을 알려준다.
        self.squarePicked.emit(sq)
        # 칸 두 개 고르기(머릿속 보드): 첫 칸 → 둘째 칸.
        if not self._picks:
            self._picks = [sq]
        elif sq == self._picks[0]:
            self._picks = []
        else:
            frm, to = self._picks[0], sq
            self._picks = []
            self.update()
            self.picked.emit(frm, to)
            return
        self.update()

    def _ask_promotion(self, to: int) -> Optional[int]:
        rect = self._sq_rect(to)
        menu = QMenu(self)
        options = [
            ("퀸", chess.QUEEN),
            ("룩", chess.ROOK),
            ("비숍", chess.BISHOP),
            ("나이트", chess.KNIGHT),
        ]
        chosen: List[int] = []
        for label, piece_type in options:
            act = menu.addAction(label)
            act.triggered.connect(lambda _=False, pt=piece_type: chosen.append(pt))
        menu.exec(self.mapToGlobal(rect.bottomLeft().toPoint()))
        return chosen[0] if chosen else None
