"""SQLite layer.

Two ideas drive the schema:

* ``mistakes`` is the main data. A mistake is a position where I lost real
  evaluation. Reviewing mistakes is the point of the whole app.
* ``problems`` is the sub feature. A problem is "show this line, type the
  next move". Problems derived from a mistake (``origin='mistake'``) get
  pushed harder than plain line problems.

Both tables carry their own SM-2 lite fields so spacing never mixes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import sr as sr_mod
from core.sr import SRState
from core.utils import data_dir, ensure_dirs, now_ts

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    source TEXT NOT NULL CHECK(source IN ('bot','human')),
    file_id TEXT,
    modified_time TEXT,
    processed INTEGER DEFAULT 0,
    analyzed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fen TEXT NOT NULL,
    context_sans TEXT,
    my_san TEXT,
    best_san TEXT,
    reply_san TEXT DEFAULT '',
    eval_before REAL,
    eval_after REAL,
    loss REAL,
    source_game_id TEXT,
    source TEXT NOT NULL CHECK(source IN ('bot','human')),
    ply INTEGER,
    reviewed INTEGER DEFAULT 0,
    correct INTEGER DEFAULT 0,
    wrong INTEGER DEFAULT 0,
    last_seen INTEGER DEFAULT 0,
    last_wrong INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    weight REAL DEFAULT 1.0,
    analyzed INTEGER DEFAULT 0,
    ease REAL DEFAULT 2.5,
    interval REAL DEFAULT 0.0,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0,
    due_at INTEGER DEFAULT 0,
    reviewed_at INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS problems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fen TEXT NOT NULL,
    context_sans TEXT,
    target_san TEXT NOT NULL,
    source_game_id TEXT,
    source TEXT NOT NULL CHECK(source IN ('bot','human')),
    ply INTEGER,
    origin TEXT NOT NULL CHECK(origin IN ('mistake','line')),
    mistake_id INTEGER,
    correct INTEGER DEFAULT 0,
    wrong INTEGER DEFAULT 0,
    last_seen INTEGER DEFAULT 0,
    last_wrong INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    weight REAL DEFAULT 1.0,
    enabled INTEGER DEFAULT 1,
    ease REAL DEFAULT 2.5,
    interval REAL DEFAULT 0.0,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0,
    due_at INTEGER DEFAULT 0,
    reviewed_at INTEGER DEFAULT 0,
    FOREIGN KEY(mistake_id) REFERENCES mistakes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_games_source ON games(source);
CREATE INDEX IF NOT EXISTS idx_games_processed ON games(processed);
CREATE INDEX IF NOT EXISTS idx_games_analyzed ON games(analyzed);
CREATE INDEX IF NOT EXISTS idx_mistakes_source ON mistakes(source);
CREATE INDEX IF NOT EXISTS idx_mistakes_due_at ON mistakes(due_at);
CREATE INDEX IF NOT EXISTS idx_mistakes_analyzed ON mistakes(analyzed);
CREATE INDEX IF NOT EXISTS idx_problems_source ON problems(source);
CREATE INDEX IF NOT EXISTS idx_problems_origin ON problems(origin);
CREATE INDEX IF NOT EXISTS idx_problems_due_at ON problems(due_at);
CREATE INDEX IF NOT EXISTS idx_problems_enabled ON problems(enabled);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mistakes_sig
    ON mistakes(fen, COALESCE(source_game_id,''), COALESCE(my_san,''), COALESCE(ply,0));
CREATE UNIQUE INDEX IF NOT EXISTS uq_problems_sig
    ON problems(fen, target_san, source);
"""


def db_path() -> Path:
    ensure_dirs()
    return data_dir() / "app.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """이미 만들어진 DB 에 새 컬럼을 붙인다(재분석 없이 쓰게)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(mistakes)").fetchall()}
    if "reply_san" not in cols:
        conn.execute("ALTER TABLE mistakes ADD COLUMN reply_san TEXT DEFAULT ''")


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def row_to_sr(row: Dict[str, Any]) -> SRState:
    return SRState(
        ease=row.get("ease") or 2.5,
        interval=row.get("interval") or 0.0,
        reps=row.get("reps") or 0,
        lapses=row.get("lapses") or 0,
        due_at=row.get("due_at") or 0,
        reviewed_at=row.get("reviewed_at") or 0,
        streak=row.get("streak") or 0,
        correct=row.get("correct") or 0,
        wrong=row.get("wrong") or 0,
        last_wrong=row.get("last_wrong") or 0,
    )


def _clamp_weight(v: float) -> float:
    if v < 0.10:
        return 0.10
    if v > 5.0:
        return 5.0
    return round(v, 3)


def mistake_weight(state: SRState) -> float:
    """약점 가중치. 틀린 횟수가 지배적이고, 최근/미복습이면 보정."""
    now = now_ts()
    base = (state.wrong or 0) * 2.0 - (state.correct or 0) * 0.8
    lw = state.last_wrong or 0
    if lw:
        age = now - lw
        if age < 86400:
            base += 1.2
        elif age < 3 * 86400:
            base += 0.8
        elif age < 7 * 86400:
            base += 0.4
    if state.reviewed_at:
        age = now - state.reviewed_at
        if age >= 14 * 86400:
            base += 1.0
        elif age >= 7 * 86400:
            base += 0.6
    streak = state.streak or 0
    if streak >= 6:
        base -= 0.8
    elif streak >= 3:
        base -= 0.5 * (streak / 3.0)
    return _clamp_weight(max(0.15, base))


def problem_weight(state: SRState, origin: str) -> float:
    """서브 기능 문제 가중치. 실수에서 파생된 문제에 보너스."""
    now = now_ts()
    base = (state.wrong or 0) * 2.0 - (state.correct or 0) * 0.8
    if origin == "mistake":
        base += 0.8
    lw = state.last_wrong or 0
    if lw:
        age = now - lw
        if age < 86400:
            base += 1.0
        elif age < 3 * 86400:
            base += 0.6
    if state.reviewed_at:
        age = now - state.reviewed_at
        if age >= 14 * 86400:
            base += 0.8
        elif age >= 7 * 86400:
            base += 0.5
    streak = state.streak or 0
    if streak >= 5:
        base -= 0.6
    elif streak >= 3:
        base -= 0.4 * (streak / 3.0)
    return _clamp_weight(max(0.10, base))


# --------------------------------------------------------------------------
# games
# --------------------------------------------------------------------------

def upsert_game(
    game_id: str,
    source: str,
    file_id: Optional[str] = None,
    modified_time: Optional[str] = None,
) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO games (game_id, source, file_id, modified_time, processed)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(game_id) DO UPDATE SET
                source=excluded.source,
                file_id=COALESCE(excluded.file_id, games.file_id),
                modified_time=COALESCE(excluded.modified_time, games.modified_time)
            """,
            (game_id, source, file_id, modified_time),
        )
        conn.commit()
    finally:
        conn.close()


def is_game_processed(game_id: str) -> bool:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT processed FROM games WHERE game_id=?", (game_id,)
        ).fetchone()
        return bool(row and row["processed"])
    finally:
        conn.close()


def mark_game_processed(game_id: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE games SET processed=1 WHERE game_id=?", (game_id,))
        conn.commit()
    finally:
        conn.close()


def is_game_analyzed(game_id: str) -> bool:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT analyzed FROM games WHERE game_id=?", (game_id,)
        ).fetchone()
        return bool(row and row["analyzed"])
    finally:
        conn.close()


def mark_game_analyzed(game_id: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE games SET analyzed=1 WHERE game_id=?", (game_id,))
        conn.commit()
    finally:
        conn.close()


def games_needing_analysis(source: Optional[str] = None) -> List[Dict[str, Any]]:
    where = "WHERE analyzed=0 AND file_id IS NOT NULL AND file_id != ''"
    params: List[Any] = []
    if source in ("bot", "human"):
        where += " AND source=?"
        params.append(source)
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT game_id, source, file_id FROM games {where} ORDER BY source",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def game_counts(source: Optional[str] = None) -> Dict[str, int]:
    """게임 수 요약. 분석 버튼이 '게임이 없어서 0'인지 '다 분석해서 0'인지
    구분해서 말할 수 있게 하려고 둔다."""
    where = ""
    params: List[Any] = []
    if source in ("bot", "human"):
        where = "WHERE source=?"
        params.append(source)
    and_ = "AND" if where else "WHERE"
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) c FROM games {where}", params
        ).fetchone()["c"]
        analyzed = conn.execute(
            f"SELECT COUNT(*) c FROM games {where} {and_} analyzed=1", params
        ).fetchone()["c"]
        pending = conn.execute(
            f"SELECT COUNT(*) c FROM games {where} {and_} analyzed=0 "
            f"AND file_id IS NOT NULL AND file_id != ''",
            params,
        ).fetchone()["c"]
        return {"total": total, "analyzed": analyzed, "pending": pending}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# mistakes
# --------------------------------------------------------------------------

def add_mistake(
    *,
    fen: str,
    context_sans: str,
    my_san: str,
    best_san: str,
    eval_before: float,
    eval_after: float,
    loss: float,
    source_game_id: str,
    source: str,
    ply: int,
    reply_san: str = "",
) -> int:
    """Insert a mistake, or return the id of the existing identical one."""
    # 최선수를 그대로 둔 수는 실수가 아니다(가짜 실수 방지).
    if my_san and my_san == best_san:
        return 0
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO mistakes (
                fen, context_sans, my_san, best_san, reply_san, eval_before,
                eval_after, loss, source_game_id, source, ply,
                ease, interval, reps, lapses, due_at, reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 2.5, 0.0, 0, 0, 0, 0)
            """,
            (
                fen,
                (context_sans or "")[:800],
                my_san or "",
                best_san or "",
                reply_san or "",
                float(eval_before),
                float(eval_after),
                float(loss),
                source_game_id or "",
                source,
                int(ply),
            ),
        )
        mid = cur.lastrowid
        if not mid or cur.rowcount == 0:
            row = conn.execute(
                """
                SELECT id FROM mistakes
                WHERE fen=? AND COALESCE(source_game_id,'')=?
                  AND COALESCE(my_san,'')=? AND COALESCE(ply,0)=?
                """,
                (fen, source_game_id or "", my_san or "", int(ply)),
            ).fetchone()
            mid = row["id"] if row else 0
        conn.commit()
        return int(mid)
    finally:
        conn.close()


def get_mistake(mistake_id: int) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM mistakes WHERE id=?", (mistake_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_mistake_sr(mistake_id: int, state: SRState) -> None:
    conn = connect()
    try:
        conn.execute(
            """
            UPDATE mistakes SET
                ease=?, interval=?, reps=?, lapses=?, due_at=?, reviewed_at=?,
                correct=?, wrong=?, last_seen=?, last_wrong=?, streak=?,
                weight=?, reviewed=1
            WHERE id=?
            """,
            (
                round(state.ease, 3),
                round(state.interval, 3),
                state.reps,
                state.lapses,
                state.due_at,
                state.reviewed_at,
                state.correct,
                state.wrong,
                state.reviewed_at,
                state.last_wrong,
                state.streak,
                mistake_weight(state),
                mistake_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def mistakes_due(
    limit: int = 100,
    source: Optional[str] = None,
    only_wrong: bool = False,
) -> List[Dict[str, Any]]:
    now = now_ts()
    where = []
    params: List[Any] = []
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    if only_wrong:
        where.append("wrong >= 1")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT * FROM mistakes
        {clause}
        ORDER BY
            CASE WHEN due_at>0 AND due_at<=? THEN 0
                 WHEN reps=0 AND wrong>=1 THEN 1
                 ELSE 2 END,
            last_wrong DESC,
            loss DESC,
            weight DESC
        LIMIT ?
    """
    conn = connect()
    try:
        rows = conn.execute(sql, (*params, now, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def list_mistakes(
    limit: int = 500,
    source: Optional[str] = None,
    only_wrong: bool = False,
) -> List[Dict[str, Any]]:
    where = []
    params: List[Any] = []
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    if only_wrong:
        where.append("wrong >= 1")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    conn = connect()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM mistakes {clause}
            ORDER BY loss DESC, last_wrong DESC, id DESC
            LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mistakes_missing_reply(limit: int = 500) -> List[Dict[str, Any]]:
    """상대 응수가 아직 없는 실수(옛 데이터)를 모은다."""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id, fen, my_san FROM mistakes "
            "WHERE COALESCE(reply_san,'')='' LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def set_mistake_reply(mistake_id: int, reply_san: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE mistakes SET reply_san=? WHERE id=?",
            (reply_san or "", mistake_id),
        )
        conn.commit()
    finally:
        conn.close()


def mistake_counts(source: Optional[str] = None) -> Dict[str, int]:
    now = now_ts()
    where = ""
    params: List[Any] = []
    if source in ("bot", "human"):
        where = "WHERE source=?"
        params.append(source)
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) c FROM mistakes {where}", params
        ).fetchone()["c"]
        due = conn.execute(
            f"SELECT COUNT(*) c FROM mistakes {where} "
            f"{'AND' if where else 'WHERE'} due_at>0 AND due_at<=?",
            (*params, now),
        ).fetchone()["c"]
        unreviewed = conn.execute(
            f"SELECT COUNT(*) c FROM mistakes {where} "
            f"{'AND' if where else 'WHERE'} (analyzed=0 OR reps=0)",
            params,
        ).fetchone()["c"]
        return {"total": total, "due": due, "unreviewed": unreviewed}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# problems
# --------------------------------------------------------------------------

def add_problem(
    *,
    fen: str,
    context_sans: str,
    target_san: str,
    source_game_id: str,
    source: str,
    ply: int,
    origin: str,
    mistake_id: Optional[int] = None,
) -> int:
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO problems (
                fen, context_sans, target_san, source_game_id, source, ply,
                origin, mistake_id,
                ease, interval, reps, lapses, due_at, reviewed_at, weight, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 2.5, 0.0, 0, 0, 0, 0, 1.0, 1)
            """,
            (
                fen,
                (context_sans or "")[:800],
                target_san,
                source_game_id or "",
                source,
                int(ply),
                origin,
                mistake_id,
            ),
        )
        pid = cur.lastrowid
        if not pid or cur.rowcount == 0:
            row = conn.execute(
                "SELECT id FROM problems WHERE fen=? AND target_san=? AND source=?",
                (fen, target_san, source),
            ).fetchone()
            pid = row["id"] if row else 0
        conn.commit()
        return int(pid)
    finally:
        conn.close()


def get_problem(problem_id: int) -> Optional[Dict[str, Any]]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def update_problem_sr(problem_id: int, state: SRState) -> None:
    origin = "line"
    conn = connect()
    try:
        row = conn.execute(
            "SELECT origin FROM problems WHERE id=?", (problem_id,)
        ).fetchone()
        if row:
            origin = row["origin"]
        conn.execute(
            """
            UPDATE problems SET
                ease=?, interval=?, reps=?, lapses=?, due_at=?, reviewed_at=?,
                correct=?, wrong=?, last_seen=?, last_wrong=?, streak=?, weight=?
            WHERE id=?
            """,
            (
                round(state.ease, 3),
                round(state.interval, 3),
                state.reps,
                state.lapses,
                state.due_at,
                state.reviewed_at,
                state.correct,
                state.wrong,
                state.reviewed_at,
                state.last_wrong,
                state.streak,
                problem_weight(state, origin),
                problem_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def problems_due(
    limit: int = 100,
    source: Optional[str] = None,
    only_wrong: bool = False,
    soft: bool = False,
) -> List[Dict[str, Any]]:
    """`soft=True` keeps next-move recall flowing (due + origin only)."""
    now = now_ts()
    where = ["enabled=1"]
    params: List[Any] = []
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    if only_wrong:
        where.append("wrong >= 1")
    clause = "WHERE " + " AND ".join(where)
    if soft:
        order = """
            CASE WHEN due_at>0 AND due_at<=? THEN 0 ELSE 1 END,
            CASE WHEN origin='mistake' THEN 0 ELSE 1 END,
            last_wrong DESC,
            weight DESC
        """
    else:
        order = """
            CASE WHEN due_at>0 AND due_at<=? THEN 0 ELSE 1 END,
            CASE WHEN origin='mistake' AND wrong>=1 THEN 0 ELSE 1 END,
            lapses DESC,
            weight DESC,
            last_wrong DESC
        """
    conn = connect()
    try:
        rows = conn.execute(
            f"SELECT * FROM problems {clause} ORDER BY {order} LIMIT ?",
            (*params, now, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def problem_counts(source: Optional[str] = None) -> Dict[str, int]:
    now = now_ts()
    where = ["enabled=1"]
    params: List[Any] = []
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    clause = "WHERE " + " AND ".join(where)
    conn = connect()
    try:
        total = conn.execute(f"SELECT COUNT(*) c FROM problems {clause}", params).fetchone()["c"]
        due = conn.execute(
            f"SELECT COUNT(*) c FROM problems {clause} AND due_at>0 AND due_at<=?",
            (*params, now),
        ).fetchone()["c"]
        return {"total": total, "due": due}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------

def today_review_counts() -> Dict[str, int]:
    from core.utils import day_start_ts

    start = day_start_ts(0)
    conn = connect()
    try:
        m = conn.execute(
            "SELECT COUNT(*) c FROM mistakes WHERE reviewed_at>=?", (start,)
        ).fetchone()["c"]
        p = conn.execute(
            "SELECT COUNT(*) c FROM problems WHERE reviewed_at>=?", (start,)
        ).fetchone()["c"]
        return {"mistakes": m, "problems": p, "total": m + p}
    finally:
        conn.close()


def hardest_mistakes(limit: int = 5, source: Optional[str] = None) -> List[Dict[str, Any]]:
    where = "WHERE wrong>=1"
    params: List[Any] = []
    if source in ("bot", "human"):
        where += " AND source=?"
        params.append(source)
    conn = connect()
    try:
        rows = conn.execute(
            f"""
            SELECT * FROM mistakes {where}
            ORDER BY wrong DESC, loss DESC LIMIT ?
            """,
            (*params, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def source_accuracy(source: Optional[str] = None) -> Dict[str, Any]:
    where = ""
    params: List[Any] = []
    if source in ("bot", "human"):
        where = "WHERE source=?"
        params.append(source)
    conn = connect()
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM(correct),0) c, COALESCE(SUM(wrong),0) w FROM mistakes {where}",
            params,
        ).fetchone()
        correct, wrong = row["c"], row["w"]
        total = correct + wrong
        acc = (correct / total * 100.0) if total else 0.0
        return {"correct": correct, "wrong": wrong, "accuracy": round(acc, 1)}
    finally:
        conn.close()
