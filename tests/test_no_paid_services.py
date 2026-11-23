"""0원 구성 지키기: 앱이 유료/종량제 서비스에 연결하지 않는지 검사한다.

새 기능을 추가할 때 결제되는 API(LLM, 결제대행, 클라우드 추론 등)를 넣으면
이 테스트가 먼저 깨진다. 대화는 로컬 Stockfish, 기록은 SQLite, 가져오기는
chess.com 공개 API + rclone/구글드라이브 무료 할당량만 쓴다.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse
import unittest

ROOT = Path(__file__).resolve().parents[1]

# 앱이 말을 거는 곳 전부. 전부 무료다 (인증키 없음 / 무료 할당량 / 공개 API).
FREE_HOSTS = {
    "api.github.com",      # 업데이트 확인, 토큰 없이 조회
    "github.com",          # 릴리스 페이지 링크
    "api.chess.com",       # chess.com 공개 아카이브 (키 없음)
    "www.chess.com",       # 봇 게임 아카이브/프로필 (로그인 없음)
    "www.googleapis.com",  # 구글드라이브 읽기전용, 무료
    "www.w3.org",          # SVG 네임스페이스 (네트워크 요청 아님)
}

# 종량제/결제 서비스가 들어오면 바로 잡는다.
PAID_MARKERS = (
    "api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com",
    "api.groq.com", "api.together.xyz", "api.mistral.ai", "api.deepseek.com",
    "api.cohere.com", "api.replicate.com", "api.x.ai", "rapidapi.com",
    "api.stripe.com", "checkout.stripe.com", "api.paypal.com",
    "bedrock.", "api.aws.amazon.com", "openai.azure.com",
)

URL = re.compile(r"https?://[^\s'\"]+")


def _python_files() -> list[Path]:
    files = [ROOT / "main.py"]
    for folder in ("core", "ui", "tests"):
        files.extend(sorted((ROOT / folder).rglob("*.py")))
    # 이 테스트 파일은 금지 문자열을 그대로 들고 있으니 비교 대상에서 뺀다.
    return [p for p in files if p.is_file() and p.name != "test_no_paid_services.py"]


class NoPaidServicesTests(unittest.TestCase):
    def test_every_url_host_is_free(self):
        bad = []
        for path in _python_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for raw in URL.findall(text):
                host = (urlparse(raw).hostname or "").lower()
                if host and host not in FREE_HOSTS:
                    bad.append(f"{path.relative_to(ROOT)}: {host}")
        self.assertEqual(bad, [], f"무료 허용 목록에 없는 호스트: {bad}")

    def test_no_payment_or_llm_provider(self):
        hits = []
        for path in _python_files():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for marker in PAID_MARKERS:
                if marker in text:
                    hits.append(f"{path.relative_to(ROOT)}: {marker}")
        self.assertEqual(hits, [], f"과금 서비스 흔적: {hits}")

    def test_config_has_no_secret_or_billing_key(self):
        # 실제 설정 파일에는 구글 API 키도 비어 있다. (쓰더라도 무료지만)
        import json
        from core import config as cfg_mod

        cfg = cfg_mod.load_config()
        self.assertEqual(cfg.get("google_drive", {}).get("api_key", ""), "")
        self.assertNotIn("api_key", cfg.get("chesscom", {}))
        self.assertNotIn("subscription", cfg)
        self.assertNotIn("billing", cfg)


if __name__ == "__main__":
    unittest.main()
