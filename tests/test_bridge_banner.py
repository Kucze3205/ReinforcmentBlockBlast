"""
Testy dla #333: baner „Combo N" czytany jako klocki (przyczyna przegranej s5 p.7, `docs/seria/s5/przegrana-p7.md`).

1. Na zrzucie `kawalek_9/039_state.png` (stan po ruchu 38) most po poprawce podaje polityce planszę z `expected`, bez
   duchów (1,6),(1,7); test idzie przez reprezentację żywego mostu: obraz jako `int`, jak po `screenshot()`.
2. Gdy odczyt różni się od `expected` poza liniami wyczyszczonymi ruchem (albo ruchu nie przyjęła gra), bierzemy ekran.
3. `tools/ok_false.py` klasyfikuje wpisy `ok: false` i sumuje się do liczby tych wpisów.
"""
import json
import os
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bridge
import ok_false
from board import Board
from pieces import Piece

P7 = os.path.join(ROOT, "docs", "seria", "s5", "partia-7")


def p7_rows():
    with open(os.path.join(P7, "chunk9_moves.jsonl"), encoding="utf-8") as f:
        return {r["n"]: r for r in (json.loads(line) for line in f if line.strip()) if "move" in r}


def piece_of(tray, i):
    return [Piece(s, f"slot{j}", -1) if s else None for j, s in enumerate(tray)][i]


class TestDropBannerGhosts(unittest.TestCase):
    def setUp(self):
        self.r38 = p7_rows()[38]
        m = self.r38["move"]
        board = Board()
        board.grid = [row[:] for row in self.r38["board"]]
        self.pieces = [Piece(s, f"slot{j}", -1) if s else None for j, s in enumerate(self.r38["tray"])]
        self.cleared = bridge.cleared_cells(board, self.pieces[m["slot"]], m["x"], m["y"])
        self.expected = self.r38["expected"]

    def test_p7_move_38_clears_row_1(self):
        self.assertEqual(self.cleared, {(1, c) for c in range(8)})

    def test_live_bridge_representation_has_no_ghosts_for_the_policy(self):
        img = np.asarray(Image.open(os.path.join(P7, "kawalek_9", "039_state.png")).convert("RGB")).astype(int)
        observed, slots = bridge.read_board(img), bridge.read_tray(img)
        self.assertEqual([(y, x) for y in range(8) for x in range(8) if observed[y][x] != self.expected[y][x]],
                         [(1, 6), (1, 7)], "read_board nadal czyta baner jako klocki (to jest przyczyna)")
        accepted = bridge.tray_consumed(self.pieces, self.r38["move"]["slot"], slots)
        self.assertTrue(accepted)
        grid, ghosts = bridge.drop_banner_ghosts(observed, self.expected, self.cleared, accepted)
        self.assertEqual(ghosts, [(1, 6), (1, 7)])
        self.assertEqual(grid, self.expected)
        self.assertEqual(grid[1], [0] * 8)

    def test_move_not_accepted_keeps_the_screen(self):
        observed = [row[:] for row in self.expected]
        observed[1][6] = observed[1][7] = 1
        grid, ghosts = bridge.drop_banner_ghosts(observed, self.expected, self.cleared, False)
        self.assertEqual(grid, observed)
        self.assertEqual(ghosts, [])

    def test_difference_outside_cleared_lines_keeps_the_screen(self):
        # klocek upadł obok celu: ghosty w czyszczonym wierszu + klocek (4,4) gdzie indziej
        observed = [row[:] for row in self.expected]
        observed[1][6] = observed[1][7] = 1
        observed[4][4] = 1 - observed[4][4]
        self.assertNotIn((4, 4), self.cleared)
        grid, ghosts = bridge.drop_banner_ghosts(observed, self.expected, self.cleared, True)
        self.assertEqual(grid, observed)
        self.assertEqual(ghosts, [])

    def test_missing_cell_keeps_the_screen(self):
        observed = [row[:] for row in self.expected]
        y, x = next((y, x) for y in range(8) for x in range(8) if self.expected[y][x])
        observed[y][x] = 0
        observed[1][6] = 1
        grid, ghosts = bridge.drop_banner_ghosts(observed, self.expected, self.cleared, True)
        self.assertEqual(grid, observed)
        self.assertEqual(ghosts, [])

    def test_agreeing_read_is_untouched(self):
        grid, ghosts = bridge.drop_banner_ghosts(self.expected, self.expected, self.cleared, True)
        self.assertEqual((grid, ghosts), (self.expected, []))


class TestTrayConsumed(unittest.TestCase):
    PIECES = [Piece([[1]], "a", -1), Piece([[1, 1]], "b", -1), None]

    def test_slot_emptied(self):
        self.assertTrue(bridge.tray_consumed(self.PIECES, 0, [None, ([[1, 1]], (0, 0)), None]))

    def test_slot_still_there(self):
        self.assertFalse(bridge.tray_consumed(self.PIECES, 0, [([[1]], (0, 0)), ([[1, 1]], (0, 0)), None]))

    def test_new_deal_after_last_piece(self):
        last = [None, Piece([[1]], "a", -1), None]
        deal = [([[1]], (0, 0)), ([[1, 1]], (0, 0)), ([[1], [1]], (0, 0))]
        self.assertTrue(bridge.tray_consumed(last, 1, deal))
        self.assertFalse(bridge.tray_consumed(self.PIECES, 0, deal))


class TestOkFalseTool(unittest.TestCase):
    def test_p7_move_38_is_a_ghost_in_a_cleared_line(self):
        r38 = p7_rows()[38]
        grupa, nadmiar, brak, _ = ok_false.klasyfikuj(r38)
        self.assertEqual((grupa, nadmiar, brak), ("duchy_w_czyszczonych", [(1, 6), (1, 7)], []))

    def test_groups_sum_to_ok_false(self):
        cnt = ok_false.przejdz(os.path.join(P7, "chunk9_moves.jsonl"))
        self.assertGreater(cnt["ok_false"], 0)
        self.assertEqual(sum(cnt[g] for g in ok_false.GRUPY), cnt["ok_false"])
        self.assertGreaterEqual(cnt["duch_dotrwal"], 1)


if __name__ == "__main__":
    unittest.main()
