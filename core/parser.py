"""PGN parsing.

Only the mainline matters here. From each game we pull the moves *I* played
and turn every one of them into a candidate training problem:

    show me the line so far, I type the next move

Because bot games and human games live in different Drive subfolders, every
line carries a ``source`` of ``bot`` or ``human``.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Iterator, List, Optional

import chess
import chess.pgn


@dataclass
class UserLine:
    ply: int              # 1-based ply of my move
    fen_before: str       # position right before my move
    san: str              # the move I actually played
    context_sans: str     # readable line leading up to my move
    source: str           # 'bot' | 'human'
    source_game_id: str


def game_id(game: chess.pgn.Game) -> str:
    """Stable id so re-scans don't duplicate games."""
    h = game.headers
    link = h.get("Link", "") or h.get("Site", "")
    key = "|".join(
        [
            link,
            h.get("Date", ""),
            h.get("Round", ""),
            h.get("White", ""),
            h.get("Black", ""),
            h.get("Result", ""),
        ]
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def user_color(
    game: chess.pgn.Game,
    username: str = "",
    fallback: str = "white",
) -> chess.Color:
    """Figure out which side I was playing."""
    if username:
        name = username.strip().lower()
        white = (game.headers.get("White") or "").strip().lower()
        black = (game.headers.get("Black") or "").strip().lower()
        if name and name in white:
            return chess.WHITE
        if name and name in black:
            return chess.BLACK
    return chess.WHITE if fallback.lower().startswith("w") else chess.BLACK


def san_line(sans: List[str], start_ply: int = 1) -> str:
    """Render a list of SAN tokens as ``1. e4 e5 2. Nf3`` style text."""
    parts: List[str] = []
    ply = start_ply
    for san in sans:
        if ply % 2 == 1:
            parts.append(f"{(ply + 1) // 2}. {san}")
        else:
            if ply == start_ply:
                parts.append(f"{ply // 2}... {san}")
            else:
                parts.append(san)
        ply += 1
    return " ".join(parts)


def iter_games(pgn_text: str) -> Iterator[chess.pgn.Game]:
    stream = io.StringIO(pgn_text)
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            return
        yield game


def extract_user_lines(
    game: chess.pgn.Game,
    source: str,
    username: str = "",
    fallback_color: str = "white",
    max_context_ply: int = 12,
    min_ply: int = 1,
) -> List[UserLine]:
    """Every move I made, with the readable line leading up to it."""
    colour = user_color(game, username, fallback_color)
    gid = game_id(game)

    board = game.board()
    sans: List[str] = []
    out: List[UserLine] = []
    ply = 0

    for move in game.mainline_moves():
        ply += 1
        fen_before = board.fen()
        i_am_to_move = board.turn == colour
        san = board.san(move)
        sans.append(san)

        if i_am_to_move and ply >= min_ply:
            start = max(1, ply - max_context_ply)
            context = san_line(sans[start - 1 : ply - 1], start_ply=start)
            out.append(
                UserLine(
                    ply=ply,
                    fen_before=fen_before,
                    san=san,
                    context_sans=context,
                    source=source,
                    source_game_id=gid,
                )
            )

        board.push(move)

    return out


def parse_pgn(
    pgn_text: str,
    source: str,
    username: str = "",
    fallback_color: str = "white",
    sync_game_ids: bool = True,
    on_game=None,
) -> List[UserLine]:
    """Parse a whole PGN file into user lines.

    ``on_game(game)`` is called for each game so callers can record it in the
    games table for dedupe.
    """
    lines: List[UserLine] = []
    for game in iter_games(pgn_text):
        if not game.headers.get("Result"):
            game.headers["Result"] = "*"
        if on_game is not None:
            on_game(game)
        lines.extend(
            extract_user_lines(
                game,
                source=source,
                username=username,
                fallback_color=fallback_color,
            )
        )
    return lines
