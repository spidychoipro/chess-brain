"""설정/DB 롤링 백업 회귀 테스트."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import backup, utils


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.patch = patch('core.utils.project_root', return_value=self.root)
        self.patch.start()
        backup.reset_for_tests()

    def tearDown(self):
        backup.reset_for_tests()
        self.patch.stop()
        self.temp.cleanup()

    def test_rotate_keeps_copies_of_db_and_config(self):
        (self.root / 'data').mkdir()
        (self.root / 'config').mkdir()
        (self.root / 'data' / 'app.db').write_bytes(b'db')
        (self.root / 'config' / 'config.json').write_text('{}', encoding='utf-8')

        backup.rotate()

        folder = backup.backup_dir()
        self.assertEqual(len(list(folder.glob('app-*.db'))), 1)
        self.assertEqual(len(list(folder.glob('config-*.json'))), 1)
        self.assertEqual(list(folder.glob('app-*.db'))[0].read_bytes(), b'db')

    def test_rotate_runs_once_per_process(self):
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'app.db').write_bytes(b'db')
        backup.rotate()
        backup.rotate()
        self.assertEqual(len(list(backup.backup_dir().glob('app-*.db'))), 1)

    def test_prune_keeps_only_five_newest(self):
        folder = backup.backup_dir()
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(8):
            (folder / f'app-20260101-00000{i}.db').write_bytes(b'x')
        backup._prune(folder, 'app-*.db')
        self.assertEqual(len(list(folder.glob('app-*.db'))), backup.KEEP)

    def test_backup_failure_never_breaks_the_app(self):
        backup.reset_for_tests()
        with patch.object(utils, 'data_dir', side_effect=OSError('disk full')):
            backup.rotate()  # 예외를 던지면 안 된다


if __name__ == '__main__':
    unittest.main()
