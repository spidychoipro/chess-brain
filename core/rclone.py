"""rclone 을 통해 드라이브 폴더를 로컬로 가져온다.

rclone 은 **자체적으로** 구글 드라이브 인증을 갖고 있으므로, 앱은 API 키나
OAuth 를 전혀 몰라도 된다. 사용자가 rclone remote(예: ``gdrive:chess-brian``)만
알려주면 ``rclone copy`` 로 ``.pgn`` 을 로컬 폴더에 미러링하고, 이어서 로컬
동기화를 돌린다. rclone 은 설치 프로그램 없이 exe 하나만 있으면 된다.
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional

from core import config as cfg_mod

# rclone.exe 를 흔히 두는 위치들 (PATH 에 없을 때 보조)
_COMMON = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "rclone.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "shims", "rclone.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), "rclone", "rclone.exe"),
    r"C:\Program Files\rclone\rclone.exe",
    r"C:\ProgramData\chocolatey\bin\rclone.exe",
]


def find_binary(cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """config > PATH > 흔한 설치 위치 순으로 rclone 실행파일을 찾는다."""
    if cfg is not None:
        p = (cfg_mod.get(cfg, "rclone.binary", "") or "").strip()
        if p and os.path.isfile(p):
            return p
    found = shutil.which("rclone")
    if found:
        return found
    for cand in _COMMON:
        if cand and os.path.isfile(cand):
            return cand
    return None


def get_remote(cfg: Dict[str, Any]) -> str:
    return (cfg_mod.get(cfg, "rclone.remote", "") or "").strip()


def build_copy_cmd(exe: str, remote: str, dest: str) -> List[str]:
    """``rclone copy`` 명령. ``.pgn`` 만, 하위폴더 구조는 유지."""
    return [
        exe,
        "copy",
        remote,
        dest,
        "--include", "*.pgn",
        "--transfers", "4",
        "--stats", "1s",
        "--stats-one-line",
        "-v",
    ]


def run_copy(exe: str, remote: str, dest: str, on_line=None) -> int:
    """rclone copy 를 실행하고 출력을 한 줄씩 넘긴다. 반환값은 종료 코드."""
    import subprocess

    cmd = build_copy_cmd(exe, remote, dest)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        text = line.rstrip()
        if text and on_line:
            on_line(text)
    proc.wait()
    return proc.returncode
