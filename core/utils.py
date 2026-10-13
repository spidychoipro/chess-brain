"""Shared paths and tiny helpers."""
from __future__ import annotations

import sys
import time
from pathlib import Path


def project_root() -> Path:
    """Where data/ and config/ live.

    Source run: the repo root. Frozen (PyInstaller) run: next to the exe,
    so data/config stay persistent instead of evaporating from the temp
    extraction dir.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    d = project_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_dir() -> Path:
    d = project_root() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_dirs() -> None:
    data_dir()
    config_dir()


def now_ts() -> int:
    return int(time.time())


def today_str() -> str:
    return time.strftime("%Y-%m-%d")


def day_start_ts(offset_days: int = 0) -> int:
    """Start of today (local) shifted by offset_days."""
    lt = time.localtime()
    base = time.mktime(
        (lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)
    )
    return int(base + offset_days * 86400)
