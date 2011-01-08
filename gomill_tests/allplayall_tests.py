"""Tests for allplayalls.py"""

from textwrap import dedent

from gomill import competitions
from gomill import allplayalls
from gomill.gtp_games import Game_result
from gomill.game_jobs import Game_job, Game_job_result
from gomill.competitions import (
    Player_config, NoGameAvailable, CompetitionError, ControlFileError)
from gomill.allplayalls import Competitor_config

from gomill_tests import competition_test_support
from gomill_tests import gomill_test_support
from gomill_tests import test_framework
from gomill_tests.competition_test_support import (
    fake_response, check_screen_report)

def make_tests(suite):
    suite.addTests(gomill_test_support.make_simple_tests(globals()))


def check_short_report(tc, comp,
                       expected_grid, expected_matchups, expected_players,
                       competition_name="testcomp"):
    """Check that an allplayall's short report is as expected."""
    expected = ("allplayall: %s\n\n%s\n%s\n%s\n" %
                (competition_name, expected_grid,
                 expected_matchups, expected_players))
    tc.assertMultiLineEqual(competition_test_support.get_short_report(comp),
                            expected)

class Allplayall_fixture(test_framework.Fixture):
    """Fixture setting up a Allplayall.

    attributes:
      comp       -- Allplayall

    """
    def __init__(self, tc, config=None):
        if config is None:
            config = default_config()
        self.tc = tc
        self.comp = allplayalls.Allplayall('testcomp')
        self.comp.initialise_from_control_file(config)
        self.comp.set_clean_status()

    def check_screen_report(self, expected):
        """Check that the screen report is as expected."""
        check_screen_report(self.tc, self.comp, expected)

    def check_short_report(self, *args, **kwargs):
        """Check that the short report is as expected."""
        check_short_report(self.tc, self.comp, *args, **kwargs)


def default_config():
    return {
        'players' : {
            't1' : Player_config("test1"),
            't2' : Player_config("test2"),
            't3' : Player_config("test3"),
            },
        'board_size' : 13,
        'komi' : 7.5,
        'competitors' : [
            Competitor_config('t1'),
            Competitor_config('t2'),
            't3',
            ],
        }



def test_default_config(tc):
    comp = allplayalls.Allplayall('test')
    config = default_config()
    comp.initialise_from_control_file(config)
    tc.assertListEqual(comp.get_matchup_ids(),
                       ['AvB', 'AvC', 'BvC'])
    mBvC = comp.get_matchup('BvC')
    tc.assertEqual(mBvC.p1, 't2')
    tc.assertEqual(mBvC.p2, 't3')
    tc.assertEqual(mBvC.board_size, 13)
    tc.assertEqual(mBvC.komi, 7.5)
    tc.assertEqual(mBvC.move_limit, 1000)
    tc.assertEqual(mBvC.scorer, 'players')
    tc.assertEqual(mBvC.number_of_games, None)
    tc.assertIs(mBvC.alternating, True)
    tc.assertIs(mBvC.handicap, None)
    tc.assertEqual(mBvC.handicap_style, 'fixed')

def test_basic_config(tc):
    comp = allplayalls.Allplayall('test')
    config = default_config()
    config['description'] = "default\nconfig"
    config['board_size'] = 9
    config['komi'] = 0.5
    config['move_limit'] = 200
    config['scorer'] = 'internal'
    config['number_of_games'] = 20
    comp.initialise_from_control_file(config)
    tc.assertEqual(comp.description, "default\nconfig")
    mBvC = comp.get_matchup('BvC')
    tc.assertEqual(mBvC.p1, 't2')
    tc.assertEqual(mBvC.p2, 't3')
    tc.assertEqual(mBvC.board_size, 9)
    tc.assertEqual(mBvC.komi, 0.5)
    tc.assertEqual(mBvC.move_limit, 200)
    tc.assertEqual(mBvC.scorer, 'internal')
    tc.assertEqual(mBvC.number_of_games, 20)
    tc.assertIs(mBvC.alternating, True)
    tc.assertIs(mBvC.handicap, None)
    tc.assertEqual(mBvC.handicap_style, 'fixed')

def test_duplicate_player(tc):
    comp = allplayalls.Allplayall('test')
    config = default_config()
    config['competitors'].append('t2')
    tc.assertRaisesRegexp(
        ControlFileError, "duplicate competitor: t2",
        comp.initialise_from_control_file, config)

def test_game_id_format(tc):
    config = default_config()
    config['number_of_games'] = 1000
    fx = Allplayall_fixture(tc, config)
    tc.assertEqual(fx.comp.get_game().game_id, 'AvB_000')

def test_get_player_checks(tc):
    fx = Allplayall_fixture(tc)
    checks = fx.comp.get_player_checks()
    tc.assertEqual(len(checks), 3)
    tc.assertEqual(checks[0].board_size, 13)
    tc.assertEqual(checks[0].komi, 7.5)
    tc.assertEqual(checks[0].player.code, "t1")
    tc.assertEqual(checks[0].player.cmd_args, ['test1'])
    tc.assertEqual(checks[1].player.code, "t2")
    tc.assertEqual(checks[1].player.cmd_args, ['test2'])
    tc.assertEqual(checks[2].player.code, "t3")
    tc.assertEqual(checks[2].player.cmd_args, ['test3'])

def test_play(tc):
    fx = Allplayall_fixture(tc)
    tc.assertIsNone(fx.comp.description)

    job1 = fx.comp.get_game()
    tc.assertIsInstance(job1, Game_job)
    tc.assertEqual(job1.game_id, 'AvB_0')
    tc.assertEqual(job1.player_b.code, 't1')
    tc.assertEqual(job1.player_w.code, 't2')
    tc.assertEqual(job1.board_size, 13)
    tc.assertEqual(job1.komi, 7.5)
    tc.assertEqual(job1.move_limit, 1000)
    tc.assertEqual(job1.game_data, ('AvB', 0))
    tc.assertIsNone(job1.sgf_filename)
    tc.assertIsNone(job1.sgf_dirname)
    tc.assertIsNone(job1.void_sgf_dirname)
    tc.assertEqual(job1.sgf_event, 'testcomp')
    tc.assertIsNone(job1.gtp_log_pathname)

    job2 = fx.comp.get_game()
    tc.assertIsInstance(job2, Game_job)
    tc.assertEqual(job2.game_id, 'AvC_0')
    tc.assertEqual(job2.player_b.code, 't1')
    tc.assertEqual(job2.player_w.code, 't3')

    # FIXME: Use fake_response?
    result1 = Game_result({'b' : 't1', 'w' : 't2'}, 'b')
    result1.sgf_result = "B+8.5"
    response1 = Game_job_result()
    response1.game_id = job1.game_id
    response1.game_result = result1
    response1.engine_names = {
        't1' : 't1 engine:v1.2.3',
        't2' : 't2 engine',
        }
    response1.engine_descriptions = {
        't1' : 't1 engine:v1.2.3',
        't2' : 't2 engine\ntest \xc2\xa3description',
        }
    response1.game_data = job1.game_data
    fx.comp.process_game_result(response1)

    expected_grid = dedent("""\
          A   B   C
    A t1     1-0 0-0
    B t2 0-1     0-0
    C t3 0-0 0-0
    """)
    expected_matchups = dedent("""\
    t1 v t2 (1 games)
    board size: 13   komi: 7.5
         wins
    t1      1 100.00%   (black)
    t2      0   0.00%   (white)
    """)
    expected_players = dedent("""\
    player t1: t1 engine:v1.2.3
    player t2: t2 engine
    test \xc2\xa3description
    """)
    fx.check_screen_report(expected_grid)
    fx.check_short_report(expected_grid, expected_matchups, expected_players)

    tc.assertListEqual(fx.comp.get_matchup_results('AvB'), [('AvB_0', result1)])
