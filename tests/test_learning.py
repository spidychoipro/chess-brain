"""Regression checks run against disposable data, never the learner's DB."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chess
import chess.engine
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from core import db, parser, pipeline, config, utils, sr, engine
from ui.board import ChessBoard
from ui.widgets import ReviewPanel
from ui.notation_pool import stage3_pool, item_id

APP = QApplication.instance() or QApplication([])


def pgn(moves, white='Me', black='Other', link=''):
    return f'[White "{white}"]\n[Black "{black}"]\n[Date "2026.10.17"]\n[Result "*"]\n[Link "{link}"]\n\n{moves} *'


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.patch = patch('core.utils.project_root', return_value=self.root)
        self.patch.start()
        db.init_db()
        self.widgets = []

    def tearDown(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        APP.processEvents()
        self.patch.stop()
        self.temp.cleanup()

    def mistake(self, **kwargs):
        values = dict(fen=chess.STARTING_FEN, context_sans='', my_san='a3', best_san='e4',
                      eval_before=1, eval_after=-1, loss=2, source_game_id='game', source='human', ply=1,
                      reply_san='e5', accepted_sans=['e4', 'd4'], best_line=['e2e4','e7e5'],
                      reply_line=['a2a3','e7e5'])
        values.update(kwargs)
        return db.add_mistake(**values)

    def panel(self, mid, **kwargs):
        panel = ReviewPanel([db.get_mistake(mid)], 'mistake', **kwargs)
        self.widgets.append(panel)
        return panel

    def test_board_orientation_and_all_click_coordinates(self):
        board = ChessBoard()
        self.widgets.append(board)
        board.resize(480, 480)
        for flipped, bottom_left, bottom_right in ((False, chess.A1, chess.H1), (True, chess.H8, chess.A8)):
            board.set_position(chess.STARTING_FEN, flipped=flipped)
            self.assertLess(board._sq_rect(bottom_left).x(), board._sq_rect(bottom_right).x())
            for square in chess.SQUARES:
                self.assertEqual(board._point_square(board._sq_rect(square).center()), square)
        board.set_position(chess.STARTING_FEN)
        played = []
        board.moveMade.connect(played.append)
        board.show()
        QTest.mouseClick(board, Qt.LeftButton, pos=board._sq_rect(chess.E2).center().toPoint())
        QTest.mouseClick(board, Qt.LeftButton, pos=board._sq_rect(chess.E4).center().toPoint())
        self.assertEqual(played, ['e4'])

    def test_future_reviews_excluded_and_new_and_overdue_included(self):
        mid = self.mistake()
        self.assertEqual([r['id'] for r in db.mistakes_due()], [mid])
        db.update_mistake_sr(mid, sr.review_state(sr.SRState(), sr.GRADE_GOOD))
        self.assertEqual(db.mistakes_due(), [])
        self.assertEqual(db.mistake_counts()['unreviewed'], 0)
        with closing(db.connect()) as conn:
            conn.execute('UPDATE mistakes SET due_at=1 WHERE id=?', (mid,))
            conn.commit()
        self.assertEqual([r['id'] for r in db.mistakes_due()], [mid])

    def test_future_problems_excluded(self):
        pid = db.add_problem(fen=chess.STARTING_FEN, context_sans='', target_san='e4', source_game_id='g', source='human', ply=1, origin='line')
        self.assertEqual(len(db.problems_due(origin='line')), 1)
        self.assertEqual(db.problems_due(origin='mistake'), [])
        db.update_problem_sr(pid, sr.review_state(sr.SRState(), sr.GRADE_GOOD))
        self.assertEqual(db.problems_due(), [])

    def test_grade_filter_applied_before_limit(self):
        self.mistake(loss=.9)
        blunder = self.mistake(loss=3, source_game_id='g2')
        self.assertEqual([r['id'] for r in db.mistakes_due(limit=1, grade='blunder')], [blunder])

    def test_reveal_retry_keeps_ten_minute_schedule_and_single_event(self):
        mid = self.mistake()
        panel = self.panel(mid)
        panel._reveal()
        first = db.get_mistake(mid)
        self.assertAlmostEqual(first['due_at'] - utils.now_ts(), 600, delta=2)
        panel._show_current()
        panel._on_move('e4')
        second = db.get_mistake(mid)
        self.assertEqual(first['due_at'], second['due_at'])
        self.assertEqual(second['correct'], 0)
        self.assertEqual(second['wrong'], 1)
        self.assertEqual(db.recent_review_stats()['total'], 1)

    def test_correct_alternative_and_no_automatic_advance(self):
        mid = self.mistake()
        panel = self.panel(mid)
        panel._on_move('d4')
        self.assertEqual(db.get_mistake(mid)['correct'], 1)
        self.assertEqual(panel.done, 0)
        self.assertTrue(panel._feedback)
        panel._after_feedback()
        self.assertEqual(panel.done, 1)

    def test_wrong_then_correct_not_first_try(self):
        mid = self.mistake()
        panel = self.panel(mid)
        panel._on_move('Nf3')
        panel._on_move('e4')
        self.assertEqual(db.recent_review_stats()['first_try'], 0)

    def test_practice_never_changes_schedule_or_statistics(self):
        mid = self.mistake()
        before = db.get_mistake(mid)
        panel = self.panel(mid, practice=True)
        panel._reveal()
        panel._show_current()
        panel._on_move('e4')
        self.assertEqual(db.get_mistake(mid), before)
        self.assertEqual(db.recent_review_stats()['total'], 0)

    def test_replay_forward_and_backward(self):
        panel = self.panel(self.mistake())
        panel._reveal()
        panel._start_replay(False)
        panel._step_replay(1)
        self.assertEqual(panel.board.board.piece_at(chess.A3), chess.Piece(chess.PAWN, chess.WHITE))
        panel._step_replay(1)
        self.assertEqual(panel.board.board.piece_at(chess.E5), chess.Piece(chess.PAWN, chess.BLACK))
        panel._step_replay(-1)
        self.assertIsNone(panel.board.board.piece_at(chess.E5))

    def test_different_games_same_headers_and_rescan(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        a = pipeline.ingest_pgn_text(pgn('1. e4 e5 2. Nf3 Nc6'), 'human', cfg)
        b = pipeline.ingest_pgn_text(pgn('1. d4 d5 2. c4 e6'), 'human', cfg)
        again = pipeline.ingest_pgn_text(pgn('1. e4 e5 2. Nf3 Nc6'), 'human', cfg)
        self.assertEqual((a['new_games'], b['new_games'], again['new_games']), (1, 1, 0))
        self.assertEqual(db.game_counts()['total'], 2)

    def test_chesscom_ids_unchanged(self):
        game = next(parser.iter_games(pgn('1. e4 e5', link='https://www.chess.com/game/live/123')))
        self.assertEqual(parser.game_id(game), parser.legacy_game_id(game))

    def test_exact_username_and_unknown_owner_rejected(self):
        game = next(parser.iter_games(pgn('1. e4 e5', white='player2', black='player')))
        self.assertEqual(parser.user_color(game, 'player'), chess.BLACK)
        with self.assertRaises(ValueError):
            parser.user_color(game, 'someone')

    def test_pgn_errors_not_marked_processed(self):
        with self.assertRaises(ValueError):
            list(parser.iter_games(pgn('1. e4 e5 2. Ke4')))

    def test_legacy_identity_migration_preserves_review_state(self):
        game = next(parser.iter_games(pgn('1. e4 e5 2. Nf3 Nc6')))
        old, new = parser.legacy_game_id(game), parser.game_id(game)
        db.upsert_game(old, 'human', 'local:old')
        line = parser.extract_user_lines(game, 'human', min_ply=2)[0]
        pid = db.add_problem(fen=line.fen_before, context_sans='', target_san=line.san, source_game_id=old, source='human', ply=line.ply, origin='line')
        state = sr.review_state(sr.SRState(), sr.GRADE_GOOD)
        db.update_problem_sr(pid, state)
        db.mark_game_processed(old)
        pipeline.ingest_pgn_text(str(game), 'human', config.DEFAULTS)
        self.assertEqual(db.game_counts()['total'], 1)
        self.assertEqual(db.get_problem(pid)['source_game_id'], new)
        self.assertEqual(db.get_problem(pid)['due_at'], state.due_at)

    def test_additive_migration_keeps_existing_records(self):
        mid = self.mistake()
        before = db.get_mistake(mid)
        db.init_db()
        db.init_db()
        self.assertEqual(db.get_mistake(mid), before)

    def test_notation_unique_and_canonical_disambiguation(self):
        pool = stage3_pool()
        self.assertEqual(len(pool), len(set(map(item_id, pool))))
        self.assertEqual(next(it['san'] for it in pool if it['concept'] == 'disambig_both'), 'Qa1b2')

    def test_stage1_requires_pawn_and_both_directions(self):
        from ui.notation import Stage1Pieces
        stage = Stage1Pieces()
        self.widgets.append(stage)
        for _ in range(35):
            stage._record(True, 'letter2glyph:6')
        self.assertFalse(stage.prog.passed)
        for kind in ('letter2glyph', 'glyph2letter'):
            for pt in chess.PIECE_TYPES:
                stage._record(True, f'{kind}:{pt}')
        self.assertTrue(stage.prog.passed)

    def test_stage4_visible_board_tracks_position(self):
        from ui.notation import Stage4Blind
        stage = Stage4Blind()
        self.widgets.append(stage)
        stage.start()
        stage.idx = 3
        stage._show()
        self.assertEqual(stage.board.board.fen(), stage.steps[3]['fen'])
        self.assertFalse(stage.board.flipped)

    def test_main_tabs_and_mode_specific_controls(self):
        from ui.main import MainWindow
        window = MainWindow()
        self.widgets.append(window)
        self.assertEqual(window.nav.currentRow(), 0)
        for i in range(5):
            window.nav.setCurrentRow(i)
            APP.processEvents()
        training = window._page('training')
        training.cb_mode.setCurrentIndex(training.cb_mode.findData('notation'))
        self.assertTrue(training.cb_source.isHidden())
        training.cb_mode.setCurrentIndex(training.cb_mode.findData('recall'))
        self.assertFalse(training.cb_source.isHidden())

    def test_home_is_first_page_with_working_actions(self):
        from ui.main import MainWindow, PAGES
        from ui.tabs.home import HomeTab

        self.assertEqual(PAGES[0][1], 'home')
        window = MainWindow()
        self.widgets.append(window)
        self.assertIs(window.stack.currentWidget(), window._page('home'))

        home = HomeTab()
        self.widgets.append(home)
        chosen = []
        home.analyze.connect(chosen.append)
        home.btn_human.click()
        home.btn_bot.click()
        home.btn_all.click()
        self.assertEqual(chosen, ['human', 'bot', 'both'])
        self.assertFalse(home.btn_review.isHidden())
        self.assertFalse(home.btn_import.isHidden())

    def test_mistakes_analysis_buttons_and_progress(self):
        from ui.tabs.mistakes import MistakesTab

        tab = MistakesTab()
        self.widgets.append(tab)
        with patch.object(tab, '_analyze') as analyze:
            tab.btn_analyze_h.click()
            tab.btn_analyze_b.click()
            tab.btn_analyze_all.click()
        self.assertEqual([call.args[0] for call in analyze.call_args_list],
                         ['human', 'bot', 'both'])

        tab._on_progress(2, 5, '분석 중')
        self.assertEqual(tab.bar.maximum(), 5)
        self.assertEqual(tab.bar.value(), 2)
        self.assertIn('분석 중', tab.lbl_progress.text())

    def test_ux_checklist_and_progress_feedback(self):
        from ui.tabs.home import HomeTab
        from ui.tabs.mistakes import MistakesTab
        from ui.worker import PipelineWorker

        home = HomeTab()
        self.widgets.append(home)
        self.assertEqual(len(home._setup_rows), 3)
        self.assertFalse(hasattr(home, "btn_setup_user"))
        self.assertNotIn("위의", home.lbl_now.text())

        tab = MistakesTab()
        self.widgets.append(tab)
        self.assertEqual(tab.bar.format(), "%p%")
        self.assertIsNotNone(tab.lbl_empty)
        tab._on_progress(2, 5, "분석 중")
        self.assertEqual(tab.bar.value(), 2)
        tab._on_ended("cancelled")
        self.assertIn("중단됨", tab.lbl_progress.text())
        self.assertFalse(tab.progress_box.isVisible())

        worker = PipelineWorker(lambda on_progress: {})
        self.assertTrue(hasattr(worker, "ended"))

    def test_selecting_a_future_mistake_is_practice(self):
        from ui.tabs.mistakes import MistakesTab
        mid = self.mistake()
        db.update_mistake_sr(mid, sr.review_state(sr.SRState(), sr.GRADE_GOOD))
        tab = MistakesTab()
        self.widgets.append(tab)
        tab.table.setCurrentCell(0, 0)
        with patch('ui.tabs.mistakes.ReviewDialog') as dialog:
            tab._review_current()
            self.assertTrue(dialog.call_args.kwargs['practice'])


class EngineTests(unittest.TestCase):
    def test_mate_zero_sign(self):
        self.assertEqual(engine._to_pawns(chess.engine.PovScore(chess.engine.Mate(0), chess.BLACK)), 100)
        self.assertEqual(engine._to_pawns(chess.engine.PovScore(chess.engine.Mate(0), chess.WHITE)), -100)

    def test_multipv_alternative_not_a_mistake(self):
        class Fake:
            def candidates(self, board):
                return [{'info': {'score': chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE)},
                         'best_san': san, 'pawns_white': cp/100}
                        for san, cp in [('e4', 40), ('d4', 30), ('Nf3', 10)]]
        self.assertIsNone(engine.find_mistake('', chess.STARTING_FEN, 'd2d4', engine=Fake()))


if __name__ == '__main__':
    unittest.main()
