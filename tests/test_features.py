"""
Testy `features.py` — dla każdej cechy plansza z ręcznie policzoną wartością
oczekiwaną (issue #57).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import Board
from features import FEATURE_NAMES, features


def make_board(rows):
    """`rows`: 8 napisów po 8 znaków '0'/'1', wiersz 0 na górze."""
    board = Board()
    board.grid = [[1 if c == "1" else 0 for c in row] for row in rows]
    return board


class TestFeatureNames(unittest.TestCase):
    def test_names_match_features_length(self):
        board = Board()
        self.assertEqual(len(FEATURE_NAMES), len(features(board)))
        self.assertEqual(len(set(FEATURE_NAMES)), len(FEATURE_NAMES))


class TestOccupiedCells(unittest.TestCase):
    def test_counts_filled_cells(self):
        # 3 wiersze pełne (24), reszta pusta.
        rows = ["11111111"] * 3 + ["00000000"] * 5
        board = make_board(rows)
        self.assertEqual(features(board)[FEATURE_NAMES.index("occupied_cells")], 24)


class TestSurroundedEmpty(unittest.TestCase):
    def test_single_hole_boxed_on_all_four_sides(self):
        # Puste pole (x=4,y=2) ma zajęte wszystkie 4 sąsiedztwa; reszta planszy pusta.
        grid = [[0] * 8 for _ in range(8)]
        grid[1][4] = 1  # góra
        grid[3][4] = 1  # dół
        grid[2][3] = 1  # lewo
        grid[2][5] = 1  # prawo
        board = Board()
        board.grid = grid
        self.assertEqual(features(board)[FEATURE_NAMES.index("surrounded_empty")], 1)


class TestEmptyRegions(unittest.TestCase):
    def test_wall_splits_board_into_two_regions(self):
        # Kolumna 4 w całości zajęta dzieli planszę na dwa spójne obszary pustki.
        rows = []
        for _ in range(8):
            row = ["0"] * 8
            row[4] = "1"
            rows.append("".join(row))
        board = make_board(rows)
        self.assertEqual(features(board)[FEATURE_NAMES.index("empty_regions")], 2)


class TestLargestEmptyRectangle(unittest.TestCase):
    def test_largest_rectangle_is_three_by_two(self):
        # Wszystko zajęte poza blokiem 3 kolumny x 2 wiersze (pole 6).
        rows = []
        for y in range(8):
            row = ["1"] * 8
            if y < 2:
                row[0] = row[1] = row[2] = "0"
            rows.append("".join(row))
        board = make_board(rows)
        self.assertEqual(features(board)[FEATURE_NAMES.index("largest_empty_rect")], 6)


class TestNearFullLines(unittest.TestCase):
    def test_counts_only_rows_missing_at_most_two(self):
        # Wiersz 0 brakuje 1 pola, wiersz 1 brakuje 2, wiersz 2 brakuje 3 (nie liczy się).
        # Żadna kolumna nie brakuje <=2 (sprawdzone ręcznie poniżej).
        rows = [
            "11111110",  # brak 1
            "11111100",  # brak 2
            "11111000",  # brak 3 -> nie liczy się
        ] + ["00000000"] * 5
        board = make_board(rows)
        self.assertEqual(features(board)[FEATURE_NAMES.index("near_full_lines")], 2)


class TestPlaceableShapes(unittest.TestCase):
    def test_only_1x1_fits_a_single_empty_cell(self):
        # Cała plansza zajęta poza jednym polem (7,7) -> tylko klocek 1x1 się mieści.
        rows = ["11111111"] * 7 + ["11111110"]
        board = make_board(rows)
        self.assertEqual(features(board)[FEATURE_NAMES.index("placeable_shapes")], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
