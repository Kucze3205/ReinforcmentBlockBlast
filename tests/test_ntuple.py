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
    LAYOUT_ADC,
    LAYOUT_C,
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
    occupied_count,
    patch_indices,
    stage_of_occupied,
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


class TestLayoutADC(unittest.TestCase):
    """Uklad ADC (#162): AD plus C (prostokaty 2x3/3x2 we wszystkich 84 polozeniach)."""

    def test_c_has_84_patches_of_six_cells(self):
        self.assertEqual(len(LAYOUT_C), 84)
        for positions in LAYOUT_C:
            self.assertEqual(len(positions), 6)

    def test_c_patches_are_2x3_or_3x2_rectangles_without_duplicates(self):
        seen = set()
        shapes = set()
        for positions in LAYOUT_C:
            key = tuple(sorted(positions))
            self.assertNotIn(key, seen, "lata C powtorzona")
            seen.add(key)
            xs = [p % Board.WIDTH for p in positions]
            ys = [p // Board.WIDTH for p in positions]
            width = max(xs) - min(xs) + 1
            height = max(ys) - min(ys) + 1
            self.assertEqual(width * height, 6)
            self.assertLess(max(xs), Board.WIDTH)
            self.assertLess(max(ys), Board.HEIGHT)
            shapes.add((height, width))
        self.assertEqual(shapes, {(2, 3), (3, 2)})

    def test_adc_is_ad_concatenated_with_c(self):
        self.assertEqual(LAYOUT_ADC, LAYOUT_AD + LAYOUT_C)
        self.assertEqual(len(LAYOUT_ADC), 52 + 84)
        self.assertEqual(list(LAYOUT_ADC[:52]), list(LAYOUT_AD))
        self.assertEqual(LAYOUTS["ADC"], LAYOUT_ADC)

    def test_adc_covers_every_cell_at_least_once(self):
        covered = set()
        for positions in LAYOUT_ADC:
            covered.update(positions)
        self.assertEqual(covered, set(range(Board.WIDTH * Board.HEIGHT)))

    def test_ntuple_value_with_adc_layout_has_136_weight_tables(self):
        ntuple = NTupleValue(layout=LAYOUT_ADC)
        self.assertEqual(len(ntuple.weights), 136)
        self.assertEqual(ntuple.value(Board()), 0.0)

    def test_adc_round_trips_through_save_load(self):
        ntuple = NTupleValue(layout=LAYOUT_ADC)
        board = Board()
        board.grid[3] = [1, 0, 1, 1, 0, 0, 1, 0]
        ntuple.update(ntuple.indices(board), 4.0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "adc.json")
            ntuple.save(path)
            loaded = NTupleValue.load(path)
        self.assertEqual(loaded.layout, LAYOUT_ADC)
        self.assertEqual(loaded.weights, ntuple.weights)
        self.assertEqual(loaded.value(board), ntuple.value(board))

    def test_layout_adc_matches_reference_on_1000_random_boards(self):
        rng = random.Random(162)
        for _ in range(1000):
            board = Board()
            for y in range(Board.HEIGHT):
                board.grid[y] = [1 if rng.random() < 0.5 else 0 for _ in range(Board.WIDTH)]
            bits = board_bits(board)
            expected = [_patch_index(bits, positions) for positions in LAYOUT_ADC]
            self.assertEqual(patch_indices(bits, LAYOUT_ADC), expected)


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


class TestStages(unittest.TestCase):
    """Etapy N-tuple (#203): domyślnie 1 etap, bitowo bez zmian; przy kilku
    etapach każdy ma własny komplet wag, wybierany z zajętości planszy."""

    def test_occupied_count(self):
        self.assertEqual(occupied_count(0), 0)
        self.assertEqual(occupied_count(1), 1)
        self.assertEqual(occupied_count((1 << 64) - 1), 64)
        board = Board()
        board.grid[0] = [1, 1, 1, 0, 0, 0, 0, 0]
        self.assertEqual(occupied_count(board_bits(board)), 3)

    def test_stage_of_occupied_no_thresholds_is_always_zero(self):
        self.assertEqual(stage_of_occupied(0, ()), 0)
        self.assertEqual(stage_of_occupied(64, ()), 0)

    def test_stage_of_occupied_counts_thresholds_reached(self):
        thresholds = (10, 30, 50)
        self.assertEqual(stage_of_occupied(0, thresholds), 0)
        self.assertEqual(stage_of_occupied(9, thresholds), 0)
        self.assertEqual(stage_of_occupied(10, thresholds), 1)
        self.assertEqual(stage_of_occupied(29, thresholds), 1)
        self.assertEqual(stage_of_occupied(30, thresholds), 2)
        self.assertEqual(stage_of_occupied(50, thresholds), 3)
        self.assertEqual(stage_of_occupied(64, thresholds), 3)

    def test_default_stages_is_one_and_single_stage_file_shape_unchanged(self):
        ntuple = NTupleValue()
        self.assertEqual(ntuple.stages, 1)
        self.assertEqual(ntuple.thresholds, ())
        self.assertEqual(ntuple.stage(Board()), 0)
        data = ntuple.to_dict()
        self.assertNotIn("stages", data)
        self.assertNotIn("thresholds", data)
        self.assertEqual(data["weights"], ntuple.weights)  # plaska lista tablic, jak przed #203

    def test_rejects_thresholds_count_mismatch(self):
        with self.assertRaises(ValueError):
            NTupleValue(stages=2, thresholds=())
        with self.assertRaises(ValueError):
            NTupleValue(stages=1, thresholds=(5,))

    def test_rejects_non_ascending_thresholds(self):
        with self.assertRaises(ValueError):
            NTupleValue(stages=3, thresholds=(10, 10))
        with self.assertRaises(ValueError):
            NTupleValue(stages=3, thresholds=(30, 10))

    def test_rejects_thresholds_out_of_range(self):
        with self.assertRaises(ValueError):
            NTupleValue(stages=2, thresholds=(0,))
        with self.assertRaises(ValueError):
            NTupleValue(stages=2, thresholds=(64,))

    def test_two_stages_pick_weights_by_occupied_cells(self):
        ntuple = NTupleValue(stages=2, thresholds=(3,))
        self.assertEqual(len(ntuple.weights), 2)
        empty = Board()
        full3 = Board()
        full3.grid[0] = [1, 1, 1, 0, 0, 0, 0, 0]
        self.assertEqual(ntuple.stage(empty), 0)
        self.assertEqual(ntuple.stage(full3), 1)
        idxs = ntuple.indices(full3)
        ntuple.update(idxs, 7.0, 1)
        self.assertEqual(ntuple.value(full3), ntuple.value_from_indices(idxs, 1))
        self.assertEqual(ntuple.value_from_indices(idxs, 0), 0.0)

    def test_two_stages_round_trip_through_save_load(self):
        ntuple = NTupleValue(layout=LAYOUT_AD, stages=2, thresholds=(20,))
        board = Board()
        board.grid[3] = [1, 0, 1, 1, 0, 0, 1, 0]
        stage = ntuple.stage(board)
        ntuple.update(ntuple.indices(board), 4.0, stage)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "staged.json")
            ntuple.save(path)
            loaded = NTupleValue.load(path)
        self.assertEqual(loaded.stages, 2)
        self.assertEqual(loaded.thresholds, (20,))
        self.assertEqual(loaded.layout, LAYOUT_AD)
        self.assertEqual(loaded.weights, ntuple.weights)
        self.assertEqual(loaded.value(board), ntuple.value(board))

    def test_single_stage_files_without_stage_fields_load_as_one_stage(self):
        ntuple = NTupleValue()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.json")
            ntuple.save(path)
            loaded = NTupleValue.load(path)
        self.assertEqual(loaded.stages, 1)
        self.assertEqual(loaded.thresholds, ())


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
