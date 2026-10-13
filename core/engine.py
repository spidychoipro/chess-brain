"""Optional Stockfish bridge.

The engine is only ever used to *find my mistakes* in human games. The
notation training sub-feature never depends on it, so a missing or wrong
path simply disables the mistakes tab instead of breaking the app.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import chess
import chess.engine


def engine_available(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def _to_pawns(pov) -> float:
    """Convert a PovScore to pawns from White's point of view."""
    score = pov.white()
    if score.is_mate():
        m = score.mate()
        return 100.0 if (m or 0) > 0 else -100.0
    return float(score.score(mate_score=10000) or 0) / 100.0


@dataclass
class MistakeResult:
    eval_before: float
    eval_after: float
    loss: float
    best_san: str
    my_san: str


class Stockfish:
    """Thin wrapper so callers don't juggle process lifecycles."""

    def __init__(self, path: str, depth: int = 12):
        if not engine_available(path):
            raise FileNotFoundError(f"stockfish not found: {path}")
        self.path = path
        self.depth = depth
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "Stockfish":
        self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            finally:
                self._engine = None

    def best_move(self, board: chess.Board) -> Dict[str, Any]:
        assert self._engine is not None
        info = self._engine.analyse(board, chess.engine.Limit(depth=self.depth))
        pv = info.get("pv") or []
        best = pv[0] if pv else None
        return {
            "info": info,
            "best": best,
            "best_san": board.san(best) if best else "",
            "pawns_white": _to_pawns(info["score"]),
        }

    def evaluate(self, board: chess.Board) -> float:
        info = self._engine.analyse(board, chess.engine.Limit(depth=self.depth))  # type: ignore[union-attr]
        return _to_pawns(info["score"])


def find_mistake(
    path: str,
    fen_before: str,
    played_uci: str,
    threshold: float = 0.80,
    depth: int = 12,
    engine: Optional[Stockfish] = None,
) -> Optional[MistakeResult]:
    """Return a MistakeResult when my move lost >= threshold pawns."""
    board = chess.Board(fen_before)
    try:
        move = chess.Move.from_uci(played_uci)
    except ValueError:
        return None
    if move not in board.legal_moves:
        return None

    owns_engine = engine is None
    if owns_engine:
        engine = Stockfish(path, depth)
        engine.__enter__()

    try:
        before = engine.best_move(board)
        sign = 1.0 if board.turn == chess.WHITE else -1.0
        score_before = before["pawns_white"] * sign

        after_board = board.copy()
        after_board.push(move)
        score_after = engine.evaluate(after_board) * sign

        my_san = board.san(move)
        loss = score_before - score_after

        if loss >= threshold:
            return MistakeResult(
                eval_before=round(score_before, 3),
                eval_after=round(score_after, 3),
                loss=round(loss, 3),
                best_san=before["best_san"],
                my_san=my_san,
            )
        return None
    finally:
        if owns_engine and engine is not None:
            engine.__exit__(None, None, None)
