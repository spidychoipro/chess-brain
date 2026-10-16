"""Settings page: drive folder, Stockfish, thresholds, defaults."""

from __future__ import annotations

import os

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
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
from core import drive
from core import rclone as rclone_mod
from ui import theme
from ui.widgets import collapsible_help
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

        self.in_api_key = QLineEdit()
        self.in_api_key.setPlaceholderText(
            "API 키 (폴더를 '링크가 있는 모든 사용자'로 공유한 경우 · 로그인 불필요)"
        )
        self.in_api_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.lbl_folder = theme.label("-", role="muted")
        self.btn_cred = QPushButton("credentials.json 선택")
        self.btn_cred.setProperty("variant", "ghost")
        self.btn_cred.clicked.connect(self._pick_credentials)
        self.btn_auth = QPushButton("구글 인증 (브라우저)")
        self.btn_auth.setProperty("variant", "ghost")
        self.btn_auth.clicked.connect(self._authorize)
        self.btn_check = QPushButton("폴더 확인")
        self.btn_check.setProperty("variant", "ghost")
        self.btn_check.clicked.connect(self._check_folder)
        self.btn_sync = QPushButton("드라이브 동기화")
        self.btn_sync.setProperty("variant", "primary")
        self.btn_sync.clicked.connect(self._sync)
        self.btn_pull = QPushButton("드라이브 → 로컬로 받기")
        self.btn_pull.setProperty("variant", "primary")
        self.btn_pull.clicked.connect(self._pull_drive)

        drive_actions = QHBoxLayout()
        drive_actions.addWidget(self.btn_cred)
        drive_actions.addWidget(self.btn_auth)
        drive_actions.addWidget(self.btn_check)
        drive_actions.addStretch(1)
        drive_actions2 = QHBoxLayout()
        drive_actions2.addWidget(self.btn_pull)
        drive_actions2.addWidget(self.btn_sync)
        drive_actions2.addStretch(1)

        drive_form = QFormLayout()
        drive_form.addRow(theme.label("chess.com 아이디", role="muted"), self.in_username)
        drive_form.addRow(theme.label("부모 폴더", role="muted"), self.in_parent)
        drive_form.addRow(theme.label("API 키", role="muted"), self.in_api_key)
        drive_form.addRow(theme.label("폴더 상태", role="muted"), self.lbl_folder)
        drive_form.addRow("", drive_actions)
        drive_form.addRow("", drive_actions2)

        self.lbl_drive_help = collapsible_help(
            "가장 쉬운 길 (API 키): 드라이브에서 부모 폴더 우클릭 → 공유 → "
            "'링크가 있는 모든 사용자 · 뷰어' 로 바꾸고, Cloud Console 에서 API 키 하나만 "
            "발급(동의화면 불필요)해 위 'API 키' 칸에 붙여넣기 → '드라이브 → 로컬로 받기'.\n"
            "비공개로 쓰려면: OAuth 클라이언트(데스크톱 앱) json 을 'credentials.json 선택' "
            "으로 고르고 '구글 인증' (브라우저 로그인).\n"
            "받아둔 파일은 '로컬 PGN 폴더'에 저장되며, 이후에는 '로컬 동기화' 만 돌려도 됨."
        )

        card_drive = theme.card()
        cd = QVBoxLayout(card_drive)
        cd.setContentsMargins(18, 16, 18, 16)
        cd.setSpacing(10)
        cd.addWidget(theme.label("구글드라이브 (선택·무료)", role="h2"))
        cd.addLayout(drive_form)
        cd.addWidget(self.lbl_drive_help)

        # -- local folder (API 없음 = 돈 안 듦) -------------------------------
        self.in_local = QLineEdit()
        self.in_local.setPlaceholderText("PGN 게임 폴더 (예: C:\\chess\\games)")
        self.btn_browse_local = QPushButton("폴더 선택")
        self.btn_browse_local.setProperty("variant", "ghost")
        self.btn_browse_local.clicked.connect(self._browse_local)
        self.lbl_local = collapsible_help(
            "하위폴더 이름(Bot / Human)으로 봇전·사람전을 자동 구분. 구글·API·비용 없음.\n"
            "드라이브에 있는 PGN을 쓰려면: (1) 드라이브에서 폴더를 zip 으로 받아 여기에 풀기, "
            "또는 (2) Google Drive for Desktop 을 설치해 나타나는 로컬 경로를 여기 지정. "
            "둘 다 구글 인증(credentials.json)이 필요 없음."
        )
        self.btn_local_sync = QPushButton("로컬 동기화")
        self.btn_local_sync.setProperty("variant", "primary")
        self.btn_local_sync.clicked.connect(self._sync_local)
        self.btn_open_local = QPushButton("폴더 열기")
        self.btn_open_local.setProperty("variant", "ghost")
        self.btn_open_local.clicked.connect(self._open_local)

        local_row = QHBoxLayout()
        local_row.addWidget(self.in_local, 1)
        local_row.addWidget(self.btn_browse_local)
        local_actions = QHBoxLayout()
        local_actions.addWidget(self.btn_local_sync)
        local_actions.addWidget(self.btn_open_local)
        local_actions.addStretch(1)

        card_local = theme.card()
        cl = QVBoxLayout(card_local)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)
        cl.addWidget(theme.label("로컬 PGN 폴더 (무료·API 없음)", role="h2"))
        cl.addWidget(self.lbl_local)
        cl.addLayout(local_row)
        cl.addLayout(local_actions)

        # -- rclone (구글 인증은 rclone 이 담당 = 앱은 설정 필요 없음) ---------
        self.in_rclone_remote = QLineEdit()
        self.in_rclone_remote.setPlaceholderText("rclone 원격 경로 (예: gdrive:chess-brian)")
        self.in_rclone_bin = QLineEdit()
        self.in_rclone_bin.setPlaceholderText("rclone.exe 경로 (비우면 PATH 자동 탐색)")
        self.btn_rclone_bin = QPushButton("찾아보기")
        self.btn_rclone_bin.setProperty("variant", "ghost")
        self.btn_rclone_bin.clicked.connect(self._browse_rclone)
        self.in_rclone_conf = QLineEdit()
        self.in_rclone_conf.setPlaceholderText("rclone.conf 경로 (비우면 기본 위치)")
        self.btn_rclone_conf = QPushButton("찾아보기")
        self.btn_rclone_conf.setProperty("variant", "ghost")
        self.btn_rclone_conf.clicked.connect(self._browse_rclone_conf)
        self.btn_rclone = QPushButton("rclone 으로 받기")
        self.btn_rclone.setProperty("variant", "primary")
        self.btn_rclone.clicked.connect(self._pull_rclone)

        # mount: 드라이브를 로컬 드라이브 문자로 붙인다(복사 없이 실시간)
        self.in_mount_point = QLineEdit()
        self.in_mount_point.setPlaceholderText("붙일 드라이브 문자 (예: X:)")
        self.btn_mount = QPushButton("드라이브 마운트")
        self.btn_mount.setProperty("variant", "primary")
        self.btn_mount.clicked.connect(self._mount_drive)
        self.btn_unmount = QPushButton("마운트 해제")
        self.btn_unmount.setProperty("variant", "ghost")
        self.btn_unmount.clicked.connect(self._unmount_drive)
        self.btn_use_mount = QPushButton("마운트 폴더를 로컬 PGN 폴더로")
        self.btn_use_mount.setProperty("variant", "ghost")
        self.btn_use_mount.clicked.connect(self._use_mount_as_local)
        self.lbl_mount = theme.label("-", role="muted")

        rclone_bin_row = QHBoxLayout()
        rclone_bin_row.addWidget(self.in_rclone_bin, 1)
        rclone_bin_row.addWidget(self.btn_rclone_bin)
        rclone_conf_row = QHBoxLayout()
        rclone_conf_row.addWidget(self.in_rclone_conf, 1)
        rclone_conf_row.addWidget(self.btn_rclone_conf)
        mount_actions = QHBoxLayout()
        mount_actions.addWidget(self.btn_mount)
        mount_actions.addWidget(self.btn_unmount)
        mount_actions.addWidget(self.btn_use_mount)
        mount_actions.addStretch(1)
        rclone_form = QFormLayout()
        rclone_form.addRow(theme.label("rclone 원격", role="muted"), self.in_rclone_remote)
        rclone_form.addRow(theme.label("rclone.exe", role="muted"), rclone_bin_row)
        rclone_form.addRow(theme.label("rclone.conf", role="muted"), rclone_conf_row)
        rclone_form.addRow(theme.label("드라이브 문자", role="muted"), self.in_mount_point)
        rclone_form.addRow(theme.label("마운트 상태", role="muted"), self.lbl_mount)
        rclone_form.addRow("", self.btn_rclone)
        rclone_form.addRow("", mount_actions)
        self.lbl_rclone = collapsible_help(
            "rclone 을 쓰면 앱에 구글 API 키/OAuth 가 전혀 필요 없다(rclone 이 인증을 들고 있음). "
            "rclone.conf 를 기본 위치가 아닌 곳에 뒀으면 그 경로도 넣는다(예: "
            "C:\\Users\\<나>\\.config\\chesspgn-auto\\rclone.conf).\n"
            "① 'rclone 으로 받기': .pgn 을 '로컬 PGN 폴더'로 복사한 뒤 바로 동기화(인터넷 없이도 이후 읽힘).\n"
            "② '드라이브 마운트': 드라이브를 로컬 드라이브 문자(예: X:)로 붙인다. 복사가 필요 없어 늘 최신이지만 "
            "Windows 는 WinFsp 가 있어야 하고, 붙인 드라이브 문자를 '로컬 PGN 폴더'로 쓰면 된다."
        )

        card_rclone = theme.card()
        cr = QVBoxLayout(card_rclone)
        cr.setContentsMargins(18, 16, 18, 16)
        cr.setSpacing(10)
        cr.addWidget(theme.label("rclone (선택·구글 설정 불필요)", role="h2"))
        cr.addWidget(self.lbl_rclone)
        cr.addLayout(rclone_form)

        # -- stockfish -------------------------------------------------------
        self.in_stockfish = QLineEdit()
        self.in_stockfish.setPlaceholderText("stockfish.exe 경로 (선택)")
        self.btn_detect_sf = QPushButton("자동 감지")
        self.btn_detect_sf.setProperty("variant", "ghost")
        self.btn_detect_sf.clicked.connect(self._detect_stockfish)
        self.btn_browse_sf = QPushButton("찾아보기")
        self.btn_browse_sf.setProperty("variant", "ghost")
        self.btn_browse_sf.clicked.connect(self._browse_stockfish)

        sf_row = QHBoxLayout()
        sf_row.addWidget(self.in_stockfish, 1)
        sf_row.addWidget(self.btn_detect_sf)
        sf_row.addWidget(self.btn_browse_sf)

        self.sp_depth = QSpinBox()
        # 예전엔 4..30 이었는데 27 같은 값이 들어가면 분석이 사실상 안 끝난다.
        self.sp_depth.setRange(6, 16)
        self.sp_threshold = QDoubleSpinBox()
        self.sp_threshold.setRange(0.1, 10.0)
        self.sp_threshold.setSingleStep(0.1)
        self.sp_threshold.setSuffix(" pawn")

        sf_form = QFormLayout()
        sf_form.addRow(theme.label("Stockfish 경로", role="muted"), sf_row)
        sf_form.addRow(theme.label("분석 depth", role="muted"), self.sp_depth)
        sf_form.addRow(
            "",
            theme.label(
                "낮을수록 빠름 · 12 권장. 16은 확실히 더 느리다(한 판에 수 분).",
                role="small",
            ),
        )
        sf_form.addRow(theme.label("실수 임계값(loss)", role="muted"), self.sp_threshold)

        self.lbl_sf = collapsible_help(
            "Stockfish 는 '내 실수' 분석에만 쓰인다(없어도 기보 트레이닝은 됨).\n"
            "'자동 감지' 를 누르면 PATH·앱 옆·흔한 설치 위치에서 stockfish*.exe 를 찾아 채워준다. "
            "없으면 stockfishchess.org 에서 받아 아무 폴더에 풀고 '찾아보기' 로 지정하면 된다."
        )

        card_sf = theme.card()
        cs = QVBoxLayout(card_sf)
        cs.setContentsMargins(18, 16, 18, 16)
        cs.setSpacing(10)
        cs.addWidget(theme.label("Stockfish (옵션)", role="h2"))
        cs.addWidget(self.lbl_sf)
        cs.addLayout(sf_form)

        # -- defaults --------------------------------------------------------
        self.cb_source = QComboBox()
        self.cb_source.addItem("Bot", "bot")
        self.cb_source.addItem("Human", "human")
        self.cb_source.addItem("Both", "both")
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("다음 수 맞추기 (Recall)", "recall")
        self.cb_mode.addItem("실수 집중 훈련 (Drill)", "drill")

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
        layout.addWidget(card_rclone)
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
        # 눌러도 됐는지 안 됐는지 모르겠다는 문제가 있어서, 마지막 동작 결과를
        # 제목 아래에 항상 남긴다(로그까지 안 내려가도 보이게).
        self.lbl_status = theme.label("준비됨.", role="muted")
        self.lbl_status.setWordWrap(True)
        outer.addWidget(self.lbl_status)
        outer.addWidget(scroll, 1)

        self._load_into_widgets()

    # -- config <-> widgets -------------------------------------------------

    def refresh(self) -> None:
        """탭에 들어올 때마다 마운트 상태를 실제와 맞춘다."""
        self._refresh_mount_status()

    def _load_into_widgets(self) -> None:
        c = self.cfg
        self.in_username.setText(cfg_mod.get(c, "chesscom.username", "") or "")
        self.in_parent.setText(cfg_mod.get(c, "google_drive.parent_folder_id", "") or "")
        self.in_api_key.setText(cfg_mod.get(c, "google_drive.api_key", "") or "")
        name = cfg_mod.get(c, "google_drive.parent_folder_name", "") or ""
        self.lbl_folder.setText(name or "-")
        self.in_stockfish.setText(cfg_mod.get(c, "stockfish.path", "") or "")
        self.in_local.setText(cfg_mod.get(c, "local.pgn_folder", "") or "")
        self.in_rclone_remote.setText(cfg_mod.get(c, "rclone.remote", "") or "")
        self.in_rclone_bin.setText(cfg_mod.get(c, "rclone.binary", "") or "")
        self.in_rclone_conf.setText(cfg_mod.get(c, "rclone.config", "") or "")
        self.in_mount_point.setText(cfg_mod.get(c, "rclone.mount_point", "") or "")
        self.sp_depth.setValue(max(6, min(16, int(cfg_mod.get(c, "stockfish.depth", 12) or 12))))
        self.sp_threshold.setValue(float(cfg_mod.get(c, "mistakes.loss_threshold", 0.80) or 0.80))
        idx = self.cb_source.findData(cfg_mod.get(c, "training.default_source", "bot"))
        self.cb_source.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.cb_mode.findData(cfg_mod.get(c, "training.default_mode", "recall"))
        self.cb_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self._refresh_mount_status()
        # 경로가 비어 있으면 흔한 자리만 훑어 자동으로 채워둔다(빠른 탐색).
        if not self.in_stockfish.text().strip():
            self._detect_stockfish(quick=True)

    def _collect(self) -> None:
        self.cfg = cfg_mod.load_config()
        cfg_mod.set_(self.cfg, "chesscom.username", self.in_username.text().strip())
        cfg_mod.set_(self.cfg, "google_drive.parent_folder_id", self.in_parent.text().strip())
        cfg_mod.set_(self.cfg, "google_drive.api_key", self.in_api_key.text().strip())
        cfg_mod.set_(self.cfg, "local.pgn_folder", self.in_local.text().strip())
        cfg_mod.set_(self.cfg, "rclone.remote", self.in_rclone_remote.text().strip())
        cfg_mod.set_(self.cfg, "rclone.binary", self.in_rclone_bin.text().strip())
        cfg_mod.set_(self.cfg, "rclone.config", self.in_rclone_conf.text().strip())
        cfg_mod.set_(self.cfg, "rclone.mount_point", self.in_mount_point.text().strip())
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

    def _set_status(self, text: str, state: str = "muted") -> None:
        self.lbl_status.setText(text)
        theme.set_state(self.lbl_status, state)

    def _summarize(self, result: dict) -> str:
        if not isinstance(result, dict):
            return str(result)
        if result.get("mounted"):
            return f"드라이브 마운트됨: {result.get('mount_point', '')}"
        if "problems" in result:
            tail = f" · 내려받음 {result['downloaded']}" if "downloaded" in result else ""
            return f"게임 {result.get('games', 0)} · 새 문제 {result.get('problems', 0)}{tail}"
        if "files" in result:
            return (
                f"파일 {result.get('files', 0)} · 새 게임 {result.get('new_games', 0)}"
                f" · 문제 {result.get('problems', 0)}"
            )
        return str(result)

    def _run(
        self,
        btn,
        fn,
        busy_text: str,
        on_done=None,
        on_failed=None,
        **kwargs,
    ) -> bool:
        """워커 실행 + 버튼에 '진행 중' 표시(눌렀는지 알 수 있게)."""
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return False
        orig = btn.text()
        self._worker = PipelineWorker(fn, **kwargs)
        self._worker.message.connect(self._log)
        self._worker.done.connect(on_done or self._on_done)
        self._worker.failed.connect(on_failed or self._on_sync_failed)
        btn.setEnabled(False)
        btn.setText(busy_text)
        self._set_status(f"{busy_text} ...", "muted")

        def _restore() -> None:
            btn.setEnabled(True)
            btn.setText(orig)

        self._worker.finished.connect(_restore)
        self._worker.start()
        return True

    _CRED_STEPS = (
        "credentials.json 이 없음. 드라이브를 쓰려면 처음 한 번만 만들면 됨:\n"
        "1) console.cloud.google.com 에서 프로젝트 생성\n"
        "2) APIs & Services > Library 에서 'Google Drive API' 사용 설정\n"
        "3) OAuth consent screen > External 로 만들고, Test users 에 본인 구글 계정 추가\n"
        "4) Credentials > Create credentials > OAuth client ID > Application type: Desktop app\n"
        "5) 만들면 JSON 이 내려받아짐 → 여기서 'credentials.json 선택' 으로 그 파일 고르기\n"
        "6) '구글 인증' 누르고 브라우저 로그인"
    )

    def _pick_credentials(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "credentials.json 선택 (OAuth 클라이언트 JSON)", "", "JSON (*.json);;모든 파일 (*)"
        )
        if not path:
            return
        try:
            dest = drive.install_credentials(path)
        except Exception as exc:  # noqa: BLE001
            self._log(f"credentials.json 저장 실패: {exc}")
            return
        self._log(f"credentials.json 저장됨: {dest}")
        self._log("이제 '구글 인증' 을 누르면 브라우저가 열림.")

    def _authorize(self) -> None:
        try:
            drive.build_service(interactive=True)
            self._log("구글 인증 완료. config/token.json 생성됨.")
        except ModuleNotFoundError as exc:
            self._log(
                f"구글 드라이브 라이브러리가 없음: {exc}\n"
                "pip install -r requirements.txt 후 exe 재빌드(build.ps1) 필요."
            )
        except FileNotFoundError:
            self._log(self._CRED_STEPS)
        except Exception as exc:
            self._log(f"인증 실패: {exc}")

    def _check_folder(self) -> None:
        self._collect()
        try:
            service = drive.build_service(interactive=False)
            if service is None:
                self._log("먼저 'API 키' 를 넣거나 '구글 인증' 을 하세요.")
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

    def _detect_stockfish(self, quick: bool = False) -> None:
        """PATH·앱 옆·흔한 설치 위치에서 stockfish*.exe 를 찾는다.

        ``quick=True`` 는 흔한 자리만 본다(탭 열 때 조용히). 버튼은 전체 탐색인데
        몇 초 걸릴 수 있어 워커 스레드에서 돌린다.
        """
        from core import engine as engine_mod

        if quick:
            try:
                path = engine_mod.find_stockfish(fast=True)
            except Exception as exc:  # noqa: BLE001
                self._log(f"Stockfish 자동 감지 실패: {exc}")
                return
            self._apply_stockfish(path, quiet=True)
            return

        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._log("Stockfish 찾는 중...")
        self._run(
            self.btn_detect_sf,
            self._run_detect,
            "찾는 중…",
            on_done=self._on_detect_done,
            on_failed=lambda e: self._log(f"자동 감지 실패: {e}"),
        )

    def _run_detect(self, on_progress=None) -> dict:
        from core import engine as engine_mod

        return {"path": engine_mod.find_stockfish()}

    def _on_detect_done(self, result: dict) -> None:
        self._apply_stockfish(result.get("path"))

    def _apply_stockfish(self, path, quiet: bool = False) -> None:
        if not path:
            if not quiet:
                self._log(
                    "Stockfish 를 못 찾음. stockfishchess.org 에서 받아 아무 폴더에 풀고 "
                    "'찾아보기' 로 지정하면 된다."
                )
            return
        self.in_stockfish.setText(path)
        if not quiet:
            self._save()
            self._log(f"Stockfish 자동 감지: {path}")

    def _refresh_mount_status(self) -> None:
        try:
            running = rclone_mod.mount_running()
        except Exception:  # noqa: BLE001
            running = False
        point = self.in_mount_point.text().strip()
        self.lbl_mount.setText(f"붙어 있음: {point}" if running else ("-" if not point else "안 붙음"))
        self.btn_unmount.setEnabled(running)

    def _mount_drive(self) -> None:
        from core import pipeline

        self._save()
        if not self.in_rclone_remote.text().strip():
            self._log("rclone 원격 경로를 입력하세요. (예: gdrive:chess분석)")
            return
        if not self.in_mount_point.text().strip():
            self._log("붙일 드라이브 문자를 입력하세요. (예: X:)")
            return
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(
            self.btn_mount,
            pipeline.mount_drive,
            "마운트 중…",
            on_done=self._on_mount_done,
            cfg=self.cfg,
        )

    def _unmount_drive(self) -> None:
        from core import pipeline

        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(
            self.btn_unmount,
            pipeline.unmount_drive,
            "해제 중…",
            on_done=lambda _r: self._on_mount_done({}),
            cfg=self.cfg,
        )

    def _on_mount_done(self, result: dict) -> None:
        self._refresh_mount_status()
        point = result.get("mount_point")
        if point:
            self._log(f"드라이브 마운트 완료: {point}")
            self._set_status(f"마운트됨: {point}", "success")
            # 붙였으면 바로 로컬 PGN 폴더로 써먹을 수 있게 안내 겸 자동 지정 제안
            if not self.in_local.text().strip():
                self._use_mount_as_local()
        else:
            self._set_status("마운트 해제됨.", "muted")

    def _use_mount_as_local(self) -> None:
        point = self.in_mount_point.text().strip()
        if not point:
            self._log("드라이브 문자를 먼저 입력하세요. (예: X:)")
            return
        self.in_local.setText(rclone_mod.normalize_mount_point(point))
        self._save()
        self._log(f"로컬 PGN 폴더를 마운트 위치로 지정: {self.in_local.text()}")

    def _browse_local(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "PGN 게임 폴더 선택")
        if path:
            self.in_local.setText(path)
            self._save()

    def _open_local(self) -> None:
        self._collect()
        path = self.in_local.text().strip()
        if not path or not os.path.isdir(path):
            self._log("먼저 로컬 PGN 폴더를 선택하세요.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _sync_local(self) -> None:
        from core import pipeline

        self._save()
        if not self.in_local.text().strip():
            self._log("먼저 로컬 PGN 폴더를 선택하세요.")
            return
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(
            self.btn_local_sync,
            pipeline.sync_local_folder,
            "동기화 중…",
            cfg=self.cfg,
        )

    def _sync(self) -> None:
        from core import pipeline

        self._save()
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(self.btn_sync, pipeline.sync_drive, "동기화 중…", cfg=self.cfg)

    def _pull_drive(self) -> None:
        from core import pipeline

        self._save()
        if not self.in_local.text().strip():
            self._log("먼저 '로컬 PGN 폴더'를 지정하세요. 내려받은 PGN 을 여기에 저장합니다.")
            return
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(
            self.btn_pull,
            pipeline.pull_drive_to_local,
            "받는 중…",
            cfg=self.cfg,
        )

    def _browse_rclone(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "rclone.exe 선택", "", "실행 파일 (*.exe);;모든 파일 (*)"
        )
        if path:
            self.in_rclone_bin.setText(path)

    def _browse_rclone_conf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "rclone.conf 선택", "", "rclone 설정 (*.conf);;모든 파일 (*)"
        )
        if path:
            self.in_rclone_conf.setText(path)

    def _pull_rclone(self) -> None:
        from core import pipeline

        self._save()
        if not self.in_local.text().strip():
            self._log("먼저 '로컬 PGN 폴더'를 지정하세요. rclone 이 여기로 받아옵니다.")
            return
        if not self.in_rclone_remote.text().strip():
            self._log("rclone 원격 경로를 입력하세요. (예: gdrive:chess-brian)")
            return
        if self._worker is not None and self._worker.isRunning():
            self._log("이미 작업이 실행 중입니다.")
            return
        self._run(
            self.btn_rclone,
            pipeline.pull_rclone_to_local,
            "받는 중…",
            cfg=self.cfg,
        )

    def _on_sync_failed(self, err: str) -> None:
        self._set_status(f"실패 — {err}", "danger")
        # 자격증명/도구가 없어서 실패한 경우엔 다음에 뭘 할지까지 보여준다.
        if "credentials.json" in err:
            self._log(self._CRED_STEPS)
            return
        if "드라이브 접근 자격" in err:
            self._log(
                "드라이브 접근 방법이 없음. 셋 중 하나:\n"
                "1) rclone (구글 설정 불필요, 추천): rclone 원격 경로를 넣고 'rclone 으로 받기'.\n"
                "2) API 키: 부모 폴더를 '링크가 있는 모든 사용자 · 뷰어'로 공유하고 "
                "Cloud Console > Credentials > Create credentials > API key 로 키를 만들어 "
                "위 'API 키' 칸에 붙여넣기.\n"
                "3) 구글 인증: 'credentials.json 선택' 후 '구글 인증'."
            )
            return
        if "rclone 을 찾을 수 없습니다" in err:
            self._log(
                "rclone.exe 를 못 찾음. rclone 은 설치 없이 exe 하나만 있으면 됨. "
                "rclone.org 에서 받아 아무 폴더에 두고 위 'rclone.exe 경로'에 지정하거나, "
                "PATH 에 넣으면 자동으로 잡힌다."
            )
            return
        self._log(f"실패: {err}")

    def _on_done(self, result: dict) -> None:
        self._log(f"완료: {result}")
        self._set_status(f"완료 — {self._summarize(result)}", "success")
        self.config_saved.emit()