"""JSON config load/save.

Everything the app needs to remember (drive folder, stockfish path, SR
thresholds) lives in one small json file next to the code so the whole
folder can be copied around as a unit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.utils import config_dir, ensure_dirs

DEFAULTS: Dict[str, Any] = {
    "chesscom": {
        "username": "",          # 내 chess.com 아이디 (빈 값이면 아래 색 기준)
        "fallback_color": "white",
    },
    "google_drive": {
        "parent_folder_id": "",
        "parent_folder_name": "",
        # 폴더를 '링크가 있는 모든 사용자'로 공유했을 때 쓰는 API 키.
        # 있으면 구글 로그인(OAuth) 없이 바로 읽는다. (무료)
        "api_key": "",
    },
    "local": {
        "pgn_folder": "",        # 로컬 PGN 폴더 (드라이브에서 내려받을 위치)
    },
    "rclone": {
        # rclone 으로 드라이브 폴더를 로컬로 가져올 때 쓴다.
        # rclone 이 자체적으로 구글 인증을 갖고 있어서 앱은 API 키/OAuth 가 필요 없다.
        "binary": "",            # rclone.exe 경로 (비우면 PATH/흔한 위치 자동 탐색)
        "config": "",            # rclone.conf 경로 (비우면 rclone 기본 위치)
        "remote": "",            # 예: "gdrive:chess분석"
        "mount_point": "",       # mount 할 드라이브 문자 (예: "X:")
    },
    "stockfish": {
        "path": "",
        "depth": 12,
        "threads": 0,            # 0 = CPU 코어 자동 (예전엔 1스레드라 느렸음)
        "hash_mb": 256,
    },
    "mistakes": {
        "loss_threshold": 0.80,  # pawn 단위 손실 임계값
        "source": "human",       # 실수 분석 기본 소스
    },
    "training": {
        "default_source": "bot",  # bot|human|both
        "default_mode": "recall",  # recall|drill
    },
    "sr": {
        "wrong_due_seconds": 600,  # 오답 후 재출제까지(초)
    },
    "ui": {
        "last_tab": "mistakes",
    },
}


def config_path() -> Path:
    ensure_dirs()
    return config_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    p = config_path()
    if not p.exists():
        save_config(DEFAULTS)
        return json.loads(json.dumps(DEFAULTS))

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    merged = json.loads(json.dumps(DEFAULTS))
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def save_config(cfg: Dict[str, Any]) -> None:
    ensure_dirs()
    p = config_path()
    with p.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def get(cfg: Dict[str, Any], path: str, default: Any = None) -> Any:
    """cfg 에서 'a.b.c' 형태로 안전하게 값을 꺼낸다."""
    node: Any = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_(cfg: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    node = cfg
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value
