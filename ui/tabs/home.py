"""Home tab: the two numbers that matter today, nothing more."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from core import db


class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lbl = QLabel()
        self.lbl.setTextFormat(Qt.RichText)
        self.btn = QPushButton("새로고침")
        self.btn.clicked.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h2>오늘 할 일</h2>"))
        layout.addWidget(self.lbl)
        layout.addWidget(self.btn)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        mc = db.mistake_counts()
        pc = db.problem_counts()
        today = db.today_review_counts()
        self.lbl.setText(
            f"<p style='font-size:16px'>"
            f"복습할 실수(due): <b>{mc['due']}</b><br>"
            f"복습할 노테이션(due): <b>{pc['due']}</b><br>"
            f"아직 안 본 실수: <b>{mc['unreviewed']}</b><br>"
            f"오늘 복습한 항목: <b>{today['total']}</b> "
            f"(실수 {today['mistakes']} · 문제 {today['problems']})"
            f"</p>"
        )
