"""
Testy `ntuple.py` (#123): uklad lat jako dana, odczyt z masek bitowych, zapis/odczyt JSON.
"""
import json
import os
import random
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark
from board import Board
from ntuple import (
    LAYOUT_A,
    LAYOUT_AD,
    LAYOUT_D,
    LAYOUTS,
    N_PATCHES,
    N_WEIGHTS,
    PATCH_LAYOUT,
    PATCH_SIZE,
    TABLE_SIZE,
    NTupleValue,
    _patch_index,
    board_bits,
    patch_indices,
)


def _board_from_grid(grid):
    board = Board()
    board.grid = [row[:] for row in grid]
    return board


class TestPatchLayout(unittest.TestCase):
    """Wariant A z #120: 8 wierszy + 8 kolumn, k=8, 16 lat x 2**8 = 4096 wag."""

    def test_sixteen_patches_of_eight_cells(self):
        self.assertEqual(N_PATCHES, 16)
        self.assertEqual(PATCH_SIZE, 8)
        self.assertEqual(TABLE_SIZE, 256)
        self.assertEqual(N_WEIGHTS, 16 * 256)
        for positions in PATCH_LAYOUT:
            self.assertEqual(len(positions), 8)

    def test_layout_covers_every_cell_at_least_once(self):
        covered = set()
        for positions in PATCH_LAYOUT:
            covered.update(positions)
        self.assertEqual(covered, set(range(Board.WIDTH * Board.HEIGHT)))

    def test_layout_is_single_source_of_truth_not_scattered(self):
        # Modul eksponuje jedna liste, z ktorej liczba i rozmiar lat sa wyprowadzone.
        self.assertEqual(len(PATCH_LAYOUT), N_PATCHES)


class TestLayoutAD(unittest.TestCase):
    """Uklad AD (#149): A (dzisiejszy PATCH_LAYOUT) plus D (kwadraty 3x3, 36 polozen)."""

    def test_a_is_unchanged_patch_layout(self):
        self.assertEqual(LAYOUT_A, PATCH_LAYOUT)
        self.assertEqual(LAYOUTS["A"], PATCH_LAYOUT)

    def test_d_has_36_patches_of_nine_cells(self):
        self.assertEqual(len(LAYOUT_D), 36)
        for positions in LAYOUT_D:
            self.assertEqual(len(positions), 9)

    def test_ad_is_a_concatenated_with_d(self):
        self.assertEqual(LAYOUT_AD, LAYOUT_A + LAYOUT_D)
        self.assertEqual(len(LAYOUT_AD), 16 + 36)
        self.assertEqual(LAYOUTS["AD"], LAYOUT_AD)

    def test_ad_covers_every_cell_at_least_once(self):
        covered = set()
        for positions in LAYOUT_AD:
            covered.update(positions)
        self.assertEqual(covered, set(range(Board.WIDTH * Board.HEIGHT)))

    def test_default_ntuple_value_uses_layout_a(self):
        ntuple = NTupleValue()
        self.assertEqual(ntuple.layout, LAYOUT_A)
        self.assertEqual(len(ntuple.weights), 16)

    def test_ntuple_value_with_ad_layout_has_52_weight_tables(self):
        ntuple = NTupleValue(layout=LAYOUT_AD)
        self.assertEqual(len(ntuple.weights), 52)
        self.assertEqual(ntuple.value(Board()), 0.0)

    def test_ad_round_trips_through_save_load(self):
        ntuple = NTupleValue(layout=LAYOUT_AD)
        board = Board()
        board.grid[3] = [1, 0, 1, 1, 0, 0, 1, 0]
        ntuple.update(ntuple.indices(board), 4.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ad.json")
            ntuple.save(path)
            loaded = NTupleValue.load(path)
        self.assertEqual(loaded.layout, LAYOUT_AD)
        self.assertEqual(loaded.weights, ntuple.weights)
        self.assertEqual(loaded.value(board), ntuple.value(board))

    def test_files_without_layout_change_load_as_a_with_same_values(self):
        # Plik zapisany dawnym kodem (patch_layout = PATCH_LAYOUT, bez wiedzy o AD)
        # wczytuje sie jako A z tymi samymi wartosciami (#149).
        ntuple = NTupleValue()
        board = Board()
        board.grid[0] = [1, 1, 0, 0, 0, 0, 0, 0]
        ntuple.update(ntuple.indices(board), 1.5)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({
                    "patch_layout": [list(p) for p in PATCH_LAYOUT],
                    "weights": ntuple.weights,
                }, fh)
            loaded = NTupleValue.load(path)
        self.assertEqual(loaded.layout, LAYOUT_A)
        self.assertEqual(loaded.reward, "score")
        self.assertEqual(loaded.value(board), ntuple.value(board))

    def test_benchmark_load_ntuple_weights_reads_ad_layout_unchanged(self):
        # Kryterium #149: benchmark.load_ntuple_weights (bez zmian w benchmark.py)
        # dziala dla pliku z ukladem AD tak samo jak dla A.
        ntuple = NTupleValue(layout=LAYOUT_AD)
        board = Board()
        board.grid[5] = [0, 1, 0, 1, 1, 0, 1, 0]
        ntuple.update(ntuple.indices(board), 2.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ad.json")
            ntuple.save(path)
            loaded = benchmark.load_ntuple_weights(path)
        self.assertEqual(loaded.layout, LAYOUT_AD)
        self.assertEqual(loaded.value(board), ntuple.value(board))


class TestBoardBits(unittest.TestCase):
    def test_empty_board_is_zero(self):
        self.assertEqual(board_bits(Board()), 0)

    def test_single_cell_sets_expected_bit(self):
        board = Board()
        board.grid[3][5] = 1
        self.assertEqual(board_bits(board), 1 << (3 * Board.WIDTH + 5))

    def test_full_board_is_all_ones(self):
        board = _board_from_grid([[1] * Board.WIDTH for _ in range(Board.HEIGHT)])
        self.assertEqual(board_bits(board), (1 << (Board.WIDTH * Board.HEIGHT)) - 1)


class TestPatchIndices(unittest.TestCase):
    def test_empty_board_all_indices_zero(self):
        self.assertEqual(patch_indices(board_bits(Board())), [0] * N_PATCHES)

    def test_full_board_all_indices_max(self):
        board = _board_from_grid([[1] * Board.WIDTH for _ in range(Board.HEIGHT)])
        self.assertEqual(patch_indices(board_bits(board)), [TABLE_SIZE - 1] * N_PATCHES)

    def test_row_patch_reads_that_row_as_a_byte(self):
        board = Board()
        board.grid[2] = [1, 0, 1, 0, 0, 0, 0, 1]
        indices = patch_indices(board_bits(board))
        # PATCH_LAYOUT[y] jest lata-wierszem y (patrz ntuple._row_patch).
        self.assertEqual(indices[2], 0b10000101)

    def test_col_patch_reads_that_column_as_a_byte(self):
        board = Board()
        for y, bit in enumerate([1, 0, 0, 1, 0, 0, 0, 1]):
            board.grid[y][4] = bit
        indices = patch_indices(board_bits(board))
        # PATCH_LAYOUT[8 + x] jest lata-kolumna x.
        self.assertEqual(indices[8 + 4], 0b10001001)


class TestPatchIndicesMatchesBitwiseReference(unittest.TestCase):
    """`patch_indices` liczy po bajtach wierszy (#158); wynik musi zostac bitowo
    taki sam jak referencja bit-po-bicie `_patch_index`, na losowych planszach."""

    def _random_board(self, rng):
        board = Board()
        for y in range(Board.HEIGHT):
            board.grid[y] = [1 if rng.random() < 0.5 else 0 for _ in range(Board.WIDTH)]
        return board

    def _check_layout(self, layout):
        rng = random.Random(158)
        for _ in range(1000):
            bits = board_bits(self._random_board(rng))
            expected = [_patch_index(bits, positions) for positions in layout]
            self.assertEqual(patch_indices(bits, layout), expected)

    def test_layout_a_matches_reference_on_1000_random_boards(self):
        self._check_layout(LAYOUT_A)

    def test_layout_ad_matches_reference_on_1000_random_boards(self):
        self._check_layout(LAYOUT_AD)


class TestNTupleValueZeroWeights(unittest.TestCase):
    def test_zero_weights_give_zero_on_any_board(self):
        ntuple = NTupleValue()
        self.assertEqual(ntuple.value(Board()), 0.0)
        full = _board_from_grid([[1] * Board.WIDTH for _ in range(Board.HEIGHT)])
        self.assertEqual(ntuple.value(full), 0.0)

        board = Board()
        board.grid[0] = [1, 1, 1, 1, 1, 1, 1, 0]
        board.grid[5][3] = 1
        self.assertEqual(ntuple.value(board), 0.0)


class TestNTupleValueUpdate(unittest.TestCase):
    def test_update_touches_only_active_weight_per_patch(self):
        ntuple = NTupleValue()
        board = Board()
        board.grid[0] = [1] * Board.WIDTH  # linia 0 pelna -> lata-wiersz 0 ma indeks 255
        idxs = ntuple.indices(board)
        ntuple.update(idxs, 5.0)
        self.assertEqual(ntuple.value(board), 5.0 * N_PATCHES)
        # Zaden inny wpis w tabeli laty-wiersza 0 nie zostal dotkniety.
        self.assertEqual(ntuple.weights[0][0], 0.0)
        self.assertEqual(ntuple.weights[0][255], 5.0)

    def test_value_from_indices_matches_value(self):
        ntuple = NTupleValue()
        board = Board()
        board.grid[1] = [1, 0, 1, 1, 0, 0, 1, 0]
        ntuple.update(ntuple.indices(board), 3.0)
        self.assertEqual(ntuple.value(board), ntuple.value_from_indices(ntuple.indices(board)))


class TestNTupleValueSaveLoad(unittest.TestCase):
    def test_round_trip_preserves_weights(self):
        ntuple = NTupleValue()
        board = Board()
        board.grid[7] = [1, 1, 0, 0, 1, 0, 1, 1]
        ntuple.update(ntuple.indices(board), 2.5)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ntuple.json")
            ntuple.save(path)
            loaded = NTupleValue.load(path)

        self.assertEqual(loaded.value(board), ntuple.value(board))
        self.assertEqual(loaded.weights, ntuple.weights)

    def test_load_rejects_mismatched_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"patch_layout": [[0, 1, 2, 3]], "weights": [[0.0] * 16]}, fh)
            with self.assertRaises(ValueError):
                NTupleValue.load(path)


class TestNTupleValueSpeed(unittest.TestCase):
    """Nie asercja na konkretna liczbe (sprzet sesji jest nieznany) — tylko dowod,
    ze evaluate() da sie zmierzyc w rozsadnym czasie na jednym watku."""

    def test_can_measure_evaluations_per_second(self):
        ntuple = NTupleValue()
        board = Board()
        board.grid[3] = [1, 0, 1, 1, 0, 0, 1, 0]
        n = 2000
        started = time.perf_counter()
        for _ in range(n):
            ntuple.value(board)
        elapsed = time.perf_counter() - started
        self.assertGreater(elapsed, 0.0)
        self.assertGreater(n / elapsed, 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
