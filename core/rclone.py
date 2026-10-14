"""rclone 을 통해 구글드라이브를 로컬처럼 쓴다.

rclone 은 **자체적으로** 구글 드라이브 인증을 갖고 있으므로, 앱은 API 키나
OAuth 를 전혀 몰라도 된다. 두 가지 방식:

- ``copy``  : ``.pgn`` 을 로컬 폴더로 복사(미러). 인터넷이 끊겨도 이후 읽기 가능.
- ``mount`` : 드라이브를 로컬 드라이브 문자(예: ``X:``)로 붙인다. 폴더가 곧
  드라이브라 복사가 필요 없지만, Windows 에서는 WinFsp 가 있어야 한다.

rclone 은 설치 프로그램 없이 exe 하나만 있으면 된다.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from core import config as cfg_mod
from core.utils import data_dir

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


def get_config(cfg: Dict[str, Any]) -> str:
    """rclone.conf 경로. 비어 있으면 rclone 기본 위치를 쓴다."""
    return (cfg_mod.get(cfg, "rclone.config", "") or "").strip()


def build_copy_cmd(exe: str, remote: str, dest: str, config: str = "") -> List[str]:
    """``rclone copy`` 명령. ``.pgn`` 만, 하위폴더 구조는 유지.

    rclone 전역 플래그(``--config``)는 서브커맨드 앞에 와야 한다.
    """
    cmd: List[str] = [exe]
    if config:
        cmd += ["--config", config]
    cmd += [
        "copy",
        remote,
        dest,
        "--include", "*.pgn",
        "--transfers", "4",
        "--stats", "1s",
        "--stats-one-line",
        "-v",
    ]
    return cmd


def run_copy(exe: str, remote: str, dest: str, config: str = "", on_line=None) -> int:
    """rclone copy 를 실행하고 출력을 한 줄씩 넘긴다. 반환값은 종료 코드."""
    cmd = build_copy_cmd(exe, remote, dest, config)
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


# -- mount (드라이브를 로컬 드라이브 문자로) -----------------------------------

# Windows 에서 rclone mount 는 WinFsp 가 있어야 한다.
_WINFSP_DLLS = [
    r"C:\Program Files (x86)\WinFsp\bin\winfsp-x64.dll",
    r"C:\Program Files\WinFsp\bin\winfsp-x64.dll",
    r"C:\Program Files (x86)\WinFsp\bin\winfsp-a64.dll",
    r"C:\Program Files\WinFsp\bin\winfsp-a64.dll",
]

# 현재 붙어 있는 mount 프로세스 (앱 수명 동안 하나만).
_MOUNT_PROC: Optional[subprocess.Popen] = None


def find_winfsp() -> Optional[str]:
    """WinFsp 설치 경로를 찾는다. 없으면 ``None`` (mount 불가)."""
    for dll in _WINFSP_DLLS:
        if os.path.isfile(dll):
            return os.path.dirname(dll)
    try:
        import winreg

        for root, key in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\WinFsp"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WinFsp"),
        ):
            try:
                with winreg.OpenKey(root, key) as k:
                    install, _ = winreg.QueryValueEx(k, "InstallDir")
                    if install and os.path.isdir(install):
                        return install
            except OSError:
                continue
    except Exception:
        pass
    return None


def get_mount_point(cfg: Dict[str, Any]) -> str:
    """드라이브 문자/경로 (예: ``X:``)."""
    return (cfg_mod.get(cfg, "rclone.mount_point", "") or "").strip()


def build_mount_cmd(exe: str, remote: str, mountpoint: str, config: str = "") -> List[str]:
    """``rclone mount`` 명령. 읽기 전용이라 앱이 실수로 드라이브를 건드리지 않는다."""
    cmd: List[str] = [exe]
    if config:
        cmd += ["--config", config]
    cmd += [
        "mount",
        remote,
        mountpoint,
        "--read-only",
        "--dir-cache-time", "1m",
        "--vfs-cache-mode", "off",
        "--volname", "chess-brain",
        "--no-modtime",
    ]
    return cmd


def mount_running() -> bool:
    return _MOUNT_PROC is not None and _MOUNT_PROC.poll() is None


def start_mount(exe: str, remote: str, mountpoint: str, config: str = "") -> subprocess.Popen:
    """rclone mount 를 백그라운드로 띄운다(창 없이). 이미 붙어 있으면 예외."""
    global _MOUNT_PROC
    if mount_running():
        raise RuntimeError("이미 드라이브가 붙어 있습니다. 먼저 '마운트 해제' 하세요.")

    log_path = data_dir() / "rclone-mount.log"
    log = open(log_path, "a", encoding="utf-8", errors="replace")
    log.write(f"\n===== mount {remote} -> {mountpoint} =====\n")
    log.flush()

    _MOUNT_PROC = subprocess.Popen(
        build_mount_cmd(exe, remote, mountpoint, config),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return _MOUNT_PROC


def normalize_mount_point(mountpoint: str) -> str:
    """``X:`` → ``X:\\`` 처럼 폴더로 읽히게 다듬는다."""
    p = mountpoint.strip()
    if len(p) == 2 and p[1] == ":":
        return p + "\\"
    return p


def wait_for_mount(mountpoint: str, timeout: float = 25.0) -> bool:
    """드라이브가 실제로 붙어 읽히기 시작할 때까지 기다린다."""
    target = normalize_mount_point(mountpoint)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _MOUNT_PROC is not None and _MOUNT_PROC.poll() is not None:
            return False  # rclone 이 곧바로 죽음 (설정/WinFsp 문제)
        if os.path.isdir(target):
            try:
                os.listdir(target)
                return True
            except OSError:
                pass
        time.sleep(0.4)
    return False


def stop_mount(timeout: float = 5.0) -> bool:
    """붙어 있는 mount 프로세스를 종료한다. 붙어 있던 게 있으면 True."""
    global _MOUNT_PROC
    proc = _MOUNT_PROC
    _MOUNT_PROC = None
    if proc is None:
        return False
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return True
