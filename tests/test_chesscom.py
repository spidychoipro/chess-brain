"""chess.com 수집 도구 연결 회귀 테스트."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from queue import Empty
from unittest.mock import patch

from core import chesscom, config as cfg_mod


class FakePopen:
    """도구 출력을 파일처럼 흘려보내는 가짜 프로세스."""

    def __init__(self, lines, code=0):
        self.stdout = io.StringIO(''.join(f'{line}\n' for line in lines))
        self._code = code

    def poll(self):
        return None

    def wait(self, timeout=None):
        return self._code

    def kill(self):
        self._code = -9


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
        self.log_patch = patch.object(chesscom, '_append_log')
        self.log_patch.start()

    def tearDown(self):
        self.log_patch.stop()
        self.temp.cleanup()

    def _run(self, lines=('최근 7일 확인', '새로 저장 300개'), code=0, **kwargs):
        fake = FakePopen(lines, code)
        with patch.object(chesscom.subprocess, 'Popen', return_value=fake) as popen:
            result = chesscom.fetch_recent(self.cfg, **kwargs)
        return result, popen

    def test_full_run_uses_all_flag_and_parses_saved_count(self):
        result, popen = self._run(full=True)
        self.assertTrue(result['ran'])
        self.assertTrue(result['ok'])
        self.assertEqual(result['new'], 300)
        args = popen.call_args.args[0]
        self.assertIn('--all-humans', args)
        self.assertNotIn('--all', args)
        self.assertIn('--no-drive-list', args)

    def test_recent_run_omits_all_flag(self):
        result, popen = self._run(lines=('새로 저장 30개',), full=False)
        self.assertEqual(result['new'], 30)
        self.assertNotIn('--all', popen.call_args.args[0])
        self.assertIn('--no-drive-list', popen.call_args.args[0])

    def test_output_lines_are_streamed_live(self):
        seen = []
        self._run(lines=('드라이브 목록 읽는 중', '게임 30개 받음', '새로 저장 30개'),
                  on_progress=seen.append)
        self.assertIn('드라이브 목록 읽는 중', seen)
        self.assertIn('게임 30개 받음', seen)

    def test_disabled_does_not_run_anything(self):
        cfg_mod.set_(self.cfg, 'chesscom.auto_fetch', False)
        with patch.object(chesscom.subprocess, 'Popen') as popen:
            result = chesscom.fetch_recent(self.cfg)
        self.assertFalse(result['ran'])
        popen.assert_not_called()

    def test_failure_becomes_warning_not_exception(self):
        result, _ = self._run(lines=('boom',), code=1)
        self.assertFalse(result['ok'])
        self.assertIn('boom', result['error'])

    def test_timeout_does_not_raise(self):
        fake = FakePopen([])
        with patch.object(chesscom.subprocess, 'Popen', return_value=fake), \
             patch.object(chesscom.Queue, 'get', side_effect=Empty), \
             patch.object(chesscom.time, 'monotonic', side_effect=[0, 1000]):
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
            self.assertEqual(
                chesscom._python_for(str(self.script), self.cfg), r'C:\Python\python.exe'
            )


if __name__ == '__main__':
    unittest.main()
