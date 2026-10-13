"""chess-brain entry point.

    python main.py
    chess-brain.exe            # PyInstaller 빌드본 (더블클릭)
    chess-brain.exe --selftest # 빌드 검증용: 오프스크린으로 1.5초 띄우고 종료

Needs PySide6 + python-chess. Google Drive and Stockfish are optional and
only light up the features that use them.
"""
from __future__ import annotations

import sys


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

    from ui.widgets import ReviewDialog

    items = db.problems_due(source=None, soft=True)
    if items:
        dialog = ReviewDialog(
            items, "problem", title="셀프테스트", parent=window
        )
        dialog.show()

    QTimer.singleShot(1500, app.quit)
    app.exec()
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

    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        print("PySide6 가 필요합니다:  pip install -r requirements.txt")
        return 1

    from core import db
    from ui import theme
    from ui.main import MainWindow

    db.init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("chess-brain")
    theme.apply(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())