"""chess.com → 로컬 PGN 수집.

앱이 chess.com API 를 직접 다시 구현하지 않고, 이미 검증된 외부 동기화 도구
(``chess_pgn_sync.py``)를 호출한다. 이 도구가 사람 게임은 공개 아카이브 API로,
봇 게임은 게임 아카이브에서 받아서 로컬 PGN 폴더와 Drive 에 저장한다.
앱은 그 뒤 기존 로컬 스캔으로 DB 에 넣는다.

도구가 찍는 줄을 한 줄씩 그대로 ``on_progress`` 로 흘려보내고
``data/chesscom-sync.log`` 에도 남긴다. 창에 로그창이 없어도 진행 상황을 볼 수
있게 하려는 것. 실패해도 예외를 던지지 않고 ``error`` 에 담는다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, Optional

from core import config as cfg_mod
from core import utils

_SAVED = re.compile(r"새로\s*저장\s*(\d+)\s*개")
_EXE = re.compile(r'"([^"]+\.exe)"', re.IGNORECASE)
LOG_NAME = "chesscom-sync.log"


def script_path(cfg: Dict[str, Any]) -> str:
    """동기화 도구 경로. 설정에 없으면 흔한 위치를 확인한다."""
    val = (cfg_mod.get(cfg, "chesscom.sync_script", "") or "").strip()
    if val:
        return os.path.expanduser(val)
    guess = Path.home() / "chesscom_pgn_auto" / "chess_pgn_sync.py"
    return str(guess) if guess.is_file() else ""


def log_path() -> Path:
    return utils.data_dir() / LOG_NAME


def _append_log(line: str) -> None:
    """도구 출력을 파일에도 남itin다. 로그 실패가 수집을 막으면 안 된다."""
    try:
        with log_path().open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
    except OSError:
        pass


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
    """chess.com 에서 새 PGN 을 받는다. 출력을 실시간으로 보여준다.

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

    # 사람 게임은 달 단위 API라 과거 전부 받아도 1~2초면 끝난다. 봇은 게임마다
    # 브라우저를 띄워서 수백 개를 한 번에 훑으면 10분 넘게 걸리므로 최근 것만 본다.
    cmd = [python, script] + (["--all-humans"] if full else [])
    # 제일 느린 건 드라이브 파일 목록 읽기(20~40초)였다. 도구가 로컬 파일과
    # processed 만으로 중복을 판단하도록 해서 3분의 2 정도를 줄인다.
    if cfg_mod.get(cfg, "chesscom.skip_drive_list", True):
        cmd.append("--no-drive-list")
    timeout = int(cfg_mod.get(cfg, "chesscom.fetch_timeout", 900) or 900)
    mode = "전체" if full else "최근 7일"
    banner = f"chess.com에서 새 대국 확인 ({mode})…"
    if on_progress:
        on_progress(banner)
    _append_log(f"===== {banner} =====")

    proc = None
    lines: list[str] = []
    try:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            cmd,
            cwd=str(Path(script).parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        queue: Queue = Queue()

        def _read() -> None:
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    queue.put(line.rstrip("\r\n"))
            finally:
                queue.put(None)

        threading.Thread(target=_read, daemon=True).start()

        deadline = time.monotonic() + timeout
        while True:
            try:
                line = queue.get(timeout=0.5)
            except Empty:
                if time.monotonic() > deadline:
                    raise subprocess.TimeoutExpired(cmd, timeout)
                if proc.poll() is not None and queue.empty():
                    break
                continue
            if line is None:
                break
            if line.strip():
                lines.append(line)
                _append_log(line)
                if on_progress:
                    on_progress(line)

        code = proc.wait(timeout=max(1, deadline - time.monotonic()))
        output = "\n".join(lines)
        match = _SAVED.search(output)
        result["ran"] = True
        result["ok"] = code == 0
        result["new"] = int(match.group(1)) if match else 0
        if code != 0:
            result["error"] = output.strip()[-300:] or f"종료 코드 {code}"
            _append_log(f"[실패] {result['error']}")
        else:
            done = f"chess.com PGN {result['new']}개 저장"
            _append_log(f"[완료] {done}")
            if on_progress:
                on_progress(done)
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill()
            proc.wait()
        result["error"] = (
            f"chess.com 수집이 {timeout}초 안에 안 끝났어요. 다음 번에 다시 시도합니다."
        )
        _append_log(f"[실패] {result['error']}")
        if on_progress:
            on_progress(result["error"])
    except Exception as exc:
        result["error"] = f"chess.com 수집 실패: {exc}"
        _append_log(f"[실패] {result['error']}")
        if on_progress:
            on_progress(result["error"])
    return result
