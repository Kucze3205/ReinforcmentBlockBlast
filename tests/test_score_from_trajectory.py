"""Testy `tools/score_from_trajectory.py` (#183): odtwarzanie wyniku partii
apki z trajektorii mostu obu wzorami (naszym i alternatywnym z
docs/rozjazd-punktacja-generator.md)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.score_from_trajectory import (
    clear_points_alt,
    combo_unit_alt,
    find_chunk_files,
    line_bonus_alt,
    load_entries,
    replay,
    summarize,
)


def write_jsonl(path, entries):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


EMPTY_BOARD = [[0] * 8 for _ in range(8)]


def board_with(cells):
    b = [row[:] for row in EMPTY_BOARD]
    for (x, y) in cells:
        b[y][x] = 1
    # jedno pole z dala od linii docelowej, zeby czyszczenie nie oproznialo
    # calej planszy (i nie doliczalo FULL_CLEAR_BONUS, ktory tu nie jest testowany)
    b[7][7] = 1
    return b


class TestAltFormula(unittest.TestCase):
    """Drabinka U(combo) 10/15/20 z docs/rozjazd-punktacja-generator.md §1."""

    def test_combo_unit_thresholds(self):
        self.assertEqual(combo_unit_alt(1), 10)
        self.assertEqual(combo_unit_alt(5), 10)
        self.assertEqual(combo_unit_alt(6), 15)
        self.assertEqual(combo_unit_alt(10), 15)
        self.assertEqual(combo_unit_alt(11), 20)
        self.assertEqual(combo_unit_alt(100), 20)

    def test_line_bonus_single_line_equals_unit(self):
        self.assertEqual(line_bonus_alt(3, 1), 10)
        self.assertEqual(line_bonus_alt(7, 1), 15)

    def test_worked_example_from_doc(self):
        """docs/rozjazd-punktacja-generator.md §2: combo przed ruchem = 9, 2 linie
        naraz -> combo_alt = 11, clear_points_alt = 11 * (20*2*1) = 440."""
        combo_alt = 9 + 2
        self.assertEqual(combo_unit_alt(combo_alt), 20)
        self.assertEqual(clear_points_alt(combo_alt, 2), 440)


class TestFindChunkFiles(unittest.TestCase):
    def test_sorts_both_naming_conventions(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["chunk10_moves.jsonl", "chunk2_moves.jsonl", "chunk1_moves.jsonl"]:
                open(os.path.join(d, name), "w").close()
            files = find_chunk_files(d)
            self.assertEqual(
                [os.path.basename(f) for f in files],
                ["chunk1_moves.jsonl", "chunk2_moves.jsonl", "chunk10_moves.jsonl"],
            )

    def test_alt_naming_convention_and_range_filter(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["moves_chunk1.jsonl", "moves_chunk2.jsonl", "moves_chunk3.jsonl"]:
                open(os.path.join(d, name), "w").close()
            files = find_chunk_files(d, first=2, last=3)
            self.assertEqual(
                [os.path.basename(f) for f in files],
                ["moves_chunk2.jsonl", "moves_chunk3.jsonl"],
            )


class TestReplay(unittest.TestCase):
    def test_single_move_no_clear_scores_placement_only(self):
        entries = [
            {
                "_source": "chunk1_moves.jsonl",
                "_chunk_num": 1,
                "n": 0,
                "board": EMPTY_BOARD,
                "tray": [[[1]], None, None],
                "move": {"slot": 0, "x": 0, "y": 0},
                "score": 0,
            }
        ]
        traj = replay(entries, expect_first_chunk=1)
        self.assertEqual(len(traj["moves"]), 1)
        self.assertEqual(traj["moves"][0]["gained"], 1)
        self.assertEqual(traj["moves"][0]["gained_alt"], 1)
        self.assertEqual(traj["events"], [])

    def test_line_clear_matches_main_formula_at_low_combo(self):
        # Plansza z jednym wolnym polem w wierszu 0; klocek 1x1 domyka wiersz.
        board = board_with([(x, 0) for x in range(1, 8)])
        entries = [
            {
                "_source": "chunk1_moves.jsonl",
                "_chunk_num": 1,
                "n": 0,
                "board": board,
                "tray": [[[1]], None, None],
                "move": {"slot": 0, "x": 0, "y": 0},
                "score": 0,
            }
        ]
        traj = replay(entries, expect_first_chunk=1)
        move = traj["moves"][0]
        # combo 0+1=1: main clear_points(1,1) = 1*10 = 10; placement=1 -> gained=11
        self.assertEqual(move["gained"], 11)
        # alt: combo_alt 0+1=1, combo_unit_alt(1)=10, taki sam wynik na tym combo
        self.assertEqual(move["gained_alt"], 11)

    def test_missing_first_chunk_is_flagged(self):
        entries = [
            {
                "_source": "chunk3_moves.jsonl",
                "_chunk_num": 3,
                "n": 0,
                "board": EMPTY_BOARD,
                "tray": [[[1]], None, None],
                "move": {"slot": 0, "x": 0, "y": 0},
                "score": 100,
            }
        ]
        traj = replay(entries, expect_first_chunk=1)
        types = [e["typ"] for e in traj["events"]]
        self.assertIn("brakujacy_kawalek_na_starcie", types)

    def test_missing_middle_chunk_is_flagged(self):
        entries = [
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 0, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 0, "y": 0}, "score": 0},
            {"_source": "chunk3_moves.jsonl", "_chunk_num": 3, "n": 0, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 1, "y": 0}, "score": 1},
        ]
        traj = replay(entries, expect_first_chunk=1)
        gaps = [e for e in traj["events"] if e["typ"] == "brakujacy_kawalek"]
        self.assertEqual(len(gaps), 1)
        self.assertIn("kawalek 1", gaps[0]["opis"])
        self.assertIn("nastepny 3", gaps[0]["opis"])

    def test_end_and_okno_and_ok_false_are_recorded_as_events(self):
        entries = [
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 0, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 0, "y": 0}, "score": 0,
             "ok": False},
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 1, "board": EMPTY_BOARD,
             "tray": [None, None, None], "score": None, "okno": "ustawienia_wstecz"},
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 1, "board": EMPTY_BOARD,
             "tray": [None, None, None], "score": None, "end": "koniec_partii", "wynik_koncowy": 999},
        ]
        traj = replay(entries, expect_first_chunk=1)
        types = {e["typ"] for e in traj["events"]}
        self.assertEqual(types, {"rozbieznosc_odczytu", "okno", "end"})

    def test_does_not_split_or_reset_on_end_event(self):
        """replay() liczy jedna, ciagla partie - nie dzieli jej sama; to
        wywolujacy decyduje, ktore kawalki naleza do jednej partii (patrz
        docstring modulu: most myli fałszywe zatrzymania z realnym końcem)."""
        board = board_with([(x, 0) for x in range(1, 8)])
        entries = [
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 0, "board": EMPTY_BOARD,
             "tray": [None, None, None], "score": None, "end": "okno: petla_bez_postepu"},
            {"_source": "chunk2_moves.jsonl", "_chunk_num": 2, "n": 0, "board": board,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 0, "y": 0}, "score": 0},
        ]
        traj = replay(entries, expect_first_chunk=1)
        self.assertEqual(len(traj["moves"]), 1)
        self.assertEqual(traj["moves"][0]["score"], 11)


class TestSummarize(unittest.TestCase):
    def test_apka_final_appended_to_move_by_move_when_ocr_consistent(self):
        entries = [
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 0, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 0, "y": 0}, "score": 0},
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 1, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 1, "y": 0}, "score": 1},
        ]
        traj = replay(entries, expect_first_chunk=1)
        summary = summarize(traj, apka_final=50, apka_final_source="test")
        self.assertTrue(summary["ocr_spojny_w_partii"])
        self.assertEqual(summary["ruch_po_ruchu"][-1]["apka_po_ruchu"], 50)
        self.assertEqual(summary["apka_wynik_koncowy"], 50)

    def test_ocr_inconsistent_when_score_decreases(self):
        entries = [
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 0, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 0, "y": 0}, "score": 50},
            {"_source": "chunk1_moves.jsonl", "_chunk_num": 1, "n": 1, "board": EMPTY_BOARD,
             "tray": [[[1]], None, None], "move": {"slot": 0, "x": 1, "y": 0}, "score": 3},
        ]
        traj = replay(entries, expect_first_chunk=1)
        summary = summarize(traj, apka_final=None)
        self.assertFalse(summary["ocr_spojny_w_partii"])
        self.assertEqual(summary["ruch_po_ruchu"], [])


class TestEndToEndOnFixtureChunks(unittest.TestCase):
    """Symuluje uklad plikow jednego przebiegu mostu (dwa kawalki, druga
    zawiera koniec partii z odczytanym wynikiem) i sprawdza load+replay+summarize
    razem, tak jak woła je main()."""

    def test_two_chunk_game_with_real_ending(self):
        with tempfile.TemporaryDirectory() as d:
            board0 = EMPTY_BOARD
            board1 = board_with([(x, 0) for x in range(1, 8)])
            write_jsonl(
                os.path.join(d, "chunk1_moves.jsonl"),
                [
                    {"n": 0, "board": board0, "tray": [[[1]], None, None],
                     "move": {"slot": 0, "x": 3, "y": 3}, "score": 0},
                ],
            )
            write_jsonl(
                os.path.join(d, "chunk2_moves.jsonl"),
                [
                    {"n": 0, "board": board1, "tray": [[[1]], None, None],
                     "move": {"slot": 0, "x": 0, "y": 0}, "score": 1},
                    {"n": 1, "board": EMPTY_BOARD, "tray": [None, None, None],
                     "score": None, "end": "koniec_partii", "wynik_koncowy": 12},
                ],
            )
            files = find_chunk_files(d)
            entries = load_entries(files)
            traj = replay(entries, expect_first_chunk=1)
            summary = summarize(traj, apka_final=12, apka_final_source="chunk2")
            self.assertEqual(summary["postawien"], 2)
            self.assertEqual(summary["wynik_main"], 1 + 11)
            self.assertEqual(summary["wynik_alt"], 1 + 11)
            self.assertEqual(summary["apka_wynik_koncowy"], 12)
            self.assertEqual(summary["events"][-1]["typ"], "end")


if __name__ == "__main__":
    unittest.main()
