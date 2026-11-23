"""Run a long pipeline call on a thread so the window keeps breathing."""
from __future__ import annotations

from typing import Any, Callable, Dict

from PySide6.QtCore import QThread, Signal


class PipelineWorker(QThread):
    message = Signal(str)
    progressed = Signal(int, int, str)  # 현재, 전체, 설명
    done = Signal(dict)
    failed = Signal(str)
    ended = Signal(str)  # done / cancelled / failed — 상태 라벨 정리용

    def __init__(self, fn: Callable[..., Dict[str, Any]], **kwargs: Any):
        super().__init__()
        self._fn = fn
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D401 - Qt entry point
        def report(value):
            if self.isInterruptionRequested():
                raise InterruptedError("작업이 중단되었습니다.")
            if isinstance(value, dict):
                done = int(value.get("done", 0) or 0)
                total = int(value.get("total", 0) or 0)
                text = str(value.get("message", "") or "")
                self.progressed.emit(done, total, text)
            else:
                text = str(value)
            self.message.emit(text)

        try:
            if self.isInterruptionRequested():
                raise InterruptedError("작업이 중단되었습니다.")
            report("작업을 시작합니다…")
            result = self._fn(on_progress=report, **self._kwargs)
            if self.isInterruptionRequested():
                raise InterruptedError("작업이 중단되었습니다.")
            self.done.emit(result or {})
            self.ended.emit("done")
        except InterruptedError:
            self.ended.emit("cancelled")
        except Exception as exc:  # surface to the UI instead of dying silently
            self.failed.emit(str(exc))
            self.ended.emit("failed")
