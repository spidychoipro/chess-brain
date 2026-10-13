"""chess-brain entry point.

    python main.py
    chess-brain.exe            # PyInstaller 빌드본 (더블클릭)
    chess-brain.exe --selftest # 빌드 검증용: 오프스크린으로 1.5초 띄우고 종료

Needs PySide6 + python-chess. Google Drive and Stockfish are optional and
only light up the features that use them.
"""
from __future__ import annotations

import sys


def _timing():
    """Env-guarded phase logger (CHESS_BRAIN_TIMING=1 로 켬).

    Windows GUI exe 는 stdout 이 없어서 temp 파일로 기록한다.
    """
    import os
    import tempfile
    import time
    from pathlib import Path

    if os.environ.get("CHESS_BRAIN_TIMING") != "1":
        return None
    path = Path(tempfile.gettempdir()) / "chess_brain_timing.txt"
    t0 = time.perf_counter()

    def log(label: str) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{label} {time.perf_counter() - t0:.3f}\n")

    return log


def _drive_ready() -> bool:
    """Whether the Google Drive client libs made it into this build."""
    try:
        import google.auth  # noqa: F401
        import google.auth.transport.requests  # noqa: F401
        import google_auth_oauthlib.flow  # noqa: F401
        import googleapiclient.discovery  # noqa: F401
        import googleapiclient.http  # noqa: F401
        return True
    except Exception:
        return False


def _selftest() -> int:
    """Offscreen launch check for packaged builds.

    Requires a working Qt platform plugin; the marker file proves the
    window was created and the event loop ran at least 1.5s.
    """
    import os
    import tempfile
    from pathlib import Path

    log = _timing()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from core import db
    from ui import theme
    from ui.main import MainWindow

    db.init_db()
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow()
    window.show()
    if log:
        log("selftest-shown")

    from ui.widgets import ReviewDialog

    items = db.problems_due(source=None, soft=True)
    if items:
        dialog = ReviewDialog(
            items, "problem", title="셀프테스트", parent=window
        )
        dialog.show()

    QTimer.singleShot(1500, app.quit)
    app.exec()
    if log:
        log("selftest-exec-done")
    drive_ok = _drive_ready()
    marker = Path(tempfile.gettempdir()) / "chess_brain_selftest_ok"
    marker.write_text(f"ok drive={drive_ok}", encoding="utf-8")
    try:
        print(f"selftest OK  drive={drive_ok}")
    except Exception:
        pass
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    log = _timing()

    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        print("PySide6 가 필요합니다:  pip install -r requirements.txt")
        return 1
    if log:
        log("import-pyside")

    from core import db
    from ui import theme
    from ui.main import MainWindow

    db.init_db()
    if log:
        log("db-init")

    app = QApplication(sys.argv)
    app.setApplicationName("chess-brain")
    theme.apply(app)
    window = MainWindow()
    if log:
        log("window-built")
    window.show()
    if log:
        log("shown")
    rc = app.exec()
    if log:
        log("exec-done")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())