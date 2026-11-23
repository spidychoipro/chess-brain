"""엔진 경로 해석: 번들 엔진을 못 찾아 분석이 막히지 않게 하는 회귀 테스트."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import engine


class EngineResolveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        bundled = self.root / "engines" / "stockfish"
        bundled.mkdir(parents=True)
        self.exe = bundled / "stockfish-windows-x86-64-universal.exe"
        self.exe.write_bytes(b"stub")

    def tearDown(self):
        self.temp.cleanup()

    def _patched(self):
        return (
            patch.object(engine, "_app_dirs", return_value=[str(self.root)]),
            patch.object(engine, "_common_dirs", return_value=[]),
            patch.object(engine.shutil, "which", return_value=None),
        )

    def test_finds_bundled_engine_one_level_down(self):
        a, b, c = self._patched()
        with a, b, c:
            self.assertEqual(engine.find_stockfish(fast=True), str(self.exe))

    def test_empty_config_falls_back_to_bundled(self):
        a, b, c = self._patched()
        with a, b, c:
            self.assertEqual(engine.resolve_engine_path(""), str(self.exe))

    def test_stale_config_falls_back_to_bundled(self):
        a, b, c = self._patched()
        with a, b, c:
            stale = str(self.root / "old-pc" / "stockfish.exe")
            self.assertEqual(engine.resolve_engine_path(stale), str(self.exe))

    def test_valid_absolute_path_is_kept(self):
        self.assertTrue(engine.engine_available(str(self.exe)))
        self.assertEqual(engine.resolve_engine_path(str(self.exe)), str(self.exe))

    def test_relative_path_resolves_from_app_root(self):
        a, b, c = self._patched()
        rel = os.path.join("engines", "stockfish", self.exe.name)
        with a, b, c, patch("core.utils.project_root", return_value=self.root):
            self.assertEqual(engine.resolve_engine_path(rel), str(self.exe.resolve()))


if __name__ == "__main__":
    unittest.main()
