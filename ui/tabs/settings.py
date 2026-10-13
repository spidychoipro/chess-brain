"""Settings tab: drive folder, Stockfish, thresholds, defaults."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core import config as cfg_mod
from core import drive, pipeline
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

        self.lbl_folder = QLabel("-")
        self.btn_auth = QPushButton("구글 인증 (브라우저 열기)")
        self.btn_auth.clicked.connect(self._authorize)
        self.btn_check = QPushButton("폴더 확인")
        self.btn_check.clicked.connect(self._check_folder)
        self.btn_sync = QPushButton("드라이브 동기화 (PGN → 문제)")
        self.btn_sync.clicked.connect(self._sync)

        self.in_stockfish = QLineEdit()
        self.in_stockfish.setPlaceholderText("stockfish.exe 경로 (선택)")
        self.btn_browse_sf = QPushButton("찾아보기")
        self.btn_browse_sf.clicked.connect(self._browse_stockfish)

        self.sp_depth = QSpinBox()
        self.sp_depth.setRange(4, 30)
        self.sp_threshold = QDoubleSpinBox()
        self.sp_threshold.setRange(0.1, 10.0)
        self.sp_threshold.setSingleStep(0.1)
        self.sp_threshold.setSuffix(" pawn")

        self.cb_source = QComboBox()
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Both", "both")

        self.cb_mode = QComboBox()
        self.cb_mode.addItem("다음 수 맞추기 (Recall)", "recall")
        self.cb_mode.addItem("노테이션 연습 (Drill)", "drill")

        self.btn_save = QPushButton("저장")
        self.btn_save.clicked.connect(self._save)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("동기화/분석 로그")

        sf_row = QHBoxLayout()
        sf_row.addWidget(self.in_stockfish, 1)
        sf_row.addWidget(self.btn_browse_sf)

        auth_row = QHBoxLayout()
        auth_row.addWidget(self.btn_auth)
        auth_row.addWidget(self.btn_check)
        auth_row.addWidget(self.btn_sync)

        form = QFormLayout()
        form.addRow("chess.com 아이디", self.in_username)
        form.addRow("드라이브 부모 폴더", self.in_parent)
        form.addRow("폴더 상태", self.lbl_folder)
        form.addRow("", auth_row)
        form.addRow("Stockfish", sf_row)
        form.addRow("분석 depth", self.sp_depth)
        form.addRow("실수 임계값(loss)", self.sp_threshold)
        form.addRow("트레이닝 기본 소스", self.cb_source)
        form.addRow("트레이닝 기본 모드", self.cb_mode)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.btn_save)
        layout.addWidget(QLabel("로그"))
        layout.addWidget(self.log, 1)

        self._load_into_widgets()

    # -- config <-> widgets -------------------------------------------------

    def _load_into_widgets(self) -> None:
        c = self.cfg
        self.in_username.setText(cfg_mod.get(c, "chesscom.username", "") or "")
        self.in_parent.setText(cfg_mod.get(c, "google_drive.parent_folder_id", "") or "")
        name = cfg_mod.get(c, "google_drive.parent_folder_name", "") or ""
        self.lbl_folder.setText(name or "-")
        self.in_stockfish.setText(cfg_mod.get(c, "stockfish.path", "") or "")
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
        path, _ = QFileDialog.getOpenFileName(self, "stockfish.exe 선택", "", "실행 파일 (*.exe);;모든 파일 (*)")
        if path:
            self.in_stockfish.setText(path)

    def _sync(self) -> None:
        self._save()
        self._run(pipeline.sync_drive, self.cfg)

    def _run(self, fn, cfg) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._worker = PipelineWorker(fn, cfg=cfg)
        self._worker.message.connect(self._log)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(lambda e: self._log(f"실패: {e}"))
        self.btn_sync.setEnabled(False)
        self._worker.finished.connect(lambda: self.btn_sync.setEnabled(True))
        self._worker.start()

    def _on_done(self, result: dict) -> None:
        self._log(f"완료: {result}")
        self.config_saved.emit()
