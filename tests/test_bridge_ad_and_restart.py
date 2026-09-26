"""
Testy dla #129: most przeżywa reklamę międzyplanszową i restart apki po jej śmierci.

Rozpoznanie reklamy testowane na prawdziwych zrzutach z przebiegu 0d96333
(`121_end.png` — reklama, `120_state.png` — ostatnia prawdziwa plansza sprzed niej)
i na zrzucie ekranu głównego po zabiciu procesu z 1bd38fa (`111_state.png`), żeby próg
ciemności nie łapał niczego poza reklamą. Restart korzysta z atrapy `adb`/`in_game` —
bez emulatora.
"""
import os
import sys
import unittest
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
from board import Board
from pieces import PIECE_POOL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "bridge", "runs")

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)


class TestIsAdScreen(unittest.TestCase):
    def test_positive_on_ad_screenshot(self):
        self.assertTrue(bridge.is_ad_screen(_load("0d96333", "121_end.png")))

    def test_negative_on_real_game_state(self):
        self.assertFalse(bridge.is_ad_screen(_load("0d96333", "120_state.png")))

    def test_negative_on_home_screen_after_app_death(self):
        """Ekran główny po zabiciu procesu jest ciemny (tapeta), ale nie tak bardzo jak
        pełnoekranowa reklama — próg nie ma prawa pomylić jednego z drugim."""
        self.assertFalse(bridge.is_ad_screen(_load("1bd38fa", "111_state.png")))


class TestBoardAndTrayEmpty(unittest.TestCase):
    def test_both_empty_is_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        self.assertTrue(bridge.board_and_tray_empty(grid, [None, None, None]))

    def test_tray_piece_present_is_not_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        slots = [([[1]], (0, 0)), None, None]
        self.assertFalse(bridge.board_and_tray_empty(grid, slots))

    def test_board_occupied_is_not_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        grid[0][0] = 1
        self.assertFalse(bridge.board_and_tray_empty(grid, [None, None, None]))


class TestCloseAd(unittest.TestCase):
    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.touch")
    def test_recovers_after_one_tap(self, touch):
        game_img = _load("0d96333", "120_state.png")
        with mock.patch("bridge.screenshot", side_effect=[game_img]):
            self.assertTrue(bridge.close_ad())
        touch.assert_any_call("DOWN", *bridge.AD_CLOSE)
        touch.assert_any_call("UP", *bridge.AD_CLOSE)

    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.touch")
    def test_gives_up_after_tries(self, touch):
        ad_img = _load("0d96333", "121_end.png")
        with mock.patch("bridge.screenshot", side_effect=[ad_img, ad_img, ad_img]):
            self.assertFalse(bridge.close_ad(tries=3))


class TestRestartApp(unittest.TestCase):
    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.adb")
    def test_restarts_without_install_or_tos(self, adb):
        with mock.patch("bridge.in_game", side_effect=[True]):
            self.assertTrue(bridge.restart_app(tries=3, wait=0))
        adb.assert_called_once_with(
            "shell", "monkey", "-p", bridge.PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        for call in adb.call_args_list:
            self.assertNotIn("install", call.args)
            self.assertNotIn("tap", call.args)

    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.adb")
    def test_gives_up_after_limit(self, adb):
        with mock.patch("bridge.in_game", side_effect=[False, False, False]):
            self.assertFalse(bridge.restart_app(tries=3, wait=0))
        self.assertEqual(adb.call_count, 3)


class TestMainSurvivesAdWindow(unittest.TestCase):
    """Stary odczyt kończył partię na 'pusta plansza i pusta tacka'. Ten test pokazuje,
    że most zamiast tego próbuje zamknąć okno i gra dalej (#129)."""

    def test_ad_window_does_not_end_the_game(self):
        empty_grid = [[0] * 8 for _ in range(8)]
        ad_img = _load("0d96333", "121_end.png")

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]
        game_img = _load("0d96333", "120_state.png")

        states = [(ad_img, empty_grid, [None, None, None])]

        def fake_settled_state():
            return states[0]

        def fake_stable_state(tries=6):
            return game_img, playable_grid, playable_slots

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.close_ad", return_value=True) as close_ad, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, game_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()):
            best_streak = bridge.main(1, policy_spec="greedy")

        close_ad.assert_called_once()
        self.assertEqual(best_streak, 0)  # jeden ruch bez porównania (drag zwraca atrapę), ale partia nie skończyła się na oknie


if __name__ == "__main__":
    unittest.main()
