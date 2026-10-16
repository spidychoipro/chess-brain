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


# 실수 등급 기준(손실 폰). 라벨은 UI 에서 그대로 쓴다.
BLUNDER_PAWNS = 2.0
MISTAKE_PAWNS = 1.0


def classify_loss(loss) -> tuple:
    """손실(폰) -> (등급키, 한국어 라벨).

    2.0 폰 이상은 블런더, 1.0 이상은 실수, 그 아래는 부정확.
    실수 탐지 임계값이 0.8 이라 대개 '부정확'부터 시작한다.
    """
    try:
        v = float(loss or 0.0)
    except (TypeError, ValueError):
        v = 0.0
    if v >= BLUNDER_PAWNS:
        return ("blunder", "블런더")
    if v >= MISTAKE_PAWNS:
        return ("mistake", "실수")
    return ("inaccuracy", "부정확")


def today_str() -> str:
    return time.strftime("%Y-%m-%d")


def day_start_ts(offset_days: int = 0) -> int:
    """Start of today (local) shifted by offset_days."""
    lt = time.localtime()
    base = time.mktime(
        (lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)
    )
    return int(base + offset_days * 86400)
