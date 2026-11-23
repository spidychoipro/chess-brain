"""설정과 학습 DB의 롤링 백업.

앱을 켤 때마다 ``data/backups`` 에 사본을 하나 남긴다. 파일이 새로 생기거나
지워져도 최근 5개 안에서 되돌릴 수 있게 하는 마지막 안전망이다. 백업이
실패해도 앱 실행 자체는 막지 않는다.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core import utils

KEEP = 5
_rotated = False


def backup_dir() -> Path:
    return utils.data_dir() / "backups"


def _prune(folder: Path, pattern: str, keep: int = KEEP) -> None:
    files = sorted(folder.glob(pattern))
    for old in files[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def rotate() -> None:
    """프로세스당 한 번, 시작할 때 설정과 DB를 복사하고 오래된 걸 정리한다."""
    global _rotated
    if _rotated:
        return
    _rotated = True
    try:
        folder = backup_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        db_file = folder.parent / "app.db"
        if db_file.is_file():
            shutil.copy2(db_file, folder / f"app-{stamp}.db")
        cfg_file = utils.config_dir() / "config.json"
        if cfg_file.is_file():
            shutil.copy2(cfg_file, folder / f"config-{stamp}.json")

        _prune(folder, "app-*.db")
        _prune(folder, "config-*.json")
    except Exception:
        # 디스크가 꽉 찼거나 권한이 없어도 학습은 계속돼야 한다.
        pass


def reset_for_tests() -> None:
    """테스트에서 프로세스 플래그를 초기화할 때만 쓴다."""
    global _rotated
    _rotated = False
