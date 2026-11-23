"""Optional Stockfish bridge.

The engine is only ever used to *find my mistakes* in human games. The
notation training sub-feature never depends on it, so a missing or wrong
path simply disables the mistakes tab instead of breaking the app.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import chess
import chess.engine


def engine_available(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def default_threads() -> int:
    """분석용 스레드 수.

    이 앱은 depth 6~20 사이의 *짧은* 탐색을 수백 번 돌린다. 이 구간에선
    Stockfish Lazy SMP 의 동기화/하이퍼스레딩 오버헤드가 이득을 넘어서서
    1스레드가 가장 빠르다(실측: depth12 1t 2.5s vs 8t 4.8s). 그래서 기본 1.
    아주 깊게(depth 24+) 돌릴 때만 늘리는 게 낫다.
    """
    return 1


# -- stockfish 자동 감지 ------------------------------------------------------

# 이름에 CPU 명령셋이 들어간 빌드가 여러 개 있으면 빠른 것부터 고른다.
def _sf_rank(name: str) -> int:
    n = name.lower()
    if n == "stockfish.exe":
        return 0
    for i, tag in enumerate(("bmi2", "avx2", "avx", "popcnt", "sse41"), start=1):
        if tag in n:
            return i
    return 6


# 훑을 때 건너뛸 폴더. OneDrive 는 규칙상 아예 열지 않는다(placeholder 다운로드 방지).
_SKIP_DIRS = {
    "windows", "$recycle.bin", "system volume information", "onedrive",
    "node_modules", ".git", ".venv", "venv", "__pycache__", "appdata",
    "saved games", "searches", "links", "favorites", "recent", "contacts",
    "templates", "nethood", "printhood", "start menu", "시작 메뉴",
    "my documents", "application data", "local settings", "cookies",
    "music", "pictures", "videos", "3d objects",
}


def _common_dirs() -> List[str]:
    env = os.environ.get
    home = env("USERPROFILE", "")
    local = env("LOCALAPPDATA", "")
    dirs = [
        local + r"\Programs",
        local + r"\Microsoft\WinGet\Links",
        local + r"\Microsoft\WinGet\Packages",
        home + r"\scoop\shims",
        home + r"\scoop\apps",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\ProgramData\chocolatey\bin",
        r"C:\stockfish",
        home,
        home + r"\Downloads",
        home + r"\Desktop",
        home + r"\Documents",
        home + r"\Projects",
        home + r"\Dev",
        home + r"\chess분석",
        home + r"\chess-brain",
        home + r"\chesscom_pgn_auto",
    ]
    return [d for d in dirs if d and os.path.isdir(d)]


def _app_dirs() -> List[str]:
    """앱(또는 소스) 옆에 stockfish 를 같이 둔 경우를 잡는다."""
    dirs: List[str] = []
    try:
        from core.utils import project_root

        root = project_root()
        dirs += [str(root), str(root / "engines"), str(root.parent)]
    except Exception:
        pass
    dirs += [os.getcwd(), os.path.join(os.getcwd(), "engines")]
    seen, out = set(), []
    for d in dirs:
        ad = os.path.abspath(d)
        if ad not in seen and os.path.isdir(ad):
            seen.add(ad)
            out.append(ad)
    return out


def _walk_for_sf(root: str, max_depth: int = 3) -> List[str]:
    root = os.path.abspath(root)
    base = root.rstrip("\\/").count(os.sep)
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip("\\/").count(os.sep) - base
        if depth >= max_depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS]
        for fn in filenames:
            low = fn.lower()
            if low.startswith("stockfish") and low.endswith(".exe"):
                found.append(os.path.join(dirpath, fn))
    return found


def find_stockfish(fast: bool = False) -> Optional[str]:
    """stockfish.exe 를 찾는다. ``fast=True`` 면 널리 훑지 않고 흔한 자리만 본다.

    PATH → 앱 옆 → 흔한 설치 위치 순. 결과는 CPU 명령셋이 빠른 빌드 우선.
    """
    which = shutil.which("stockfish")
    if which and os.path.isfile(which):
        return which

    candidates: List[str] = []
    # 앱 폴더도 재귀적으로 본다. 번들 엔진은 engines\stockfish\ 안에 있어서
    # 한 겹만 보면 못 찾는다 (릴리스 zip 이 그 구조로 들어간다).
    for d in _app_dirs():
        candidates += _walk_for_sf(d, max_depth=2)

    dirs = _common_dirs()
    # fast 는 한 단계만(=예: Downloads\stockfish\stockfish.exe 같은 한 겹 안쪽까지),
    # 버튼을 눌렀을 땐 몇 단계 더 들어가 본다.
    depth = 1 if fast else 3
    for d in dirs:
        candidates += _walk_for_sf(d, max_depth=depth)

    if not candidates:
        return None
    # 중복 제거 후 CPU 명령셋 빠른 빌드 우선.
    uniq = sorted(set(candidates))
    uniq.sort(key=lambda p: (_sf_rank(os.path.basename(p)), os.path.basename(p).lower()))
    return uniq[0]


def resolve_engine_path(path: str) -> str:
    """설정 경로가 비었거나 깨졌으면 앱 폴더의 번들/시스템 엔진으로 대체한다.

    릴리스 zip 에는 ``engines\\stockfish\\`` 가 같이 들어간다. 새 사용자는 설정을
    하나도 안 건드려도 분석이 돌아야 하므로, 저장된 경로가 없거나 예전 컴퓨터를
    가리키고 있으면 자동 감지로 넘어간다.
    """
    if path:
        p = os.path.expanduser(path)
        root = None
        try:
            from core.utils import project_root

            root = project_root()
        except Exception:
            pass
        if os.path.isabs(p) and os.path.isfile(p):
            return os.path.abspath(p)
        # 상대 경로는 cwd 가 아니라 앱 폴더 기준으로 먼저 찾는다. 더블클릭 실행 시
        # cwd 가 어디든 ( 바로가기 '시작 위치' 등 ) 번들 엔진을 찾을 수 있게.
        if root is not None:
            alt = root / p
            if alt.is_file():
                return str(alt.resolve())
        if os.path.isfile(p):
            return os.path.abspath(p)
    return find_stockfish(fast=True) or ""


def _to_pawns(pov) -> float:
    """Convert a PovScore to pawns from White's point of view."""
    score = pov.white()
    return float(score.score(mate_score=10000) or 0) / 100.0


@dataclass
class MistakeResult:
    eval_before: float
    eval_after: float
    loss: float
    best_san: str
    my_san: str
    reply_san: str = ""   # 내가 둔 수에 대한 상대의 최선 응수(왜 나빴는지)
    accepted_sans: List[str] = field(default_factory=list)
    best_line: List[str] = field(default_factory=list)
    reply_line: List[str] = field(default_factory=list)
    mate_before: Optional[int] = None
    mate_after: Optional[int] = None


class Stockfish:
    """Thin wrapper so callers don't juggle process lifecycles."""

    def __init__(
        self,
        path: str,
        depth: int = 12,
        threads: Optional[int] = None,
        hash_mb: Optional[int] = None,
    ):
        resolved = resolve_engine_path(path) if path else find_stockfish(fast=True) or ""
        if not engine_available(resolved):
            raise FileNotFoundError(f"stockfish not found: {path or '(설정 없음)'}")
        self.path = resolved
        self.depth = depth
        # 0/None 이면 자동. 기본이 1스레드라 분석이 유난히 느렸다.
        self.threads = threads or default_threads()
        self.hash_mb = hash_mb if hash_mb is not None else 256
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "Stockfish":
        self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
        # 스레드/해시를 안 주면 1스레드라 실수 분석이 오래 걸린다.
        try:
            self._engine.configure({"Threads": int(self.threads), "Hash": int(self.hash_mb)})
        except Exception:  # noqa: BLE001 - 엔진이 옵션을 안 받아도 그냥 진행
            pass
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

    def candidates(self, board: chess.Board) -> List[Dict[str, Any]]:
        assert self._engine is not None
        infos = self._engine.analyse(board, chess.engine.Limit(depth=self.depth), multipv=3)
        return [{"info": info, "best_san": board.san(info["pv"][0]),
                 "pawns_white": _to_pawns(info["score"])}
                for info in infos if info.get("pv")]


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
        candidates = engine.candidates(board)
        if not candidates:
            return None
        before = candidates[0]
        sign = 1.0 if board.turn == chess.WHITE else -1.0
        score_before = before["pawns_white"] * sign

        my_san = board.san(move)
        best_san = before["best_san"]
        mate_before = before["info"]["score"].pov(board.turn).mate()
        accepted = []
        for candidate in candidates:
            mate = candidate["info"]["score"].pov(board.turn).mate()
            value = candidate["pawns_white"] * sign
            if (mate_before is not None and mate_before > 0 and mate is not None and mate > 0) or (
                mate_before is None and mate is None and score_before - value <= 0.25
            ):
                accepted.append(candidate["best_san"])
        if best_san not in accepted:
            accepted.insert(0, best_san)

        # 엔진 최선수를 그대로 둔 건 실수가 아니다.
        if my_san in accepted:
            return None

        after_board = board.copy()
        after_board.push(move)
        after = None
        mate_after = None
        # 수를 둔 뒤 국면이 끝났으면 엔진 점수를 믿지 말고 직접 판정한다.
        # 체크메이트 직후 Stockfish 는 Mate(0) 을 주는데, _to_pawns 가 부호를
        # 못 살려서 -100 으로 뒤집히는 문제가 있었다(메이트를 걸었는데 손실 200).
        if after_board.is_checkmate():
            score_after = 100.0              # 내가 메이트를 걸었다
        elif after_board.is_game_over():     # 스테일메이트/기물부족/50수 = 무승부
            score_after = 0.0
        else:
            after = engine.best_move(after_board)
            score_after = after["pawns_white"] * sign
            mate_after = after["info"]["score"].pov(board.turn).mate()

        loss = score_before - score_after

        if loss >= threshold:
            # 왜 나빴는지: 상대가 어떻게 응수했을지(처벌 수)를 같이 남긴다.
            # 국면이 끝났으면(메이트/무승부) 응수가 없으니 건너뛴다.
            reply_san = ""
            if not after_board.is_game_over():
                try:
                    reply_san = (after.get("best_san") or "") if after else ""
                except Exception:  # noqa: BLE001 - 응수 못 구해도 실수 자체는 살린다
                    reply_san = ""
            return MistakeResult(
                eval_before=round(score_before, 3),
                eval_after=round(score_after, 3),
                loss=round(loss, 3),
                best_san=best_san,
                my_san=my_san,
                reply_san=reply_san,
                accepted_sans=accepted,
                best_line=[m.uci() for m in before["info"].get("pv", [])[:8]],
                reply_line=([move.uci()] + [m.uci() for m in after["info"].get("pv", [])[:7]]) if after else [move.uci()],
                mate_before=mate_before,
                mate_after=mate_after,
            )
        return None
    finally:
        if owns_engine and engine is not None:
            engine.__exit__(None, None, None)
