"""#317: reklama interaktywna „koło fortuny" (s3 partia 3, kawałek 18) nie jest modalem Ustawień.
Klatki z `docs/seria/s3/partia-3/kawalek_18/`; pętla mostu przez atrapy, `screenshot()` zwraca `int`."""
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
K18 = os.path.join(ROOT, "docs", "seria", "s3", "partia-3", "kawalek_18")
RUNS = os.path.join(ROOT, "bridge", "runs")
BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


def _load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


def _ad(name):
    return _load(os.path.join(K18, name))


def _run(first_img, after_imgs, patches, max_moves=1):
    empty = [[0] * 8 for _ in range(8)]
    board = Board()
    board.grid = [row[:] for row in empty]
    board.place_piece(BEAM2, 0, 0)
    slots = [([[1, 1]], (20, 460)), None, None]
    after = iter(after_imgs)
    last = [after_imgs[-1]]

    def stable(tries=6):
        last[0] = next(after, last[0])
        return last[0], board.grid, slots

    with mock.patch("bridge.settled_state", return_value=(first_img, empty, [None, None, None])), \
         mock.patch("bridge.stable_state", side_effect=stable), \
         mock.patch("bridge.in_game", return_value=True), \
         mock.patch("bridge.read_score", return_value=None), \
         mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, after_imgs[-1])), \
         mock.patch("bridge.annotate"), mock.patch("PIL.Image.Image.save"), \
         mock.patch("bridge.os.makedirs"), mock.patch("bridge.time.sleep"), \
         mock.patch("builtins.open", mock.mock_open()) as m_open:
        started = [mock.patch(*a, **k).start() for a, k in patches]
        try:
            bridge.main(max_moves, policy_spec="greedy", seria=True)
        finally:
            mock.patch.stopall()
    return [json.loads(c.args[0]) for c in m_open().write.call_args_list], started


class TestInteractiveAdDetector(unittest.TestCase):
    def test_positive_and_not_settings(self):
        for name in ("035_state.png", "final.png"):
            with self.subTest(name=name):
                img = _ad(name)
                self.assertTrue(bridge.is_interactive_ad_screen(img))
                self.assertFalse(bridge.is_settings_screen(img) and not bridge.is_interactive_ad_screen(img))

    def test_negative_on_live_board_and_other_windows(self):
        for img in (_ad("034_state.png"), _load(os.path.join(RUNS, "44a8ea2", "p1a_settings.png")),
                    _load(os.path.join(RUNS, "0d96333", "120_state.png")),
                    _load(os.path.join(RUNS, "0d96333", "121_end.png"))):
            self.assertFalse(bridge.is_interactive_ad_screen(img))

    def test_other_ads_keep_their_names(self):
        self.assertTrue(bridge.is_settings_screen(_load(os.path.join(RUNS, "44a8ea2", "p1a_settings.png"))))


class TestInteractiveAdLoop(unittest.TestCase):
    def test_taps_close_and_logs_window(self):
        ad, board_img = _ad("035_state.png"), _load(os.path.join(RUNS, "0d96333", "120_state.png"))
        entries, (close, back, hard) = _run(
            ad, [board_img], [(("bridge.tap_interactive_close",), {}), (("bridge.press_back",), {}),
                              (("bridge.hard_restart_app",), {})])
        close.assert_called_once()
        back.assert_not_called()
        hard.assert_not_called()
        self.assertEqual(entries[0]["okno"], "reklama_interaktywna")

    def test_falls_back_to_hard_restart_after_k_failed_taps(self):
        """#318: po K nieudanych „>>" jeden twardy restart (`restart_app` byłby no-opem przy oknie w procesie
        apki); gdy okno dalej stoi, „>>" jest stukane znów, a bezpiecznik kończy kawałek."""
        ad = _ad("035_state.png")
        entries, (close, back, hard, _) = _run(
            ad, [ad], [(("bridge.tap_interactive_close",), {}), (("bridge.press_back",), {}),
                       (("bridge.hard_restart_app",), {"return_value": True}), (("bridge.screenshot",), {})],
            max_moves=1000)
        k = bridge.INTERACTIVE_AD_BACK_TRIES
        hard.assert_called_once()
        back.assert_not_called()
        self.assertEqual(entries[k]["okno"], "restart_twardy")
        self.assertEqual(entries[k]["okno_przed_restartem"], "reklama_interaktywna")
        self.assertEqual(close.call_count, len(entries) - 1)  # każdy wpis poza twardym restartem stuka „>>"
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")

    def test_hard_restart_not_repeated_while_window_stands(self):
        ad = _ad("035_state.png")
        entries, (_, _, hard, _) = _run(
            ad, [ad], [(("bridge.tap_interactive_close",), {}), (("bridge.press_back",), {}),
                       (("bridge.hard_restart_app",), {"return_value": True}), (("bridge.screenshot",), {})],
            max_moves=1000)
        self.assertEqual(hard.call_count, 1)
        self.assertEqual(sum(e.get("okno") == "restart_twardy" for e in entries), 1)


if __name__ == "__main__":
    unittest.main()
