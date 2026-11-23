"""Update-check logic: version ordering and GitHub response handling."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from core import update, version


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class UpdateTests(unittest.TestCase):
    def test_version_key_ordering(self):
        self.assertGreater(update.version_key("v0.2.1"), update.version_key("0.2.0"))
        self.assertGreater(update.version_key("1.0.0"), update.version_key("v0.9.9"))
        self.assertEqual(update.version_key("v0.2.0"), (0, 2, 0))
        self.assertLess(update.version_key("nightly"), update.version_key("0.0.1"))

    def test_newer_tag_reports_available(self):
        payload = json.dumps([{"name": "v0.2.1"}]).encode("utf-8")
        with patch.object(update.urllib.request, "urlopen", return_value=FakeResponse(payload)):
            result = update.check_latest()
        self.assertTrue(result["ok"])
        self.assertTrue(result["available"])
        self.assertEqual(result["latest"], "0.2.1")
        self.assertEqual(result["current"], version.__version__)

    def test_same_tag_reports_not_available(self):
        payload = json.dumps([{"name": f"v{version.__version__}"}]).encode("utf-8")
        with patch.object(update.urllib.request, "urlopen", return_value=FakeResponse(payload)):
            result = update.check_latest()
        self.assertTrue(result["ok"])
        self.assertFalse(result["available"])

    def test_network_failure_is_reported(self):
        with patch.object(update.urllib.request, "urlopen", side_effect=OSError("offline")):
            result = update.check_latest()
        self.assertFalse(result["ok"])
        self.assertIn("offline", result["error"])
        self.assertFalse(result["available"])

    def test_progress_callback_called(self):
        seen = []
        payload = json.dumps([{"name": "v0.2.1"}]).encode("utf-8")
        with patch.object(update.urllib.request, "urlopen", return_value=FakeResponse(payload)):
            update.check_latest(on_progress=seen.append)
        self.assertEqual(seen, ["업데이트 확인 중…"])


if __name__ == "__main__":
    unittest.main()
