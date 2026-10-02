"""
Testy dla #333: baner „Combo N" czytany jako klocki (przyczyna przegranej s5 p.7, `docs/seria/s5/przegrana-p7.md`).

1. Na zrzucie `kawalek_9/039_state.png` (stan po ruchu 38) most po poprawce podaje polityce planszę z `expected`, bez
   duchów (1,6),(1,7); test idzie przez reprezentację żywego mostu: obraz jako `int`, jak po `screenshot()`.
2. Gdy odczyt różni się od `expected` poza liniami wyczyszczonymi ruchem (albo ruchu nie przyjęła gra), bierzemy ekran.
3. `tools/ok_false.py` klasyfikuje wpisy `ok: false` i sumuje się do liczby tych wpisów.

Testy dla #339: napis „Perfect!" / „Combo N" na środku planszy (poza liniami wyczyszczonymi, więc `drop_banner_ghosts` go
nie łapie): `bridge.drop_banner_text` bierze `expected` w polach różnicy, ale tylko tam, gdzie zrzut pokazuje nakładkę.
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


SERIA = os.path.join(ROOT, "docs", "seria")


def wpis_i_zrzut(seria_partia, kawalek, n):
    """-> (wpis z logu, zrzut stanu po ruchu n jako `int` (jak po `bridge.screenshot()`))."""
    d = os.path.join(SERIA, seria_partia)
    with open(os.path.join(d, f"chunk{kawalek}_moves.jsonl"), encoding="utf-8") as f:
        r = next(r for r in (json.loads(line) for line in f if line.strip()) if r.get("n") == n and "move" in r)
    img = np.asarray(Image.open(os.path.join(d, f"kawalek_{kawalek}", f"{n + 1:03d}_state.png")).convert("RGB")).astype(int)
    return r, img


def plansza_decyzji(r, img):
    """Plansza, którą dostaje polityka po ruchu `r`: ten sam przebieg co w pętli mostu (`observed` z logu, tacka ze zrzutu)."""
    m = r["move"]
    board = Board()
    board.grid = [row[:] for row in r["board"]]
    pieces = [Piece(s, f"slot{j}", -1) if s else None for j, s in enumerate(r["tray"])]
    accepted = bridge.tray_consumed(pieces, m["slot"], bridge.read_tray(img))
    grid, duchy = bridge.drop_banner_ghosts(r["observed"], r["expected"],
                                            bridge.cleared_cells(board, pieces[m["slot"]], m["x"], m["y"]), accepted)
    grid, napis = bridge.drop_banner_text(img, grid, r["expected"], accepted)
    return grid, napis, accepted


class TestDropBannerText(unittest.TestCase):
    def test_perfect_adds_a_cell_that_is_not_there(self):
        # s4/p1/k22 wpis 54: „Perfect!" na wierszu 4 dodaje (4,3)
        r, img = wpis_i_zrzut("s4/partia-1", 22, 54)
        self.assertEqual([(y, x) for y in range(8) for x in range(8) if bridge.read_board(img)[y][x] != r["expected"][y][x]],
                         [(4, 3)], "read_board nadal czyta napis jako klocek (to jest przyczyna)")
        self.assertEqual(r["observed"][4][3], 1)
        grid, napis, accepted = plansza_decyzji(r, img)
        self.assertTrue(accepted)
        self.assertEqual(napis, [(4, 3)])
        self.assertEqual(grid, r["expected"])
        self.assertEqual(grid[4][3], 0)

    def test_combo_hides_a_block(self):
        # s5/p2/k4 wpis 19: „+240 Combo 39" zakrywa klocek (4,3), odczyt go gubi
        r, img = wpis_i_zrzut("s5/partia-2", 4, 19)
        self.assertEqual((r["observed"][4][3], r["expected"][4][3]), (0, 1))
        grid, napis, accepted = plansza_decyzji(r, img)
        self.assertTrue(accepted)
        self.assertEqual(napis, [(4, 3)])
        self.assertEqual(grid, r["expected"])
        self.assertEqual(grid[4][3], 1)

    def test_echo_without_overlay_keeps_the_screen(self):
        # s5/p5/k7 wpis 49: plansza bez nakładki, odczyt zgodny z ekranem, `expected` niesie stare błędy (dawny_duch+zakryte_wraca)
        r, img = wpis_i_zrzut("s5/partia-5", 7, 49)
        self.assertNotEqual(r["observed"], r["expected"])
        self.assertEqual([y for y in bridge.NAPIS_WIERSZE
                          if any(bridge.cell_flatness(img, y, c) >= bridge.NAPIS_ROZRZUT for c in range(8))], [])
        grid, napis, accepted = plansza_decyzji(r, img)
        self.assertTrue(accepted)
        self.assertEqual(napis, [])
        self.assertEqual(grid, r["observed"])
        self.assertEqual(grid, bridge.read_board(img))

    def test_flatness_separates_overlay_from_flat_cells(self):
        _, img = wpis_i_zrzut("s4/partia-1", 22, 54)
        self.assertGreaterEqual(bridge.cell_flatness(img, 4, 3), bridge.NAPIS_ROZRZUT)  # pod „Perfect!"
        self.assertLess(bridge.cell_flatness(img, 7, 0), bridge.NAPIS_ROZRZUT)  # ściana klocka
        self.assertLess(bridge.cell_flatness(img, 0, 4), bridge.NAPIS_ROZRZUT)  # puste pole

    def test_move_not_accepted_keeps_the_screen(self):
        r, img = wpis_i_zrzut("s4/partia-1", 22, 54)
        grid, napis = bridge.drop_banner_text(img, r["observed"], r["expected"], False)
        self.assertEqual((grid, napis), (r["observed"], []))

    def test_overlay_outside_banner_rows_keeps_the_screen(self):
        r, img = wpis_i_zrzut("s4/partia-1", 22, 54)
        observed = [row[:] for row in r["expected"]]
        observed[0][0] = 1 - observed[0][0]  # różnica w wierszu 0 (tam, gdzie nie ma napisu)
        grid, napis = bridge.drop_banner_text(img, observed, r["expected"], True)
        self.assertEqual((grid, napis), (observed, []))

    def test_corrected_cells_are_the_only_change(self):
        r, img = wpis_i_zrzut("s5/partia-2", 4, 19)
        grid, napis = bridge.drop_banner_text(img, r["observed"], r["expected"], True)
        zmiany = [(y, x) for y in range(8) for x in range(8) if grid[y][x] != r["observed"][y][x]]
        self.assertEqual(zmiany, napis)
        self.assertIsNot(grid, r["observed"])  # `observed` z logu zostaje surowy


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
    def test_napis_rule_measure_on_two_examples(self):
        for seria_partia, k, n in (("s4/partia-1", 22, 54), ("s5/partia-2", 4, 19)):
            plik = os.path.join(SERIA, seria_partia, f"chunk{k}_moves.jsonl")
            w = next(w for w in ok_false.wpisy_podgrup(plik) if w["n"] == n)
            self.assertEqual(ok_false.klasa_napisu(w), "napis")
            przed, po, pola = ok_false.po_zmianie(w, ok_false._obraz(w))
            self.assertEqual(pola, [(4, 3)])
            self.assertNotEqual(przed, po)
            self.assertEqual(po, w["wpis"]["expected"])


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
