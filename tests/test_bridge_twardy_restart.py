"""#318: twardy restart apki (`am force-stop`) jako ostatnia deska przed bezpiecznikiem okien.
Pętla mostu przez atrapy `stable_state`/`screenshot`/`hard_restart_app`; klatki z `bridge/runs/`."""
import json
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
K = bridge.PROGRESS_SAFEGUARD_TRIES


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)


EMPTY = [[0] * 8 for _ in range(8)]
_board = Board()
_board.grid = [row[:] for row in EMPTY]
_board.place_piece(BEAM2, 0, 0)
PLAYABLE = _board.grid
SLOTS = [([[1, 1]], (20, 460)), None, None]
NO_SLOTS = [None, None, None]


def _imgs():
    """Dwie klatki gry (osobne kopie, żeby licznik wiązać po tożsamości) i modal Ustawień jako „okno"."""
    base = _load("0d96333", "120_state.png")
    return base.copy(), base.copy(), _load("495cd91", "before_retry.png")


class Scenario:
    """Kolejka klatek dla `settled_state` i kolejnych `stable_state`; ostatnia powtarza się bez końca.
    Licznik HUD bierze z `scores` po tożsamości obrazu."""

    def __init__(self, frames, scores, after_restart_img=None, restart_ok=True):
        self.frames, self.scores = list(frames), scores
        self.after_restart_img = after_restart_img if after_restart_img is not None else self.frames[0][0]
        self.restart_ok = restart_ok

    def run(self, max_moves=1000, seria=True):
        queue = list(self.frames[1:]) or list(self.frames)  # klatkę 0 dostaje `settled_state`

        def stable(tries=6):
            return queue.pop(0) if len(queue) > 1 else queue[0]

        with mock.patch("bridge.settled_state", return_value=self.frames[0]), \
             mock.patch("bridge.stable_state", side_effect=stable), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.press_back"), \
             mock.patch("bridge.stable_score", return_value=(100, [100, 100])), \
             mock.patch("bridge.read_score", side_effect=lambda img, box=bridge.SCORE_BOX: self.scores.get(id(img))), \
             mock.patch("bridge.drag", side_effect=lambda *a, **k: ({"finger": [0, 0]}, self.frames[0][0])), \
             mock.patch("bridge.screenshot", return_value=self.after_restart_img), \
             mock.patch("bridge.hard_restart_app", return_value=self.restart_ok) as hard, \
             mock.patch("bridge.annotate"), mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(max_moves, policy_spec="greedy", seria=seria)
        return [json.loads(c.args[0]) for c in m_open().write.call_args_list], hard


class TestHardRestartApp(unittest.TestCase):
    def test_force_stop_then_restart_app(self):
        calls = []
        with mock.patch("bridge.adb", side_effect=lambda *a: calls.append(("adb",) + a)), \
             mock.patch("bridge.restart_app", side_effect=lambda *a, **k: calls.append(("restart",)) or True), \
             mock.patch("bridge.time.sleep"):
            self.assertTrue(bridge.hard_restart_app())
        self.assertEqual(calls, [("adb", "shell", "am", "force-stop", bridge.PACKAGE), ("restart",)])

    def test_false_when_app_does_not_come_back(self):
        with mock.patch("bridge.adb"), mock.patch("bridge.restart_app", return_value=False), \
             mock.patch("bridge.time.sleep"):
            self.assertFalse(bridge.hard_restart_app())


class TestWindowChainHardRestart(unittest.TestCase):
    def test_stuck_window_one_hard_restart_then_game_goes_on(self):
        game, game2, window = _imgs()
        frames = [(game, PLAYABLE, SLOTS)] + [(window, EMPTY, NO_SLOTS)] * (K + 2) + [(game2, PLAYABLE, SLOTS)]
        entries, hard = Scenario(frames, {id(game): 1000, id(game2): 1000}, after_restart_img=game2).run(max_moves=2)
        hard.assert_called_once()
        restarts = [e for e in entries if e.get("okno") == "restart_twardy"]
        self.assertEqual(len(restarts), 1)
        r = restarts[0]
        self.assertEqual((r["licznik_przed"], r["licznik_po"]), (1000, 1000))
        self.assertEqual(r["okno_przed_restartem"], "ustawienia_wstecz")
        self.assertNotIn("end", r)
        i = entries.index(r)
        self.assertEqual(i, K)  # ruch, potem K wpisów okiennych; K-ty to restart
        self.assertFalse(any("end" in e for e in entries))

    def test_window_still_stuck_after_hard_restart_ends_as_loop(self):
        game, _, window = _imgs()
        entries, hard = Scenario([(game, PLAYABLE, SLOTS), (window, EMPTY, NO_SLOTS)], {id(game): 1000}).run()
        hard.assert_called_once()
        okna = [e["okno"] for e in entries if "move" not in e]
        self.assertEqual(len(okna), 2 * K)
        self.assertEqual(okna[K - 1], "restart_twardy")
        self.assertEqual(okna.count("restart_twardy"), 1)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertEqual(sum("end" in e for e in entries), 1)

    def test_app_not_coming_back_after_hard_restart(self):
        game, _, window = _imgs()
        sc = Scenario([(game, PLAYABLE, SLOTS), (window, EMPTY, NO_SLOTS)], {id(game): 1000}, restart_ok=False)
        entries, hard = sc.run()
        hard.assert_called_once()
        self.assertEqual(entries[-1]["okno"], "restart_twardy")
        self.assertEqual(entries[-1]["end"], "gra nie jest na pierwszym planie")

    def test_move_rearms_hard_restart(self):
        game, game2, window = _imgs()
        frames = ([(game, PLAYABLE, SLOTS)] + [(window, EMPTY, NO_SLOTS)] * (K + 1)
                  + [(game2, PLAYABLE, SLOTS)] + [(window, EMPTY, NO_SLOTS)])
        entries, hard = Scenario(frames, {id(game): 10, id(game2): 20}, after_restart_img=game2).run(max_moves=100)
        self.assertEqual(hard.call_count, 2)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")


class TestLostGame(unittest.TestCase):
    def _stuck_then(self, after_frame, scores, after_restart_img):
        game, _, window = _imgs()
        frames = [(game, PLAYABLE, SLOTS)] + [(window, EMPTY, NO_SLOTS)] * (K + 1) + [after_frame]
        scores = {**scores, id(game): 1000}
        return Scenario(frames, scores, after_restart_img=window if after_restart_img is None else after_restart_img).run(max_moves=100)

    def test_lower_counter_right_after_restart_ends_chunk(self):
        low = _imgs()[1]
        entries, hard = self._stuck_then((low, PLAYABLE, SLOTS), {id(low): 40}, after_restart_img=low)
        r = entries[-1]
        self.assertEqual((r["okno"], r["end"]), ("restart_utracil_partie", "okno: restart_utracil_partie"))
        self.assertEqual((r["licznik_przed"], r["licznik_po"]), (1000, 40))
        hard.assert_called_once()

    def test_lower_counter_on_first_board_frame_ends_chunk(self):
        low = _imgs()[1]
        entries, _ = self._stuck_then((low, PLAYABLE, SLOTS), {id(low): 40}, after_restart_img=None)
        self.assertEqual(entries[-1]["end"], "okno: restart_utracil_partie")
        self.assertEqual((entries[-1]["licznik_przed"], entries[-1]["licznik_po"]), (1000, 40))
        self.assertFalse(any("move" in e for e in entries[1:]))  # nowej partii nie gramy dalej

    def test_empty_board_with_tray_after_nonempty_ends_chunk(self):
        fresh = _imgs()[1]
        entries, _ = self._stuck_then((fresh, EMPTY, SLOTS), {}, after_restart_img=None)
        self.assertEqual(entries[-1]["end"], "okno: restart_utracil_partie")
        self.assertEqual(entries[-1]["licznik_przed"], 1000)

    def test_counter_not_lower_is_the_same_game(self):
        same = _imgs()[1]
        entries, _ = self._stuck_then((same, PLAYABLE, SLOTS), {id(same): 1000}, after_restart_img=None)
        self.assertFalse(any(e.get("okno") == "restart_utracil_partie" for e in entries))
        self.assertTrue(any("move" in e for e in entries[K + 1:]))


class TestGameOverNeverRestarts(unittest.TestCase):
    def test_game_over_in_series_ends_chunk_without_restart(self):
        game, _, window = _imgs()
        calls = {"n": 0}

        def is_settings(img):
            if img is window:
                calls["n"] += 1
                return calls["n"] <= K - 1  # K-1 okien Ustawień, potem ten sam ekran to koniec partii
            return False

        sc = Scenario([(game, PLAYABLE, SLOTS), (window, EMPTY, NO_SLOTS)], {id(game): 1000})
        with mock.patch("bridge.is_settings_screen", side_effect=is_settings), \
             mock.patch("bridge.is_game_over_screen", side_effect=lambda img: img is window):
            entries, hard = sc.run()
        hard.assert_not_called()
        self.assertEqual(entries[-1]["end"], "koniec_partii")


if __name__ == "__main__":
    unittest.main()
