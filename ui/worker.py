"""Run a long pipeline call on a thread so the window keeps breathing."""
from __future__ import annotations

from typing import Any, Callable, Dict

from PySide6.QtCore import QThread, Signal


class PipelineWorker(QThread):
    message = Signal(str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Dict[str, Any]], **kwargs: Any):
        super().__init__()
        self._fn = fn
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D401 - Qt entry point
        try:
            result = self._fn(on_progress=lambda m: self.message.emit(str(m)), **self._kwargs)
            self.done.emit(result or {})
        except Exception as exc:  # surface to the UI instead of dying silently
            self.failed.emit(str(exc))
