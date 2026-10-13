"""Settings page: drive folder, Stockfish, thresholds, defaults."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import drive, pipeline
from core.utils import config_dir
from ui import theme
from ui.worker import PipelineWorker


class SettingsTab(QWidget):
    config_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = cfg_mod.load_config()
        self._worker = None

        self.in_username = QLineEdit()
        self.in_username.setPlaceholderText("chess.com 아이디 (내가 둔 수 판별용)")

        self.in_parent = QLineEdit()
        self.in_parent.setPlaceholderText("구글드라이브 부모 폴더 ID 또는 공유 URL")

        self.lbl_folder = theme.label("-", role="muted")
        self.btn_auth = QPushButton("구글 인증 (브라우저)")
        self.btn_auth.setProperty("variant", "ghost")
        self.btn_auth.clicked.connect(self._authorize)
        self.btn_check = QPushButton("폴더 확인")
        self.btn_check.setProperty("variant", "ghost")
        self.btn_check.clicked.connect(self._check_folder)
        self.btn_sync = QPushButton("드라이브 동기화")
        self.btn_sync.setProperty("variant", "primary")
        self.btn_sync.clicked.connect(self._sync)

        drive_actions = QHBoxLayout()
        drive_actions.addWidget(self.btn_auth)
        drive_actions.addWidget(self.btn_check)
        drive_actions.addWidget(self.btn_sync)
        drive_actions.addStretch(1)

        drive_form = QFormLayout()
        drive_form.addRow(theme.label("chess.com 아이디", role="muted"), self.in_username)
        drive_form.addRow(theme.label("부모 폴더", role="muted"), self.in_parent)
        drive_form.addRow(theme.label("폴더 상태", role="muted"), self.lbl_folder)
        drive_form.addRow("", drive_actions)

        card_drive = theme.card()
        cd = QVBoxLayout(card_drive)
        cd.setContentsMargins(18, 16, 18, 16)
        cd.setSpacing(10)
        cd.addWidget(theme.label("구글드라이브 (선택·무료)", role="h2"))
        cd.addLayout(drive_form)

        # -- local folder (API 없음 = 돈 안 듦) -------------------------------
        self.in_local = QLineEdit()
        self.in_local.setPlaceholderText("PGN 게임 폴더 (예: C:\\chess\\games)")
        self.btn_browse_local = QPushButton("폴더 선택")
        self.btn_browse_local.setProperty("variant", "ghost")
        self.btn_browse_local.clicked.connect(self._browse_local)
        self.lbl_local = theme.label(
            "하위폴더 이름(Bot / Human)으로 봇전·사람전을 자동 구분. 구글·API·비용 없음.",
            role="muted",
        )
        self.btn_local_sync = QPushButton("로컬 동기화")
        self.btn_local_sync.setProperty("variant", "primary")
        self.btn_local_sync.clicked.connect(self._sync_local)

        local_row = QHBoxLayout()
        local_row.addWidget(self.in_local, 1)
        local_row.addWidget(self.btn_browse_local)
        local_actions = QHBoxLayout()
        local_actions.addWidget(self.btn_local_sync)
        local_actions.addStretch(1)

        card_local = theme.card()
        cl = QVBoxLayout(card_local)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)
        cl.addWidget(theme.label("로컬 PGN 폴더 (무료·API 없음)", role="h2"))
        cl.addWidget(self.lbl_local)
        cl.addLayout(local_row)
        cl.addLayout(local_actions)

        # -- stockfish -------------------------------------------------------
        self.in_stockfish = QLineEdit()
        self.in_stockfish.setPlaceholderText("stockfish.exe 경로 (선택)")
        self.btn_browse_sf = QPushButton("찾아보기")
        self.btn_browse_sf.setProperty("variant", "ghost")
        self.btn_browse_sf.clicked.connect(self._browse_stockfish)

        sf_row = QHBoxLayout()
        sf_row.addWidget(self.in_stockfish, 1)
        sf_row.addWidget(self.btn_browse_sf)

        self.sp_depth = QSpinBox()
        self.sp_depth.setRange(4, 30)
        self.sp_threshold = QDoubleSpinBox()
        self.sp_threshold.setRange(0.1, 10.0)
        self.sp_threshold.setSingleStep(0.1)
        self.sp_threshold.setSuffix(" pawn")

        sf_form = QFormLayout()
        sf_form.addRow(theme.label("Stockfish 경로", role="muted"), sf_row)
        sf_form.addRow(theme.label("분석 depth", role="muted"), self.sp_depth)
        sf_form.addRow(theme.label("실수 임계값(loss)", role="muted"), self.sp_threshold)

        card_sf = theme.card()
        cs = QVBoxLayout(card_sf)
        cs.setContentsMargins(18, 16, 18, 16)
        cs.setSpacing(10)
        cs.addWidget(theme.label("Stockfish (옵션)", role="h2"))
        cs.addLayout(sf_form)

        # -- defaults --------------------------------------------------------
        self.cb_source = QComboBox()
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Both", "both")
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("다음 수 맞추기 (Recall)", "recall")
        self.cb_mode.addItem("노테이션 연습 (Drill)", "drill")

        df = QFormLayout()
        df.addRow(theme.label("트레이닝 기본 소스", role="muted"), self.cb_source)
        df.addRow(theme.label("트레이닝 기본 모드", role="muted"), self.cb_mode)

        card_defaults = theme.card()
        cd2 = QVBoxLayout(card_defaults)
        cd2.setContentsMargins(18, 16, 18, 16)
        cd2.setSpacing(10)
        cd2.addWidget(theme.label("기본값", role="h2"))
        cd2.addLayout(df)

        self.btn_save = QPushButton("설정 저장")
        self.btn_save.setProperty("variant", "primary")
        self.btn_save.clicked.connect(self._save)

        self.log = QPlainTextEdit()
        self.log.setPlaceholderText("동기화/분석 로그")
        self.log.setMinimumHeight(140)

        # 긴 설정 폼이 작은 창에서 잘리지 않도록 스크롤 영역으로 감싼다
        content = QWidget()
        content.setObjectName("SettingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)
        layout.addWidget(card_local)
        layout.addWidget(card_drive)
        layout.addWidget(card_sf)
        layout.addWidget(card_defaults)
        layout.addWidget(self.btn_save)
        layout.addWidget(theme.label("로그", role="caption"))
        layout.addWidget(self.log, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 16, 20)
        outer.setSpacing(14)
        outer.addWidget(theme.label("설정", role="h1"))
        outer.addWidget(scroll, 1)

        self._load_into_widgets()

    # -- config <-> widgets -------------------------------------------------

    def _load_into_widgets(self) -> None:
        c = self.cfg
        self.in_username.setText(cfg_mod.get(c, "chesscom.username", "") or "")
        self.in_parent.setText(cfg_mod.get(c, "google_drive.parent_folder_id", "") or "")
        name = cfg_mod.get(c, "google_drive.parent_folder_name", "") or ""
        self.lbl_folder.setText(name or "-")
        self.in_stockfish.setText(cfg_mod.get(c, "stockfish.path", "") or "")
        self.in_local.setText(cfg_mod.get(c, "local.pgn_folder", "") or "")
        self.sp_depth.setValue(int(cfg_mod.get(c, "stockfish.depth", 12) or 12))
        self.sp_threshold.setValue(float(cfg_mod.get(c, "mistakes.loss_threshold", 0.80) or 0.80))
        idx = self.cb_source.findData(cfg_mod.get(c, "training.default_source", "bot"))
        self.cb_source.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.cb_mode.findData(cfg_mod.get(c, "training.default_mode", "recall"))
        self.cb_mode.setCurrentIndex(idx if idx >= 0 else 0)

    def _collect(self) -> None:
        self.cfg = cfg_mod.load_config()
        cfg_mod.set_(self.cfg, "chesscom.username", self.in_username.text().strip())
        cfg_mod.set_(self.cfg, "google_drive.parent_folder_id", self.in_parent.text().strip())
        cfg_mod.set_(self.cfg, "local.pgn_folder", self.in_local.text().strip())
        cfg_mod.set_(self.cfg, "stockfish.path", self.in_stockfish.text().strip())
        cfg_mod.set_(self.cfg, "stockfish.depth", int(self.sp_depth.value()))
        cfg_mod.set_(self.cfg, "mistakes.loss_threshold", float(self.sp_threshold.value()))
        cfg_mod.set_(self.cfg, "training.default_source", self.cb_source.currentData())
        cfg_mod.set_(self.cfg, "training.default_mode", self.cb_mode.currentData())

    def _save(self) -> None:
        self._collect()
        cfg_mod.save_config(self.cfg)
        self._log("저장 완료.")
        self.config_saved.emit()

    # -- actions ------------------------------------------------------------

    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    def _authorize(self) -> None:
        try:
            drive.build_service(interactive=True)
            self._log("구글 인증 완료. config/token.json 생성됨.")
        except ModuleNotFoundError as exc:
            self._log(
                f"구글 드라이브 라이브러리가 없음: {exc}\n"
                "pip install -r requirements.txt 후 exe 재빌드(build.ps1) 필요."
            )
        except FileNotFoundError as exc:
            self._log(
                f"{exc}\n"
                f"credentials.json 은 여기 둬야 함: {config_dir() / 'credentials.json'}"
            )
        except Exception as exc:
            self._log(f"인증 실패: {exc}")

    def _check_folder(self) -> None:
        self._collect()
        try:
            service = drive.build_service(interactive=False)
            if service is None:
                self._log("먼저 구글 인증이 필요합니다.")
                return
            fid = drive.resolve_folder_id(service, self.in_parent.text())
            info = drive.get_folder(service, fid)
            if not info:
                self._log("폴더를 찾을 수 없습니다.")
                return
            self.lbl_folder.setText(info["name"])
            cfg_mod.set_(self.cfg, "google_drive.parent_folder_name", info["name"])
            cfg_mod.save_config(self.cfg)
            self._log(f"폴더 확인: {info['name']}")
        except Exception as exc:
            self._log(f"폴더 확인 실패: {exc}")

    def _browse_stockfish(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "stockfish.exe 선택", "", "실행 파일 (*.exe);;모든 파일 (*)"
        )
        if path:
            self.in_stockfish.setText(path)

    def _browse_local(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "PGN 게임 폴더 선택")
        if path:
            self.in_local.setText(path)
            self._save()

    def _sync_local(self) -> None:
        self._save()
        if not self.in_local.text().strip():
            self._log("먼저 로컬 PGN 폴더를 선택하세요.")
            return
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._worker = PipelineWorker(pipeline.sync_local_folder, cfg=self.cfg)
        self._worker.message.connect(self._log)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(lambda e: self._log(f"실패: {e}"))
        self.btn_local_sync.setEnabled(False)
        self._worker.finished.connect(lambda: self.btn_local_sync.setEnabled(True))
        self._worker.start()

    def _sync(self) -> None:
        self._save()
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._worker = PipelineWorker(pipeline.sync_drive, cfg=self.cfg)
        self._worker.message.connect(self._log)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(lambda e: self._log(f"실패: {e}"))
        self.btn_sync.setEnabled(False)
        self._worker.finished.connect(lambda: self.btn_sync.setEnabled(True))
        self._worker.start()

    def _on_done(self, result: dict) -> None:
        self._log(f"완료: {result}")
        self.config_saved.emit()