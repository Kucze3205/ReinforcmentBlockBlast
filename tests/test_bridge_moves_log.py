"""
Testy dla #198: trzy usterki mechaniczne mostu znalezione w sesji danych z cyklu 20 (#190).

1. `bridge.py` przy każdym wywołaniu nadpisywał `bridge-out/moves.jsonl` w trybie `"w"` —
   verifier, który nie zdążył skopiować pliku przed kolejnym wywołaniem, tracił całą
   trajektorię (sesja `cb91077`, `chunk3_moves.jsonl` z #191).
2. Most czytał wynik z ekranu końca partii i od razu stukał „Play" bez zostawienia zrzutu —
   kryteria sesji danych wymagają zrzutu, verifier musiał nagrywać ekran obok mostu.
3. Pierwszy odczyt wyniku po wykryciu końca partii bywa błędny, bo licznik jeszcze się
   animuje (kawałek 12 z #190) — most potrzebuje stabilizacji przez ponowny odczyt.

Wszystkie testy atrapują `adb`/`screenshot` — bez emulatora.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "bridge", "runs")


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)


class TestNextMovesPath(unittest.TestCase):
    """#198 punkt 1: kolejne wywołania nie mają prawa nadpisać pliku poprzedniego."""

    def test_first_call_uses_plain_name(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bridge.next_moves_path(d), os.path.join(d, "moves.jsonl"))

    def test_second_call_gets_numbered_name_without_touching_first(self):
        with tempfile.TemporaryDirectory() as d:
            first = bridge.next_moves_path(d)
            with open(first, "w") as f:
                f.write("wpis z pierwszego wywołania\n")
            second = bridge.next_moves_path(d)
            self.assertNotEqual(first, second)
            open(second, "w").close()
            third = bridge.next_moves_path(d)
            self.assertNotIn(third, (first, second))
            with open(first) as f:
                self.assertEqual(f.read(), "wpis z pierwszego wywołania\n")

    def test_never_reuses_an_existing_path(self):
        with tempfile.TemporaryDirectory() as d:
            for _ in range(4):
                path = bridge.next_moves_path(d)
                open(path, "w").close()
            seen = set()
            for _ in range(4):
                path = bridge.next_moves_path(d)
                self.assertNotIn(path, seen)
                open(path, "w").close()
                seen.add(path)


class TestStableScore(unittest.TestCase):
    """#198 punkt 3: odczyt wyniku aż dwa kolejne się zgodzą, z limitem prób i pełnym logiem."""

    def test_stable_first_read_needs_no_extra_screenshot_call(self):
        img = object()
        with mock.patch("bridge.read_score", return_value=100), \
             mock.patch("bridge.screenshot") as screenshot:
            score, reads = bridge.stable_score(img, bridge.SCORE_BOX)
        self.assertEqual(score, 100)
        self.assertEqual(reads, [100, 100])
        screenshot.assert_called_once()

    def test_unstable_reads_converge_before_limit(self):
        img = object()
        with mock.patch("bridge.read_score", side_effect=[100, 105, 110, 110]), \
             mock.patch("bridge.screenshot"):
            score, reads = bridge.stable_score(img, bridge.SCORE_BOX, tries=6)
        self.assertEqual(score, 110)
        self.assertEqual(reads, [100, 105, 110, 110])

    def test_gives_up_at_try_limit_without_convergence(self):
        img = object()
        with mock.patch("bridge.read_score", side_effect=[1, 2, 3, 4]), \
             mock.patch("bridge.screenshot"):
            score, reads = bridge.stable_score(img, bridge.SCORE_BOX, tries=4)
        self.assertEqual(score, 4)
        self.assertEqual(reads, [1, 2, 3, 4])


class TestMainSavesGameOverScreenshotBeforePlay(unittest.TestCase):
    """#198 punkt 2: zrzut ekranu końca partii zapisany, zanim most stuknie „Play", z nazwą
    pliku w tym samym wpisie `koniec_partii`."""

    def test_screenshot_saved_before_tap_play_and_named_in_log(self):
        gameover_img = _load("1402cff", "chunk7_010_gameover_screen.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        calls = []

        def fake_settled_state():
            return gameover_img, empty_grid, [None, None, None]

        def fake_save(self, path, *a, **k):
            calls.append(("save", path))

        def fake_tap_play():
            calls.append(("tap_play", None))

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.screenshot", return_value=gameover_img), \
             mock.patch("bridge.read_score", return_value=8532), \
             mock.patch("bridge.tap_play", side_effect=fake_tap_play), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save", new=fake_save), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(50, policy_spec="greedy")

        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        entry = entries[0]
        self.assertTrue(entry["koniec_partii"])
        self.assertIn("zrzut_konca", entry)
        tap_index = next(i for i, (name, _) in enumerate(calls) if name == "tap_play")
        save_index = next(i for i, (name, path) in enumerate(calls)
                           if name == "save" and os.path.basename(path) == entry["zrzut_konca"])
        self.assertLess(save_index, tap_index)


if __name__ == "__main__":
    unittest.main()
