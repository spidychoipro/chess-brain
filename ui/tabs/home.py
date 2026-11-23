"""Home page: today's work, one-click actions and a first-run checklist."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from core import config as cfg_mod
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


def _step_row(number: str, text: str, button: QPushButton) -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    mark = theme.label(number, role="h2")
    label = theme.label(text, role="muted")
    label.setWordWrap(True)
    lay.addWidget(mark, 0)
    lay.addWidget(label, 1)
    lay.addWidget(button, 0)
    row.mark = mark
    row.text_label = label
    row.button = button
    row.number = number
    return row


class HomeTab(QWidget):
    openReview = Signal()
    openImport = Signal()
    openSetup = Signal(str)
    analyze = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl_now = theme.label("", role="h2")
        self.lbl_now.setWordWrap(True)

        self.btn_review = QPushButton("복습 시작")
        self.btn_review.setProperty("variant", "primary")
        self.btn_review.setToolTip("복습할 시간이 된 실수와 새 실수를 풉니다.")
        self.btn_import = QPushButton("대국 가져오기")
        self.btn_import.setToolTip("지정한 PGN 폴더에서 새 대국을 읽습니다.")
        self.btn_human = QPushButton("사람전 분석")
        self.btn_bot = QPushButton("봇전 분석")
        self.btn_all = QPushButton("전체 분석")
        for button in (self.btn_human, self.btn_bot, self.btn_all):
            button.setProperty("variant", "ghost")
        self.btn_human.setToolTip("사람과 둔 대국만 Stockfish로 분석합니다.")
        self.btn_bot.setToolTip("봇과 둔 대국만 Stockfish로 분석합니다.")
        self.btn_all.setToolTip("아직 분석하지 않은 모든 대국을 분석합니다.")

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.btn_review)
        actions.addWidget(self.btn_import)
        actions.addStretch(1)
        actions.addWidget(self.btn_human)
        actions.addWidget(self.btn_bot)
        actions.addWidget(self.btn_all)

        self.card_due_m = _stat_card("-", "복습할 실수")
        self.card_due_p = _stat_card("-", "복습할 기보 문제")
        self.card_new = _stat_card("-", "아직 안 본 실수")
        self.card_today = _stat_card("-", "오늘 푼 항목")

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.addWidget(self.card_due_m, 0, 0)
        grid.addWidget(self.card_due_p, 0, 1)
        grid.addWidget(self.card_new, 1, 0)
        grid.addWidget(self.card_today, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        # 첫 실행 때만 보이는 안내. 설정이 채워지면 저절로 사라진다.
        self.setup_card = theme.card()
        setup = QVBoxLayout(self.setup_card)
        setup.setContentsMargins(18, 16, 18, 16)
        setup.setSpacing(10)
        setup.addWidget(theme.label("처음 시작하기", role="h2"))
        setup.addWidget(
            theme.label(
                "아래 세 가지만 준비하면 복습과 분석이 바로 돼요. 끝난 항목은 초록으로 표시됩니다.",
                role="muted",
            )
        )
        self.btn_setup_pgn = QPushButton("폴더 선택")
        self.btn_setup_sf = QPushButton("찾아보기")
        self.btn_setup_import = QPushButton("가져오기")
        for button in (self.btn_setup_pgn, self.btn_setup_sf, self.btn_setup_import):
            button.setProperty("variant", "ghost")
        self._setup_rows = [
            _step_row("1", "PGN 폴더 지정", self.btn_setup_pgn),
            _step_row("2", "Stockfish 경로", self.btn_setup_sf),
            _step_row("3", "대국 가져오기", self.btn_setup_import),
        ]
        for row in self._setup_rows:
            setup.addWidget(row)

        self.lbl_empty = theme.label("", role="empty")
        self.lbl_empty.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("홈", role="h1"))
        layout.addWidget(self.lbl_now)
        layout.addLayout(actions)
        layout.addLayout(grid)
        layout.addWidget(self.setup_card)
        layout.addWidget(self.lbl_empty)
        layout.addStretch(1)

        self.btn_review.clicked.connect(self.openReview.emit)
        self.btn_import.clicked.connect(self.openImport.emit)
        self.btn_human.clicked.connect(lambda: self.analyze.emit("human"))
        self.btn_bot.clicked.connect(lambda: self.analyze.emit("bot"))
        self.btn_all.clicked.connect(lambda: self.analyze.emit("both"))
        self.btn_setup_pgn.clicked.connect(lambda: self.openSetup.emit("pgn"))
        self.btn_setup_sf.clicked.connect(lambda: self.openSetup.emit("stockfish"))
        self.btn_setup_import.clicked.connect(self.openImport.emit)

        self.refresh()

    def refresh(self) -> None:
        cfg = cfg_mod.load_config()
        mc = db.mistake_counts()
        pc = db.problem_counts()
        today = db.today_review_counts()
        games = db.game_counts()
        self._set_number(self.card_due_m, str(mc["due"]))
        self._set_number(self.card_due_p, str(pc["due"]))
        self._set_number(self.card_new, str(mc["unreviewed"]))
        self._set_number(self.card_today, str(today["total"]))

        if not games["total"]:
            self.lbl_now.setText("아직 가져온 대국이 없어요. '대국 가져오기'부터 눌러보세요.")
            theme.set_state(self.lbl_now, "accent")
        elif mc["due"]:
            self.lbl_now.setText(f"복습할 실수 {mc['due']}개가 있어요. '복습 시작'을 눌러보세요.")
            theme.set_state(self.lbl_now, "accent")
        elif mc["unreviewed"]:
            self.lbl_now.setText(f"새 실수 {mc['unreviewed']}개가 쌓였어요. 한 번 풀어보세요.")
            theme.set_state(self.lbl_now, "accent")
        else:
            self.lbl_now.setText("오늘 할 복습은 없어요. 새 대국을 가져오거나 분석해 보세요.")
            theme.set_state(self.lbl_now, "muted")

        steps = {
            "pgn": bool(cfg_mod.get(cfg, "local.pgn_folder", "") or ""),
            "stockfish": bool(cfg_mod.get(cfg, "stockfish.path", "") or ""),
            "import": games["total"] > 0,
        }
        for row, key in zip(self._setup_rows, ("pgn", "stockfish", "import")):
            is_done = steps[key]
            row.mark.setText("✓" if is_done else row.number)
            theme.set_state(row.mark, "success" if is_done else "")
            theme.set_state(row.text_label, "success" if is_done else "")
            row.button.setVisible(not is_done)
        self.setup_card.setVisible(not all(steps.values()))

        if not games["total"]:
            self.lbl_empty.setText(
                "PGN 폴더가 지정돼 있으면 가져오기만 눌러도 대국이 채워져요. "
                "경로는 '설정'에서 확인할 수 있어요."
            )
            self.lbl_empty.show()
        elif not mc["total"] and not pc["total"]:
            self.lbl_empty.setText(
                "대국은 있지만 실수가 없어요. Stockfish 경로를 확인하고 "
                "'사람전 분석' 또는 '봇전 분석'을 눌러보세요."
            )
            self.lbl_empty.show()
        else:
            self.lbl_empty.hide()

    def _set_number(self, card: QWidget, value: str) -> None:
        for child in card.findChildren(QWidget):
            if child.property("role") == "big":
                child.setText(value)
                return
