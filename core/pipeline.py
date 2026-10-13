"""Glue: Drive/local PGN -> problems, and Stockfish -> mistakes.

Kept separate from the UI so the whole pipeline can be exercised from a
plain script (handy for testing without launching Qt).
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import chess

from core import config as cfg_mod
from core import db, drive, engine as engine_mod, parser

Progress = Optional[Callable[[str], None]]


def _note(on_progress: Progress, msg: str) -> None:
    if on_progress:
        on_progress(msg)


def _user_settings(cfg: Dict[str, Any]):
    username = cfg_mod.get(cfg, "chesscom.username", "") or ""
    fallback = cfg_mod.get(cfg, "chesscom.fallback_color", "white") or "white"
    return username, fallback


def ingest_pgn_text(
    pgn_text: str,
    source: str,
    cfg: Dict[str, Any],
    file_id: Optional[str] = None,
    modified_time: Optional[str] = None,
    on_progress: Progress = None,
) -> Dict[str, int]:
    """Parse one PGN blob and store its user lines as line problems."""
    db.init_db()
    username, fallback = _user_settings(cfg)
    stats = {"games": 0, "new_games": 0, "lines": 0, "problems": 0}

    for game in parser.iter_games(pgn_text):
        stats["games"] += 1
        gid = parser.game_id(game)
        db.upsert_game(gid, source, file_id, modified_time)
        if db.is_game_processed(gid):
            continue
        stats["new_games"] += 1
        lines = parser.extract_user_lines(
            game,
            source=source,
            username=username,
            fallback_color=fallback,
            min_ply=2,
        )
        for ln in lines:
            stats["lines"] += 1
            pid = db.add_problem(
                fen=ln.fen_before,
                context_sans=ln.context_sans,
                target_san=ln.san,
                source_game_id=gid,
                source=source,
                ply=ln.ply,
                origin="line",
            )
            if pid:
                stats["problems"] += 1
        db.mark_game_processed(gid)
    return stats


def import_local_file(
    path: str,
    source: str,
    cfg: Dict[str, Any],
    on_progress: Progress = None,
) -> Dict[str, int]:
    _note(on_progress, f"읽는 중: {os.path.basename(path)}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    # 로컬 파일은 파일 경로 자체를 식별자로 쓴다.
    return ingest_pgn_text(
        text,
        source,
        cfg,
        file_id="local:" + os.path.abspath(path),
        modified_time=str(int(os.path.getmtime(path))),
        on_progress=on_progress,
    )


def sync_drive(cfg: Dict[str, Any], on_progress: Progress = None) -> Dict[str, int]:
    """Read the configured parent folder and ingest every .pgn found."""
    db.init_db()
    parent = cfg_mod.get(cfg, "google_drive.parent_folder_id", "")
    if not parent:
        raise ValueError("설정에서 구글드라이브 부모 폴더를 먼저 지정하세요.")
    service = drive.build_service()
    parent_id = drive.resolve_folder_id(service, parent)

    _note(on_progress, "드라이브에서 .pgn 찾는 중...")
    files = drive.list_pgn_files(service, parent_id)
    _note(on_progress, f"{len(files)}개 PGN 발견")

    total = {"files": len(files), "games": 0, "new_games": 0, "lines": 0, "problems": 0}
    for i, f in enumerate(files, 1):
        source = f.source or "human"
        if f.source is None:
            _note(on_progress, f"[분류불명→human] {'/'.join(f.path_parts)}/{f.name}")
        _note(on_progress, f"({i}/{len(files)}) {f.name} [{source}]")
        text = drive.read_text(service, f.file_id)
        s = ingest_pgn_text(
            text,
            source,
            cfg,
            file_id=f.file_id,
            modified_time=f.modified_time,
        )
        for k in ("games", "new_games", "lines", "problems"):
            total[k] += s[k]
    _note(on_progress, f"완료: 새 게임 {total['new_games']} / 문제 {total['problems']}")
    return total


def analyze_mistakes(
    cfg: Dict[str, Any],
    source: str = "human",
    on_progress: Progress = None,
) -> Dict[str, int]:
    """Run Stockfish over not-yet-analyzed games to collect my mistakes."""
    db.init_db()
    sf_path = cfg_mod.get(cfg, "stockfish.path", "")
    depth = int(cfg_mod.get(cfg, "stockfish.depth", 12) or 12)
    threshold = float(cfg_mod.get(cfg, "mistakes.loss_threshold", 0.80) or 0.80)

    if not engine_mod.engine_available(sf_path):
        raise ValueError("설정에서 stockfish.exe 경로를 지정하세요.")

    username, fallback = _user_settings(cfg)
    pending = db.games_needing_analysis(source)
    if not pending:
        _note(on_progress, f"분석할 {source} 게임이 없습니다.")
        return {"games": 0, "mistakes": 0, "problems": 0}

    # 같은 파일을 두 번 내려받지 않도록 file_id 로 묶는다.
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for g in pending:
        by_file.setdefault(g["file_id"], []).append(g)

    stats = {"games": 0, "mistakes": 0, "problems": 0}
    service = None
    if any(not fid.startswith("local:") for fid in by_file):
        service = drive.build_service()
    with engine_mod.Stockfish(sf_path, depth) as sf:
        for file_id, games in by_file.items():
            if file_id.startswith("local:"):
                with open(file_id[len("local:") :], "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            else:
                text = drive.read_text(service, file_id)

            wanted = {g["game_id"] for g in games}
            for game in parser.iter_games(text):
                gid = parser.game_id(game)
                if gid not in wanted:
                    continue
                gsource = next(g["source"] for g in games if g["game_id"] == gid)
                lines = parser.extract_user_lines(
                    game, source=gsource, username=username, fallback_color=fallback
                )
                stats["games"] += 1
                _note(on_progress, f"분석 중: {game.headers.get('White','?')} vs {game.headers.get('Black','?')}")
                for ln in lines:
                    board = chess.Board(ln.fen_before)
                    try:
                        move = board.parse_san(ln.san)
                    except ValueError:
                        continue
                    res = engine_mod.find_mistake(
                        sf_path,
                        ln.fen_before,
                        move.uci(),
                        threshold=threshold,
                        depth=depth,
                        engine=sf,
                    )
                    if res is None:
                        continue
                    mid = db.add_mistake(
                        fen=ln.fen_before,
                        context_sans=ln.context_sans,
                        my_san=res.my_san,
                        best_san=res.best_san,
                        eval_before=res.eval_before,
                        eval_after=res.eval_after,
                        loss=res.loss,
                        source_game_id=gid,
                        source=gsource,
                        ply=ln.ply,
                    )
                    stats["mistakes"] += 0 if mid == 0 else 1
                    if mid and res.best_san:
                        pid = db.add_problem(
                            fen=ln.fen_before,
                            context_sans=ln.context_sans,
                            target_san=res.best_san,
                            source_game_id=gid,
                            source=gsource,
                            ply=ln.ply,
                            origin="mistake",
                            mistake_id=mid,
                        )
                        if pid:
                            stats["problems"] += 1
                db.mark_game_analyzed(gid)
    _note(on_progress, f"완료: 실수 {stats['mistakes']} / 복습문제 {stats['problems']}")
    return stats
