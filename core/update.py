"""Check GitHub for a newer release tag.

No API key, no background polling, no cost. The user asks explicitly, we ask
GitHub once, and we show the result. Network failures are reported, never
silently swallowed.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Optional

from core import version

Progress = Optional[Callable[[str], None]]


def version_key(text: str) -> tuple:
    """`v0.2.1` -> (0, 2, 1). Unparseable tags sort below everything."""
    raw = (text or "").strip().lstrip("vV")
    try:
        return tuple(int(part) for part in raw.split("."))
    except ValueError:
        return (0,)


def check_latest(on_progress: Progress = None) -> Dict[str, Any]:
    """Return current/latest versions and whether an update exists."""
    if on_progress:
        on_progress("업데이트 확인 중…")

    request = urllib.request.Request(
        version.TAGS_API,
        headers={
            "User-Agent": "chess-brain-update-check",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            tags = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "current": version.__version__,
            "latest": None,
            "available": False,
            "url": version.RELEASES_URL,
        }

    latest = ""
    if isinstance(tags, list) and tags:
        latest = str((tags[0] or {}).get("name", "") or "").lstrip("vV")
    current = version.__version__
    available = bool(latest and version_key(latest) > version_key(current))
    return {
        "ok": True,
        "error": "",
        "current": current,
        "latest": latest,
        "available": available,
        "url": version.RELEASES_URL,
    }
