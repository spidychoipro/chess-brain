"""훈련 커리큘럼: 실수에 테마를 붙이고, 왜 틀렸는지 설명하고, 다음 문제를 고른다.

엔진이 준 원자료(최선수·PV·평가)를 코칭 자료로 가공하는 단계다. 여기서 만든
``theme`` 과 ``explanation`` 은 실수 테이블에 저장되고, 커리큘럼 탭과 복습
다이얼로그가 그대로 쓴다.

분석은 순수 보드 연산만 쓴다. 엔진을 다시 돌리지 않아서 옛 실수 4천 개도
몇 초 안에 테마가 붙는다.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import chess

from core import db
from core.utils import now_ts

# 테마 키 → 화면에 보여줄 말. 순서는 약한 테마부터 정렬할 때도 쓴다.
THEMES: Dict[str, str] = {
    "missed_mate": "메이트 놓침",
    "allowed_mate": "메이트 당함",
    "back_rank": "백 랭크",
    "hanging": "기물 걸림",
    "missed_capture": "잡을 수 놓침",
    "fork": "포크·더블어택",
    "pin": "핀·묶임",
    "tactic": "전술 미스",
    "opening": "오프닝 판단",
    "endgame": "엔드게임",
    "positional": "위치 판단",
}

PIECE_KO = {
    chess.PAWN: "폰",
    chess.KNIGHT: "나이트",
    chess.BISHOP: "비숍",
    chess.ROOK: "룩",
    chess.QUEEN: "퀸",
    chess.KING: "킹",
}

PIECE_VALUE = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# 이미 이만큼 지고 있으면 "어떻게 두나 똑같다"는 수를 실수로 부르지 않는다.
LOST_POSITION_EVAL = -4.0


def _lines(item: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    def parse(raw: Any) -> List[str]:
        if isinstance(raw, list):
            return [str(x) for x in raw]
        try:
            value = json.loads(raw or "[]")
            return [str(x) for x in value] if isinstance(value, list) else []
        except (ValueError, TypeError):
            return []

    return parse(item.get("best_line")), parse(item.get("reply_line"))


def _move(board: chess.Board, uci: str) -> Optional[chess.Board]:
    if not uci:
        return None
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return None
    if move not in board.legal_moves:
        return None
    nxt = board.copy()
    nxt.push(move)
    return nxt


def is_lost_position(item: Dict[str, Any]) -> bool:
    """이미 기물/평가에서 밀려서 카드로 만들 의미가 없는 국면인지."""
    before = item.get("eval_before")
    mate_before = item.get("mate_before")
    if mate_before is not None and mate_before < 0:
        return True
    if before is None:
        return False
    try:
        return float(before) <= LOST_POSITION_EVAL
    except (TypeError, ValueError):
        return False


def classify(item: Dict[str, Any]) -> str:
    """실수 하나에 테마를 붙인다. 보드facts + 엔진 PV만 쓴다."""
    try:
        board = chess.Board(item["fen"])
    except Exception:
        return "tactic"
    best, reply = _lines(item)
    ply = int(item.get("ply") or 0)
    loss = float(item.get("loss") or 0)
    best_san = item.get("best_san") or ""
    reply_san = item.get("reply_san") or ""
    mate_before = item.get("mate_before")
    mate_after = item.get("mate_after")

    # 메이트는 다른 모든 분류보다 우선한다. 놓친 메이트와 당한 메이트를 구분한다.
    if (mate_after is not None and mate_after < 0) or "#" in reply_san:
        return "allowed_mate"
    if (mate_before is not None and mate_before > 0) or "#" in best_san:
        return "missed_mate"

    my_uci = reply[0] if reply else ""
    after = _move(board, my_uci)
    my_side = board.turn

    # 백 랭크: 내 왕이 1/8랭크에 있고 앞을 폰이 막지 않는데 상대가 룩/퀸을 가짐.
    if after is not None:
        ksq = after.king(my_side)
        if ksq is not None and chess.square_rank(ksq) in (0, 7):
            rank = chess.square_rank(ksq)
            enemy = not my_side
            heavy = bool(after.pieces(chess.ROOK, enemy) or after.pieces(chess.QUEEN, enemy))
            f = chess.square_file(ksq)
            step = 1 if rank == 0 else -1
            shield = False
            for ff in (f - 1, f, f + 1):
                if 0 <= ff < 8:
                    piece = after.piece_at(chess.square(ff, rank + step))
                    if piece and piece.color == my_side and piece.piece_type == chess.PAWN:
                        shield = True
            if heavy and not shield:
                return "back_rank"

    # 상대 응수가 내 기물을 잡았으면 '걸림'이다.
    if after is not None and len(reply) >= 2 and _legal(board, my_uci, reply[1]):
        reply_move = chess.Move.from_uci(reply[1])
        if after.is_capture(reply_move):
            victim = after.piece_at(reply_move.to_square)
            if victim and victim.piece_type != chess.PAWN:
                return "hanging"

    after_reply = _move(after, reply[1]) if after is not None and len(reply) >= 2 else None
    if after_reply is not None:
        mover = after_reply.piece_at(chess.Move.from_uci(reply[1]).to_square)
        if mover:
            attacked = [
                after_reply.piece_at(sq)
                for sq in after_reply.attacks(chess.Move.from_uci(reply[1]).to_square)
            ]
            valuable = [
                p for p in attacked
                if p and p.color == my_side and p.piece_type != chess.KING
                and PIECE_VALUE[p.piece_type] >= 3
            ]
            if len(valuable) >= 2:
                return "fork"
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            if any(after_reply.is_pinned(my_side, sq) for sq in after_reply.pieces(piece_type, my_side)):
                return "pin"

    # 내가 상대 기물을 잡을 수 있었는데 안 잡았다.
    if best:
        best_board = _move(board, best[0])
        if best_board is not None and board.is_capture(chess.Move.from_uci(best[0])):
            victim = board.piece_at(chess.Move.from_uci(best[0]).to_square)
            if victim and victim.piece_type != chess.PAWN:
                return "missed_capture"

    material = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        material += PIECE_VALUE[piece_type] * (
            len(board.pieces(piece_type, chess.WHITE)) + len(board.pieces(piece_type, chess.BLACK))
        )
    if material <= 13:
        return "endgame"
    if ply <= 20:
        return "opening"
    return "tactic" if loss >= 2.0 else "positional"


def _legal(board: chess.Board, my_uci: str, reply_uci: str) -> bool:
    try:
        move = chess.Move.from_uci(my_uci)
        if move not in board.legal_moves:
            return False
        nxt = board.copy()
        nxt.push(move)
        return chess.Move.from_uci(reply_uci) in nxt.legal_moves
    except ValueError:
        return False


def _captured_piece(item: Dict[str, Any]) -> str:
    try:
        board = chess.Board(item["fen"])
        _, reply = _lines(item)
        if len(reply) < 2:
            return ""
        after = _move(board, reply[0])
        if after is None:
            return ""
        move = chess.Move.from_uci(reply[1])
        if move not in after.legal_moves or not after.is_capture(move):
            return ""
        piece = after.piece_at(move.to_square)
        return PIECE_KO.get(piece.piece_type, "기물") if piece else ""
    except Exception:
        return ""


def explain(item: Dict[str, Any], theme: Optional[str] = None) -> str:
    """사람이 읽고 바로 이해할 수 있는 한두 문장 해설을 만든다."""
    theme = theme or item.get("theme") or classify(item)
    my = item.get("my_san") or "둔 수"
    best = item.get("best_san") or "추천 수"
    reply = item.get("reply_san") or ""

    if theme == "allowed_mate":
        return f"{my}을 두면 상대가 {reply or '메이트 수'}로 메이트가 납니다. {best}가 필요했습니다."
    if theme == "missed_mate":
        return f"{best}로 메이트를 만들 수 있었는데 놓쳤습니다. {my}은 결정력을 놓친 수였습니다."
    if theme == "back_rank":
        return f"내 왕 앞이 열려 있어 백 랭크 메이트 위험이 있습니다. {best}로 통로를 막아야 합니다."
    if theme == "hanging":
        piece = _captured_piece(item)
        what = f"{piece}을(를)" if piece else "기물을"
        return f"{my}을 두면 상대가 {reply or '응수'}로 {what} 잡습니다. {best}가 정답입니다."
    if theme == "missed_capture":
        return f"상대 기물을 잡을 수 있었습니다. {best}가 내 수 {my}보다 낫습니다."
    if theme == "fork":
        return f"상대가 {reply or '응수'}로 두 기물을 동시에 노립니다. {best}로 먼저 처리해야 합니다."
    if theme == "pin":
        return f"상대가 {reply or '응수'}로 내 기물을 묶습니다. {best}가 필요했습니다."
    if theme == "opening":
        return f"오프닝에서 {best}가 더 자연스럽습니다. {my}은 전개나 중앙 싸움에서 밀립니다."
    if theme == "endgame":
        return f"엔드게임에서 {best}가 정확합니다. {my}은 남은 기물 배치에서 손해입니다."
    if theme == "positional":
        return f"한 수로 보이는 손해는 작아도 꾸준히 밀립니다. 더 나은 수는 {best}입니다."
    return (
        f"{my} 대신 {best}를 두었어야 합니다. "
        + (f"상대는 {reply}로 처벌할 수 있었습니다." if reply else "엔진 평가가 크게 떨어졌습니다.")
    )


def backfill() -> int:
    """옛 실수에 테마·해설·생성시각을 붙인다. 이미 붙은 건 건드리지 않는다."""
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM mistakes WHERE COALESCE(theme,'')='' OR created_at=0"
        ).fetchall()
        now = now_ts()
        changed = 0
        for row in rows:
            item = dict(row)
            theme = classify(item)
            explanation = explain(item, theme)
            excluded = 1 if is_lost_position(item) else 0
            conn.execute(
                "UPDATE mistakes SET theme=?, explanation=?, "
                "created_at=CASE WHEN created_at>0 THEN created_at ELSE ? END, excluded=? "
                "WHERE id=?",
                (theme, explanation, now, excluded, item["id"]),
            )
            changed += 1
        conn.commit()
        return changed
    finally:
        conn.close()


def theme_stats(source: Optional[str] = None) -> List[Dict[str, Any]]:
    """테마별 실수 수·복습 예정·정답률. 약한 테마가 위로 오게 정렬한다."""
    now = now_ts()
    where = ["COALESCE(theme,'')<>''", "excluded=0"]
    params: List[Any] = [now]
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    clause = " AND ".join(where)
    conn = db.connect()
    try:
        rows = conn.execute(
            f"""
            SELECT theme,
                   COUNT(*) total,
                   SUM(CASE WHEN due_at>0 AND due_at<=? THEN 1 ELSE 0 END) due,
                   COALESCE(SUM(correct),0) c,
                   COALESCE(SUM(wrong),0) w,
                   ROUND(AVG(loss),2) avg_loss
            FROM mistakes WHERE {clause}
            GROUP BY theme
            """,
            (*params,),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        seen = d["c"] + d["w"]
        d["label"] = THEMES.get(d["theme"], d["theme"])
        d["mastery"] = round(d["c"] / seen, 2) if seen else None
        d["seen"] = seen
        out.append(d)
    # 한 번도 안 틀린 테마도 약한 쪽으로 본다(아직 실력이 안 검증됐으니까).
    out.sort(key=lambda x: ((x["mastery"] if x["mastery"] is not None else 0.3), -x["total"]))
    return out


def recommend(limit: int = 10, source: Optional[str] = None,
              focus: Optional[str] = None) -> List[Dict[str, Any]]:
    """다음 세션 문제를 고른다. 정답률 낮은 테마에서 주로 뽑되 섞어서 준다."""
    now = now_ts()
    if focus:
        where = ["theme=?", "excluded=0", "(due_at=0 OR due_at<=?)"]
        params: List[Any] = [focus, now]
        if source in ("bot", "human"):
            where.append("source=?")
            params.append(source)
        params.append(limit)
        conn = db.connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM mistakes WHERE {' AND '.join(where)} "
                "ORDER BY weight DESC, loss DESC, last_wrong DESC LIMIT ?",
                params,
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    stats = [s for s in theme_stats(source) if s["total"] >= 2]
    if not stats:
        return db.mistakes_due(limit=limit, source=source)
    themes = [s["theme"] for s in stats[:3]]
    picked: List[Dict[str, Any]] = []
    for theme in themes:
        selected = db.mistakes_due(limit=max(2, limit // len(themes)), source=source, theme=theme)
        picked.extend(selected)
        if len(picked) >= limit:
            break
    if len(picked) < limit:
        seen_ids = {p["id"] for p in picked}
        for row in db.mistakes_due(limit=limit * 3, source=source):
            if row["id"] not in seen_ids and row.get("theme") in themes:
                picked.append(row)
                if len(picked) >= limit:
                    break
    return picked[:limit]


def recurrence(weeks: int = 6, source: Optional[str] = None) -> Dict[str, Dict[str, int]]:
    """테마별로 최근 N주 / 그 직전 N주에 새로 생긴 실수 수를 돌려준다."""
    now = now_ts()
    span = weeks * 7 * 86400
    recent_from, prior_from = now - span, now - 2 * span
    where = ["excluded=0", "COALESCE(theme,'')<>''"]
    params: List[Any] = []
    if source in ("bot", "human"):
        where.append("source=?")
        params.append(source)
    clause = " AND ".join(where)
    conn = db.connect()
    try:
        rows = conn.execute(
            f"""
            SELECT theme,
                   SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) recent,
                   SUM(CASE WHEN created_at>=? AND created_at<? THEN 1 ELSE 0 END) prior
            FROM mistakes WHERE {clause}
            GROUP BY theme
            """,
            (recent_from, prior_from, recent_from, *params),
        ).fetchall()
    finally:
        conn.close()
    return {
        r["theme"]: {
            "label": THEMES.get(r["theme"], r["theme"]),
            "recent": int(r["recent"] or 0),
            "prior": int(r["prior"] or 0),
        }
        for r in rows
    }
