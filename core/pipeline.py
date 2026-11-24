"""Glue: Drive/local PGN -> problems, and Stockfish -> mistakes.

Kept separate from the UI so the whole pipeline can be exercised from a
plain script (handy for testing without launching Qt).
"""
from __future__ import annotations

import io
import os
from typing import Any, Callable, Dict, List, Optional

import chess

from core import config as cfg_mod
from core import curriculum, db, drive, engine as engine_mod, parser

Progress = Optional[Callable[[str], None]]


def _note(on_progress: Progress, msg: str) -> None:
    if on_progress:
        on_progress(msg)


def _count(on_progress: Progress, done: int, total: int, msg: str) -> None:
    """숫자 진행률이 필요한 단계에서 쓴다. worker가 이 dict를 시그널로 바꾼다."""
    if on_progress:
        on_progress({"done": done, "total": total, "message": msg})


def _user_settings(cfg: Dict[str, Any]):
    username = cfg_mod.get(cfg, "chesscom.username", "") or ""
    fallback = cfg_mod.get(cfg, "chesscom.fallback_color", "white") or "white"
    return username, fallback


def _fill_missing_replies_with(sf, on_progress: Progress = None, limit: int = 500) -> int:
    """옛 실수의 '상대 응수'를 채운다(재분석 없이 엔진만 다시 돌림).

    국면이 이미 끝난 경우는 응수가 없으니 '-' 로 표시해 두 번 일하지 않게 한다.
    """
    rows = db.mistakes_missing_reply(limit=limit)
    if not rows:
        return 0
    _note(on_progress, f"상대 응수 채우는 중: {len(rows)}개")
    filled = 0
    for i, r in enumerate(rows, 1):
        _count(on_progress, i, len(rows), f"상대 응수 채우는 중 {i}/{len(rows)}")
        try:
            b = chess.Board(r["fen"])
            b.push(b.parse_san(r["my_san"]))
        except Exception:  # noqa: BLE001
            db.set_mistake_reply(r["id"], "-")
            continue
        if b.is_game_over():
            db.set_mistake_reply(r["id"], "-")
            continue
        try:
            rep = sf.best_move(b).get("best_san") or "-"
        except Exception:  # noqa: BLE001
            rep = "-"
        db.set_mistake_reply(r["id"], rep)
        filled += 1
    _note(on_progress, f"상대 응수 {filled}개 채움")
    return filled


def fill_missing_replies(cfg: Dict[str, Any], on_progress: Progress = None) -> int:
    """새로 분석할 게임이 없어도 '실수 분석' 버튼이 응수를 채우게 한다."""
    sf_path = engine_mod.resolve_engine_path(cfg_mod.get(cfg, "stockfish.path", ""))
    if not engine_mod.engine_available(sf_path):
        return 0
    depth = max(4, min(16, int(cfg_mod.get(cfg, "stockfish.depth", 12) or 12)))
    threads = int(cfg_mod.get(cfg, "stockfish.threads", 0) or 0)
    hash_mb = int(cfg_mod.get(cfg, "stockfish.hash_mb", 256) or 256)
    with engine_mod.Stockfish(
        sf_path, depth, threads=threads or None, hash_mb=hash_mb
    ) as sf:
        return _fill_missing_replies_with(sf, on_progress)


def ingest_pgn_text(
    pgn_text: str,
    source: str,
    cfg: Dict[str, Any],
    file_id: Optional[str] = None,
    modified_time: Optional[str] = None,
    on_progress: Progress = None,
) -> Dict[str, int]:
    """Parse one PGN blob and store its user lines as line problems."""
    db.init_db()
    username, fallback = _user_settings(cfg)
    stats = {"games": 0, "new_games": 0, "lines": 0, "problems": 0,
             "skipped": 0, "errors": 0}

    # 한 게임이 깨졌다고 파일 전체(그리고 뒤의 모든 파일)가 멈추면 안 된다.
    # 게임마다 에러를 격리해서 건너뛰고 나머지는 계속 읽는다.
    stream = io.StringIO(pgn_text)
    while True:
        try:
            game = chess.pgn.read_game(stream)
        except Exception as exc:
            stats["errors"] += 1
            _note(on_progress, f"PGN 읽기 오류: {exc}")
            break
        if game is None:
            break
        if game.errors:
            stats["errors"] += 1
            _note(on_progress, f"잘못된 PGN 건너뜀: {game.errors[0]}")
            continue
        stats["games"] += 1
        try:
            gid = parser.game_id(game)
            # Validate ownership before marking a game processed.
            parser.user_color(game, username, fallback)
            if gid != parser.legacy_game_id(game):
                existing_lines = parser.extract_user_lines(game, source, username, fallback)
                db.migrate_game_identity(
                    parser.legacy_game_id(game), gid,
                    {(ln.fen_before, ln.san, ln.ply) for ln in existing_lines},
                )
            db.upsert_game(gid, source, file_id, modified_time)
            if db.is_game_processed(gid):
                continue
            stats["new_games"] += 1
            lines = parser.extract_user_lines(
                game,
                source=source,
                username=username,
                fallback_color=fallback,
                min_ply=2,
            )
            made = 0
            for ln in lines:
                stats["lines"] += 1
                made += 1
                pid = db.add_problem(
                    fen=ln.fen_before,
                    context_sans=ln.context_sans,
                    target_san=ln.san,
                    source_game_id=gid,
                    source=source,
                    ply=ln.ply,
                    origin="line",
                )
                if pid:
                    stats["problems"] += 1
            if made == 0:
                # 아이디/색이 안 맞거나 PGN이 잘리면 내 수가 0개가 된다. 여기서
                # processed를 찍어버리면 설정을 고쳐도 영구히 다시 읽지 않는다.
                stats["skipped"] += 1
                _note(on_progress, f"내 수가 없어 보류: {gid} (아이디/색 확인 필요)")
            else:
                db.mark_game_processed(gid)
        except Exception as exc:
            # 예: 설정한 아이디가 없는 다른 계정의 게임. 그 게임만 건너뛴다.
            stats["errors"] += 1
            _note(on_progress, f"게임 건너뜀: {exc}")
            continue
    return stats


def import_local_file(
    path: str,
    source: str,
    cfg: Dict[str, Any],
    on_progress: Progress = None,
) -> Dict[str, int]:
    _note(on_progress, f"읽는 중: {os.path.basename(path)}")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    # 로컬 파일은 파일 경로 자체를 식별자로 쓴다.
    return ingest_pgn_text(
        text,
        source,
        cfg,
        file_id="local:" + os.path.abspath(path),
        modified_time=str(int(os.path.getmtime(path))),
        on_progress=on_progress,
    )


def sync_local_folder(
    cfg: Dict[str, Any],
    on_progress: Progress = None,
) -> Dict[str, int]:
    """Scan a local folder and ingest every .pgn under it.

    This is the *no-Google, no-cost* path: the user keeps PGNs in a local
    folder with Bot/Human subfolders, and source is derived from those
    folder names (same classifier the Drive path uses).
    """
    db.init_db()
    root = cfg_mod.get(cfg, "local.pgn_folder", "") or ""
    if not root or not os.path.isdir(root):
        raise ValueError(
            "로컬 PGN 폴더를 찾을 수 없습니다: "
            f"{root or '(비어 있음)'}\n"
            "설정에서 실제 폴더를 고르세요. 드라이브 문자(예: X:)를 쓴다면 "
            "WinFsp 설치 후 '드라이브 마운트'가 붙어 있어야 그 드라이브가 보인다."
        )

    _note(on_progress, f"스캔 중: {root}")
    pgn_files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".pgn"):
                pgn_files.append(os.path.join(dirpath, name))
    pgn_files.sort()

    empty = {"files": 0, "games": 0, "new_games": 0, "lines": 0, "problems": 0,
             "skipped": 0, "errors": 0}
    if not pgn_files:
        _note(on_progress, "찾은 .pgn 파일이 없습니다.")
        return empty

    _note(on_progress, f".pgn {len(pgn_files)}개 발견")
    total = dict(empty)
    for i, path in enumerate(pgn_files, 1):
        _count(on_progress, i, len(pgn_files), f"PGN 읽는 중 {i}/{len(pgn_files)}")
        rel = os.path.relpath(path, root)
        parts = rel.split(os.sep)
        # 하위폴더 이름 우선, 파일 이름의 힌트는 보조로 쓴다.
        src = (
            drive.classify_source(parts[:-1])
            or drive.classify_source(parts)
            or "human"
        )
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            stats = ingest_pgn_text(
                text,
                src,
                cfg,
                file_id="local:" + os.path.abspath(path),
                modified_time=str(int(os.path.getmtime(path))),
            )
        except Exception as exc:
            total["errors"] += 1
            _note(on_progress, f"파일 건너뜀 {os.path.basename(path)}: {exc}")
            continue
        for k in total:
            total[k] += stats.get(k, 0)
        total["files"] += 1
    _note(on_progress, f"동기화 완료: {total}")
    return total


def sync_drive(cfg: Dict[str, Any], on_progress: Progress = None) -> Dict[str, int]:
    """Read the configured parent folder and ingest every .pgn found."""
    db.init_db()
    parent = cfg_mod.get(cfg, "google_drive.parent_folder_id", "")
    if not parent:
        raise ValueError("설정에서 구글드라이브 부모 폴더를 먼저 지정하세요.")
    service = drive.build_service()
    parent_id = drive.resolve_folder_id(service, parent)

    _note(on_progress, "드라이브에서 .pgn 찾는 중...")
    files = drive.list_pgn_files(service, parent_id)
    _note(on_progress, f"{len(files)}개 PGN 발견")

    total = {"files": len(files), "games": 0, "new_games": 0, "lines": 0, "problems": 0,
             "skipped": 0, "errors": 0}
    for i, f in enumerate(files, 1):
        source = f.source or "human"
        if f.source is None:
            _note(on_progress, f"[분류불명→human] {'/'.join(f.path_parts)}/{f.name}")
        _note(on_progress, f"({i}/{len(files)}) {f.name} [{source}]")
        text = drive.read_text(service, f.file_id)
        s = ingest_pgn_text(
            text,
            source,
            cfg,
            file_id=f.file_id,
            modified_time=f.modified_time,
        )
        for k in ("games", "new_games", "lines", "problems", "skipped", "errors"):
            total[k] += s.get(k, 0)
    _note(on_progress, f"완료: 새 게임 {total['new_games']} / 문제 {total['problems']}")
    return total


def pull_drive_to_local(cfg: Dict[str, Any], on_progress: Progress = None) -> Dict[str, int]:
    """드라이브 부모 폴더의 .pgn 을 로컬 PGN 폴더로 내려받고, 이어서 로컬 동기화한다.

    "드라이브 링크를 넣으면 그걸 로컬로 가져와서 쓴다" 는 경로. 로컬 폴더에
    하위 구조(Bot / Human)를 그대로 만들어 저장하므로 이후에는 로컬 동기화만
    돌려도 된다. 접근은 API 키(링크 공유 폴더) 또는 구글 인증(OAuth) 아무거나.
    """
    db.init_db()
    root = cfg_mod.get(cfg, "local.pgn_folder", "") or ""
    if not root:
        raise ValueError(
            "먼저 '로컬 PGN 폴더'를 지정하세요. 내려받은 PGN 을 여기에 저장합니다."
        )
    os.makedirs(root, exist_ok=True)

    parent = cfg_mod.get(cfg, "google_drive.parent_folder_id", "")
    if not parent:
        raise ValueError("설정에서 구글드라이브 부모 폴더를 먼저 지정하세요.")

    service = drive.build_service()
    if service is None:
        raise ValueError(
            "드라이브 접근 자격이 없습니다. 'API 키' 를 넣거나 '구글 인증' 을 하세요."
        )
    parent_id = drive.resolve_folder_id(service, parent)

    _note(on_progress, "드라이브에서 .pgn 찾는 중...")
    files = drive.list_pgn_files(service, parent_id)
    _note(on_progress, f"{len(files)}개 PGN → 로컬로 내려받기")

    root_abs = os.path.abspath(root)
    downloaded = 0
    for i, f in enumerate(files, 1):
        parts = [p for p in f.path_parts if p not in ("", ".", "..", "/", "\\")]
        dest = os.path.join(root, *parts, f.name)
        if not os.path.abspath(dest).startswith(root_abs):
            _note(on_progress, f"건너뜀(경로 이상): {f.name}")
            continue
        drive.download_to(service, f.file_id, dest)
        downloaded += 1
        _note(on_progress, f"({i}/{len(files)}) 저장: {'/'.join(parts + [f.name])}")

    _note(on_progress, f"{downloaded}개 저장 완료 → 로컬 동기화 시작")
    stats = sync_local_folder(cfg, on_progress)
    stats["downloaded"] = downloaded
    return stats


def pull_rclone_to_local(cfg: Dict[str, Any], on_progress: Progress = None) -> Dict[str, int]:
    """rclone copy 로 드라이브 폴더를 로컬로 가져온 뒤, 이어서 로컬 동기화한다.

    rclone 이 구글 인증을 들고 있으니 앱은 API 키/OAuth 가 필요 없다. 사용자는
    rclone remote(예: ``gdrive:chess-brian``)만 지정하면 된다.
    """
    from core import rclone as rclone_mod

    db.init_db()
    root = cfg_mod.get(cfg, "local.pgn_folder", "") or ""
    if not root:
        raise ValueError("먼저 '로컬 PGN 폴더'를 지정하세요. rclone 이 여기로 받아옵니다.")
    remote = rclone_mod.get_remote(cfg)
    if not remote:
        raise ValueError("설정에서 rclone 원격 경로를 지정하세요. (예: gdrive:chess-brian)")
    exe = rclone_mod.find_binary(cfg)
    if not exe:
        raise ValueError(
            "rclone 을 찾을 수 없습니다. 'rclone.exe 경로'를 지정하거나 PATH 에 넣으세요. "
            "(rclone 은 설치 없이 exe 하나만 있으면 됨)"
        )

    os.makedirs(root, exist_ok=True)
    _note(on_progress, f"rclone copy {remote} → {root}")
    code = rclone_mod.run_copy(
        exe, remote, root, config=rclone_mod.get_config(cfg),
        on_line=lambda m: _note(on_progress, m),
    )
    if code != 0:
        raise RuntimeError(f"rclone 실패 (code {code}). remote/경로를 확인하세요.")

    _note(on_progress, "rclone 완료 → 로컬 동기화 시작")
    return sync_local_folder(cfg, on_progress)


def auto_catch_up(
    cfg: Dict[str, Any], on_progress: Progress = None, fetch_all: bool = False
) -> Dict[str, Any]:
    """앱을 켜지 않은 사이 쌓인 대국을 자동으로 따라잡는다.

    순서: chess.com 에서 새 PGN 받기 → 마운트 경로가 죽었으면 다시 붙이고 →
    rclone 으로 드라이브의 새 PGN을 로컬 폴더에 받고 → 로컬 폴더를 스캔한다.
    ``fetch_all=True`` 면 아직 안 받은 과거 게임 전부를 훑는다(5개월치 300판도
    여기서 처리). 실패해도 예외 대신 ``warnings`` 에 담고 로컬 스캔은 계속한다.
    """
    from core import chesscom as chesscom_mod
    from core import rclone as rclone_mod

    db.init_db()
    root = (cfg_mod.get(cfg, "local.pgn_folder", "") or "").strip()
    result: Dict[str, Any] = {
        "files": 0, "games": 0, "new_games": 0, "problems": 0, "skipped": 0,
        "errors": 0, "pulled": False, "mounted": False, "warnings": [],
        "fetched": 0, "fetch_ok": True,
    }
    if not root:
        result["warnings"].append("로컬 PGN 폴더가 지정되지 않아 자동 가져오기를 건너뛰었어요.")
        return result

    # chess.com 은 게임 수와 무관하게 달 단위 API 한 번으로 받는다.
    # 도구가 로컬/드라이브에 PGN 을 저장하면 아래 스캔이 그대로 읽는다.
    fetch = chesscom_mod.fetch_recent(cfg, on_progress, full=fetch_all)
    result["fetched"] = int(fetch.get("new", 0) or 0)
    result["fetch_ok"] = bool(fetch.get("ok"))
    if fetch.get("error"):
        result["warnings"].append(fetch["error"])

    exe = rclone_mod.find_binary(cfg)
    remote = rclone_mod.get_remote(cfg)
    mount_point = rclone_mod.normalize_mount_point(rclone_mod.get_mount_point(cfg))
    is_mount_path = bool(mount_point) and (
        os.path.normcase(os.path.abspath(root))
        == os.path.normcase(os.path.abspath(mount_point))
    )
    if remote and exe and is_mount_path and not os.path.isdir(root):
        try:
            mount_drive(cfg, on_progress)
            result["mounted"] = True
        except Exception as exc:
            result["warnings"].append(f"드라이브 다시 붙이기 실패: {exc}")

    if not os.path.isdir(root):
        result["warnings"].append(f"로컬 PGN 폴더를 찾을 수 없어요: {root}")
        return result

    if remote and exe and not is_mount_path:
        try:
            _note(on_progress, f"드라이브에서 새 대국 확인: {remote}")
            code = rclone_mod.run_copy(
                exe, remote, root, config=rclone_mod.get_config(cfg),
                on_line=lambda m: _note(on_progress, m),
            )
            if code == 0:
                result["pulled"] = True
            else:
                result["warnings"].append(
                    f"드라이브에서 받기 실패(code {code}). 로컬 파일로 계속합니다."
                )
        except Exception as exc:
            result["warnings"].append(f"드라이브 확인 실패: {exc}. 로컬 파일로 계속합니다.")

    try:
        stats = sync_local_folder(cfg, on_progress)
    except Exception as exc:
        result["warnings"].append(f"로컬 동기화 실패: {exc}")
        return result
    for key in ("files", "games", "new_games", "problems", "skipped", "errors"):
        result[key] = stats.get(key, 0)
    if result["errors"]:
        result["warnings"].append(
            f"읽지 못한 게임 {result['errors']}개가 있어요. 로그에서 이유를 확인하세요."
        )
    return result


def mount_drive(cfg: Dict[str, Any], on_progress: Progress = None) -> Dict[str, Any]:
    """rclone mount 로 드라이브를 로컬 드라이브 문자에 붙인다 (복사 없이 실시간).

    붙고 나면 그 드라이브 문자를 '로컬 PGN 폴더'로 쓰면 된다. Windows 는 WinFsp 필요.
    """
    from core import rclone as rclone_mod

    exe = rclone_mod.find_binary(cfg)
    if not exe:
        raise ValueError(
            "rclone 을 찾을 수 없습니다. 'rclone.exe 경로'를 지정하거나 PATH 에 넣으세요."
        )
    remote = rclone_mod.get_remote(cfg)
    if not remote:
        raise ValueError("설정에서 rclone 원격 경로를 지정하세요. (예: gdrive:chess분석)")
    mount_point = rclone_mod.get_mount_point(cfg)
    if not mount_point:
        raise ValueError("붙일 드라이브 문자를 입력하세요. (예: X:)")
    if rclone_mod.find_winfsp() is None:
        raise ValueError(
            "WinFsp 가 필요합니다(mount 기능). winfsp.dev 에서 설치 후 다시 시도하세요. "
            "설치 없이 쓰려면 'rclone 으로 받기'(copy)를 쓰면 됩니다."
        )

    _note(on_progress, f"rclone mount {remote} → {mount_point}")
    rclone_mod.start_mount(exe, remote, mount_point, config=rclone_mod.get_config(cfg))
    if not rclone_mod.wait_for_mount(mount_point):
        rclone_mod.stop_mount()
        raise RuntimeError(
            "마운트 실패. data\\rclone-mount.log 를 확인하세요 "
            "(remote/드라이브 문자/WinFsp 문제일 수 있음)."
        )
    _note(on_progress, f"마운트됨: {mount_point} — 이제 '로컬 PGN 폴더'로 쓰면 됩니다.")
    return {"mounted": True, "mount_point": mount_point}


def unmount_drive(cfg: Dict[str, Any] = None, on_progress: Progress = None) -> Dict[str, Any]:
    """붙어 있는 rclone mount 를 해제한다."""
    from core import rclone as rclone_mod

    stopped = rclone_mod.stop_mount()
    if stopped:
        _note(on_progress, "마운트 해제됨.")
    else:
        _note(on_progress, "붙어 있는 드라이브가 없습니다.")
    return {"mounted": False, "stopped": stopped}


def analyze_mistakes(
    cfg: Dict[str, Any],
    source: Optional[str] = "human",
    on_progress: Progress = None,
    auto_sync: bool = False,
) -> Dict[str, int]:
    """Run Stockfish over not-yet-analyzed games to collect my mistakes.

    ``auto_sync`` 를 켜면 분석할 게임이 하나도 없을 때 로컬 PGN 폴더를 먼저
    읽는다. 사용자가 동기화를 깜빡하고 분석 버튼을 먼저 눌러도 '실수 0개'로
    끝나지 않고 버튼 한 번에 결과까지 가게 하려는 것.
    """
    db.init_db()
    sf_path = engine_mod.resolve_engine_path(cfg_mod.get(cfg, "stockfish.path", ""))
    raw_depth = int(cfg_mod.get(cfg, "stockfish.depth", 12) or 12)
    # depth 27 같은 값이 들어오면 분석이 사실상 안 끝난다. 안전하게 자른다.
    depth = max(4, min(16, raw_depth))
    if depth != raw_depth:
        _note(on_progress, f"depth {raw_depth} → {depth} 로 조정(너무 깊으면 안 끝남).")
    threshold = float(cfg_mod.get(cfg, "mistakes.loss_threshold", 0.80) or 0.80)
    skip_lost = bool(cfg_mod.get(cfg, "mistakes.skip_lost_positions", True))
    threads = int(cfg_mod.get(cfg, "stockfish.threads", 0) or 0)
    hash_mb = int(cfg_mod.get(cfg, "stockfish.hash_mb", 256) or 256)

    if not engine_mod.engine_available(sf_path):
        raise ValueError("설정에서 stockfish.exe 경로를 지정하세요.")

    username, fallback = _user_settings(cfg)
    pending = db.games_needing_analysis(source)

    if not pending and auto_sync:
        root = cfg_mod.get(cfg, "local.pgn_folder", "") or ""
        if root and os.path.isdir(root):
            _note(on_progress, "분석할 게임이 없어 로컬 PGN 폴더를 먼저 읽는다...")
            try:
                sync_local_folder(cfg, on_progress)
            except Exception as exc:  # 동기화 실패는 분석 결과를 막지 않는다
                _note(on_progress, f"로컬 동기화 실패: {exc}")
            pending = db.games_needing_analysis(source)

    if not pending:
        counts = db.game_counts(source)
        root = cfg_mod.get(cfg, "local.pgn_folder", "") or ""
        folder_ok = bool(root) and os.path.isdir(root)
        # 게임이 아예 없어서 0인지, 다 분석해서 0인지 나눠서 알려준다.
        reason = "no_games" if counts["total"] == 0 else "all_analyzed"
        filled = 0
        if reason == "all_analyzed":
            _note(on_progress, "새로 분석할 게임이 없습니다. (이미 다 분석됨)")
            # 게임은 다 분석돼도 옛 실수의 상대 응수는 아직 비어 있을 수 있다.
            filled = fill_missing_replies(cfg, on_progress)
        elif not folder_ok:
            _note(on_progress, f"분석할 게임이 없고 로컬 PGN 폴더도 못 찾음: {root or '(비어 있음)'}")
        else:
            _note(on_progress, "분석할 게임이 없습니다. 먼저 PGN 을 동기화하세요.")
        return {
            "games": 0,
            "mistakes": 0,
            "problems": 0,
            "filled": filled,
            "games_total": counts["total"],
            "pending_before": 0,
            "reason": reason,
            "folder_ok": folder_ok,
            "folder": root,
        }

    # 같은 파일을 두 번 내려받지 않도록 file_id 로 묶는다.
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for g in pending:
        by_file.setdefault(g["file_id"], []).append(g)

    stats = {"games": 0, "mistakes": 0, "problems": 0, "filled": 0}
    total_games = len(pending)
    service = None
    if any(not fid.startswith("local:") for fid in by_file):
        service = drive.build_service()
    with engine_mod.Stockfish(
        sf_path, depth, threads=threads or None, hash_mb=hash_mb
    ) as sf:
        _note(on_progress, f"분석 시작 (depth {depth}, 스레드 {sf.threads})")
        for file_id, games in by_file.items():
            # PGN 을 옮기거나 드라이브 접근이 끊겨도 나머지 게임 분석은 계속된다.
            try:
                if file_id.startswith("local:"):
                    with open(file_id[len("local:") :], "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                else:
                    text = drive.read_text(service, file_id)
            except Exception as exc:
                _note(on_progress, f"PGN 읽기 실패, 건너뜀: {os.path.basename(file_id)} ({exc})")
                continue

            wanted = {g["game_id"] for g in games}
            for game in parser.iter_games(text):
                gid = parser.game_id(game)
                if gid not in wanted:
                    continue
                gsource = next(g["source"] for g in games if g["game_id"] == gid)
                lines = parser.extract_user_lines(
                    game, source=gsource, username=username, fallback_color=fallback
                )
                stats["games"] += 1
                _count(
                    on_progress,
                    stats["games"],
                    total_games,
                    f"분석 중 {stats['games']}/{total_games} · "
                    f"{game.headers.get('White', '?')} vs {game.headers.get('Black', '?')}",
                )
                for ln in lines:
                    _note(on_progress, f"분석 중 · {ln.ply}번째 반수")
                    board = chess.Board(ln.fen_before)
                    try:
                        move = board.parse_san(ln.san)
                    except ValueError:
                        continue
                    res = engine_mod.find_mistake(
                        sf_path,
                        ln.fen_before,
                        move.uci(),
                        threshold=threshold,
                        depth=depth,
                        engine=sf,
                        skip_lost=skip_lost,
                    )
                    if res is None:
                        continue
                    item = {
                        "fen": ln.fen_before, "ply": ln.ply,
                        "best_san": res.best_san, "my_san": res.my_san,
                        "reply_san": res.reply_san, "loss": res.loss,
                        "mate_before": res.mate_before, "mate_after": res.mate_after,
                        "best_line": res.best_line, "reply_line": res.reply_line,
                    }
                    theme = curriculum.classify(item)
                    mid = db.add_mistake(
                        fen=ln.fen_before,
                        context_sans=ln.context_sans,
                        my_san=res.my_san,
                        best_san=res.best_san,
                        eval_before=res.eval_before,
                        eval_after=res.eval_after,
                        loss=res.loss,
                        source_game_id=gid,
                        source=gsource,
                        ply=ln.ply,
                        reply_san=res.reply_san,
                        accepted_sans=res.accepted_sans,
                        best_line=res.best_line,
                        reply_line=res.reply_line,
                        mate_before=res.mate_before,
                        mate_after=res.mate_after,
                        theme=theme,
                        explanation=curriculum.explain(item, theme),
                    )
                    stats["mistakes"] += 0 if mid == 0 else 1
                    if mid and res.best_san:
                        pid = db.add_problem(
                            fen=ln.fen_before,
                            context_sans=ln.context_sans,
                            target_san=res.best_san,
                            source_game_id=gid,
                            source=gsource,
                            ply=ln.ply,
                            origin="mistake",
                            mistake_id=mid,
                        )
                        if pid:
                            stats["problems"] += 1
                db.mark_game_analyzed(gid)
        stats["filled"] = _fill_missing_replies_with(sf, on_progress)
    _note(on_progress, f"완료: 실수 {stats['mistakes']} / 복습문제 {stats['problems']}")
    return {
        **stats,
        "games_total": db.game_counts(source)["total"],
        "pending_before": len(pending),
        "reason": "",
    }
