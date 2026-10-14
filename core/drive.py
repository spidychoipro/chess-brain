"""Google Drive, read only.

We point at *one* parent folder. Inside it, ``Bot`` and ``Human`` subfolders
separate bot games from human games, and every ``.pgn`` under them becomes
training material. Files are read straight from Drive and never written
back to disk, which keeps the app tiny.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from core.utils import config_dir

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
FOLDER_MIME = "application/vnd.google-apps.folder"

_BOT_NAMES = {"bot", "bots", "vsbot", "vs bot", "engine"}
_HUMAN_NAMES = {"human", "humans", "player", "players", "people", "vs human"}


def classify_source(path_parts: Sequence[str]) -> Optional[str]:
    """Map a file's folder names to ``bot`` / ``human`` (None if unclear)."""
    for part in path_parts:
        name = part.strip().lower()
        if name in _BOT_NAMES:
            return "bot"
        if name in _HUMAN_NAMES:
            return "human"
    # 부분 일치도 허용 (예: "Bot Games", "Human vs Human")
    for part in path_parts:
        name = part.strip().lower()
        if "bot" in name:
            return "bot"
        if "human" in name or "player" in name:
            return "human"
    return None


@dataclass
class DriveFile:
    file_id: str
    name: str
    modified_time: str
    path_parts: Tuple[str, ...]

    @property
    def source(self) -> Optional[str]:
        return classify_source(self.path_parts)


def token_path():
    return config_dir() / "token.json"


def credentials_path():
    return config_dir() / "credentials.json"


def install_credentials(src_path: str):
    """Copy an OAuth client JSON to config/credentials.json, validating first.

    Lets the user pick the file they downloaded from Google Cloud Console
    instead of having to find the config folder by hand.
    """
    import json
    import shutil
    from pathlib import Path

    src = Path(src_path)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"JSON 을 읽을 수 없음: {exc}") from exc

    if "installed" not in data and "web" not in data:
        raise ValueError(
            "OAuth 클라이언트 JSON 이 아님. Google Cloud Console > "
            "Credentials > OAuth client ID (Desktop app) 에서 받은 파일인지 확인."
        )

    dest = credentials_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return dest


def build_service(interactive: bool = True, api_key: Optional[str] = None):
    """Build a Drive v3 client.

    우선순위: 저장된 OAuth 토큰(비공개 접근) → API 키(링크 공유 폴더, 로그인 불필요)
    → 대화형 OAuth 로그인. API 키 방식은 구글 로그인 창을 띄우지 않는다.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    tp = token_path()
    if tp.exists():
        creds = Credentials.from_authorized_user_file(str(tp), SCOPES)

    if creds and creds.valid:
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        tp.write_text(creds.to_json(), encoding="utf-8")
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    if api_key is None:
        api_key = configured_api_key()
    if api_key:
        return build("drive", "v3", developerKey=api_key, cache_discovery=False)

    if not interactive:
        return None

    cp = credentials_path()
    if not cp.exists():
        raise FileNotFoundError(
            "config/credentials.json 이 필요합니다. "
            "Google Cloud Console 에서 OAuth 클라이언트(데스크톱 앱)를 만들어 "
            "내려받은 뒤 config/credentials.json 으로 저장하세요."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(cp), SCOPES)
    creds = flow.run_local_server(port=0)
    tp.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def configured_api_key() -> str:
    """config 의 google_drive.api_key (없으면 빈 문자열)."""
    try:
        from core import config as cfg_mod

        cfg = cfg_mod.load_config()
        return (cfg_mod.get(cfg, "google_drive.api_key", "") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def is_authorized() -> bool:
    return token_path().exists() or bool(configured_api_key())


def get_folder(service, folder_id: str) -> Optional[dict]:
    return (
        service.files()
        .get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
        .execute()
    )


def resolve_folder_id(service, value: str) -> str:
    """Accept a raw folder id or a share URL and return the folder id."""
    v = (value or "").strip()
    if "/folders/" in v:
        return v.split("/folders/")[1].split("?")[0].split("/")[0]
    if "id=" in v:
        return v.split("id=")[1].split("&")[0]
    return v


def list_pgn_files(
    service,
    parent_id: str,
    max_depth: int = 3,
    _path: Tuple[str, ...] = (),
    _depth: int = 0,
) -> List[DriveFile]:
    """Recursively collect every .pgn file under ``parent_id``."""
    results: List[DriveFile] = []
    page_token = None
    while True:
        resp = (
            service.files()
            .list(
                q=f"'{parent_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,modifiedTime)",
                pageSize=200,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        for f in resp.get("files", []):
            if f["mimeType"] == FOLDER_MIME:
                if _depth < max_depth:
                    results.extend(
                        list_pgn_files(
                            service,
                            f["id"],
                            max_depth=max_depth,
                            _path=_path + (f["name"],),
                            _depth=_depth + 1,
                        )
                    )
            elif f["name"].lower().endswith(".pgn"):
                results.append(
                    DriveFile(
                        file_id=f["id"],
                        name=f["name"],
                        modified_time=f.get("modifiedTime", ""),
                        path_parts=_path,
                    )
                )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def read_text(service, file_id: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload
    import io

    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue().decode("utf-8", errors="replace")


def download_to(service, file_id: str, dest_path: str) -> None:
    """Stream a Drive file straight to ``dest_path`` (부모 폴더는 자동 생성)."""
    from googleapiclient.http import MediaIoBaseDownload
    from pathlib import Path

    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with dest.open("wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def list_child_folders(service, parent_id: str) -> List[dict]:
    resp = (
        service.files()
        .list(
            q=f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false",
            fields="files(id,name)",
            pageSize=200,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    return resp.get("files", [])
