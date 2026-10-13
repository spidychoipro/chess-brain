"""SM-2 lite spacing model.

Deliberately tiny: three grades, integer-ish intervals in days. The point
is not academic fidelity to Anki/FSRS, it is "show me the thing again right
before I forget it".
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from core.utils import now_ts

# 1 = Again (틀림), 2 = Good (맞음), 3 = Easy (쉬웠음)
GRADE_AGAIN = 1
GRADE_GOOD = 2
GRADE_EASY = 3

MIN_EASE = 1.30
MAX_EASE = 3.0


@dataclass
class SRState:
    ease: float = 2.5
    interval: float = 0.0   # days
    reps: int = 0
    lapses: int = 0
    due_at: int = 0         # unix ts
    reviewed_at: int = 0    # unix ts
    streak: int = 0
    correct: int = 0
    wrong: int = 0
    last_wrong: int = 0


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def review_state(
    state: SRState,
    grade: int,
    wrong_due_seconds: int = 600,
) -> SRState:
    """Return the next SR state for a graded review."""
    now = now_ts()
    ease = state.ease or 2.5
    interval = state.interval or 0.0
    reps = state.reps or 0

    if grade <= GRADE_AGAIN:
        # 틀림: 읽던 기억을 흔들어 놓고 곧바로 다시 만나게 한다.
        new_ease = _clamp(ease - 0.25, MIN_EASE, MAX_EASE)
        return replace(
            state,
            ease=new_ease,
            interval=1.0,
            reps=0,
            lapses=(state.lapses or 0) + 1,
            due_at=now + max(60, int(wrong_due_seconds)),
            reviewed_at=now,
            streak=0,
            wrong=(state.wrong or 0) + 1,
            last_wrong=now,
        )

    # 맞음
    if grade >= GRADE_EASY:
        ease_delta = 0.20
    else:
        ease_delta = 0.10

    if reps == 0:
        new_reps = 1
        new_interval = 1.0
        new_ease = ease
    elif reps == 1:
        new_reps = 2
        new_interval = 6.0
        new_ease = _clamp(ease + ease_delta, MIN_EASE, MAX_EASE)
    else:
        new_ease = _clamp(ease + ease_delta, MIN_EASE, MAX_EASE)
        new_reps = reps + 1
        new_interval = max(1.0, interval * new_ease)

    return replace(
        state,
        ease=new_ease,
        interval=new_interval,
        reps=new_reps,
        due_at=now + int(new_interval * 86400),
        reviewed_at=now,
        streak=(state.streak or 0) + 1,
        correct=(state.correct or 0) + 1,
    )


def is_due(row: dict, now: int | None = None) -> bool:
    now = now if now is not None else now_ts()
    due = row.get("due_at") or 0
    return 0 < due <= now
