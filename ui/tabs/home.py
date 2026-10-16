"""Home page: the numbers that matter today, on cards."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from core import db
from ui import theme


def _stat_card(big: str, caption: str) -> QWidget:
    card = theme.card()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(4)
    lay.addWidget(theme.label(big, role="big"))
    lay.addWidget(theme.label(caption, role="caption"))
    return card


class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.card_due_m = _stat_card("-", "복습할 실수 (due)")
        self.card_due_p = _stat_card("-", "복습할 문제 (due)")
        self.card_new = _stat_card("-", "아직 안 본 실수")
        self.card_today = _stat_card("-", "오늘 복습한 항목")

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.addWidget(self.card_due_m, 0, 0)
        grid.addWidget(self.card_due_p, 0, 1)
        grid.addWidget(self.card_new, 1, 0)
        grid.addWidget(self.card_today, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # 지금 해야 할 일을 맨 위에 한 줄로 크게 보여준다.
        self.lbl_now = theme.label("", role="h2")
        self.lbl_now.setWordWrap(True)

        intro = theme.label(
            "틀린 실수일수록 더 자주, 잊어버리기 직전에 다시 만나는 앱. \n"
            "왼쪽 '내 실수' 탭부터 시작하면 됨.",
        )
        intro.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("홈", role="h1"))
        layout.addWidget(self.lbl_now)
        layout.addLayout(grid)
        layout.addWidget(intro)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        mc = db.mistake_counts()
        pc = db.problem_counts()
        today = db.today_review_counts()
        self._set_number(self.card_due_m, str(mc["due"]))
        self._set_number(self.card_due_p, str(pc["due"]))
        self._set_number(self.card_new, str(mc["unreviewed"]))
        self._set_number(self.card_today, str(today["total"]))

        # 복습할 게 있으면 그 카드를 강조하고 안내 문구도 바꾼다.
        due = mc["due"]
        if due > 0:
            theme.set_state(self.card_due_m, "primary")
            self.lbl_now.setText(f"지금 복습할 실수 {due}개 — '내 실수' 탭에서 바로 시작")
            theme.set_state(self.lbl_now, "accent")
        else:
            theme.set_state(self.card_due_m, "")
            self.lbl_now.setText("지금 할 복습은 없어. 새 게임을 동기화하거나 기보 트레이닝을 해봐.")
            theme.set_state(self.lbl_now, "muted")

    def _set_number(self, card: QWidget, value: str) -> None:
        for child in card.findChildren(QWidget):
            if child.property("role") == "big":
                child.setText(value)
                return
