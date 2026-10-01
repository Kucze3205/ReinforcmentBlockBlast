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
from board import Board
from pieces import PIECE_POOL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "bridge", "runs")

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


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

    def test_slow_gold_variant_animation_converges_within_game_over_tries(self):
        """#218: wariant fioletowo-złoty z koroną/confetti (`chunk6_025_end.png`, #212) miał
        serię rosnącą [None, 8004, 14226, 20284, 25644, 30179] — dokładnie `tries=6` domyślnych
        prób, bez dwóch zgodnych odczytów z rzędu. `GAME_OVER_SCORE_TRIES` (12) daje margines,
        żeby zobaczyć powtórzenie ostatniej wartości, gdy animacja rzeczywiście się skończyła."""
        img = object()
        reads = [None, 8004, 14226, 20284, 25644, 30179, 30179]
        with mock.patch("bridge.read_score", side_effect=reads), \
             mock.patch("bridge.screenshot"):
            score, seen = bridge.stable_score(img, bridge.GAME_OVER_SCORE_BOX, tries=bridge.GAME_OVER_SCORE_TRIES)
        self.assertEqual(score, 30179)
        self.assertEqual(seen, reads)


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


class TestIsGameOverScreenGoldVariant(unittest.TestCase):
    """#218/#212: nowy wariant ekranu końca — tło fioletowo-złote z koroną i confetti
    (`chunk6_025_end.png`) — musi być rozpoznany jak pozostałe warianty (test fioletu go już
    łapie z marginesem: 0,976 pikseli spełnia warunek, próg 0,5)."""

    def test_positive_on_gold_crown_variant(self):
        self.assertTrue(bridge.is_game_over_screen(_load("1b1763a", "chunk6_025_end.png")))

    def test_uses_purple_score_box(self):
        img = _load("1b1763a", "chunk6_025_end.png")
        self.assertEqual(bridge.game_over_score_box(img), bridge.GAME_OVER_SCORE_BOX)


class TestMainDetectsFrozenBoard(unittest.TestCase):
    """#218: sesja danych #212 (kawałki 25-27) — most powtarzał ten sam ruch `slot1->(3,5)`
    przez 67 ruchów bez zmiany planszy, bo `petla_bez_postepu` liczy tylko wpisy okienkowe
    (`window_streak` zeruje się na każdym zwykłym ruchu, nawet z ROZBIEŻNOŚCIĄ). Teraz
    `BOARD_STUCK_TRIES` ruchów z rzędu, w których odczyt po przeciągnięciu jest identyczny z
    planszą sprzed ruchu, kończy kawałek z `okno: plansza_zawieszona` i zrzutem."""

    def _frozen_board_kwargs(self):
        board_img = _load("0d96333", "120_state.png")
        board = Board()
        board.grid = [[0] * 8 for _ in range(8)]
        board.place_piece(BEAM2, 0, 0)
        frozen_grid = board.grid
        frozen_slots = [([[1, 1]], (20, 460)), None, None]

        def fake_settled_state():
            return board_img, frozen_grid, frozen_slots

        def fake_stable_state(tries=6):
            return board_img, frozen_grid, frozen_slots

        return dict(
            settled_state=mock.patch("bridge.settled_state", side_effect=fake_settled_state),
            stable_state=mock.patch("bridge.stable_state", side_effect=fake_stable_state),
            in_game=mock.patch("bridge.in_game", return_value=True),
            read_score=mock.patch("bridge.read_score", return_value=100),
            drag=mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, board_img)),
            annotate=mock.patch("bridge.annotate"),
            save=mock.patch("PIL.Image.Image.save"),
            makedirs=mock.patch("bridge.os.makedirs"),
        )

    def test_ends_chunk_after_board_stuck_tries_with_okno_and_snapshot(self):
        """#323: pierwsze zawieszenie to twardy restart apki (wpis `restart_twardy`), dopiero
        kolejne `BOARD_STUCK_TRIES` ruchów bez zmiany planszy kończy kawałek."""
        patches = self._frozen_board_kwargs()
        with patches["settled_state"], patches["stable_state"], patches["in_game"], \
             patches["read_score"], patches["drag"], patches["annotate"], patches["save"], \
             patches["makedirs"], mock.patch("bridge.screenshot", return_value=None), \
             mock.patch("bridge.hard_restart_app", return_value=True) as hard, \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            best_streak = bridge.main(30, policy_spec="greedy")

        hard.assert_called_once()
        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertEqual(len(entries), 2 * bridge.BOARD_STUCK_TRIES)
        self.assertTrue(all("move" in e for e in entries))
        restart = entries[bridge.BOARD_STUCK_TRIES - 1]
        self.assertEqual(restart["okno"], "restart_twardy")
        self.assertEqual(restart["okno_przed_restartem"], "plansza_zawieszona")
        self.assertIn("zrzut_zawieszenia", restart)
        self.assertTrue(all(e.get("okno") != "plansza_zawieszona" for e in entries[:-1]))
        last = entries[-1]
        self.assertEqual(last["okno"], "plansza_zawieszona")
        self.assertEqual(last["end"], "okno: plansza_zawieszona")
        self.assertIn("zrzut_zawieszenia", last)
        self.assertEqual(best_streak, 0)

    def test_does_not_trigger_on_a_single_frozen_read(self):
        """Jeden zamrożony odczyt z rzędu to szum OCR (zdarzyło się raz w materiale #212,
        `chunk1_moves.jsonl`, i nigdy się nie powtórzyło) — próg wymaga `BOARD_STUCK_TRIES`."""
        board_img = _load("0d96333", "120_state.png")
        slots = [([[1, 1]], (20, 460)), None, None]

        def grid_with(n):
            b = Board()
            b.grid = [[0] * 8 for _ in range(8)]
            for k in range(n):
                b.place_piece(BEAM2, k, 0)
            return b.grid

        initial_grid = grid_with(1)
        stable_returns = [grid_with(1), grid_with(2), grid_with(3)]

        def fake_settled_state():
            return board_img, initial_grid, slots

        calls = {"i": 0}

        def fake_stable_state(tries=6):
            g = stable_returns[calls["i"]]
            calls["i"] += 1
            return board_img, g, slots

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.read_score", return_value=100), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, board_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(3, policy_spec="greedy")

        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertEqual(len(entries), 3)
        self.assertTrue(all("okno" not in e for e in entries))


if __name__ == "__main__":
    unittest.main()
