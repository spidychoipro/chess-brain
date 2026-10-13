"""chess-brain entry point.

    python main.py

Needs PySide6 + python-chess. Google Drive and Stockfish are optional and
only light up the features that use them.
"""
from __future__ import annotations

import sys


def main() -> int:
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
