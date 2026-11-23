"""chess.com 수집 도구 연결 회귀 테스트."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import chesscom, config as cfg_mod


class ChesscomFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.script = self.root / 'chess_pgn_sync.py'
        self.script.write_text('# stub', encoding='utf-8')
        (self.root / 'python.cmd').write_text(
            '@echo off\n"C:\\Python\\python.exe" %*\n', encoding='utf-8'
        )
        self.cfg = cfg_mod.load_config()
        cfg_mod.set_(self.cfg, 'chesscom.sync_script', str(self.script))
        cfg_mod.set_(self.cfg, 'chesscom.python', 'python-stub')
        cfg_mod.set_(self.cfg, 'chesscom.auto_fetch', True)

    def tearDown(self):
        self.temp.cleanup()

    def test_full_run_uses_all_flag_and_parses_saved_count(self):
        done = subprocess.CompletedProcess([], 0, stdout='새로 저장 300개\n', stderr='')
        with patch.object(chesscom.subprocess, 'run', return_value=done) as run:
            result = chesscom.fetch_recent(self.cfg, full=True)
        self.assertTrue(result['ran'])
        self.assertTrue(result['ok'])
        self.assertEqual(result['new'], 300)
        self.assertEqual(run.call_args.args[0][-1], '--all')

    def test_recent_run_omits_all_flag(self):
        done = subprocess.CompletedProcess([], 0, stdout='새로 저장 30개', stderr='')
        with patch.object(chesscom.subprocess, 'run', return_value=done) as run:
            result = chesscom.fetch_recent(self.cfg, full=False)
        self.assertEqual(result['new'], 30)
        self.assertNotIn('--all', run.call_args.args[0])

    def test_disabled_does_not_run_anything(self):
        cfg_mod.set_(self.cfg, 'chesscom.auto_fetch', False)
        with patch.object(chesscom.subprocess, 'run') as run:
            result = chesscom.fetch_recent(self.cfg)
        self.assertFalse(result['ran'])
        run.assert_not_called()

    def test_failure_becomes_warning_not_exception(self):
        done = subprocess.CompletedProcess([], 1, stdout='', stderr='boom')
        with patch.object(chesscom.subprocess, 'run', return_value=done):
            result = chesscom.fetch_recent(self.cfg)
        self.assertFalse(result['ok'])
        self.assertIn('boom', result['error'])

    def test_timeout_does_not_raise(self):
        with patch.object(
            chesscom.subprocess, 'run', side_effect=subprocess.TimeoutExpired('x', 1)
        ):
            result = chesscom.fetch_recent(self.cfg)
        self.assertFalse(result['ok'])
        self.assertIn('900초', result['error'])

    def test_missing_script_reports_error(self):
        cfg_mod.set_(self.cfg, 'chesscom.sync_script', str(self.root / 'none.py'))
        result = chesscom.fetch_recent(self.cfg)
        self.assertFalse(result['ok'])
        self.assertIn('찾지 못', result['error'])

    def test_python_is_read_from_python_cmd_when_unset(self):
        cfg_mod.set_(self.cfg, 'chesscom.python', '')
        with patch.object(chesscom.Path, 'is_file', return_value=True):
            self.assertEqual(chesscom._python_for(str(self.script), self.cfg), r'C:\Python\python.exe')


if __name__ == '__main__':
    unittest.main()
