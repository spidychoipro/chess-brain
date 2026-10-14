"""Optional Stockfish bridge.

The engine is only ever used to *find my mistakes* in human games. The
notation training sub-feature never depends on it, so a missing or wrong
path simply disables the mistakes tab instead of breaking the app.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
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
    for d in _app_dirs():
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for fn in names:
            low = fn.lower()
            if low.startswith("stockfish") and low.endswith(".exe"):
                candidates.append(os.path.join(d, fn))

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

    def __init__(
        self,
        path: str,
        depth: int = 12,
        threads: Optional[int] = None,
        hash_mb: Optional[int] = None,
    ):
        if not engine_available(path):
            raise FileNotFoundError(f"stockfish not found: {path}")
        self.path = path
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

        my_san = board.san(move)
        best_san = before["best_san"]

        # 엔진 최선수를 그대로 둔 건 실수가 아니다.
        if best_san and best_san == my_san:
            return None

        after_board = board.copy()
        after_board.push(move)
        # 수를 둔 뒤 국면이 끝났으면 엔진 점수를 믿지 말고 직접 판정한다.
        # 체크메이트 직후 Stockfish 는 Mate(0) 을 주는데, _to_pawns 가 부호를
        # 못 살려서 -100 으로 뒤집히는 문제가 있었다(메이트를 걸었는데 손실 200).
        if after_board.is_checkmate():
            score_after = 100.0              # 내가 메이트를 걸었다
        elif after_board.is_game_over():     # 스테일메이트/기물부족/50수 = 무승부
            score_after = 0.0
        else:
            score_after = engine.evaluate(after_board) * sign

        loss = score_before - score_after

        if loss >= threshold:
            return MistakeResult(
                eval_before=round(score_before, 3),
                eval_after=round(score_after, 3),
                loss=round(loss, 3),
                best_san=best_san,
                my_san=my_san,
            )
        return None
    finally:
        if owns_engine and engine is not None:
            engine.__exit__(None, None, None)
