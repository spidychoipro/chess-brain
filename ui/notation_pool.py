"""노테이션 훈련용 문제 풀.

이전엔 3단계가 고정 9문제뿐이라 한두 번 돌리면 순서를 외워버렸다. 여기서는

  * 실제 오프닝 라인에서 뽑은 자연스러운 수
  * 앙파상 / 승격 / 잡으면서 승격 / 캐슬링 / 체크 / 메이트 / 기물 구분 같은
    특수 개념을 직접 만든 국면으로

를 합쳐 넓은 풀을 코드로 만든다. 각 문제에 ``concept`` 태그가 붙어 있어서
4단계가 아니라 3단계에서 약점을 겨냥할 수 있다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import chess

CONCEPT_KR: Dict[str, str] = {
    "pawn": "폰 이동 (글자 없음)",
    "piece": "기물 이동 (글자 + 칸)",
    "capture": "잡기 (x)",
    "pawn_capture": "폰으로 잡기 (파일 글자 + x)",
    "check": "체크 (+)",
    "mate": "체크메이트 (#)",
    "castle": "캐슬링 (O-O / O-O-O)",
    "promo": "승격 (=Q)",
    "promo_capture": "잡으면서 승격 (axb8=Q)",
    "disambig_file": "같은 기물 구분 · 파일 (Nbd2)",
    "disambig_rank": "같은 기물 구분 · 랭크 (R1a3)",
    "disambig_both": "같은 기물 구분 · 칸 전체 (Qa1b2)",
    "en_passant": "앙파상 (exd6)",
}

_TIPS: Dict[str, str] = {
    "pawn": "폰은 글자가 없어. 목적지 칸만 쓴다. (예: e4)",
    "piece": "기물 글자 + 목적지 칸. (예: Nf3)",
    "capture": "'x'는 잡기야. (예: Bxc6 = 비숍이 c6을 잡음)",
    "pawn_capture": "폰이 잡을 땐 출발 파일 글자를 써. (예: exd5)",
    "check": "'+'는 체크야.",
    "mate": "'#'는 체크메이트야.",
    "castle": "캐슬링은 O-O(킹사이드) / O-O-O(퀸사이드).",
    "promo": "승격은 '=Q' 처럼 써. (예: a8=Q)",
    "promo_capture": "잡으면서 승격하면 'axb8=Q'.",
    "disambig_file": "같은 기물이 둘 다 갈 수 있으면 파일 글자를 붙여. (예: Nbd2)",
    "disambig_rank": "같은 파일에 있으면 랭크 숫자를 붙여. (예: R1a3)",
    "disambig_both": "파일도 랭크도 같으면 칸 전체를 붙여. (예: Qa1b2)",
    "en_passant": "앙파상은 폰이 잡는 것처럼 파일 글자로 써. (예: exd6)",
}


def concept_tip(concept: str) -> str:
    return _TIPS.get(concept, "")


def _step(board: chess.Board, san: str, concept: str) -> Dict[str, Any]:
    mv = board.parse_san(san)
    return {
        "fen": board.fen(),
        "san": board.san(mv),
        "from": mv.from_square,
        "to": mv.to_square,
        "piece": board.piece_at(mv.from_square).piece_type,
        "concept": concept,
    }


def _line(sans: List[str], concepts: List[str]) -> List[Dict[str, Any]]:
    b = chess.Board()
    out: List[Dict[str, Any]] = []
    for san, concept in zip(sans, concepts):
        out.append(_step(b, san, concept))
        b.push(b.parse_san(san))
    return out


def _mk(fen: str, san: str, concept: str) -> Dict[str, Any]:
    return _step(chess.Board(fen), san, concept)


def item_id(it: Dict[str, Any]) -> str:
    return f"{it.get('concept','')}:{it['san']}"


def stage3_pool() -> List[Dict[str, Any]]:
    """3단계 전체 풀. 쉬운 개념부터 골고루."""
    items: List[Dict[str, Any]] = []

    # 자연스러운 오프닝 라인 (폰/기물/잡기/폰잡기/캐슬링/체크메이트)
    items += _line(
        ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Bxc6", "dxc6", "O-O"],
        ["pawn", "pawn", "piece", "piece", "piece", "pawn",
         "capture", "pawn_capture", "castle"],
    )
    items += _line(
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5"],
        ["pawn", "pawn", "pawn", "pawn", "piece", "piece", "piece"],
    )
    items += _line(
        ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4"],
        ["pawn", "pawn", "piece", "pawn", "pawn", "pawn_capture", "capture"],
    )
    items += _line(
        ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"],
        ["pawn", "pawn", "piece", "piece", "piece", "piece", "mate"],
    )
    items += _line(
        ["e4", "e6", "d4", "d5", "Nc3", "Nf6", "e5"],
        ["pawn", "pawn", "pawn", "pawn", "piece", "piece", "pawn"],
    )
    items += _line(
        ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4"],
        ["pawn", "piece", "pawn", "pawn", "piece", "piece", "pawn"],
    )

    # 특수 개념은 국면을 직접 만든다.
    items.append(_mk("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "O-O-O", "castle"))
    items.append(_mk("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "O-O", "castle"))
    items.append(_mk("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "Rh8+", "check"))
    items.append(_mk("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "Ra8#", "mate"))
    items.append(_mk("8/P6k/8/8/8/8/7K/8 w - - 0 1", "a8=Q", "promo"))
    items.append(_mk("1r5k/P7/8/8/8/8/7K/8 w - - 0 1", "axb8=Q", "promo_capture"))
    items.append(_mk("4k3/8/8/8/8/5N2/8/1N2K3 w - - 0 1", "Nbd2", "disambig_file"))
    items.append(_mk("4k3/8/8/R7/8/8/8/R3K3 w - - 0 1", "R1a3", "disambig_rank"))
    items.append(_mk("4k3/8/8/8/8/2Q5/8/Q3K3 w - - 0 1", "Qa1b2", "disambig_both"))

    # 앙파상: 1.e4 a6 2.e5 d5 -> exd6
    b = chess.Board()
    for s in ["e4", "a6", "e5", "d5"]:
        b.push(b.parse_san(s))
    items.append(_step(b, "exd6", "en_passant"))

    # 중복 제거(fen + san)
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (it["fen"], it["san"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def stage2_targets(level: int) -> List[str]:
    """칸 이름 난이도. 0=모서리·중앙, 1=가장자리, 2=전체."""
    if level <= 0:
        return ["a1", "h1", "a8", "h8", "d4", "e4", "d5", "e5"]
    if level == 1:
        return [
            chess.square_name(s)
            for s in chess.SQUARES
            if chess.square_name(s)[0] in "ah" or chess.square_name(s)[1] in "18"
        ]
    return [chess.square_name(s) for s in chess.SQUARES]


def stage4_lines() -> List[Tuple[str, List[str]]]:
    """4단계(머릿속 보드) 라인들. 이름 + SAN 목록."""
    return [
        ("루이 로페스", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4"]),
        ("이탈리안", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6"]),
        ("퀸즈 갬빗", ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7"]),
        ("시실리안", ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"]),
    ]


def line_steps(sans: List[str]) -> List[Dict[str, Any]]:
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
            }
        )
        b.push(mv)
    return out
