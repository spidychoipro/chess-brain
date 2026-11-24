"""커리큘럼: 테마 분류·해설·백필·추천 회귀 테스트."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess

from core import curriculum, db


class CurriculumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.patcher = patch('core.utils.project_root', return_value=Path(self.temp.name))
        self.patcher.start()
        db.init_db()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def item(self, fen, **kwargs):
        base = dict(
            fen=fen, ply=10, my_san='a3', best_san='e4', reply_san='e5',
            loss=2.0, eval_before=1.0, eval_after=-1.0,
            best_line=[], reply_line=['a2a3', 'e7e5'],
            mate_before=None, mate_after=None,
        )
        base.update(kwargs)
        return base

    def test_missed_mate_and_allowed_mate_are_separate(self):
        self.assertEqual(
            curriculum.classify(self.item(chess.STARTING_FEN, best_san='Qh7#')),
            'missed_mate',
        )
        self.assertEqual(
            curriculum.classify(self.item(chess.STARTING_FEN, reply_san='Ra1#')),
            'allowed_mate',
        )

    def test_hanging_piece(self):
        fen = '5r2/8/8/8/8/5N2/PPPP1PPP/RNBQKB1R w - - 0 1'
        item = self.item(fen, reply_line=['a2a3', 'f8f3'], reply_san='Rxf3')
        self.assertEqual(curriculum.classify(item), 'hanging')
        self.assertIn('나이트', curriculum.explain(item, 'hanging'))

    def test_back_rank(self):
        fen = '4r1k1/pppp1ppp/8/8/8/8/PPPP4/5RK1 w - - 0 1'
        self.assertEqual(
            curriculum.classify(self.item(fen, reply_line=['a2a3', 'e8e1'])),
            'back_rank',
        )

    def test_missed_capture(self):
        fen = '4k3/8/8/3q4/8/4P3/8/3RK3 w - - 0 1'
        item = self.item(fen, best_line=['d1d5'], best_san='Rxd5')
        self.assertEqual(curriculum.classify(item), 'missed_capture')

    def test_endgame_fallback(self):
        self.assertEqual(
            curriculum.classify(self.item('8/8/8/4k3/8/4K3/8/8 w - - 0 1')),
            'endgame',
        )

    def test_lost_position_detection(self):
        self.assertTrue(curriculum.is_lost_position(self.item(chess.STARTING_FEN, eval_before=-8)))
        self.assertFalse(curriculum.is_lost_position(self.item(chess.STARTING_FEN, eval_before=2)))

    def test_explanation_mentions_best_move(self):
        text = curriculum.explain(self.item(chess.STARTING_FEN, best_san='Nf3'), 'tactic')
        self.assertIn('Nf3', text)

    def test_backfill_tags_existing_mistakes(self):
        mid = db.add_mistake(
            fen=chess.STARTING_FEN, context_sans='', my_san='a3', best_san='e4',
            eval_before=1, eval_after=-1, loss=2, source_game_id='g',
            source='human', ply=1, best_line=['e2e4'], reply_line=['a2a3', 'e7e5'],
        )
        row = db.get_mistake(mid)
        self.assertTrue(row['theme'])
        self.assertTrue(row['explanation'])
        self.assertTrue(row['created_at'] > 0)
        stats = curriculum.theme_stats()
        self.assertEqual(sum(s['total'] for s in stats), 1)

    def test_lost_position_is_excluded_from_curriculum_but_kept_in_db(self):
        mid = db.add_mistake(
            fen=chess.STARTING_FEN, context_sans='', my_san='a3', best_san='e4',
            eval_before=-9, eval_after=-11, loss=2, source_game_id='g',
            source='human', ply=1,
        )
        self.assertEqual(db.get_mistake(mid)['excluded'], 1)
        self.assertEqual(curriculum.theme_stats(), [])

    def test_recommend_picks_from_weakest_theme(self):
        for i in range(4):
            db.add_mistake(
                fen=f'8/8/8/8/8/8/{i}P6/4K2k w - - 0 1',
                context_sans='', my_san='a3', best_san='e4',
                eval_before=1, eval_after=-1, loss=2, source_game_id=f'g{i}',
                source='human', ply=1, theme='back_rank',
            )
        picks = curriculum.recommend(limit=3, source='human')
        self.assertTrue(picks)
        self.assertTrue(all(p['theme'] == 'back_rank' for p in picks))


if __name__ == '__main__':
    unittest.main()
