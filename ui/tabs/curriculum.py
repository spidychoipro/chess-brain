"""커리큘럼 탭: 약한 테마를 찾아 훈련을 권하고, 재발 여부를 보여준다."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import curriculum
from ui import theme
from ui.widgets import ReviewDialog


class CurriculumTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.cb_source = QComboBox()
        self.cb_source.addItem("사람", "human")
        self.cb_source.addItem("봇", "bot")
        self.cb_source.addItem("전체", "both")

        self.lbl_summary = theme.label("", role="big")
        self.lbl_note = theme.label("", role="small")
        self.lbl_note.setWordWrap(True)

        self.btn_recommend = QPushButton("오늘의 추천 10문제")
        self.btn_recommend.setProperty("variant", "primary")
        self.btn_recommend.clicked.connect(lambda: self._start())

        self.btn_theme = QPushButton("선택 테마 훈련")
        self.btn_theme.setProperty("variant", "ghost")
        self.btn_theme.clicked.connect(lambda: self._start(focus=True))

        toolbar = theme.card(flat=True)
        tool = QHBoxLayout(toolbar)
        tool.setContentsMargins(14, 10, 14, 10)
        tool.addWidget(theme.label("상대", role="muted"))
        tool.addWidget(self.cb_source)
        tool.addStretch(1)
        tool.addWidget(self.btn_theme)
        tool.addWidget(self.btn_recommend)

        summary = theme.card()
        slay = QVBoxLayout(summary)
        slay.setContentsMargins(18, 16, 18, 16)
        slay.setSpacing(4)
        slay.addWidget(self.lbl_summary)
        slay.addWidget(self.lbl_note)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["테마", "실수", "복습 예정", "정답률", "최근 4주", "직전 4주"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        report = theme.card()
        rlay = QVBoxLayout(report)
        rlay.setContentsMargins(18, 14, 18, 14)
        rlay.addWidget(theme.label("재발 추적", role="h2"))
        self.lbl_report = theme.label("", role="small")
        self.lbl_report.setWordWrap(True)
        rlay.addWidget(self.lbl_report)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(theme.label("훈련 커리큘럼", role="h1"))
        layout.addWidget(toolbar)
        layout.addWidget(summary)
        layout.addWidget(theme.label("테마별 현재 상태", role="h2"))
        layout.addWidget(self.table, 1)
        layout.addWidget(report)

        self.cb_source.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def _src(self):
        source = self.cb_source.currentData()
        return None if source == "both" else source

    def _update_buttons(self):
        self.btn_theme.setEnabled(bool(self.table.selectedItems()))

    def refresh(self) -> None:
        source = self._src()
        stats = curriculum.theme_stats(source)
        trend = curriculum.recurrence(weeks=4, source=source)
        self.table.setRowCount(0)
        for s in stats:
            i = self.table.rowCount()
            self.table.insertRow(i)
            t = trend.get(s["theme"], {"recent": 0, "prior": 0})
            mastery = (
                f"{round(s['mastery'] * 100)}%" if s["mastery"] is not None else "미측정"
            )
            vals = [
                s["label"], str(s["total"]), str(s["due"]), mastery,
                str(t["recent"]), str(t["prior"]),
            ]
            for c, v in enumerate(vals):
                self.table.setItem(i, c, QTableWidgetItem(v))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        if not stats:
            self.lbl_summary.setText("아직 분류된 실수가 없습니다")
            self.lbl_note.setText(
                "홈에서 대국을 가져오고 실수 분석을 돌리면 테마가 자동으로 붙습니다."
            )
            self.lbl_report.setText("아직 측정할 기록이 없습니다.")
            self._update_buttons()
            return

        weakest = stats[0]
        due = sum(s["due"] for s in stats)
        total = sum(s["total"] for s in stats)
        mastery = (
            f"{round(weakest['mastery'] * 100)}%" if weakest["mastery"] is not None else "미측정"
        )
        self.lbl_summary.setText(
            f"가장 약한 테마: {weakest['label']} (정답률 {mastery})"
        )
        self.lbl_note.setText(
            f"분류된 실수 {total}개 · 지금 복습 {due}개. "
            "약한 테마에서 문제를 주로 뽑되 다른 테마도 섞어서 내보냅니다. "
            "이미 크게 지고 있는 국면은 카드에서 제외했습니다."
        )

        lines = []
        for s in stats:
            t = trend.get(s["theme"])
            if not t or (t["prior"] == 0 and t["recent"] == 0):
                continue
            if t["prior"] > t["recent"]:
                change = f"{t['prior']}회 → {t['recent']}회 (줄음)"
            elif t["prior"] < t["recent"]:
                change = f"{t['prior']}회 → {t['recent']}회 (늘음)"
            else:
                change = f"{t['recent']}회 (변화 없음)"
            lines.append(f"{s['label']}: {change}")
        self.lbl_report.setText(
            "\n".join(lines) if lines else
            "새 실수가 쌓이면 테마별로 직전 4주와 비교해 보여줍니다. "
            "카드에 테마가 붙은 시점부터 측정됩니다."
        )
        self._update_buttons()

    def _start(self, focus: bool = False) -> None:
        source = self._src()
        selected = None
        if focus and self.table.selectedItems():
            label = self.table.item(self.table.currentRow(), 0).text()
            selected = next(
                (k for k, v in curriculum.THEMES.items() if v == label), None
            )
        items = curriculum.recommend(limit=10, source=source, focus=selected)
        if not items:
            QMessageBox.information(
                self, "훈련 커리큘럼",
                "아직 복습할 실수가 없습니다. 먼저 실수 분석을 돌려주세요.",
            )
            return
        cfg = cfg_mod.load_config()
        ReviewDialog(
            items, "mistake",
            wrong_due_seconds=int(cfg_mod.get(cfg, "sr.wrong_due_seconds", 600) or 600),
            title="커리큘럼 훈련", parent=self,
        ).exec()
        self.refresh()
