"""노테이션 학습 '진행'과 약점 가중 선택.

이전 버전은 단계마다 점수가 리셋되고 통과 기준도 없어서 퀴즈 쇼에 가까웠다.
여기서는 단계별로

  * 통과 기준(정답 수 + 정답률)을 두고
  * 항목별 정오를 저장해서 틀린 항목을 더 자주 내도록 가중치를 준다.

진행은 ``data/notation_progress.json`` 하나에 모아둔다. 앱을 껐다 켜도 남는다.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.utils import data_dir


def _default_path() -> Path:
    return data_dir() / "notation_progress.json"


def load(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or _default_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    p = path or _default_path()
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class Record:
    """한 단계의 진행 상태 + 항목 선택 가중치."""

    def __init__(
        self,
        key: str,
        goal: int = 15,
        accuracy: float = 0.8,
        path: Optional[Path] = None,
    ):
        self.key = key
        self.goal = goal
        self.accuracy_goal = accuracy
        self.path = path
        data = load(path)
        self.state: Dict[str, Any] = dict(data.get(key) or {})
        self.state.setdefault("correct", 0)
        self.state.setdefault("total", 0)
        self.state.setdefault("passed", False)
        self.state.setdefault("items", {})
        self.streak = 0

    # -- 조회 ---------------------------------------------------------------
    @property
    def correct(self) -> int:
        return int(self.state.get("correct", 0))

    @property
    def total(self) -> int:
        return int(self.state.get("total", 0))

    @property
    def passed(self) -> bool:
        return bool(self.state.get("passed", False))

    def accuracy(self) -> float:
        return (self.correct / self.total) if self.total else 0.0

    def remaining(self) -> int:
        return max(0, self.goal - self.correct)

    # -- 기록 ---------------------------------------------------------------
    def note(self, item_id: str, ok: bool) -> None:
        it = self.state["items"].setdefault(item_id, {"r": 0, "w": 0})
        it["r" if ok else "w"] += 1
        self.state["total"] = self.total + 1
        if ok:
            self.state["correct"] = self.correct + 1
            self.streak += 1
        else:
            self.streak = 0
        if (
            not self.passed
            and self.correct >= self.goal
            and self.accuracy() >= self.accuracy_goal
        ):
            self.state["passed"] = True

    def reset(self) -> None:
        self.state.clear()
        self.state.update({"correct": 0, "total": 0, "passed": False, "items": {}})
        self.streak = 0

    # -- 선택 ---------------------------------------------------------------
    def weight(self, item_id: str) -> float:
        """틀린 적 많을수록 ↑, 맞힌 적 많을수록 ↓ (바닥은 둬서 완전히 안 죽게)."""
        it = self.state["items"].get(item_id) or {}
        return max(0.4, 1.0 + 1.6 * int(it.get("w", 0)) - 0.35 * int(it.get("r", 0)))

    def pick(self, ids: List[str], exclude: Optional[str] = None) -> str:
        pool = [i for i in ids if i != exclude] or list(ids)
        weights = [self.weight(i) for i in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def flush(self) -> None:
        # 다른 단계가 먼저 저장했을 수 있으니 다시 읽고 내 키만 갈아끼운다.
        data = load(self.path)
        data[self.key] = self.state
        save(data, self.path)
