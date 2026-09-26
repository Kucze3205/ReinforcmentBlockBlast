"""
Testy `ntuple.py` (#123): uklad lat jako dana, odczyt z masek bitowych, zapis/odczyt JSON.
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import Board
from ntuple import (
    N_PATCHES,
    N_WEIGHTS,
    PATCH_LAYOUT,
    PATCH_SIZE,
    TABLE_SIZE,
    NTupleValue,
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
