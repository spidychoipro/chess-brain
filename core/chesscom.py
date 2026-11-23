"""chess.com → 로컬 PGN 수집.

앱이 chess.com API 를 직접 다시 구현하지 않고, 이미 검증된 외부 동기화 도구
(``chess_pgn_sync.py``)를 호출한다. 이 도구가 사람 게임은 공개 아카이브 API로,
봇 게임은 게임 아카이브에서 받아서 로컬 PGN 폴더와 Drive 에 저장한다.
앱은 그 뒤 기존 로컬 스캔으로 DB 에 넣는다.

게임 수는 중요하지 않다. API 는 달 단위로 한 번에 받고, 도구의 processed 목록이
이미 받은 게임을 걸러서 새 것만 저장한다. 3일치 30판이나 5개월치 300판이나
같은 방식으로 처리된다.

네트워크가 막히거나 도구가 없어도 예외를 던지지 않고 ``error`` 에 담는다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from core import config as cfg_mod

_SAVED = re.compile(r"새로\s*저장\s*(\d+)\s*개")
_EXE = re.compile(r'"([^"]+\.exe)"', re.IGNORECASE)


def script_path(cfg: Dict[str, Any]) -> str:
    """동기화 도구 경로. 설정에 없으면 흔한 위치를 확인한다."""
    val = (cfg_mod.get(cfg, "chesscom.sync_script", "") or "").strip()
    if val:
        return os.path.expanduser(val)
    guess = Path.home() / "chesscom_pgn_auto" / "chess_pgn_sync.py"
    return str(guess) if guess.is_file() else ""


def _python_for(script: str, cfg: Dict[str, Any]) -> str:
    """도구를 돌릴 파이썬. frozen 앱의 sys.executable 은 exe 라서 못 쓴다."""
    val = (cfg_mod.get(cfg, "chesscom.python", "") or "").strip()
    if val:
        return os.path.expanduser(val)
    cmd = Path(script).with_name("python.cmd")
    if cmd.is_file():
        try:
            match = _EXE.search(cmd.read_text(encoding="utf-8", errors="replace"))
            if match and Path(match.group(1)).is_file():
                return match.group(1)
        except OSError:
            pass
    if not getattr(sys, "frozen", False):
        return sys.executable
    return shutil.which("python") or shutil.which("py") or ""


def fetch_recent(
    cfg: Dict[str, Any],
    on_progress: Optional[Any] = None,
    full: bool = False,
) -> Dict[str, Any]:
    """chess.com 에서 새 PGN 을 받는다. 실패해도 예외를 던지지 않는다.

    ``full=True`` 면 ``--all`` 로 아직 안 받은 과거 게임 전부를 훑는다. 앱을 켠
    뒤 첫 따라잡기에서 쓴다. 그 외에는 도구 기본값(최근 7일)으로 가볍게 확인한다.
    """
    result: Dict[str, Any] = {
        "ran": False, "ok": False, "new": 0, "error": "", "full": bool(full)
    }
    if not cfg_mod.get(cfg, "chesscom.auto_fetch", True):
        return result

    script = script_path(cfg)
    if not script or not Path(script).is_file():
        result["error"] = "chess.com 수집 도구를 찾지 못했어요. (설정에서 경로 지정)"
        return result
    python = _python_for(script, cfg)
    if not python:
        result["error"] = "수집 도구를 돌릴 파이썬을 찾지 못했어요."
        return result

    cmd = [python, script] + (["--all"] if full else [])
    timeout = int(cfg_mod.get(cfg, "chesscom.fetch_timeout", 900) or 900)
    mode = "전체" if full else "최근 7일"
    if on_progress:
        on_progress(f"chess.com에서 새 대국 확인 ({mode})…")
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            cmd,
            cwd=str(Path(script).parent),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        match = _SAVED.search(output)
        result["ran"] = True
        result["ok"] = proc.returncode == 0
        result["new"] = int(match.group(1)) if match else 0
        if proc.returncode != 0:
            result["error"] = output.strip()[-300:] or f"종료 코드 {proc.returncode}"
        elif on_progress:
            on_progress(f"chess.com PGN {result['new']}개 저장")
    except subprocess.TimeoutExpired:
        result["error"] = (
            f"chess.com 수집이 {timeout}초 안에 안 끝났어요. 다음 번에 다시 시도합니다."
        )
    except Exception as exc:
        result["error"] = f"chess.com 수집 실패: {exc}"
    return result
