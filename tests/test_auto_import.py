"""방치한 동안 쌓인 대국을 자동으로 따라잡는 경로에 대한 회귀 테스트."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess.pgn
from core import db, parser, pipeline, rclone, utils


def pgn(moves, white='Me', black='Other'):
    return (
        f'[White "{white}"]\n[Black "{black}"]\n'
        f'[Date "2026.11.20"]\n[Result "*"]\n\n{moves} *'
    )


def game_id(text):
    return parser.game_id(chess.pgn.read_game(io.StringIO(text)))


class AutoImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.patch = patch('core.utils.project_root', return_value=self.root)
        self.patch.start()
        db.init_db()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def cfg(self, folder):
        return {
            'chesscom': {'username': '', 'fallback_color': 'white', 'auto_fetch': False},
            'local': {'pgn_folder': str(folder)},
            'rclone': {'binary': '', 'config': '', 'remote': '', 'mount_point': ''},
            'stockfish': {'path': '', 'depth': 12},
        }

    def test_game_with_no_user_lines_is_retried_later(self):
        text = pgn('1. e4 e5 2. Nf3 Nc6')
        gid = game_id(text)
        cfg = self.cfg(self.root / 'pgn')

        # 아이디/색 문제로 내 수가 0개로 읽힌 상황을 흉내낸다.
        with patch.object(pipeline.parser, 'extract_user_lines', return_value=[]):
            first = pipeline.ingest_pgn_text(text, 'human', cfg)

        self.assertEqual(first['skipped'], 1)
        self.assertEqual(first['problems'], 0)
        self.assertFalse(db.is_game_processed(gid))

        # 설정을 고친 뒤 다시 읽으면 이번엔 문제가 생기고 처리 완료가 된다.
        second = pipeline.ingest_pgn_text(text, 'human', cfg)
        self.assertGreater(second['problems'], 0)
        self.assertTrue(db.is_game_processed(gid))

    def test_auto_catch_up_reads_local_folder(self):
        folder = self.root / 'pgn'
        (folder / 'Human').mkdir(parents=True)
        (folder / 'Human' / 'a.pgn').write_text(pgn('1. e4 e5 2. Nf3 Nc6'), encoding='utf-8')
        (folder / 'Human' / 'b.pgn').write_text(pgn('1. d4 d5 2. c4 e6'), encoding='utf-8')

        result = pipeline.auto_catch_up(self.cfg(folder))

        self.assertEqual(result['new_games'], 2)
        self.assertEqual(result['files'], 2)
        self.assertGreater(result['problems'], 0)
        self.assertEqual(result['warnings'], [])

    def test_foreign_game_does_not_stop_later_games(self):
        folder = self.root / 'pgn'
        folder.mkdir()
        mixed = (
            pgn('1. e4 e5 2. Nf3 Nc6', white='SomeoneElse')
            + '\n\n'
            + pgn('1. d4 d5 2. c4 e6')
        )
        (folder / 'a.pgn').write_text(mixed, encoding='utf-8')
        cfg = self.cfg(folder)
        cfg['chesscom']['username'] = 'Me'

        result = pipeline.auto_catch_up(cfg)

        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['new_games'], 1)
        self.assertGreater(result['problems'], 0)

    def test_auto_catch_up_missing_folder_warns_instead_of_raising(self):
        result = pipeline.auto_catch_up(self.cfg(self.root / 'does-not-exist'))
        self.assertTrue(result['warnings'])
        self.assertEqual(result['new_games'], 0)

    def test_drive_failure_does_not_block_local_import(self):
        folder = self.root / 'pgn'
        folder.mkdir()
        (folder / 'a.pgn').write_text(pgn('1. e4 e5 2. Nf3 Nc6'), encoding='utf-8')
        cfg = self.cfg(folder)
        cfg['rclone']['remote'] = 'gdrive:test'
        dummy = self.root / 'rclone.exe'
        dummy.write_bytes(b'')
        cfg['rclone']['binary'] = str(dummy)

        with patch.object(rclone, 'find_binary', return_value=str(dummy)), \
             patch.object(rclone, 'run_copy', return_value=1):
            result = pipeline.auto_catch_up(cfg)

        self.assertEqual(result['new_games'], 1)
        self.assertFalse(result['pulled'])
        self.assertTrue(any('받기 실패' in w for w in result['warnings']))

    def test_dead_mount_path_warns_instead_of_raising(self):
        missing = self.root / 'X'
        cfg = self.cfg(missing)
        cfg['rclone']['remote'] = 'gdrive:test'
        dummy = self.root / 'rclone.exe'
        dummy.write_bytes(b'')
        cfg['rclone']['binary'] = str(dummy)

        with patch.object(rclone, 'find_binary', return_value=str(dummy)), \
             patch.object(rclone, 'normalize_mount_point', return_value=str(missing)), \
             patch.object(pipeline, 'mount_drive', side_effect=RuntimeError('테스트 실패')):
            result = pipeline.auto_catch_up(cfg)

        self.assertTrue(any('다시 붙이기 실패' in w for w in result['warnings']))
        self.assertTrue(any('찾을 수 없어요' in w for w in result['warnings']))


if __name__ == '__main__':
    unittest.main()
